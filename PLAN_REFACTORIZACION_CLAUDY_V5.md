# Plan de Refactorización — Claudy v5

**Fecha:** 9 de junio de 2026
**Base analizada:** rama `claudy-v4` (commit `cf23dcf`)

---

## ✅ ESTADO DE EJECUCIÓN (9 jun 2026)

| Fase | Estado | Notas |
|---|---|---|
| 0 — Seguridad | ✅ Hecha | Tag `v4-estable`; PAT fuera del remote (**revocar en GitHub pendiente de Felipe**); node_modules/dist fuera del repo |
| 1 — Limpieza | ✅ Hecha | CLI TS, web React, patches y bots Discord/WhatsApp eliminados. Solo Telegram |
| 2 — Partir pet.py | 🟡 Núcleo hecho | `core/memory`, `core/llm`, `core/gateway`, `core/prompts` extraídos (pet.py 19.090 → ~16.500 líneas). Pendiente gradual: `features/` (documentos, email, calendar, scheduler) y `ui/` |
| 3 — Memoria FTS5 | ✅ Hecha | FTS5 toda la historia, contexto eficiente, archivado garantizado (fix de compresión que borraba), vault incremental |
| 4 — Telegram | ✅ Hecha | channels/telegram_bot.py: HTML nativo, progreso 1 mensaje, hot-reload, watchdog, /memoria /resumen /estado. Pendiente menor: cola de mensajes |
| 5 — Respuestas | ✅ Hecha | Prompt único por canal, streaming default, modelos 2026, Pollinations opt-in, extract_text único. Pendiente: unificar los ~49 intents por keyword en registro |
| 6 — Calidad | ✅ Hecha | Logging rotativo, 20 tests nuevos (todos verdes), README/requirements reescritos |
**Regla de oro:** la interfaz actual de `chat.html` (sidebar CLAUDY v4.0, estados Google Drive/Telegram, PRODUCTOS QCORE, Deep Research, consola) **NO se toca visualmente**. Todo el refactor es interno.

---

## 1. Diagnóstico — qué es Claudy hoy

Claudy es una mascota de escritorio (tkinter + pywebview) que:

- Muestra un sprite animado flotante y un panel de chat HTML (`chat.html`, React por CDN).
- Responde con IA usando una cadena de proveedores: OpenCode local (4096) → API remota (Anthropic / OpenAI / DeepSeek / Google) → Pollinations como último recurso.
- Tiene **memoria infinita en SQLite** (`memory.db` en Google Drive `QCORE-ECOSYSTEM/MEMORIAS`, con fallback a `~/.claudy/`): tabla `memory` + `memory_archive` (nunca borra, archiva) + `memory_summaries` (compresión) + `checkpoints`, con espejo a vault Obsidian.
- Expone un **Gateway HTTP** local (puerto 8720) que desacopla los canales externos.
- Corre un **bot de Telegram** como subproceso independiente (`bg_telegram_bot.py`): texto, voz (Whisper STT + edge-tts TTS), documentos/fotos, mensajes de progreso.
- Tiene "poderes" locales (`claudy_powers.py`): apps, archivos, docx/xlsx/pptx/pdf, descargas.
- Contexto de productos QCORE (`qcore_products.py`), calendario, email, deep research, scheduler, kanban, skills SKILL.md, cron propio.

### El problema central

`pet.py` tiene **19.090 líneas (931 KB), 658 funciones, en UNA sola clase** `ClawdPet(tk.Tk)` que mezcla: animación del sprite, ventanas, memoria, llamadas LLM, gateway, gestión de bots, detección de intenciones (~50 chequeos por keyword + una función de 780 líneas), generación de documentos, email, calendario… Es inmantenible: cada cambio arriesga romper otra cosa.

---

## 2. Qué está BIEN (se conserva tal cual)

| Componente | Por qué se queda |
|---|---|
| `chat.html` | UI moderna, coincide con el diseño aprobado (la imagen). Solo se permiten fixes de bugs, cero cambios visuales. |
| Memoria SQLite infinita + archivo + resúmenes + checkpoints | Diseño correcto: nunca pierde datos (archiva en vez de borrar). Se conserva y se mejora el *recall*. |
| Espejo a Obsidian / vault QCORE | Integración clave con tu ecosistema. Se queda. |
| Gateway HTTP 8720 | Buen desacople app ↔ canales. Se queda como contrato estable. |
| Bot Telegram como subproceso | Arquitectura correcta (no muere con la app). Se queda y se potencia. |
| `claudy_powers.py`, `qcore_products.py`, `secure_store.py`, `obsidian_export.py`, `google_calendar.py`, `google_docs.py`, `deep_research.py`, `email_client.py`, `task_scheduler.py`, `gallery_view.py` | Ya son módulos separados — la dirección correcta. Se mantienen (con limpieza menor). |
| Cadena de fallback multi-proveedor | Resiliencia real. Se conserva (Pollinations pasa a ser opt-in, ver §6). |
| Sistema de skills SKILL.md + auto-aprendizaje | Diferenciador de Claudy. Se queda. |
| Sprites, animaciones, tray, hotkey Alt+Space, drag&drop | Funciona bien. Se queda. |

