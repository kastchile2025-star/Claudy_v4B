import os

filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pet.py')
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix bubble vertical offset
content = content.replace("wy = cy - h - 10", "wy = cy - h - 40")

# 2. Fix vintage grid color to be opaque (no magenta bleeding)
content = content.replace("grid_color = (180, 170, 145, 60)", "grid_color = (204, 190, 156, 255)")

# 3. Fix vintage inner border to be opaque
content = content.replace("outline=(140, 125, 100, 180)", "outline=(160, 145, 115, 255)")

# 4. Fix top icon colors (replace hardcoded fg="#dbe6ff")
content = content.replace('fg="#dbe6ff"', 'fg=THEME.get("button_fg", "#dbe6ff")')

# 5. Fix input field text color to use input_fg (defaulting to text_secondary)
content = content.replace('fg=THEME["text_secondary"]', 'fg=THEME.get("input_fg", THEME["text_secondary"])')

# 6. Add "input_fg" to vintage theme
old_vintage = '''        "text_primary": "#2c1810",
        "text_secondary": "#6b5744",'''
new_vintage = '''        "text_primary": "#2c1810",
        "text_secondary": "#6b5744",
        "input_fg": "#e6d5b8",'''
content = content.replace(old_vintage, new_vintage)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("UI patches applied.")
