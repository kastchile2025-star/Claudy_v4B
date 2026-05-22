"""Modern canvas-based chat view for Claudy.

Design principles (impeccable / product register):
- Restrained color (tinted neutrals + one accent <=10%), no glassmorphism reflex.
- Asymmetric corner radii to differentiate roles (no iMessage tails).
- Monogram avatars (no emoji glyphs, no gradient, no glow).
- Tighter type scale (~1.2 ratio), one family, system font.
- Motion: ease-out-expo, 180ms, slide+fade, no bounce.
- Spacing rhythm varies (user 14/12, bot 16/14).
"""
from __future__ import annotations

import math
import time
import tkinter as tk
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageTk


# -------------------- helpers --------------------

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _ease_out_expo(t: float) -> float:
    return 1.0 if t >= 1 else 1 - math.pow(2, -10 * t)


def _font(size: int, weight: str = "normal") -> ImageFont.FreeTypeFont:
    name = "segoeuib.ttf" if weight == "bold" else "segoeui.ttf"
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except OSError:
            return ImageFont.load_default()


def _bubble_asymmetric(
    width: int,
    height: int,
    fill: str,
    border: str | None,
    role: str,
) -> Image.Image:
    """Bubble with role-specific asymmetric corner radii.

    user → squared top-right (16, 4, 16, 16)
    bot  → squared top-left  (4, 16, 16, 16)
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill_rgb = _hex_to_rgb(fill)
    if role == "user":
        radii = (16, 4, 16, 16)
    else:
        radii = (4, 16, 16, 16)
    try:
        d.rounded_rectangle((0, 0, width - 1, height - 1),
                            radius=14, fill=(*fill_rgb, 255), corners=radii)
    except TypeError:
        # Pillow < 9.2 fallback: uniform radius
        d.rounded_rectangle((0, 0, width - 1, height - 1),
                            radius=14, fill=(*fill_rgb, 255))
    if border:
        try:
            d.rounded_rectangle((0, 0, width - 1, height - 1),
                                radius=14, outline=(*_hex_to_rgb(border), 255),
                                width=1, corners=radii)
        except TypeError:
            d.rounded_rectangle((0, 0, width - 1, height - 1),
                                radius=14, outline=(*_hex_to_rgb(border), 255),
                                width=1)
    return img


def _avatar_monogram(size: int, fill: str, fg: str, char: str, role: str) -> Image.Image:
    """Flat monogram avatar. Bot = squared 4px radius, user = circle."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill_rgb = _hex_to_rgb(fill)
    if role == "bot":
        d.rounded_rectangle((0, 0, size - 1, size - 1), radius=4,
                            fill=(*fill_rgb, 255))
    else:
        d.ellipse((0, 0, size - 1, size - 1), fill=(*fill_rgb, 255))
    font = _font(int(size * 0.55), "bold")
    try:
        bbox = d.textbbox((0, 0), char, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (size - tw) // 2 - bbox[0]
        ty = (size - th) // 2 - bbox[1]
    except Exception:
        tx, ty = size // 4, size // 4
    d.text((tx, ty), char, font=font, fill=(*_hex_to_rgb(fg), 255))
    return img


def _get_bot_avatar(size: int, fill: str, fg: str) -> Image.Image:
    """Load the current active skin frame as bot avatar, fallback to monogram."""
    import os
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        claudy_avatar_path = os.path.join(script_dir, "claudy_orbit_frame_0.png")
        if os.path.exists(claudy_avatar_path):
            img = Image.open(claudy_avatar_path).convert("RGBA")
            # Ensure clean binary transparency threshold matching the 3D sprite
            r, g, b, alpha = img.split()
            binary_alpha = alpha.point(lambda p: 255 if p > 30 else 0)
            img = Image.merge("RGBA", (r, g, b, binary_alpha))
            return img.resize((size, size), Image.Resampling.LANCZOS)
    except Exception:
        pass
    return _avatar_monogram(size, fill, fg, "C", "bot")


# -------------------- ChatView --------------------

# Tipografía: escala 1.2, una familia.
FONT_BODY = ("Segoe UI", 11)
FONT_BADGE = ("Segoe UI", 8, "bold")
FONT_TS = ("Segoe UI", 9)
FONT_SYS = ("Segoe UI", 10, "italic")


class ChatView(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        theme: dict,
        width: int = 330,
        height: int = 280,
        **kw,
    ) -> None:
        super().__init__(parent, bg=theme.get("bg_bubble", "#0f0e14"),
                         highlightthickness=0, bd=0, **kw)
        self.theme = theme
        self._width = width
        self._height = height
        self._messages: list[dict] = []
        self._image_refs: list[ImageTk.PhotoImage] = []
        self._row_widgets: list[tk.Widget] = []
        self._typing_widget: tk.Widget | None = None
        self._typing_after: str | None = None
        self._typing_dot_phase = 0
        self._last_role: str | None = None

        self.canvas = tk.Canvas(
            self, bg=theme.get("bg_bubble", "#0f0e14"),
            highlightthickness=0, bd=0, width=width, height=height,
        )
        self.scroll = tk.Scrollbar(
            self, orient="vertical", width=3,
            bg=theme.get("bg_bubble_border", "#2a2733"),
            troughcolor=theme.get("bg_bubble", "#0f0e14"),
            activebackground=theme.get("accent", "#c4b5fd"),
            highlightthickness=0, bd=0, relief="flat",
            command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self.canvas, bg=theme.get("bg_bubble", "#0f0e14"))
        self._inner_id = self.canvas.create_window(0, 0, anchor="nw", window=self._inner)
        self._inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._on_wheel))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

    # ------------ public api ------------
    def add_user(self, text: str, ts: float | None = None) -> None:
        self._add_message("user", text, ts or time.time())

    def add_bot(self, text: str, ts: float | None = None) -> None:
        self._add_message("bot", text, ts or time.time())

    def add_system(self, text: str) -> None:
        self._add_message("system", text, time.time())

    def add_file_card(
        self,
        filename: str,
        on_open_file=None,
        on_open_folder=None,
        message: str = "Listo. Archivo generado",
    ) -> None:
        """Compact card with file icon, name, message, and clickable folder button."""
        bg_bubble = self.theme.get("bg_bubble", "#0f0e14")
        surface = self.theme.get("bg_bubble_border", "#2a2733")
        accent = self.theme.get("accent", "#c4b5fd")
        text_primary = self.theme.get("text_primary", "#ece9f5")
        text_secondary = self.theme.get("text_secondary", "#8a8499")
        divider = self.theme.get("divider", "#1d1b26")

        pad_top = 10 if self._last_role else 6
        row = tk.Frame(self._inner, bg=bg_bubble)
        row.pack(fill="x", padx=12, pady=(pad_top, 2))

        av_img = _get_bot_avatar(24, self.theme.get("accent_dim", "#3a3349"), accent)
        atkimg = ImageTk.PhotoImage(av_img)
        self._image_refs.append(atkimg)
        av = tk.Label(row, image=atkimg, bg=bg_bubble, bd=0)
        av.pack(side="left", padx=(0, 8), anchor="nw")

        # Card body — bot-style bubble.
        ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").upper()
        card_w = max(220, min(self._width - 80, 300))
        card_h = 64
        bubble_img = _bubble_asymmetric(card_w, card_h, surface, divider, "bot")
        btkimg = ImageTk.PhotoImage(bubble_img)
        self._image_refs.append(btkimg)

        stack = tk.Frame(row, bg=bg_bubble)
        stack.pack(side="left", anchor="w")
        canvas = tk.Canvas(stack, width=card_w, height=card_h,
                           bg=bg_bubble, highlightthickness=0, bd=0)
        canvas.create_image(0, 0, anchor="nw", image=btkimg)

        # File icon tag.
        canvas.create_rectangle(14, 16, 46, 48, fill=accent, outline="",
                                tags=("file_icon",))
        canvas.create_text(30, 32, text=ext or "DOC",
                           fill=self.theme.get("bg_bubble"),
                           font=("Segoe UI", 8, "bold"),
                           tags=("file_icon",))

        # Filename (truncated) + message.
        display_name = filename if len(filename) <= 38 else filename[:35] + "..."
        canvas.create_text(56, 16, anchor="nw", text=display_name,
                           fill=text_primary, font=("Segoe UI", 10, "bold"),
                           tags=("file_open",))
        canvas.create_text(56, 34, anchor="nw", text=message,
                           fill=text_secondary, font=("Segoe UI", 9))

        if on_open_file:
            canvas.tag_bind("file_icon", "<Button-1>", lambda _e: on_open_file())
            canvas.tag_bind("file_icon", "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
            canvas.tag_bind("file_icon", "<Leave>", lambda _e: canvas.configure(cursor=""))
        if on_open_folder:
            canvas.tag_bind("file_open", "<Button-1>", lambda _e: on_open_folder())
            canvas.tag_bind("file_open", "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
            canvas.tag_bind("file_open", "<Leave>", lambda _e: canvas.configure(cursor=""))

        canvas.pack()
        self._row_widgets.append(row)
        self._last_role = "bot"
        self.after(20, self._scroll_to_bottom)

    def load_history(self, messages: list[dict]) -> None:
        self.clear()
        for m in messages:
            role = m.get("role", "")
            text = (m.get("text", "") or "").strip()
            if not text:
                continue
            ts = m.get("ts")
            if role in ("user", "Usuario"):
                self._add_message("user", text, ts, animate=False)
            elif role in ("bot", "Claudy"):
                self._add_message("bot", text, ts, animate=False)
            else:
                self._add_message("system", text, ts, animate=False)
        self.after(20, self._scroll_to_bottom)

    def show_typing(self) -> None:
        if self._typing_widget is not None:
            return
        bg_bubble = self.theme.get("bg_bubble", "#0f0e14")
        surface = self.theme.get("bg_bubble_border", "#2a2733")
        accent = self.theme.get("accent", "#c4b5fd")

        wrap = tk.Frame(self._inner, bg=bg_bubble)
        wrap.pack(fill="x", anchor="w", padx=12, pady=(6, 4))

        av_img = _get_bot_avatar(24, surface, accent)
        atkimg = ImageTk.PhotoImage(av_img)
        self._image_refs.append(atkimg)
        av = tk.Label(wrap, image=atkimg, bg=bg_bubble, bd=0)
        av.pack(side="left", padx=(0, 8))

        bubble = _bubble_asymmetric(46, 22, surface, self.theme.get("divider"), "bot")
        bimg = ImageTk.PhotoImage(bubble)
        self._image_refs.append(bimg)
        canvas = tk.Canvas(wrap, width=bubble.width, height=bubble.height,
                           bg=bg_bubble, highlightthickness=0, bd=0)
        canvas.create_image(0, 0, anchor="nw", image=bimg)
        cx0 = bubble.width // 2 - 9
        cy = bubble.height // 2
        dots = []
        for i in range(3):
            d = canvas.create_oval(cx0 + i * 9 - 2, cy - 2, cx0 + i * 9 + 2, cy + 2,
                                   fill=accent, outline="")
            dots.append(d)
        canvas.pack(side="left")
        self._typing_widget = wrap
        self._typing_dots = dots
        self._typing_canvas = canvas
        self._typing_dot_phase = 0
        self._animate_typing()
        self.after(20, self._scroll_to_bottom)

    def hide_typing(self) -> None:
        if self._typing_after:
            try:
                self.after_cancel(self._typing_after)
            except Exception:
                pass
            self._typing_after = None
        if self._typing_widget is not None:
            try:
                self._typing_widget.destroy()
            except Exception:
                pass
            self._typing_widget = None

    def add_options(self, options: list, on_select) -> None:
        """Render beautiful, interactive, clickable options for guided flows."""
        bg_bubble = self.theme.get("bg_bubble", "#0f0e14")
        bg_input = self.theme.get("bg_input", "#171520")
        accent = self.theme.get("accent", "#c4b5fd")
        text_primary = self.theme.get("text_primary", "#ece9f5")
        text_secondary = self.theme.get("text_secondary", "#8a8499")
        
        container = tk.Frame(self._inner, bg=bg_bubble)
        container.pack(fill="x", padx=44, pady=(2, 6))
        
        # We will keep track of option rows so we can disable them after a selection is made
        rows_to_disable = []
        
        def make_select_handler(opt_text, row_widget, labels):
            def handler(_e):
                # Disable all options in this container to prevent double click/re-select
                for r, lbls in rows_to_disable:
                    try:
                        r.unbind("<Button-1>")
                        r.unbind("<Enter>")
                        r.unbind("<Leave>")
                        r.configure(cursor="")
                        for l in lbls:
                            l.unbind("<Button-1>")
                            l.configure(cursor="")
                    except Exception:
                        pass
                # Trigger selection callback
                on_select(opt_text)
            return handler

        for opt in options:
            # opt is a tuple: (value_to_submit, title, description)
            val, title, desc = opt
            
            row = tk.Frame(
                container,
                bg=bg_input,
                bd=1,
                highlightthickness=1,
                highlightbackground=self.theme.get("bg_input_border", "#2a2733"),
                highlightcolor=accent,
                cursor="hand2"
            )
            row.pack(fill="x", pady=3)
            
            title_lbl = tk.Label(
                row,
                text=title,
                bg=bg_input,
                fg=text_primary,
                font=("Segoe UI", 9, "bold"),
                anchor="w",
                justify="left",
                cursor="hand2"
            )
            title_lbl.pack(fill="x", padx=(10, 10), pady=(6, 1))
            
            desc_lbl = tk.Label(
                row,
                text=f"({desc})",
                bg=bg_input,
                fg=text_secondary,
                font=("Segoe UI", 8, "italic"),
                anchor="w",
                justify="left",
                cursor="hand2",
                wraplength=self._width - 100
            )
            desc_lbl.pack(fill="x", padx=(10, 10), pady=(1, 6))
            
            # Hover bindings
            def make_hover(r=row, t=title_lbl, d=desc_lbl):
                def hover(_e):
                    r.configure(bg=accent, highlightbackground=accent)
                    t.configure(bg=accent, fg="#000000")
                    d.configure(bg=accent, fg="#2a2733")
                return hover
                
            def make_leave(r=row, t=title_lbl, d=desc_lbl):
                def leave(_e):
                    r.configure(bg=bg_input, highlightbackground=self.theme.get("bg_input_border", "#2a2733"))
                    t.configure(bg=bg_input, fg=text_primary)
                    d.configure(bg=bg_input, fg=text_secondary)
                return leave
            
            row.bind("<Enter>", make_hover())
            row.bind("<Leave>", make_leave())
            
            # Click bindings
            click_handler = make_select_handler(val, row, [title_lbl, desc_lbl])
            row.bind("<Button-1>", click_handler)
            title_lbl.bind("<Button-1>", click_handler)
            desc_lbl.bind("<Button-1>", click_handler)
            
            rows_to_disable.append((row, [title_lbl, desc_lbl]))
            
        self._row_widgets.append(container)
        self.after(20, self._scroll_to_bottom)

    def add_summary_card(self, topic, depth, images, references, style, language) -> None:
        """Render a premium visual summary card for report configurations."""
        bg_bubble = self.theme.get("bg_bubble", "#0f0e14")
        bg_input = self.theme.get("bg_input", "#171520")
        accent = self.theme.get("accent", "#c4b5fd")
        text_primary = self.theme.get("text_primary", "#ece9f5")
        text_secondary = self.theme.get("text_secondary", "#8a8499")
        
        container = tk.Frame(
            self._inner, 
            bg=bg_input, 
            bd=1, 
            highlightthickness=1,
            highlightbackground=self.theme.get("bg_input_border", "#2a2733")
        )
        container.pack(fill="x", padx=44, pady=(6, 6))
        
        # Header
        header = tk.Label(
            container,
            text="📋 CONFIGURACIÓN DEL INFORME",
            bg=bg_input,
            fg=accent,
            font=("Segoe UI", 9, "bold"),
            anchor="w"
        )
        header.pack(fill="x", padx=12, pady=(10, 6))
        
        # Divider line
        div = tk.Frame(container, height=1, bg=self.theme.get("bg_input_border", "#2a2733"))
        div.pack(fill="x", padx=12, pady=(0, 8))
        
        # Config grid items
        items = [
            ("Tema", topic),
            ("Alcance", depth),
            ("Imágenes", images),
            ("Referencias", references),
            ("Estilo", style),
            ("Idioma", language)
        ]
        
        grid_frame = tk.Frame(container, bg=bg_input)
        grid_frame.pack(fill="x", padx=12, pady=(0, 10))
        
        for label, val in items:
            row_frame = tk.Frame(grid_frame, bg=bg_input)
            row_frame.pack(fill="x", pady=2)
            
            lbl = tk.Label(
                row_frame,
                text=f"{label}:",
                bg=bg_input,
                fg=text_secondary,
                font=("Segoe UI", 9, "bold"),
                anchor="w",
                width=12
            )
            lbl.pack(side="left")
            
            val_lbl = tk.Label(
                row_frame,
                text=val,
                bg=bg_input,
                fg=text_primary,
                font=("Segoe UI", 9),
                anchor="w"
            )
            val_lbl.pack(side="left", fill="x", expand=True)
            
        self._row_widgets.append(container)
        self.after(20, self._scroll_to_bottom)

    def clear(self) -> None:
        self.hide_typing()
        for w in self._row_widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self._row_widgets.clear()
        self._messages.clear()
        self._image_refs.clear()
        self._last_role = None

    def apply_theme(self, theme: dict) -> None:
        self.theme = theme
        bg = theme.get("bg_bubble", "#0f0e14")
        self.configure(bg=bg)
        self.canvas.configure(bg=bg)
        self._inner.configure(bg=bg)
        saved = list(self._messages)
        self.clear()
        for m in saved:
            self._add_message(m["role"], m["text"], m["ts"], animate=False)

    # ------------ internals ------------
    def _on_inner_configure(self, _e=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, e) -> None:
        self.canvas.itemconfigure(self._inner_id, width=e.width)
        self._width = e.width

    def _on_wheel(self, e) -> None:
        try:
            self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except Exception:
            pass

    def _scroll_to_bottom(self) -> None:
        try:
            self._inner.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.canvas.yview_moveto(1.0)
            self.after(50, self._do_resilient_scroll)
        except tk.TclError:
            pass

    def _do_resilient_scroll(self) -> None:
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _animate_typing(self) -> None:
        if self._typing_widget is None:
            return
        try:
            canvas = self._typing_canvas
            accent = self.theme.get("accent", "#c4b5fd")
            muted = self.theme.get("text_secondary", "#8a8499")
            for i, d in enumerate(self._typing_dots):
                phase = (self._typing_dot_phase + i * 2) % 6
                color = accent if phase < 3 else muted
                canvas.itemconfigure(d, fill=color)
            self._typing_dot_phase = (self._typing_dot_phase + 1) % 6
        except Exception:
            return
        self._typing_after = self.after(180, self._animate_typing)

    def _format_ts(self, ts: float) -> str:
        try:
            dt = datetime.fromtimestamp(ts)
            now = datetime.now()
            if dt.date() == now.date():
                return dt.strftime("%H:%M")
            return dt.strftime("%d %b · %H:%M")
        except Exception:
            return ""

    def _add_message(
        self,
        role: str,
        text: str,
        ts: float | None,
        animate: bool = True,
    ) -> None:
        ts = ts or time.time()
        self._messages.append({"role": role, "text": text, "ts": ts})

        bg_bubble = self.theme.get("bg_bubble", "#0f0e14")
        surface = self.theme.get("bg_bubble_border", "#2a2733")
        accent = self.theme.get("accent", "#c4b5fd")
        text_primary = self.theme.get("text_primary", "#ece9f5")
        text_secondary = self.theme.get("text_secondary", "#8a8499")
        divider = self.theme.get("divider", "#1d1b26")

        # System: discreet centered note, no bubble.
        if role == "system":
            pad_top = 10 if self._last_role else 4
            row = tk.Frame(self._inner, bg=bg_bubble)
            row.pack(fill="x", padx=12, pady=(pad_top, 4))
            lbl = tk.Label(row, text=text, bg=bg_bubble, fg=text_secondary,
                           font=FONT_SYS, justify="center",
                           wraplength=self._width - 60)
            lbl.pack()
            self._row_widgets.append(row)
            self._last_role = "system"
            self.after(20, self._scroll_to_bottom)
            return

        is_user = role in ("user", "Usuario")
        # Spacing rhythm: variable based on role transitions.
        if self._last_role is None:
            pad_top = 6
        elif self._last_role == role:
            pad_top = 4
        else:
            pad_top = 10

        # Color choices — Restrained.
        if is_user:
            fill = accent
            text_color = "#0f0e14"  # high contrast against accent
            av_char = "T"
            av_fill = accent
            av_fg = "#0f0e14"
            pad_x, pad_y = 14, 10
            avatar_radius = "circle"
        else:
            fill = surface
            text_color = text_primary
            av_char = "C"
            av_fill = self.theme.get("accent_dim", "#3a3349")
            av_fg = accent
            pad_x, pad_y = 16, 12
            avatar_radius = "square"

        row = tk.Frame(self._inner, bg=bg_bubble)
        row.pack(fill="x", padx=12, pady=(pad_top, 2))

        if is_user:
            av_img = _avatar_monogram(24, av_fill, av_fg, av_char, "user")
        else:
            av_img = _get_bot_avatar(24, av_fill, av_fg)
        atkimg = ImageTk.PhotoImage(av_img)
        self._image_refs.append(atkimg)
        av = tk.Label(row, image=atkimg, bg=bg_bubble, bd=0)
        if is_user:
            av.pack(side="right", padx=(8, 0), anchor="ne")
        else:
            av.pack(side="left", padx=(0, 8), anchor="nw")

        # Measure text.
        max_text_width = max(140, self._width - 110)
        sizer = tk.Label(self, text=text, font=FONT_BODY, wraplength=max_text_width,
                         justify="left", bg=bg_bubble, fg=text_color,
                         padx=pad_x, pady=pad_y)
        sizer.update_idletasks()
        tw = sizer.winfo_reqwidth()
        th = sizer.winfo_reqheight()
        sizer.destroy()

        bubble_w = min(max_text_width + pad_x * 2, max(tw, 80))
        bubble_h = th + 4

        bubble_img = _bubble_asymmetric(bubble_w, bubble_h, fill,
                                        divider if not is_user else None,
                                        "user" if is_user else "bot")
        btkimg = ImageTk.PhotoImage(bubble_img)
        self._image_refs.append(btkimg)

        stack = tk.Frame(row, bg=bg_bubble)
        stack.pack(side="right" if is_user else "left", anchor="e" if is_user else "w")

        canvas = tk.Canvas(stack, width=bubble_img.width, height=bubble_img.height,
                           bg=bg_bubble, highlightthickness=0, bd=0)
        img_id = canvas.create_image(0, 0, anchor="nw", image=btkimg)
        canvas.create_text(
            pad_x, pad_y - 2, anchor="nw",
            text=text, fill=text_color, font=FONT_BODY,
            width=bubble_w - pad_x * 2,
        )
        canvas.pack()

        ts_text = self._format_ts(ts)
        ts_lbl = tk.Label(stack, text=ts_text, bg=bg_bubble, fg=text_secondary,
                          font=FONT_TS)
        ts_lbl.pack(anchor="e" if is_user else "w", padx=2, pady=(2, 0))

        # Copy to clipboard double-click and right-click functionality
        def _copy_message(event=None):
            try:
                self.clipboard_clear()
                self.clipboard_append(text)
                orig_fg = ts_lbl.cget("fg")
                ts_lbl.configure(text="¡Copiado! ✓", fg=accent)
                def _restore():
                    try:
                        ts_lbl.configure(text=ts_text, fg=orig_fg)
                    except Exception:
                        pass
                self.after(1500, _restore)
            except Exception:
                pass

        canvas.configure(cursor="hand2")
        canvas.bind("<Double-Button-1>", _copy_message)

        # Right-click context menu
        menu = tk.Menu(self, tearoff=0, bg=bg_bubble, fg=text_primary,
                       activebackground=accent, activeforeground="#0f0e14", bd=0)
        menu.add_command(label="Copiar mensaje", command=_copy_message)

        def _show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            except Exception:
                pass

        canvas.bind("<Button-3>", _show_menu)

        self._row_widgets.append(row)
        self._last_role = role
        self.after(20, self._scroll_to_bottom)

        if animate:
            self._animate_in(stack, canvas, img_id, bubble_img)

    def _animate_in(
        self,
        stack: tk.Frame,
        canvas: tk.Canvas,
        img_id: int,
        base_img: Image.Image,
    ) -> None:
        """Slide-up 8px + fade, 180ms ease-out-expo, 6 frames."""
        steps = 6
        total_ms = 180
        frame_ms = total_ms // steps

        # Pre-bake faded variants for the bubble.
        frames: list[ImageTk.PhotoImage] = []
        for i in range(1, steps + 1):
            t = _ease_out_expo(i / steps)
            faded = base_img.copy()
            a = faded.split()[-1]
            a = a.point(lambda v, al=t: int(v * al))
            faded.putalpha(a)
            frames.append(ImageTk.PhotoImage(faded))
        self._image_refs.extend(frames)

        # Slide via tk.Frame.pack_configure padding tweak (avoids reflow).
        idx = {"i": 0}
        start_off = 8

        def step():
            if idx["i"] >= steps:
                try:
                    stack.pack_configure(pady=(0, 0))
                except Exception:
                    pass
                return
            t = _ease_out_expo((idx["i"] + 1) / steps)
            try:
                canvas.itemconfigure(img_id, image=frames[idx["i"]])
                # Slide effect: shift the canvas content downward via padding shrink.
                off = int(start_off * (1 - t))
                stack.pack_configure(pady=(off, 0))
            except tk.TclError:
                return
            idx["i"] += 1
            self.after(frame_ms, step)

        step()
