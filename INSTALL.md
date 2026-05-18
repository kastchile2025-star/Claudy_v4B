# Instalacion de Claudy v4

Guia para correr Claudy en una maquina nueva (Windows).

## 1. Requisitos del sistema

- **Windows 10/11**
- **Node.js 20+** ([nodejs.org](https://nodejs.org))
- **Python 3.11+** ([python.org](https://python.org)) — recomendado 3.13
- **Git** ([git-scm.com](https://git-scm.com))
- **ffmpeg** (para transcripcion de audios de Telegram)
  ```powershell
  winget install Gyan.FFmpeg
  ```

## 2. Clonar el repositorio

```powershell
git clone https://github.com/kastchile2025-star/Claudy_v4.git
cd Claudy_v4
```

## 3. Instalar dependencias

### CLI (Node.js)
```powershell
npm install
npm install -g opencode-ai
```

### Pet de escritorio (Python)
```powershell
pip install -r requirements.txt
```

### Browser para automation (Playwright)
```powershell
python -m playwright install chromium
```

## 4. Configurar OpenCode

```powershell
opencode auth login
```

Sigue el flujo para autenticar con DeepSeek, OpenAI, Anthropic u otro proveedor.

## 5. Crear configuracion de Claudy

Crea el archivo `~/.claudy/config.json` (en Windows: `C:\Users\<tuusuario>\.claudy\config.json`):

```json
{
  "opencode": {
    "baseUrl": "http://127.0.0.1:4096",
    "defaultModel": "deepseek/deepseek-v4-pro",
    "apiKey": "",
    "username": "opencode",
    "password": ""
  },
  "agent": {
    "systemPrompt": "Eres Claudy, asistente personal. Hablas espanol directo.",
    "maxTokens": 4096,
    "temperature": 0.7
  },
  "tools": {
    "enabled": true,
    "allowRead": true,
    "allowWrite": false,
    "allowExec": false,
    "allowedRoot": "C:/Users/tuusuario",
    "commandTimeoutMs": 10000,
    "maxOutputChars": 20000
  },
  "server": {
    "port": 3001,
    "host": "127.0.0.1"
  }
}
```

### Opcional: Telegram bot
Agrega al config:
```json
"telegram": {
  "botToken": "TU_TOKEN_DE_BOTFATHER",
  "allowedUsers": ["TU_USER_ID"],
  "ttsReply": false
}
```

### Opcional: Email SMTP
```json
"email": {
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 465,
  "smtp_user": "tu@gmail.com",
  "smtp_pass": "app-password",
  "from": "tu@gmail.com"
}
```

### Opcional: Gmail IMAP (para /gmail)
```json
"gmail": {
  "user": "tu@gmail.com",
  "appPassword": "abcd efgh ijkl mnop"
}
```

(crea app password en [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords))

## 6. Iniciar OpenCode server

En una terminal aparte:
```powershell
opencode serve --port 4096 --hostname 127.0.0.1
```

## 7. Iniciar Claudy

### CLI
```powershell
npm run build
npm link
claudy chat
```

### Pet de escritorio
```powershell
python src/desktop/pet.py
```

O en background sin ventana:
```powershell
pythonw src/desktop/pet.py
```

## 8. Comandos disponibles en el bubble

Mas de 90 comandos slash. Algunos destacados:

- `/personality <nombre>` — cambia personalidad (directo, brutal, profesor, etc.)
- `/voice on` — TTS
- `/voice listen` — STT con wake word
- `/img <prompt>` — genera imagen
- `/browse <url>` — navega web
- `/yt <url>` — resume video YouTube
- `/iva <monto>` — calcula IVA Chile
- `/uf` — indicadores economicos
- `/ocr <imagen>` — extrae texto
- `/recordar <query>` — busqueda semantica en memoria
- `/delegate <tarea>` — subagente paralelo
- `/mcp list` — servidores MCP
- `/board` `/task add ...` — kanban
- `/aprender <nombre>` — destila conversacion en SKILL.md
- `Alt+Space` — hotkey global

Ve `HERMES_REPLICATION_PLAN.md` y `PROGRESO.md` para la lista completa.

## 9. Skills personalizadas

Pon archivos `SKILL.md` en `~/.claudy/skills/<nombre>/SKILL.md` y se cargan al arrancar.
O usa `/skill install <user/repo>` para instalar de GitHub.

## 10. Problemas comunes

- **"opencode no responde"**: ejecuta `opencode serve --port 4096 --hostname 127.0.0.1` en otra terminal.
- **"no module named X"**: corre `pip install -r requirements.txt` de nuevo.
- **Telegram bot no arranca**: verifica el token en config y mira `~/.claudy/telegram_bot.log`.
- **PyAudio falla al instalar**: instala Visual C++ Build Tools o usa `pipwin install PyAudio`.
