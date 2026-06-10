"""Tests del conversor markdown -> HTML de Telegram (channels/telegram_bot.py).

El módulo del bot hace sys.exit si no hay token, así que extraemos la
función pura md_to_telegram_html del fuente y la evaluamos aislada.
"""
import html
import os
import re
import sys
import unittest

_BOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "channels", "telegram_bot.py")


def _load_converter():
    src = open(_BOT, encoding="utf-8").read()
    fn_src = src[src.index("def md_to_telegram_html"):src.index("# Locate ffmpeg")]
    ns = {"re": re, "html": html}
    exec(fn_src, ns)
    return ns["md_to_telegram_html"]


md = _load_converter()


class TestTelegramFormat(unittest.TestCase):
    def test_negrita(self):
        self.assertEqual(md("hola **mundo**"), "hola <b>mundo</b>")

    def test_codigo_inline(self):
        self.assertEqual(md("usa `pip install`"), "usa <code>pip install</code>")

    def test_bloque_codigo(self):
        out = md("```python\nprint(1)\n```")
        self.assertEqual(out, "<pre>print(1)</pre>")

    def test_link(self):
        out = md("[QCORE](https://qcorespa.com)")
        self.assertEqual(out, '<a href="https://qcorespa.com">QCORE</a>')

    def test_escape_html(self):
        out = md("riesgo <script> & 1<2")
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("&amp;", out)

    def test_codigo_no_recibe_formato(self):
        out = md("`**no negrita**`")
        self.assertEqual(out, "<code>**no negrita**</code>")

    def test_titulo_a_negrita(self):
        self.assertEqual(md("## Resumen"), "<b>Resumen</b>")


if __name__ == "__main__":
    unittest.main(verbosity=2)
