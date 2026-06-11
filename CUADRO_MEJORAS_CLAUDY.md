# Cuadro de Mejoras de Claudy

**Fecha:** 10 de junio de 2026
**Fuentes:** informe "Funcionalidades de Hermes y OpenClaw" + informe "Apple Intelligence WWDC 2025/2026", cruzados con el estado real de Claudy v4B y los planes existentes (`HERMES_REPLICATION_PLAN.md`, `PLAN_REFACTORIZACION_CLAUDY_V5.md`).

**Leyenda Estado:** ✅ ya lo tiene · 🟡 parcial · 📋 ya planificado · 🆕 idea nueva
**Prioridad:** ⭐⭐⭐ alta (diferenciador real) · ⭐⭐ media · ⭐ baja

---

## A. Ideas extraídas de HERMES AGENT

| # | Funcionalidad | Qué aporta a Claudy | Estado | Prioridad | Esfuerzo |
|---|---|---|---|---|---|
| A1 | **Bucle de aprendizaje cerrado** (auto-skills): al terminar una tarea exitosa, evaluar y guardar el patrón como SKILL.md reusable, indexado en FTS5 | Claudy se vuelve más rápido y barato con el uso; el informe reporta grandes ahorros de tokens en tareas repetidas | 📋 (plan 2.4) | ⭐⭐⭐ | 6-8 h |
| A2 | **"The Curator"**: demonio que audita la biblioteca de skills, consolida redundantes y purga las de bajo uso | Evita que las auto-skills (A1) degeneren en basura acumulada; complemento natural del cron ya existente | 🆕 | ⭐⭐ | 3-4 h |
| A3 | **Filtro de comandos Manual / Smart / YOLO + fail-closed**: bloqueo permanente de comandos destructivos (`rm -rf /`, fork bombs); modo Smart usa un LLM barato para evaluar riesgo; timeout = denegar | Seguridad seria para los "poderes" de Claudy (hoy ejecuta con confirmaciones ad-hoc); el modo Smart es la joya: autonomía sin riesgo | ✅ (11 jun 2026, `core/command_guard.py`, comando `/permisos`) | ⭐⭐⭐ | 4-6 h |
| A4 | **Filtro de inyección de prompts y credenciales**: escanear entradas (Telegram, archivos analizados, webs scrapeadas) buscando intentos de reescribir directrices o exfiltrar `.env` | Claudy lee webs y documentos de terceros → vector de ataque real hoy | 🆕 | ⭐⭐⭐ | 2-3 h |
| A5 | **Memoria search-first formalizada**: buffer inmediato → ventana deslizante → FTS5 profundo, solo escalando si no se encuentra | Reduce ruido contextual y tokens; Claudy ya tiene FTS5 + contexto eficiente (fase 3 v5), falta formalizar el orden de escalada | 🟡 | ⭐⭐ | 2-3 h |
| A6 | **Sub-agentes efímeros jerárquicos** (`/delegate`): el principal instancia workers aislados sin comunicación horizontal | Tareas paralelas (investigar + redactar + descargar) sin contaminar el contexto principal | 📋 (plan 2.1) | ⭐⭐ | 4-6 h |
| A7 | **SOUL.md / personalidades**: identidad y directrices emocionales en archivo editable, con presets | Personalización rápida; encaja con el prompt único por canal ya hecho en v5 | 📋 (plan 1.3) | ⭐⭐ | 1 h |
| A8 | **execute_code / herramientas programáticas**: colapsar secuencias multi-paso en una sola llamada que ejecuta código | Menos latencia y menos llamadas al modelo en flujos como "informe": planificar una vez, ejecutar en local | 🆕 | ⭐⭐ | 4-6 h |
| A9 | **Optimización evolutiva de prompts (estilo DSPy/GEPA)**: leer trazas de ejecución (debug.log) y proponer mejoras a los prompts de sistema y SKILL.md | Versión ligera: un comando `/optimizar` que analiza los últimos fallos y sugiere ajustes de prompt | 🆕 | ⭐ | 6-8 h |
| A10 | **Pairing seguro de canales** (códigos efímeros TTL, rate-limit, lockout, chmod 0600) | Endurecer el emparejamiento del bot de Telegram con usuarios autorizados | 🆕 | ⭐⭐ | 2-3 h |
| A11 | **Gestor visual de configuración** (la Desktop app de Hermes lo destaca): GUI que reemplaza editar config.json a mano | Claudy ya tiene panel de ajustes parcial; completarlo para tokens, modelos, voz, canales | 🟡 | ⭐⭐ | 3-4 h |
| A12 | **Streaming de tool-calls en consola**: mostrar en vivo qué herramienta ejecuta el agente y su salida | La "CLAUDY CONSOLE" del chat ya muestra status; extenderlo a cada poder ejecutado da transparencia tipo Hermes Desktop | 🟡 | ⭐⭐ | 2-3 h |

