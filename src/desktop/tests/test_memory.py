"""Tests de core/memory.py — el contrato de memoria infinita.

Ejecutar: python -m pytest tests/test_memory.py -q   (desde src/desktop)
o:        python tests/test_memory.py
"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import MemoryMixin, MEMORY_MAX_MESSAGES


def make_dummy():
    tmp = tempfile.mkdtemp(prefix="claudy_memtest_")

    class Dummy(MemoryMixin):
        def _memory_db_path(self):
            return os.path.join(tmp, "memory.db")

        def _memory_jsonl_path(self):
            return os.path.join(tmp, "memory.jsonl")

        def _get_obsidian_vault(self):
            return ""

        def load_claudy_config(self):
            return {}

    d = Dummy()
    d._init_memory_db()
    return d


class TestMemoriaInfinita(unittest.TestCase):
    def test_fts_disponible(self):
        d = make_dummy()
        self.assertTrue(d._memory_fts_ok, "FTS5 debe estar disponible en Python 3.12+")

    def test_guardar_y_buscar_fts(self):
        d = make_dummy()
        d._save_memory_sqlite("Usuario", "la factura de COMBAS quedó enviada en marzo")
        d._save_memory_sqlite("Claudy", "Roadix tiene el módulo de inventario al día")
        hits = d._search_memory("factura combas")
        self.assertTrue(hits, "FTS debe encontrar por relevancia")
        self.assertIn("COMBAS", hits[0]["text"])

    def test_busqueda_sin_diacriticos(self):
        d = make_dummy()
        d._save_memory_sqlite("Usuario", "el módulo de facturación está listo")
        hits = d._search_memory("modulo facturacion")
        self.assertTrue(hits, "unicode61 remove_diacritics debe igualar módulo/modulo")

    def test_prune_nunca_pierde_mensajes(self):
        d = make_dummy()
        n = MEMORY_MAX_MESSAGES * 4 + 50
        for i in range(n):
            d._save_memory_sqlite("Usuario", f"mensaje historico {i}")
        conn = sqlite3.connect(d._memory_db_path())
        mem = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
        arc = conn.execute("SELECT COUNT(*) FROM memory_archive").fetchone()[0]
        fts = conn.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0]
        conn.close()
        self.assertEqual(mem + arc, n, "prune debe archivar, jamás borrar")
        self.assertEqual(fts, n, "el índice FTS retiene TODA la historia")

    def test_compresion_archiva_antes_de_borrar(self):
        d = make_dummy()
        n = MEMORY_MAX_MESSAGES * 3 + 10
        for i in range(n):
            d._save_memory_sqlite("Usuario", f"dato {i}")
        d._compress_context()
        conn = sqlite3.connect(d._memory_db_path())
        mem = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
        arc = conn.execute("SELECT COUNT(*) FROM memory_archive").fetchone()[0]
        conn.close()
        self.assertEqual(mem + arc, n, "la compresión debe archivar los originales")

    def test_load_recent_eficiente(self):
        d = make_dummy()
        for i in range(30):
            d._save_memory_sqlite("Usuario", f"m{i}")
        recent = d._load_recent_memory(5)
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[-1]["text"], "m29", "orden cronológico, último al final")

    def test_contexto_incluye_recall_antiguo(self):
        d = make_dummy()
        d._save_memory_sqlite("Usuario", "la clave del servidor roadix es importante")
        for i in range(60):
            d._save_memory_sqlite("Usuario", f"relleno {i}")
        ctx = d._build_memory_context("que sabes del servidor roadix")
        self.assertIn("Recuerdos relevantes", ctx)
        self.assertIn("roadix", ctx.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
