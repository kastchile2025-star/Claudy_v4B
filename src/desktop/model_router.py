"""Model routing: clasifica el prompt y elige el modelo adecuado (C6).

Categorias:
  - simple:  saludos, preguntas cortas, traducciones, calculos -> modelo barato
  - code:    codigo, debugging, scripts, refactor -> modelo bueno para codigo
  - complex: informes, analisis, razonamiento multi-paso -> modelo potente
  - default: lo que no encaja arriba -> modelo default del usuario

Config (~/.claudy/config.json):
  "router": {"enabled": true, "simple": "...", "code": "...", "complex": "..."}

El hook vive en core/llm.py (send_quick_message): el chat del usuario se
clasifica con classify(); las llamadas internas tier="fast" usan el modelo
"simple" directo. Control por chat: /router (core/llm.py _router_cmd).

Nota es-CL: los patrones aceptan las dos grafías (con y sin tilde) porque
el dictado por voz y la escritura rápida mezclan ambas.
"""
import re

CATEGORIES = ("simple", "code", "complex", "default")

_CODE_HINTS = re.compile(
    r"\b(c[oó]digo|script|funci[oó]n(?:es)?|m[eé]todo|clase\b|class\b|def\b|"
    r"bug|error|excepci[oó]n|exception|traceback|stack\s*trace|"
    r"refactor\w*|depura\w*|debug\w*|compila\w*|"
    r"implementa\w*|programa\s+(?:en|que|un)|snippet|"
    r"python|javascript|typescript|java\b|rust|golang|c\+\+|c#|"
    r"sql|regex|json|yaml|html|css|api\b|endpoint|"
    r"unittest|pytest|tests?\b|"
    r"git\s+(?:commit|push|pull|merge|rebase|branch))\b",
    re.I,
)

_COMPLEX_HINTS = re.compile(
    r"\b(anal[ií]za\w*|an[aá]lisis|dise[ñn]a\w*|dise[ñn]o\s+de|"
    r"planea\w*|planifica\w*|plan\s+de\s+|estrategia|arquitectura|"
    r"compara\w*|comparaci[oó]n|eval[uú]a\w*|evaluaci[oó]n|"
    r"pros\s+y\s+contras|ventajas\s+y\s+desventajas|paso\s+a\s+paso|"
    r"explica\s+(?:detalladamente|en\s+detalle|a\s+fondo)|"
    r"investiga\w*|investigaci[oó]n|deep\s+research|"
    r"informe|reporte\b|ensayo|redacta\w*|"
    r"resumen\s+ejecutivo|razona\w*|justifica\w*|"
    r"por\s*qu[eé]\b|profundiza\w*|exhaustiv[oa])",
    re.I,
)

_SIMPLE_HINTS = re.compile(
    r"^(hola|holi|hi|hey|buenas|buenos\s+d[ií]as|buenas\s+(?:tardes|noches)|"
    r"gracias|ya\b|ok\b|dale|"
    r"qu[eé]\s+(?:hora|fecha|d[ií]a)|cu[aá]nto\s+(?:es|son|vale)|cu[aá]ntos?\s+son|"
    r"qu[eé]\s+es\b|qu[eé]\s+significa|define|definici[oó]n\s+de|"
    r"traduce|c[oó]mo\s+se\s+dice|convierte|"
    r"abre|cierra|l[ií]stame|ayuda)",
    re.I,
)


def classify(prompt: str) -> str:
    """Returns 'simple' | 'code' | 'complex' | 'default'."""
    if not prompt:
        return "default"
    p = prompt.strip()
    words = len(p.split())

    # Corto y empieza como pregunta/charla simple
    if words <= 12 and _SIMPLE_HINTS.search(p):
        return "simple"

    if _CODE_HINTS.search(p):
        return "code"

    # Largo, o con señales de razonamiento/informe
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
