"""Claudy features.translation — Live Translation (C7).

Traducción al vuelo en el chat y en Telegram. Dos modos:

  one-shot : "/traducir <texto>"  o  "/traducir al ingles <texto>"
             traduce ese texto y responde, sin cambiar de estado.
  modo     : "/traducir on [al <idioma>]"  activa la traducción continua:
             cada mensaje siguiente de Felipe se traduce automáticamente al
             idioma destino hasta "/traducir off".

La traducción la hace el LLM con un prompt acotado (tier rápido) — sin
dependencias externas. El idioma destino por defecto es inglés; si el texto
ya está en el destino, se traduce al español (bidireccional básico).

Mixin de ClawdPet: usa send_quick_message. El estado vive en
self._translate_mode / self._translate_target (no se persiste: es de sesión).
"""
import re

# Idiomas soportados por nombre → etiqueta canónica que entiende el LLM.
LANGUAGES = {
    "ingles": "inglés", "inglés": "inglés", "english": "inglés", "en": "inglés",
    "español": "español", "espanol": "español", "castellano": "español", "es": "español",
    "frances": "francés", "francés": "francés", "fr": "francés",
    "portugues": "portugués", "portugués": "portugués", "pt": "portugués",
    "aleman": "alemán", "alemán": "alemán", "de": "alemán",
    "italiano": "italiano", "it": "italiano",
    "japones": "japonés", "japonés": "japonés", "ja": "japonés",
    "chino": "chino", "mandarin": "chino", "mandarín": "chino", "zh": "chino",
}

DEFAULT_TARGET = "inglés"

# "/traducir al ingles ..." / "al inglés:" — captura el idioma destino.
_TO_LANG_RX = re.compile(
    r"^\s*(?:al?|to|en|hacia)\s+([a-záéíóúñ]+)\s*[:,]?\s*", re.IGNORECASE)


class TranslationMixin:

    def _translate_target_lang(self):
        return getattr(self, "_translate_target", None) or DEFAULT_TARGET

    @staticmethod
    def _parse_target_language(text):
        """Si el texto empieza con 'al <idioma>', devuelve (idioma_canónico, resto).
        Si no, (None, texto). Reconoce solo idiomas de LANGUAGES."""
        m = _TO_LANG_RX.match(text or "")
        if not m:
            return None, (text or "").strip()
        lang_word = m.group(1).lower()
        canonical = LANGUAGES.get(lang_word)
        if not canonical:
            return None, (text or "").strip()
        return canonical, text[m.end():].strip()

    def _translate_text(self, text, target=None):
        """Traduce `text` al idioma destino. Bidireccional básico: si el texto
        ya parece estar en el destino, lo lleva al español."""
        text = (text or "").strip()
        if not text:
            return ""
        target = target or self._translate_target_lang()
        prompt = (
            "Eres un traductor. Traduce el siguiente texto al "
            f"{target}. Si el texto YA está en {target}, tradúcelo al español. "
            "Responde ÚNICAMENTE con la traducción, sin comillas, sin notas, "
            "sin explicaciones ni el idioma de origen.\n\n"
            f"Texto:\n{text}"
        )
        try:
            out = self.send_quick_message(
                prompt, _skip_skill_action=True, timeout=60,
                max_tokens=1000, tier="fast")
        except Exception as e:
            return f"(no pude traducir: {e})"
        return (out or "").strip()

    def _handle_translate_command(self, arg):
        """Maneja '/traducir ...'. Devuelve el texto de respuesta para el chat."""
        arg = (arg or "").strip()
        low = arg.lower()

        # Activar/desactivar el modo continuo.
        if low in ("on", "activar", "modo"):
            self._translate_mode = True
            return (f"🌐 Modo traducción ACTIVO → {self._translate_target_lang()}.\n"
                    "Cada mensaje que escribas lo traduzco. Desactívalo con /traducir off.")
        if low.startswith("on ") or low.startswith("activar "):
            lang, _ = self._parse_target_language(arg.split(None, 1)[1])
            if lang:
                self._translate_target = lang
            self._translate_mode = True
            return (f"🌐 Modo traducción ACTIVO → {self._translate_target_lang()}.\n"
                    "Desactívalo con /traducir off.")
        if low in ("off", "desactivar", "stop", "no"):
            self._translate_mode = False
            return "🌐 Modo traducción desactivado."

        # Cambiar idioma destino sin texto: "/traducir al frances"
        lang, rest = self._parse_target_language(arg)
        if lang and not rest:
            self._translate_target = lang
            estado = "activo" if getattr(self, "_translate_mode", False) else "para la próxima vez"
            return f"🌐 Idioma destino: {lang} ({estado}). Usa /traducir <texto> o /traducir on."

        # One-shot: "/traducir [al <idioma>] <texto>"
        if lang:
            target = lang
            text = rest
        else:
            target = self._translate_target_lang()
            text = arg
        if not text:
            return ("Uso: /traducir <texto>  ·  /traducir al inglés <texto>  ·  "
                    "/traducir on  ·  /traducir off")
        result = self._translate_text(text, target)
        return f"🌐 ({target})\n{result}"

    def _maybe_translate_incoming(self, prompt):
        """Si el modo continuo está activo, devuelve la traducción del prompt;
        si no, devuelve None (para que el flujo normal siga). El control de
        comandos (/traducir off, etc.) NO pasa por aquí."""
        if not getattr(self, "_translate_mode", False):
            return None
        text = (prompt or "").strip()
        if not text or text.startswith("/"):
            return None
        target = self._translate_target_lang()
        return f"🌐 ({target})\n{self._translate_text(text, target)}"
