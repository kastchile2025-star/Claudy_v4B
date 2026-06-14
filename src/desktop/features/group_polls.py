"""Claudy features.group_polls — Encuestas inteligentes en grupos (C11).

Cuando el bot está en un grupo de Telegram y alguien plantea una decisión con
opciones ("¿pizza o sushi?", "¿nos juntamos el viernes o el sábado?"), Claudy
detecta la pregunta y propone una encuesta NATIVA de Telegram con esas opciones.

Pieza pura y testeable: detecta si un mensaje es una decisión con alternativas y
extrae las opciones. El bot decide si lanzar la encuesta (send_poll). Conservador
a propósito: solo dispara con una pregunta clara de elección, para no spamear.

Patrones que dispara:
  - "¿A o B?"            → opciones [A, B]
  - "¿A, B o C?"         → opciones [A, B, C]
  - "prefieren X o Y"    → opciones [X, Y]
  - listas con "1) .. 2) .." dentro de una pregunta.
"""
import re

# Conectores que separan alternativas. "o"/"u" son los principales en español.
_OR_SPLIT = re.compile(r"\s*(?:,|\bo\b|\bu\b|/)\s*", re.IGNORECASE)

# Verbos/forma que sugieren que se pide elegir (refuerza la señal de pregunta).
_DECISION_HINT = re.compile(
    r"\b(prefier|elegi|eligen|votam|decidi|qu[eé] tal|nos juntamos|"
    r"hacemos|pedimos|vamos|mejor|cu[aá]l|qu[eé] prefieren|opci[oó]n)\w*",
    re.IGNORECASE)

_STOP = {"el", "la", "los", "las", "un", "una", "de", "del", "al", "a", "que",
         "y", "en", "por", "para", "con", "es", "son", "se"}

MIN_OPTION_LEN = 1
MAX_OPTIONS = 10


def _clean_option(opt):
    opt = (opt or "").strip(" ¿?¡!.")
    # Quita prefijos de lista "1)", "a.", "-".
    opt = re.sub(r"^\s*(?:\d+[\).]|[a-z][\).]|[-*•])\s*", "", opt, flags=re.IGNORECASE)
    return opt.strip()


def detect_poll(text):
    """Si el mensaje plantea una decisión con opciones, devuelve
    {"question": ..., "options": [...]}; si no, None.

    Reglas conservadoras para no proponer encuestas a cada rato:
      - Debe ser una pregunta (termina en '?' o empieza con '¿').
      - Debe haber 2..MAX_OPTIONS alternativas separadas por o/u/coma.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    is_question = raw.endswith("?") or raw.startswith("¿") or "¿" in raw
    if not is_question:
        return None

    # Toma el tramo de la pregunta (entre ¿ y ?), o todo si no hay ¿.
    m = re.search(r"¿([^?]*)\?", raw)
    inner = m.group(1) if m else raw.strip("¿?").strip()

    # Caso lista numerada: "¿qué hacemos? 1) cine 2) parque 3) casa"
    list_opts = re.findall(r"(?:\d+[\).]|[-*•])\s*([^\d\n\-*•]+)", raw)
    if len(list_opts) >= 2:
        options = [_clean_option(o) for o in list_opts]
        options = [o for o in options if len(o) >= MIN_OPTION_LEN][:MAX_OPTIONS]
        if 2 <= len(options) <= MAX_OPTIONS:
            q = (m.group(1).strip() if m else "¿Qué eligen?")
            return {"question": _as_question(q), "options": options}

    # Caso "A o B [o C]": separa por conectores el tramo tras el último verbo guía.
    candidate = inner
    hint = _DECISION_HINT.search(inner)
    if hint:
        candidate = inner[hint.end():].strip(" :,")
    parts = [_clean_option(p) for p in _OR_SPLIT.split(candidate)]
    parts = [p for p in parts if p and p.lower() not in _STOP and len(p) >= MIN_OPTION_LEN]

    # Exige que el conector " o "/" u " aparezca de verdad (no solo comas), para
    # no confundir enumeraciones que no son una elección.
    if not re.search(r"\b[ou]\b|/", candidate, re.IGNORECASE):
        return None
    # Dedup conservando orden.
    seen, options = set(), []
    for p in parts:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            options.append(p)
    if not (2 <= len(options) <= MAX_OPTIONS):
        return None
    # Opciones demasiado largas → probablemente no es una elección simple.
    if any(len(o) > 60 for o in options):
        return None
    question = _as_question(inner)
    return {"question": question, "options": options}


def _as_question(text):
    text = (text or "").strip()
    if not text:
        return "¿Qué eligen?"
    if not text.endswith("?"):
        text = text.rstrip(".") + "?"
    if not text.startswith("¿"):
        text = "¿" + text
    return text


class GroupPollsMixin:
    """Engancha la detección de encuestas al flujo de mensajes de grupo del bot.

    Solo se activa en chats de grupo y si telegram.groupPolls está habilitado en
    config. La creación real de la encuesta (send_poll) la hace el bot; aquí solo
    decidimos si proponerla."""

    def _group_polls_enabled(self):
        try:
            cfg = self.load_claudy_config()
            return bool(cfg.get("telegram", {}).get("groupPolls", False))
        except Exception:
            return False

    def _suggest_group_poll(self, text):
        """Devuelve el dict de encuesta si procede, o None. El bot usa el
        resultado para llamar a send_poll."""
        if not self._group_polls_enabled():
            return None
        return detect_poll(text)
