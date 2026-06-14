"""Claudy core.commands — Router de comandos slash (refactor estructural).

PROBLEMA QUE RESUELVE: el dispatch de comandos vivía como una cadena de 50+
`if prompt.startswith(...)` dentro de show_chat_bubble.submit (~2.800 líneas),
anidada en closures locales. Eso lo hacía intestable y obligaba a tocar un
método monstruoso para cualquier comando nuevo.

ENFOQUE INCREMENTAL (sin big-bang): este router CONVIVE con la cadena vieja.
- Los comandos migrados se registran aquí con un prefijo y un handler.
- pet.submit() llama primero a `dispatch`; si hay match, ejecuta y termina.
- Lo aún no migrado cae a la cadena existente, intacta. Cero riesgo.

Un handler recibe un `CommandContext` y devuelve True si manejó el comando.
El contexto encapsula lo que los closures locales daban (responder, correr en
background, status, entry) para que los handlers no dependan de variables
locales de submit y SEAN TESTEABLES con un contexto falso.
"""
import threading


class CommandContext:
    """Lo que un handler de comando necesita, sin acoplarse a show_chat_bubble.

    pet      : la instancia de ClawdPet (para _set_response_text, mixins, etc.)
    prompt   : el texto completo del comando ("/traducir al inglés hola").
    respond  : callback (texto) → muestra la respuesta y restaura el input.
    run_async: callback (fn) → corre fn() en background y muestra su retorno.
    """

    def __init__(self, pet, prompt, respond, run_async):
        self.pet = pet
        self.prompt = prompt
        self.respond = respond
        self.run_async = run_async

    def arg(self, prefix):
        """Texto tras el prefijo del comando, ya .strip()-eado.
        ctx.arg('/traducir') sobre '/traducir al inglés hola' → 'al inglés hola'."""
        rest = self.prompt[len(prefix):] if self.prompt.startswith(prefix) else ""
        return rest.strip()


class CommandRouter:
    """Tabla de prefijo → handler. El match es por prefijo más largo primero,
    para que '/skill crear' gane a '/skill' si ambos están registrados."""

    def __init__(self):
        self._routes = []  # [(prefix, handler, exact)]

    def register(self, prefix, handler, exact=False):
        """Registra un handler. Si exact=True, solo matchea el comando completo
        (igualdad tras strip), útil para '/optimizar' sin argumentos."""
        self._routes.append((prefix, handler, exact))
        # Prefijos más largos primero: '/skill crear' antes que '/skill'.
        self._routes.sort(key=lambda r: len(r[0]), reverse=True)
        return self

    def command(self, prefix, exact=False):
        """Azúcar de decorador: @router.command('/foo')."""
        def deco(fn):
            self.register(prefix, fn, exact)
            return fn
        return deco

    def _match(self, prompt):
        stripped = (prompt or "").strip()
        for prefix, handler, exact in self._routes:
            if exact:
                if stripped == prefix:
                    return handler
            else:
                # Prefijo seguido de fin de cadena o espacio: '/traducir' no debe
                # matchear '/traducirX', pero sí '/traducir' y '/traducir hola'.
                if stripped == prefix or stripped.startswith(prefix + " "):
                    return handler
        return None

    def dispatch(self, ctx):
        """Ejecuta el handler que matchee el prompt del contexto.
        Devuelve True si algún handler manejó el comando (y se debe terminar),
        False si ninguno matcheó (cae a la cadena vieja)."""
        handler = self._match(ctx.prompt)
        if handler is None:
            return False
        result = handler(ctx)
        # Un handler que devuelve None se considera 'manejado' (ya respondió).
        return True if result is None else bool(result)

    def prefixes(self):
        return [p for p, _, _ in self._routes]


