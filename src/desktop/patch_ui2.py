"""
Claudy UI Improvements Patch
Applies all visual improvements to pet.py and chat_view.py:
1. Input text color fix (visible fg)
2. Header icon improvements (bigger icons, glow border)
3. ENVIAR button glow animation
4. Nocturne as default theme
"""
import os
import re

PET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pet.py')
CHAT_VIEW_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chat_view.py')

# ─────────────────────────────────────────────────────────────────────────
# 1. pet.py patches
# ─────────────────────────────────────────────────────────────────────────
with open(PET_PATH, 'r', encoding='utf-8') as f:
    pet = f.read()

# 1a. Set default theme back to glass (Nocturne, index 1)
pet = pet.replace(
    "# Active theme — start with vintage (Pergamino)\n_THEME_KEYS = list(THEMES.keys())\n_active_theme_idx = 4",
    "# Active theme — start with glass (Nocturne)\n_THEME_KEYS = list(THEMES.keys())\n_active_theme_idx = 1"
)
# fallback: also try the "start with glass" comment version
pet = pet.replace(
    "# Active theme — start with glass\n_THEME_KEYS = list(THEMES.keys())\n_active_theme_idx = 4",
    "# Active theme — start with glass (Nocturne)\n_THEME_KEYS = list(THEMES.keys())\n_active_theme_idx = 1"
)

# 1b. Fix hardcoded input entry color
old_entry = '''        entry = tk.Text(
            bub,
            bg="#071026", fg="#f7f9ff",'''
new_entry = '''        entry = tk.Text(
            bub,
            bg="#071026", fg="#e8eeff",'''
pet = pet.replace(old_entry, new_entry)

# 1c. Fix placeholder color to be more visible (light blue-grey)
pet = pet.replace('entry.config(fg="#9fb2ff")', 'entry.config(fg="#5a78cc")')
pet = pet.replace('entry.config(fg="#f7f9ff")', 'entry.config(fg="#e8eeff")')
pet = pet.replace('''                entry.config(fg="#9fb2ff")''', '                entry.config(fg="#5a78cc")')

# 1d. Improve header icon buttons: bigger icons + glowing border
old_history = '''        history_btn = tk.Label(
            bub, text="\\u2630", bg=chat_theme["button_bg"], fg=chat_theme["button_fg"],
            font=("Segoe UI Symbol", 11), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["bg_input_border"], highlightthickness=1,
        )'''
new_history = '''        history_btn = tk.Label(
            bub, text="\\u2630", bg=chat_theme["button_bg"], fg=chat_theme["accent_glow"],
            font=("Segoe UI Symbol", 13), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["accent"], highlightthickness=2,
        )'''
pet = pet.replace(old_history, new_history)

old_folder = '''        folder_btn = tk.Label(
            bub, text="\\U0001F4C1", bg=chat_theme["button_bg"], fg=chat_theme["button_fg"],
            font=("Segoe UI Emoji", 10), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["bg_input_border"], highlightthickness=1,
        )'''
new_folder = '''        folder_btn = tk.Label(
            bub, text="\\U0001F4C1", bg=chat_theme["button_bg"], fg=chat_theme["accent_glow"],
            font=("Segoe UI Emoji", 12), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["accent"], highlightthickness=2,
        )'''
pet = pet.replace(old_folder, new_folder)

old_open_loc = '''        open_location_btn = tk.Label(
            bub, text="\\U0001F4C2", bg=chat_theme["button_bg"], fg=chat_theme["button_fg"],
            font=("Segoe UI Emoji", 10), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["bg_input_border"], highlightthickness=1,
        )'''
new_open_loc = '''        open_location_btn = tk.Label(
            bub, text="\\U0001F4C2", bg=chat_theme["button_bg"], fg=chat_theme["accent_glow"],
            font=("Segoe UI Emoji", 12), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["accent"], highlightthickness=2,
        )'''
pet = pet.replace(old_open_loc, new_open_loc)

old_clear = '''        clear_btn = tk.Label(
            bub, text="\\U0001F9F9", bg=chat_theme["button_bg"], fg=chat_theme["button_fg"],
            font=("Segoe UI Emoji", 10), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["bg_input_border"], highlightthickness=1,
        )'''
new_clear = '''        clear_btn = tk.Label(
            bub, text="\\U0001F9F9", bg=chat_theme["button_bg"], fg=chat_theme["accent_glow"],
            font=("Segoe UI Emoji", 12), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["accent"], highlightthickness=2,
        )'''
