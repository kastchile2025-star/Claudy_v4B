"""C7 — Live Translation (features/translation.py).

Prueba el parseo de idioma destino y la máquina de estados del modo continuo.
La traducción real (LLM) se stubea para no llamar a la red.

Ejecutar: python tests/test_translation.py   (desde src/desktop)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.translation import TranslationMixin, DEFAULT_TARGET  # noqa: E402


class Host(TranslationMixin):
    def __init__(self):
        self._translate_mode = False
        self._translate_target = None
        self.last_prompt = None

    def send_quick_message(self, prompt, **kw):
        self.last_prompt = prompt
        return "TRADUCCION"


class TestParseTarget(unittest.TestCase):
    def test_detecta_idioma_y_resto(self):
        lang, rest = Host()._parse_target_language("al inglés hola mundo")
        self.assertEqual(lang, "inglés")
        self.assertEqual(rest, "hola mundo")

    def test_sin_idioma_devuelve_none(self):
        lang, rest = Host()._parse_target_language("hola mundo")
        self.assertIsNone(lang)
        self.assertEqual(rest, "hola mundo")

    def test_idioma_desconocido_no_consume(self):
        lang, rest = Host()._parse_target_language("al klingon saludos")
        self.assertIsNone(lang)
        self.assertEqual(rest, "al klingon saludos")

    def test_acepta_alias_sin_acento(self):
        lang, _ = Host()._parse_target_language("al frances bonjour")
        self.assertEqual(lang, "francés")


class TestComandos(unittest.TestCase):
    def test_one_shot_default_ingles(self):
        h = Host()
        out = h._handle_translate_command("hola")
        self.assertIn("inglés", out)
        self.assertIn("TRADUCCION", out)
        self.assertFalse(h._translate_mode)

    def test_one_shot_con_idioma(self):
        h = Host()
        out = h._handle_translate_command("al portugués buenos días")
        self.assertIn("portugués", out)
        self.assertIn("buenos días", h.last_prompt)

    def test_activar_modo(self):
        h = Host()
        out = h._handle_translate_command("on")
        self.assertTrue(h._translate_mode)
        self.assertIn("ACTIVO", out)

    def test_activar_modo_con_idioma(self):
        h = Host()
        h._handle_translate_command("on al alemán")
        self.assertTrue(h._translate_mode)
        self.assertEqual(h._translate_target, "alemán")

    def test_desactivar_modo(self):
        h = Host()
        h._translate_mode = True
        out = h._handle_translate_command("off")
        self.assertFalse(h._translate_mode)
        self.assertIn("desactivado", out.lower())

    def test_cambiar_idioma_sin_texto(self):
        h = Host()
        out = h._handle_translate_command("al italiano")
        self.assertEqual(h._translate_target, "italiano")
        self.assertIn("italiano", out)

    def test_uso_vacio_muestra_ayuda(self):
        out = Host()._handle_translate_command("")
        self.assertIn("Uso:", out)


class TestModoContinuo(unittest.TestCase):
    def test_intercepta_cuando_activo(self):
        h = Host()
        h._translate_mode = True
        out = h._maybe_translate_incoming("texto normal")
        self.assertIsNotNone(out)
        self.assertIn("TRADUCCION", out)

    def test_no_intercepta_cuando_inactivo(self):
        h = Host()
        self.assertIsNone(h._maybe_translate_incoming("texto"))

    def test_no_traduce_comandos(self):
        h = Host()
        h._translate_mode = True
        self.assertIsNone(h._maybe_translate_incoming("/algo"))

    def test_target_por_defecto(self):
        self.assertEqual(Host()._translate_target_lang(), DEFAULT_TARGET)


if __name__ == "__main__":
    unittest.main(verbosity=2)