---

## 3. Qué está MAL (se modifica)

1. **`pet.py` monolito de 19K líneas** → dividir en paquetes (§5).
2. **Doble system prompt divergente**: `_get_superpowers()` (protocolo completo) y el `base_sys` de `send_quick_message` dicen cosas distintas → una sola fuente de verdad.
3. **Detección de intenciones frágil**: ~50 `if X in lower` + `_try_handle_skill_action` de 780 líneas + regex en `claudy_powers` → registro único de intents con prioridades.
4. **Código de extracción de respuesta duplicado 3 veces** dentro de `send_quick_message` → una función `extract_text(response)`.
5. **Canales muertos**: `bg_discord_bot.py` y `bg_whatsapp_bot.py` → **se eliminan. Solo Telegram** (requisito).
6. **Código legacy muerto**: CLI TypeScript (`src/*.ts`, `src/commands/`), web React vieja (`src/web/`), `dist/`, `patch*.py`, `fix_text.py`, `widen_sidebar.py`, `backup_original/` → se eliminan o archivan.
7. **`node_modules/` versionado en git** → se elimina del repo (infla el historial).
8. **SEGURIDAD: token GitHub (PAT) incrustado en la URL del remote** → revocar token y usar credential manager. **Acción inmediata, antes de todo lo demás.**
9. **`except Exception: pass` silencioso por todas partes** → logging real en `~/.claudy/logs/claudy.log`.
10. **Memoria carga TODA la tabla en cada prompt** (`_load_memory()` lee todo y toma los últimos N) → consulta SQL directa + índice FTS5. Con memoria infinita esto hoy se degrada con el tiempo.
11. **Vault Obsidian se relee completo cada 5 min** → indexado incremental por mtime.
12. **Catálogo de modelos desactualizado** (`claude-sonnet-4-20250514`, `gpt-4o`…) → actualizar (claude-sonnet-4-6, claude-haiku-4-5, etc.).
13. **Pollinations (API gratuita de terceros) recibe tus prompts** como último fallback sin avisar → privacidad: pasa a opt-in en config.
14. **Bot Telegram lee config solo al arrancar** → recarga en caliente de token/usuarios/voz.
15. **Docs desactualizados** (README describe la versión Node/React que ya no existe) → reescribir.
16. **Solo 2 archivos de test** para 25K líneas → tests para memoria, intents y extracción LLM.

---

## 4. Fases del refactor

### Fase 0 — Seguridad y red de protección (½ día) ⚠️ PRIMERO
- [ ] Revocar el PAT de GitHub expuesto en el remote y reconfigurar `origin` sin token (Git Credential Manager).
- [ ] Tag `v4-estable` + backup completo (`scripts/backup-claudy-full.ps1`).
- [ ] Sacar `node_modules/` y `dist/` del índice de git (`git rm -r --cached`), ampliar `.gitignore`.
- [ ] Verificación: la app arranca igual que antes.

### Fase 1 — Limpieza de código muerto (1 día)
- [ ] Eliminar: `src/cli.ts`, `src/commands/`, `src/config.ts`, `src/web/`, `dist/`, `package.json`/`package-lock.json` (la CLI TS ya no es la app), `patch.py`, `patch_qcore.py`, `patch_ui.py`, `patch_ui2.py`, `fix_text.py`, `widen_sidebar.py`, `backup_original/`.
- [ ] **Solo Telegram**: eliminar `bg_discord_bot.py`, `bg_whatsapp_bot.py` y todo su cableado en `pet.py` (`_start_discord_if_configured`, `/vincular_discord`, menús, config keys).
- [ ] Mover `generate_moon_frames.py`, `generate_coffee_frames.py`, `gen_informe_rusa.py` a `tools/` (utilidades de desarrollo, no runtime).
- [ ] Verificación: arranque + chat + Telegram funcionan.

### Fase 2 — Partir el monolito `pet.py` (el corazón, 4-6 días)
Estructura objetivo (extracción incremental, un módulo por commit, la app debe arrancar tras cada paso):

```
src/desktop/
├── pet.py                  # Solo: ventana, sprite, animación, tray, drag (≈2.500 líneas)
├── core/
│   ├── config.py           # load/save config + secure_store
│   ├── memory.py           # Memoria infinita SQLite + FTS5 + resúmenes + checkpoints
│   ├── llm.py              # Cadena de proveedores + extract_text() único + tools
│   ├── prompts.py          # System prompt ÚNICO (variantes: escritorio / telegram)
│   ├── intents.py          # Registro de intents (decoradores, prioridades)
│   └── gateway.py          # Servidor HTTP 8720
├── channels/
│   └── telegram.py         # (ex bg_telegram_bot.py) único canal externo
├── features/
│   ├── documents.py        # docx/pdf/xlsx/pptx (orquestación; claudy_powers queda como lib)
│   ├── research.py         # deep_research
│   ├── scheduler.py        # task_scheduler + cron + alarmas
│   ├── email.py            # email_client + Mission Control drafts
│   ├── calendar.py         # google_calendar
│   └── kanban.py
└── ui/
    ├── chat.html           # SIN CAMBIOS VISUALES
    ├── webview_api.py      # WebViewApi + wrappers (ya casi extraíble tal cual)
    └── bubbles.py          # Burbujas tkinter legacy
```

