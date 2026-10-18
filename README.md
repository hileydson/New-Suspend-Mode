# 🚀 Download in Background (Decky Loader Plugin)

<p align="center">
  <img src="assets/icon.svg" width="128" height="128" alt="Download in Background Icon" />
</p>

<p align="center">
  <b>Mantenha seus downloads do Steam ativos em segundo plano com a tela apagada e economia máxima de bateria no SteamOS!</b>
</p>

---

## 🇧🇷 Português

### 💡 O que o plugin faz?

Quando você está baixando jogos no Steam Deck e aciona a ação de suspender (botão Power ou menu de energia):
1. **Intercepta a Suspensão:** Não deixa o console entrar em suspensão imediatamente se houver downloads em andamento. O estado do download é relido **no instante** em que você pede para suspender — então pausar e apertar o Power logo em seguida já conta como pausado, sem esperar o próximo ciclo de verificação.
2. **Exibe o Status do Download (HUD):** Mostra um card elegante e translúcido na tela com o nome do jogo, velocidade atual (MB/s), barra de progresso (%), tempo restante e nível da bateria com uma contagem regressiva de alguns segundos (padrão: 5s, configurável).
3. **Apaga a Tela & Economia Máxima:**
   - Reduz o brilho físico da luz de fundo (backlight) para `0` (LCD).
   - Exibe uma camada 100% preta pura (`#000000`), desligando totalmente os pixels em modelos OLED.
   - Aplica perfil de economia de energia na CPU (`power-saver` / governor `powersave`).
   - Trava a GPU na frequência mínima (200 MHz).
   - Muta o áudio para evitar sons de notificações ou do sistema.
4. **Bloqueio Total de Botões:** Enquanto a tela está apagada, **nenhum** botão do console é registrado. Isso é feito com o `inhibited` do input core do kernel (`/sys/class/input/inputN/inhibited`), que descarta o evento antes de qualquer programa recebê-lo — inclusive programas que já capturaram o dispositivo com exclusividade, como o Steam Input. Apenas o botão **Power** continua vivo.
5. **Download em Ritmo Calmo (ventoinhas paradas):** O limite de clock sozinho não esfria nada, porque o Steam usa todo ciclo que recebe. Então o plugin limita os **bytes por segundo** (policer de ingress via `tc`) e o **orçamento de CPU** do Steam (cota `cpu.max` no cgroup dele). Menos dados por segundo = menos descompressão, menos escrita no SSD, menos calor. O download demora mais e o console fica frio, no estilo de um console portátil.
6. **Regras Inteligentes de Auto-Suspensão:**
   - 🔋 **Bateria Baixa (&le; 15%):** Se a bateria cair para 15% (ou limite configurado) enquanto estiver na bateria, o console restaura o estado e entra em suspensão real para evitar esgotamento total da bateria.
   - 🏁 **Downloads Concluídos:** Quando todos os downloads terminarem (fila vazia por alguns segundos), o console entra automaticamente em suspensão real. *(Não acontece no Modo Standby — veja abaixo.)*
7. **Retomada Instantânea:** Ao apertar o botão **Power**, a tela acende imediatamente e todos os perfis de energia, áudio e input voltam ao normal. Qualquer menu que um botão perdido tenha aberto é fechado automaticamente.
8. **Nunca Deixa o Sistema Lento:** Tudo que o plugin altera é restaurado em etapas isoladas — uma falha em qualquer etapa não pula as outras — com verificação forçada no final e um arquivo de estado em disco. Se o plugin morrer com a tela apagada, o próximo carregamento desfaz a sessão inteira, **sem precisar reiniciar o console**.

---

### 🎮 Modo Standby (desligar e acordar com o controle)

Opção nova e opcional (desligada por padrão). Com ela ativada, **o sleep do SteamOS é substituído** pelo **Modo Standby**: a tela apaga, o consumo cai ao mínimo, o download (se houver) continua, e o console fica esperando um controle pedir ele de volta — igual a um console de mesa.

