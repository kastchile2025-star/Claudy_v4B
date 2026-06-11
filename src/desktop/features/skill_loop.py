"""Claudy features.skill_loop — Bucle de aprendizaje cerrado + The Curator.

Estilo Hermes Agent (Nous Research). Cuatro piezas:

  0. ÍNDICE FTS5 (_skills_fts_*): las SKILL.md se indexan en SQLite FTS5
     (~/.claudy/skills_index.db) y el system prompt usa carga search-first:
     catálogo compacto de TODAS + texto completo solo de las relevantes al
     mensaje. Es el ahorro de tokens que reporta Hermes en tareas repetidas.
  1. AUTO-SKILLS (_auto_skill_check): al cerrar una conversación, un evaluador
     en background decide si la sesión contiene un procedimiento multi-paso
     reutilizable y lo destila solo en una SKILL.md (~/.claudy/skills/<slug>/),
     marcada con origin="auto" en su _meta.json.
  2. THE CURATOR (_curator_run / _curator_tick): demonio periódico (24 h) que
     mantiene la biblioteca sana — archiva skills auto-creadas que nunca se
     usaron y fusiona el par de skills más duplicado (máx. 1 fusión por pasada).
     Nunca borra: mueve a ~/.claudy/skills/_archive/.
  3. DESCRIBE-A-SKILL (_create_skill_from_description): genera una SKILL.md
     completa desde una descripción en lenguaje natural ("/skill crear <desc>"),
     sin necesidad de que la conversación haya ocurrido.

Se usa como mixin: ClawdPet hereda de SkillLoopMixin. Depende de helpers de la
clase compuesta: send_quick_message, _skill_slug, _skill_dir, _load_skill_meta,
_save_skill_meta, _installed_skill_slugs, _create_skill_stub,
_show_notification, _debug_log, after.
"""
import datetime
import json
import os
import re
import shutil
import sqlite3
import threading
import time


# Stopwords + muletillas de petición: sin esto, el OR de tokens hace que
# "de"/"la"/"quiero" matcheen TODAS las skills y el ranking pierda sentido.
_FTS_STOPWORDS = frozenset(
    "de del la el los las un una unos unas que con sin para por como este esta "
    "esto ese esa eso mis tus sus les cuando donde quiero dame hazme haz "
    "necesito puedes podrias ayuda ayudame sobre entre hasta desde todo toda "
    "todos todas algo cada vez hoy ahora aqui ahi por favor".split())


def fts_query(text):
    """Texto libre → consulta FTS5 segura: tokens con contenido (sin stopwords)
    citados y unidos con OR."""
    tokens = re.findall(r"[\wáéíóúñü]+", (text or "").lower())
    tokens = [t for t in tokens
              if len(t) >= 3 and t.translate(str.maketrans("áéíóú", "aeiou"))
              not in _FTS_STOPWORDS][:12]
    return " OR ".join(f'"{t}"' for t in tokens)

# Formato canónico de SKILL.md que comparten /aprender, auto-skills y describe.
SKILL_FORMAT = (
    "---\n"
    "name: <slug-kebab-corto>\n"
    "description: <una línea clara: cuándo usar esta skill>\n"
    "---\n\n"
    "# <Título>\n\n"
    "## Cuándo usarla\n"
    "<2-3 líneas: qué situación o pedido la dispara>\n\n"
    "## Pasos\n"
    "1. <paso concreto y accionable>\n"
    "2. <paso concreto>\n"
    "3. <paso concreto>\n\n"
    "## Reglas\n"
    "- <regla aprendida o restricción>\n"
    "- <otra regla>\n\n"
    "## Ejemplo\n"
    "<un caso concreto de uso>"
)


