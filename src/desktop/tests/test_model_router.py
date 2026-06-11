"""Tests del router de modelos por complejidad (model_router.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from model_router import classify, pick_model  # noqa: E402


class TestClassifySimple(unittest.TestCase):
    def test_saludos_y_preguntas_cortas(self):
        for p in ("hola claudy", "buenos días", "gracias!",
                  "qué hora es", "que es un eclipse",
                  "qué es la fotosíntesis", "cuánto es 15% de 89000",
                  "traduce hello world", "cómo se dice gato en inglés",
                  "abre spotify"):
            self.assertEqual(classify(p), "simple", p)

    def test_corto_sin_pistas_es_simple(self):
        self.assertEqual(classify("dame ideas para el almuerzo"), "simple")


class TestClassifyCode(unittest.TestCase):
    def test_con_acentos_y_sin_acentos(self):
        for p in ("escribe una función que ordene una lista",
                  "escribe una funcion que ordene una lista",
                  "tengo un error en mi código python",
                  "tengo un error en mi codigo python",
                  "depura este script que tira traceback",
                  "haz refactoring de esta clase",
                  "arma una consulta sql para ventas por mes",
                  "necesito un regex para validar rut"):
            self.assertEqual(classify(p), "code", p)


class TestClassifyComplex(unittest.TestCase):
    def test_con_acentos_y_sin_acentos(self):
        for p in ("analiza las ventajas y desventajas de arrendar versus comprar",
                  "analízame el mercado inmobiliario de santiago",
                  "hazme un informe sobre la reforma de pensiones",
                  "redacta un ensayo sobre la inteligencia artificial",
                  "investiga a fondo las alternativas de hosting",
                  "compara aws contra azure para una pyme",
                  "evalúa esta estrategia de marketing",
                  "por qué fracasó la economía argentina",
                  "explícame paso a paso cómo funciona una hipoteca"):
            self.assertEqual(classify(p), "complex", p)

    def test_prompt_muy_largo_es_complex(self):
        p = "palabra " * 90
        self.assertEqual(classify(p), "complex")


class TestClassifyDefault(unittest.TestCase):
    def test_medio_sin_pistas(self):
        p = "cuéntame algo entretenido sobre la historia de valparaíso y sus cerros"
        self.assertEqual(classify(p), "default")

    def test_vacio(self):
        self.assertEqual(classify(""), "default")
        self.assertEqual(classify(None), "default")


class TestPickModel(unittest.TestCase):
    CFG = {"router": {"enabled": True, "simple": "barato", "code": "codigo",
                      "complex": "potente"}}

    def test_router_apagado_usa_fallback(self):
        cfg = {"router": {"enabled": False, "simple": "barato"}}
        self.assertEqual(pick_model("hola", cfg, "default-m"), "default-m")

    def test_rutea_por_categoria(self):
        self.assertEqual(pick_model("hola claudy", self.CFG, "d"), "barato")
        self.assertEqual(pick_model("depura mi código python", self.CFG, "d"), "codigo")
        self.assertEqual(pick_model("hazme un informe de mercado", self.CFG, "d"), "potente")

    def test_categoria_sin_modelo_usa_fallback(self):
        cfg = {"router": {"enabled": True, "complex": "potente"}}
        self.assertEqual(pick_model("hola", cfg, "d"), "d")

    def test_sin_config_usa_fallback(self):
        self.assertEqual(pick_model("hola", {}, "d"), "d")
        self.assertEqual(pick_model("hola", None, "d"), "d")


if __name__ == "__main__":
    unittest.main(verbosity=2)
