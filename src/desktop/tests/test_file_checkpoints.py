"""Tests de snapshots y restauración de archivos (claudy_powers)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import claudy_powers as cp  # noqa: E402


class FileCheckpointBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="claudy_fck_")
        self.backups = os.path.join(self.tmp, "file_backups")
        os.makedirs(self.backups)
        self._orig_dir = cp._file_backups_dir
        cp._file_backups_dir = lambda: self.backups
        self.target = os.path.join(self.tmp, "notas.txt")
        with open(self.target, "w", encoding="utf-8") as f:
            f.write("version uno")

    def tearDown(self):
        cp._file_backups_dir = self._orig_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _read(self):
        with open(self.target, encoding="utf-8") as f:
            return f.read()


class TestSnapshotIndex(FileCheckpointBase):
    def test_snapshot_registra_en_indice(self):
        backup = cp._snapshot_file(self.target)
        self.assertTrue(os.path.isfile(backup))
        entries = cp._load_backup_index()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["original"], os.path.abspath(self.target))

    def test_archivo_inexistente_no_snapshotea(self):
        self.assertEqual(cp._snapshot_file(os.path.join(self.tmp, "no.txt")), "")
        self.assertEqual(cp._load_backup_index(), [])


class TestRestore(FileCheckpointBase):
    def test_write_file_y_deshacer(self):
        cp.write_file(self.target, "version dos")
        self.assertEqual(self._read(), "version dos")
        out = cp.restore_file_backup("")
        self.assertIn("Restaurado", out)
        self.assertEqual(self._read(), "version uno")

    def test_restaurar_por_ruta(self):
        otro = os.path.join(self.tmp, "otro.txt")
        with open(otro, "w", encoding="utf-8") as f:
            f.write("otro original")
        cp.write_file(self.target, "v2")
        cp.write_file(otro, "otro cambiado")
        out = cp.restore_file_backup(otro)
        self.assertIn("Restaurado", out)
        with open(otro, encoding="utf-8") as f:
            self.assertEqual(f.read(), "otro original")
        self.assertEqual(self._read(), "v2")  # el otro archivo no se toca

    def test_restaurar_por_numero(self):
        cp.write_file(self.target, "v2")
        cp.write_file(self.target, "v3")
        # [1] = snapshot de v2 (el más reciente), [2] = snapshot de v1
        out = cp.restore_file_backup("2")
        self.assertIn("Restaurado", out)
        self.assertEqual(self._read(), "version uno")

    def test_replace_in_file_tambien_snapshotea(self):
        cp.replace_in_file(self.target, "uno", "1")
        self.assertEqual(self._read(), "version 1")
        cp.restore_file_backup("")
        self.assertEqual(self._read(), "version uno")

    def test_la_restauracion_es_deshacible(self):
        cp.write_file(self.target, "version dos")
        cp.restore_file_backup("")           # vuelve a v1 (y respalda v2)
        self.assertEqual(self._read(), "version uno")
        cp.restore_file_backup("")           # el último snapshot ahora es v2
        self.assertEqual(self._read(), "version dos")

    def test_selector_sin_match(self):
        cp.write_file(self.target, "v2")  # hay snapshots, pero no de ese archivo
        self.assertIn("No encontré", cp.restore_file_backup("inexistente.doc"))

    def test_sin_snapshots(self):
        self.assertIn("No hay snapshots", cp.restore_file_backup(""))
        self.assertIn("No hay snapshots", cp.list_file_backups())

    def test_listado(self):
        cp.write_file(self.target, "v2")
        out = cp.list_file_backups()
        self.assertIn("notas.txt", out)
        self.assertIn("[1]", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
