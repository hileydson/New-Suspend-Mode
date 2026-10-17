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
1. **Intercepta a Suspensão:** Não deixa o console entrar em suspensão imediatamente se houver downloads em andamento.
2. **Exibe o Status do Download (HUD):** Mostra um card elegante e translúcido na tela com o nome do jogo, velocidade atual (MB/s), barra de progresso (%), tempo restante e nível da bateria com uma contagem regressiva de alguns segundos (padrão: 5s, configurável).
3. **Apaga a Tela & Economia Máxima:**
   - Reduz o brilho físico da luz de fundo (backlight) para `0` (LCD).
   - Exibe uma camada 100% preta pura (`#000000`), desligando totalmente os pixels em modelos OLED.
   - Aplica perfil de economia de energia na CPU (`power-saver` / governor `powersave`).
   - Trava a GPU na frequência mínima (200 MHz).
   - Muta o áudio para evitar sons de notificações ou do sistema.
4. **Regras Inteligentes de Auto-Suspensão:**
   - 🔋 **Bateria Baixa (&le; 15%):** Se a bateria cair para 15% (ou limite configurado) enquanto estiver na bateria, o console restaura o estado e entra em suspensão real para evitar esgotamento total da bateria.
   - 🏁 **Downloads Concluídos:** Quando todos os downloads terminarem (fila vazia por alguns segundos), o console entra automaticamente em suspensão real.
5. **Retomada Instantânea:** Ao apertar o botão Power, tocar na tela ou apertar qualquer botão do controle, a tela acende imediatamente e os perfis de desempenho e áudio normais são restaurados.

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

- **Ativar/Desativar Plugin:** Liga ou desliga a interceptação de suspensão.
- **Limite de Bateria para Auto-Suspensão:** Ajustável de 5% a 30% (padrão: 15%).
- **Tempo de Exibição do HUD:** Ajustável de 0s a 15s (padrão: 5s). Se colocado em 0s, a tela apaga imediatamente ao suspender.
- **Atraso para Suspensão ao Concluir:** Ajustável de 5s a 60s (padrão: 15s).
- **Desligar Luz de Fundo (Backlight):** Desliga os LEDs da tela física.
- **Modo Preto Puro OLED:** Desliga os pixels pretos da tela OLED.
- **Reduzir CPU para Powersave:** Diminui consumo do processador durante o download.
- **Reduzir GPU para 200MHz:** Economiza energia limitando a GPU integrada.
- **Mutar Áudio com Tela Apagada:** Evita sons indesejados no quarto/ambiente.

---

## 🇺🇸 English

### 💡 Features

- **Prevent Premature Sleep:** Intercepts system sleep/suspend requests when downloads are active in Steam Game Mode.
- **Download Status HUD:** Shows game name, download speed, remaining time, percentage, and battery level for 5 seconds before turning off screen.
- **Display Blanking:**
  - Sets LCD display backlight brightness to 0.
  - Draws a 100% black `#000000` overlay, powering down OLED pixels.
- **Maximum Power Savings:**
  - CPU governor switched to `powersave` / power-saver profile.
  - GPU engine clock clamped to minimum 200 MHz.
  - Audio sinks muted.
- **Safety Auto-Suspend:**
  - Suspends automatically when battery drops below 15% (configurable).
  - Suspends automatically once all downloads are completed.
- **Instant Wake:** Pressing the power button, touching the screen, or pressing any gamepad button immediately restores normal brightness and performance profiles.

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
