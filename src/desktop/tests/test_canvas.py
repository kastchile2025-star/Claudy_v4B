"""Tests del Live Canvas agéntico (features/canvas.py)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from features.canvas import (  # noqa: E402
    CanvasMixin, markdown_to_html, normalize_chart, build_canvas_html,
)


class FakePet(CanvasMixin):
    def __init__(self, tmp):
        self.tmp = tmp
        self.opened = []
        self._current_session_msgs = []

    def _canvas_dir(self):
        return self.tmp

    def _canvas_open(self, path):
        self.opened.append(path)


class TestMarkdown(unittest.TestCase):
    def test_tabla_a_html(self):
        md = ("| Producto | Precio |\n"
              "|---|---|\n"
              "| Notebook | $549.990 |\n"
              "| Mouse | $12.990 |")
        out = markdown_to_html(md)
        self.assertIn("<table>", out)
        self.assertIn("<th>Producto</th>", out)
        self.assertIn("<td>$12.990</td>", out)
        self.assertNotIn("|---|", out)

    def test_titulos_negritas_listas(self):
        out = markdown_to_html("# Informe\n## Datos\n- punto **clave**\n- otro\ntexto `cod`")
        self.assertIn("<h1>Informe</h1>", out)
        self.assertIn("<h2>Datos</h2>", out)
        self.assertIn("<li>punto <b>clave</b></li>", out)
        self.assertIn("<code>cod</code>", out)

    def test_escapa_html_malicioso(self):
        out = markdown_to_html("texto <script>alert(1)</script>")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)


class TestChart(unittest.TestCase):
    def test_spec_completo(self):
        c = normalize_chart({"type": "line", "labels": ["E", "F"],
                             "datasets": [{"label": "Ventas", "data": [1, 2]}]})
        self.assertEqual(c["type"], "line")

    def test_acepta_json_string_y_data_simple(self):
        c = normalize_chart('{"type": "pie", "labels": ["A","B"], "data": [3,4], "title": "X"}')
        self.assertEqual(c["datasets"][0]["data"], [3, 4])

    def test_tipo_invalido_cae_a_bar(self):
        c = normalize_chart({"type": "hologram", "labels": ["A"], "data": [1]})
        self.assertEqual(c["type"], "bar")

    def test_invalidos(self):
        self.assertIsNone(normalize_chart(None))
        self.assertIsNone(normalize_chart("no es json"))
        self.assertIsNone(normalize_chart({"labels": [], "data": []}))


class TestBuildHtml(unittest.TestCase):
    def test_con_grafico_incluye_chartjs(self):
        doc = build_canvas_html("Ventas", "# Hola", {"labels": ["A"], "data": [1]})
        self.assertIn("chart.js", doc)
        self.assertIn("new Chart", doc)
        self.assertIn("<h1>Hola</h1>", doc)

    def test_sin_grafico_no_carga_chartjs(self):
        doc = build_canvas_html("Solo texto", "# Hola")
        self.assertNotIn("chart.js", doc)


class TestCanvasShow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="claudy_canvas_")
        self.pet = FakePet(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_show_guarda_y_abre(self):
        out = self.pet._canvas_show("Comparativa AWS vs Azure", "| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIn("Abrí el canvas", out)
        self.assertEqual(len(self.pet.opened), 1)
        with open(self.pet.opened[0], encoding="utf-8") as f:
            self.assertIn("<table>", f.read())

    def test_sin_contenido_no_abre(self):
        out = self.pet._canvas_show("Vacío", "")
        self.assertIn("no hay contenido", out)
        self.assertEqual(self.pet.opened, [])

    def test_cmd_sin_arg_usa_ultima_respuesta(self):
        self.pet._current_session_msgs = [
            {"role": "user", "text": "dame la tabla"},
            {"role": "bot", "text": "| x | y |\n|---|---|\n| 1 | 2 |"},
        ]
        out = self.pet._canvas_cmd("")
        self.assertIn("Abrí el canvas", out)

    def test_cmd_sin_arg_sin_historial(self):
        self.assertIn("Uso:", self.pet._canvas_cmd(""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
