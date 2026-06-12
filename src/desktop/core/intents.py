"""Claudy core.intents — Registro de intents y despachador (refactor v5).

Dos capas, en orden de prioridad:

1. SLASH_COMMANDS — registro DECLARATIVO de comandos /slash. Cada entrada es
   (prefijos, handler). El orden de la tabla es la prioridad (igual que las
   ~35 ramas if/startswith que reemplaza). Para agregar un comando nuevo:
   una línea en la tabla, nada más.

2. _try_handle_skill_action — heurísticas de lenguaje natural (clima, juegos,
   descargas, skills...) que requieren extracción de entidades; siguen como
   código, pero ahora viven aquí y no en pet.py.

Se usa como mixin: ClawdPet hereda de IntentsMixin.
"""
import os
import re


def _arg(prompt):
    """Argumento tras el comando, con strip (uso más común)."""
    return prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""


def _arg_raw(prompt):
    """Argumento tras el comando SIN strip (rutas con ' | contenido')."""
    return prompt.split(None, 1)[1] if " " in prompt.strip() else ""


# --- Handlers de documentos (delegan en claudy_powers) ---

def _cmd_docx(self, prompt, lower):
    rest = _arg_raw(prompt)
    try:
        import claudy_powers as cp
        path, content = cp.parse_path_content_arg(rest)
        return cp.create_docx(path, content) if path else "Uso: /docx <ruta> | <contenido>"
    except Exception as e:
        return f"Error creando docx: {e}"


def _cmd_xlsx(self, prompt, lower):
    rest = _arg_raw(prompt)
    try:
        import claudy_powers as cp
        path, content = cp.parse_path_content_arg(rest)
        import json
        try:
            data = json.loads(content)
        except Exception:
            data = [line.split(",") for line in content.split("\n") if line.strip()]
        return cp.create_xlsx(path, data) if path else "Uso: /xlsx <ruta> | <contenido CSV/JSON>"
    except Exception as e:
        return f"Error creando xlsx: {e}"


def _cmd_pptx(self, prompt, lower):
    rest = _arg_raw(prompt)
    try:
        import claudy_powers as cp
        path, content = cp.parse_path_content_arg(rest)
        import json
        slides, title, subtitle, theme = None, "", "", "business"
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                slides = parsed.get("slides")
                title = parsed.get("title", "")
                subtitle = parsed.get("subtitle", "")
                theme = parsed.get("theme", "business")
            elif isinstance(parsed, list):
                slides = parsed
        except Exception:
            slides = [{"title": s.strip(), "bullets": ["Detalle"]} for s in content.split("\n") if s.strip()]
        return cp.create_pptx(path, slides, title, subtitle, theme) if path else "Uso: /pptx <ruta> | <contenido JSON>"
    except Exception as e:
        return f"Error creando pptx: {e}"


def _cmd_pdf(self, prompt, lower):
    rest = _arg_raw(prompt)
    try:
        import claudy_powers as cp
        path, content = cp.parse_path_content_arg(rest)
        return cp.create_pdf(path, content) if path else "Uso: /pdf <ruta> | <contenido>"
    except Exception as e:
        return f"Error creando pdf: {e}"


def _cmd_mkdir(self, prompt, lower):
    path = _arg(prompt)
    try:
        import claudy_powers as cp
        return cp.create_folder(path) if path else "Uso: /mkdir <ruta>"
    except Exception as e:
        return f"Error creando carpeta: {e}"


def _cmd_write(self, prompt, lower):
    rest = _arg_raw(prompt)
    try:
        import claudy_powers as cp
        path, content = cp.parse_path_content_arg(rest)
        return cp.write_file(path, content) if path else "Uso: /write <ruta> | <contenido>"
    except Exception as e:
        return f"Error escribiendo archivo: {e}"


def _cmd_append(self, prompt, lower):
    rest = _arg_raw(prompt)
    try:
        import claudy_powers as cp
        path, content = cp.parse_path_content_arg(rest)
        return cp.append_file(path, content) if path else "Uso: /append <ruta> | <contenido>"
    except Exception as e:
        return f"Error agregando contenido: {e}"


def _cmd_replace(self, prompt, lower):
    rest = _arg_raw(prompt)
    parts = [x.strip() for x in rest.split(" | ", 2)]
    if len(parts) < 3:
        return "Uso: /replace <ruta> | <buscar> | <reemplazo>"
    try:
        import claudy_powers as cp
        return cp.replace_in_file(parts[0], parts[1], parts[2])
    except Exception as e:
        return f"Error editando archivo: {e}"


def _cmd_backup(self, prompt, lower):
    parts = prompt.strip().split()
    sub = parts[1].lower() if len(parts) > 1 else ""
    if sub in ("on", "auto", "activar", "enable"):
        return self._set_auto_backup(True)
    if sub in ("off", "desactivar", "disable"):
        return self._set_auto_backup(False)
    if sub in ("status", "estado"):
        return self._backup_status()
    if sub in ("restore", "restaurar"):
        return ("Para restaurar usa: powershell -ExecutionPolicy Bypass "
                "-File scripts\\restore-claudy-full.ps1")
    return self._run_backup_now()


def _cmd_kanban(self, prompt, lower):
    if lower.startswith(("/kanban add ", "/kanban crear ")):
        title = prompt.split(None, 2)[2].strip() if len(prompt.split(None)) > 2 else ""
        return self._kanban_add(title) if title else "Uso: /kanban add <titulo>"
    if lower.startswith(("/kanban move ", "/kanban mover ")):
        parts = prompt.split(None)
        if len(parts) >= 4:
            try:
                return self._kanban_move(int(parts[2]), parts[3])
            except ValueError:
                pass
        return "Uso: /kanban move <id> <backlog|todo|in_progress|done>"
    if lower.startswith(("/kanban delete ", "/kanban borrar ")):
        parts = prompt.split(None)
        try:
            return self._kanban_delete(int(parts[2]))
        except (ValueError, IndexError):
            return "Uso: /kanban delete <id>"
    return self._kanban_list()


def _cmd_webhook(self, prompt, lower):
    if lower.startswith(("/webhook add ", "/webhook crear ")):
        parts = prompt.split(None, 2)
        if len(parts) >= 3:
            words = parts[2].split()
            name = words[0] if words else ""
            url = " ".join(words[1:]) if len(words) > 1 else ""
            return self._webhook_register(name, url) if name and url else "Uso: /webhook add <nombre> <url>"
        return "Uso: /webhook add <nombre> <url>"
    if lower.startswith(("/webhook trigger", "/webhook disparar")):
        return self._webhook_trigger_all()
    return self._webhook_list()


