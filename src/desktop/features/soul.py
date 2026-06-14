"""Claudy features.soul — SOUL.md: identidad y tono editables (A7).

Estilo Hermes: la personalidad y las directrices emocionales de Claudy viven en
un archivo de texto editable (~/.claudy/SOUL.md) que se inyecta en el system
prompt, en vez de estar hardcodeadas. Felipe puede editarlo a mano o cargar un
preset (`/alma <preset>`), y el cambio aplica a la próxima respuesta.

SOUL.md NO reemplaza el protocolo de respuesta de core/prompts.py (eso es
funcional y se mantiene): solo añade una capa de TONO y CARÁCTER. Por eso se
inyecta como un bloque acotado y marcado.

Mixin de ClawdPet: usa _set_response_text. Sin dependencias externas.
"""
import os

SOUL_FILENAME = "SOUL.md"

# Presets de personalidad. Cada uno es el cuerpo de un SOUL.md listo para usar.
PRESETS = {
    "default": (
        "# Alma de Claudy\n\n"
        "Eres cercano y directo, como un amigo técnico de confianza. Hablas en "
        "español natural, sin formalidad excesiva ni adornos. Vas al grano pero "
        "con calidez: un toque de humor cuando encaja, cero cuando Felipe está "
        "apurado o el tema es serio. Tienes criterio propio y lo dices.\n"
    ),
    "profesional": (
        "# Alma de Claudy — Profesional\n\n"
        "Eres sobrio, preciso y orientado a resultados. Tono ejecutivo: claro, "
        "estructurado, sin coloquialismos ni humor. Priorizas exactitud y "
        "concisión. Tratas cada tarea como si fuera para un cliente exigente.\n"
    ),
    "cercano": (
        "# Alma de Claudy — Cercano\n\n"
        "Eres cálido, empático y conversacional. Te interesas por cómo le va a "
        "Felipe, celebras los avances y suavizas las malas noticias sin ocultarlas. "
        "Humor amable y cercano, pero sin perder utilidad ni enrollarte.\n"
    ),
    "brutal": (
        "# Alma de Claudy — Brutal\n\n"
        "Eres directo hasta lo incómodo: dices la verdad sin envolverla. Cero "
        "halagos vacíos, cero rodeos. Si una idea es mala, lo dices y explicas por "
        "qué. Respetas a Felipe demasiado como para mentirle por cortesía. Firme, "
        "nunca grosero.\n"
    ),
    "mentor": (
        "# Alma de Claudy — Mentor\n\n"
        "Eres paciente y didáctico. No solo resuelves: explicas el porqué para que "
        "Felipe aprenda. Haces buenas preguntas, propones el siguiente paso y "
        "señalas trampas comunes. Animas el progreso sin condescendencia.\n"
    ),
}

MAX_SOUL_CHARS = 2000  # cota dura: el alma no debe inflar el prompt sin control


class SoulMixin:

    def _soul_path(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", SOUL_FILENAME)

    def _read_soul(self):
        """Contenido de SOUL.md (recortado), o '' si no existe/está vacío."""
        path = self._soul_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read(MAX_SOUL_CHARS + 200).strip()[:MAX_SOUL_CHARS]
        except Exception:
            return ""

    def _soul_context(self):
        """Bloque a inyectar en el system prompt. Si no hay SOUL.md, usa el
        preset 'default' implícito (sin escribir nada al disco)."""
        body = self._read_soul()
        if not body:
            body = PRESETS["default"].strip()
        return ("═══ ALMA (tono y carácter — SOUL.md) ═══\n"
                f"{body}\n"
                "Aplica este tono SIN romper el protocolo de respuesta de arriba.\n\n")

    def _write_soul(self, body):
        path = self._soul_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(body.rstrip() + "\n")
            return True
        except Exception:
            return False

    def _handle_soul_command(self, arg):
        """Comando /alma:
          /alma                 → muestra el alma actual
          /alma <preset>        → carga un preset (default/profesional/...)
          /alma presets         → lista los presets
          /alma editar          → dice dónde está el archivo para editarlo
        """
        arg = (arg or "").strip().lower()

        if not arg or arg in ("ver", "show"):
            body = self._read_soul() or PRESETS["default"].strip()
            origen = "SOUL.md" if self._read_soul() else "preset 'default' (no hay SOUL.md aún)"
            return f"🫀 Alma actual ({origen}):\n\n{body}"

        if arg in ("presets", "lista", "list"):
            return ("Presets de alma disponibles:\n"
                    + "\n".join(f"  • {name}" for name in PRESETS)
                    + "\n\nCárgalo con: /alma <preset>")

        if arg in ("editar", "edit", "archivo"):
            path = self._soul_path()
            if not os.path.exists(path):
                self._write_soul(PRESETS["default"])
            return (f"Edita tu alma aquí:\n{path}\n"
                    "Cualquier cambio aplica en la próxima respuesta.")

        if arg in PRESETS:
            if self._write_soul(PRESETS[arg]):
                return (f"🫀 Alma cambiada al preset '{arg}'.\n"
                        "Aplica desde la próxima respuesta. Edítala con /alma editar.")
            return "No pude escribir SOUL.md (revisa permisos en ~/.claudy)."

        return (f"No conozco el preset '{arg}'.\n"
                "Usa /alma presets para ver los disponibles, o /alma editar para personalizarla.")