pet = pet.replace(old_clear, new_clear)

# 1e. Minimize button brighter
old_min = '''        minimize_btn = tk.Label(
            bub, text="\\u2212", bg=chat_theme["header_bg"], fg="#ffffff",
            font=("Bahnschrift SemiBold", 12), cursor="hand2",
            padx=6, pady=3, relief="flat", bd=0,
        )'''
new_min = '''        minimize_btn = tk.Label(
            bub, text="\\u2212", bg=chat_theme["button_bg"], fg=chat_theme["accent_glow"],
            font=("Bahnschrift SemiBold", 14), cursor="hand2",
            padx=6, pady=3, relief="flat", bd=0,
            highlightbackground=chat_theme["accent"], highlightthickness=2,
        )'''
pet = pet.replace(old_min, new_min)

# 1f. ENVIAR button: purple gradient with cyan border + pulse animation
old_send = '''        _btn_bg = "c02dff"
        _btn_fg = "#ffffff"
        _btn_hover = "#58c7ff"
        send_btn = tk.Label(
            bub, text="ENVIAR", bg=_btn_bg, fg=_btn_fg,
            font=("Arial Black", 9), cursor="hand2",
            padx=8, pady=8, relief="flat", bd=0,
            highlightbackground=_btn_hover, highlightthickness=1,
        )
        send_id = canvas.create_window(main_x1 - 104, 512, anchor="nw", width=76, height=44, window=send_btn)
        send_btn.bind("<Enter>", lambda _e: send_btn.config(bg=_btn_hover, fg="#06111f"))
        send_btn.bind("<Leave>", lambda _e: send_btn.config(bg=_btn_bg, fg=_btn_fg))'''

new_send = '''        _btn_bg = "#8a2be2"
        _btn_fg = "#ffffff"
        _btn_hover = "#58c7ff"
        send_btn = tk.Label(
            bub, text="ENVIAR", bg=_btn_bg, fg=_btn_fg,
            font=("Arial Black", 10), cursor="hand2",
            padx=10, pady=8, relief="flat", bd=0,
            highlightbackground="#58c7ff", highlightthickness=2,
        )
        send_id = canvas.create_window(main_x1 - 104, 512, anchor="nw", width=82, height=44, window=send_btn)
        _pulse_on = [False]
        def _pulse_send():
            if not _pulse_on[0]:
                return
            try:
                cur = send_btn.cget("highlightbackground")
                nxt = "#c02dff" if cur == "#58c7ff" else "#58c7ff"
                send_btn.config(highlightbackground=nxt)
                bub.after(600, _pulse_send)
            except Exception:
                pass
        def _start_pulse(_e=None):
            send_btn.config(bg="#5b3cf5", highlightbackground="#58c7ff")
            _pulse_on[0] = True
            _pulse_send()
        def _stop_pulse(_e=None):
            _pulse_on[0] = False
            send_btn.config(bg=_btn_bg, highlightbackground="#8a2be2")
        send_btn.bind("<Enter>", lambda _e: (_start_pulse(), send_btn.config(bg=_btn_hover, fg="#06111f")))
        send_btn.bind("<Leave>", lambda _e: (_stop_pulse(), send_btn.config(bg=_btn_bg, fg=_btn_fg)))'''

# Try the actual content in the file
old_send_actual = '''        _btn_bg = "#c02dff"
        _btn_fg = "#ffffff"
        _btn_hover = "#58c7ff"
        send_btn = tk.Label(
            bub, text="ENVIAR", bg=_btn_bg, fg=_btn_fg,
            font=("Arial Black", 9), cursor="hand2",
            padx=8, pady=8, relief="flat", bd=0,
            highlightbackground=_btn_hover, highlightthickness=1,
        )
        send_id = canvas.create_window(main_x1 - 104, 512, anchor="nw", width=76, height=44, window=send_btn)
        send_btn.bind("<Enter>", lambda _e: send_btn.config(bg=_btn_hover, fg="#06111f"))
        send_btn.bind("<Leave>", lambda _e: send_btn.config(bg=_btn_bg, fg=_btn_fg))'''
pet = pet.replace(old_send_actual, new_send)

# 1g. Restore plain entry.config for placeholder (ensure proper colors)
pet = pet.replace(
    '''        entry.insert(0, _PLACEHOLDER)
        entry.config(fg="#9fb2ff")''',
    '''        entry.insert(0, _PLACEHOLDER)
        entry.config(fg="#5a78cc")'''
)

with open(PET_PATH, 'w', encoding='utf-8') as f:
    f.write(pet)

