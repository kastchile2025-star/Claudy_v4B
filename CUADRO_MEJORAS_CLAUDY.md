# Cuadro de Mejoras de Claudy

**Fecha:** 10 de junio de 2026
**Fuentes:** informe "Funcionalidades de Hermes y OpenClaw" + informe "Apple Intelligence WWDC 2025/2026", cruzados con el estado real de Claudy v4B y los planes existentes (`HERMES_REPLICATION_PLAN.md`, `PLAN_REFACTORIZACION_CLAUDY_V5.md`).

**Leyenda Estado:** ✅ ya lo tiene · 🟡 parcial · 📋 ya planificado · 🆕 idea nueva
**Prioridad:** ⭐⭐⭐ alta (diferenciador real) · ⭐⭐ media · ⭐ baja

---

## A. Ideas extraídas de HERMES AGENT

| # | Funcionalidad | Qué aporta a Claudy | Estado | Prioridad | Esfuerzo |
|---|---|---|---|---|---|
| A1 | **Bucle de aprendizaje cerrado** (auto-skills): al terminar una tarea exitosa, evaluar y guardar el patrón como SKILL.md reusable, indexado en FTS5 | Claudy se vuelve más rápido y barato con el uso; el informe reporta grandes ahorros de tokens en tareas repetidas | ✅ (11 jun 2026: índice FTS5 `skills_index.db` + carga search-first en `skill_loop.py`; el loop auto-skill ya estaba cableado) | ⭐⭐⭐ | 6-8 h |
| A2 | **"The Curator"**: demonio que audita la biblioteca de skills, consolida redundantes y purga las de bajo uso | Evita que las auto-skills (A1) degeneren en basura acumulada; complemento natural del cron ya existente | ✅ (`_curator_run` en `skill_loop.py`, pasada cada 24 h, archiva sin borrar) | ⭐⭐ | 3-4 h |
| A3 | **Filtro de comandos Manual / Smart / YOLO + fail-closed**: bloqueo permanente de comandos destructivos (`rm -rf /`, fork bombs); modo Smart usa un LLM barato para evaluar riesgo; timeout = denegar | Seguridad seria para los "poderes" de Claudy (hoy ejecuta con confirmaciones ad-hoc); el modo Smart es la joya: autonomía sin riesgo | ✅ (11 jun 2026, `core/command_guard.py`, comando `/permisos`) | ⭐⭐⭐ | 4-6 h |
| A4 | **Filtro de inyección de prompts y credenciales**: escanear entradas (Telegram, archivos analizados, webs scrapeadas) buscando intentos de reescribir directrices o exfiltrar `.env` | Claudy lee webs y documentos de terceros → vector de ataque real hoy | ✅ (11 jun 2026, `core/injection_guard.py` en extracción de documentos y resultados web) | ⭐⭐⭐ | 2-3 h |
| A5 | **Memoria search-first formalizada**: buffer inmediato → ventana deslizante → FTS5 profundo, solo escalando si no se encuentra | Reduce ruido contextual y tokens; Claudy ya tiene FTS5 + contexto eficiente (fase 3 v5), falta formalizar el orden de escalada | ✅ (13 jun 2026, `core/memory.py`: `_should_escalate_to_deep` — vault/FTS5/Obsidian solo si la ventana caliente no cubre las keywords del prompt) | ⭐⭐ | 2-3 h |
| A6 | **Sub-agentes efímeros jerárquicos** (`/delegate`): el principal instancia workers aislados sin comunicación horizontal | Tareas paralelas (investigar + redactar + descargar) sin contaminar el contexto principal | ✅ (13 jun 2026, aislamiento por ID en `_check_subagent_result` + bloqueo de recursión `CLAUDY_SUBAGENT`; **arreglado bug**: había 2 `_spawn_subagent` y el malo —archivos globales que colisionaban— pisaba al bueno) | ⭐⭐ | 4-6 h |
| A7 | **SOUL.md / personalidades**: identidad y directrices emocionales en archivo editable, con presets | Personalización rápida; encaja con el prompt único por canal ya hecho en v5 | ✅ (13 jun 2026, `features/soul.py`: `~/.claudy/SOUL.md` + 5 presets + `/alma`, inyectado en el system prompt) | ⭐⭐ | 1 h |
| A8 | **execute_code / herramientas programáticas**: colapsar secuencias multi-paso en una sola llamada que ejecuta código | Menos latencia y menos llamadas al modelo en flujos como "informe": planificar una vez, ejecutar en local | ✅ (13 jun 2026, tool `execute_code` en `pet.py` con filtro fail-closed `_execute_code_guarded`) | ⭐⭐ | 4-6 h |
| A9 | **Optimización evolutiva de prompts (estilo DSPy/GEPA)**: leer trazas de ejecución (debug.log) y proponer mejoras a los prompts de sistema y SKILL.md | Versión ligera: un comando `/optimizar` que analiza los últimos fallos y sugiere ajustes de prompt | ✅ (13 jun 2026, `features/optimizer.py`, comando `/optimizar`) | ⭐ | 6-8 h |
| A10 | **Pairing seguro de canales** (códigos efímeros TTL, rate-limit, lockout, chmod 0600) | Endurecer el emparejamiento del bot de Telegram con usuarios autorizados | ✅ (13 jun 2026, `core/pairing.py` + `/vincular` genera código en Desktop y lo canjea el bot) | ⭐⭐ | 2-3 h |
| A11 | **Gestor visual de configuración** (la Desktop app de Hermes lo destaca): GUI que reemplaza editar config.json a mano | Claudy ya tiene panel de ajustes parcial; completarlo para tokens, modelos, voz, canales | ✅ (13 jun 2026, `_build_config_panels` en `pet.py`: paneles de Modelo/Voz/Telegram en Ajustes) | ⭐⭐ | 3-4 h |
| A12 | **Streaming de tool-calls en consola**: mostrar en vivo qué herramienta ejecuta el agente y su salida | La "CLAUDY CONSOLE" del chat ya muestra status; extenderlo a cada poder ejecutado da transparencia tipo Hermes Desktop | ✅ (13 jun 2026, `_emit_tool_console` en `pet.py` + hook en `core/llm.py`, sin tocar el DOM) | ⭐⭐ | 2-3 h |

