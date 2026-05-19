"""Model routing: clasifica el prompt y elige el modelo adecuado.

Categorias:
  - simple: saludos, definiciones cortas, calculos triviales -> modelo rapido/barato
  - code:   pide codigo, debugging, refactor -> modelo bueno para codigo
  - complex: tareas largas, razonamiento, multi-paso -> modelo mas potente
  - default: lo que no encaja en lo anterior -> modelo default del usuario
"""
import re


_CODE_HINTS = re.compile(
    r"\b(codigo|funcion|funci[oó]n|class\b|def\b|bug|error|traceback|stacktrace|"
    r"refactor|implementa|implement[aá]|escribe.*(?:script|funcion|programa)|"
    r"python|javascript|typescript|java|rust|golang|sql|regex|"
    r"compila|debug|test|tests|unittest|pytest)\b",
    re.I,
)

_COMPLEX_HINTS = re.compile(
    r"\b(analiza|disena|dise[ñn]a|planea|estrategia|arquitectura|"
    r"compara|evalua|eval[uú]a|pros y contras|paso a paso|"
    r"explica detalladamente|investiga|resumen ejecutivo|"
    r"razona|justifica|por que|porque\b)\b",
    re.I,
)

_SIMPLE_HINTS = re.compile(
    r"^(hola|holi|hi|hey|buenas|buenos dias|buenas tardes|gracias|"
    r"que (?:hora|fecha|dia)|cuanto es|cuantos? son|"
    r"que es\b|define|definicion de|abre|cierra|listame|ayuda)",
    re.I,
)


def classify(prompt: str) -> str:
    """Returns 'simple' | 'code' | 'complex' | 'default'."""
    if not prompt:
        return "default"
    p = prompt.strip()
    words = len(p.split())

    # Very short and matches simple patterns
    if words <= 12 and _SIMPLE_HINTS.search(p):
        return "simple"

    if _CODE_HINTS.search(p):
        return "code"

    # Long prompts or those with reasoning hints
    if words > 80 or _COMPLEX_HINTS.search(p):
        return "complex"

    if words <= 8:
        return "simple"

    return "default"


def pick_model(prompt: str, config: dict, fallback: str) -> str:
    """Choose a model based on prompt category.

    Config schema:
      router:
        enabled: true|false
        simple:  "provider/model"
        code:    "provider/model"
        complex: "provider/model"
    """
    router = (config or {}).get("router", {}) or {}
    if not router.get("enabled", False):
        return fallback
    category = classify(prompt)
    chosen = router.get(category)
    return chosen if chosen else fallback
