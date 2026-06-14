"""A6 — Sub-agentes efímeros aislados.

Prueba el contrato de _check_subagent_result: recoge el subagente 'done' más
reciente sin recoger, lo marca como recogido, y NUNCA mezcla resultados de
distintos subagentes (cada uno en su <id>.json). Esto cubre el bug que tenía
la versión vieja (archivo global compartido).

Ejecutar: python tests/test_subagents.py   (desde src/desktop)
"""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Host:
    """Reimplementa el contrato de _check_subagent_result sobre un dir temporal,
    idéntico al de pet.py, para testearlo sin la app."""
    def __init__(self, d):
        self._d = d

    def _subagents_dir(self):
        return self._d

    # copia textual del método de pet.py
    def _check_subagent_result(self):
        d = self._subagents_dir()
        candidates = []
        for fn in os.listdir(d):
            if not fn.endswith(".json"):
                continue
            path = os.path.join(d, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            if data.get("status") == "done" and not data.get("collected"):
                candidates.append((os.path.getmtime(path), path, data))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        _, path, data = candidates[0]
        try:
            data["collected"] = True
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return data.get("result", "Sin resultado")


def _write(d, sid, status, result, collected=False, mtime=None):
    path = os.path.join(d, f"{sid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"id": sid, "status": status, "result": result,
                   "collected": collected}, f)
    if mtime:
        os.utime(path, (mtime, mtime))


class TestCheckResult(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="claudy_sub_")
        self.h = Host(self.d)

    def test_sin_subagentes(self):
        self.assertIsNone(self.h._check_subagent_result())

    def test_running_no_se_recoge(self):
        _write(self.d, "a", "running", "")
        self.assertIsNone(self.h._check_subagent_result())

    def test_recoge_done(self):
        _write(self.d, "a", "done", "resultado A")
        self.assertEqual(self.h._check_subagent_result(), "resultado A")

    def test_no_recoge_dos_veces(self):
        _write(self.d, "a", "done", "resultado A")
        self.assertEqual(self.h._check_subagent_result(), "resultado A")
        # La segunda vez ya está 'collected' → None.
        self.assertIsNone(self.h._check_subagent_result())

    def test_aislamiento_dos_subagentes_no_se_pisan(self):
        # El bug viejo: ambos escribían el mismo archivo global. Ahora cada uno
        # tiene su <id>.json y los dos resultados sobreviven.
        _write(self.d, "a", "done", "resultado A", mtime=time.time() - 10)
        _write(self.d, "b", "done", "resultado B", mtime=time.time())
        # Recoge el más reciente primero (B), luego A. Ninguno se pierde.
        first = self.h._check_subagent_result()
        second = self.h._check_subagent_result()
        self.assertEqual({first, second}, {"resultado A", "resultado B"})
        self.assertIsNone(self.h._check_subagent_result())


if __name__ == "__main__":
    unittest.main(verbosity=2)