## B. Ideas extraídas de OPENCLAW

| # | Funcionalidad | Qué aporta a Claudy | Estado | Prioridad | Esfuerzo |
|---|---|---|---|---|---|
| B1 | **Live Canvas controlado por el agente**: el agente decide renderizar visualizaciones interactivas según la sesión | Claudy ya tiene Canvas para informes; el salto es que Claudy lo abra por iniciativa propia con tablas/gráficos cuando la respuesta lo amerite | ✅ (12 jun 2026, `features/canvas.py`: tool LLM `show_canvas` + `/canvas`, tablas + Chart.js) | ⭐⭐⭐ | 4-6 h |
| B2 | **Precedencia de skills workspace > global**: skills por carpeta de proyecto que pisan a las globales | Claudy trabaja sobre proyectos QCORE distintos; permitiría comportamiento por producto (SmartStudent vs Roadix) | ✅ (12 jun 2026, `workspaces` en config + `<workspace>/.claudy-skills` en `skill_loop.py`) | ⭐⭐ | 2-3 h |
| B3 | **Catálogo de recetas (estilo ClawHub)**: biblioteca local de automatizaciones preconfiguradas listas para instalar | Ya existe `/skill buscar` + find-skills; falta curar un catálogo propio QCORE (facturación, informes, scraping) | ✅ (13 jun 2026, `features/recipes.py`: 6 recetas QCORE + `/recetas` y `/receta instalar`) | ⭐ | continuo |
| B4 | **Trazabilidad de linaje de sub-agentes**: metadatos de jerarquía para visualizar la ramificación de tareas | Si se hace A6/`/delegate`, mostrar el árbol de subtareas en el chat | ✅ (14 jun 2026, `subagent_runner.py` persiste `parent`/`root_task`; `_render_subagent_tree` dibuja el árbol; comando `/linaje`/`/arbol`/`/tree`) | ⭐ | 2-3 h |
| B5 | **Permisos auto-aprobados solo lectura + solo en CWD**: lo no destructivo dentro del workspace pasa solo; escrituras piden confirmación | Regla simple y sólida para los poderes de archivos de Claudy; combina con A3 | ✅ (11 jun 2026, READONLY_PATTERNS en `command_guard.py`) | ⭐⭐⭐ | incluido en A3 |
| B6 | **Lección negativa**: el modelo de permisos laxos de OpenClaw terminó en CVEs, plugins maliciosos y bloqueos institucionales | Validar/sandboxear skills de terceros antes de instalarlas (hoy `/skill install` confía a ciegas) | ✅ (12 jun 2026, `core/skill_vetting.py`: veta inyecciones y comandos catastróficos; override con «confiar») | ⭐⭐ | 2-3 h |