Método: extraer clase/funciones → importar en `ClawdPet` (composición: `self.memory`, `self.llm`, `self.intents`…) → smoke test → commit. Sin big-bang.

### Fase 3 — Memoria: sigue infinita, ahora escala (1-2 días)
- [ ] **Garantía explícita**: nada se borra jamás — `memory` (caliente) + `memory_archive` (fría) + `memory_summaries`. Se documenta como contrato.
- [ ] Índice **FTS5** sobre memoria + archivo → recall instantáneo de toda la historia ("¿qué hablamos de Roadix en marzo?").
- [ ] `_build_memory_context`: dejar de cargar toda la tabla; SQL con `LIMIT` para lo reciente + FTS para lo relevante al prompt (incluye archivo).
- [ ] Vault Obsidian: índice incremental por mtime (no relectura completa).
- [ ] Comando `/memoria <consulta>` disponible en escritorio **y Telegram**.
- [ ] Migración automática al primer arranque; cero pérdida de datos.

### Fase 4 — Telegram como único canal, mejorado (2 días)
- [ ] Recarga en caliente de config (token, usuarios, ttsReply) sin reiniciar el bot.
- [ ] Formato nativo Telegram: el prompt de Telegram permite **negrita/cursiva/código** (HTML parse_mode) — hoy el prompt anti-markdown de tkinter empobrece las respuestas del bot.
- [ ] Progreso editando un solo mensaje ("escribiendo… 🔄") en vez de 5 mensajes sueltos.
- [ ] Watchdog: si el subproceso del bot muere, la app lo relanza sola y lo refleja en el indicador "Telegram: Conectado" del sidebar.
- [ ] `/memoria`, `/resumen` (resumen del día), `/estado` (salud de la app) como comandos del bot.
- [ ] Cola de mensajes si el Gateway está ocupado (hoy se serializa con timeout de 180 s).

### Fase 5 — Mejores respuestas e interacciones (2 días)
- [ ] **Un solo system prompt** en `core/prompts.py` con variantes por canal (escritorio = texto plano; Telegram = formato Telegram).
- [ ] Catálogo de modelos actualizado + router por tarea (rápido para charla, potente para informes/research).
- [ ] **Streaming activado por defecto** en el chat de escritorio (ya existe tras `_streaming_enabled`, hoy apagado).
- [ ] Intents unificados en `core/intents.py`: tabla única con prioridades; lo ambiguo cae al LLM con tool-calling (el `TOOL_REGISTRY` ya existe — usarlo como camino principal en vez de keywords).
- [ ] Pollinations **opt-in** (`config.providers.allowFreefallback: false` por defecto).
- [ ] Memoria de preferencias de estilo: si pides "más corto", se guarda y se inyecta al prompt.
- [ ] Respuestas con seguimiento: tareas largas reportan hitos reales (ya hay infraestructura de milestones — conectarla al progreso real de tools).

### Fase 6 — Calidad y cierre (1-2 días)
- [ ] `logging` a `~/.claudy/logs/claudy.log` con rotación; eliminar `except: pass` en rutas críticas (memoria, LLM, gateway, telegram).
- [ ] Tests: `test_memory.py` (guardar/buscar/archivar/FTS), `test_intents.py`, `test_llm_extract.py`.
- [ ] README + PROYECTO_ACTUALIZADO reescritos describiendo la arquitectura real.
- [ ] `requirements.txt` partido en core / opcional (`requirements-extras.txt`: playwright, torch, etc.).

**Total estimado: ~12-14 días de trabajo efectivo.** Cada fase deja la app funcionando; se puede pausar después de cualquier fase.

---

## 5. Mejoras claras para Claudy (punto 4 del pedido)

1. **Recall total**: FTS5 sobre TODA la historia (incluido archivo) — hoy solo busca con LIKE sobre la memoria caliente.
2. **Resumen diario por Telegram**: cron a las 21:00 con lo conversado/hecho del día (usa `memory_summaries`).
3. **Watchdog Telegram** + indicador del sidebar siempre veraz.
4. **Streaming visible** en el chat de escritorio por defecto.
5. **Hot-reload de config** (token Telegram, voz, modelos) sin reiniciar.
6. **Privacidad**: fallback gratuito de terceros solo si lo activas.
7. **Modelos 2026** + router por tipo de tarea.
8. **Logs reales** para diagnosticar en segundos lo que hoy es invisible.

## 6. Qué NO cambia (garantías)

- La UI queda **exactamente** como en la imagen aprobada.
- La memoria sigue siendo **infinita** (se refuerza: archivado explícito, nunca delete).
- Telegram sigue funcionando durante todo el refactor (es el único canal que queda).
- `memory.db` en Google Drive y el espejo Obsidian no se mueven de lugar.
- Los comandos actuales (`/buscar`, `/docx`, `/recordar`, `/vincular`, etc.) siguen respondiendo igual.