print("pet.py patched.")

# ─────────────────────────────────────────────────────────────────────────
# 2. chat_view.py patches
# ─────────────────────────────────────────────────────────────────────────
with open(CHAT_VIEW_PATH, 'r', encoding='utf-8') as f:
    cv = f.read()

# 2a. Increase avatar size from 30 to 36 px
cv = cv.replace('av_img = _avatar_monogram(30, av_fill, av_fg, av_char, "user")', 
                'av_img = _avatar_monogram(36, av_fill, av_fg, av_char, "user")')
cv = cv.replace('av_img = _get_bot_avatar(30, av_fill, av_fg)',
                'av_img = _get_bot_avatar(36, av_fill, av_fg)')

# 2b. Upgrade avatar functions to add glowing ring
old_monogram = '''def _avatar_monogram(size: int, bg: str, fg: str, letter: str, role: str) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg_rgb = _hex_to_rgb(bg)
    fg_rgb = _hex_to_rgb(fg)
    d.ellipse((0, 0, size - 1, size - 1), fill=(*bg_rgb, 255))
    try:
        font = ImageFont.truetype("arial.ttf", size // 2)
    except Exception:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - tw) // 2, (size - th) // 2 - 1), letter, fill=(*fg_rgb, 255), font=font)
    return img'''
new_monogram = '''def _avatar_monogram(size: int, bg: str, fg: str, letter: str, role: str) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg_rgb = _hex_to_rgb(bg)
    fg_rgb = _hex_to_rgb(fg)
    # Outer glow ring
    glow_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_img)
    gd.ellipse((0, 0, size - 1, size - 1), outline=(88, 199, 255, 200), width=2)
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(2))
    img = Image.alpha_composite(img, glow_img)
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, size - 3, size - 3), fill=(*bg_rgb, 255))
    d.ellipse((1, 1, size - 2, size - 2), outline=(88, 199, 255, 200), width=1)
    try:
        font = ImageFont.truetype("arial.ttf", size // 2)
    except Exception:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - tw) // 2, (size - th) // 2 - 1), letter, fill=(*fg_rgb, 255), font=font)
    return img'''
cv = cv.replace(old_monogram, new_monogram)

# 2c. Make user bubble gradient more vivid (deeper indigo to bright violet)
old_user_grad = '''        else:
            # Gradient blue-to-purple
            color_start = (61, 126, 255) # #3d7eff
            color_end = (122, 60, 255)   # #7a3cff
            max_dist = max(1, width + height)
            for y in range(height):
                for x in range(width):
                    t = (x + y) / max_dist
                    r = int(color_start[0] + (color_end[0] - color_start[0]) * t)
                    g = int(color_start[1] + (color_end[1] - color_start[1]) * t)
                    b = int(color_start[2] + (color_end[2] - color_start[2]) * t)
                    fill_img.putpixel((x, y), (r, g, b, 255))'''
new_user_grad = '''        else:
            # Gradient indigo-to-violet (vivid, high contrast)
            color_start = (80, 40, 220)  # deep indigo #5028dc
            color_end = (180, 30, 255)   # bright violet #b41eff
            max_dist = max(1, width + height)
            for y in range(height):
                for x in range(width):
                    t = (x + y) / max_dist
                    r = int(color_start[0] + (color_end[0] - color_start[0]) * t)
                    g = int(color_start[1] + (color_end[1] - color_start[1]) * t)
                    b = int(color_start[2] + (color_end[2] - color_start[2]) * t)
                    fill_img.putpixel((x, y), (r, g, b, 255))'''
cv = cv.replace(old_user_grad, new_user_grad)

# 2d. Add cyan glow edge highlight on user bubbles
old_glow = '''    fill_img.putalpha(mask)
    img = Image.alpha_composite(img, fill_img)'''
new_glow = '''    fill_img.putalpha(mask)
    img = Image.alpha_composite(img, fill_img)

    # Glow outline on user bubbles for extra pop
    if role == "user" and style not in ("minimal", "vintage"):
        glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        try:
            glow_draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=12,
                                        outline=(88, 199, 255, 90), width=1)
        except TypeError:
            glow_draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=12,
                                        outline=(88, 199, 255, 90))
        img = Image.alpha_composite(img, glow_layer)'''
cv = cv.replace(old_glow, new_glow)

with open(CHAT_VIEW_PATH, 'w', encoding='utf-8') as f:
    f.write(cv)

print("chat_view.py patched.")
print("All done!")
