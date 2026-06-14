"""Router de comandos (core/commands.py) — lo que el refactor hace testeable.

Antes, el dispatch vivía en un método de 2.800 líneas imposible de testear.
Ahora el match prefijo→handler y el ruteo se prueban con un pet falso.

Ejecutar: python tests/test_commands.py   (desde src/desktop)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.commands import (  # noqa: E402
    CommandRouter, CommandContext, build_default_router)


class FakePet:
    """Pet mínimo: registra qué métodos de mixin se llamaron."""
    def __init__(self):
        self.calls = []
        self.response = None

    def _set_response_text(self, txt):
        self.response = txt

    def _handle_translate_command(self, arg):
        self.calls.append(("translate", arg)); return f"tr:{arg}"

    def _optimize_prompts(self):
        self.calls.append(("optimize",)); return "opt"

    def _deliver_digest(self):
        self.calls.append(("digest",)); return "digest"

    def _recipes_catalog(self, arg):
        self.calls.append(("catalog", arg)); return "cat"

    def _install_recipe(self, slug):
        self.calls.append(("install", slug)); return "inst"

    def _generate_pairing_code(self):
        self.calls.append(("gencode",)); return "code"

    def _vincular_telegram_user(self, uid):
        self.calls.append(("vincular", uid)); return "linked"

    def _spawn_subagent(self, task):
        self.calls.append(("spawn", task)); return True, f"lanzado:{task}"

    def _list_subagents(self):
        self.calls.append(("list_sub",)); return "lista"

    def _get_subagent_result(self, sid):
        self.calls.append(("get_sub", sid)); return f"res:{sid}"

    def _subagent_tree(self):
        self.calls.append(("tree",)); return "🌳 árbol"

    def _kanban_list(self):
        self.calls.append(("board",)); return "tablero"

    def _kanban_add(self, txt):
        self.calls.append(("kadd", txt)); return "add"

    def _kanban_move(self, tid, col):
        self.calls.append(("kmove", tid, col)); return "move"

    def _kanban_delete(self, tid):
        self.calls.append(("kdel", tid)); return "del"

    def _spotify_play(self, q):
        self.calls.append(("play", q)); return "play"

    def _git_cmd(self, args):
        self.calls.append(("git", tuple(args))); return "git-out"

    def _search_skills_registry(self, q):
        self.calls.append(("skbuscar", q)); return "buscar"

    def _install_skill(self, src, force=False):
        self.calls.append(("skinstall", src, force)); return True, "instalada"


def make_ctx(pet, prompt):
    responded = []
    ran = []

    def respond(txt):
        responded.append(txt)

    def run_async(fn):
        ran.append(fn())  # síncrono en el test

    ctx = CommandContext(pet, prompt, respond, run_async)
    ctx._responded = responded
    ctx._ran = ran
    return ctx


class TestMatch(unittest.TestCase):
    def setUp(self):
        self.r = CommandRouter()
        self.r.register("/foo", lambda c: c.respond("foo"))

    def test_match_exacto_y_con_arg(self):
        self.assertIsNotNone(self.r._match("/foo"))
        self.assertIsNotNone(self.r._match("/foo bar"))

    def test_no_match_prefijo_parcial(self):
        # '/foobar' NO debe matchear '/foo'.
        self.assertIsNone(self.r._match("/foobar"))

    def test_prefijo_mas_largo_gana(self):
        r = CommandRouter()
        r.register("/skill", lambda c: "corto")
        r.register("/skill crear", lambda c: "largo")
        self.assertEqual(r._match("/skill crear x")(None), "largo")
        self.assertEqual(r._match("/skill list")(None), "corto")

    def test_exact_solo_iguales(self):
        r = CommandRouter()
        r.register("/ping", lambda c: "p", exact=True)
        self.assertIsNotNone(r._match("/ping"))
        self.assertIsNone(r._match("/ping algo"))


class TestArg(unittest.TestCase):
    def test_arg_extrae_resto(self):
        ctx = make_ctx(FakePet(), "/traducir al inglés hola")
        self.assertEqual(ctx.arg("/traducir"), "al inglés hola")

    def test_arg_vacio(self):
        ctx = make_ctx(FakePet(), "/avisos")
        self.assertEqual(ctx.arg("/avisos"), "")


class TestDefaultRouter(unittest.TestCase):
    def setUp(self):
        self.r = build_default_router()

    def test_traducir_llama_handler(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/traducir al inglés hola")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("translate", "al inglés hola"), pet.calls)

    def test_optimizar_exacto(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/optimizar")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("optimize",), pet.calls)

    def test_avisos(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/avisos")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("digest",), pet.calls)

    def test_receta_instalar(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/receta instalar factura-mensual-combas")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("install", "factura-mensual-combas"), pet.calls)

    def test_recetas_lista(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/recetas")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("catalog", ""), pet.calls)

    def test_vincular_sin_arg_genera_codigo(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/vincular")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("gencode",), pet.calls)

    def test_vincular_con_id(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/vincular 12345")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("vincular", "12345"), pet.calls)

    def test_delegate_lanza_subagente(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/delegate analiza pet.py")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("spawn", "analiza pet.py"), pet.calls)

    def test_delegate_sin_tarea_pide_tarea(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/delegate")
        self.assertTrue(self.r.dispatch(ctx))
        # No debe llamar a spawn si no hay tarea.
        self.assertNotIn(("spawn", ""), pet.calls)

    def test_subagents_lista(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/subagents")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("list_sub",), pet.calls)

    def test_subagent_con_id(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/subagent 20260613_x")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("get_sub", "20260613_x"), pet.calls)

    def test_linaje_muestra_arbol(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/linaje")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("tree",), pet.calls)

    def test_linaje_exacto_no_matchea_con_args(self):
        # /linaje es exact: '/linaje algo' no debe rutearse aquí.
        pet = FakePet()
        ctx = make_ctx(pet, "/linaje algo")
        self.assertFalse(self.r.dispatch(ctx))

    def test_board(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/board")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("board",), pet.calls)

    def test_task_add(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/task add comprar pan")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("kadd", "comprar pan"), pet.calls)

    def test_task_done(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/task done 3")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("kmove", "3", "done"), pet.calls)

    def test_play(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/play bad bunny")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("play", "bad bunny"), pet.calls)

    def test_git_status(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/git status")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("git", ("status",)), pet.calls)

    def test_git_commit_hace_add_y_commit(self):
        pet = FakePet()
        ctx = make_ctx(pet, '/git commit "mi mensaje"')
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("git", ("add", "-A")), pet.calls)
        self.assertIn(("git", ("commit", "-m", "mi mensaje")), pet.calls)

    def test_skill_buscar(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/skill buscar facturas")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("skbuscar", "facturas"), pet.calls)

    def test_skill_install_normal(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/skill install github.com/x/y")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("skinstall", "github.com/x/y", False), pet.calls)

    def test_skill_install_confiar_fuerza(self):
        pet = FakePet()
        ctx = make_ctx(pet, "/skill install github.com/x/y confiar")
        self.assertTrue(self.r.dispatch(ctx))
        self.assertIn(("skinstall", "github.com/x/y", True), pet.calls)

    def test_skill_use_cae_a_la_cadena(self):
        # /skill use NO está migrado: el router debe devolver False.
        pet = FakePet()
        ctx = make_ctx(pet, "/skill use foo")
        self.assertFalse(self.r.dispatch(ctx))

    def test_comando_no_registrado_cae(self):
        # Un comando que el router no conoce devuelve False (cae a la cadena vieja).
        pet = FakePet()
        ctx = make_ctx(pet, "/algo-que-no-existe")
        self.assertFalse(self.r.dispatch(ctx))


if __name__ == "__main__":
    unittest.main(verbosity=2)