Isso vale tanto para o **botão Power físico** quanto para a opção **Sleep** escolhida à mão no menu de energia do SteamOS. São dois caminhos bem diferentes:

- **Botão Power:** o plugin pega o evento no próprio dispositivo de hardware (`EVIOCGRAB` no botão ACPI), então nem o SteamOS nem a Steam chegam a saber que ele foi apertado.
- **Menu de energia:** o plugin captura a **ativação do próprio item "Suspender"**, na fase de captura do evento, **antes** de o handler da Steam rodar. Esse é o ponto inteiro: o botão Power funciona porque a Steam nunca fica sabendo que você pediu para dormir, então não há nada que ela faça com a interface dela e nada para desfazer depois. Interceptar os métodos que ela chama no **fim** do handler era tarde demais. O item é identificado pelo **texto** dele (em vários idiomas, com acentos normalizados), e só quando o plugin fosse assumir o sleep de qualquer forma — com o plugin desligado ou ocioso, o menu se comporta exatamente como sempre. Capturado, o plugin chama a **mesma função do backend** que o botão Power chama. Os métodos do cliente Steam continuam envolvidos como segunda linha de defesa.
- **Métodos do cliente Steam** (segunda linha) São **dois**, e o segundo foi o que demorou a aparecer: a Steam chama `SteamClient.User.PrepareForSystemSuspend()` — que suspende os jogos em execução e coloca a interface no estado de "dormindo" — **antes** de chamar `SteamClient.System.SuspendPC()`. Interceptar só o `SuspendPC` impedia a suspensão mas deixava a Steam preparada para uma que nunca aconteceria, e nada jamais chamava o `ResumeSuspendedGames()` que desfaz isso: a interface voltava pela metade, com a tela preta e os menus funcionando. Agora os dois são interceptados, uma suspensão vira **uma** decisão só (as chamadas seguintes são seguradas até a resposta), e se a decisão for "não é caso meu" todas são liberadas na ordem original. Na volta, o `ResumeSuspendedGames()` é chamado de qualquer forma, como a Steam faria num resume de verdade.

Esse "antes" é o ponto crítico. Bloquear a suspensão mais embaixo — com um inibidor do logind, ou mascarando `sleep.target` — chega tarde: a Steam já iniciou a sequência dela e apagou a tela, a suspensão falha, e a sessão fica **presa numa tela preta acesa** sem como voltar. Por isso nada é mascarado no systemd; se o plugin decidir que não é caso dele agir, o método original é chamado e o SteamOS suspende exatamente como sempre, com a animação dele.

**Na volta**, o plugin tira o overlay preto da tela **à mão**, sem depender do React. Essa era a causa real da tela preta com os menus funcionando: o estado dizia que o console tinha acordado, mas o `<div>` preto continuava no documento, em z-index 9999999, porque aquele componente não voltou a renderizar. Os menus funcionavam porque a Steam move o foco com a navegação interna dela, que não passa por eventos de DOM — então desenhavam por cima do retângulo preto do próprio plugin. Agora o nó é escondido na hora e de novo em 120ms, 400ms e 1,2s, e o esconder é desfeito toda vez que o modo é acionado. Além disso o plugin desfaz a parte dele (hardware restaurado) e, se a interface da Steam tiver saído do lugar quando o Sleep foi clicado, **volta a rota de onde ela estava**. Se a Steam não mexeu na interface, nada é navegado. A limpeza da volta é uma função só, usada pelos três caminhos que podem acordar o console (botão, evento do backend e sincronização do poll) — antes era copiada três vezes, e duas das cópias esqueciam de limpar o splash e o estado de standby.

**O que aparece na tela depende de qual recurso está em jogo:**

| Situação | O que o plugin faz |
| --- | --- |
| Download ativo (com ou sem o standby ligado) | Mostra o **card do download** (nome, velocidade, progresso, contagem regressiva) e depois apaga |
| Standby ligado, **sem** download ativo | Mostra o **logo do plugin com "New Suspend Mode"** por alguns segundos e depois apaga |
| Standby desligado, sem download | Não interfere: o SteamOS suspende normalmente, com a animação dele |

