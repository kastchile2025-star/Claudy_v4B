"""Tests de core/intents.py — registro declarativo de comandos /slash.

Verifica que el registro respeta las prioridades del despachador original
(el orden de la tabla), incluidos los casos borde históricos:
  - /recordar <texto>  -> alarma (_set_reminder), NO búsqueda de memoria
  - /memoria <texto>   -> búsqueda FTS (_search_memory_cmd)
  - /ejecutar <cmd>    -> comando shell (_execute_command), NO archivo
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.intents import IntentsMixin, SLASH_COMMANDS


class Probe(IntentsMixin):
    """Registra qué método del pet se habría llamado, sin ejecutar nada."""

    def __getattr__(self, name):
        def _f(*a, **k):
            return f"CALL:{name}:{a}"
        return _f


def dispatch(prompt):
    p = Probe()
    return p._dispatch_slash_command(prompt, prompt.lower().strip())


class TestSlashRegistry(unittest.TestCase):
    def test_tabla_no_vacia(self):
        self.assertGreaterEqual(len(SLASH_COMMANDS), 30)

    def test_buscar(self):
        h, r = dispatch("/buscar precio dolar")
        self.assertTrue(h)
        self.assertIn("_web_search_and_answer:('precio dolar',)", r)

    def test_recordar_es_alarma_no_memoria(self):
        h, r = dispatch("/recordar 10 minutos cafe")
        self.assertTrue(h)
        self.assertIn("_set_reminder", r)

    def test_memoria_es_busqueda_fts(self):
        h, r = dispatch("/memoria factura combas")
        self.assertTrue(h)
        self.assertIn("_search_memory_cmd", r)

    def test_ejecutar_es_comando_no_archivo(self):
        h, r = dispatch("/ejecutar dir")
        self.assertTrue(h)
        self.assertIn("_execute_command", r)

    def test_kanban_subcomandos(self):
        h, r = dispatch("/kanban add nueva tarea")
        self.assertIn("_kanban_add:('nueva tarea',)", r)
        h, r = dispatch("/kanban move 3 done")
        self.assertIn("_kanban_move:(3, 'done')", r)
        h, r = dispatch("/kanban")
        self.assertIn("_kanban_list", r)

    def test_worktree(self):
        h, r = dispatch("/worktree add experimento main")
        self.assertIn("_worktree_create:('experimento', 'main')", r)

    def test_checkpoint_default_manual(self):
        h, r = dispatch("/checkpoint")
        self.assertIn("_create_checkpoint:('manual',)", r)

    def test_rollback_sin_arg(self):
        h, r = dispatch("/rollback")
        self.assertIn("_rollback_checkpoint:(None,)", r)

    def test_comando_sin_arg_pide_uso(self):
        h, r = dispatch("/buscar")
        # "/buscar" sin espacio final no matchea "/buscar " -> no atendido
        self.assertFalse(h)

    def test_texto_normal_pasa_de_largo(self):
        h, _ = dispatch("hola como estas")
        self.assertFalse(h)
        h, _ = dispatch("que hora es")
        self.assertFalse(h)


if __name__ == "__main__":
    unittest.main(verbosity=2)
