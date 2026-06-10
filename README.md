# Claudy v5 — Asistente IA personal de escritorio

**Claudy** es una mascota de escritorio con IA para Windows: un sprite animado
que vive en tu pantalla, con un panel de chat moderno, memoria infinita y un
bot de Telegram como canal remoto. Hecho en Python puro.

> Refactor v5 (junio 2026): el monolito `pet.py` se partió en módulos
> (`core/`, `channels/`), la memoria ganó búsqueda FTS5 sobre toda la
> historia, y Telegram pasó a ser el único canal externo, con formato nativo.
> Detalle completo en [PLAN_REFACTORIZACION_CLAUDY_V5.md](PLAN_REFACTORIZACION_CLAUDY_V5.md).

## Características

- **Mascota animada** (tkinter): drag & drop, snap a bordes, bandeja del
  sistema, hotkey global `Alt+Space`, animaciones idle.
- **Chat de escritorio** (pywebview + `chat.html`): sidebar con estado de
  Google Drive y Telegram, productos QCORE, Deep Research, streaming en vivo.
- **Memoria infinita** (SQLite): nada se borra jamás — capa caliente +
  archivo + resúmenes + checkpoints, con índice **FTS5** para recordar
  cualquier cosa de toda la historia (`/memoria <consulta>`).
- **Espejo Obsidian**: cada conversación y conocimiento se refleja en el
  vault QCORE (Google Drive).
- **Bot de Telegram**: texto, notas de voz (Whisper), fotos y documentos,
  respuestas con formato nativo (negrita/código), respuestas por audio
  opcionales (edge-tts), comandos `/memoria`, `/resumen`, `/estado`, `/voz`.
- **Multi-proveedor LLM**: OpenCode local → Anthropic / DeepSeek / OpenAI /
  Google con fallback automático y pool de credenciales.
- **Poderes locales**: abrir/instalar apps, archivos, crear docx/xlsx/pptx/pdf,
  capturas, descargas, calendario de Google, kanban, cron, skills SKILL.md.

## Arquitectura

```
src/desktop/
├── pet.py                  # Ventana, sprite, animación, UI glue (en adelgazamiento)
├── core/
│   ├── memory.py           # Memoria infinita SQLite + FTS5 + vault (MemoryMixin)
│   ├── llm.py              # Cadena de proveedores + tools (LLMMixin)
│   ├── prompts.py          # System prompt ÚNICO, variantes por canal (PromptsMixin)
│   ├── gateway.py          # HTTP 127.0.0.1:8720 — contrato app<->canales (GatewayMixin)
│   └── logging_setup.py    # Logs con rotación en ~/.claudy/logs/
├── channels/
│   └── telegram_bot.py     # Bot Telegram (proceso aparte, único canal externo)
├── chat.html               # UI del chat (NO tocar el diseño)
├── claudy_powers.py        # Poderes locales (apps, archivos, documentos)
├── qcore_products.py       # Contexto de productos QCORE
├── secure_store.py         # Secretos encriptados en config.json
└── tests/                  # python -m unittest discover tests
```

La clase `ClawdPet` compone los mixins: `MemoryMixin, LLMMixin, GatewayMixin,
PromptsMixin, tk.Tk`. Cada mixin es un módulo independiente y testeable.

### Flujo de un mensaje

```
Escritorio: chat.html → WebViewApi → ask_claudy → send_quick_message (core/llm)
Telegram:   bot → POST :8720/api {"message", "channel":"telegram"} (core/gateway)
                          ↓
       intents (_try_handle_skill_action) → o LLM con contexto de memoria
                          ↓
       memoria SQLite (+FTS) + espejo Obsidian + respuesta al canal
```

## Instalación

Requisitos: Windows 10/11, Python 3.12+, ffmpeg (para audio de Telegram).

```bash
git clone https://github.com/kastchile2025-star/Claudy_v4.git
cd Claudy_v4
pip install -r requirements.txt        # núcleo
pip install -r requirements-extras.txt # opcional: micrófono, OCR, playwright...
iniciar_claudy.bat
```

## Configuración

Archivo: `~/.claudy/config.json` (los tokens se encriptan en reposo
automáticamente con `secure_store`).

```json
{
  "opencode": { "baseUrl": "http://127.0.0.1:4096", "defaultModel": "deepseek-chat" },
  "providers": {
    "anthropic": { "key": "..." },
    "deepseek":  { "key": "..." },
    "fallback": ["deepseek-chat"],
    "allowFreeFallback": false
  },
  "telegram": { "botToken": "...", "allowedUsers": ["123456789"], "ttsReply": false },
  "gateway": { "port": 8720 }
}
```

- `providers.allowFreeFallback`: si todos los proveedores fallan, permite el
  fallback gratuito de Pollinations (terceros). **Apagado por defecto por
  privacidad.**
- La memoria vive en `G:\Mi unidad\QCORE-ECOSYSTEM\MEMORIAS\AGENTES-MEMORY\claudy_local\memory.db`
  si el Drive está montado; si no, en `~/.claudy/memory.db`.

## Telegram

1. Crea un bot con @BotFather y dile a Claudy: `vincula mi telegram <token>`
   (o pega el token en Configuración).
2. Autoriza tu usuario: `/vincular <tu_id>` desde el escritorio.
3. El bot corre como proceso independiente con watchdog: si se cae, la app
   lo revive sola (máx 5 reinicios/hora).

Comandos del bot: `/memoria <consulta>` (busca en toda la historia),
`/resumen` (lo de hoy), `/estado` (salud), `/voz on|off` (audio o texto),
`/atajos`. También acepta notas de voz, fotos y documentos.

## Memoria infinita — contrato

1. `memory` (caliente, últimos ~400-800 mensajes) → contexto inmediato.
2. `memory_archive` → todo lo antiguo, **nunca se borra**.
3. `memory_summaries` → resúmenes de rangos comprimidos.
4. `memory_fts` (FTS5) → índice de búsqueda sobre TODO lo anterior.
5. Vault Obsidian → espejo legible en markdown.

`/memoria <lo que sea>` responde desde cualquier época de la historia.

## Tests

```bash
cd src/desktop
python -m unittest discover tests -v
```

## Logs

`~/.claudy/logs/claudy.log` (rotación 1 MB × 5). El log del bot de Telegram
queda en `~/.claudy/telegram_bot.log`.

## Licencia

MIT — proyecto personal de Felipe Castro / QCORE SPA.
