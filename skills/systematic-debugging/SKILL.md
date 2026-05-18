---
name: systematic-debugging
description: Depuración sistemática en 4 fases — entiende el bug antes de arreglarlo. Úsalo cuando haya un error, crash, comportamiento inesperado o bug difícil de reproducir.
---

# Systematic Debugging

Usa esta skill cuando el usuario reporte un error, bug o comportamiento inesperado. El objetivo es encontrar la causa raíz antes de proponer una solución.

## Regla fundamental

NUNCA propongas una solución hasta completar las 4 fases. Un fix sin diagnóstico es adivinar.

## Fase 1: Entender el bug

- ¿Qué debería pasar vs qué pasa realmente?
- ¿Cuándo ocurre? ¿Siempre o bajo ciertas condiciones?
- ¿Hay un mensaje de error exacto? Cópialo completo.
- ¿Qué cambió antes de que apareciera? (código, dependencias, entorno)

## Fase 2: Reproducirlo

- Construye el caso mínimo que reproduce el fallo.
- Si no puedes reproducirlo, pide más contexto al usuario.
- Verifica en qué entorno ocurre (OS, versión de Node/Python/etc.).

## Fase 3: Aislar la causa raíz

- Usa logs, prints o debugger para trazar el flujo.
- Bisección: comenta código hasta encontrar la línea que falla.
- Lee el stack trace de abajo hacia arriba — el error real suele estar al fondo.
- Busca asunciones incorrectas en el código (tipos, nulls, orden de ejecución).

## Fase 4: Proponer y verificar el fix

- Explica la causa raíz antes de mostrar el código.
- El fix debe ser mínimo — no refactorices mientras depuras.
- Después del fix, verifica que el caso de reproducción ya no falla.
- Si el fix introduce nuevas asunciones, documéntalo.

## Formato de respuesta

```
CAUSA RAÍZ: [explicación en 1-2 líneas]
FIX: [código mínimo]
VERIFICACIÓN: [cómo confirmar que está resuelto]
```