def _cmd_worktree(self, prompt, lower):
    if lower.startswith(("/worktree add ", "/worktree crear ")):
        parts = prompt.split(None)
        name = parts[2] if len(parts) > 2 else ""
        branch = parts[3] if len(parts) > 3 else "main"
        return self._worktree_create(name, branch) if name else "Uso: /worktree add <nombre> [branch]"
    if lower.startswith(("/worktree remove ", "/worktree borrar ")):
        parts = prompt.split(None)
        name = parts[2] if len(parts) > 2 else ""
        return self._worktree_remove(name) if name else "Uso: /worktree remove <nombre>"
    return self._worktree_list()


def _cmd_subagent_result(self, prompt, lower):
    r = self._check_subagent_result()
    return r if r else "No hay resultados de subagente pendientes."


# ============================================================
# REGISTRO: (prefijos, handler). Orden de la tabla = prioridad.
# Los prefijos con espacio final exigen argumento (igual que antes).
# ============================================================
SLASH_COMMANDS = [
    (("/buscar ", "/search "),
     lambda s, p, l: s._web_search_and_answer(_arg(p)) if _arg(p) else "¿Qué quieres que busque?"),
    (("/screenshot", "/captura", "/screen"),
     lambda s, p, l: s._take_screenshot()),
    (("/leer ", "/read ", "/abrir "),
     lambda s, p, l: s._read_local_file(_arg(p)) if _arg(p) else "Qué archivo quieres que lea?"),
    (("/docx ", "/create-docx ", "/crear-docx "), _cmd_docx),
    (("/xlsx ", "/create-xlsx ", "/crear-xlsx ", "/excel "), _cmd_xlsx),
    (("/pptx ", "/create-pptx ", "/crear-pptx ", "/powerpoint "), _cmd_pptx),
    (("/pdf ", "/create-pdf ", "/crear-pdf "), _cmd_pdf),
    (("/mkdir ", "/crear-carpeta "), _cmd_mkdir),
    (("/write ", "/crear-archivo "), _cmd_write),
    (("/append ", "/agregar-archivo "), _cmd_append),
    (("/replace ", "/edit-replace "), _cmd_replace),
    (("/cmd ", "/command ", "/ejecutar "),
     lambda s, p, l: s._execute_command(_arg(p)) if _arg(p) else "Qué comando quieres ejecutar?"),
    (("/permisos", "/guard", "/modo-comandos"),
     lambda s, p, l: s._guard_cmd(_arg(p))),
    (("/vigilar quitar ", "/vigilar borrar ", "/vigilar eliminar "),
     lambda s, p, l: s._watch_remove(p.split()[2] if len(p.split()) > 2 else "")),
    (("/vigilando", "/vigilancias"),
     lambda s, p, l: s._watch_list()),
    (("/vigilar ",),
     lambda s, p, l: s._watch_add(p)),
    (("/vigilar",),
     lambda s, p, l: s._watch_list()),
    (("/router",),
     lambda s, p, l: s._router_cmd(_arg(p))),
    (("/agenda-pantalla", "/agendar-pantalla", "/screen-evento"),
     lambda s, p, l: s._screen_to_calendar(p)),
    (("/navegar", "/browser", "/web "),
     lambda s, p, l: s._browser_cmd(_arg(p))),
    (("/deshacer-archivo", "/restaurar-archivo"),
     lambda s, p, l: __import__("claudy_powers").restore_file_backup(_arg(p))),
    (("/backups-archivos", "/snapshots"),
     lambda s, p, l: __import__("claudy_powers").list_file_backups()),
    (("/canvas",),
     lambda s, p, l: s._canvas_cmd(_arg_raw(p))),
    (("/mcp",),
     lambda s, p, l: s._mcp_cmd(_arg(p))),
    (("/recordar ", "/reminder ", "/alarma "),
     lambda s, p, l: s._set_reminder(_arg(p)) if _arg(p) else "Formato: /recordar 10 minutos comprar leche"),
    (("/noticias", "/news", "/noti"),
     lambda s, p, l: s._get_news()),
    (("/traducir ", "/translate ", "/trad"),
     lambda s, p, l: s._translate_text(_arg(p)) if _arg(p) else "Formato: /traducir hello world a español"),
    (("/calc ", "/calcular ", "/math "),
     lambda s, p, l: s._calculate(_arg(p)) if _arg(p) else "Qué quieres calcular? Ej: /calc 2+2*3"),
    (("/musica ", "/music ", "/media "),
     lambda s, p, l: s._control_music(_arg(p)) if _arg(p) else "Acciones: play, pause, siguiente, anterior"),
    (("/tema", "/theme", "/modo"),
     lambda s, p, l: s._toggle_theme()),
    (("/backup", "/respaldo"), _cmd_backup),
    (("/disco", "/espacio", "/disk", "/space", "/almacenamiento"),
     lambda s, p, l: s._get_disk_space()),
    (("/buscar_archivo", "/find_file", "/buscar archivo"),
     lambda s, p, l: s._search_files(_arg(p)) if _arg(p) else "Qué archivo buscas? Ej: /buscar_archivo reporte.pdf"),
    (("/instalar", "/install"),
     lambda s, p, l: s._install_app(_arg(p)) if _arg(p) else "Qué aplicación quieres instalar? Ej: /instalar winrar"),
    (("/descargar", "/download", "/bajar"),
     lambda s, p, l: s._download_file(_arg(p)) if _arg(p) else "Qué URL quieres descargar? Ej: /descargar https://ejemplo.com/archivo.zip"),
    (("/ejecutar", "/run", "/abrir archivo"),
     lambda s, p, l: s._execute_file(_arg(p)) if _arg(p) else "Que archivo quieres ejecutar? Ej: /ejecutar C:\\Users\\felip\\Downloads\\app.exe"),
    (("/checkpoint", "/guardar_punto"),
     lambda s, p, l: s._create_checkpoint(_arg(p) or "manual")),
    (("/rollback", "/deshacer", "/volver"),
     lambda s, p, l: s._rollback_checkpoint(_arg(p) or None)),
    (("/checkpoints", "/puntos"),
     lambda s, p, l: s._list_checkpoints()),
    (("/recordar ", "/buscar_memoria ", "/memoria "),
     lambda s, p, l: s._search_memory_cmd(_arg(p)) if _arg(p) else "Que quieres buscar en la memoria? Ej: /memoria python"),
    (("/delegar ", "/delegate "),
     lambda s, p, l: s._spawn_subagent(_arg(p)) if _arg(p) else "Que tarea delego? Ej: /delegar analizar el codigo de pet.py"),
    (("/resultado", "/sub_result"), _cmd_subagent_result),
    (("/kanban", "/board"), _cmd_kanban),
    (("/webhook", "/webhooks"), _cmd_webhook),
    (("/worktree", "/worktrees"), _cmd_worktree),
]


