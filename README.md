# Claudy - Asistente de IA Personal

**Claudy** es un fork simplificado de [OpenClaw](https://github.com/openclaw/openclaw), un asistente de IA personal que corre localmente en tu maquina y se conecta a OpenCode.

## Caracteristicas

- Chat web en tiempo real
- Integracion con **OpenCode** via servidor local
- Canal opcional de **Telegram Bot** con polling local
- Transcripcion de audios de Telegram usando la skill local `qwen-asr`
- Tools locales por comandos slash: `/read`, `/write`, `/exec`, `/browse`
- Sistema de **skills** en Markdown (`SKILL.md`)
- Memoria vectorial local en `~/.claudy/memory.json`
- Voice en navegador: dictado STT y lectura TTS
- Historial de conversaciones persistente
- Selector de modelos desde la UI
- Configuracion editable desde la app
- Interfaz moderna y responsive

## Stack Tecnologico

- **Backend**: Node.js/Bun + Express + WebSocket
- **Frontend**: React + Vite + Tailwind CSS
- **LLM**: OpenCode server (`opencode serve`)
- **Canales**: Web UI y Telegram Bot API
- **Storage**: JSON files en `~/.claudy/`

## Opcion 1: GitHub Codespaces

La forma mas facil de probar Claudy es en un **GitHub Codespace**. No necesitas instalar nada en tu computadora.

1. Ve al repo: https://github.com/kastchile2025-star/Claudy
2. Haz clic en el boton verde **Code** y luego **Codespaces**.
3. Crea un codespace desde `main`.
4. Espera 1-2 minutos a que se configure.
5. Abre el puerto `3000` en el navegador.

> Nota: el backend usa el puerto `3001` y el frontend usa el puerto `3000`.

Scripts utiles en Codespaces:

```bash
bash scripts/codespace-install-opencode.sh
bash scripts/codespace-opencode.sh
bash scripts/codespace-backend.sh
bash scripts/codespace-frontend.sh
```

O para levantar todo en segundo plano con logs:

```bash
bash scripts/codespace-all.sh
```

Para detener servicios en segundo plano:

```bash
bash scripts/codespace-stop.sh
```

## Opcion 2: Instalacion Local

### Requisitos

- Node.js 20+ o Bun
- OpenCode CLI disponible en tu maquina

### Pasos

```bash
# 1. Clonar el repo
git clone https://github.com/kastchile2025-star/Claudy.git
cd Claudy

# 2. Instalar backend
cd backend
bun install

# 3. Iniciar OpenCode en otra terminal
opencode serve --port 4096 --hostname 127.0.0.1

# 4. Iniciar backend
bun run src/server.ts

# 5. Instalar frontend en otra terminal
cd ../frontend
bun install

# 6. Iniciar frontend
bun run dev

# 7. Abrir la app
# http://localhost:3000
```

## Uso

1. Abre http://localhost:3000 en tu navegador.
2. Escribe un mensaje para comenzar.
3. Selecciona diferentes modelos desde el menu superior.
4. Ve a Configuracion para cambiar OpenCode, Telegram, tools, skills, memoria o prompt del agente.

## Tools Locales

Claudy incluye tools invocadas manualmente por comandos slash. Por seguridad, `/write` y `/exec` vienen apagados por defecto.

| Comando | Funcion |
| --- | --- |
| `/read README.md` | Lee un archivo dentro del directorio permitido. |
| `/browse https://example.com` | Descarga texto basico de una pagina web. |
| `/write notas/demo.txt\ncontenido` | Escribe un archivo. Requiere activar escritura. |
| `/exec bun --version` | Ejecuta un comando. Requiere activar ejecucion. |
| `/skills` | Lista skills instalados. |
| `/skill_search telegram` | Busca skills instalados. |
| `/skill_find pdf` | Busca skills en internet usando skills.sh. |
| `/skill_install_best pdf` | Instala el mejor `SKILL.md` encontrado y actualiza el README local de skills. |
| `/skill_install URL` | Instala un `SKILL.md` desde una URL. |

Puedes configurar el directorio permitido desde la UI o con `CLAUDY_TOOLS_ROOT`. Las tools de archivos y ejecucion no pueden salir de ese directorio.

## Skills

Claudy puede cargar habilidades desde archivos `SKILL.md`.

- Los skills del proyecto viven en `skills/<nombre>/SKILL.md`.
- Los skills instalados por el usuario se guardan en `~/.claudy/skills/<nombre>/SKILL.md`.
- Cada instalacion copia `SKILL.md` y, si la fuente es GitHub, tambien archivos auxiliares del directorio del skill.
- Cada instalacion actualiza `~/.claudy/skills/README.md` con nombre, descripcion, fuente y ruta local.
- Cuando escribes un mensaje, Claudy busca skills relevantes y los agrega como contexto del agente.
- Desde Configuracion puedes buscar skills instalados o instalar uno pegando una URL a `SKILL.md`.
- Tambien puedes decir en lenguaje natural: `instala una skill para leer pdf`.

Ejemplo de URL compatible:

```text
https://github.com/vercel-labs/skills/blob/main/skills/find-skills/SKILL.md
```

Comandos utiles desde el chat web:

```text
/skill_find pdf
/skill_install_best pdf
```

Comandos equivalentes desde el CLI:

```text
/find-skill pdf
/install-skill pdf
```

Los skills son instrucciones en Markdown. Instala solo skills de fuentes confiables.

## Memoria Vectorial

Claudy guarda recuerdos locales de mensajes utiles y los recupera por similitud para dar contexto en futuras respuestas.

- Archivo local: `~/.claudy/memory.json`
- No usa un servicio externo de embeddings.
- Usa un vector hash local liviano para busqueda semantica aproximada.
- Puedes activar/desactivar memoria y cambiar limites desde Configuracion.

## Voice

La interfaz web incluye voz usando APIs del navegador:

- **STT**: boton de microfono para dictar mensajes.
- **TTS**: boton de volumen para leer respuestas del asistente.

La disponibilidad depende del navegador y sus permisos de microfono. En Chrome/Edge suele funcionar mejor.

## Telegram

Claudy puede responder mensajes desde un bot de Telegram usando polling local.
Tambien puede recibir notas de voz, audios o documentos de audio y transcribirlos con la skill local `qwen-asr` si existe en `~/.claudy/skills/qwen-asr/scripts/main.py`.

1. Crea un bot con BotFather y guarda el token de forma privada.
2. Abre Configuracion en Claudy.
3. Activa Telegram.
4. Pega el bot token.
5. Recomendado: limita los Chat IDs permitidos a tu chat personal.
6. Guarda la configuracion y escribe al bot desde Telegram.

Tambien puedes configurar variables de entorno:

```bash
TELEGRAM_BOT_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_ALLOWED_CHAT_IDS=123456789
CLAUDY_ASR_TIMEOUT_MS=600000
CLAUDY_FFMPEG=ffmpeg
CLAUDY_TELEGRAM_AUDIO_MAX_BYTES=26214400
```

> Importante: no subas el token al repositorio. Claudy lo guarda localmente en `~/.claudy/config.json`.

Para audios de Telegram, Claudy intenta convertir notas de voz `.oga/.opus` a WAV mono 16 kHz con `ffmpeg` antes de llamar la skill `qwen-asr`. Si la transcripcion tarda mucho, aumenta `CLAUDY_ASR_TIMEOUT_MS`.

## Configuracion

Archivo local: `~/.claudy/config.json`

```json
{
  "opencode": {
    "baseUrl": "http://127.0.0.1:4096",
    "defaultModel": "opencode-go/qwen3.6-plus"
  },
  "telegram": {
    "enabled": false,
    "botToken": "",
    "allowedChatIds": []
  },
  "skills": {
    "enabled": true,
    "maxContextSkills": 3
  },
  "memory": {
    "enabled": true,
    "maxResults": 5,
    "maxEntries": 500
  },
  "tools": {
    "enabled": true,
    "allowRead": true,
    "allowWrite": false,
    "allowExec": false,
    "allowBrowser": true,
    "allowedRoot": "..",
    "commandTimeoutMs": 10000,
    "maxOutputChars": 20000
  },
  "agent": {
    "systemPrompt": "Eres Claudy, un asistente de IA personal...",
    "maxTokens": 4096,
    "temperature": 0.7
  },
  "server": {
    "port": 3001,
    "host": "127.0.0.1"
  }
}
```

Variables utiles en `.env`:

```bash
CLAUDY_SKILLS_ENABLED=true
CLAUDY_MAX_CONTEXT_SKILLS=3
CLAUDY_MEMORY_ENABLED=true
CLAUDY_MEMORY_MAX_RESULTS=5
CLAUDY_MEMORY_MAX_ENTRIES=500
CLAUDY_TOOLS_ENABLED=true
CLAUDY_TOOL_READ=true
CLAUDY_TOOL_BROWSER=true
CLAUDY_TOOL_WRITE=false
CLAUDY_TOOL_EXEC=false
CLAUDY_TOOLS_ROOT=..
CLAUDY_TOOL_TIMEOUT_MS=10000
CLAUDY_TOOL_MAX_OUTPUT_CHARS=20000
```

## Estructura del Proyecto

```text
claudy/
|-- backend/
|   |-- src/
|   |   |-- server.ts        # Servidor Express + WebSocket
|   |   |-- opencode.ts      # Cliente OpenCode server
|   |   |-- telegram.ts      # Canal Telegram Bot API
|   |   |-- skills.ts        # Loader y buscador de skills
|   |   |-- memory.ts        # Memoria vectorial local
|   |   |-- toolrunner.ts    # Tools slash locales
|   |   |-- agent.ts         # Loop del agente
|   |   |-- config.ts        # Gestion de configuracion
|   |   |-- sessions/        # Almacenamiento de sesiones
|   |   |-- tools/           # Herramientas legacy
|-- frontend/
|   |-- index.html           # Entrada Vite
|   |-- src/                 # React app (Vite)
|-- skills/
|   |-- find-skills/
|   |   |-- SKILL.md          # Skill base para descubrir habilidades
```

## Roadmap

- [x] Telegram polling
- [x] Tools: exec, read, write, browser
- [x] Sistema de skills basado en Markdown
- [x] Memoria vectorial local
- [x] Voice: STT + TTS
- [ ] Discord u otros canales
- [ ] Embeddings externos opcionales
- [ ] Permisos avanzados por tool

## Creditos

- Fork inspirado en [OpenClaw](https://github.com/openclaw/openclaw) por Peter Steinberger y comunidad
- Powered by [OpenCode](https://opencode.ai/)

## Licencia

MIT