## C. Ideas extraídas de APPLE WWDC 2025/2026

| # | Funcionalidad (origen) | Qué aporta a Claudy | Estado | Prioridad | Esfuerzo |
|---|---|---|---|---|---|
| C1 | **Notify Me** (Safari 2026): monitorizar una página y avisar ante cambios (precio, stock, texto) | "Claudy, avísame cuando baje el precio de X" → cron existente + scraper existente + aviso por Telegram. Win rápido y muy útil | ✅ (11 jun 2026, `features/watcher.py`, `/vigilar` + NL + indicadores mindicador.cl) | ⭐⭐⭐ | 3-4 h |
| C2 | **Describe a Shortcut / Describe an Extension** (2026): describir en lenguaje natural una automatización y que el sistema la genere | "Claudy, crea una skill que cada viernes me arme el resumen de facturas" → genera el SKILL.md + cron solo. Combina A1 + cron NL (plan 1.7) | ✅ (`/skill crear <desc>` en `skill_loop.py`, sugiere cron si detecta horario) | ⭐⭐⭐ | 4-6 h |
| C3 | **On-screen awareness de Siri AI**: el asistente entiende lo que hay en pantalla y actúa sobre ello | Claudy ya saca screenshots y los analiza; el salto es accionar: "agenda lo que está en pantalla", "responde este correo visible" | ✅ caso calendario (11 jun 2026, `features/screen_actions.py`); otros accionables (correo) pendientes | ⭐⭐⭐ | 4-6 h |
| C4 | **Inteligencia visual sobre capturas** (2025): reconocer eventos en imágenes y crear citas de calendario automáticamente | Caso concreto del C3: screenshot/foto de un flyer → evento en Google Calendar (integración ya existente) | ✅ (11 jun 2026, «agenda lo que está en pantalla» → visión → Google Calendar) | ⭐⭐ | 3-4 h |
| C5 | **Passwords agéntico** (2026): agente que navega en background y completa flujos web multi-paso solos | Es el caso de uso estrella del browser automation ya planificado (plan 2.2 Playwright): formularios, descargas de facturas, portales | ✅ (11 jun 2026, `features/browser.py`: /navegar + NL + 5 tools LLM, perfil persistente para logins) | ⭐⭐⭐ | 4-6 h |
| C6 | **Jerarquía de modelos AFM 3** (router por complejidad): modelo chico para tareas rápidas, grande para razonamiento, especializado para imágenes | Router de modelos en Claudy: clasificación barata (haiku/qwen) para intents y resúmenes, premium solo para informes/código. Ahorro directo de costes | ✅ (11 jun 2026, `model_router.py` reescrito + comando `/router`) | ⭐⭐⭐ | 4-6 h |
| C7 | **Live Translation** (2025): traducción bidireccional en vivo en conversaciones | Comando/modo `/traducir` en chat y Telegram: Claudy traduce mensajes entrantes/salientes al vuelo | ✅ (13 jun 2026, `features/translation.py`: `/traducir` one-shot + modo continuo `/traducir on`) | ⭐ | 2-3 h |
| C8 | **Hold Assist / Call Screening** (2025) → filtrado inteligente de interrupciones | Versión Claudy: resumir y priorizar notificaciones acumuladas de Telegram en una sola entrega ("3 mensajes importantes, 5 ruido") | ✅ (13 jun 2026, `features/digest.py`: encola cron/watcher, prioriza y agrupa; `/avisos` + `telegram.digestNotifications`) | ⭐ | 3-4 h |
| C9 | **Resúmenes de cámaras del hogar** (2026) → condensar alertas secuenciales en una notificación con descripción y búsqueda natural | Patrón aplicable al cron/scheduler: agrupar avisos repetidos del mismo origen en un digest | 🆕 | ⭐ | 2-3 h |
| C10 | **Memoria de conversación continua + app dedicada de Siri AI** | Valida el rumbo ya tomado (memoria infinita FTS5 + historial). Refuerzo, no acción nueva | ✅ | — | — |
| C11 | **Encuestas inteligentes en grupos** (2025) | Si el bot de Telegram entra a grupos: detectar decisiones pendientes y proponer encuesta nativa de Telegram | ✅ (13 jun 2026, `features/group_polls.py`: detecta "¿A o B?" y lanza `send_poll`; `telegram.groupPolls`) | ⭐ | 2-3 h |

