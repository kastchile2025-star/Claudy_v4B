"""Claudy ui.bubbles — Burbujas tkinter del pet (refactor v5).

Dibujo y ciclo de vida de las burbujas legacy que flotan junto al sprite:
globos de pensamiento, burbuja de bienvenida, estilos por tema (glass,
vintage, minimal, terminal, editorial), posicionamiento respecto al área
útil de pantalla y auto-ocultado.

El chat principal (webview con chat.html) NO vive aquí: su lógica sigue en
pet.py (show_chat_bubble) y el puente JS en ui/webview_api.py.

Se usa como mixin: ClawdPet hereda de BubblesMixin. Accede al estado del
módulo pet a través de puentes: _ui_colors() (tema activo), _work_area(),
_transparent_color(), _bubble_mini_size().
"""
import math
import random
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageTk


class BubblesMixin:
    def _toggle_bubble_from_hotkey(self):
        if self.bubble_win and self.bubble_interactive and not self.bubble_minimized:
            try:
                mf = getattr(self, "_minimize_bubble", None)
                if mf:
                    mf()
                    return
            except Exception:
                pass
            self.hide_bubble()
            return
        if self.bubble_minimized and hasattr(self, "_expand_bubble"):
            self._expand_bubble()
            return
        self.show_chat_bubble()

    def _show_welcome_bubble_when_ready(self, _attempts=0):
        """Wait for the webview HTML to be fully loaded before showing the welcome chat.
        Retries every 250ms for up to ~8 seconds, then opens anyway (Tkinter fallback)."""
        MAX_ATTEMPTS = 32  # 32 * 250ms = 8 seconds max wait
        if not self._webview_ready and _attempts < MAX_ATTEMPTS:
            self.after(250, lambda: self._show_welcome_bubble_when_ready(_attempts + 1))
            return
        self._show_welcome_bubble()

    def _show_welcome_bubble(self):
        saludos = [
            "Hola, soy Claudy, tu asistente personal. ¿En qué andas hoy?",
            "Buenas, soy Claudy. ¿Qué tema te tiene la cabeza ocupada hoy?",
            "Hey, soy Claudy. ¿Hay algo en lo que te pueda dar una mano ahora?",
            "Hola, Claudy aquí. ¿Qué pregunta llevas dando vueltas hoy?",
            "Soy Claudy, tu copiloto. ¿Qué quieres resolver primero?",
        ]
        try:
            self.show_chat_bubble(text=random.choice(saludos))
        except Exception:
            pass

    def hide_bubble(self):
        self._cancel_idle_timer()
        self._stop_zzz_animation()
        if self.bubble_win:
            try:
                self.bubble_win.destroy()
            except Exception:
                pass
            self.bubble_win = None
        if self.webview_win:
            try:
                # Move off-screen instead of hide() to keep WebView2 rendered
                self.webview_win.move(-9999, -9999)
            except Exception:
                pass
        # Also close the Tkinter history window if it is open
        if self.history_win is not None:
            try:
                self.history_win.destroy()
            except Exception:
                pass
            self.history_win = None
        self._webview_visible = False
        self._bubble_hidden_at = time.time()
        self._bubble_canvas = None
        self._chat_view = None
        self.bubble_interactive = False
        self.bubble_minimized = False
        # Restore Claudy topmost now that the webview is hidden
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
            
        # Restore pre-chat pet position if saved
        if hasattr(self, "_pre_chat_pet_x") and self._pre_chat_pet_x is not None:
            try:
                self.geometry(f"+{self._pre_chat_pet_x}+{self._pre_chat_pet_y}")
                self.base_x = self._pre_chat_pet_x
                self.base_y = self._pre_chat_pet_y
            except Exception:
                pass
            self._pre_chat_pet_x = None
            self._pre_chat_pet_y = None

    def _on_bubble_focus_out(self, _event=None):
        # Delay check so focus can settle on the new widget
        self.after(50, self._check_bubble_focus)

    def bubble_position(self, width, height):
        margin = 18      # screen-edge breathing room
        pet_gap = 4      # gap between Claudy and the bubble/chat
        pet_x = self.base_x
        pet_y = self.base_y
        pet_w = self.width
        pet_h = self.height

        if width >= 500:
            # Large chat window: position ABOVE the pet so Claudy stays visible
            # below it. Anchor horizontally to the pet's side: if pet is near the
            # right edge, align chat's right edge with pet's right edge (and vice
            # versa). Fall back to side-by-side only when the chat is taller than
            # the available vertical space above the pet.
            available_above = pet_y - self._work_area().top - pet_gap
            if height <= available_above:
                # Anchor to whichever side the pet is closer to, so the chat
                # doesn't get clamped off-screen on the opposite edge.
                space_left = pet_x - self._work_area().left
                space_right = self._work_area().right - (pet_x + pet_w)
                if space_right <= space_left:
                    # Pet is near right edge → align chat's right edge to pet's right edge
                    x = (pet_x + pet_w) - width
                else:
                    # Pet near left edge → align chat's left edge to pet's left edge
                    x = pet_x
                y = pet_y - height - pet_gap
            else:
                # Chat doesn't fit above → fall back to side-by-side
                space_left = pet_x - self._work_area().left
                space_right = self._work_area().right - (pet_x + pet_w)
                if space_left >= space_right:
                    x = pet_x - width - pet_gap
                else:
                    x = pet_x + pet_w + pet_gap
                y = pet_y + pet_h - height
        else:
            # Position small thought bubble ABOVE Claudy, centered horizontally
            x = pet_x + pet_w // 2 - width // 2
            y = pet_y - height - pet_gap

            # If it doesn't fit above, try beside (left, then right)
            if y < self._work_area().top + margin:
                y = self._work_area().top + margin
                left_x = pet_x - width - pet_gap
                right_x = pet_x + pet_w + pet_gap
                if left_x >= self._work_area().left + margin:
                    x = left_x
                elif right_x + width <= self._work_area().right - margin:
                    x = right_x

        # Clamp to screen edges
        x = max(self._work_area().left + margin, min(x, self._work_area().right - width - margin))
        y = max(self._work_area().top + margin, min(y, self._work_area().bottom - height - margin))
        return x, y

    def minimized_position(self, size):
        """Position for the minimized Zzz bubble: floats just above pet's head."""
        pet_x = self.base_x
        pet_y = self.base_y
        pet_w = self.width
        # Center horizontally on pet, closer to its head
        x = pet_x + pet_w // 2 - size // 2
        y = pet_y - size + 42
        return x, y

    def _sync_minimized_bubble(self):
        """If chat is minimized, keep the Zzz bubble glued to the pet."""
        if not (self.bubble_win and self.bubble_minimized):
            return
        try:
            sz = self._bubble_mini_size()
            cx, cy = self.minimized_position(sz)
            self.bubble_win.geometry(f"{sz}x{sz}+{cx}+{cy}")
        except tk.TclError:
            pass

    def _rounded_bubble_path(self, w, h, r, tail_h=10, tail_w=14):
        """Return a list of (x,y) points for a speech-bubble polygon."""
        points = []
        # Top edge.
        points += self._arc_points(r, r, r, 180, 270)
        points += self._arc_points(w - r, r, r, 270, 360)
        # Right edge.
        points += self._arc_points(w - r, h - r - tail_h, r, 0, 45)
        # Tail.
        cx = w // 2
        points.append((cx + tail_w // 2, h - tail_h))
        points.append((cx, h))
        points.append((cx - tail_w // 2, h - tail_h))
        # Bottom-left rounding.
        points += self._arc_points(r, h - r - tail_h, r, 135, 180)
        return points

    @staticmethod
    def _arc_points(cx, cy, r, start_deg, end_deg, steps=8):
        pts = []
        for i in range(steps + 1):
            ang = math.radians(start_deg + (end_deg - start_deg) * i / steps)
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        return pts

    def _draw_bubble(self, canvas, w, h, bg, border):
        style = THEME.get("style", "glass")
        if style == "terminal":
            self._draw_bubble_terminal(canvas, w, h, bg, border)
        elif style == "editorial":
            self._draw_bubble_editorial(canvas, w, h, bg, border)
        elif style == "minimal":
            self._draw_bubble_minimal(canvas, w, h, bg, border)
        elif style == "vintage":
            self._draw_bubble_vintage(canvas, w, h, bg, border)
        else:
            self._draw_bubble_glass(canvas, w, h, bg, border)

    def _draw_bubble_vintage(self, canvas, w, h, bg, border):
        """Parchment paper background with grid lines and leather frame."""
        try:
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            radius = 16

            # 1. Leather/wood outer frame (dark brown rounded rect)
            frame_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            frame_mask = Image.new("L", (w, h), 0)
            ImageDraw.Draw(frame_mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
            frame_fill = Image.new("RGBA", (w, h), (61, 52, 41, 255))  # #3d3429
            frame_fill.putalpha(frame_mask)
            img = Image.alpha_composite(img, frame_fill)

            # 2. Inner parchment paper area (inset 8px)
            inset = 8
            paper_w, paper_h = w - inset * 2, h - inset * 2
            paper = Image.new("RGBA", (paper_w, paper_h), (0, 0, 0, 0))
            paper_mask = Image.new("L", (paper_w, paper_h), 0)
            ImageDraw.Draw(paper_mask).rounded_rectangle(
                (0, 0, paper_w - 1, paper_h - 1), radius=radius - 4, fill=255)
            # Paper color with subtle noise
            paper_base = Image.new("RGBA", (paper_w, paper_h), (212, 197, 160, 255))  # #d4c5a0
            paper_base.putalpha(paper_mask)
            img.paste(paper_base, (inset, inset), paper_base)

            # 3. Grid lines on paper
            draw = ImageDraw.Draw(img)
            grid_color = (204, 190, 156, 255)  # very faint
            grid_spacing = 20
            for gx in range(inset + grid_spacing, w - inset, grid_spacing):
                draw.line([(gx, inset + 4), (gx, h - inset - 4)], fill=grid_color, width=1)
            for gy in range(inset + grid_spacing, h - inset, grid_spacing):
                draw.line([(inset + 4, gy), (w - inset - 4, gy)], fill=grid_color, width=1)

            # 4. Leather frame border (2px)
            draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius,
                                   outline=(90, 78, 61, 255), width=2)
            # Inner border on paper edge
            draw.rounded_rectangle((inset - 1, inset - 1, w - inset, h - inset),
                                   radius=radius - 4, outline=(160, 145, 115, 255), width=1)

            # 5. Corner studs (small circles at corners)
            stud_r = 4
            stud_color = (120, 105, 82, 200)
            for sx, sy in [(14, 14), (w - 15, 14), (14, h - 15), (w - 15, h - 15)]:
                draw.ellipse((sx - stud_r, sy - stud_r, sx + stud_r, sy + stud_r),
                             fill=stud_color, outline=(80, 70, 55, 255))

            tk_img = ImageTk.PhotoImage(img)
            self._bg_photo_image_ref = tk_img
            canvas.create_image(0, 0, anchor="nw", image=tk_img, tags=("bubble_bg",))
        except Exception:
            canvas.create_rectangle(0, 0, w, h, fill="#d4c5a0", outline="#5a4e3d", width=2,
                                    tags=("bubble_bg",))

    def _draw_bubble_minimal(self, canvas, w, h, bg, border):
        """Matte solid background with clean 1px border — Obsidian Clean theme."""
        try:
            bg_rgb = (10, 10, 12)  # #0a0a0c
            border_rgb = (39, 39, 42)  # #27272a
            radius = 24
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            mask = Image.new("L", (w, h), 0)
            mask_d = ImageDraw.Draw(mask)
            mask_d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
            fill_layer = Image.new("RGBA", (w, h), (*bg_rgb, 255))
            fill_layer.putalpha(mask)
            img = Image.alpha_composite(img, fill_layer)
            draw_on = ImageDraw.Draw(img)
            draw_on.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius,
                                      outline=(*border_rgb, 255), width=1)
            tk_img = ImageTk.PhotoImage(img)
            self._bg_photo_image_ref = tk_img
            canvas.create_image(0, 0, anchor="nw", image=tk_img, tags=("bubble_bg",))
        except Exception:
            canvas.create_rectangle(0, 0, w, h, fill=bg, outline=border, width=1,
                                    tags=("bubble_bg",))

    def _draw_bubble_glass(self, canvas, w, h, bg, border):
        # Premium neon shell: deep gradient, vignette, dotted texture and soft dual glow.
        try:
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)

            top_rgb = _hex_to_rgb("#07142d")
            bottom_rgb = _hex_to_rgb("#070814")
            accent_left = _hex_to_rgb(THEME.get("accent_glow", "#58c7ff"))
            accent_right = _hex_to_rgb(THEME.get("accent", "#c02dff"))

            for y in range(h):
                t = y / h
                r = int(top_rgb[0] + (bottom_rgb[0] - top_rgb[0]) * t)
                g = int(top_rgb[1] + (bottom_rgb[1] - top_rgb[1]) * t)
                b = int(top_rgb[2] + (bottom_rgb[2] - top_rgb[2]) * t)
                d.line([(0, y), (w, y)], fill=(r, g, b, 255))

            for i in range(0, w, 12):
                for j in range(0, h, 12):
                    blend = i / max(1, w - 1)
                    dot_rgb = (
                        int(accent_left[0] * (1 - blend) + accent_right[0] * blend),
                        int(accent_left[1] * (1 - blend) + accent_right[1] * blend),
                        int(accent_left[2] * (1 - blend) + accent_right[2] * blend),
                    )
                    d.ellipse((i, j, i + 1, j + 1), fill=(*dot_rgb, 28))

            vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            vd = ImageDraw.Draw(vignette)
            vd.ellipse((-w * 0.25, -h * 0.1, w * 0.55, h * 0.7), fill=(*accent_left, 48))
            vd.ellipse((w * 0.45, h * 0.05, w * 1.15, h * 0.95), fill=(*accent_right, 42))
            vignette = vignette.filter(ImageFilter.GaussianBlur(52))
            img = Image.alpha_composite(img, vignette)

            mask = Image.new("L", (w, h), 0)
            mask_d = ImageDraw.Draw(mask)
            radius = 34
            mask_d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
            img.putalpha(mask)

            glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.rounded_rectangle((6, 6, w - 7, h - 7), radius=radius,
                                 outline=(*accent_left, 160), width=4)
            gd.rounded_rectangle((10, 10, w - 11, h - 11), radius=radius - 4,
                                 outline=(*accent_right, 140), width=3)
            glow = glow.filter(ImageFilter.GaussianBlur(10))
            img = Image.alpha_composite(glow, img)

            draw_on_img = ImageDraw.Draw(img)
            border_rgb = _hex_to_rgb(border)
            draw_on_img.rounded_rectangle((6, 6, w - 7, h - 7), radius=radius,
                                          outline=(*border_rgb, 255), width=2)
            draw_on_img.rounded_rectangle((14, 14, w - 15, h - 15), radius=26,
                                          outline=(*_hex_to_rgb(THEME.get("divider", "#4f2cc8")), 135), width=1)

            tk_img = ImageTk.PhotoImage(img)
            self._bg_photo_image_ref = tk_img
            canvas.create_image(0, 0, anchor="nw", image=tk_img, tags=("bubble_bg",))
        except Exception:
            outer = self._rounded_bubble_path(w, h, 22, tail_h=0, tail_w=0)
            canvas.create_polygon(outer, smooth=True, fill=bg, outline=border, width=2,
                                  tags=("bubble_bg",))

    def _draw_bubble_terminal(self, canvas, w, h, bg, border):
        # Sharp rectangle, scanlines, double border, CRT corner glow
        canvas.create_rectangle(0, 0, w, h, fill=bg, outline="", tags=("bubble_bg",))
        # Scanlines — horizontal faint lines every 3px
        for y in range(0, h, 3):
            canvas.create_line(0, y, w, y, fill=self._ui_colors()["divider"], width=1, tags=("bubble_bg",))
        # Double border — outer thin, inner accent
        canvas.create_rectangle(0, 0, w - 1, h - 1, outline=border, width=1, tags=("bubble_bg",))
        canvas.create_rectangle(4, 4, w - 5, h - 5, outline=self._ui_colors()["accent"], width=1, tags=("bubble_bg",))
        # Tail/pointer at bottom-center
        cx = w // 2
        canvas.create_polygon(
            [cx - 8, h - 1, cx, h + 8, cx + 8, h - 1],
            fill=bg, outline=self._ui_colors()["accent"], width=1, tags=("bubble_bg",)
        )
        # Corner brackets (CRT corners)
        for (x0, y0, x1, y1, x2, y2) in [
            (8, 8, 8, 16, 16, 8),               # TL
            (w - 9, 8, w - 9, 16, w - 17, 8),    # TR
            (8, h - 9, 8, h - 17, 16, h - 9),    # BL
            (w - 9, h - 9, w - 9, h - 17, w - 17, h - 9),  # BR
        ]:
            canvas.create_line(x0, y0, x1, y1, fill=self._ui_colors()["accent_glow"], width=2, tags=("bubble_bg",))
            canvas.create_line(x0, y0, x2, y2, fill=self._ui_colors()["accent_glow"], width=2, tags=("bubble_bg",))

    def _draw_bubble_editorial(self, canvas, w, h, bg, border):
        # Paper-like: cream background, single hairline border, no shadow drama
        canvas.create_rectangle(0, 0, w, h, fill=bg, outline="", tags=("bubble_bg",))
        # A single accent line on top (editorial bar)
        canvas.create_rectangle(0, 0, w, 3, fill=self._ui_colors()["accent"], outline="", tags=("bubble_bg",))
        # Hairline border
        canvas.create_rectangle(0, 0, w - 1, h - 1, outline=border, width=1, tags=("bubble_bg",))
        # Tail
        cx = w // 2
        canvas.create_polygon(
            [cx - 7, h - 1, cx, h + 7, cx + 7, h - 1],
            fill=bg, outline=border, width=1, tags=("bubble_bg",)
        )

    def show_thought(self, text):
        self.hide_bubble()
        self.bubble_interactive = False

        bub = tk.Toplevel(self)
        bub.overrideredirect(True)
        bub.attributes("-topmost", True)
        bub.configure(bg=self._transparent_color())
        bub.wm_attributes("-transparentcolor", self._transparent_color())

        # Measure text to auto-size.
        temp = tk.Label(bub, text=text, font=("Bahnschrift SemiBold", 10), wraplength=220)
        temp.update_idletasks()
        tw, th = temp.winfo_reqwidth(), temp.winfo_reqheight()
        temp.destroy()

        pad_x, pad_y = 28, 20
        width = max(160, tw + pad_x * 2)
        height = max(70, th + pad_y * 2 + 10)

        canvas = tk.Canvas(bub, width=width, height=height, bg=self._transparent_color(), highlightthickness=0, bd=0)
        canvas.pack()

        try:
            img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.rounded_rectangle((4, 4, width - 5, height - 5), radius=22,
                                 outline=(192, 45, 255, 150), width=4)
            glow = glow.filter(ImageFilter.GaussianBlur(7))
            img = Image.alpha_composite(img, glow)
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((8, 8, width - 9, height - 9), radius=20,
                                fill=(5, 9, 29, 245), outline=(88, 199, 255, 190), width=1)
            d.ellipse((18, height - 16, 28, height - 6), fill=(5, 9, 29, 230),
                      outline=(88, 199, 255, 160), width=1)
            # Pre-composite onto magenta background so semi-transparent pixels
            # don't bleed pink through Tkinter's -transparentcolor.
            bg_layer = Image.new("RGBA", (width, height), (255, 0, 255, 255))
            composited = Image.alpha_composite(bg_layer, img)
            # Convert to RGB (drop alpha) since we're using chroma-key transparency
            final = composited.convert("RGB")
            # Snap near-magenta pixels to exact #FF00FF so chroma-key works
            px = final.load()
            for _y in range(final.height):
                for _x in range(final.width):
                    r, g, b = px[_x, _y]
                    if r > 200 and g < 55 and b > 200:
                        px[_x, _y] = (255, 0, 255)
            tk_img = ImageTk.PhotoImage(final)
            self._thought_bg_ref = tk_img
            canvas.create_image(0, 0, anchor="nw", image=tk_img)
        except Exception:
            canvas.create_polygon(
                self._rounded_bubble_path(width, height, 22, tail_h=0, tail_w=0),
                smooth=True, fill="#05091d", outline="#58c7ff", width=1,
            )

        canvas.create_text(
            width // 2, height // 2 - 4,
            text=text, width=width - pad_x * 2,
            fill="#f7f9ff",
            font=("Bahnschrift SemiBold", 10),
            justify="center",
        )

        cx, cy = self.bubble_position(width, height)
        bub.geometry(f"{width}x{height}+{cx}+{cy}")
        self.bubble_win = bub

    def show_pet_speech_bubble(self, text, duration=5000, on_click=None):
        """Show a premium floating speech bubble directly above the pet's head.

        If on_click is given, clicking the bubble runs it (e.g. reopen the chat
        to show the finished work).
        """
        if hasattr(self, "_pet_speech_win") and self._pet_speech_win:
            try:
                self._pet_speech_win.destroy()
            except Exception:
                pass
            self._pet_speech_win = None
            
        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        
        try:
            win.wm_attributes("-alpha", 0.0)
        except Exception:
            pass
            
        win.configure(bg=self._transparent_color())
        win.wm_attributes("-transparentcolor", self._transparent_color())

        wraplength = 210
        temp = tk.Label(win, text=text, font=("Bahnschrift SemiBold", 9), wraplength=wraplength)
        temp.update_idletasks()
        bw = max(180, temp.winfo_reqwidth() + 34)
        bh = max(58, temp.winfo_reqheight() + 28)
        temp.destroy()

        canvas = tk.Canvas(win, width=bw, height=bh, bg=self._transparent_color(), highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        try:
            img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            glow = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.rounded_rectangle((4, 4, bw - 5, bh - 5), radius=20,
                                 outline=(88, 199, 255, 145), width=4)
            gd.rounded_rectangle((8, 8, bw - 9, bh - 9), radius=18,
                                 outline=(192, 45, 255, 130), width=3)
            glow = glow.filter(ImageFilter.GaussianBlur(7))
            img = Image.alpha_composite(img, glow)
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((8, 8, bw - 9, bh - 9), radius=18,
                                fill=(5, 9, 29, 246), outline=(88, 199, 255, 180), width=1)
            d.polygon([(bw // 2 - 9, bh - 10), (bw // 2, bh - 1), (bw // 2 + 9, bh - 10)],
                      fill=(5, 9, 29, 246), outline=(88, 199, 255, 130))
            # Pre-composite onto magenta background so semi-transparent pixels
            # don't bleed pink through Tkinter's -transparentcolor.
            bg_layer = Image.new("RGBA", (bw, bh), (255, 0, 255, 255))
            composited = Image.alpha_composite(bg_layer, img)
            final = composited.convert("RGB")
            # Snap near-magenta pixels to exact #FF00FF so chroma-key works
            px = final.load()
            for _y in range(final.height):
                for _x in range(final.width):
                    r, g, b = px[_x, _y]
                    if r > 200 and g < 55 and b > 200:
                        px[_x, _y] = (255, 0, 255)
            tk_img = ImageTk.PhotoImage(final)
            win._speech_bg_ref = tk_img
            canvas.create_image(0, 0, anchor="nw", image=tk_img)
        except Exception:
            canvas.create_rectangle(0, 0, bw, bh, fill="#05091d", outline="#58c7ff", width=1)

        canvas.create_text(
            bw // 2, bh // 2 - 2,
            text=text,
            width=wraplength,
            fill="#f7f9ff",
            font=("Bahnschrift SemiBold", 9),
            justify="center",
        )
        
        win.update_idletasks()
        
        px = self.winfo_x()
        py = self.winfo_y()
        pw = self.winfo_width()
        
        cx = px + pw // 2
        bx = cx - bw // 2
        by = py - bh - 10
        
        win.geometry(f"{bw}x{bh}+{bx}+{by}")
        self._pet_speech_win = win

        # Click en la burbuja → ejecuta el callback (p.ej. reabrir el chat).
        if on_click is not None:
            def _do_click(_e=None):
                try:
                    win.destroy()
                except Exception:
                    pass
                if getattr(self, "_pet_speech_win", None) == win:
                    self._pet_speech_win = None
                try:
                    on_click()
                except Exception:
                    pass
            canvas.configure(cursor="hand2")
            canvas.bind("<Button-1>", _do_click)

        def fade_in(alpha=0.0, current_y=by+10):
            if not win.winfo_exists():
                return
            if alpha < 1.0:
                alpha += 0.15
                current_y -= 1.5
                win.attributes("-alpha", min(1.0, alpha))
                win.geometry(f"+{bx}+{int(current_y)}")
                self.after(20, lambda: fade_in(alpha, current_y))
            else:
                win.attributes("-alpha", 1.0)
                win.geometry(f"+{bx}+{by}")
                if duration is not None:
                    self.after(duration, lambda: fade_out())
                
        def fade_out(alpha=1.0):
            if not win.winfo_exists():
                return
            if alpha > 0.0:
                alpha -= 0.15
                win.attributes("-alpha", max(0.0, alpha))
                self.after(20, lambda: fade_out(alpha))
            else:
                try:
                    win.destroy()
                except Exception:
                    pass
                if getattr(self, "_pet_speech_win", None) == win:
                    self._pet_speech_win = None
                    
                # If minimized and no longer working, restore Zzz sleep visual elements
                if getattr(self, "bubble_minimized", False) and not getattr(self, "_milestone_active", False):
                    canvas = getattr(self, "_canvas", None)
                    idle_items = getattr(self, "_idle_items", None)
                    if canvas and idle_items:
                        for item in idle_items:
                            try:
                                canvas.itemconfigure(item, state="normal")
                            except Exception:
                                pass
                        self._start_zzz_animation()
                    
        fade_in()

    def _auto_hide_bubble(self):
        """Hide the bubble after 60s of inactivity."""
        if self.bubble_win and self.bubble_minimized:
            self.hide_bubble()
        self._idle_hide_timer = None