class IntentsMixin:
    def _dispatch_slash_command(self, prompt, lower):
        """Recorre SLASH_COMMANDS en orden (la tabla es la prioridad).
        Devuelve (True, resultado) si un comando atendio el prompt."""
        for prefixes, handler in SLASH_COMMANDS:
            if lower.startswith(prefixes):
                try:
                    return True, handler(self, prompt, lower)
                except Exception as e:
                    return True, f"Error ejecutando {prefixes[0].strip()}: {e}"
        return False, None

    def _try_cleanup_and_filesearch_nl(self, prompt, lower):
        """Limpieza del PC y búsqueda de archivos — slash y lenguaje natural.

        Centraliza todo el ruteo de los botones 🧹 y 🔎 del sidebar. Corre antes
        de claudy_powers.detect_intent para que estas frases no caigan en
        find_in/search_app con la query sin limpiar.
        """
        # «/limpiar» analiza y propone; «/limpiar todo|1,3|cancelar» ejecuta.
        if lower in ("/limpiar", "/limpieza", "analiza la limpieza",
                     "analizar limpieza", "limpia mi pc", "limpiar mi pc",
                     "analiza mi pc para limpiar", "propuestas de limpieza",
                     "limpia el pc", "limpiar el pc"):
            return True, self._cleanup_analyze()
        if lower.startswith("/limpiar ") or lower.startswith("/limpieza "):
            return True, self._cleanup_execute(prompt.split(None, 1)[1].strip())

        # Por tamaño: "limpia/borra/busca los archivos de más de 1 GB",
        # "limpiar todos los archivos que sean sobre 500 MB"
        m_big = re.search(
            r"archivos?\b.{0,40}?(?:sobre|m[aá]s\s+de|mayor(?:es)?\s+(?:a|de|que)|"
            r"arriba\s+de|superior(?:es)?\s+a|>)\s*"
            r"(\d+(?:[.,]\d+)?)\s*(tb|teras?|gb|gigas?|mb|megas?|kb)\b", lower)
        if m_big and any(k in lower for k in (
                "limpia", "limpiar", "borra", "borrar", "elimina", "eliminar",
                "busca", "buscar", "encuentra", "muestra", "mostrar",
                "lista", "listar", "revisa")):
            num = float(m_big.group(1).replace(",", "."))
            mult = {"kb": 1024, "mb": 1024 ** 2, "mega": 1024 ** 2,
                    "gb": 1024 ** 3, "giga": 1024 ** 3,
                    "tb": 1024 ** 4, "tera": 1024 ** 4}.get(m_big.group(2)[:4], 1024 ** 3)
            return True, self._cleanup_big_files(int(num * mult))

        # Difusa: "busca todas las alternativas para limpiar el pc",
        # "cómo puedo liberar espacio en el disco"
        if (("limpi" in lower or "liberar espacio" in lower)
                and any(k in lower for k in ("pc", "computador", "notebook", "equipo",
                                             "laptop", "disco", "windows", "espacio"))
                and any(k in lower for k in ("alternativa", "opcion", "opción", "propuesta",
                                             "analiza", "analizar", "busca", "revisa",
                                             "como", "cómo", "puedo", "liberar"))):
            return True, self._cleanup_analyze()

        # Selección natural: "limpia el 1 y el 3", "limpiar 2", "limpia todo" —
        # solo con una propuesta vigente (si no, podría significar otra cosa).
        if getattr(self, "_cleanup_proposals", None):
            m_sel = re.match(
                r"^limpi(?:a|ar)\s+(?:el\s+|los\s+)?(\d+(?:\s*(?:,|y|e)\s*(?:el\s+)?\d+)*)\s*$",
                lower)
            if m_sel:
                sel = re.sub(r"\s*(?:,|y|e)\s*(?:el\s+)?", ",", m_sel.group(1)).replace(" ", "")
                return True, self._cleanup_execute(sel)
            if lower in ("limpia todo", "limpiar todo", "limpia todos", "limpiar todos"):
                return True, self._cleanup_execute("todo")

        # Búsqueda precisa: "busca/encuentra el archivo <query>", quitando
        # muletillas de ubicación ("en el notebook *.iso" → "*.iso").
        m_fs = re.match(
            r"^(?:busca(?:r|me)?|encuentra|encontrar|localiza(?:r)?|ubica(?:r)?)\s+"
            r"(?:el\s+|la\s+|los\s+|las\s+|un\s+|una\s+|todos\s+los\s+)?"
            r"(?:archivos?|ficheros?)\s+(.+)$", lower)
        if m_fs:
            q = m_fs.group(1).strip()
            loc = (r"(?:en|dentro\s+de(?:l)?)\s+(?:el\s+|la\s+|mi\s+|este\s+|esta\s+|todo\s+el\s+)?"
                   r"(?:notebook|pc|computador(?:a)?|equipo|laptop|m[aá]quina|"
                   r"windows|sistema|disco\s+duro|disco)\b\s*")
            q = re.sub(r"^(?:que\s+se\s+llam[ae]\s+|llamad[oa]\s+|de\s+nombre\s+|"
                       r"con\s+(?:el\s+)?nombre\s+)", "", q)
            q = re.sub(rf"^{loc}", "", q)
            q = re.sub(rf"\s+{loc}$", "", q)
            q = q.strip().strip('"\'').strip(".!?,¿¡")
            # Si aún queda "X en Y", Y es una carpeta real → que lo tome find_in
            if q and not re.search(r"\s+en\s+\S", q):
                self._last_file_query = q
                return True, self._search_files(q)

        return False, None

    def _try_handle_skill_action(self, prompt):
        lower = prompt.lower().strip()

        # ===== Confirmación pendiente del guard de comandos («sí» / «no») =====
        # Va primero: si hay un comando esperando OK, este mensaje puede ser
        # la respuesta y no debe caer en ningún otro intent.
        try:
            g_handled, g_result = self._guard_try_confirm(prompt, lower)
            if g_handled:
                return True, g_result
        except Exception:
            pass

        # ===== Screenshot accionable: «agenda lo que está en pantalla» =====
        # Requiere mención explícita de la pantalla, así el NL normal de
        # calendario («agenda reunión mañana a las 10») no se ve afectado.
        try:
            from features.screen_actions import SCREEN_EVENT_RX
            if SCREEN_EVENT_RX.search(prompt):
                return True, self._screen_to_calendar(prompt)
        except Exception:
            pass

        # ===== Browser: «entra a <url> y dime los precios» =====
        # Navegación real con Playwright; el NL exige el patrón entra/navega
        # + URL, así que no choca con el resto.
        try:
            from features.browser import parse_navigate_request
            _nav = parse_navigate_request(prompt)
            if _nav:
                return True, self._browser_navigate_nl(_nav["url"], _nav["question"])
        except Exception:
            pass

        # ===== Notify Me: vigilar páginas/indicadores («avísame cuando baje
        # el precio de <url>», «avísame si el dólar baja de 900»). Va antes
        # del resto: si no, caería en recordatorios o en la búsqueda web de
        # datos actuales. Con hora explícita («en 30 min», «a las 9») es un
        # recordatorio, no una vigilancia.
        try:
            if (not lower.startswith("/")
                    and not re.search(r"\ben\s+\d+\s*(?:minuto|min|hora|seg)", lower)
                    and not re.search(r"\ba\s+las?\s+\d", lower)):
                from features.watcher import parse_watch_request
                if parse_watch_request(prompt):
                    return True, self._watch_add(prompt)
        except Exception:
            pass

        # Clean politeness wrappers so natural language triggers match perfectly
        cleaned_prompt = prompt
        try:
            import claudy_powers as cp
            cleaned_prompt = cp.clean_politeness_prefixes(prompt)
        except Exception:
            pass

        # ===== Marcador directo para analizar un archivo por ruta (lo usa el bot de Telegram) =====
        if prompt.strip().startswith("[CLAUDY_ANALYZE_FILE:") and prompt.strip().endswith("]"):
            try:
                path = prompt.strip()[len("[CLAUDY_ANALYZE_FILE:"):-1].strip().strip('"\'')
                if os.path.exists(path):
                    return True, self._analyze_local_file_sync(path)
                return True, f"No encontré el archivo en {path}."
            except Exception as e:
                return True, f"No pude analizar el archivo: {e}"

        # ===== Actualizar memoria (Claudy + agentes + Obsidian) bajo orden explícita =====
        try:
            mem_hit, mem_fact = self._extract_memory_fact(prompt, lower)
            if mem_hit:
                return True, self._remember_knowledge(mem_fact)
        except Exception:
            pass

        # ===== Limpieza del PC y búsqueda precisa de archivos =====
        # Debe ir ANTES de _try_local_file_action ("busca el archivo X en mi pc"
        # ahí se ANALIZA en vez de ubicarse) y de claudy_powers.detect_intent
        # ("busca el archivo X" caía en search_app/find_in con la query sucia).
        cl_lower = cleaned_prompt.lower().strip()
        nl_handled, nl_result = self._try_cleanup_and_filesearch_nl(cleaned_prompt, cl_lower)
        if nl_handled:
            return True, nl_result

        # ===== Buscar + analizar un archivo LOCAL (debe ir ANTES de crear-documento,
        # porque "analiza el archivo X de la carpeta Y" NO es crear un documento) =====
        try:
            loc_handled, loc_result = self._try_local_file_action(prompt, lower)
            if loc_handled:
                return True, loc_result
        except Exception:
            pass

        # ===== Crear documento .docx/.pdf con contenido generado por LLM =====
        try:
            handled, result = self._try_handle_create_document(cleaned_prompt)
            if handled:
                return True, result
        except Exception:
            pass

        # ===== CLAUDY POWERS (intent detection lenguaje natural) =====
        try:
            import claudy_powers as cp
            intent, arg = cp.detect_intent(prompt)
            if intent:
                # Confirm sensitive actions in the response, then execute async
                return True, cp.execute_intent(intent, arg)
        except Exception:
            pass

        # ===== Comandos /slash — registro declarativo (core/intents.py) =====
        # Antes: ~35 ramas if/startswith aquí. Orden de la tabla = prioridad.
        sc_handled, sc_result = self._dispatch_slash_command(prompt, lower)
        if sc_handled:
            return True, sc_result


        # ---- Natural language routing (no / prefix) ----

        # Weather/Clima: auto-search for weather queries
        weather_kws = ["clima ", "clima de ", "el clima en ", "tiempo en ", "pronóstico ",
                       "pronostico ", "weather ", "temperatura en ", "lluvia en ",
                       "va a llover", "hace frío", "hace calor", "clima para"]
        if any(kw in lower for kw in weather_kws):
            # Extract city name from the prompt
            city = ""
            city_kws = ["clima de ", "clima en ", "el clima en ", "tiempo en ", "pronóstico de ",
                        "pronostico de ", "pronóstico en ", "pronostico en ", "temperatura en ",
                        "lluvia en ", "clima para ", "weather in ", "weather for "]
            for ck in city_kws:
                if ck in lower:
                    city = prompt[lower.index(ck) + len(ck):].strip().strip(".!?")
                    break
            if not city:
                # Try to extract any location-like word after "clima"
                after = prompt[lower.index("clima") + 5:].strip() if "clima" in lower else prompt
                city = after.strip().strip(".!?")

            # Clean trailing time/duration phrases from city name
            trailing_phrases = [
                "para toda la semana", "toda la semana", "para la semana",
                "de esta semana", "esta semana", "la semana",
                "para hoy", "de hoy", "hoy",
                "para mañana", "de mañana", "mañana",
                "para los proximos dias", "para los próximos días",
                "de los proximos dias", "de los próximos días",
                "por favor", "porfavor", "porfa", "please",
                "para el fin de semana", "el fin de semana",
            ]
            city_lower = city.lower()
            for phrase in trailing_phrases:
                if phrase in city_lower:
                    idx = city_lower.index(phrase)
                    city = city[:idx].strip()
                    city_lower = city.lower()

            # Also remove leading filler words
            for art in ["dame ", "dime ", "cual es ", "cuál es ", "como esta ", "cómo está ",
                         "el ", "la ", "los ", "las ", "del ", "de ", "en "]:
                if city.lower().startswith(art):
                    city = city[len(art):]

            city = city.strip().strip(".!?,")

            # Check if city is a reference to current location
            local_kws = ["mi ubicacion", "mi ubicación", "mi ciudad", "aqui", "aquí", "aca", "acá", "donde estoy", "donde vivo", "mi zona"]
            if city.lower() in local_kws:
                city = ""

            return True, self._get_weather(city)

        # "busca en internet" / "busca en la web" — pasan al LLM para síntesis natural
        web_search_kws = ["busca en internet", "buscar en internet", "busca en la web",
                          "buscar en la web", "busca en google", "googleame", "googlea"]
        # "corrobora/verifica/confirma/chequea X en internet" también es búsqueda
        # real: antes caía al LLM directo, que respondía de memoria inventando
        # fuentes. Tolera typos comunes (correborar) y acentos.
        _verify_hit = (
            re.search(r"\b(?:corr?[oe]bor|verif|conf[ií]rm|chequ[eé]|comprueb|comprob)\w*", lower)
            and any(n in lower for n in ("internet", "la web", "google", "en línea",
                                         "en linea", "online")))
        if any(kw in lower for kw in web_search_kws) or _verify_hit:
            query = prompt
            for kw in web_search_kws:
                if kw in lower:
                    query = prompt[lower.index(kw) + len(kw):].strip()
                    break
            # "tengo este dato, ¿puedes corroborarlo en internet?" deja la query
            # vacía o trivial: en ese caso se busca con el MENSAJE completo
            # (la destilación en _web_search_and_answer lo vuelve palabras clave).
            if len(query.split()) < 3:
                query = prompt
            return True, self._web_search_and_answer(query) if query.strip() else "¿Qué quieres que busque?"

        # Play game: "quiero jugar megaman de nes", "jugar super mario snes"
        play_kws = ["quiero jugar ", "jugar a ", "jugar ", "pon el juego ", "abre el juego ", "corre el juego "]
        if any(kw in lower for kw in play_kws):
            full_what = ""
            for kw in play_kws:
                if kw in lower:
                    full_what = prompt[lower.index(kw) + len(kw):].strip().strip('"').strip("'").strip(".!?")
                    break
            if full_what:
                # Try to extract console from "de nes", "en snes", "para gba"
                for c_kw in [" de ", " en ", " para ", " on ", " for "]:
                    if c_kw in full_what.lower():
                        parts = full_what.lower().split(c_kw)
                        game = parts[0].strip()
                        console = parts[1].strip()
                        # Handle trailing phrases like "para toda la semana" or similar junk
                        return True, self._play_game(game, console)
                return True, self._play_game(full_what)

        # Download: detect URLs + download intent
        url_pattern = re.compile(r'https?://[^\s<>"]+')
        urls_found = url_pattern.findall(prompt)
        download_keywords = ["descarga", "descargar", "bajar", "download", "trae este archivo", "consigue este archivo"]
        if urls_found and any(kw in lower for kw in download_keywords):
            return True, self._download_file(urls_found[0])

        # Download by name (no URL): "descarga megaman rom", "baja el emulador de snes"
        download_name_kws = ["descarga ", "descargar ", "bajar ", "bajame ", "bájame ",
                             "download ", "descárgame ", "descargame "]
        if any(kw in lower for kw in download_name_kws) and not urls_found:
            what = ""
            for kw in download_name_kws:
                if kw in lower:
                    what = prompt[lower.index(kw) + len(kw):].strip().strip('"').strip("'").strip(".!?")
                    for art in ["el ", "la ", "los ", "las ", "un ", "una ", "de ", "del "]:
                        if what.lower().startswith(art):
                            what = what[len(art):]
                            break
                    break
            if what:
                self._last_file_query = what
                return True, self._download_by_name(what)

        # File search: detect explicit keywords + file names with extensions + search intent
        # NOTA: NO incluir "donde está" / "donde esta" sin "el archivo" — son demasiado amplios
        # y rompen preguntas como "donde están ubicados ellos?"
        file_search_kws = ["busca el archivo", "buscar archivo", "busca archivo", "encuentra el archivo",
                           "encuentra archivo", "dónde está el archivo", "donde esta el archivo",
                           "dónde está el fichero", "donde esta el fichero",
                           "busca en mi pc", "buscar en mi pc",
                           "buscar en mi computadora", "find file", "buscando archivo",
                           "buscando el archivo", "buscando este archivo", "busca este archivo"]
        has_search_intent = any(kw in lower for kw in file_search_kws)

        # Also detect if prompt contains a file name with extension + search words
        file_pattern = re.search(r'\b\S+\.(dll|exe|pdf|txt|doc|docx|xls|xlsx|ppt|pptx|zip|rar|7z|jpg|jpeg|png|gif|mp3|mp4|avi|mov|csv|json|xml|py|js|ts|html|css|java|cpp|c|h|go|rs|php|rb|swift|kt|sql|md|log|ini|cfg|bat|ps1|msi|iso|torrent)\b', lower)
        search_words = ["busca", "buscar", "buscando", "encuentra", "donde", "dónde", "está", "esta", "quiero", "necesito"]
        has_file_and_intent = file_pattern and any(w in lower for w in search_words)

        if has_search_intent or has_file_and_intent:
            query = ""
            for kw in file_search_kws:
                if kw in lower:
                    query = prompt[lower.index(kw) + len(kw):].strip()
                    break
            if not query and file_pattern:
                query = file_pattern.group(0)
            # Quitar muletillas de ubicación y nombre para quedarnos con la query:
            #   "en el notebook *.iso"     → "*.iso"
            #   "factura.pdf en mi pc"     → "factura.pdf"
            #   "llamado informe.docx"     → "informe.docx"
            if query:
                loc = (r"(?:en|dentro\s+de(?:l)?)\s+(?:el|la|mi|este|esta|todo\s+el)?\s*"
                       r"(?:notebook|pc|computador(?:a)?|equipo|laptop|m[aá]quina|"
                       r"windows|sistema|disco(?:\s+[a-z]:?)?)")
                query = re.sub(r"^(?:que\s+se\s+llam[ae]|llamad[oa]|de\s+nombre|"
                               r"con\s+(?:el\s+)?nombre)\s+", "", query, flags=re.I)
                query = re.sub(rf"^{loc}\s*", "", query, flags=re.I)
                query = re.sub(rf"\s+{loc}\s*$", "", query, flags=re.I)
                query = query.strip().strip('"\'').strip(".!?,")
            if not query and file_pattern:
                query = file_pattern.group(0)
            if query:
                self._last_file_query = query
            return True, self._search_files(query) if query else "Qué archivo buscas?"

        # Execute: "abre", "ejecuta", "corre" + file path
        exec_kws = ["abre el archivo", "abrir archivo", "ejecuta", "ejecutar", "corre el archivo",
                     "run file", "abre este archivo"]
        if any(kw in lower for kw in exec_kws):
            for kw in exec_kws:
                if kw in lower:
                    path = prompt[lower.index(kw) + len(kw):].strip().strip('"').strip("'")
                    break
            # If path looks like a file path (has extension or starts with drive letter)
            if path and (os.path.splitext(path)[1] or path[1:3] == ":\\"):
                return True, self._execute_file(path)

        # Install app: "instala winrar", "quiero instalar vlc", etc.
        install_kws = ["instala ", "instalar ", "baja e instala ", "quiero instalar ",
                       "necesito instalar ", "me puedes instalar ", "podrias instalar ",
                       "podrías instalar ", "consígueme e instala ", "bájame e instala ",
                       "puedes instalar "]
        if any(kw in lower for kw in install_kws):
            app_name = ""
            for kw in install_kws:
                if kw in lower:
                    app_name = prompt[lower.index(kw) + len(kw):].strip().strip('"').strip("'").strip(".!?")
                    # Strip leading articles/prepositions
                    for art in ["el ", "la ", "los ", "las ", "un ", "una ", "de ", "del "]:
                        if app_name.lower().startswith(art):
                            app_name = app_name[len(art):]
                            break
                    break
            if app_name:
                return True, self._install_app(app_name)

        # Existing skill handlers
        kw_find = ["busca skill", "buscar skill", "busca skills", "buscar skills",
                    "busca una skill", "buscar una skill", "find skill", "instalar skill",
                    "skill para", "skill de"]
        if any(kw in lower for kw in kw_find):
            query = prompt
            for kw in ["skill para", "skill de", "skill sobre", "buscar skills", "busca skills",
                        "buscar skill", "busca skill", "buscar una skill", "busca una skill", "find skill"]:
                if kw in lower:
                    query = prompt[lower.index(kw) + len(kw):].strip()
                    break
            return True, self._execute_find_skills(query or "general")
        kw_pdf = ["crea un pdf", "crear un pdf", "crea pdf", "crear pdf",
                   "genera pdf", "generar pdf", "haz un pdf", "hacer un pdf"]
        if any(kw in lower for kw in kw_pdf):
            content = prompt
            for kw in kw_pdf:
                if kw in lower:
                    content = prompt[lower.index(kw) + len(kw):].strip()
                    break
            title = content.split("\n")[0].strip()[:80] or "Documento Claudy"
            return True, self._create_pdf_simple(title, content)
        kw_analyze = ["analiza", "leer", "extraer texto", "abrir", "lee el"]
        if any(kw in lower for kw in kw_analyze) and ".pdf" in lower:
            paths = re.findall(r'[A-Z]:[\\\/][^\s"\'<>]+\.pdf', prompt)
            if not paths:
                paths = re.findall(r'["\']?([^\s"\'<>]+\.pdf)["\']?', prompt, re.IGNORECASE)
            if paths:
                return True, self._analyze_pdf_text(paths[0])
            return True, "No encuentro la ruta del PDF. Dame la ruta completa."
        kw_obsidian = ["crea una nota", "crear una nota", "crea nota", "crear nota",
                        "guarda en obsidian", "guardar en obsidian", "nota en obsidian",
                        "nueva nota", "crear nota en"]
        if any(kw in lower for kw in kw_obsidian):
            content = prompt
            for kw in kw_obsidian:
                if kw in lower:
                    content = prompt[lower.index(kw) + len(kw):].strip()
                    break
            title = content.split("\n")[0].strip()[:80] or f"Nota_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            return True, self._create_obsidian_note(title, content)
        kw_obs_search = ["busca en obsidian", "buscar en obsidian", "buscar nota", "busca nota",
                          "mis notas", "notas de"]
        if any(kw in lower for kw in kw_obs_search):
            query = prompt
            for kw in kw_obs_search:
                if kw in lower:
                    query = prompt[lower.index(kw) + len(kw):].strip()
                    break
            return True, self._search_obsidian_notes(query or "")

        # ==============================================================
        # NEW SYSTEM COMMANDS
        # ==============================================================

        # PROCESOS: "dame los procesos", "que esta corriendo", "/procesos"
        procesos_kws = ["/procesos", "procesos", "que esta corriendo", "qué está corriendo",
                        "tareas activas", "procesos activos", "listame los procesos",
                        "aplicaciones abiertas", "programas abiertos", "que programas",
                        "dame los procesos", "muestrame los procesos", "ver procesos"]
        if any(kw in lower for kw in procesos_kws):
            return True, self._list_processes()

        # MATAR proceso: "mata el proceso 1234", "/matar 1234", "/kill 1234", "termina el proceso 1234"
        matar_match = re.search(r'(?:/matar\s+|/kill\s+|mata\s+(?:el\s+)?proceso\s+|termina\s+(?:el\s+)?proceso\s+|cerrar\s+proceso\s+|matar\s+proceso\s+)(\d+)', lower)
        if matar_match:
            return True, self._kill_process(int(matar_match.group(1)))

        # EXPLORAR: "explora descargas", "/explorar C:\Users", "que hay en", "listame archivos"
        explorar_kws = ["/explorar ", "/explore ", "explora ", "explorar ", "explorando ",
                        "que hay en ", "qué hay en ", "listame archivos en ", "lista archivos en ",
                        "dime que hay en ", "muestra archivos en ", "ver archivos en "]
        if any(kw in lower for kw in explorar_kws):
            ruta = ""
            for kw in explorar_kws:
                if kw in lower:
                    ruta = prompt[lower.index(kw) + len(kw):].strip().strip('"').strip("'")
                    break
            if not ruta or ruta.lower() in ["escritorio", "desktop"]:
                ruta = os.path.expanduser("~/Desktop")
            elif ruta.lower() in ["descargas", "downloads"]:
                ruta = os.path.expanduser("~/Downloads")
            elif ruta.lower() in ["documentos", "documents", "documentos"]:
                ruta = os.path.expanduser("~/Documents")
            return True, self._explore_dir(ruta)

        # APPS instaladas: "dame las apps instaladas", "/apps", "programas instalados"
        apps_kws = ["/apps", "aplicaciones instaladas", "apps instaladas", "programas instalados",
                     "que aplicaciones tengo", "que programas tengo", "dame las apps",
                     "dame los programas", "lista de programas", "lista de aplicaciones",
                     "aplicaciones que tengo", "programas que tengo", "software instalado"]
        if any(kw in lower for kw in apps_kws):
            return True, self._list_installed_apps()

        # WIFI: "ver wifi", "/wifi", "red wifi", "contraseña wifi"
        wifi_kws = ["/wifi", "ver wifi", "red wifi", "mi wifi", "conexion wifi", "conexión wifi",
                     "red inalambrica", "red inalámbrica", "redes disponibles",
                     "dame el wifi", "estado del wifi", "info wifi", "informacion wifi"]
        if any(kw in lower for kw in wifi_kws):
            return True, self._wifi_info()

        # BLUETOOTH: "ver bluetooth", "/bluetooth", "dispositivos bluetooth"
        bt_kws = ["/bluetooth", "ver bluetooth", "dispositivos bluetooth",
                   "dispositivos conectados bluetooth", "bluetooth dispositivos",
                   "dame el bluetooth", "que bluetooth tengo"]
        if any(kw in lower for kw in bt_kws):
            return True, self._bluetooth_info()

        # APAGAR/REINICIAR: "apaga en 10 minutos", "/apagar 10", "reinicia en 5"
        apagar_match = re.search(r'(?:apaga\s+en\s+|apagar\s+en\s+|/apagar\s+|reinicia\s+en\s+|/reiniciar\s+|reiniciar\s+en\s+|/restart\s+)(\d+)', lower)
        if apagar_match:
            minutos = int(apagar_match.group(1))
            is_reboot = lower.startswith("reinicia") or lower.startswith("/reiniciar") or lower.startswith("/restart")
            return True, self._shutdown_timer(minutos, reboot=is_reboot)

        # CANCELAR APAGADO: "cancela el apagado", "/noapagar"
        cancel_kws = ["cancela el apagado", "cancelar apagado", "cancela apagado",
                       "no apagues", "no apagar", "/noapagar", "detén el apagado", "deten el apagado"]
        if any(kw in lower for kw in cancel_kws):
            return True, self._cancel_shutdown()

        # NOTAS: "toma nota", "/notas", "apunta", "guarda esto", "nota rapida"
        notas_kws = ["/notas", "toma nota", "tomar nota", "apunta", "nota rápida", "nota rapida",
                     "guarda esto", "guardar esto", "anota esto", "anotar esto",
                     "quiero tomar una nota", "dame mis notas", "muestrame las notas",
                     "notas guardadas", "lee mis notas"]
        if any(kw in lower for kw in notas_kws):
            # Check if it's a read request
            read_notas = ["dame mis notas", "muestrame las notas", "notas guardadas",
                          "lee mis notas", "ver notas", "que notas tengo"]
            if any(kw in lower for kw in read_notas):
                return True, self._read_notes()
            # Extract note content
            for kw in notas_kws:
                if kw in lower and kw not in read_notas:
                    content = prompt[lower.index(kw) + len(kw):].strip()
                    if content:
                        return True, self._save_note(content)
                    break
            return True, self._save_note("")

        # CLIPBOARD: "copia al portapapeles", "/clipboard", "pegar", "copiar"
        clipboard_kws = ["/clipboard", "/portapapeles", "/copiar", "/pegar",
                         "copia al portapapeles", "copiar al portapapeles", "pegar del portapapeles",
                         "que hay en el portapapeles", "portapapeles", "lee el portapapeles",
                         "ver portapapeles", "muestra el portapapeles"]
        if any(kw in lower for kw in clipboard_kws):
            # Check if it's a write action (copiar algo específico)
            if any(kw in lower for kw in ["copia ", "copiar "]):
                text = prompt
                for kw in ["copia al portapapeles ", "copiar al portapapeles ", "copia ", "copiar "]:
                    if kw in lower:
                        text = prompt[lower.index(kw) + len(kw):].strip()
                        break
                return True, self._clipboard_copy(text) if text else self._clipboard_read()
            return True, self._clipboard_read()

        # EN VIVO (always on top): "ponte al frente", "/envivo", "modo siempre visible"
        envivo_kws = ["/envivo", "siempre visible", "ponte al frente", "ponte siempre visible",
                       "modo visible", "quedate al frente", "quédate al frente", "mantente visible",
                       "siempre al frente", "al frente"]
        if any(kw in lower for kw in envivo_kws):
            # Check if it's a disable request
            if any(kw in lower for kw in ["quita", "quitar", "desactiva", "no quiero", "sal del modo", "ya"]):
                return True, self._toggle_always_on_top(False)
            return True, self._toggle_always_on_top(True)

        # COMANDOS/AYUDA: "que comandos tienes", "/atajos", "/ayuda", "/comandos"
        help_kws = ["/atajos", "/ayuda", "/comandos", "/help", "/commands",
                     "que comandos tienes", "qué comandos tienes", "que puedes hacer",
                     "qué puedes hacer", "lista de comandos", "dame los comandos",
                     "comandos disponibles", "funciones", "que sabes hacer"]
        if any(kw in lower for kw in help_kws):
            return True, self._show_help()

        # VOZ: "usar voz", "/voz", "input por voz", "dictado", "escucha"
        voz_kws = ["/voz", "usar voz", "input por voz", "dictado", "hablar",
                    "reconocimiento de voz", "voz a texto", "escucha", "/escucha"]
        if any(kw in lower for kw in voz_kws):
            if lower.strip() in ("/voz stop", "deja de escuchar", "silencio", "dejar de escuchar", "para de escuchar"):
                return True, self._stop_voice_listen()
            return True, self._start_voice_listen()

        # TELEGRAM TOKEN: "/telegram-token <TOKEN>" — guarda el token y arranca el bot
        if lower.startswith("/telegram-token ") or lower.startswith("/telegram_token "):
            token = prompt.split(None, 1)[1].strip().strip('"\'')
            return True, self._set_telegram_token(token) if token else (
                "Uso: /telegram-token <TOKEN>\nPide el token a @BotFather en Telegram.")

        # TELEGRAM STATUS: "/telegram-status" — ver estado (token / usuarios / bot vivo)
        if lower.strip() in ("/telegram-status", "/telegram_status", "telegram status", "estado telegram"):
            return True, self._telegram_status()

        # VINCULAR Telegram: "/vincular <uid>"
        if lower.startswith("/vincular ") or lower.startswith("vincular "):
            uid = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._vincular_telegram_user(uid) if uid else "Uso: /vincular <ID_de_Telegram>"

        # SKILLS: listar / recargar
        if lower.strip() in ("/skills", "/skill list", "skills cargadas", "que skills tienes"):
            return True, self._list_dynamic_skills()
        if lower.startswith("/skill crear ") or lower.startswith("crear skill "):
            parts = prompt.split(None, 2)
            desc = parts[2].strip() if len(parts) > 2 else ""
            # Describe-a-skill: si trae una descripción genera la skill completa
            # con el LLM; si es solo un nombre corto, cae al stub clásico.
            return True, (self._create_skill_from_description(desc)
                          if desc else "Uso: /skill crear <descripción de lo que debe hacer>")

        # SKILLS: mantenimiento manual de la biblioteca (The Curator)
        if lower.strip() in ("/skill curar", "/skills curar", "/curator", "curar skills"):
            return True, self._curator_run(manual=True)

        # SKILLS: aprender de la conversación actual (estilo Hermes Curator)
        if lower.startswith("/aprender ") or lower.startswith("/learn "):
            parts = prompt.split(None, 1)
            name = parts[1].strip() if len(parts) > 1 else ""
            return True, self._learn_skill_from_conversation(name) if name else "Uso: /aprender <nombre-de-la-skill>"

        # SKILLS: estadísticas de uso / aprendizaje
        if lower.strip() in ("/skill stats", "/skills stats", "/skill estado", "estado de skills"):
            return True, self._skill_stats()

        # SKILLS: refinar/mejorar una skill existente (la otra mitad del bucle Hermes)
        if (lower.startswith("/skill mejorar ") or lower.startswith("/skill refinar ")
                or lower.startswith("/refinar ") or lower.startswith("/mejorar-skill ")):
            parts = prompt.split(None, 2) if lower.startswith("/skill") else prompt.split(None, 1)
            name = (parts[2] if lower.startswith("/skill") and len(parts) > 2
                    else parts[1] if len(parts) > 1 else "").strip()
            return True, self._refine_skill(name) if name else "Uso: /skill mejorar <nombre>"

        refine_match = re.search(
            r'(?:mejora|refina|actualiza)\s+(?:la\s+)?skill\s+([^\.\?!,]+)', lower, re.IGNORECASE)
        if refine_match:
            return True, self._refine_skill(refine_match.group(1).strip())

        # Describe-a-skill en lenguaje natural: "crea una skill que <haga algo>"
        # (descripción → SKILL.md completa, sin depender de la conversación).
        create_match = re.search(
            r'(?:crea|crear|hazme|haz|genera)\s+(?:una\s+)?skill\s+que\s+(.+)',
            prompt, re.IGNORECASE | re.DOTALL)
        if create_match:
            return True, self._create_skill_from_description("que " + create_match.group(1).strip())

        # Auto-detección: "guarda esto como skill X", "aprende esto como X", "memoriza esto como X"
        learn_match = re.search(
            r'(?:guarda esto como|aprende esto como|aprende a|memoriza esto como|crea (?:una )?skill (?:de|para))\s+([^\.\?!,]+)',
            lower, re.IGNORECASE
        )
        if learn_match:
            name = learn_match.group(1).strip()
            return True, self._learn_skill_from_conversation(name)

        # SKILLS: eliminar
        if lower.startswith("/skill eliminar ") or lower.startswith("/skill delete ") or lower.startswith("eliminar skill "):
            parts = prompt.split(None, 2)
            name = parts[2].strip() if len(parts) > 2 else ""
            return True, self._delete_skill(name) if name else "Uso: /skill eliminar <nombre>"

        # ===== DATO ACTUAL → BÚSQUEDA WEB AUTOMÁTICA (anti-alucinación) =====
        # El system prompt pide "dato actual → busca primero", pero eso depende
        # de que el modelo obedezca; cuando no busca, responde de memoria con
        # datos creíbles y FALSOS (bug del horario del mundial 2026). Esto lo
        # vuelve determinístico: horarios, precios, resultados, noticias y
        # versiones SIEMPRE pasan por internet, con o sin Deep Research activo.
        # Va antes del bloque cron para que "a qué hora juega X" no caiga ahí.
        _personal_ctx = re.search(
            r"\b(?:mi|mis|nuestr[oa]s?)\b|\barchivo|\bcarpeta|\btest|\bc[oó]digo|"
            r"\bscript|\bproyecto|\bqcore|\bsmartstudent|\broadix|\bluxium|\bclaudy|"
            # frases de recordatorio/cron: deben llegar al scheduler, no a la web
            r"\bav[ií]same\b|\brecu[eé]rdame\b|\balarma\b|\brecordatorio\b|"
            r"\bagend|\bprogr[aá]mame\b|\bcada\s+\d|\bcada\s+(?:hora|d[ií]a|semana)", lower)
        _current_data = re.search(
            r"\ba\s+qu[eé]\s+hora\b|\bhorarios?\b|"
            r"\bcu[aá]ndo\s+(?:es|ser[aá]|empieza|comienza|inicia|parte|juega|sale|estrena|abre|cierra)\b|"
            r"\bprecio\s+del?\b|\bcotizaci[oó]n\b|\bcu[aá]nto\s+(?:vale|cuesta|est[aá])\b|"
            r"\bvalor\s+del?\s+(?:d[oó]lar|euro|uf|utm|bitcoin)\b|\bd[oó]lar\s+hoy\b|"
            r"\bresultado\s+del?\s+partido\b|\bmarcador\b|\bqui[eé]n\s+(?:gan[oó]|va\s+ganando)\b|"
            r"\bnoticias?\b|\b[uú]ltima\s+versi[oó]n\b|\bversi[oó]n\s+m[aá]s\s+reciente\b", lower)
        if _current_data and not _personal_ctx:
            return True, self._web_search_and_answer(prompt)

        # CRON: programar / listar / eliminar tareas
        if lower.strip() in ("/cron list", "/cron listar", "cron list", "tareas programadas", "que tareas tienes"):
            return True, self._list_cron_jobs()

        # Gestión avanzada: editar, pausar/activar y crear tareas semanales.
        # Va antes del parser NL para que "los martes a las 9 ..." no se trate como diario.
        cron_mgmt = self._manage_cron_command(prompt)
        if cron_mgmt is not None:
            return True, cron_mgmt

        cron_expr = self._generate_cron_expression(prompt)
        if cron_expr:
            return True, cron_expr

        # CRON natural language: "recuerdame cada X" / "avisame a las HH" / etc.
        nl = self._parse_cron_nl(prompt)
        if nl:
            kind, params, msg = nl
            if kind == "interval":
                return True, self._add_cron_interval(params, msg)
            if kind == "daily":
                h, m = params
                return True, self._add_cron_daily(h, m, msg)

        cron_match = re.match(r'(?:/cron\s+cada\s+(\d+)\s+(min|minutos|minuto|h|horas|hora)\s+)(.+)', lower)
        if cron_match:
            n = int(cron_match.group(1))
            unit = cron_match.group(2)
            msg = cron_match.group(3).strip()
            interval_min = n if unit.startswith("min") else n * 60
            return True, self._add_cron_interval(interval_min, msg)

        cron_time_match = re.match(r'(?:/cron\s+a\s+las?\s+(\d{1,2}):?(\d{2})?\s+)(.+)', lower)
        if cron_time_match:
            h = int(cron_time_match.group(1))
            m = int(cron_time_match.group(2) or 0)
            msg = cron_time_match.group(3).strip()
            return True, self._add_cron_daily(h, m, msg)

        cron_del_match = re.match(r'(?:/cron\s+delete\s+(\d+)|/cron\s+eliminar\s+(\d+)|eliminar\s+tarea\s+(\d+))', lower)
        if cron_del_match:
            idx = int(cron_del_match.group(1) or cron_del_match.group(2) or cron_del_match.group(3)) - 1
            return True, self._delete_cron_job(idx)

        # AGENDA: crear reunión en Google Calendar
        if lower.startswith("/agendar") or re.search(r'\b(agenda|agendar|agéndame|agendame)\b.*\b(reuni[oó]n|meeting|cita|llamada|evento)\b', lower):
            return True, self._handle_agendar(prompt)

        return False, ""

