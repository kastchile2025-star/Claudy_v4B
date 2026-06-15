"""scan_product_versions: responde "¿cuál es la última versión de <producto>?"
con el dato REAL del disco (POINT_v3), sin internet.

Regresión del bug donde Claudy se iba a internet para preguntar la versión de
un producto interno de QCORE (Point/Tentación a Granel).

Ejecutar: python tests/test_product_versions.py   (desde src/desktop)
"""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qcore_products import (  # noqa: E402
    scan_product_versions, scan_installers, build_context_prompt)


class TestScanVersions(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="claudy_pv_")

    def _mkdirs(self, *names):
        for n in names:
            os.makedirs(os.path.join(self.d, n), exist_ok=True)

    def test_ultima_por_numero_de_version(self):
        self._mkdirs("POINT_v1", "POINT_v2", "POINT_v3")
        items, ultima = scan_product_versions(self.d)
        self.assertEqual(ultima[0], "POINT_v3")

    def test_numero_gana_a_fecha(self):
        # v2 se crea después que v3 → igual gana v3 (mayor número de versión).
        os.makedirs(os.path.join(self.d, "APP_v3"))
        time.sleep(0.02)
        os.makedirs(os.path.join(self.d, "APP_v2"))
        items, ultima = scan_product_versions(self.d)
        self.assertEqual(ultima[0], "APP_v3")

    def test_sin_numeros_usa_mtime(self):
        os.makedirs(os.path.join(self.d, "alpha"))
        time.sleep(0.02)
        os.makedirs(os.path.join(self.d, "beta"))  # más reciente
        items, ultima = scan_product_versions(self.d)
        self.assertEqual(ultima[0], "beta")

    def test_ignora_ocultas_y_basura(self):
        self._mkdirs("v1", ".git", "__pycache__", "$RECYCLE")
        items, ultima = scan_product_versions(self.d)
        nombres = [it[0] for it in items]
        self.assertIn("v1", nombres)
        self.assertNotIn(".git", nombres)
        self.assertNotIn("__pycache__", nombres)

    def test_ruta_inexistente(self):
        items, ultima = scan_product_versions(r"X:\no\existe")
        self.assertEqual(items, [])
        self.assertIsNone(ultima)

    def test_ruta_vacia(self):
        items, ultima = scan_product_versions("")
        self.assertEqual((items, ultima), ([], None))

    def test_formatos_de_version_variados(self):
        self._mkdirs("proj v1", "proj-v2", "proj_version_5", "proj_v10")
        items, ultima = scan_product_versions(self.d)
        self.assertEqual(ultima[0], "proj_v10")  # 10 > 5 > 2 > 1


class TestScanInstallers(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="claudy_inst_")

    def _touch(self, name):
        with open(os.path.join(self.d, name), "w") as f:
            f.write("x")

    def test_ultimo_por_semver_no_alfabetico(self):
        # v1.3.10 > v1.3.7 numéricamente (alfabéticamente "10" < "7").
        self._touch("App_Instalador_v1.3.7.exe")
        self._touch("App_Instalador_v1.3.10.exe")
        self._touch("App_Instalador_v1.2.0.exe")
        insts, ultimo = scan_installers(self.d)
        self.assertEqual(ultimo[0], "App_Instalador_v1.3.10.exe")

    def test_v1_3_7_gana_a_v1_0_0(self):
        for v in ("1.0.0", "1.2.0", "1.3.0", "1.3.7"):
            self._touch(f"TentacionAGranel_Instalador_v{v}.exe")
        insts, ultimo = scan_installers(self.d)
        self.assertEqual(ultimo[0], "TentacionAGranel_Instalador_v1.3.7.exe")

    def test_solo_exe(self):
        self._touch("Instalador_v1.0.0.exe")
        self._touch("setup.iss")
        self._touch("wizard.bmp")
        insts, _ = scan_installers(self.d)
        self.assertEqual([i[0] for i in insts], ["Instalador_v1.0.0.exe"])

    def test_sin_exe(self):
        self._touch("readme.txt")
        self.assertEqual(scan_installers(self.d), ([], None))

    def test_ruta_inexistente(self):
        self.assertEqual(scan_installers(r"X:\nope"), ([], None))


class TestContextInjection(unittest.TestCase):
    def test_point_context_marca_la_ruta(self):
        # No dependemos de Drive: solo verificamos que el bloque se intenta
        # construir desde la ruta del producto (si Drive no está, sale vacío y
        # el resto del contexto sigue presente).
        ctx = build_context_prompt("Point")
        self.assertIn("Point", ctx)
        self.assertIn("[FIN CONTEXTO Point]", ctx)


if __name__ == "__main__":
    unittest.main(verbosity=2)