---

## Top 8 — Hoja de ruta sugerida (impacto/esfuerzo)

| Orden | Mejora | Por qué primero | Esfuerzo |
|---|---|---|---|
| 1 | ✅ **A3+B5 — Filtro de comandos Manual/Smart/YOLO + lectura libre solo en workspace** (hecho 11 jun 2026) | Seguridad es prerequisito para todo lo agéntico que viene después; el informe muestra cómo OpenClaw pagó caro ignorarla | 4-6 h |
| 2 | ✅ **C1 — Notify Me (vigilar páginas web)** (hecho 11 jun 2026) | Win rápido con piezas que ya existen (cron + scraper + Telegram); utilidad diaria inmediata | 3-4 h |
| 3 | ✅ **C6 — Router de modelos por complejidad** (hecho 11 jun 2026) | Ahorro de costes en cada interacción; mejora latencia percibida | 4-6 h |
| 4 | ✅ **A1 — Auto-skills (bucle de aprendizaje cerrado)** (hecho 11 jun 2026) | El diferenciador de Hermes; Claudy ya tiene la mitad (skills + FTS5) | 6-8 h |
| 5 | ✅ **C2 — "Describe una skill" en lenguaje natural** (ya existía: `/skill crear`) | Multiplica el valor de A1: las skills las crea el usuario hablando | 4-6 h |
| 6 | ✅ **A4 — Filtro anti-inyección de prompts** (hecho 11 jun 2026) | Claudy procesa contenido externo (webs, docs, Telegram) a diario | 2-3 h |
| 7 | ✅ **C3/C4 — Screenshot accionable (pantalla → calendario)** (hecho 11 jun 2026) | Efecto "wow" tipo Siri AI con integraciones que ya existen | 4-6 h |
| 8 | ✅ **A2 — The Curator (mantenimiento de skills)** (ya existía en `skill_loop.py`) | Necesario una vez que A1/C2 empiecen a generar skills solas | 3-4 h |

**Total estimado del Top 8: ~30-40 horas.**

## Notas

- Los ítems 📋 ya estaban en `HERMES_REPLICATION_PLAN.md`; este cuadro los confirma y los prioriza frente a las ideas nuevas.
- La regla de oro del plan v5 se mantiene: **la UI de chat.html no se toca visualmente**; todo lo de arriba es backend/funcionalidad (B1 usa el Canvas ya existente).
- Los dos informes fuente tienen cifras faltantes (campos perdidos al exportar a DOCX); las prioridades de este cuadro se basan en las funcionalidades descritas, no en sus métricas.

## Estado al 13 jun 2026

