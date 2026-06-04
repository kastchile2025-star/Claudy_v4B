"""Tests for rag_index: local folder/document retrieval.

Forces the dependency-free hash embedding so tests never download a model.

Run from anywhere:
    python -m unittest discover -s src/desktop/tests -p "test_*.py"
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rag_index  # noqa: E402


class RagIndexTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="claudy_rag_")
        # Isolate persistence.
        rag_index.RAG_DIR = os.path.join(self._tmp, "rag")
        rag_index.VECS_PATH = os.path.join(rag_index.RAG_DIR, "vectors.jsonl")
        rag_index.META_PATH = os.path.join(rag_index.RAG_DIR, "meta.json")
        # Force the hash fallback (no model download).
        rag_index._model = None
        rag_index._model_tried = True
        # A small corpus with clearly distinct topics.
        self._docs = os.path.join(self._tmp, "docs")
        os.makedirs(self._docs)
        self._write("futbol.md", "El mundial de futbol se juega cada cuatro anios. "
                                 "Messi y la seleccion argentina ganaron el campeonato.")
        self._write("cocina.txt", "Receta de pan casero: harina, agua, levadura y sal. "
                                  "Hornear a 220 grados durante treinta minutos.")
        self._write("finanzas.md", "El presupuesto trimestral incluye ingresos y egresos. "
                                   "El flujo de caja determina la liquidez de la empresa.")

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write(self, name, content):
        with open(os.path.join(self._docs, name), "w", encoding="utf-8") as f:
            f.write(content)

    def test_hash_embed_is_normalized(self):
        v = rag_index._hash_embed("hola mundo hola")
        norm = sum(x * x for x in v) ** 0.5
        self.assertAlmostEqual(norm, 1.0, places=5)
        self.assertEqual(len(v), rag_index.HASH_DIM)

    def test_chunking(self):
        text = "palabra " * 500  # ~4000 chars
        chunks = rag_index._chunk(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= rag_index.CHUNK_CHARS for c in chunks))

    def test_index_and_search(self):
        result = rag_index.index_folder(self._docs)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["files_indexed"], 3)
        self.assertGreaterEqual(result["total_chunks"], 3)

        hits = rag_index.search("quien gano el mundial de futbol", k=3)
        self.assertTrue(hits)
        self.assertIn("futbol.md", hits[0]["path"])

        hits2 = rag_index.search("como hago pan en el horno", k=3)
        self.assertIn("cocina.txt", hits2[0]["path"])

    def test_reindex_is_idempotent_per_file(self):
        rag_index.index_folder(self._docs)
        first = rag_index.status()["chunks"]
        rag_index.index_folder(self._docs)  # same files again
        second = rag_index.status()["chunks"]
        self.assertEqual(first, second)  # no duplicate chunks

    def test_status_and_clear(self):
        rag_index.index_folder(self._docs)
        self.assertTrue(rag_index.status()["exists"])
        rag_index.clear()
        self.assertFalse(rag_index.status()["exists"])
        self.assertEqual(rag_index.search("anything"), [])


if __name__ == "__main__":
    unittest.main()
