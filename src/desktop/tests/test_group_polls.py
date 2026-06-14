"""C11 — Encuestas inteligentes en grupos (features/group_polls.py).

Prueba la detección de decisiones con opciones y, sobre todo, que NO dispare
con mensajes que no son una elección (falsos positivos = spam de encuestas).

Ejecutar: python tests/test_group_polls.py   (desde src/desktop)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.group_polls import detect_poll, GroupPollsMixin  # noqa: E402


class TestDetecta(unittest.TestCase):
    def test_dos_opciones_simples(self):
        p = detect_poll("¿pizza o sushi?")
        self.assertIsNotNone(p)
        self.assertEqual(set(o.lower() for o in p["options"]), {"pizza", "sushi"})

    def test_tres_opciones(self):
        p = detect_poll("¿nos juntamos el viernes, sábado o domingo?")
        self.assertIsNotNone(p)
        self.assertEqual(len(p["options"]), 3)

    def test_con_verbo_de_decision(self):
        p = detect_poll("¿qué prefieren, cine o teatro?")
        self.assertIsNotNone(p)
        self.assertIn("cine", [o.lower() for o in p["options"]])
        self.assertIn("teatro", [o.lower() for o in p["options"]])

    def test_lista_numerada(self):
        p = detect_poll("¿qué hacemos? 1) cine 2) parque 3) casa")
        self.assertIsNotNone(p)
        self.assertEqual(len(p["options"]), 3)

    def test_question_normalizada(self):
        p = detect_poll("¿café o té?")
        self.assertTrue(p["question"].startswith("¿"))
        self.assertTrue(p["question"].endswith("?"))


class TestNoDetecta(unittest.TestCase):
    def test_pregunta_sin_opciones(self):
        self.assertIsNone(detect_poll("¿cómo están todos?"))

    def test_afirmacion_no_es_encuesta(self):
        self.assertIsNone(detect_poll("hoy comimos pizza o sushi, riquísimo"))

    def test_pregunta_abierta(self):
        self.assertIsNone(detect_poll("¿qué opinan del proyecto?"))

    def test_una_sola_opcion(self):
        self.assertIsNone(detect_poll("¿vamos al cine?"))

    def test_opciones_demasiado_largas(self):
        # Frases largas: probablemente no es una elección simple → no encuesta.
        long = ("¿deberíamos contratar a la agencia que nos recomendó marcela "
                "o mejor seguir haciéndolo internamente con el equipo actual?")
        self.assertIsNone(detect_poll(long))

    def test_texto_vacio(self):
        self.assertIsNone(detect_poll(""))


class _Host(GroupPollsMixin):
    def __init__(self, enabled):
        self._enabled = enabled

    def load_claudy_config(self):
        return {"telegram": {"groupPolls": self._enabled}}


class TestMixin(unittest.TestCase):
    def test_desactivado_no_sugiere(self):
        self.assertIsNone(_Host(enabled=False)._suggest_group_poll("¿pizza o sushi?"))

    def test_activado_sugiere(self):
        out = _Host(enabled=True)._suggest_group_poll("¿pizza o sushi?")
        self.assertIsNotNone(out)
        self.assertEqual(len(out["options"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