Cerrada la segunda tanda: los 4 ítems que estaban 🟡 parciales (A5, A11, A12, B3)
y las 6 ideas 🆕 sin empezar (A8, A9, A10, C7, C8, C11) quedaron ✅ implementadas
y con tests (la suite pasó de 272 a 338 tests, todos en verde). Quedan como
únicos pendientes los ítems explícitamente abiertos/continuos: A6 y B4 (dependen
de `/delegate`), A7 (SOUL.md, plan 1.3), y el resto ya estaba ✅ en la primera tanda.
Módulos nuevos: `features/{translation,optimizer,digest,group_polls,recipes}.py`
y `core/pairing.py`.

## Tercera tanda — A6, A7 + salud estructural (13 jun 2026)

Cerrados los dos últimos pendientes (A6, A7) y un barrido de deuda técnica.
La suite subió a **391 tests, todos en verde**. Cambios:

- **Router de comandos** (`core/commands.py`): el dispatch vivía en una cadena
  de 50+ `if prompt.startswith(...)` dentro de `show_chat_bubble` (~2.800
  líneas, intestable). Ahora hay una tabla prefijo→handler testeable; conviven
  con la cadena vieja y se migran incrementalmente. Migrados: `/traducir`,
  `/recetas`, `/optimizar`, `/avisos`, `/vincular`, `/delegate`, `/subagents`,
  `/alma`. **Bug arreglado de paso**: `/vincular` sin args vinculaba un usuario
  "r" en vez de generar código.
- **Logging en rutas críticas** (`core/logging_setup.warn`): se reemplazaron los
  `except: pass` que ocultaban bugs en memoria (guardar/podar), cron
  (alarmas/jobs) y gateway por `log.warning`. Antes esos fallos eran invisibles.
- **Tests de scheduler y gateway** (antes sin cobertura). El de scheduler
  **descubrió un bug real**: "a las 8 de la noche" agendaba a las 08:00 en vez
  de 20:00 (y dejaba "de la noche" en el mensaje). Arreglado.
- **A6** además arregló un bug grave: había **dos** `_spawn_subagent`; el malo
  (archivos globales que se pisaban entre subagentes) tapaba al bueno y rompía
  `ok, msg = self._spawn_subagent(...)`.

Pendiente real que queda: **B4** (linaje visual de sub-agentes), que ahora es
viable sobre el A6 ya aislado. La regla de oro (no tocar chat.html) se mantuvo.

## Cuarta tanda — B4 + deuda + higiene de tests (14 jun 2026)

Cerrado el **último pendiente del cuadro (B4)** y dos frentes de calidad. La
suite subió a **411 tests, todos en verde y sin un solo ResourceWarning**.

- **B4 — linaje de sub-agentes**: `subagent_runner.py` ahora persiste `parent`
  y `root_task` (propagados por env desde `_spawn_subagent`); A6 sigue
  prohibiendo recursión, así que el árbol es raíz→hijos, pero el render es
  genérico. `_render_subagent_tree` dibuja con conectores ├─/└─ agrupando por
  tarea raíz; comando `/linaje` (alias `/arbol`, `/tree`) en el router, y
  `/subagents` ahora invita a usarlo. No toca el DOM. Tests: `test_lineage.py`.
- **Deuda de pet.py**: migrados 6 comandos más de la cadena de ~2.800 líneas al
  router testeable (`/board`, `/task`, `/play`, `/git` —incluido el caso
  commit—, `/skill buscar`, `/skill install`). `/skill use` se queda en la
  cadena (no era trivial). Tests del router: 13 → 30.
- **Higiene de tests**: eliminados todos los ResourceWarning. `mcp_client.close()`
  cierra los pipes stdin/stdout/stderr; `test_config_panels` y
  `test_telegram_format` cierran sus ficheros; y `test_screen_actions` ahora
  **mockea google_calendar** en vez de pegar a la red (era frágil —dependía de
  no tener Calendar conectado— y dejaba un socket SSL abierto).

Con esto el cuadro queda **100 % ✅**. La regla de oro (no tocar chat.html) se
mantuvo en las cuatro tandas.