Ou seja: basta **um dos dois** recursos estar em jogo para o nosso modo substituir o sleep original. Com os dois ligados, o nosso modo é sempre usado. O tempo do logo na tela usa o mesmo ajuste do HUD de download (padrão 5s; em 0s entra na hora).

**O controle Bluetooth é desconectado ao entrar no modo.** Dois motivos: o controle se desliga em vez de gastar bateria ao lado de um console que está "desligado", e um controle que continua conectado nunca poderia gerar o evento de conexão que deveria acordar o console. Reconexões automáticas nos primeiros 12 segundos são ignoradas, para o console não acordar sozinho logo depois de apagar.

A desconexão é feita **via D-Bus** (`org.bluez.Device1.Disconnect`, pelo `busctl`), e não pelo `bluetoothctl`: o `bluetoothctl` cai no shell interativo dele quando não gosta de um argumento e fica bloqueado lendo o stdin até o timeout matá-lo — era assim que a desconexão falhava calada e o controle continuava ligado. O `bluetoothctl` ficou só como plano B, e com o stdin fechado. O endereço do controle é descoberto por dois caminhos (o campo `uniq`/`phys` do dispositivo de input e a lista de pareados do próprio bluez), então um controle que não expõe o endereço no input ainda é encontrado. **Fone e teclado Bluetooth nunca são desconectados** — só o que o bluez identifica como controle (`input-gaming`).

**Como o console volta:**

| Tipo de controle | O que acorda o console |
| --- | --- |
| 🔵 **Bluetooth** | **Só conectar.** O Bluetooth fica ligado no standby, então basta ligar um controle já pareado. Não precisa apertar nada. |
| 🔌 **USB / dongle** | **Apertar um botão:** Guide/Home (o botão do meio), **Select** ou **Start**. Só conectar não acorda. |
| 🎮 **Controle embutido** (Steam Deck / ROG Ally) | **Não acorda.** Os botões do próprio console continuam bloqueados de propósito. Só o botão **Power**. |

**Detalhes importantes:**

- **"Shut Down" do menu da Steam continua desligando de verdade.** O plugin intercepta o botão Power e o "Sleep", não o desligamento real — então você nunca fica sem como desligar o console.
- **O standby consome bateria**, porque o console continua ligado (é o que permite acordar com o controle). A regra de bateria baixa protege: ao atingir o limite configurado, ele cai para uma suspensão real.
- **Como o controle é lido:** o plugin tenta pegar o controle com exclusividade (`EVIOCGRAB`), o que é o caso ideal — nós vemos os botões e o Steam não vê nada. Se o Steam já tiver capturado o controle, o plugin inibe o evdev dele (para nenhum botão agir na interface sem você ver) e passa a ler os relatórios `hidraw` do controle, que o inhibit não bloqueia. Se o controle não permitir nenhum dos dois, isso é registrado no log e aquele controle não acorda o console.
- O painel do plugin mostra `STANDBY` quando está nesse modo.

---

### 📦 Estrutura do Projeto

```
Steamdeck Plugin/
├── assets/                  # Ícones PNG e SVG do plugin
│   ├── icon.png
│   └── icon.svg
├── dist/                    # Bundle compilado do frontend
│   ├── index.js
│   └── index.js.map
├── src/                     # Código fonte TypeScript / React
│   ├── components/
│   │   ├── Overlay.tsx      # HUD de download e tela preta
│   │   └── SettingsPanel.tsx# Painel do menu Quick Access (QAM)
│   ├── index.tsx            # Ponto de entrada do plugin Decky
│   ├── styles.ts            # Estilos CSS / Glassmorphism
│   └── types.ts             # Tipos TypeScript
├── .github/workflows/       # Workflow de CI/CD para GitHub Releases
│   └── build.yml
├── install.sh               # Script de instalação direta no Steam Deck
├── Makefile                 # Automação de compilação e empacotamento
├── package.json             # Dependências frontend (@decky/ui, @decky/api)
├── plugin.json              # Metadados do plugin Decky (root flag ativada)
├── main.py                  # Backend Python (inhibit, backlight, power, battery)
├── tsconfig.json            # Configuração TypeScript
├── rollup.config.js         # Bundler Rollup (@decky/rollup)
└── DownloadInBackground.zip # Arquivo pronto para instalar no Decky Loader!
```

