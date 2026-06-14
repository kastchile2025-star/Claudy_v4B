"""B4 — linaje visual de sub-agentes.

Prueba el árbol que dibuja /linaje: agrupa por tarea raíz, cuelga los hijos de
su `parent`, tolera registros corruptos y refleja el estado (running/done).
Reimplementa el contrato de _load_subagent_records sobre un dir temporal y usa
la _render_subagent_tree real de pet.py (es @staticmethod pura).

Ejecutar: python tests/test_lineage.py   (desde src/desktop)
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_records(d):
    """Copia textual del contrato de ClawdPet._load_subagent_records."""
    records = {}
    for fn in os.listdir(d):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, fn), "r", encoding="utf-8") as f:
                rec = json.load(f)
        except Exception:
            continue
        sid = rec.get("id") or fn[:-5]
        rec.setdefault("id", sid)
        records[sid] = rec
    return records


def _render(records):
    # Importa la implementación real (no la reescribe): garantiza que el test
    # protege el código que se ejecuta de verdad.
    from pet import ClawdPet
    return ClawdPet._render_subagent_tree(records)


def _write(d, sid, **fields):
    fields.setdefault("id", sid)
    with open(os.path.join(d, f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(fields, f)


class TestLineage(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="claudy_lin_")

    def test_vacio(self):
        self.assertEqual(_render(_load_records(self.d)),
                         "Sin subagentes en el linaje.")

    def test_raiz_y_estado(self):
        _write(self.d, "a", task="investigar X", parent="root",
               root_task="informe X", status="done", started=1)
        out = _render(_load_records(self.d))
        self.assertIn("🌳 informe X", out)
        self.assertIn("✅ a: investigar X", out)
        # único hijo de la raíz → conector de cierre
        self.assertIn("└─", out)

    def test_running_vs_done(self):
        _write(self.d, "a", task="t1", parent="root", root_task="R",
               status="running", started=1)
        _write(self.d, "b", task="t2", parent="root", root_task="R",
               status="done", started=2)
        out = _render(_load_records(self.d))
        self.assertIn("⏳ a: t1", out)
        self.assertIn("✅ b: t2", out)

    def test_agrupa_por_tarea_raiz(self):
        _write(self.d, "a", task="t", parent="root", root_task="RAIZ1",
               status="done", started=1)
        _write(self.d, "b", task="t", parent="root", root_task="RAIZ2",
               status="done", started=2)
        out = _render(_load_records(self.d))
        self.assertIn("🌳 RAIZ1", out)
        self.assertIn("🌳 RAIZ2", out)

    def test_hijos_anidados(self):
        # Aunque A6 hoy prohíbe recursión, el render debe colgar un hijo de su
        # parent si los datos lo indican (extensibilidad futura).
        _write(self.d, "root1", task="raiz", parent="root", root_task="R",
               status="done", started=1)
        _write(self.d, "child1", task="sub", parent="root1", root_task="R",
               status="done", started=2)
        out = _render(_load_records(self.d))
        lines = out.splitlines()
        # El hijo aparece indentado bajo su padre.
        idx_parent = next(i for i, l in enumerate(lines) if "root1: raiz" in l)
        idx_child = next(i for i, l in enumerate(lines) if "child1: sub" in l)
        self.assertGreater(idx_child, idx_parent)
        self.assertTrue(lines[idx_child].startswith("   ") or
                        lines[idx_child].startswith("│"))

    def test_parent_ausente_es_raiz(self):
        # parent apunta a un id que no existe → se trata como raíz, no se pierde.
        _write(self.d, "huerfano", task="t", parent="desaparecido",
               root_task="R", status="done", started=1)
        out = _render(_load_records(self.d))
        self.assertIn("huerfano: t", out)

    def test_tolera_corrupto(self):
        _write(self.d, "ok", task="bien", parent="root", root_task="R",
               status="done", started=1)
        with open(os.path.join(self.d, "malo.json"), "w", encoding="utf-8") as f:
            f.write("{ no es json")
        out = _render(_load_records(self.d))
        self.assertIn("ok: bien", out)

    def test_trunca_tarea_larga(self):
        _write(self.d, "a", task="x" * 200, parent="root", root_task="R",
               status="done", started=1)
        out = _render(_load_records(self.d))
        self.assertIn("...", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
