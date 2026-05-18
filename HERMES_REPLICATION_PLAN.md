# Plan de Replicacion de Hermes Agent en Claudy

Inventario de capacidades de Hermes Agent (Nous Research) mapeado a Claudy, dividido en 2 fases.

Fuente: https://hermes-agent.nousresearch.com/docs/user-guide/features/overview

---

## FASE 1 — Quick Wins (capacidades base, esfuerzo bajo, alto impacto)

Objetivo: que Claudy se sienta como un asistente real con voz, vision, personalidad y presencia multi-canal. Todas las features de esta fase reusan codigo existente o usan APIs gratuitas/baratas.

### 1.1 — Voice mode (TTS gratuita con Edge TTS)
- Que: Claudy lee sus respuestas en voz alta usando Edge TTS de Microsoft (gratis, voces neuronales en espanol).
- Donde: agregar `tts.py` en `src/desktop/`, hook despues de cada respuesta del modelo.
- Esfuerzo: 1-2 horas.
- Dependencia: `pip install edge-tts`.

### 1.2 — Activar bots de mensajeria (Telegram + WhatsApp + Discord)
- Que: Claudy responde desde Telegram/WhatsApp/Discord con la misma memoria SQLite del pet.
- Donde: `src/desktop/bg_telegram_bot.py`, `bg_whatsapp_bot.py`, `bg_discord_bot.py` ya existen — conectarlos al cliente OpenCode + memoria compartida.
- Esfuerzo: 2-3 horas (configurar tokens y arrancarlos como threads del pet).

### 1.3 — `/personality` swap (SOUL.md presets)
- Que: cambiar la personalidad del asistente con un comando: serio, cariñoso, brutalmente directo, profesor, etc.
- Donde: agregar `personalities/` con archivos `.md`, comando `/personality <nombre>` en el bubble del pet que sobreescribe el `systemPrompt` en `config.json`.
- Esfuerzo: 1 hora.

### 1.4 — Vision (pegar imagen al bubble)
- Que: pegar imagen desde portapapeles al bubble y Claudy la analiza (OCR, descripcion, codigo de screenshots).
- Donde: bind `Ctrl+V` en el entry del bubble, capturar imagen con PIL, mandarla al modelo vision (DeepSeek/GPT-4o-vision).
- Esfuerzo: 2-3 horas.

### 1.5 — Image generation (FAL.ai / o gratis con Pollinations)
- Que: comando `/img <prompt>` genera imagen y la muestra en el bubble.
- Donde: helper `image_gen.py`, usar API gratuita de Pollinations.ai como default (no requiere key).
- Esfuerzo: 1-2 horas.

### 1.6 — Checkpoints + rollback de archivos
- Que: antes de modificar un archivo, snapshot automatico; comando `/rollback` lo revierte.
- Donde: wrapper en las operaciones de file edit, guardar copias en `~/.claudy/checkpoints/<timestamp>/`.
- Esfuerzo: 1-2 horas.

### 1.7 — Cron natural language
- Que: "recordame cada lunes a las 9am revisar la lista de pendientes" → cron job real.
- Donde: el engine ya existe (`self.after(3000, self._start_cron_engine)`), parsing de lenguaje natural con regex + tabla de palabras clave.
- Esfuerzo: 2-3 horas.

**Total Fase 1: ~12-16 horas de trabajo. Output: Claudy con voz, vision, multi-canal, personalidad y automatizacion basica.**

---

## FASE 2 — Capacidades Avanzadas (arquitectura)

Objetivo: convertir a Claudy en un agente verdaderamente extensible y autonomo, capaz de delegar trabajo, navegar la web, conectarse a herramientas externas via MCP y aprender skills nuevas en runtime.

### 2.1 — Subagentes paralelos (delegate_task)
- Que: comando `/delegate <tarea>` lanza un proceso Python independiente con su propio contexto y terminal. Hasta 3 simultaneos.
- Como: spawn de `subprocess` con un script `subagent_runner.py` que reusa la config de Claudy con sesion aislada.
- Esfuerzo: 4-6 horas.