---

### 🛠️ Como Instalar e Testar no Steam Deck

#### Método 1: Pelo arquivo ZIP (Mais simples)
1. Copie o arquivo gerado `DownloadInBackground.zip` para o seu Steam Deck (via pendrive, SSH, Warpinator ou Google Drive).
2. No Steam Deck em Modo Jogo, abra o Decky Loader (botão `...`).
3. Vá nas configurações do Decky (ícone de engrenagem) -> **Developer** (Desenvolvedor).
4. Selecione **"Install plugin from ZIP"** (Instalar plugin de arquivo ZIP) e escolha o `DownloadInBackground.zip`.

#### Método 2: Instalação direta via Terminal / SSH
No Konsole do Steam Deck (ou via SSH):
```bash
# Clone ou transfira a pasta para o Steam Deck
cd "Steamdeck Plugin"

# Execute o instalador automático
chmod +x install.sh
./install.sh
```

O script copia os arquivos diretamente para `~/homebrew/plugins/DownloadInBackground/`.

---

### ⚙️ Opções Configuráveis no Menu do Decky

**Comportamento**
- **Ativar/Desativar Plugin:** Liga ou desliga a interceptação de suspensão. Desligado, o SteamOS se comporta exatamente como sem o plugin.
- **Limite de Bateria para Auto-Suspensão:** Ajustável de 5% a 30% (padrão: 15%).
- **Tempo de Exibição do HUD:** Ajustável de 0s a 15s (padrão: 5s). Em 0s, a tela apaga imediatamente.
- **Atraso para Suspensão ao Concluir:** Ajustável de 30s a 600s (padrão: 120s).
- **Bloquear Todos os Inputs com a Tela Apagada** (padrão: ligado): congela o mapeamento de botões e desconecta controles externos, deixando só o Power responder.

**Modo Standby e Despertar por Controle**
- **Substituir o Sleep pelo Standby** (padrão: desligado): ativa o modo descrito acima, tanto no botão Power quanto na opção Sleep do menu do SteamOS.
- **Acordar ao Conectar Controle Bluetooth** (padrão: ligado).
- **Acordar com Botão do Controle** (padrão: ligado): Guide/Home, Select ou Start em controles USB/dongle.

**Tela e Energia**
- **Desligar Luz de Fundo (Backlight):** Zera o brilho do painel físico.
- **Modo Preto Puro OLED:** Camada `#000000`, apagando os pixels em telas OLED.
- **Reduzir CPU para Powersave:** Governor `powersave`, clock mínimo, turbo desligado e limites de PPT/APU reduzidos.
- **Reduzir GPU:** Trava o nível de performance da GPU em `low`.
- **Mutar Áudio com Tela Apagada:** Evita sons indesejados.

**Ritmo do Download (ventoinha e calor)**
- **Diminuir Velocidade do Download** (padrão: ligado) e **Teto de Velocidade** de 1 a 30 MB/s (padrão: 6 MB/s ≈ 21 GB/hora).
- **Orçamento de CPU do Steam:** 0 a 100% de um núcleo (padrão: 30%). É o que mantém o chip frio o suficiente para a ventoinha não ligar.