## B. Ideas extraídas de OPENCLAW

| # | Funcionalidad | Qué aporta a Claudy | Estado | Prioridad | Esfuerzo |
|---|---|---|---|---|---|
| B1 | **Live Canvas controlado por el agente**: el agente decide renderizar visualizaciones interactivas según la sesión | Claudy ya tiene Canvas para informes; el salto es que Claudy lo abra por iniciativa propia con tablas/gráficos cuando la respuesta lo amerite | 🟡 | ⭐⭐⭐ | 4-6 h |
| B2 | **Precedencia de skills workspace > global**: skills por carpeta de proyecto que pisan a las globales | Claudy trabaja sobre proyectos QCORE distintos; permitiría comportamiento por producto (SmartStudent vs Roadix) | 🆕 | ⭐⭐ | 2-3 h |
| B3 | **Catálogo de recetas (estilo ClawHub)**: biblioteca local de automatizaciones preconfiguradas listas para instalar | Ya existe `/skill buscar` + find-skills; falta curar un catálogo propio QCORE (facturación, informes, scraping) | 🟡 | ⭐ | continuo |
| B4 | **Trazabilidad de linaje de sub-agentes**: metadatos de jerarquía para visualizar la ramificación de tareas | Si se hace A6/`/delegate`, mostrar el árbol de subtareas en el chat | 🆕 | ⭐ | 2-3 h |
| B5 | **Permisos auto-aprobados solo lectura + solo en CWD**: lo no destructivo dentro del workspace pasa solo; escrituras piden confirmación | Regla simple y sólida para los poderes de archivos de Claudy; combina con A3 | ✅ (11 jun 2026, READONLY_PATTERNS en `command_guard.py`) | ⭐⭐⭐ | incluido en A3 |
| B6 | **Lección negativa**: el modelo de permisos laxos de OpenClaw terminó en CVEs, plugins maliciosos y bloqueos institucionales | Validar/sandboxear skills de terceros antes de instalarlas (hoy `/skill install` confía a ciegas) | 🆕 | ⭐⭐ | 2-3 h |

## C. Ideas extraídas de APPLE WWDC 2025/2026

