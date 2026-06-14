"""Claudy core.memory — Memoria infinita de Claudy (extraído de pet.py, refactor v5).

Capas de memoria (NINGUNA se borra jamás — contrato de memoria infinita):
  - memory          : mensajes recientes (SQLite, memory.db en Google Drive QCORE
                      o ~/.claudy como fallback)
  - memory_archive  : mensajes antiguos archivados (nunca se eliminan)
  - memory_summaries: resúmenes comprimidos de rangos antiguos
  - checkpoints     : puntos de restauración de la conversación
  - Vault Obsidian  : espejo en markdown (QCORE-ECOSYSTEM/MEMORIAS/VAULT)

Se usa como mixin: ClawdPet hereda de MemoryMixin. Los métodos acceden a
`self.load_claudy_config()` y `self.send_quick_message()` definidos en otras
partes de la clase compuesta.
"""
import datetime
import json
import os
import re
import sqlite3
import time

try:
    from core.logging_setup import warn as _log_warn
except Exception:  # uso standalone en tests sin el paquete core en el path
    def _log_warn(component, message, exc=None):
        pass

MEMORY_MAX_MESSAGES = 200
MEMORY_CONTEXT_MESSAGES = 20
MEMORY_CONTEXT_CHARS = 6000

# A5 — Recuperación search-first por capas (estilo Hermes). El orden de escalada
# es: buffer inmediato → ventana deslizante → FTS5 profundo (+ vault). Solo se
# escala a la capa siguiente si la actual no cubre las palabras clave del prompt.
# Esto reduce ruido contextual y tokens: una pregunta cuyo tema ya está en los
# mensajes recientes NO dispara la búsqueda profunda en el archivo ni en el vault.
MEMORY_BUFFER_MESSAGES = 6        # Capa 1: últimos intercambios (siempre presentes)
MEMORY_WINDOW_MESSAGES = 40       # Capa 2: ventana deslizante para cubrir el tema
MEMORY_DEEP_MIN_KEYWORD = 4       # Long. mínima de palabra clave para considerar "cubierta"


