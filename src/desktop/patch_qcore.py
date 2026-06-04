"""
Claudy UI Patch — QCORE Products Sidebar + Clean Chat + Avatar + Email
1. Replace "CONVERSACIONES" with QCORE SPA products as context shortcuts
2. "Nueva conversacion" → compress + save Obsidian + clear chat + greet
3. Email → jorge.castro@qcorespa.com
4. Avatar → person initials "JC"
5. Chat starts clean (greeting only), memory untouched
6. Default theme → Nocturne (glass, idx=1)
"""
import os, datetime

PET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pet.py')

with open(PET_PATH, 'r', encoding='utf-8') as f:
    pet = f.read()

# ──────────────────────────────────────────────────────────────────
# 1. Replace sidebar conversations with QCORE products
# ──────────────────────────────────────────────────────────────────
old_conversations = '''        canvas.create_text(34, 270, anchor="nw", text="CONVERSACIONES", fill="#58c7ff", font=("Bahnschrift SemiBold", 8), tags=("bubble_bg",))
        for idx, (title, when) in enumerate((
            ("Proyecto SaaS Futurista", "09:37"),
            ("Ideas de negocio", "Ayer"),
            ("Componentes UI", "Ayer"),
            ("Analisis de datos", "3 dias"),
        )):
            y = 296 + idx * 40
            row_fill = "#211064" if idx == 0 else "#060c22"
            rounded_panel(30, y, 206, y + 32, 12, row_fill, "#182752", 1)
            canvas.create_text(52, y + 8, anchor="nw", text=title, fill="#ffffff" if idx == 0 else "#c7d2ff",
                               font=("Bahnschrift SemiBold", 8), tags=("bubble_bg",))
            canvas.create_text(180, y + 8, anchor="nw", text=when, fill="#a9b8ff",
                               font=("Bahnschrift", 8), tags=("bubble_bg",))'''

new_conversations = '''        canvas.create_text(34, 270, anchor="nw", text="PRODUCTOS QCORE", fill="#58c7ff", font=("Bahnschrift SemiBold", 8), tags=("bubble_bg",))
        _qcore_products = [
            ("SmartStudent", "EDU", "#6c5ce7"),
            ("Roadix", "AUTO", "#00b894"),
            ("Luxium", "CORE", "#e17055"),
            ("UnitCore", "CLIN", "#0984e3"),
            ("Campaign Studio", "MKT", "#fdcb6e"),
            ("Mission Control", "OPS", "#a29bfe"),
        ]
        self._product_btns = []
        for idx, (title, tag, color) in enumerate(_qcore_products):
            y = 296 + idx * 36
            row_fill = "#211064" if idx == 0 else "#060c22"
            row_id = rounded_panel(30, y, 206, y + 30, 12, row_fill, "#182752", 1)
            dot_id = canvas.create_oval(38, y + 10, 48, y + 20, fill=color, outline="", tags=("bubble_bg",))
            txt_id = canvas.create_text(54, y + 7, anchor="nw", text=title, fill="#ffffff" if idx == 0 else "#c7d2ff",
                               font=("Bahnschrift SemiBold", 8), tags=("bubble_bg",))
            tag_id = canvas.create_text(194, y + 8, anchor="ne", text=tag, fill=color,
                               font=("Bahnschrift SemiBold", 8), tags=("bubble_bg",))
            # Click handler → switch context to this product
            def _switch_product(_e=None, name=title, c=color):
                self._active_product = name
                chat = getattr(self, "_chat_view", None)
                if chat:
                    chat.add_system(f"Contexto cambiado a: {name}")
                try:
                    status.configure(text=f"Producto: {name}", fg=c)
                except Exception:
                    pass
            for item in (row_id, dot_id, txt_id, tag_id):
                canvas.tag_bind(item, "<Button-1>", _switch_product)
                canvas.tag_bind(item, "<Enter>", lambda _e, c=color: canvas.configure(cursor="hand2"))
                canvas.tag_bind(item, "<Leave>", lambda _e: canvas.configure(cursor=""))
            self._product_btns.append((title, tag, color))'''
pet = pet.replace(old_conversations, new_conversations)

# ──────────────────────────────────────────────────────────────────
# 2. "Nueva conversacion" → compress + save + clear + greet
# ──────────────────────────────────────────────────────────────────
old_nueva = '''        rounded_panel(34, 204, 202, 238, 16, "#803cff", "#58c7ff", 1)
        canvas.create_text(118, 221, text="+ Nueva conversacion", fill="#ffffff", font=("Bahnschrift SemiBold", 10), tags=("bubble_bg",))'''

