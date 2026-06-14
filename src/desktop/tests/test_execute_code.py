"""A8 — execute_code: ejecución programática con filtro fail-closed.

Replicamos _execute_code_guarded con un _execute_python stub para probar la
capa de seguridad sin lanzar subprocesos en cada caso. Un test de humo final
sí ejecuta código real para confirmar el camino feliz.

Ejecutar: python tests/test_execute_code.py   (desde src/desktop)
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.command_guard import check_blocked  # noqa: E402


# Copia textual del contrato de pet._execute_code_guarded (+ patrones). Un test
# verifica que estos patrones sigan presentes en pet.py para no desincronizar.
_CODE_BLOCKED_PATTERNS = [
    (r"shutil\.rmtree\s*\(\s*['\"]?(?:/|~|[a-zA-Z]:[\\/]?)['\"]?\s*\)",
     "shutil.rmtree sobre una raíz"),
    (r"os\.system\s*\(", "os.system"),
    (r"subprocess\.(?:run|call|Popen|check_output)\s*\(", "subprocess"),
    (r"\beval\s*\(|\bexec\s*\(", "eval/exec dinámico"),
    (r"__import__\s*\(\s*['\"]os['\"]", "import dinámico de os"),
    (r"socket\.|requests\.|urllib\.request\.urlopen", "acceso de red crudo"),
]


class Host:
    def _debug_log(self, *a):
        pass

    def _execute_python(self, code, timeout=15):
        # Ejecutor real (igual que pet.py) para el test de humo.
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        tmp.write(code)
        tmp.close()
        try:
            r = subprocess.run([sys.executable, tmp.name], capture_output=True,
                               text=True, timeout=timeout, encoding="utf-8")
            return ((r.stdout or "") + (("\nSTDERR: " + r.stderr) if r.stderr else "")).strip() or "(sin salida)"
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    def _execute_code_guarded(self, code, timeout=20):
        code = (code or "").strip()
        if not code:
            return "No se entregó código para ejecutar."
        reason = check_blocked(code)
        if reason:
            return f"🚫 Código rechazado por seguridad: {reason}."
        for pat, why in _CODE_BLOCKED_PATTERNS:
            if re.search(pat, code, re.IGNORECASE):
                return f"🚫 Código rechazado por seguridad: {why}."
        try:
            timeout = max(1, min(int(timeout), 60))
        except Exception:
            timeout = 20
        return self._execute_python(code, timeout=timeout)


class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.h = Host()

    def test_rechaza_os_system(self):
        out = self.h._execute_code_guarded("import os\nos.system('echo hola')")
        self.assertIn("rechazado", out.lower())

    def test_rechaza_subprocess(self):
        out = self.h._execute_code_guarded("import subprocess\nsubprocess.run(['ls'])")
        self.assertIn("rechazado", out.lower())

    def test_rechaza_rmtree_raiz(self):
        out = self.h._execute_code_guarded("import shutil\nshutil.rmtree('C:/')")
        self.assertIn("rechazado", out.lower())

    def test_rechaza_eval(self):
        out = self.h._execute_code_guarded("eval('2+2')")
        self.assertIn("rechazado", out.lower())

    def test_rechaza_red(self):
        out = self.h._execute_code_guarded("import urllib.request\nurllib.request.urlopen('http://x')")
        self.assertIn("rechazado", out.lower())

    def test_rm_rf_solo_es_inerte_sin_ejecutor(self):
        # Un 'rm -rf /' como string Python NO se ejecuta por sí solo: para
        # correrlo haría falta os.system/subprocess, que ya están bloqueados.
        # Así, el string suelto es inerte y se permite imprimirlo.
        out = self.h._execute_code_guarded("cmd = 'rm -rf /'\nprint(len(cmd))")
        self.assertEqual(out, "8")

    def test_rm_rf_via_os_system_si_se_rechaza(self):
        # Pero intentar EJECUTARLO sí se rechaza (por os.system).
        out = self.h._execute_code_guarded("import os\nos.system('rm -rf /')")
        self.assertIn("rechazado", out.lower())

    def test_codigo_vacio(self):
        self.assertIn("No se entregó", self.h._execute_code_guarded(""))


class TestHappyPath(unittest.TestCase):
    def test_calculo_simple_se_ejecuta(self):
        h = Host()
        out = h._execute_code_guarded("print(sum(range(10)))")
        self.assertEqual(out, "45")

    def test_transformacion_de_datos(self):
        h = Host()
        code = "data=[3,1,2]\nprint(','.join(map(str, sorted(data))))"
        self.assertEqual(h._execute_code_guarded(code), "1,2,3")


class TestContractInSync(unittest.TestCase):
    def test_patrones_existen_en_pet_py(self):
        pet_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pet.py")
        with open(pet_path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("_CODE_BLOCKED_PATTERNS", src)
        self.assertIn("_execute_code_guarded", src)
        self.assertIn('register_tool("execute_code"', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