**Diagnóstico**
- **Desconectar Também o Controle Embutido** (padrão: desligado, **experimental**): só use se algum botão ainda agir com a tela apagada. Desconecta a interface HID bruta do controle interno, o que travou a sessão em alguns consoles.
- **Recuperar a Interface na Volta** (padrão: ligado): se a interface não voltar ao que era depois de acordar de um sleep iniciado pelo **menu do SteamOS**, navega para a home e, em último caso, recarrega a interface da Steam. A decisão não é por cor: o plugin guarda, a cada poll, uma assinatura do que está no meio da tela enquanto tudo está funcionando, e compara com o que está lá depois de acordar. Essa medição é feita na **janela da interface**, obtida por uma referência de DOM do componente que o Decky monta: o escopo de um plugin vive no `SharedJSContext` da Steam, que é uma janela escondida de **1x1 pixel** — medir `window` de lá reporta um viewport 1x1 e um documento 2x2, e qualquer verificação feita assim nunca dispara. O recarregamento, que é o passo caro, exige **dois** sinais independentes: a assinatura mudou **e** não há nada legível na tela. Nunca age no caminho do botão Power, que volta limpo.
- **Gravar Logs de Diagnóstico** (padrão: ligado): registra o panorama completo de input e temperatura em cada ciclo, em `~/homebrew/logs/`. Procure por `DIB APPLY CHECK`, `DIB RESTORE CHECK`, `DIB INPUT DIAGNOSTICS` e `DIB TELEMETRY`.
- **Restaurar Hardware Agora** (botão): devolve clocks, limites de energia e tetos de velocidade ao normal na hora, inclusive o que tiver sobrado de uma queda do plugin, sem reiniciar. Pode ser apertado a qualquer momento.

### 🧯 Por que o console não volta lento

Três camadas, porque uma só não resolveu:

1. **O valor original nunca é sobrescrito.** Entrar no modo duas vezes sem restaurar no meio salvava como "original" o valor que o próprio plugin tinha acabado de escrever — restaurar passava a significar "escrever 800 MHz e 6 W de volta". Agora o primeiro save vence, e um valor que já está no alvo não é salvo (senão a restauração viraria um no-op).
2. **O restore converge.** Uma passada não basta: trocar o perfil ACPI ou a política térmica da ASUS faz o firmware re-aplicar os limites dele, sobrescrevendo clocks restaurados um instante antes. Por isso o perfil e os limites de energia voltam **antes** dos clocks, e depois o plugin **relê tudo e reescreve o que não pegou**, até 3 passadas, registrando no log o que nunca pegou.
3. **O plugin continua olhando por 25s depois.** O restore relê e reescreve até a máquina concordar, mas para de olhar em menos de um segundo. Trocar o perfil ACPI faz o firmware re-aplicar os limites dele **no tempo dele** — ou seja, a máquina pode concordar com o restore e desfazê-lo logo depois, quando ninguém está vendo. Por isso o loop re-verifica durante 25 segundos após acordar e reescreve o que tiver sido desfeito, registrando `[DIB POST-RESTORE]` quando precisa agir.
4. **Rede de segurança.** O que ainda estiver exatamente no valor que o plugin escreveu, e sem original para voltar (queda, recarregamento do plugin), é forçado para um padrão seguro: `scaling_max_freq` → `cpuinfo_max_freq`, GPU → `auto`, turbo → ligado, EPP → `balance_performance`. O **governor fica de fora de propósito**: `powersave` é o padrão normal do amd-pstate, forçá-lo seria brigar com o sistema. E o que o usuário mudou no meio do caminho não é tocado.

---

## 🇺🇸 English

### 💡 Features

- **Prevent Premature Sleep:** Intercepts system sleep/suspend requests when downloads are active in Steam Game Mode.
- **Download Status HUD:** Shows game name, download speed, remaining time, percentage, and battery level for 5 seconds before turning off screen.
- **Display Blanking:**
  - Sets LCD display backlight brightness to 0.
  - Draws a 100% black `#000000` overlay, powering down OLED pixels.
- **Maximum Power Savings:**
  - CPU governor switched to `powersave` / power-saver profile, turbo off, PPT limits lowered.
  - GPU performance level clamped to `low`.
  - Audio sinks muted.
