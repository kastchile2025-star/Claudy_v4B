"""A7 — SOUL.md: personalidad editable (features/soul.py).

Prueba lectura/escritura del alma, carga de presets, el bloque que se inyecta
al system prompt y los comandos /alma, sobre un HOME temporal.

Ejecutar: python tests/test_soul.py   (desde src/desktop)
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.soul import SoulMixin, PRESETS, MAX_SOUL_CHARS  # noqa: E402


class Host(SoulMixin):
    def __init__(self, home):
        self._home = home

    def _soul_path(self):
        return os.path.join(self._home, ".claudy", "SOUL.md")


def make_host():
    return Host(tempfile.mkdtemp(prefix="claudy_soul_"))


class TestReadWrite(unittest.TestCase):
    def test_sin_archivo_lee_vacio(self):
        self.assertEqual(make_host()._read_soul(), "")

    def test_escribe_y_lee(self):
        h = make_host()
        self.assertTrue(h._write_soul("# Mi alma\nSoy directo."))
        self.assertIn("Soy directo", h._read_soul())

    def test_recorte_a_max(self):
        h = make_host()
        h._write_soul("x" * (MAX_SOUL_CHARS + 500))
        self.assertLessEqual(len(h._read_soul()), MAX_SOUL_CHARS)


class TestContext(unittest.TestCase):
    def test_contexto_sin_archivo_usa_default(self):
        ctx = make_host()._soul_context()
        self.assertIn("ALMA", ctx)
        # El default menciona "amigo técnico".
        self.assertIn("amigo técnico", ctx)

    def test_contexto_refleja_preset_cargado(self):
        h = make_host()
        h._handle_soul_command("brutal")
        ctx = h._soul_context()
        self.assertIn("Brutal", ctx)

    def test_contexto_no_rompe_protocolo(self):
        # El bloque dice explícitamente que no rompe el protocolo de arriba.
        self.assertIn("SIN romper el protocolo", make_host()._soul_context())


class TestCommands(unittest.TestCase):
    def test_lista_presets(self):
        out = make_host()._handle_soul_command("presets")
        for name in PRESETS:
            self.assertIn(name, out)

    def test_carga_preset_valido(self):
        h = make_host()
        out = h._handle_soul_command("mentor")
        self.assertIn("mentor", out.lower())
        self.assertIn("Mentor", h._read_soul())

    def test_preset_invalido(self):
        out = make_host()._handle_soul_command("klingon")
        self.assertIn("no conozco", out.lower())

    def test_ver_actual(self):
        h = make_host()
        h._handle_soul_command("profesional")
        out = h._handle_soul_command("")
        self.assertIn("Profesional", out)

    def test_editar_crea_archivo(self):
        h = make_host()
        out = h._handle_soul_command("editar")
        self.assertTrue(os.path.exists(h._soul_path()))
        self.assertIn("SOUL.md", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
