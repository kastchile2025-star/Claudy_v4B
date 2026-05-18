---
name: web-search-answer
description: Sintetizar resultados de búsqueda web en respuestas directas y útiles. Úsalo cuando el usuario pida buscar algo en internet, quiera información actualizada, precios, noticias, clima o cualquier dato en tiempo real.
---

# Web Search Answer

Usa esta skill cuando el usuario pida información que requiera búsqueda web: precios, clima, noticias, resultados deportivos, definiciones actuales, etc.

## Cómo responder con resultados de búsqueda

Cuando tengas resultados de internet:

1. **No muestres las URLs crudas** — el usuario quiere la respuesta, no los links.
2. **Sintetiza directamente**: toma lo más relevante de los resultados y responde en 2-4 líneas.
3. **Si el dato es específico** (precio, temperatura, marcador): dalo exacto y menciona la fuente brevemente.
4. **Si hay contradicción** entre fuentes: menciona la más confiable o la más reciente.

## Formato de respuesta

```
[Dato concreto o respuesta directa en 1-3 líneas]
Fuente: [nombre del sitio, opcional]
```

## Ejemplos

Usuario: "¿cuánto está el dólar hoy?"
Respuesta: "El dólar blue está a $1.250 (compra) / $1.270 (venta). Fuente: Cronista."

Usuario: "¿qué es ICTUE?"
Respuesta: "ICTUE (Instituto de Ciencia y Tecnología para la Unión Europea) es... [síntesis]. Fuente: ictue.org"

## Cuándo buscar vs cuándo responder desde conocimiento

**Busca en internet cuando:**
- Precios, cotizaciones, tarifas
- Clima y pronóstico
- Noticias recientes (últimos días/semanas)
- Resultados deportivos en vivo
- Horarios, disponibilidad, estado de servicios

**Responde desde conocimiento cuando:**
- Definiciones estables (¿qué es TCP/IP?)
- Conceptos históricos o científicos
- Código y programación
- Matemáticas

## Comando disponible

```
/buscar <consulta>
```
