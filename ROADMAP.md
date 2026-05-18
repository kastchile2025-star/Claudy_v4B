# Claudy — Hoja de Ruta de Mejoras

> Clasificación de 10 mejoras propuestas + sugerencias previas en 3 categorías de impacto.
> Última actualización: 2026-05-11

---

## 🔴 ALTO IMPACTO (Implementar primero)

### P1-1: Cancelación de streaming con Ctrl+C
**Problema:** Ctrl+C actualmente mata toda la sesión. El usuario quiere cancelar solo la respuesta en curso y seguir chateando.
**Solución:** Separar el handler SIGINT: si hay streaming activo, abortar el AbortController del stream; si no hay streaming, salir normalmente.
**Archivos:** `src/commands/chat.ts`
**Complejidad:** Baja (cambio en handler existente)

### P1-2: Auto-resumen de sesiones largas
**Problema:** Cuando una sesión crece mucho, el contexto se satura y el modelo pierde información relevante.
**Solución:** Detectar cuando los mensajes > umbral (ej. 30 mensajes). Llamar al modelo para generar un resumen compacto, reemplazar mensajes antiguos con el resumen, mantener los últimos N mensajes intactos.
**Archivos:** `src/commands/chat.ts`, `src/utils.ts`
**Complejidad:** Media (requiere llamada adicional al modelo)

### P1-3: Búsqueda semántica en memoria
**Problema:** El sistema de memoria actual usa scoring por keywords, que no captura contexto semántico.
**Solución:** Integrar embeddings locales (ej. `@xenova/transformers` o API de OpenCode) para almacenar y buscar memorias por similitud semántica. Mantener keyword search como fallback.
**Archivos:** `src/memory.ts`
**Complejidad:** Alta (cambio de arquitectura de memoria)

### P1-4: Drag & drop del pet
**Problema:** El pet no se puede mover fácilmente por la pantalla.
**Solución:** Implementar arrastre con mouse en la ventana del pet (tkinter `bind('<B1-Motion>')`).
**Archivos:** `src/desktop/pet.py`
**Complejidad:** Baja

### P1-5: Snap to edges
**Problema:** El pet puede quedar en posiciones incómodas que tapan contenido.
**Solución:** Al soltar el drag, detectar proximidad a bordes de pantalla y ajustar automáticamente.
**Archivos:** `src/desktop/pet.py`
**Complejidad:** Baja