### 2.2 — Browser automation (Playwright)
- Que: Claudy puede navegar webs, llenar forms, extraer datos, hacer login en sitios.
- Como: `pip install playwright`, helper `browser.py` con metodos `goto`, `fill`, `click`, `extract`.
- Esfuerzo: 4-6 horas.

### 2.3 — MCP client (stdio + HTTP)
- Que: conectar Claudy a servidores MCP externos (Filesystem, GitHub, Postgres, Slack, etc.) sin escribir tools nativos.
- Como: cliente MCP en Python siguiendo el spec de Anthropic, registrar tools dinamicamente al arrancar.
- Esfuerzo: 6-8 horas.

### 2.4 — Skills dinamicas auto-generadas
- Que: cuando Claudy resuelve un problema complejo, ofrece guardarlo como skill reusable en `~/.claudy/skills/`. La proxima vez lo aplica solo.
- Como: trigger al final de cada conversacion con `_evaluate_skill_extraction`; loader dinamico al arrancar.
- Esfuerzo: 6-8 horas.

### 2.5 — Provider fallback + credential pools
- Que: si DeepSeek falla, fallback automatico a otro provider; rotacion de API keys cuando una se ratelimitea.
- Como: wrapper en `opencode.ts` con lista de providers ordenada, retry logic con backoff.
- Esfuerzo: 3-4 horas.

### 2.6 — Hooks lifecycle
- Que: el usuario registra callbacks Python que se ejecutan en eventos (`on_message`, `on_tool_call`, `on_error`).
- Como: hook system con archivo `~/.claudy/hooks.py` cargado al arrancar.
- Esfuerzo: 2-3 horas.

### 2.7 — Memory providers externos
- Que: en vez de SQLite local, opcion de usar Mem0 / Supermemory / Honcho como backend para memoria vectorial con embeddings.
- Como: interface `MemoryProvider` con implementaciones intercambiables.
- Esfuerzo: 4-6 horas.

### 2.8 — Batch processing
- Que: `/batch <archivo.txt>` ejecuta cientos de prompts en paralelo y guarda resultados en JSONL (formato ShareGPT) — util para evals o data generation.
- Como: ThreadPoolExecutor con limite de concurrencia, output a `~/.claudy/batches/`.
- Esfuerzo: 3-4 horas.

### 2.9 — API server OpenAI-compatible
- Que: Claudy expone endpoint `http://localhost:3001/v1/chat/completions` compatible con OpenAI; cualquier cliente (Open WebUI, LobeChat, scripts) lo usa.
- Como: ya existe `_start_gateway`; ajustar el schema de request/response al spec OpenAI.
- Esfuerzo: 3-4 horas.

**Total Fase 2: ~35-49 horas. Output: Claudy como agente autonomo extensible con browser, subagentes, MCP, skills emergentes y API publica.**

---

## Resumen ejecutivo

| Fase | Foco | Tiempo | Resultado |
|------|------|--------|-----------|
| 1 | Capacidades visibles para el usuario | 12-16h | Voz, vision, multi-canal, personalidad, cron |
| 2 | Arquitectura avanzada | 35-49h | Subagentes, browser, MCP, skills emergentes |

**Recomendacion**: empezar por Fase 1 (impacto inmediato, esfuerzo bajo). Validar lo que mas usas y recien entonces atacar Fase 2.

## Lo que Claudy YA tiene
- Memoria SQLite infinita con archivo (`memory.db` + `memory_archive`)
- Cron engine (skeleton, falta NL parsing)
- Bots Telegram/Discord/WhatsApp (skeleton, falta conectar)
- Gateway HTTP server (skeleton, falta spec OpenAI)
- Carpeta `skills/` (falta loader dinamico)
- Kanban DB
- Personalidad base (`systemPrompt` editable)
