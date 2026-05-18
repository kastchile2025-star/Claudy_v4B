---
name: test-driven-development
description: TDD — forzar el ciclo RED-GREEN-REFACTOR. Tests antes que código. Úsalo cuando el usuario quiera implementar una función con tests, o cuando haya que agregar tests a código existente.
---

# Test-Driven Development

Usa esta skill para guiar al usuario en TDD: escribir el test que falla ANTES de escribir el código.

## El ciclo TDD

### 🔴 RED — Escribe el test que falla
```python
# El test describe exactamente qué debe hacer la función
def test_suma_dos_numeros():
    assert suma(2, 3) == 5  # suma() no existe todavía — el test debe FALLAR
```

Ejecuta: el test debe fallar con un error claro (no un error de sintaxis).

### 🟢 GREEN — Haz que el test pase con el mínimo código posible
```python
def suma(a, b):
    return a + b  # mínimo código para que el test pase
```

No escribas más de lo necesario. Si el test pasa con `return 5` hardcodeado, está bien por ahora — el siguiente test lo forzará a generalizarse.

### 🔵 REFACTOR — Limpia sin romper los tests
- Elimina duplicación
- Mejora nombres
- Simplifica lógica
Los tests deben seguir pasando tras el refactor.

## Reglas clave

- Nunca escribas código de producción sin un test rojo primero.
- Un test debe probar UNA sola cosa.
- Si el test es difícil de escribir, el diseño de la función está mal.
- Los tests son documentación — sus nombres deben describir el comportamiento.

## Ejemplo completo (Python/pytest)

```python
# tests/test_validador.py
def test_email_valido_acepta_formato_correcto():
    assert es_email_valido("user@example.com") == True

def test_email_invalido_rechaza_sin_arroba():
    assert es_email_valido("userexample.com") == False

def test_email_invalido_rechaza_cadena_vacia():
    assert es_email_valido("") == False
```

```python
# src/validador.py — escrito DESPUÉS de los tests
import re

def es_email_valido(email: str) -> bool:
    if not email:
        return False
    return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', email))
```

## Agregando tests a código existente

Si el código ya existe sin tests:
1. Escribe tests que describan el comportamiento ACTUAL (aunque sea incorrecto).
2. Ahora refactoriza con confianza — los tests capturarán regresiones.
3. Agrega tests para casos borde que no estaban cubiertos.