| # | Funcionalidad (origen) | Qué aporta a Claudy | Estado | Prioridad | Esfuerzo |
|---|---|---|---|---|---|
| C1 | **Notify Me** (Safari 2026): monitorizar una página y avisar ante cambios (precio, stock, texto) | "Claudy, avísame cuando baje el precio de X" → cron existente + scraper existente + aviso por Telegram. Win rápido y muy útil | ✅ (11 jun 2026, `features/watcher.py`, `/vigilar` + NL + indicadores mindicador.cl) | ⭐⭐⭐ | 3-4 h |
| C2 | **Describe a Shortcut / Describe an Extension** (2026): describir en lenguaje natural una automatización y que el sistema la genere | "Claudy, crea una skill que cada viernes me arme el resumen de facturas" → genera el SKILL.md + cron solo. Combina A1 + cron NL (plan 1.7) | 🆕 | ⭐⭐⭐ | 4-6 h |
| C3 | **On-screen awareness de Siri AI**: el asistente entiende lo que hay en pantalla y actúa sobre ello | Claudy ya saca screenshots y los analiza; el salto es accionar: "agenda lo que está en pantalla", "responde este correo visible" | 🟡 | ⭐⭐⭐ | 4-6 h |
| C4 | **Inteligencia visual sobre capturas** (2025): reconocer eventos en imágenes y crear citas de calendario automáticamente | Caso concreto del C3: screenshot/foto de un flyer → evento en Google Calendar (integración ya existente) | 🆕 | ⭐⭐ | 3-4 h |
| C5 | **Passwords agéntico** (2026): agente que navega en background y completa flujos web multi-paso solos | Es el caso de uso estrella del browser automation ya planificado (plan 2.2 Playwright): formularios, descargas de facturas, portales | 📋 (plan 2.2) | ⭐⭐⭐ | 4-6 h |
| C6 | **Jerarquía de modelos AFM 3** (router por complejidad): modelo chico para tareas rápidas, grande para razonamiento, especializado para imágenes | Router de modelos en Claudy: clasificación barata (haiku/qwen) para intents y resúmenes, premium solo para informes/código. Ahorro directo de costes | ✅ (11 jun 2026, `model_router.py` reescrito + comando `/router`) | ⭐⭐⭐ | 4-6 h |
| C7 | **Live Translation** (2025): traducción bidireccional en vivo en conversaciones | Comando/modo `/traducir` en chat y Telegram: Claudy traduce mensajes entrantes/salientes al vuelo | 🆕 | ⭐ | 2-3 h |
| C8 | **Hold Assist / Call Screening** (2025) → filtrado inteligente de interrupciones | Versión Claudy: resumir y priorizar notificaciones acumuladas de Telegram en una sola entrega ("3 mensajes importantes, 5 ruido") | 🆕 | ⭐ | 3-4 h |
| C9 | **Resúmenes de cámaras del hogar** (2026) → condensar alertas secuenciales en una notificación con descripción y búsqueda natural | Patrón aplicable al cron/scheduler: agrupar avisos repetidos del mismo origen en un digest | 🆕 | ⭐ | 2-3 h |
| C10 | **Memoria de conversación continua + app dedicada de Siri AI** | Valida el rumbo ya tomado (memoria infinita FTS5 + historial). Refuerzo, no acción nueva | ✅ | — | — |
| C11 | **Encuestas inteligentes en grupos** (2025) | Si el bot de Telegram entra a grupos: detectar decisiones pendientes y proponer encuesta nativa de Telegram | 🆕 | ⭐ | 2-3 h |

---

## Top 8 — Hoja de ruta sugerida (impacto/esfuerzo)

| Orden | Mejora | Por qué primero | Esfuerzo |
|---|---|---|---|
| 1 | ✅ **A3+B5 — Filtro de comandos Manual/Smart/YOLO + lectura libre solo en workspace** (hecho 11 jun 2026) | Seguridad es prerequisito para todo lo agéntico que viene después; el informe muestra cómo OpenClaw pagó caro ignorarla | 4-6 h |
| 2 | ✅ **C1 — Notify Me (vigilar páginas web)** (hecho 11 jun 2026) | Win rápido con piezas que ya existen (cron + scraper + Telegram); utilidad diaria inmediata | 3-4 h |
| 3 | ✅ **C6 — Router de modelos por complejidad** (hecho 11 jun 2026) | Ahorro de costes en cada interacción; mejora latencia percibida | 4-6 h |
| 4 | **A1 — Auto-skills (bucle de aprendizaje cerrado)** | El diferenciador de Hermes; Claudy ya tiene la mitad (skills + FTS5) | 6-8 h |
| 5 | **C2 — "Describe una skill" en lenguaje natural** | Multiplica el valor de A1: las skills las crea el usuario hablando | 4-6 h |
| 6 | **A4 — Filtro anti-inyección de prompts** | Claudy procesa contenido externo (webs, docs, Telegram) a diario | 2-3 h |
| 7 | **C3/C4 — Screenshot accionable (pantalla → calendario/correo)** | Efecto "wow" tipo Siri AI con integraciones que ya existen | 4-6 h |
| 8 | **A2 — The Curator (mantenimiento de skills)** | Necesario una vez que A1/C2 empiecen a generar skills solas | 3-4 h |

**Total estimado del Top 8: ~30-40 horas.**

## Notas

- Los ítems 📋 ya estaban en `HERMES_REPLICATION_PLAN.md`; este cuadro los confirma y los prioriza frente a las ideas nuevas.
- La regla de oro del plan v5 se mantiene: **la UI de chat.html no se toca visualmente**; todo lo de arriba es backend/funcionalidad (B1 usa el Canvas ya existente).
- Los dos informes fuente tienen cifras faltantes (campos perdidos al exportar a DOCX); las prioridades de este cuadro se basan en las funcionalidades descritas, no en sus métricas.
