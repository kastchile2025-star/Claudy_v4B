---
name: writing-plans
description: Escribir planes de implementación claros antes de codear — tareas pequeñas, rutas críticas, código de referencia. Úsalo cuando el usuario quiera planear una feature, refactor o tarea compleja.
---

# Writing Plans

Usa esta skill cuando el usuario quiera planear una implementación antes de escribir código. Un buen plan evita rewrites.

## Cuándo planear

- La tarea toca más de 3 archivos
- Hay múltiples enfoques posibles
- El usuario no está seguro de cómo empezar
- La tarea podría romperse en pasos paralelos

## Estructura del plan

```markdown
## Contexto
[Por qué se hace este cambio. El problema que resuelve.]

## Enfoque
[La estrategia elegida y por qué. Menciona alternativas descartadas si es relevante.]

## Tareas
1. [ ] Tarea pequeña y concreta → verificar con: [cómo saber que está lista]
2. [ ] Siguiente tarea → verificar con: [criterio]
3. [ ] ...

## Archivos clave
- `ruta/archivo.ts` — qué cambia aquí
- `ruta/otro.py` — qué cambia aquí

## Verificación final
[Cómo probar que todo el plan funcionó end-to-end]
```

## Reglas al planear

- Cada tarea debe ser ejecutable en 15-30 min. Si es más, subdivídela.
- Nombra archivos y funciones concretas, no "el módulo X".
- Si hay una función existente que hacer el trabajo, reutilízala — no la reinventes.
- El plan no debe suponer conocimiento que no tengas. Si falta contexto, pregunta primero.
- Las tareas deben estar en orden de dependencias (no puedes hacer la 3 sin la 1).

## Tamaño adecuado

Un plan para una feature de un día: 4-8 tareas.
Un plan para un bugfix: 2-4 tareas.
Si tienes más de 10 tareas, el alcance está mal definido — acótalo.