class SkillLoopMixin:

    # ──────────────────────────────────────────────────────────
    # 0) ÍNDICE FTS5 + carga search-first de skills
    # ──────────────────────────────────────────────────────────
    def _skills_root(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", "skills")

    def _skills_index_path(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", "skills_index.db")

    def _skills_scan(self):
        """[(slug, ruta_SKILL.md, mtime)] de las skills instaladas (sin _archive)."""
        root = self._skills_root()
        out = []
        if not os.path.isdir(root):
            return out
        for folder in sorted(os.listdir(root)):
            if folder.startswith("_"):
                continue
            full = os.path.join(root, folder)
            if not os.path.isdir(full):
                continue
            for cand in ("SKILL.md", "skill.md", "Skill.md"):
                p = os.path.join(full, cand)
                if os.path.isfile(p):
                    try:
                        out.append((folder, p, os.path.getmtime(p)))
                    except OSError:
                        pass
                    break
        return out

    def _skills_fts_refresh(self):
        """Reconstruye el índice si algún SKILL.md cambió (firma por mtime).
        Reconstrucción completa: son decenas de archivos chicos, milisegundos.
        Devuelve True si el índice quedó disponible."""
        try:
            entries = self._skills_scan()
            sig = {slug: mtime for slug, _, mtime in entries}
            if (sig == getattr(self, "_skills_fts_sig", None)
                    and getattr(self, "_skills_fts_ok", False)):
                return True
            conn = sqlite3.connect(self._skills_index_path())
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
                    slug, content, tokenize='unicode61 remove_diacritics 2'
                )
            """)
            conn.execute("DELETE FROM skills_fts")
            for slug, path, _ in entries:
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(8000)
                    conn.execute("INSERT INTO skills_fts (slug, content) VALUES (?, ?)",
                                 (slug, content))
                except Exception:
                    continue
            conn.commit()
            conn.close()
            self._skills_fts_sig = sig
            self._skills_fts_ok = True
            return True
        except Exception as e:
            self._skills_fts_ok = False
            try:
                self._debug_log("SKILLS FTS", f"índice no disponible: {e}")
            except Exception:
                pass
            return False

    def _skills_fts_search(self, query, limit=3):
        """Slugs de skills relevantes al texto, rankeadas por bm25.
        Devuelve None si FTS5 no está disponible (≠ [] que es 'sin matches')."""
        if not self._skills_fts_refresh():
            return None
        q = fts_query(query)
        if not q:
            return []
        try:
            conn = sqlite3.connect(self._skills_index_path())
            rows = conn.execute(
                "SELECT slug FROM skills_fts WHERE skills_fts MATCH ? "
                "ORDER BY bm25(skills_fts) LIMIT ?", (q, limit)).fetchall()
            conn.close()
            return [r[0] for r in rows]
        except Exception:
            return None

    def _load_installed_skills(self, prompt=None, max_skills=20, max_chars_per_skill=400):
        """Contexto de skills para el system prompt — search-first (Hermes).

        Con índice FTS5: catálogo compacto (slug + descripción) de TODAS las
        skills + texto completo SOLO de las ≤3 relevantes al mensaje. Antes se
        inyectaban hasta 20 skills × 400 chars en cada prompt.
        Sin FTS5 (o sin prompt): fallback al comportamiento clásico."""
        entries = self._skills_scan()
        if not entries:
            return ""
        relevant = self._skills_fts_search(prompt, limit=3) if prompt else None
        if relevant is None:
            return self._load_skills_legacy(entries, max_skills, max_chars_per_skill)

        catalog = []
        bodies = {}
        for slug, path, _ in entries[:max_skills * 3]:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    body = f.read(4000)
            except Exception:
                continue
            m = re.search(r"^description:\s*(.+)$", body[:500], re.M)
            catalog.append(f"- {slug}: {m.group(1).strip() if m else ''}")
            if slug in relevant:
                if body.startswith("---"):
                    end = body.find("---", 3)
                    if end > 0:
                        body = body[end + 3:].strip()
                bodies[slug] = body[:1600]
        parts = ["[CATÁLOGO DE SKILLS INSTALADAS]"] + catalog
        if bodies:
            parts.append("\n[SKILLS RELEVANTES PARA ESTE MENSAJE — síguelas si aplican]")
            for slug in relevant:
                if slug in bodies:
                    parts.append(f"### {slug}\n{bodies[slug]}")
        parts.append("[Fin skills locales]\n\n")
        return "\n".join(parts)

    def _load_skills_legacy(self, entries, max_skills, max_chars_per_skill):
        """Comportamiento clásico: todas las skills truncadas (sin FTS5)."""
        chunks = []
        for slug, path, _ in entries[:max_skills]:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    body = f.read(max_chars_per_skill * 2)
                if body.startswith("---"):
                    end = body.find("---", 3)
                    if end > 0:
                        body = body[end + 3:].strip()
                chunks.append(f"### {slug}\n{body[:max_chars_per_skill]}")
            except Exception:
                pass
        if not chunks:
            return ""
        return "[SKILLS INSTALADAS LOCALMENTE]\n" + "\n\n".join(chunks) + "\n[Fin skills locales]\n\n"

    # ──────────────────────────────────────────────────────────
    # Helpers compartidos
    # ──────────────────────────────────────────────────────────
    def _skill_catalog_brief(self):
        """Lista 'slug: descripción' de las skills instaladas (para prompts)."""
        lines = []
        for slug in self._installed_skill_slugs():
            desc = ""
            try:
                with open(os.path.join(self._skill_dir(slug), "SKILL.md"), encoding="utf-8") as f:
                    head = f.read(400)
                m = re.search(r"^description:\s*(.+)$", head, re.M)
                desc = m.group(1).strip() if m else ""
            except Exception:
                pass
            lines.append(f"- {slug}: {desc}")
        return "\n".join(lines) or "(ninguna)"

    def _skill_description(self, slug):
        try:
            with open(os.path.join(self._skill_dir(slug), "SKILL.md"), encoding="utf-8") as f:
                head = f.read(500)
            m = re.search(r"^description:\s*(.+)$", head, re.M)
            return (m.group(1).strip() if m else "")
        except Exception:
            return ""

    def _write_skill_md(self, slug, content, origin):
        """Limpia fences, valida frontmatter, guarda SKILL.md y marca el origen.
        Devuelve la ruta o None si el contenido no es una skill válida."""
        content = re.sub(r"^```[a-z]*\n", "", (content or "").strip())
        content = re.sub(r"\n```$", "", content).strip()
        if not content.startswith("---") or len(content) < 60:
            return None
        folder = self._skill_dir(slug)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "SKILL.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        meta = self._load_skill_meta(slug)
        meta["origin"] = origin
        self._save_skill_meta(slug, meta)
        return path

    def _archive_skill(self, slug, reason=""):
        """Mueve una skill a ~/.claudy/skills/_archive/ (el Curator nunca borra)."""
        archive_root = os.path.join(os.path.expanduser("~"), ".claudy", "skills", "_archive")
        os.makedirs(archive_root, exist_ok=True)
        src = self._skill_dir(slug)
        dest = os.path.join(archive_root, slug)
        if os.path.isdir(dest):
            dest = os.path.join(archive_root, f"{slug}-{int(time.time())}")
        shutil.move(src, dest)
        try:
            self._debug_log("CURATOR ARCHIVE", f"{slug}: {reason}")
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────
    # 1) AUTO-SKILLS — bucle de aprendizaje cerrado
    # ──────────────────────────────────────────────────────────
    def _auto_skill_check(self, session_msgs):
        """Evalúa (en background) si la sesión recién cerrada merece volverse skill.

        Exigente a propósito: charla casual o tareas ya cubiertas → no crea nada.
        Cooldown de 30 min entre evaluaciones para no quemar tokens."""
        try:
            now = time.time()
            if now - getattr(self, "_last_auto_skill_eval", 0.0) < 1800:
                return
            texts = [m for m in (session_msgs or [])
                     if isinstance(m, dict) and (m.get("text") or "").strip()]
            if len(texts) < 8:  # mínimo ~4 intercambios reales
                return
            self._last_auto_skill_eval = now

            transcript = "\n".join(
                f"{'Usuario' if m.get('role') in ('user', 'Usuario') else 'Claudy'}: "
                f"{(m.get('text') or '')[:400]}"
                for m in texts
            )[-6000:]

            eval_prompt = (
                "Eres el evaluador del bucle de aprendizaje de un asistente personal. "
                "Analiza esta conversación TERMINADA y decide si contiene UN procedimiento "
                "multi-paso reutilizable que el asistente debería recordar como skill (receta).\n\n"
                f"SKILLS QUE YA EXISTEN (no dupliques ninguna):\n{self._skill_catalog_brief()}\n\n"
                f"CONVERSACIÓN:\n{transcript}\n\n"
                "Responde EXACTAMENTE una de dos cosas:\n"
                "NO\n"
                'o un JSON en una sola línea: {"name": "nombre-corto-kebab", "reason": "por qué vale la pena"}\n'
                "Sé exigente: charla casual, preguntas sueltas, o tareas ya cubiertas por "
                "una skill existente = NO."
            )
            verdict = self.send_quick_message(
                eval_prompt, _skip_skill_action=True, timeout=60, max_tokens=200, tier="fast")
            m = re.search(r"\{.*\}", verdict or "", re.S)
            if not m:
                return
            try:
                data = json.loads(m.group(0))
            except Exception:
                return
            slug = self._skill_slug(data.get("name", ""))
            if not slug or os.path.isfile(os.path.join(self._skill_dir(slug), "SKILL.md")):
                return

            gen_prompt = (
                "Destila esta conversación en un archivo SKILL.md reutilizable para un "
                "asistente personal. El objetivo: que la próxima vez que aparezca una "
                "situación similar, el asistente sepa exactamente qué hacer.\n\n"
                f"Nombre de la skill: {slug}\n"
                f"Por qué vale la pena: {data.get('reason', '')}\n\n"
                f"CONVERSACIÓN:\n{transcript}\n\n"
                f"Responde SOLO el contenido del archivo, sin fences, con este formato exacto:\n\n{SKILL_FORMAT}\n\n"
                f"Usa name: {slug} en el frontmatter. Anonimiza datos personales del ejemplo."
            )
            content = self.send_quick_message(
                gen_prompt, _skip_skill_action=True, timeout=90, max_tokens=1200, tier="fast")
            path = self._write_skill_md(slug, content, origin="auto")
            if not path:
                return
            self._debug_log("AUTO-SKILL CREATED", f"{slug} ({data.get('reason', '')[:80]})")
            try:
                self.after(0, lambda: self._show_notification(
                    "Claudy aprendió",
                    f"Aprendí sola una skill nueva: '{slug}'. Revísala con /skills."))
            except Exception:
                pass
        except Exception as e:
            try:
                self._debug_log("AUTO-SKILL ERROR", str(e))
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────
    # 2) THE CURATOR — mantenimiento periódico de la biblioteca
    # ──────────────────────────────────────────────────────────
    def _curator_tick(self):
        """Lanzado por self.after: corre el Curator en background y se reagenda."""
        try:
            threading.Thread(target=self._curator_run, daemon=True, name="curator").start()
        finally:
            try:
                self.after(24 * 3600 * 1000, self._curator_tick)
            except Exception:
                pass

    def _curator_run(self, manual=False):
        """Audita la biblioteca: archiva auto-skills sin uso y fusiona duplicados.

        Conservador a propósito: solo archiva skills creadas automáticamente
        (las del usuario no se tocan) y fusiona máximo UN par por pasada."""
        if getattr(self, "_curator_running", False):
            return "El Curator ya está trabajando, espera a que termine."
        self._curator_running = True
        actions = []
        try:
            now = datetime.datetime.now()

            # ── Paso 1: archivar auto-skills viejas y sin uso ──
            for slug in list(self._installed_skill_slugs()):
                meta = self._load_skill_meta(slug)
                if meta.get("origin") != "auto":
                    continue
                try:
                    created = datetime.datetime.fromisoformat(str(meta.get("created", "")))
                except Exception:
                    continue
                age_days = (now - created).days
                if age_days >= 30 and int(meta.get("uses", 0)) < 2:
                    try:
                        self._archive_skill(slug, f"auto-creada, {age_days}d, {meta.get('uses', 0)} usos")
                        actions.append(f"archivé '{slug}' (auto-creada, {age_days} días sin uso real)")
                    except Exception:
                        continue

            # ── Paso 2: fusionar el par más duplicado (overlap de descripciones) ──
            slugs = self._installed_skill_slugs()
            best_pair, best_score = None, 0.0
            descs = {s: self._skill_description(s) for s in slugs}

            def _tokens(s, d):
                base = (s.replace("-", " ") + " " + d).lower()
                return set(re.findall(r"[a-záéíóúñ0-9]{4,}", base))

            for i, a in enumerate(slugs):
                ta = _tokens(a, descs[a])
                if not ta:
                    continue
                for b in slugs[i + 1:]:
                    tb = _tokens(b, descs[b])
                    if not tb:
                        continue
                    jaccard = len(ta & tb) / max(1, len(ta | tb))
                    if jaccard > best_score:
                        best_pair, best_score = (a, b), jaccard

            if best_pair and best_score >= 0.6:
                a, b = best_pair
                # Conservar la más usada; la otra se fusiona y archiva
                uses_a = int(self._load_skill_meta(a).get("uses", 0))
                uses_b = int(self._load_skill_meta(b).get("uses", 0))
                keep, drop = (a, b) if uses_a >= uses_b else (b, a)
                try:
                    with open(os.path.join(self._skill_dir(keep), "SKILL.md"), encoding="utf-8") as f:
                        keep_md = f.read()
                    with open(os.path.join(self._skill_dir(drop), "SKILL.md"), encoding="utf-8") as f:
                        drop_md = f.read()
                    merge_prompt = (
                        "Eres el curador de la biblioteca de skills de un asistente. Estas dos "
                        "skills se solapan demasiado; fusiónalas en UNA sola que cubra ambos "
                        "casos sin perder reglas ni pasos importantes.\n\n"
                        f"=== SKILL A CONSERVAR ({keep}) ===\n{keep_md[:2500]}\n\n"
                        f"=== SKILL A ABSORBER ({drop}) ===\n{drop_md[:2500]}\n\n"
                        f"Responde SOLO el archivo SKILL.md fusionado (sin fences), manteniendo "
                        f"'name: {keep}' en el frontmatter y el formato estándar."
                    )
                    merged = self.send_quick_message(
                        merge_prompt, _skip_skill_action=True, timeout=90, max_tokens=1500, tier="fast")
                    if self._write_skill_md(keep, merged, origin=self._load_skill_meta(keep).get("origin", "manual")):
                        self._archive_skill(drop, f"fusionada en '{keep}' (similitud {best_score:.0%})")
                        actions.append(f"fusioné '{drop}' dentro de '{keep}' (se solapaban {best_score:.0%})")
                except Exception as e:
                    self._debug_log("CURATOR MERGE ERROR", str(e))
        finally:
            self._curator_running = False

        if actions:
            self._debug_log("CURATOR", "; ".join(actions))
            if not manual:
                try:
                    self.after(0, lambda: self._show_notification(
                        "Curator de skills", "Mantenimiento: " + "; ".join(actions)))
                except Exception:
                    pass
        if manual:
            return ("🧹 Curator: " + "; ".join(actions)) if actions else \
                "🧹 Curator: biblioteca revisada, todo en orden (nada que archivar ni fusionar)."
        return ""

    # ──────────────────────────────────────────────────────────
    # 3) DESCRIBE-A-SKILL — crear desde lenguaje natural
    # ──────────────────────────────────────────────────────────
    def _create_skill_from_description(self, description):
        """Genera una SKILL.md completa desde una descripción del usuario.

        '/skill crear resumen semanal de facturas en un xlsx' → skill lista.
        Si la descripción es solo un nombre corto, cae al stub clásico."""
        description = (description or "").strip()
        if not description:
            return "Uso: /skill crear <descripción de lo que debe hacer la skill>"
        if len(description.split()) < 3:
            return self._create_skill_stub(description)

        prompt = (
            "Crea una skill (archivo SKILL.md) para un asistente personal de escritorio "
            "a partir de esta descripción del usuario:\n\n"
            f"\"{description}\"\n\n"
            f"Responde SOLO el contenido del archivo, sin fences, con este formato exacto:\n\n{SKILL_FORMAT}\n\n"
            "Los pasos deben ser accionables por el asistente: qué preguntar, qué "
            "comandos o herramientas usar, y en qué formato entregar el resultado."
        )
        try:
            content = self.send_quick_message(
                prompt, _skip_skill_action=True, timeout=90, max_tokens=1200, tier="fast")
        except Exception as e:
            return f"Error generando la skill: {e}"

        m = re.search(r"^name:\s*([a-z0-9\-_]+)", (content or ""), re.M)
        slug = self._skill_slug(m.group(1) if m else "-".join(description.split()[:4]))
        if os.path.isfile(os.path.join(self._skill_dir(slug), "SKILL.md")):
            n = 2
            while os.path.isfile(os.path.join(self._skill_dir(f"{slug}-{n}"), "SKILL.md")):
                n += 1
            slug = f"{slug}-{n}"
            content = re.sub(r"^name:\s*.+$", f"name: {slug}", content, count=1, flags=re.M)

        path = self._write_skill_md(slug, content, origin="described")
        if not path:
            return ("No pude generar una skill válida desde esa descripción. "
                    "Intenta describirla con más detalle (qué hace, cuándo, con qué formato).")

        extra = ""
        if re.search(
            r"\b(cada|todos los|todas las)\s+(lunes|martes|mi[ée]rcoles|jueves|viernes|"
            r"s[áa]bado|domingo|d[íi]a|semana|mes)\b|\ba las \d{1,2}", description, re.I,
        ):
            extra = ("\n⏰ Veo un horario en la descripción: si quieres que se ejecute sola, "
                     f"dime por ejemplo «recuérdame cada viernes a las 9 ejecutar la skill {slug}».")
        return (f"✓ Skill creada desde tu descripción: {slug}\n"
                f"Guardada en: {path}\n"
                f"Se cargará automáticamente en cada conversación.{extra}")