class MemoryMixin:
    def _memory_db_path(self):
        drive_dir = r"G:\Mi unidad\QCORE-ECOSYSTEM\MEMORIAS\AGENTES-MEMORY\claudy_local"
        if os.path.isdir(drive_dir):
            return os.path.join(drive_dir, "memory.db")
        return os.path.join(os.path.expanduser("~"), ".claudy", "memory.db")

    def _memory_jsonl_path(self):
        drive_dir = r"G:\Mi unidad\QCORE-ECOSYSTEM\MEMORIAS\AGENTES-MEMORY\claudy_local"
        if os.path.isdir(drive_dir):
            return os.path.join(drive_dir, "memory.jsonl")
        return os.path.join(os.path.expanduser("~"), ".claudy", "memory.jsonl")

    def _init_memory_db(self):
        """Initialize SQLite database and migrate existing JSONL data."""
        db_path = self._memory_db_path()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                memory_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (memory_id) REFERENCES memory(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_role ON memory(role)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_created ON memory(created_at)")
        conn.commit()
        conn.close()
        self._migrate_jsonl_to_sqlite()
        self._init_memory_fts()

    # ------------------------------------------------------------------
    # FTS5 — búsqueda de texto completo sobre TODA la historia
    # (memoria caliente + archivo). El índice retiene lo archivado, así el
    # recall sigue siendo infinito aunque la tabla memory se compacte.
    # ------------------------------------------------------------------
    def _init_memory_fts(self):
        """Crea el índice FTS5 y lo rellena con lo que falte (memoria + archivo)."""
        db_path = self._memory_db_path()
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    role, text, created_at, tokenize='unicode61 remove_diacritics 2'
                )
            """)
            n_fts = conn.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0]
            n_mem = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
            n_arc = 0
            try:
                n_arc = conn.execute("SELECT COUNT(*) FROM memory_archive").fetchone()[0]
            except sqlite3.OperationalError:
                pass
            if n_fts < n_mem + n_arc:
                # Backfill completo (idempotente: se reconstruye desde cero)
                conn.execute("DELETE FROM memory_fts")
                conn.execute(
                    "INSERT INTO memory_fts (role, text, created_at) "
                    "SELECT role, text, created_at FROM memory"
                )
                try:
                    conn.execute(
                        "INSERT INTO memory_fts (role, text, created_at) "
                        "SELECT role, text, created_at FROM memory_archive"
                    )
                except sqlite3.OperationalError:
                    pass
            conn.commit()
            conn.close()
            self._memory_fts_ok = True
        except Exception as e:
            # SQLite sin FTS5: la búsqueda cae al LIKE clásico
            self._memory_fts_ok = False
            print(f"[memoria] FTS5 no disponible, uso LIKE: {e}")

    @staticmethod
    def _fts_query(query):
        """Convierte texto libre en una consulta FTS5 segura: tokens citados
        unidos con OR (evita errores de sintaxis con caracteres especiales)."""
        tokens = re.findall(r"[\wáéíóúñü]+", (query or "").lower())
        tokens = [t for t in tokens if len(t) >= 2][:12]
        if not tokens:
            return ""
        return " OR ".join(f'"{t}"' for t in tokens)

    def _migrate_jsonl_to_sqlite(self):
        """One-time migration from memory.jsonl to SQLite."""
        jl_path = self._memory_jsonl_path()
        if not os.path.exists(jl_path):
            return
        db_path = self._memory_db_path()
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
        if count > 0:
            conn.close()
            return  # Already has data, skip migration
        try:
            with open(jl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if isinstance(msg, dict) and "role" in msg and "text" in msg:
                            conn.execute(
                                "INSERT INTO memory (role, text, created_at) VALUES (?, ?, ?)",
                                (msg["role"], msg["text"], msg.get("time", datetime.datetime.now().isoformat())),
                            )
                    except json.JSONDecodeError:
                        continue
            conn.commit()
            # Rename old file as backup
            backup = jl_path + ".bak"
            os.rename(jl_path, backup)
        except Exception:
            pass
        finally:
            conn.close()

    def _tidy_history_text(self, role, text):
        """Texto a mostrar en el panel de Historial.
        Devuelve None si el mensaje no debe mostrarse (ruido interno de máquina).
        Compacta volcados largos (análisis, JSON crudo) a una etiqueta legible.
        No modifica la base de datos: solo cambia la presentación."""
        t = (text or "").strip()
        if not t:
            return None
        low = t.lower()

        # Análisis de carpeta/archivo: mostrar resumen compacto, no el volcado entero.
        m = re.match(r"\[an[aá]lisis de (carpeta|archivo):\s*(.+?)\]", t, re.I)
        if m:
            kind = m.group(1).lower()
            target = m.group(2).strip()
            base = target.replace("\\", "/").rstrip("/").split("/")[-1] or target
            icon = "📁" if kind == "carpeta" else "📄"
            return f"{icon} Análisis de {kind}: {base}"

        # Resultado de creación de archivo ("Archivo creado: C:\...\X.docx"):
        # mostrar solo la línea con la ruta, sin el volcado de detalles.
        if low.startswith("archivo creado:"):
            first = t.splitlines()[0].strip()
            return f"📄 {first}"

        # Informes completos (Markdown largo con título y secciones): el panel
        # debe mostrar una etiqueta con el tema, no el documento entero.
        if len(t) > 600 and (t.lstrip().startswith("# ") or t.count("## ") >= 2):
            m_t = re.search(r"^#\s+(.+)$", t, re.M)
            title = m_t.group(1).strip() if m_t else t.strip().splitlines()[0][:70]
            return f"📄 Informe generado: {title} (guardado como archivo)"

        # Prompts internos de formato / instrucciones de máquina: no mostrar.
        noise = (
            "body_html", "solo el json", "sólo el json",
            "devuelve unicamente un objeto json", "devuelve únicamente un objeto json",
            "solo como referencia de formato", "el body_html debe usar",
            "no incluyas comentarios ni explicaciones",
        )
        if any(n in low for n in noise):
            return None

        # JSON crudo (borrador estructurado, etc.): etiqueta compacta.
        if t[:1] in "{[" and t[-1:] in "}]":
            try:
                data = json.loads(t)
                subj = ""
                if isinstance(data, dict):
                    subj = (data.get("subject") or data.get("asunto") or "").strip()
                return f"📧 Borrador estructurado{(': ' + subj) if subj else ''}"
            except Exception:
                pass

        return t

    def _load_memory(self):
        """Load all messages from SQLite."""
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return []
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, text, created_at as time FROM memory ORDER BY id ASC"
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _search_memory(self, query, limit=10):
        """Busca en TODA la historia (memoria + archivo) con FTS5 rankeado por
        relevancia (bm25). Fallback a LIKE sobre la memoria caliente."""
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return []
        fts_q = self._fts_query(query)
        if fts_q and getattr(self, "_memory_fts_ok", True):
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT role, text, created_at as time FROM memory_fts "
                    "WHERE memory_fts MATCH ? ORDER BY bm25(memory_fts) LIMIT ?",
                    (fts_q, limit),
                ).fetchall()
                conn.close()
                if rows:
                    return [dict(r) for r in rows]
            except Exception:
                pass
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, text, created_at as time FROM memory WHERE text LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _load_recent_memory(self, n=50):
        """Últimos n mensajes vía SQL (no carga la tabla completa)."""
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return []
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, text, created_at as time FROM "
                "(SELECT id, role, text, created_at FROM memory ORDER BY id DESC LIMIT ?) "
                "ORDER BY id ASC",
                (n,),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _get_last_chat_preview(self, n=4, max_len=400):
        """Return a formatted string with the last n messages for the chat preview.

        Uses [[USER]] / [[CLAUDY]] markers so _set_response_text can render
        each message as a styled bubble with role-specific colors.
        """
        recent = self._load_recent_memory(n)
        if not recent:
            return ""
        lines = []
        for msg in recent:
            role = msg.get("role", "")
            text = (msg.get("text", "") or "").strip()
            if not text:
                continue
            tag = "[[USER]]" if role == "Usuario" else "[[CLAUDY]]"
            if len(text) > max_len:
                text = text[:max_len].rstrip() + "..."
            lines.append(f"{tag}{text}")
        return "\n".join(lines)

    def _save_memory_sqlite(self, role, text):
        """Save a message to SQLite (always runs)."""
        db_path = self._memory_db_path()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO memory (role, text) VALUES (?, ?)",
                (role, text),
            )
            if getattr(self, "_memory_fts_ok", False):
                try:
                    conn.execute(
                        "INSERT INTO memory_fts (role, text, created_at) "
                        "VALUES (?, ?, datetime('now','localtime'))",
                        (role, text),
                    )
                except Exception:
                    pass
            conn.commit()
            conn.close()
        except Exception as e:
            # Crítico: si no se guarda, se pierde un mensaje de la memoria infinita.
            _log_warn("memoria", "no pude guardar el mensaje en SQLite", e)
        self._prune_memory()
        self._save_count = getattr(self, "_save_count", 0) + 1
        if self._save_count % 50 == 0:
            self._compress_context()

    def _save_memory(self, role, text):
        """Save to SQLite + mirror to external provider + Obsidian vault if configured."""
        self._save_memory_sqlite(role, text)
        # Track current session messages for clean restart
        if not hasattr(self, "_current_session_msgs"):
            self._current_session_msgs = []
        self._current_session_msgs.append({
            "role": role, "text": text, "ts": time.time()
        })
        # Optional mirror to external provider
        try:
            cfg = self.load_claudy_config()
            if (cfg.get("memory", {}).get("provider") or "sqlite") != "sqlite":
                if not hasattr(self, "_mem_provider"):
                    try:
                        import memory_providers
                        self._mem_provider = memory_providers.get_provider(cfg, self)
                    except Exception:
                        self._mem_provider = None
                if self._mem_provider and not isinstance(self._mem_provider, type(self)):
                    try:
                        self._mem_provider.save(role, text)
                    except Exception:
                        pass
            # Always mirror to Obsidian vault
            try:
                vault = self._get_or_create_obsidian_vault()
                import obsidian_export as ox
                ox.append_today(vault, role, text)
            except Exception as e:
                print(f"[obsidian] error: {e}")
        except Exception:
            pass

    def _prune_memory(self):
        """Keep DB from growing infinitely large."""
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return
        try:
            conn = sqlite3.connect(db_path)
            total = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
            if total > MEMORY_MAX_MESSAGES * 4:
                # Archive old rows to memory_archive table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_archive (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        role TEXT, text TEXT, created_at TEXT
                    )
                """)
                excess = total - MEMORY_MAX_MESSAGES * 2
                conn.execute("""
                    INSERT INTO memory_archive (role, text, created_at)
                    SELECT role, text, created_at FROM memory ORDER BY id ASC LIMIT ?
                """, (excess,))
                conn.execute("DELETE FROM memory WHERE id IN (SELECT id FROM memory ORDER BY id ASC LIMIT ?)", (excess,))
                conn.commit()
            conn.close()
        except Exception as e:
            # Crítico: el archivado protege el contrato de memoria infinita.
            _log_warn("memoria", "fallo al podar/archivar memoria", e)

    _VAULT_STOPWORDS = {
        "para", "como", "esta", "este", "esto", "esos", "esas", "pero", "porque", "con",
        "los", "las", "del", "una", "uno", "unos", "unas", "que", "qué", "cual", "cuál",
        "donde", "dónde", "cuando", "cuándo", "sobre", "entre", "hacia", "desde", "hasta",
        "claudy", "felipe", "tengo", "quiero", "puedes", "dame", "the", "and", "for", "with",
        "qcore", "memoria", "memorias", "contexto", "nota", "notas",
    }

    def _load_vault_notes(self, max_age=300):
        """Carga las notas .md del vault QCORE como lista de
        (ruta_rel, nombre, contenido). Caché incremental por mtime: tras la
        primera pasada solo se releen del disco las notas que cambiaron
        (antes se releía el vault completo cada 5 minutos)."""
        import time as _t
        now = _t.time()
        if getattr(self, "_vault_notes_cache", None) is not None and (now - getattr(self, "_vault_cache_time", 0)) < max_age:
            return self._vault_notes_cache
        prev = getattr(self, "_vault_notes_mtimes", {}) or {}
        prev_content = {rel: (name, content) for rel, name, content
                        in (getattr(self, "_vault_notes_cache", None) or [])}
        notes, mtimes = [], {}
        try:
            vault = self._get_obsidian_vault()
            if vault and os.path.isdir(vault):
                for root, dirs, files in os.walk(vault):
                    dirs[:] = [d for d in dirs if d not in (".obsidian", ".git", "Templates")]
                    for f in files:
                        if not f.endswith(".md"):
                            continue
                        fp = os.path.join(root, f)
                        rel = os.path.relpath(fp, vault)
                        try:
                            mt = os.path.getmtime(fp)
                        except Exception:
                            continue
                        mtimes[rel] = mt
                        if rel in prev_content and prev.get(rel) == mt:
                            name, content = prev_content[rel]
                            notes.append((rel, name, content))
                            continue
                        try:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                                content = fh.read()
                        except Exception:
                            continue
                        notes.append((rel, f, content))
        except Exception:
            pass
        self._vault_notes_cache = notes
        self._vault_notes_mtimes = mtimes
        self._vault_cache_time = now
        return notes

    def _search_vault_relevant(self, query, max_notes=4, max_chars=5000):
        """Devuelve las notas del vault más relevantes al query (campañas, facturas,
        procesos, agentes, etc.). Scoring por coincidencia de palabras clave."""
        import re as _re
        notes = self._load_vault_notes()
        if not notes:
            return ""
        words = [w for w in _re.findall(r"[a-záéíóúñ0-9]{4,}", (query or "").lower())
                 if w not in self._VAULT_STOPWORDS]
        if not words:
            return ""
        scored = []
        for rel, name, content in notes:
            low = content.lower()
            namelow = (rel + " " + name).lower()
            score = 0
            for w in set(words):
                score += low.count(w)
                if w in namelow:
                    score += 8  # coincidencia en nombre/carpeta pesa más
            if score > 0:
                scored.append((score, rel, content))
        if not scored:
            return ""
        scored.sort(key=lambda x: -x[0])
        parts = []
        total = 0
        for score, rel, content in scored[:max_notes]:
            snippet = f"--- {rel} ---\n{content.strip()}\n"
            if total + len(snippet) > max_chars:
                snippet = snippet[:max(0, max_chars - total)] + "...\n"
            parts.append(snippet)
            total += len(snippet)
            if total >= max_chars:
                break
        return ("[Memoria del ecosistema QCORE — notas relevantes del vault]\n"
                + "".join(parts) + "[/Memoria del ecosistema]\n\n") if parts else ""

    # Muletillas de conversación que no son "tema": si solo aparecen estas,
    # el prompt es charla casual y no justifica bajar a la capa profunda.
    _PROMPT_STOPWORDS = frozenset(
        "como cómo esta está estas estás estoy estamos cual cuál cuales cuáles "
        "donde dónde cuando cuándo porque por qué para pero aunque tambien también "
        "entonces ahora hoy ayer mañana bien mal mejor peor mucho poco nada todo "
        "hola hello gracias chao adios adiós saludos buenas buenos dias días "
        "tardes noches favor please".split())

    @classmethod
    def _prompt_keywords(cls, prompt):
        """Palabras clave con contenido del prompt (>= MEMORY_DEEP_MIN_KEYWORD,
        sin stopwords). Base para decidir si una capa de memoria 'cubre' el tema.
        Normaliza diacríticos antes de filtrar (cómo→como) para que las
        muletillas acentuadas también caigan."""
        words = re.findall(r"[a-záéíóúñü0-9]+", (prompt or "").lower())
        stop = cls._VAULT_STOPWORDS | cls._PROMPT_STOPWORDS
        out = set()
        for w in words:
            if len(w) < MEMORY_DEEP_MIN_KEYWORD:
                continue
            norm = w.translate(str.maketrans("áéíóú", "aeiou"))
            if w in stop or norm in stop:
                continue
            out.add(w)
        return out

    def _should_escalate_to_deep(self, prompt, window_msgs):
        """A5 — ¿hay que bajar a la capa profunda (FTS5 + vault)?

        Devuelve False (no escalar) solo si la ventana deslizante ya contiene
        TODAS las palabras clave del prompt: el contexto reciente basta y la
        búsqueda profunda sería ruido. Si el prompt no tiene palabras clave
        (saludo, charla casual), tampoco se escala."""
        keywords = self._prompt_keywords(prompt)
        if not keywords:
            return False
        haystack = " ".join((m.get("text") or "") for m in (window_msgs or [])).lower()
        haystack = haystack.translate(str.maketrans("áéíóú", "aeiou"))
        missing = [k for k in keywords
                   if k.translate(str.maketrans("áéíóú", "aeiou")) not in haystack]
        # Escala si al menos una palabra clave del prompt no aparece en la ventana.
        return bool(missing)

    def _build_memory_context(self, prompt=None):
        # A5 — Recuperación search-first por capas. Capa 1 (buffer) + Capa 2
        # (ventana deslizante) siempre se cargan vía SQL con LIMIT. La Capa 3
        # (FTS5 profundo en el archivo + notas del vault) solo se activa si la
        # ventana caliente no cubre las palabras clave del prompt — así una
        # pregunta sobre algo recién hablado no arrastra ruido del archivo.
        messages = self._load_recent_memory(MEMORY_WINDOW_MESSAGES)
        escalate = bool(prompt) and self._should_escalate_to_deep(prompt, messages)

        # Capa 3a — Notas relevantes del vault (campañas, facturas, procesos...).
        # Solo si hay que escalar: si el tema ya está caliente, nos lo saltamos.
        relevant_vault = ""
        if escalate:
            try:
                relevant_vault = self._search_vault_relevant(prompt)
            except Exception:
                relevant_vault = ""
        if not messages:
            return relevant_vault
        context_parts = []
        total_chars = 0
        for msg in reversed(messages):
            line = f"{msg['role']}: {msg['text']}\n"
            if total_chars + len(line) > MEMORY_CONTEXT_CHARS:
                break
            context_parts.insert(0, line)
            total_chars += len(line)
        chat_context = "[Contexto de conversaciones anteriores]\n" + "".join(context_parts) + "\n[Fin del contexto]\n\n" if context_parts else ""

        # Capa 3b — Recall de historia antigua relevante al prompt (FTS5 sobre
        # toda la historia, incluido el archivo). Excluye lo ya presente en la
        # ventana caliente. Solo cuando se escala (search-first).
        if escalate:
            try:
                recent_texts = {m["text"] for m in messages}
                hits = [h for h in self._search_memory(prompt, limit=8)
                        if h.get("text") and h["text"] not in recent_texts]
                if hits:
                    old_parts, old_chars = [], 0
                    for h in hits:
                        snippet = f"[{h.get('time', '')}] {h['role']}: {h['text'][:400]}\n"
                        if old_chars + len(snippet) > 2500:
                            break
                        old_parts.append(snippet)
                        old_chars += len(snippet)
                    if old_parts:
                        chat_context += ("[Recuerdos relevantes de conversaciones antiguas]\n"
                                         + "".join(old_parts)
                                         + "[/Recuerdos relevantes]\n\n")
            except Exception:
                pass

        # Add compressed summaries if available
        try:
            db_path = self._memory_db_path()
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                summaries = conn.execute(
                    "SELECT text FROM memory_summaries ORDER BY id DESC LIMIT 3"
                ).fetchall()
                conn.close()
                if summaries:
                    sum_text = "\n".join(s[0] for s in summaries)
                    chat_context += f"[Historial resumido]\n{sum_text}\n[/Historial resumido]\n\n"
        except Exception:
            pass

        # Capa 3c — Notas más recientes de Obsidian por mtime. Solo al escalar:
        # recorrer el vault entero en cada prompt es caro y, si el tema ya está
        # caliente, estas notas serían ruido.
        obs_context = ""
        try:
            if escalate:
                vault = self._get_obsidian_vault()
            else:
                vault = None
            if vault:
                md_files = []
                for root, dirs, files in os.walk(vault):
                    if '.obsidian' in dirs:
                        dirs.remove('.obsidian')
                    for f in files:
                        if f.endswith('.md'):
                            fpath = os.path.join(root, f)
                            md_files.append((fpath, os.path.getmtime(fpath)))
                
                if md_files:
                    md_files.sort(key=lambda x: x[1], reverse=True)
                    obs_parts = []
                    obs_chars = 0
                    for fpath, _ in md_files[:3]:
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            note_name = os.path.basename(fpath)
                            snippet = f"--- Nota: {note_name} ---\n{content}\n"
                            if obs_chars + len(snippet) > 4000:
                                snippet = snippet[:4000 - obs_chars] + "...\n"
                            obs_parts.append(snippet)
                            obs_chars += len(snippet)
                            if obs_chars >= 4000:
                                break
                        except Exception:
                            continue
                    
                    if obs_parts:
                        obs_context = "[Contexto de notas recientes en Obsidian]\n" + "".join(obs_parts) + "\n[Fin de notas de Obsidian]\n\n"
        except Exception as e:
            print(f"Error reading Obsidian context: {e}")

        return relevant_vault + chat_context + obs_context

    def _compress_context(self):
        """Summarize old messages to save token budget."""
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return
        try:
            conn = sqlite3.connect(db_path)
            total = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
            if total < MEMORY_MAX_MESSAGES * 3:
                conn.close()
                return
            # Find the oldest checkpoint to protect its range
            oldest_cp = conn.execute(
                "SELECT MIN(memory_id) FROM checkpoints"
            ).fetchone()[0]
            # Keep last 200 messages, but protect checkpointed messages
            keep = MEMORY_MAX_MESSAGES * 2
            if oldest_cp:
                # Don't delete messages that are part of any checkpoint
                conn.close()
                return  # Skip compression if checkpoints exist (simpler approach)
            old = conn.execute(
                "SELECT id, role, text FROM memory ORDER BY id ASC LIMIT ?",
                (total - keep,),
            ).fetchall()
            if not old:
                conn.close()
                return
            summary = self._summarize_messages(old)
            if summary:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        text TEXT NOT NULL,
                        range_start INTEGER, range_end INTEGER,
                        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                    )
                """)
                conn.execute(
                    "INSERT INTO memory_summaries (text, range_start, range_end) VALUES (?, ?, ?)",
                    (summary, old[0][0], old[-1][0]),
                )
                # Contrato de memoria infinita: archivar SIEMPRE antes de
                # compactar (antes se borraban los originales y solo quedaba
                # el resumen).
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_archive (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        role TEXT, text TEXT, created_at TEXT
                    )
                """)
                ids = [row[0] for row in old]
                conn.executemany(
                    "INSERT INTO memory_archive (role, text, created_at) "
                    "SELECT role, text, created_at FROM memory WHERE id = ?",
                    [(i,) for i in ids],
                )
                conn.executemany("DELETE FROM memory WHERE id = ?", [(i,) for i in ids])
                conn.commit()
            conn.close()
        except Exception:
            pass

    def _summarize_messages(self, messages):
        """Create a brief summary of messages."""
        if not messages:
            return ""
        parts = []
        for mid, role, text in messages:
            short = text[:200].replace("\n", " ") if text else ""
            parts.append(f"[{role}]: {short}")
        if len(parts) > 50:
            parts = parts[:50]
        return "Resumen de conversacion anterior: " + "; ".join(parts)

    def _compress_and_save_to_obsidian(self):
        """Compress current session messages and save summary to Obsidian."""
        session_msgs = getattr(self, "_current_session_msgs", [])
        if not session_msgs or len(session_msgs) < 2:
            return
        # Build summary text
        parts = []
        for m in session_msgs:
            role = m.get("role", "")
            text = (m.get("text", "") or "")[:300]
            parts.append(f"[{role}]: {text}")
        summary = "Resumen de sesion: " + "; ".join(parts[:30])
        # Save to SQLite summaries
        try:
            db_path = self._memory_db_path()
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        text TEXT NOT NULL,
                        range_start INTEGER, range_end INTEGER,
                        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                    )
                """)
                conn.execute(
                    "INSERT INTO memory_summaries (text, range_start, range_end) VALUES (?, ?, ?)",
                    (summary, 0, len(session_msgs)),
                )
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"[compress] db error: {e}")
        # Save to Obsidian
        try:
            vault = self._get_or_create_obsidian_vault()
            root = os.path.join(vault, "Claudy", "Summaries")
            os.makedirs(root, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            product = getattr(self, "_active_product", "General")
            path = os.path.join(root, f"sesion_{product}_{ts}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"---\ntags: [claudy, summary, {product.lower().replace(' ','-')}]\ndate: {ts[:10]}\nproduct: {product}\n---\n\n")
                f.write(f"# Sesion {product} — {ts[:10]}\n\n")
                for m in session_msgs:
                    role = "**Felipe**" if m.get("role") in ("user", "Usuario") else "**Claudy**"
                    text = (m.get("text", "") or "")[:500]
                    f.write(f"{role}: {text}\n\n")
        except Exception as e:
            print(f"[obsidian summary] error: {e}")

    def _get_or_create_obsidian_vault(self):
        """Auto-detect or create Obsidian vault for Claudy memory.
        Priority: 1) config, 2) QCORE Drive vault, 3) local fallback.
        """
        try:
            cfg = self.load_claudy_config()
            vault = (cfg.get("obsidian", {}) or {}).get("vault", "")
            if vault and os.path.isdir(vault):
                return vault
        except Exception:
            pass
        # Primary: QCORE ecosystem vault on Google Drive
        drive_vault = r"G:\Mi unidad\QCORE-ECOSYSTEM\MEMORIAS\VAULT"
        if os.path.isdir(drive_vault):
            return drive_vault
        # Fallback: local
        default = os.path.join(os.path.expanduser("~"), "Documents", "Claudy", "Obsidian")
        os.makedirs(default, exist_ok=True)
        return default

    def _create_checkpoint(self, label="manual"):
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return "No hay memoria activa para guardar un checkpoint."
        try:
            conn = sqlite3.connect(db_path)
            last_id = conn.execute("SELECT MAX(id) FROM memory").fetchone()[0]
            if last_id is None:
                conn.close()
                return "No hay mensajes en la memoria."
            conn.execute(
                "INSERT INTO checkpoints (label, memory_id) VALUES (?, ?)",
                (label, last_id),
            )
            conn.commit()
            conn.close()
            return f"Checkpoint '{label}' guardado en el mensaje #{last_id}."
        except Exception as e:
            return f"Error al guardar checkpoint: {e}"

    def _rollback_checkpoint(self, label=None):
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return "No hay memoria activa para hacer rollback."
        try:
            conn = sqlite3.connect(db_path)
            if label:
                cp = conn.execute(
                    "SELECT id, label, memory_id, created_at FROM checkpoints WHERE label = ? ORDER BY id DESC LIMIT 1",
                    (label,),
                ).fetchone()
            else:
                cp = conn.execute(
                    "SELECT id, label, memory_id, created_at FROM checkpoints ORDER BY id DESC LIMIT 1",
                ).fetchone()
            if not cp:
                conn.close()
                return "No hay checkpoints guardados. Usa /checkpoint para crear uno."
            # Delete all messages after the checkpoint
            conn.execute("DELETE FROM memory WHERE id > ?", (cp[2],))
            # Delete this checkpoint and any newer ones
            conn.execute("DELETE FROM checkpoints WHERE id >= ?", (cp[0],))
            conn.commit()
            conn.close()
            return f"Rollback al checkpoint '{cp[1]}' (mensaje #{cp[2]}, {cp[3]}). Se eliminaron los mensajes posteriores."
        except Exception as e:
            return f"Error en rollback: {e}"

    def _list_checkpoints(self):
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return "No hay memoria activa."
        try:
            conn = sqlite3.connect(db_path)
            cps = conn.execute(
                "SELECT id, label, memory_id, created_at FROM checkpoints ORDER BY id DESC LIMIT 10"
            ).fetchall()
            conn.close()
            if not cps:
                return "No hay checkpoints guardados."
            lines = ["Checkpoints:"]
            for cid, label, mid, cat in cps:
                lines.append(f"  [{cat}] {label} — mensaje #{mid}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    def _search_memory_cmd(self, query):
        """Comando /memoria <consulta> — busca en TODA la historia (FTS5)."""
        results = self._search_memory(query, limit=8)
        if not results:
            return f"No encontré '{query}' en la memoria (busqué en toda la historia)."
        lines = [f"Encontré esto sobre '{query}' en mi memoria:"]
        for r in results:
            text = (r.get("text") or "")[:220].replace("\n", " ")
            when = (r.get("time") or "")[:16]
            lines.append(f"  • [{when}] {r.get('role', '')}: {text}")
        return "\n".join(lines)

    def _get_obsidian_vault(self):
        """Find Obsidian vault path from config or common locations."""
        config_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
            vault = cfg.get("obsidian", {}).get("vaultPath", "")
            if vault and os.path.isdir(vault):
                return vault
        except Exception:
            pass
        # Common default locations. El vault QCORE en Drive tiene prioridad.
        defaults = [
            r"G:\Mi unidad\QCORE-ECOSYSTEM\MEMORIAS\VAULT",
            os.path.join(os.path.expanduser("~"), "Obsidian"),
            os.path.join(os.path.expanduser("~"), "Documents", "Obsidian"),
            os.path.join(os.path.expanduser("~"), "OneDrive", "Obsidian"),
        ]
        for d in defaults:
            if os.path.isdir(d):
                return d
        # Último recurso: el resolver de escritura (config → Drive QCORE → local).
        try:
            return self._get_or_create_obsidian_vault()
        except Exception:
            return None

    _MEMORY_UPDATE_TRIGGERS = [
        "actualiza la memoria de los agentes",
        "actualiza tu memoria y la de obsidian",
        "guarda esto en tu memoria y en obsidian",
        "actualiza tus memorias",
        "actualiza tu memoria",
        "actualiza la memoria",
        "actualiza obsidian",
        "guarda esto en tu memoria",
        "guarda esto en obsidian",
        "guarda en tu memoria",
        "guarda en la memoria",
        "guarda en memoria",
        "guarda en obsidian",
        "guárdalo en tu memoria",
        "guardalo en tu memoria",
        "guárdalo en memoria",
        "guardalo en memoria",
        "agrega a tu memoria",
        "agrégalo a tu memoria",
        "agregalo a tu memoria",
        "agrega a la memoria",
        "memoriza esto",
        "memoriza que",
        "memoriza:",
        "graba en memoria",
        "ten esto en tu memoria",
        "recuérdalo en tu memoria",
        "recuerdalo en tu memoria",
    ]

    def _extract_memory_fact(self, prompt, lower):
        """Si el prompt ordena guardar conocimiento en memoria, devuelve
        (True, fact). `fact` puede venir vacío (=> resumir conversación reciente).
        Si no es una orden de memoria, devuelve (False, '')."""
        hit = None
        for t in self._MEMORY_UPDATE_TRIGGERS:
            if t in lower:
                hit = t
                break
        if not hit:
            return False, ""
        idx = lower.find(hit)
        fact = prompt[idx + len(hit):].strip()
        # Quitar conectores iniciales ("con", "que", "lo siguiente:", ":", "esto:")
        fact = re.sub(r'^(?:\s*[:\-,]\s*)?(?:con|que|de que|lo siguiente|esto|esto que|el dato de que|el hecho de que)\b[:\s]*',
                      '', fact, flags=re.IGNORECASE).strip(" :,-")
        # Referencias a la conversación => resumir (fact vacío)
        if re.match(r'^(lo que|lo último|lo ultimo|lo de|nuestra conversaci|la conversaci|lo que hablamos|lo que te dije|eso|esto)\b',
                    fact, flags=re.IGNORECASE):
            fact = ""
        return True, fact

    def _remember_knowledge(self, fact, summarize_if_empty=True):
        """Guarda un conocimiento DURADERO en las capas de memoria de Claudy:
        memory.db (memoria compartida de Claudy + agentes) y el vault de Obsidian.
        Si `fact` viene vacío, resume la conversación reciente. Devuelve el mensaje
        de confirmación para mostrar a Felipe."""
        fact = (fact or "").strip()
        if not fact and summarize_if_empty:
            try:
                recent = self._load_memory()[-10:]
                convo = "\n".join(f"{m.get('role','')}: {m.get('text','')}" for m in recent if m.get("text"))
                if convo.strip():
                    sp = ("Extrae en 1-3 frases concisas el DATO o CONOCIMIENTO duradero que "
                          "Claudy debe recordar de esta conversación (hechos, decisiones, "
                          "preferencias de Felipe; NADA de saludos ni relleno). Devuelve solo el "
                          "dato, sin preámbulo:\n\n" + convo)
                    fact = (self.send_quick_message(sp, _skip_skill_action=True, timeout=60) or "").strip()
            except Exception:
                pass
        if not fact:
            return ("¿Qué quieres que recuerde? Dime el dato, o di "
                    "\"actualiza tu memoria con lo último que hablamos\".")

        saved = []
        # 1) memory.db — base compartida por Claudy y los agentes (AGENTES-MEMORY)
        try:
            self._save_memory_sqlite("Conocimiento", f"[MEMORIA] {fact}")
            saved.append("memoria de Claudy y agentes (memory.db)")
        except Exception:
            pass
        # 2) Obsidian — nota duradera y recuperable por búsqueda de relevancia
        try:
            vault = self._get_obsidian_vault()
            if vault and os.path.isdir(vault):
                note_dir = os.path.join(vault, "Claudy")
                os.makedirs(note_dir, exist_ok=True)
                note_path = os.path.join(note_dir, "Memoria-Claudy.md")
                if not os.path.exists(note_path):
                    with open(note_path, "w", encoding="utf-8") as f:
                        f.write("---\ntags: [claudy, memoria]\n---\n\n# Memoria de Claudy\n\n"
                                "Conocimiento duradero que Claudy debe tener presente.\n\n")
                stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                with open(note_path, "a", encoding="utf-8") as f:
                    f.write(f"- {stamp} · {fact}\n")
                saved.append("Obsidian (Claudy/Memoria-Claudy.md)")
        except Exception:
            pass
        # 3) Refrescar la caché del vault para que el dato sea recuperable de inmediato
        self._vault_notes_cache = None

        if not saved:
            return "No pude guardar el dato (revisa memory.db y el vault de Obsidian)."
        return ("Memoria actualizada ✓\nGuardé: \"" + (fact[:200] + ("..." if len(fact) > 200 else "")) +
                "\"\nEn: " + " · ".join(saved) + ".\nLo tendré presente cuando me preguntes.")

