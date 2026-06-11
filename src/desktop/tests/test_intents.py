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


def nl(prompt, **attrs):
    """Despacha por la capa de lenguaje natural con un Probe configurable."""
    p = Probe()
    for k, v in attrs.items():
        setattr(p, k, v)
    return p._try_handle_skill_action(prompt)


class TestLimpiezaNL(unittest.TestCase):
    """Limpieza invocada en lenguaje natural (botón 🧹 y frases libres)."""

    def test_archivos_sobre_1gb(self):
        h, r = nl("limpiar todos los archivos que sea sobre 1GB")
        self.assertTrue(h)
        self.assertIn(f"_cleanup_big_files:({1024 ** 3},)", r)

    def test_archivos_mas_de_500mb(self):
        h, r = nl("busca los archivos de más de 500 mb")
        self.assertTrue(h)
        self.assertIn(f"_cleanup_big_files:({500 * 1024 ** 2},)", r)

    def test_alternativas_para_limpiar_el_pc(self):
        h, r = nl("busca todas las alternativas para limpiar el pc")
        self.assertTrue(h)
        self.assertIn("_cleanup_analyze", r)

    def test_seleccion_natural_con_propuesta_vigente(self):
        h, r = nl("limpia el 1 y el 3", _cleanup_proposals=[{"id": 1}])
        self.assertTrue(h)
        self.assertIn("_cleanup_execute:('1,3',)", r)

    def test_seleccion_sin_propuesta_no_ejecuta_limpieza(self):
        # Sin propuesta vigente la frase es ambigua: no debe ir a _cleanup_execute
        # (hoy la toma el scheduler de cron, comportamiento pre-existente).
        _, r = nl("limpia el 1 y el 3", _cleanup_proposals=None)
        self.assertNotIn("_cleanup_execute", str(r))


class TestCorroborarEnInternet(unittest.TestCase):
    """'corrobora/verifica X en internet' debe buscar de verdad, no responder
    de memoria inventando fuentes (bug del horario del mundial 2026)."""

    def test_corroborar_con_typo_dispara_busqueda(self):
        # Frase real del usuario, typo incluido ("correborarla")
        h, r = nl("el partido es a las 13:30 horas de Chile. tengo esta informacion "
                  "puedes correborarla en internet")
        self.assertTrue(h)
        self.assertIn("_web_search_and_answer", r)

    def test_verificar_en_internet(self):
        h, r = nl("verifica en internet la hora del partido inaugural del mundial")
        self.assertTrue(h)
        self.assertIn("_web_search_and_answer", r)

    def test_confirmar_online(self):
        h, r = nl("puedes confirmar online el precio del dólar hoy")
        self.assertTrue(h)
        self.assertIn("_web_search_and_answer", r)

    def test_verificar_sin_internet_no_dispara(self):
        # "verifica" sin mención de internet/web no debe ir a búsqueda web
        _, r = nl("verifica que el archivo config.json tenga el token")
        self.assertNotIn("_web_search_and_answer", str(r))


class TestDatoActualBuscaSiempre(unittest.TestCase):
    """Preguntas de datos actuales (horarios, precios, resultados, noticias)
    deben ir SIEMPRE a búsqueda web, sin depender de que el LLM obedezca."""

    def test_horario_de_evento(self):
        h, r = nl("horario partido inaugural mundial 2026 Chile")
        self.assertTrue(h)
        self.assertIn("_web_search_and_answer", r)

    def test_a_que_hora(self):
        h, r = nl("a que hora juega mexico con sudafrica")
        self.assertTrue(h)
        self.assertIn("_web_search_and_answer", r)

    def test_precio_actual(self):
        h, r = nl("precio del bitcoin")
        self.assertTrue(h)
        self.assertIn("_web_search_and_answer", r)

    def test_recordatorio_no_va_a_la_web(self):
        # "avísame cuando empieza..." es una alarma, no una búsqueda
        _, r = nl("avísame cuando empieza el partido")
        self.assertNotIn("_web_search_and_answer", str(r))

    def test_contexto_personal_no_va_a_la_web(self):
        # "cuándo es mi reunión" es del calendario propio, no de internet
        _, r = nl("cuándo es mi reunión con el equipo")
        self.assertNotIn("_web_search_and_answer", str(r))


class TestBusquedaArchivosNL(unittest.TestCase):
    """Búsqueda de archivos en lenguaje natural (botón 🔎 y frases libres)."""

    def test_busca_el_archivo_simple(self):
        h, r = nl("busca el archivo factura_mayo.pdf")
        self.assertTrue(h)
        self.assertIn("_search_files:('factura_mayo.pdf',)", r)

    def test_comodin_y_ubicacion_delante(self):
        h, r = nl("encuentra el archivo en el notebook *.iso")
        self.assertTrue(h)
        self.assertIn("_search_files:('*.iso',)", r)

    def test_ubicacion_al_final_se_quita(self):
        h, r = nl("busca el archivo informe.docx en mi pc")
        self.assertTrue(h)
        self.assertIn("_search_files:('informe.docx',)", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
