"""Acceso a archivos: _file_search_roots resuelve las carpetas donde Claudy
puede buscar/leer (perfil + Drive/vault + fileAccess.searchRoots de config).

Regresión del bug donde Claudy solo miraba 4 carpetas del perfil y no Drive,
así que no encontraba los productos QCORE (POINT, Tentación) y se iba a internet.

Usa el _file_search_roots REAL de pet.py con un host que sobreescribe la config
y el vault. Para aislar de las carpetas reales del usuario, parchea
os.path.expanduser para que "~" apunte a un home temporal vacío.

Ejecutar: python tests/test_file_access.py   (desde src/desktop)
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pet import ClawdPet  # noqa: E402


class Host(ClawdPet):
    """Solo lo que _file_search_roots toca: load_claudy_config y _get_obsidian_vault.
    No llama a ClawdPet.__init__ (evita la GUI)."""
    def __init__(self, cfg, vault=None):
        self._cfg = cfg
        self._vault = vault

    def load_claudy_config(self):
        return self._cfg

    def _get_obsidian_vault(self):
        return self._vault


class TestFileSearchRoots(unittest.TestCase):
    def setUp(self):
        # Workspace aislado fuera del home real. Dentro creamos un "home" vacío
        # para que las carpetas de prueba NO queden cubiertas por ~.
        self.base = tempfile.mkdtemp(prefix="claudy_fa_")
        self.home = os.path.join(self.base, "home")
        os.makedirs(self.home, exist_ok=True)
        real_expand = os.path.expanduser

        def fake_expand(p):
            if p == "~" or p.startswith("~/") or p.startswith("~\\"):
                return p.replace("~", self.home, 1)
            return real_expand(p)

        self._patch = mock.patch("os.path.expanduser", side_effect=fake_expand)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def _mk(self, *names):
        out = []
        for n in names:
            p = os.path.join(self.base, n)
            os.makedirs(p, exist_ok=True)
            out.append(os.path.normpath(p))
        return out

    def test_incluye_searchroots_de_config(self):
        (proj,) = self._mk("proyecto")
        host = Host({"fileAccess": {"searchRoots": [proj]}})
        self.assertIn(proj, host._file_search_roots())

    def test_incluye_el_vault(self):
        (vault,) = self._mk("vault")
        host = Host({}, vault=vault)
        self.assertIn(vault, host._file_search_roots())

    def test_ignora_rutas_inexistentes(self):
        ghost = os.path.normpath(os.path.join(self.base, "no-existe"))
        host = Host({"fileAccess": {"searchRoots": [ghost]}})
        self.assertNotIn(ghost, host._file_search_roots())

    def test_deduplica_subcarpeta_de_otra_raiz(self):
        (parent,) = self._mk("padre")
        child = os.path.normpath(os.path.join(parent, "hijo"))
        os.makedirs(child, exist_ok=True)
        host = Host({"fileAccess": {"searchRoots": [parent, child]}})
        roots = host._file_search_roots()
        self.assertIn(parent, roots)
        self.assertNotIn(child, roots)  # ya cubierto por el padre

    def test_siempre_incluye_el_home(self):
        host = Host({})
        self.assertIn(os.path.normpath(self.home), host._file_search_roots())

    def test_config_vacia_no_explota(self):
        self.assertIsInstance(Host({})._file_search_roots(), list)

    def test_searchroots_no_lista_se_tolera(self):
        host = Host({"fileAccess": {"searchRoots": None}})
        self.assertIsInstance(host._file_search_roots(), list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
