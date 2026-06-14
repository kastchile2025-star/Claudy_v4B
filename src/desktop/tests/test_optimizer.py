"""A9 — Optimización ligera de prompts (features/optimizer.py).

Prueba el parseo del debug.log y la agrupación de fallos. La llamada al LLM se
stubea; verificamos que solo se invoca cuando hay fallos reales.

Ejecutar: python tests/test_optimizer.py   (desde src/desktop)
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.optimizer import (  # noqa: E402
    OptimizerMixin, parse_debug_blocks, summarize_failures)


SAMPLE_LOG = """[2026-06-13T10:00:00] ROUTER
modelo elegido: deepseek-chat

[2026-06-13T10:01:00] BROWSER ERROR
timeout al cargar la página sii.cl

[2026-06-13T10:02:00] AUTO-SKILL CREATED
nueva skill: foo

[2026-06-13T10:03:00] BROWSER ERROR
timeout al cargar otra página

[2026-06-13T10:04:00] COMMAND DENIED
rm -rf bloqueado por command_guard
"""


def make_host(log_text=""):
    tmp = tempfile.mkdtemp(prefix="claudy_opt_")
    path = os.path.join(tmp, "debug.log")
    if log_text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(log_text)

    class Host(OptimizerMixin):
        def __init__(self):
            self._path = path
            self.llm_called = False

        def _debug_log_path(self):
            return self._path

        def load_claudy_config(self):
            return {"agent": {"systemPrompt": "soy claudy"}}

        def _skill_catalog_brief(self):
            return "- foo: hace foo"

        def send_quick_message(self, prompt, **kw):
            self.llm_called = True
            return "Sugerencia: añade manejo de timeouts."

    return Host()


class TestParsing(unittest.TestCase):
    def test_parsea_bloques(self):
        blocks = parse_debug_blocks(SAMPLE_LOG)
        self.assertEqual(len(blocks), 5)
        self.assertEqual(blocks[0][1], "ROUTER")

    def test_agrupa_solo_fallos(self):
        counter, examples = summarize_failures(parse_debug_blocks(SAMPLE_LOG))
        # BROWSER ERROR (x2) y COMMAND DENIED son fallos; ROUTER y AUTO-SKILL no.
        self.assertEqual(counter["BROWSER ERROR"], 2)
        self.assertEqual(counter["COMMAND DENIED"], 1)
        self.assertNotIn("ROUTER", counter)
        self.assertNotIn("AUTO-SKILL CREATED", counter)


class TestComando(unittest.TestCase):
    def test_sin_log_no_llama_llm(self):
        h = make_host("")  # sin archivo
        out = h._optimize_prompts()
        self.assertIn("No hay trazas", out)
        self.assertFalse(h.llm_called)

    def test_log_sin_fallos_no_llama_llm(self):
        h = make_host("[2026-06-13T10:00:00] ROUTER\ntodo bien\n")
        out = h._optimize_prompts()
        self.assertIn("no veo fallos", out.lower())
        self.assertFalse(h.llm_called)

    def test_con_fallos_llama_llm_y_resume(self):
        h = make_host(SAMPLE_LOG)
        out = h._optimize_prompts()
        self.assertTrue(h.llm_called)
        self.assertIn("Sugerencia", out)
        self.assertIn("ningún cambio se aplicó", out)

    def test_lee_solo_la_cola_grande(self):
        # Un log enorme: solo se leen los últimos bytes, no debe romper.
        big = "[2026-06-13T10:00:00] INFO\nx\n\n" * 5000 + \
              "[2026-06-13T11:00:00] BROWSER ERROR\nfinal\n"
        h = make_host(big)
        raw = h._read_recent_debug(max_bytes=2000)
        self.assertLessEqual(len(raw), 2100)
        self.assertIn("BROWSER ERROR", raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
