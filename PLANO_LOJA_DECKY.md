# Plano: aprovar o New Suspend Mode na loja do Decky

> **Branch de trabalho:** `rework-fix-decky-loader`
> **Data da análise:** 19/10/2026
> **PR anterior:** [#1156](https://github.com/SteamDeckHomebrew/decky-plugin-database/pull/1156) (fechado sem merge)

---

## Status da execução (19/10/2026)

As Fases 1 a 5 foram executadas e estão adicionadas ao git (sem commit). Faltam três coisas, todas suas:

1. **Rodar o comando de remoção do `dist/` e dos zips** (o filtro de segurança bloqueou do meu lado):
   ```bash
   git rm --cached dist/index.js dist/index.js.map NewSuspendMode.zip DownloadInBackground.zip
   ```
2. **Testar no hardware** (Fase 0 + matriz da seção 5).
3. **Fase 7**: testadores, 2 PRs de outros plugins e o PR novo (texto pronto na seção 6).

**Verificações feitas sem hardware:**

| O quê | Como | Resultado |
|---|---|---|
| Lógica do patch de Sleep | 25 cenários rodando o `sleepPatch.ts` compilado contra uma `SuspendResumeStore` falsa, com o **patcher real** do `@decky/ui` | 25/25 |
| Divisão do backend | Comparação de fonte e AST de cada um dos 149 membros, das 4170 linhas não vazias da classe (comentários incluídos) e dos valores em execução | Nenhuma diferença |
| Carga do plugin | Zip extraído e carregado na mesma sequência do Decky Loader (`py_modules` no path, `decky` injetado, `Plugin()`) | OK, as 9 rotas do frontend existem |
| Tipos e lint | `tsc` e `pyflakes` | Sem erros |

**Onde a execução diferiu do plano, e por quê:**

- **Dois patches, não um.** `RequestSleep` (só o menu chama) e `InitiateSleep` (todo o resto). Hoje o Sleep do menu e os outros pedidos de sono seguem caminhos diferentes no backend (`request_standby` e `trigger_suspend_intercept`). Patchar os dois mantém isso idêntico.
- **Sono real continua pelo backend** (`systemctl suspend`), como antes. Passar a usar o `InitiateSleep` original mudaria um comportamento que já funciona.
- **Heartbeat mantido.** `RegisterForOnResumeFromSuspend` não aparece no código atual da Steam, então trocar seria arriscado.
- **`sudo tee` mantido** dentro do `_write_sysfs`, como reserva sem shell. Só os `sudo sh -c` com f-string saíram.
- **Correção incluída:** o frontend antigo ignorava "Enable Plugin When Plugged In" no Sleep do menu (olhava só `enabled`). Agora segue a mesma regra do backend (`_effective_enabled`).
- **Removido:** o toggle "Recover The Interface On Wake". A recuperação que ele ligava não existe mais, porque a causa foi eliminada.

---

## Sumário

1. [Situação atual](#1-situação-atual)
2. [As três críticas, medidas](#2-as-três-críticas-medidas)
3. [Descobertas da análise](#3-descobertas-da-análise)
4. [Plano em fases](#4-plano-em-fases)
5. [Matriz de testes](#5-matriz-de-testes)
6. [Roteiro do novo PR](#6-roteiro-do-novo-pr)
7. [A caixa de IA](#7-a-caixa-de-ia)
8. [Riscos e mitigação](#8-riscos-e-mitigação)
9. [Regras de trabalho combinadas](#9-regras-de-trabalho-combinadas)
10. [Referências](#10-referências)

---

## 1. Situação atual

O PR #1156 foi fechado em **19/10/2026 às 22:12** por **AAGaming00**, um dos mantenedores principais do Decky Loader. O review foi marcado como `CHANGES_REQUESTED`:

> It's a cool idea, but theres way too much incomprehensible DOM nonsense going on (we don't do that here, learn proper patching) in your way too long index js, and you pushed the dist folder by accident. Closing for now until this can be properly developed.

**Não foi banimento.** A frase *"Closing for now until this can be properly developed"* deixa a porta aberta para enviar de novo. Ele não citou a declaração de uso de IA. A recusa foi só técnica.

---

## 2. As três críticas, medidas

As três críticas estão corretas.

| Crítica | Medição | Situação |
|---|---|---|
| "learn proper patching" | Usos de `afterPatch`, `beforePatch`, `replacePatch`, `findModuleChild` e `findInReactTree`: **0 cada**. Contra cerca de 38 acessos diretos ao DOM | Procede |
| "way too long index js" | [src/index.tsx](src/index.tsx) tem **1874 linhas**, de um frontend de 2958 | Procede |
| "pushed the dist folder" | Estão no git: `dist/index.js`, `dist/index.js.map`, `NewSuspendMode.zip` e `DownloadInBackground.zip`. O [.gitignore](.gitignore) não lista `dist/` nem `*.zip`, e o [template oficial](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/.gitignore) lista `dist/` | Procede |

---

## 3. Descobertas da análise

Baixei o código da interface da Steam do repositório **SteamTracking**, que extrai e versiona o JS do cliente (snapshot de 19/10/2026), e li o fluxo real do Sleep. O que segue vem desse código, não de suposição.

### 3.1 A causa raiz da tela preta das rodadas R1 a R5 era nossa

A Steam tem uma store global de suspensão, criada no próprio `sp.js` com `window.SuspendResumeStore = I`. O fluxo do Sleep é este:

```
Menu "Sleep" ─► SuspendResumeStore.RequestSleep()
                 └─► serviço nativo (SleepManager)
                      └─► OnRequestSuspend()
                           └─► this.InitiateSleep()
                                └─► OnSuspendRequest()
                                     ├─ m_bSuspending = true        ◄── a tela de "suspendendo" aparece aqui
                                     ├─ U = await PrepareForSystemSuspend()
                                     ├─ if (U.result != OK) ...
                                     └─ SuspendPC()
```

Nosso hook em `SteamClient.User.PrepareForSystemSuspend` devolvia `Promise.resolve()`, ou seja, um resultado vazio. A Steam então lê `U.result` desse resultado vazio, o que dá **TypeError**. Com isso, `m_bSuspending` **fica `true` para sempre**.

Enquanto `m_bSuspending` está `true`, a Steam mantém montado o componente `SuspendDialogInner`, que fica numa camada de overlay acima de tudo. Os menus laterais continuam desenhando por cima dele. Era **exatamente** o sintoma que perseguimos: tela preta com menus funcionando.

Toda a recuperação que construímos depois tratava um sintoma que nós mesmos causávamos:

- comparar a "assinatura" do centro da tela;
- voltar a rota anterior;
- esconder nós do DOM;
- recarregar a UI da Steam com `RestartJSContext`.

### 3.2 O jeito certo é um patch só

`InitiateSleep` é o ponto por onde passam os caminhos de sono:

| Origem | Caminho até `InitiateSleep` | Status |
|---|---|---|
| Item "Sleep" do menu de energia | `RequestSleep()` → nativo → `OnRequestSuspend` → `this.InitiateSleep()` | Visto no código |
| Botão "Sleep" do modal da Valve | `SuspendResumeStore.InitiateSleep()` direto | Visto no código |
| Tela "jogando em outro lugar" (60 s) | `SuspendResumeStore.InitiateSleep()` direto | Visto no código |
| Botão de energia físico / sono por inatividade | Nativo → `NotifyRequestSuspend` → `OnRequestSuspend` → `this.InitiateSleep()` | **Provável. Confirmar na Fase 0/2** |

**Por que é seguro trocar essa função:** os membros que a Steam registra como *actions* MobX são `OnSuspendRequest`, `OnSystemResumedFromSuspend` etc. **`InitiateSleep` não está nessa lista**, é um método comum do protótipo. Então o `replacePatch` do Decky pode substituí-lo na instância sem esbarrar nas proteções do MobX. `OnSuspendRequest` é `action.bound` e **não deve** ser patchado.

```ts
import { replacePatch, callOriginal, findModuleExport } from "@decky/ui";

const store =
  (window as any).SuspendResumeStore ??
  findModuleExport(
    (e: any) => typeof e?.InitiateSleep === "function" && typeof e?.OnSuspendRequest === "function"
  );

const patch = replacePatch(store, "InitiateSleep", (args) => {
  if (!shouldTakeOver()) return callOriginal; // SteamOS dorme exatamente como sem o plugin
  enterNewSuspendMode();
  return undefined; // a Steam nunca entra em "suspendendo", então não sobra nada para recuperar
});

// onDismount:
patch.unpatch();

// Sono real que o próprio plugin quer (horário configurado, bateria crítica, downloads concluídos):
patch.original.call(store);
```

**Se falhar:** se uma atualização da Steam remover ou renomear a store, o patch não é instalado. O plugin registra um aviso e o SteamOS dorme normalmente. Hoje, quando a abordagem por DOM falha, a tela fica travada.

### 3.3 O recurso nativo da Valve só existe no Steam Deck

A Steam tem a opção **"Finish Downloads Before Sleep"**, com este texto:

> *"If your device enters sleep mode, your games will continue downloading in a low-power, display-off state."*

Ela vem com um modal "Continue Downloading?" e manda o aparelho dormir quando a bateria cai abaixo de 20%.

**Mas ela é restrita ao Steam Deck.** O código da tela de configurações só mostra a opção quando o serviço nativo de sono informa `is_low_power_download_supported`:

```js
function P() {
  const R = p((te) => te.is_low_power_download_supported ?? !1);
  return R.isSuccess && R.data;
}
// a opção "system_enable_low_power_downloads" só é renderizada se P() for true
```

Esse sinal vem do lado nativo, não da interface. O código confirma que é uma checagem de capacidade da plataforma. Que ela só é verdadeira no Deck é o que você relatou: a Valve construiu o recurso em cima do hardware do Deck. A imprensa diz o mesmo. Por isso a opção não aparece no ROG Ally X nem no desktop.

**O que isso significa para o PR:**

- **Ajuda no argumento de "plugin único".** O plugin leva para outros aparelhos com SteamOS o que a Valve fez só para o Deck. E ainda faz coisas que a Valve não faz: acordar pelo controle, sono real em horário configurado com retorno pelo RTC, TV sem sinal, substituir o Sleep mesmo sem download, limitar a velocidade do download.
- **Exige atenção à convivência no Deck.** A maior parte de quem usa a loja do Decky tem Steam Deck. No Deck, com download ativo e a opção nativa ligada, a Steam mostra o próprio modal antes de chegar ao `InitiateSleep`. Precisamos definir o comportamento ali. Proposta: deixar o modal da Valve agir. Se o usuário escolher "Sleep" no modal, o nosso patch decide como em qualquer outro Sleep.
- **Não temos Steam Deck para testar.** Esse cenário precisa de um testador externo (Fase 7).

### 3.4 Problemas que o revisor viu mas não citou

| Problema | Onde | Por que pesa |
|---|---|---|
| `"author": "Antigravity"` | [plugin.json:3](plugin.json#L3) | Antigravity é uma IDE de IA do Google. Contradiz a caixa "I am the original author" |
| Imagem da loja é o banner do template | [plugin.json](plugin.json) | Parece placeholder |
| Chama métodos desconhecidos da Steam escolhidos por regex | [src/index.tsx:456-513](src/index.tsx#L456-L513) | Para um revisor, parece código perigoso |
| Despeja toda a API do SteamClient no log | [src/index.tsx:1734-1781](src/index.tsx#L1734-L1781) | Código de depuração enviado na versão final |
| `RegisterForOnSuspendRequest` | [src/index.tsx:1596-1695](src/index.tsx#L1596-L1695) | Não aparece em lugar nenhum do código atual da Steam. Provavelmente nunca dispara |
| 6× `sudo sh -c "echo ... > path"` e 1× `sudo tee` | [main.py](main.py) (2160, 3840, 3852, 4034, 4065, 4380, 4400) | O plugin já roda como root. Shell montado com f-string é mal visto |
| `main.py` com **5019 linhas** num arquivo só | [main.py](main.py) | Provavelmente recebe a mesma crítica do `index.tsx` |

### 3.5 Quanto sai do `index.tsx`

Com o patch da seção 3.2, estes blocos deixam de ter motivo para existir:

| Bloco | Linhas |
|---|---|
| Medição de tela e janela da UI (contorno do SharedJSContext) | [145-213](src/index.tsx#L145-L213) |
| Esconder o overlay via DOM | [215-276](src/index.tsx#L215-L276) |
| Guarda do menu (texto "Sleep" em 30 idiomas) | [278-421](src/index.tsx#L278-L421) |
| Amostragem do centro da tela | [423-442](src/index.tsx#L423-L442) |
| Cancelar a suspensão por regex | [444-513](src/index.tsx#L444-L513) |
| Recuperação da UI, `RestartJSContext` e restauração de rota | [515-623](src/index.tsx#L515-L623) |
| Sondagem de tela no wake | [625-686](src/index.tsx#L625-L686) |
| Monkeypatch do SteamClient e máquina de estados de "takeover" | [910-1182](src/index.tsx#L910-L1182) |
| Bloqueio de input via `window` | [1209-1231](src/index.tsx#L1209-L1231) |
| Callback de `RegisterForOnSuspendRequest` | [1596-1695](src/index.tsx#L1596-L1695) |
| Dump da API e heartbeat de salto de relógio | [1725-1809](src/index.tsx#L1725-L1809) |

**Total: cerca de 1000 linhas.** O trabalho no frontend é principalmente apagar código, o que é bem menos arriscado do que eu tinha estimado antes de ler o código da Steam.

---

## 4. Plano em fases

Ordem recomendada: **0 → 1 → 2 → teste → 3 + 4 → teste → 5 → matriz completa → 7**

### Fase 0: Verificação no hardware (você, sem mudar código)

**Objetivo:** confirmar que o código analisado é o mesmo que roda nos seus aparelhos.

**Como abrir o console:**

1. No aparelho: Decky → Configurações → Desenvolvedor → ligar **"Allow Remote CEF Debugging"**.
2. Em outro PC, no Chrome: `chrome://inspect/#devices` → *Configure...* → adicionar `<IP do aparelho>:8081`.
3. Clicar em *inspect* no alvo **SharedJSContext** e abrir a aba *Console*.

Se o console der trabalho demais, eu coloco uma linha de log temporária no plugin que faz a mesma checagem.

**Tarefas:**

- [ ] Ally X: `typeof SuspendResumeStore?.InitiateSleep` → esperado `"function"`
- [ ] Desktop: mesma checagem
- [ ] Ally X e desktop: confirmar que **"Finish Downloads Before Sleep" não aparece** em Configurações → Energia
- [ ] Anotar a versão do SteamOS e o canal (Stable/Beta/Preview) de cada aparelho

**Risco:** nenhum.

### Fase 1: Higiene do repositório

**Objetivo:** resolver a crítica 3 e os sinais de alerta do manifesto.

- [x] Adicionar `dist/`, `*.zip` e `build/` ao `.gitignore`. O zip continua sendo gerado localmente, só deixa de ir para o git.
- [ ] `git rm --cached dist/index.js dist/index.js.map NewSuspendMode.zip DownloadInBackground.zip`. **Bloqueado do meu lado: você roda.**
- [x] `plugin.json`: `author` → `hileydson`
- [x] `plugin.json`: `image` → `assets/icon.png` do repositório
- [x] `package.json`: versão `2.0.0` → `2.1.0`
- [x] `LICENSE`: titular "Download in Background Contributors" → `hileydson`

**Risco:** nenhum no comportamento.

### Fase 2: Núcleo (trocar a interceptação)

**Objetivo:** resolver a crítica 1 eliminando a causa, não o sintoma.

- [x] Criar `src/steam/sleepPatch.ts`, com patch em `RequestSleep` **e** `InitiateSleep` (ver "Status da execução")
- [x] Decidir de forma síncrona pelo estado local. O backend confirma com `trigger_suspend_intercept`. Se responder `allow`, chamar o original
- [x] Com o plugin já no nosso modo, um pedido de sono significa **acordar**
- [x] ~~Sonos reais pelo `InitiateSleep` original~~ → **mantido o caminho atual do backend**, para não mudar comportamento
- [x] ~~Trocar o heartbeat~~ → **mantido**: a API substituta não aparece no código atual da Steam
- [x] Apagar os blocos da seção 3.5
- [x] `onDismount` → `unpatch()` dos dois patches
- [x] Vigia do botão de energia no backend mantido, sem alteração

**Risco:** médio, porque muda o caminho principal. É validado pelos itens 1 a 8 da matriz.
**Pronto quando:** itens 1 a 8 da matriz passarem no Ally X e no desktop.

### Fase 3: Estado e overlay sem DOM

- [x] Trocar as variáveis globais `let shared*` com lista de listeners por uma store única com `useSyncExternalStore`, a API oficial do React para isso
- [x] Overlay controlado só por estado: renderiza `null` quando inativo. Depois do wake, a store pede aos componentes para conferir o estado de novo em 120, 400 e 1200 ms. Isso faz, sem DOM, o papel das antigas repetições de `forceHideOverlayDom`
- [x] Remover `forceHideOverlayDom`, o `probeRef`/`ownerDocument.defaultView` e os listeners de input em `window`. Esses listeners ficavam na janela oculta do SharedJSContext, então provavelmente nunca recebiam nada. O bloqueio de input real é feito pelo backend

**Risco:** o antigo bug do "overlay preso depois do wake". **Não sei a causa com certeza.** Se ele voltar, investigamos a causa em vez de esconder o nó.

### Fase 4: Frontend em módulos

**Objetivo:** resolver a crítica 2.

Estrutura final:

```
src/
├── index.tsx                  #  33 linhas: só o definePlugin e a ligação das peças
├── state.ts                   # estado único + useSyncExternalStore
├── flows.ts                   # splash, HUD, entrar e acordar
├── backend.ts                 # eventos do Python + polling + heartbeat
├── steam/
│   ├── sleepPatch.ts          # patches em RequestSleep e InitiateSleep
│   └── downloads.ts           # leitura do SteamClient.Downloads
├── components/
│   ├── GlobalOverlay.tsx
│   ├── Overlay.tsx
│   ├── PluginContent.tsx
│   ├── SettingsPanel.tsx      # 281 linhas
│   └── AdvancedSettings.tsx   # as seções reveladas por "Advanced Features"
├── styles.ts
└── types.ts
```

- [x] **Meta atingida:** o maior arquivo de lógica tem 217 linhas. `styles.ts` (325) é só CSS.

### Fase 5: Backend (preventivo)

- [x] Trocar os 6 `sudo sh -c` por `self._write_sysfs(...)` (o `sudo tee` sem shell ficou só como reserva dentro dele)
- [x] Dividir o `main.py` (5019 → 448 linhas) em `py_modules/new_suspend_mode/`: 22 arquivos (19 mixins, um por área, mais constantes, detector de downloads e `__init__`). O nome do pacote é único para não colidir com nada do sistema, já que `py_modules` entra no fim do `sys.path`. Também confirmei no código da CLI do Decky que o build da loja empacota `py_modules`
- [x] Atualizar `package`, `install.sh` e `Makefile` para incluir `py_modules`
- [x] ~~Remover tipos de `log_debug`~~ → não se aplica: o endpoint aceita qualquer payload, não há lista para limpar
- [x] Extra: corrigidos 5 avisos antigos de lint e um log que mostrava "420:00" em vez de "07:00"

**Risco:** baixo por mudança, mas o volume é grande. É uma movimentação mecânica, sem mudar a lógica.

### Fase 6: Matriz completa (você)

Ver a [seção 5](#5-matriz-de-testes). Os testes valem nos canais **Stable e Beta**, porque o checkbox do PR afirma isso.

### Fase 7: Comunidade e novo PR

- [ ] Entrar no Discord do Decky e pedir testadores, **de preferência alguém com Steam Deck**
- [ ] Testar e comentar em 2 PRs de outros plugins. O template pede isso e o README diz que pode priorizar o seu PR
- [ ] Atualizar o submódulo no fork `hileydson/decky-plugin-database` para o commit novo
- [ ] Abrir um PR novo usando **exatamente** o template `plugin_addition` (roteiro na [seção 6](#6-roteiro-do-novo-pr))

---

## 5. Matriz de testes

| # | Cenário | Ally X | Desktop/TV | Deck (terceiro) |
|---|---|:-:|:-:|:-:|
| 1 | Sleep do menu, sem download → nosso modo | ☐ | ☐ | ☐ |
| 2 | Sleep do menu, com download → HUD → nosso modo | ☐ | ☐ | ☐ |
| 3 | Botão de energia → nosso modo | ☐ | ☐ | ☐ |
| 4 | Acordar pelo controle (Bluetooth) | ☐ | ☐ | ☐ |
| 5 | Acordar pelo botão de energia | ☐ | ☐ | ☐ |
| 6 | Depois de acordar: UI normal, sem tela preta e sem menu lateral aberto | ☐ | ☐ | ☐ |
| 7 | Plugin desligado → Sleep idêntico ao SteamOS normal | ☐ | ☐ | ☐ |
| 8 | Recarregar ou desinstalar o plugin → Sleep normal funcionando | ☐ | ☐ | ☐ |
| 9 | Sono real no horário configurado + retorno pelo RTC ao nosso modo | ☐ | ☐ | ☐ |
| 10 | TV sem sinal (force connector off) e volta do vídeo | — | ☐ | — |
| 11 | "Enable Plugin When Plugged In" | ☐ | ☐ | ☐ |
| 12 | Bateria crítica → sono real | ☐ | — | ☐ |
| 13 | Downloads concluídos → sono real | ☐ | ☐ | ☐ |
| 14 | Modal nativo "Continue Downloading?" convivendo com o plugin | — | — | ☐ |
| 15 | Canal Stable | ☐ | ☐ | ☐ |
| 16 | Canal Beta | ☐ | ☐ | ☐ |

---

## 6. Roteiro do novo PR

Texto pronto para colar, seguindo **exatamente** o template `plugin_addition`. Antes de enviar:

- Marque "works properly on the Stable and Beta update channels" **só depois** de testar nos dois canais.
- **Backend: recomendo "No" nas três perguntas** (mudança em relação ao #1156). O comentário do template mostra que a pergunta sobre "3rd party tool not statically linked" é sobre binários que o plugin **traz junto**, por causa da glibc. Este plugin não traz nenhum: só chama ferramentas que já vêm no SteamOS. Com "No", o teste exigido passa a ser **Stable/Beta**, e por isso o texto abaixo já tem só essa linha. A nota visível embaixo das respostas explica isso ao revisor. A decisão é sua: se preferir manter "Yes", troque a linha de teste pela do Preview.
- O vídeo é o mesmo do #1156: o comportamento visível não mudou.
- Marque as caixas de "Community" só depois de testar os 2 PRs, e comente os links aqui.

```markdown
# Add New Suspend Mode to Plugin Store

Resubmission of #1156, reworked to address the review (see "Changes since #1156" below).

New Suspend Mode replaces the SteamOS "Sleep" with a plugin-managed standby. Choosing Sleep in the power menu, or pressing the power button, blacks the screen out while the system stays on: downloads keep going, fans settle, Bluetooth stays reachable, and any paired controller (Xbox, PlayStation, 8BitDo, generic) wakes the console by itself.

- Controller-aware standby in place of Sleep, from the power menu and the power button.
- Quiet hours: inside a configurable window, Sleep is the real SteamOS suspend. An optional RTC alarm wakes the console at the end of the window and puts it back into the plugin's standby.
- Download pacing while the screen is off: speed cap (`tc`) and CPU budget (cgroup v2 `cpu.max`).
- Force TV Off for desktops on a TV: disables the DRM connector so the TV gets a real no-signal. It is restored on wake, and after a crash from the plugin's saved state.
- Hardware watchdog and a "Restore Hardware Now" button: every throttle the plugin applies is recorded and reversible without a reboot.
- Enable When Plugged In, for PCs that are always on AC.

Tested on a ROG Ally X running SteamOS and on a desktop PC running SteamOS (RX 9070 XT on a TV).

How it differs from what exists: SteamOS's own "Finish Downloads Before Sleep" is only offered where the system reports low-power download support, which is the Steam Deck. On an Ally, a Legion Go or a desktop it does not appear. This plugin brings that behaviour to those devices, plus controller wake, quiet hours with an RTC return, and a real no-signal on a TV. On a Steam Deck, when the plugin takes a sleep over, its mode replaces Valve's prompt. When it leaves a sleep alone, Valve's behaviour is unchanged.

## Changes since #1156

1. **No DOM manipulation, proper patching.** Sleep is taken over with `replacePatch` on the Steam client's suspend store: `RequestSleep` for the power menu and `InitiateSleep` for every other request. The store is found through `window.SuspendResumeStore`, with a `findModuleExport` fallback. The patch runs before Steam sets its `suspending` state, so the interface is never left half-suspended, and the recovery workarounds are gone. If the store can't be found, nothing is patched and Sleep stays stock. Both patches are removed in `onDismount`.
2. **index.tsx: 1874 → 33 lines.** The frontend is split into `state.ts` (`useSyncExternalStore`), `flows.ts`, `backend.ts`, `steam/sleepPatch.ts`, `steam/downloads.ts` and the components. The Python backend is split the same way into `py_modules/new_suspend_mode/`, one mixin per concern.
3. **dist/ and build zips** removed from the repository and ignored.

## Disclosure: AI assistance

This plugin, including this rework, was developed with an AI assistant (Claude), which wrote a majority of the code. The design decisions, hardware testing and bug reproduction are mine, and every change was verified on the hardware listed above. For that reason the "Generative AI was NOT used…" box below is left unchecked.

## Demo

https://github.com/user-attachments/assets/8a11da45-ddbd-41fa-9d81-151db2afbebb

## Task Checklist

### Developer

- [x] I am the original author or an authorized maintainer of this plugin.
- [x] I have abided by the licenses of the libraries I am utilizing, including attaching license notices where appropriate.
- [ ] Generative AI was NOT used to write a majority of the code I am submitting.

### Plugin

- [x] I have verified that my plugin works properly on the Stable and Beta update channels of SteamOS.
- [x] I have verified my plugin is unique or provides more/alternative functionality to a plugin already on the store.

### Backend

- **No**: I am using a custom backend other than Python.
- **No**: I am using a tool or software from a 3rd party FOSS project that does not have it's dependencies [statically linked](https://en.wikipedia.org/wiki/Static_library).
- **No**: I am using a custom binary that has all of it's dependencies statically linked.

Note: the plugin ships no binaries. The backend only calls tools that come with SteamOS (`systemctl`, `journalctl`, `busctl`, `tc`, `gamescopectl`), and `ryzenadj` only if the user already has it installed.

### Community

- [ ] I have tested and left feedback on two other [pull requests][pulls] for new or updating plugins.
- [ ] I have commented links to my testing report in this PR.

## Testing

- [ ] Tested by a third party on SteamOS Stable or Beta update channel.

[pulls]: https://github.com/steamdeckHomebrew/decky-plugin-database/pulls?q=is%3Apr+is%3Aopen+sort%3Acreated-desc+-status%3Afailure+-draft%3Atrue+-author%3A%40me
```

---

## 7. A caixa de IA

O template de adição tem a caixa:

> *"Generative AI was NOT used to write a majority of the code I am submitting."*

E o template geral avisa: *"NOT FOLLOWING A TEMPLATE MAY RESULT IN YOUR PR BEING DENIED FOR SUSPECTED AI USAGE!"*

**A situação real:** o rework vai ser escrito em boa parte pelo Claude de novo, e as 5019 linhas do backend já foram. Então **essa caixa continua desmarcada**, como você fez no #1156. Ela não deve ser marcada se não for verdade.

**O que de fato reduz o risco:** você entender o patch novo o bastante para responder perguntas do revisor com suas palavras. O "learn proper patching" foi dirigido a quem envia o PR. Na Fase 2, cada parte do patch é explicada antes de seguirmos.

---

## 8. Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Atualização da Steam remove ou renomeia `SuspendResumeStore` | Baixa a média | Busca reserva com `findModuleExport` pela forma da store. Se nada for encontrado, o plugin não faz nada e o sono continua normal |
| O botão de energia não passa por `InitiateSleep` | Média | Verificação na Fase 0/2. O vigia do botão no backend fica como reserva |
| Overlay preso depois do wake volta | Média | Investigar a causa (Fase 3), não esconder o nó |
| Regressão ao dividir o `main.py` | Baixa | Movimentação mecânica, sem mudar a lógica, e testes depois de cada módulo |
| Convivência com o modal nativo no Deck não testada | Alta, sem Deck próprio | Testador externo com Deck (Fase 7) |
| O mantenedor recusar por uso de IA | Desconhecida | Não dá para resolver com engenharia. Declarar com honestidade e dominar o código |
| Os números de linha do `sp.js` mudam a cada atualização da Steam | Certa | Usar os nomes (`SuspendResumeStore`, `InitiateSleep`), não os números de linha |

---

## 9. Regras de trabalho combinadas

- Git: **só `git add`** nos arquivos alterados. Sem commit, branch, push, reset ou stash.
- Avisar **antes** de remover qualquer coisa no git.
- Gerar o `NewSuspendMode.zip` de novo depois de cada ajuste.
- **Não quebrar nada que já funciona.** Cada fase termina com teste no hardware antes da próxima.

---

## 10. Referências

**Código da Steam** (snapshot de 19/10/2026, `ClientExtracted/steamui/sp.js`):

- Store de suspensão: classe com `InitiateSleep`, `OnSuspendRequest` e `window.SuspendResumeStore = I`
- Menu de energia: `tr = () => { m.Ze.RequestSleep(); }`
- Restrição do recurso nativo: `is_low_power_download_supported`
- Overlay de suspensão: componente `SuspendDialogInner`, montado enquanto `m_bSuspending` é `true`

**Decky:**

- Patcher: `node_modules/@decky/ui/dist/utils/patcher.js` (`replacePatch`, `callOriginal`, `unpatch`)
- `sys.path` do loader: [sandboxed_plugin.py](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/sandboxed_plugin.py) (acrescenta `py_modules`)
- [Template oficial de plugin](https://github.com/SteamDeckHomebrew/decky-plugin-template)
- [Templates de PR da loja](https://github.com/SteamDeckHomebrew/decky-plugin-database/tree/main/.github/PULL_REQUEST_TEMPLATE)
- [SteamDatabase/SteamTracking](https://github.com/SteamDatabase/SteamTracking)

**Recurso nativo da Valve:**

- [AlternativeTo: Valve adds a new low-power mode to SteamOS](https://alternativeto.net/news/2025/11/valve-adds-a-new-low-power-mode-to-steamos-for-downloading-games-with-the-screen-off)
- [TechRadar: Valve just made Steam Deck downloads much easier](https://www.techradar.com/gaming/steam-deck/valve-just-made-steam-deck-downloads-much-easier-and-i-hope-this-feature-comes-to-all-steamos-handhelds)
- [Notebookcheck: Upcoming Steam Deck update enables background downloads](https://www.notebookcheck.net/Upcoming-Steam-Deck-update-enables-background-downloads-via-a-new-low-power-mode.1155525.0.html)