### P1-6: Auto-start con Windows
**Problema:** El usuario tiene que lanzar Claudy manualmente cada vez.
**Solución:** Crear acceso directo en `shell:startup` o entrada en registro `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
**Archivos:** `src/desktop/pet.py` (nuevo módulo `autostart.py`)
**Complejidad:** Baja

### P1-7: System tray icon
**Problema:** No hay forma de minimizar Claudy a la bandeja del sistema.
**Solución:** Usar `pystray` o `pywin32` para crear icono en system tray con menú contextual (mostrar/ocultar/salir).
**Archivos:** `src/desktop/pet.py`
**Complejidad:** Media

### P1-8: Notificaciones nativas de Windows
**Problema:** Claudy no puede alertar al usuario cuando no está en foco.
**Solución:** Usar `win10toast` o `plyer` para enviar notificaciones toast de Windows (ej. cuando termina una tarea larga o hay un recordatorio).
**Archivos:** `src/desktop/pet.py`
**Complejidad:** Baja

---

## 🟡 MEDIO IMPACTO (Implementar segundo)

### P2-1: Cliente MCP para herramientas externas
**Problema:** Claudy no puede usar herramientas externas compatibles con MCP (Model Context Protocol).
**Servidores prioritarios:** Brave Search, GitHub, filesystem, fetch, memoria.
**Solución:** Implementar cliente MCP que se conecte a servidores locales, registre herramientas disponibles y las exponga al modelo como function calls.
**Archivos:** `src/mcp-client.ts` (nuevo), `src/commands/chat.ts`
**Complejidad:** Alta

### P2-2: Function calling nativo
**Problema:** Las herramientas actuales se ejecutan por detección de intents en el texto del usuario, no por decisión del modelo.
**Solución:** Si el modelo soporta function calling (OpenAI, Claude), pasar herramientas como tool definitions y dejar que el modelo decida cuándo usarlas.
**Archivos:** `src/opencode.ts`, `src/commands/chat.ts`
**Complejidad:** Media (depende de capacidades del modelo)

### P2-3: Búsqueda web robusta
**Problema:** DuckDuckGo scraping es frágil y se rompe frecuentemente.
**Solución:** Integrar API oficial (Brave Search, Serper, Tavily) o usar MCP server de búsqueda. Mantener DuckDuckGo como fallback gratuito.
**Archivos:** `src/websearch.ts`
**Complejidad:** Media

### P2-4: Búsqueda de sesiones por texto completo
**Problema:** No se puede buscar contenido dentro de sesiones pasadas.
**Solución:** Indexar mensajes de sesiones en SQLite o archivo de texto. Comando `/buscar <texto>` que devuelva sesiones y fragmentos relevantes.
**Archivos:** `src/session-search.ts` (nuevo), `src/commands/chat.ts`
**Complejidad:** Media

---

## 🟢 BAJO IMPACTO (Implementar tercero)

### P3-1: Soporte de imágenes
**Problema:** Claudy no puede analizar imágenes enviadas por el usuario.
**Solución:** Detectar paths de imágenes en el input, convertir a base64, enviar al modelo si soporta vision (GPT-4V, Claude, Gemini).
**Archivos:** `src/commands/chat.ts`, `src/opencode.ts`
**Complejidad:** Media (depende de capacidades del modelo)

### P3-2: Model routing inteligente
**Problema:** El usuario usa el mismo modelo para todo, incluso cuando un modelo más barato/rápido sería suficiente.
**Solución:** Clasificar la consulta (simple → modelo rápido, compleja → modelo potente, código → modelo con mejor coding). Routing transparente.
**Archivos:** `src/model-router.ts` (nuevo), `src/commands/chat.ts`
**Complejidad:** Media

### P3-3: Export multi-formato
**Problema:** Las sesiones solo se guardan en formato interno JSON.
**Solución:** Comando `/export <formato>` que genere archivos en Markdown, PDF, HTML, o TXT con formato limpio.
**Archivos:** `src/export.ts` (nuevo), `src/commands/chat.ts`
**Complejidad:** Baja

---

## 📋 Plan de Ejecución por Fases

### Fase 1: UX Desktop (Semanas 1-2)
- [ ] P1-4: Drag & drop del pet
- [ ] P1-5: Snap to edges
- [ ] P1-6: Auto-start con Windows
- [ ] P1-7: System tray icon
- [ ] P1-8: Notificaciones nativas

### Fase 2: CLI Core (Semanas 3-4)
- [ ] P1-1: Cancelación de streaming con Ctrl+C
- [ ] P1-2: Auto-resumen de sesiones largas
- [ ] P2-4: Búsqueda de sesiones por texto completo
- [ ] P3-3: Export multi-formato

### Fase 3: Inteligencia (Semanas 5-7)
- [ ] P1-3: Búsqueda semántica en memoria
- [ ] P2-3: Búsqueda web robusta
- [ ] P2-1: Cliente MCP
- [ ] P2-2: Function calling nativo

### Fase 4: Avanzado (Semanas 8+)
- [ ] P3-1: Soporte de imágenes
- [ ] P3-2: Model routing inteligente

---

## 📊 Resumen

| Categoría | Count | Esfuerzo total estimado |
|-----------|-------|------------------------|
| Alto impacto | 8 | 2-3 semanas |
| Medio impacto | 4 | 3-4 semanas |
| Bajo impacto | 3 | 2-3 semanas |
| **Total** | **15** | **7-10 semanas** |

## 🔗 Dependencias

- `P2-1 (MCP)` → `P2-2 (Function calling)`: MCP usa function calling como mecanismo de ejecución
- `P1-3 (Memoria semántica)` → `P2-4 (Búsqueda sesiones)`: Pueden compartir infraestructura de embeddings
- `P2-3 (Búsqueda web)` → `P2-1 (MCP)`: Brave Search MCP server puede reemplazar búsqueda custom
