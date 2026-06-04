import sys
with open('pet.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('_active_theme_idx = 0', '_active_theme_idx = 4', 1)

# Fix hardcoded ENVIAR button colors to use theme
old_btn = '''        send_btn = tk.Label(
            bub, text="ENVIAR", bg="#c02dff", fg="#ffffff",
            font=("Arial Black", 9), cursor="hand2",
            padx=8, pady=8, relief="flat", bd=0,
            highlightbackground="#58c7ff", highlightthickness=1,
        )
        send_id = canvas.create_window(width - 118, 510, anchor="nw", width=84, height=46, window=send_btn)
        send_btn.bind("<Enter>", lambda _e: send_btn.config(bg="#58c7ff", fg="#06111f"))
        send_btn.bind("<Leave>", lambda _e: send_btn.config(bg="#c02dff", fg="#ffffff"))'''

new_btn = '''        _btn_bg = THEME.get("accent", "#c02dff")
        _btn_fg = THEME.get("bg_bubble", "#ffffff")
        if THEME.get("style") == "vintage": _btn_fg = THEME.get("bg_input", "#2e2820")
        _btn_hover = THEME.get("accent_glow", "#58c7ff")
        send_btn = tk.Label(
            bub, text="ENVIAR", bg=_btn_bg, fg=_btn_fg,
            font=("Arial Black", 9), cursor="hand2",
            padx=8, pady=8, relief="flat", bd=0,
            highlightbackground=_btn_hover, highlightthickness=1,
        )
        send_id = canvas.create_window(width - 118, 510, anchor="nw", width=84, height=46, window=send_btn)
        send_btn.bind("<Enter>", lambda _e: send_btn.config(bg=_btn_hover, fg="#06111f"))
        send_btn.bind("<Leave>", lambda _e: send_btn.config(bg=_btn_bg, fg=_btn_fg))'''

content = content.replace(old_btn, new_btn)

with open('pet.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched successfully.")