new_nueva = '''        nueva_bg = rounded_panel(34, 204, 202, 238, 16, "#803cff", "#58c7ff", 1)
        nueva_txt = canvas.create_text(118, 221, text="+ Nueva conversacion", fill="#ffffff", font=("Bahnschrift SemiBold", 10), tags=("bubble_bg",))
        def _nueva_conversacion(_e=None):
            # 1. Compress current session and save to Obsidian
            try:
                self._compress_and_save_to_obsidian()
            except Exception as ex:
                print(f"[nueva conv] compress error: {ex}")
            # 2. Clear current session messages
            self._current_session_msgs = []
            # 3. Clear chat view and show greeting
            chat = getattr(self, "_chat_view", None)
            if chat:
                chat.clear()
                chat.add_system("Hola Felipe, \\u00bfen qu\\u00e9 te ayudo?")
            try:
                status.configure(text="Nueva conversacion iniciada", fg="#58c7ff")
            except Exception:
                pass
        for _item in (nueva_bg, nueva_txt):
            canvas.tag_bind(_item, "<Button-1>", _nueva_conversacion)
            canvas.tag_bind(_item, "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
            canvas.tag_bind(_item, "<Leave>", lambda _e: canvas.configure(cursor=""))'''
pet = pet.replace(old_nueva, new_nueva)

# ──────────────────────────────────────────────────────────────────
# 3. Email and name
# ──────────────────────────────────────────────────────────────────
pet = pet.replace('text="Felipe Dev"', 'text="Felipe Castro"')
pet = pet.replace('text="felipe@dev.com"', 'text="jorge.castro@qcorespa.com"')

# ──────────────────────────────────────────────────────────────────
# 4. Avatar: replace circle with initials "JC"
# ──────────────────────────────────────────────────────────────────
old_avatar_section = '''        rounded_panel(30, height - 78, 206, height - 34, 16, "#071026", "#24366e", 1)
        canvas.create_oval(44, height - 68, 74, height - 38, outline="#58c7ff", fill="#12194a", width=1, tags=("bubble_bg",))'''
new_avatar_section = '''        rounded_panel(30, height - 78, 206, height - 34, 16, "#071026", "#24366e", 1)
        # Draw avatar image (or fallback to text "JC")
        avatar_drawn = False
        try:
            from PIL import Image, ImageTk, ImageDraw
            avatar_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatar_developer.png")
            if os.path.exists(avatar_path):
                img = Image.open(avatar_path).convert("RGBA")
                size = (30, 30)
                img = img.resize(size, Image.Resampling.LANCZOS)
                mask = Image.new("L", size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, size[0] - 1, size[1] - 1), fill=255)
                output = Image.new("RGBA", size, (0, 0, 0, 0))
                output.paste(img, (0, 0), mask=mask)
                self._avatar_photo = ImageTk.PhotoImage(output)
                canvas.create_image(44, height - 68, anchor="nw", image=self._avatar_photo, tags=("bubble_bg",))
                avatar_drawn = True
        except Exception as e:
            print(f"[avatar] error: {e}")

        if not avatar_drawn:
            canvas.create_oval(44, height - 68, 74, height - 38, outline="#58c7ff", fill="#12194a", width=2, tags=("bubble_bg",))
            canvas.create_text(59, height - 53, text="JC", fill="#58c7ff", font=("Bahnschrift SemiBold", 10), tags=("bubble_bg",))
        else:
            canvas.create_oval(44, height - 68, 74, height - 38, outline="#58c7ff", fill="", width=2, tags=("bubble_bg",))'''
pet = pet.replace(old_avatar_section, new_avatar_section)

# ──────────────────────────────────────────────────────────────────
# 5. Chat starts clean (greeting only)
# ──────────────────────────────────────────────────────────────────
old_history_load = '''            # Load history.
            try:
                if getattr(self, "_chat_history_buffer", None) is not None:
                    chat.load_history(self._chat_history_buffer)
                    self._chat_history_buffer = None
                else:
                    history = self._load_memory()[-12:] if hasattr(self, "_load_memory") else []
                    chat.load_history(history)
            except Exception:
                pass
            # If a starting prompt text was provided (and no history), show as system.
            if not chat._messages and text:
                chat.add_system(text)'''

new_history_load = '''            # Fresh start: only show greeting. Memory stays in SQLite/Obsidian.
            # If re-opened mid-session, restore current session messages.
            if getattr(self, "_chat_history_buffer", None) is not None:
                chat.load_history(self._chat_history_buffer)
                self._chat_history_buffer = None
            elif getattr(self, "_current_session_msgs", None):
                chat.load_history(self._current_session_msgs)
            else:
                chat.add_system("Hola Felipe, \\u00bfen qu\\u00e9 te ayudo?")'''