- **Total Button Lockout:** With the screen off, no console button registers anything. Done with the kernel input core's `inhibited` attribute, which drops events before any client receives them — including clients that already hold the device exclusively, such as Steam Input. Only the power button stays live.
- **Calm Download Pace (fans stay off):** Clock limits alone do not keep a console cool, because Steam uses every cycle it is given. So the plugin caps the **bytes per second** (`tc` ingress policer) and Steam's **CPU budget** (a `cpu.max` quota on its own cgroup). Fewer bytes per second means less decompression, less SSD writing and far less heat: the download takes longer and the console stays cold.
- **Standby Instead Of Sleep** (optional, off by default): replaces the system's own sleep — both the physical power button and the Sleep option in the SteamOS power menu — with a standby that turns the console "off" like a desk console: screen black, downloads continuing, waiting for a controller. With a download running you get the download card; with nothing downloading you get the plugin logo and "New Suspend Mode", then black. The physical button is caught at the hardware device; the power menu is caught by wrapping the Steam client's own suspend methods, which is the only point early enough — blocking the suspend further down (a logind inhibitor, or a masked `sleep.target`) happens after Steam has already blanked the screen, and the failed suspend leaves the session stuck on a black lit screen. Nothing is masked at the systemd level, and when the plugin has no reason to act the original method is called so SteamOS sleeps exactly as usual. Connected Bluetooth controllers are disconnected on the way in (over D-Bus, never through `bluetoothctl`, which can block on stdin and silently do nothing); headsets and keyboards are left alone.
  - **Bluetooth pad:** just connecting it wakes the console. Bluetooth stays powered in standby.
  - **USB / dongle pad:** press Guide/Home, Select or Start. Connecting alone does not wake it.
  - **Built-in pad:** stays dead on purpose. Only the power button.
  - **Shut Down** from the Steam menu still really powers off; only the power button and Sleep are intercepted.
- **Safety Auto-Suspend:**
  - Suspends automatically when battery drops below 15% (configurable), in standby too.
  - Suspends automatically once all downloads are completed (not in standby).
- **Instant Wake:** Pressing the power button restores brightness, power profiles, audio and input at once, and dismisses any menu a stray button press may have opened.
- **Never Leaves The System Slow:** Four layers, because fewer were not enough. (1) The saved original is never overwritten by a second pass, so "restore" can never mean writing the throttled value back in. (2) Changes are undone in isolated stages, with the platform profile and power limits going back *before* the clocks, since firmware re-applies its own limits when the profile changes. (3) Everything restored is then re-read and re-written until the machine stops disagreeing, up to three extra passes, and whatever never sticks is named in the log. (4) Anything still holding exactly the value this plugin wrote, with no original left to put back, is forced to a safe default (`cpuinfo_max_freq`, GPU `auto`, turbo on, EPP `balance_performance`); the scaling governor is deliberately left alone, since `powersave` is the normal amd-pstate default. Plus an on-disk state file, so a plugin crash with the screen off is undone on the next load, and a **Restore Hardware Now** button for everything else — no reboot needed.
- **Recovers The Interface:** The power menu calls `SteamClient.User.PrepareForSystemSuspend()` — which suspends running games and moves Steam's interface into its sleeping state — before it calls `SteamClient.System.SuspendPC()`. Wrapping only the latter stopped the suspend but left Steam prepared for one that never came, with nothing to call `ResumeSuspendedGames()`: the interface came back with a black screen and working menus. Both are wrapped now, one sleep is one decision (later calls are held until the answer arrives, and released in the original order if it turns out not to be ours), and the wake calls `ResumeSuspendedGames()` as Steam would on a real resume. A sleep started from the power menu is a UI action, and Steam's own click handler has already run by the time the plugin is consulted — so whatever it did to its interface has to be walked back, not just prevented. The plugin tells the Steam client its suspend was cancelled (through whichever method on this build can only mean that), closes the menus, puts the route back, and compares a signature of the middle of the screen, sampled while the interface was last known healthy, against what is there after the wake. If it changed, it navigates home; if it changed *and* nothing on screen is readable, it reloads the Steam interface as a last resort. The physical-button path is never touched, because Steam never hears about it and it comes back clean.

### 🔨 Building from Source

```bash
# Install dependencies
pnpm install

# Build frontend bundle
pnpm run build

# Package into zip for Decky Loader
pnpm run package
```

---

## 📄 License
MIT License. See [LICENSE](LICENSE) for details.