def build_default_router():
    """Construye el router con los comandos ya extraídos a mixins limpios.

    Estos handlers NO dependen de los closures de submit ni de claudy_powers/
    claudy_extras: solo del pet y del contexto. Por eso son los primeros en
    migrar. Los demás comandos seguirán en la cadena vieja hasta migrarse.
    """
    router = CommandRouter()

    def _arg_for(ctx, *prefixes):
        """Resto del comando para el prefijo que realmente matchea el prompt."""
        for p in prefixes:
            if ctx.prompt.strip() == p or ctx.prompt.startswith(p + " "):
                return ctx.arg(p)
        return ""

    # C7 — Live Translation
    def _traducir(ctx):
        arg = _arg_for(ctx, "/traducir", "/translate")
        ctx.run_async(lambda: ctx.pet._handle_translate_command(arg))
    router.register("/traducir", _traducir)
    router.register("/translate", _traducir)

    # A9 — Optimización de prompts (sin argumentos)
    def _optimizar(ctx):
        ctx.pet._set_response_text("🔧 Analizando trazas de ejecución para optimizar...")
        ctx.run_async(lambda: ctx.pet._optimize_prompts())
    router.register("/optimizar", _optimizar, exact=True)
    router.register("/optimize", _optimizar, exact=True)

    # C8 — Digest de notificaciones (sin argumentos)
    def _avisos(ctx):
        ctx.respond(ctx.pet._deliver_digest())
    router.register("/avisos", _avisos, exact=True)
    router.register("/notificaciones", _avisos, exact=True)

    # B3 — Catálogo de recetas QCORE
    def _recetas(ctx):
        arg = _arg_for(ctx, "/recetas", "/receta")
        if ctx.prompt.startswith("/receta ") and (
                arg.startswith("instalar ") or arg.startswith("instala ")
                or arg.startswith("install ")):
            slug = arg.split(None, 1)[1].strip() if " " in arg else ""
            ctx.respond(ctx.pet._install_recipe(slug))
        else:
            ctx.respond(ctx.pet._recipes_catalog(arg))
    router.register("/recetas", _recetas)
    router.register("/receta", _recetas)

    # A10 — Pairing seguro de canales
    def _vincular(ctx):
        arg = _arg_for(ctx, "/vincular", "/vincula")
        if not arg:
            ctx.respond(ctx.pet._generate_pairing_code())
        else:
            ctx.respond(ctx.pet._vincular_telegram_user(arg))
    router.register("/vincular", _vincular)
    router.register("/vincula", _vincular)

    # A6 — Sub-agentes efímeros
    def _delegate(ctx):
        task = _arg_for(ctx, "/delegate", "/delegar")
        if not task:
            ctx.respond("¿Qué tarea delego? Ej: /delegate analizar el código de pet.py")
            return
        ok, msg = ctx.pet._spawn_subagent(task)
        ctx.respond(msg)
    router.register("/delegate", _delegate)
    router.register("/delegar", _delegate)

    def _subagents(ctx):
        ctx.respond(ctx.pet._list_subagents())
    router.register("/subagents", _subagents, exact=True)
    router.register("/subagentes", _subagents, exact=True)

    def _subagent(ctx):
        sid = _arg_for(ctx, "/subagent", "/subagente")
        if not sid:
            ctx.respond("Uso: /subagent <id>  (mira /subagents para los IDs)")
            return
        ctx.respond(ctx.pet._get_subagent_result(sid))
    router.register("/subagent", _subagent)
    router.register("/subagente", _subagent)

    # B4 — linaje visual de sub-agentes (árbol de subtareas de /delegate)
    def _linaje(ctx):
        ctx.respond(ctx.pet._subagent_tree())
    router.register("/linaje", _linaje, exact=True)
    router.register("/arbol", _linaje, exact=True)
    router.register("/tree", _linaje, exact=True)

    # A7 — Alma editable (SOUL.md)
    def _alma(ctx):
        arg = _arg_for(ctx, "/alma", "/soul")
        ctx.respond(ctx.pet._handle_soul_command(arg))
    router.register("/alma", _alma)
    router.register("/soul", _alma)

    # ── Deuda estructural: comandos "solo responder texto" migrados de la
    # cadena de show_chat_bubble. Todos cumplen el contrato respond(): no tocan
    # widgets locales (status/entry/after) salvo lo que respond() ya encapsula.

    # /board — tablero Kanban
    def _board(ctx):
        ctx.respond(ctx.pet._kanban_list())
    router.register("/board", _board, exact=True)

    # /task add|done|del
    def _task(ctx):
        rest = ctx.arg("/task")
        if rest.startswith("add "):
            ctx.respond(ctx.pet._kanban_add(rest[4:].strip()))
        elif rest.startswith("done "):
            ctx.respond(ctx.pet._kanban_move(rest[5:].strip(), "done"))
        elif rest.startswith("del "):
            ctx.respond(ctx.pet._kanban_delete(rest[4:].strip()))
        else:
            ctx.respond("Usa: /task add <texto> | /task done <id> | /task del <id>")
    router.register("/task", _task)

    # /play <query> — Spotify
    def _play(ctx):
        ctx.respond(ctx.pet._spotify_play(ctx.arg("/play")))
    router.register("/play", _play)

    # /git <args> — incluye el caso especial commit "mensaje"
    def _git(ctx):
        args = ctx.arg("/git").split()
        if args and args[0] == "commit" and len(args) >= 2:
            msg = " ".join(args[1:]).strip('"\'')
            ctx.pet._git_cmd(["add", "-A"])
            ctx.respond(ctx.pet._git_cmd(["commit", "-m", msg]))
        else:
            ctx.respond(ctx.pet._git_cmd(args))
    router.register("/git", _git)

    # /skill buscar|search <q>  y  /skill install <src> [confiar]
    def _skill_buscar(ctx):
        q = _arg_for(ctx, "/skill buscar", "/skill search")
        ctx.respond(ctx.pet._search_skills_registry(q))
    router.register("/skill buscar", _skill_buscar)
    router.register("/skill search", _skill_buscar)

    def _skill_install(ctx):
        src = ctx.arg("/skill install")
        force = False
        if src.lower().endswith((" confiar", " --force", " force")):
            force = True
            src = src.rsplit(None, 1)[0].strip()
        ok, msg = ctx.pet._install_skill(src, force=force)
        ctx.respond(msg)
    router.register("/skill install", _skill_install)

    return router