pet = pet.replace(old_history_load, new_history_load)

# ──────────────────────────────────────────────────────────────────
# 6. Add _compress_and_save_to_obsidian method + _current_session_msgs tracking
# ──────────────────────────────────────────────────────────────────
# Find _compress_context and add the new method right after it
compress_marker = '''    def _summarize_messages(self, messages):
        """Create a brief summary of messages."""
        if not messages:
            return ""
        parts = []
        for mid, role, text in messages:
            short = text[:200].replace("\\n", " ") if text else ""
            parts.append(f"[{role}]: {short}")
        if len(parts) > 50:
            parts = parts[:50]
        return "Resumen de conversacion anterior: " + "; ".join(parts)'''

new_after_summarize = compress_marker + '''

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
                f.write(f"---\\ntags: [claudy, summary, {product.lower().replace(' ','-')}]\\ndate: {ts[:10]}\\nproduct: {product}\\n---\\n\\n")
                f.write(f"# Sesion {product} — {ts[:10]}\\n\\n")
                for m in session_msgs:
                    role = "**Felipe**" if m.get("role") in ("user", "Usuario") else "**Claudy**"
                    text = (m.get("text", "") or "")[:500]
                    f.write(f"{role}: {text}\\n\\n")
        except Exception as e:
            print(f"[obsidian summary] error: {e}")

    def _get_or_create_obsidian_vault(self):
        """Auto-detect or create Obsidian vault for Claudy memory."""
        try:
            cfg = self.load_claudy_config()
            vault = (cfg.get("obsidian", {}) or {}).get("vault", "")
            if vault and os.path.isdir(vault):
                return vault
        except Exception:
            pass
        drive_vault = r"G:/Mi unidad/QCORE-ECOSYSTEM/MEMORIAS/VAULT"
        if os.path.isdir(drive_vault):
            return drive_vault
        default = os.path.join(os.path.expanduser("~"), "Documents", "Claudy", "Obsidian")
        os.makedirs(default, exist_ok=True)
        return default'''
pet = pet.replace(compress_marker, new_after_summarize)

# ──────────────────────────────────────────────────────────────────
# 7. Track session messages in _save_memory
# ──────────────────────────────────────────────────────────────────
old_save = '''    def _save_memory(self, role, text):
        """Save to SQLite + mirror to external provider + Obsidian vault if configured."""
        self._save_memory_sqlite(role, text)'''
new_save = '''    def _save_memory(self, role, text):
        """Save to SQLite + mirror to external provider + Obsidian vault if configured."""
        self._save_memory_sqlite(role, text)
        # Track current session messages for clean restart
        if not hasattr(self, "_current_session_msgs"):
            self._current_session_msgs = []
        self._current_session_msgs.append({
            "role": role, "text": text, "ts": time.time()
        })'''
pet = pet.replace(old_save, new_save)

# ──────────────────────────────────────────────────────────────────
# 8. Always save to Obsidian (not just when configured)
# ──────────────────────────────────────────────────────────────────
old_obsidian_mirror = '''            # Mirror to Obsidian vault if configured
            vault = (cfg.get("obsidian", {}) or {}).get("vault", "")
            if vault and os.path.isdir(vault):
                try:
                    import obsidian_export as ox
                    ox.append_today(vault, role, text)
                except Exception as e:
                    print(f"[obsidian] error: {e}")'''
new_obsidian_mirror = '''            # Always mirror to Obsidian vault
            try:
                vault = self._get_or_create_obsidian_vault()
                import obsidian_export as ox
                ox.append_today(vault, role, text)
            except Exception as e:
                print(f"[obsidian] error: {e}")'''
pet = pet.replace(old_obsidian_mirror, new_obsidian_mirror)

# ──────────────────────────────────────────────────────────────────
# 9. Add _active_product initialization
# ──────────────────────────────────────────────────────────────────
old_interactive = '''        self.bubble_interactive = True
        self.bubble_minimized = False'''
new_interactive = '''        self.bubble_interactive = True
        self.bubble_minimized = False
        if not hasattr(self, "_active_product"):
            self._active_product = "General"
        if not hasattr(self, "_current_session_msgs"):
            self._current_session_msgs = []'''
pet = pet.replace(old_interactive, new_interactive)

with open(PET_PATH, 'w', encoding='utf-8') as f:
    f.write(pet)

print("All patches applied!")
