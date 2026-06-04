import os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pet.py')
with open(path, 'r', encoding='utf-8') as f:
    pet = f.read()

# 1. Widen sidebar: 218 -> 278 (+60px), shift main panel start
pet = pet.replace('side_x0, side_x1 = 18, 218', 'side_x0, side_x1 = 18, 278')
pet = pet.replace('main_x0, main_x1 = 234, width - 18', 'main_x0, main_x1 = 294, width - 18')

# 2. Widen total window
pet = pet.replace('BUBBLE_WIDTH = 820', 'BUBBLE_WIDTH = 880')

# 3. Sidebar inner panels wider
pet = pet.replace('rounded_panel(34, 128, 202, 182,', 'rounded_panel(34, 128, 262, 182,')
pet = pet.replace('nueva_bg = rounded_panel(34, 204, 202, 238,', 'nueva_bg = rounded_panel(34, 204, 262, 238,')
pet = pet.replace('nueva_txt = canvas.create_text(118, 221,', 'nueva_txt = canvas.create_text(148, 221,')

# Status dot position
pet = pet.replace('side_x0 + 188, 138,', 'side_x0 + 248, 138,')

# Google Drive status indicator position
pet = pet.replace('canvas.create_oval(114, 146, 122, 154,', 'canvas.create_oval(154, 146, 162, 154,')
pet = pet.replace('canvas.create_text(126, 144,', 'canvas.create_text(168, 144,')

# Products list panels
pet = pet.replace('rounded_panel(30, y, 206, y + 30,', 'rounded_panel(30, y, 266, y + 30,')
pet = pet.replace('tag_id = canvas.create_text(194, y + 8,', 'tag_id = canvas.create_text(254, y + 8,')

# User profile panel & avatar adjustments
pet = pet.replace('rounded_panel(30, height - 78, 206, height - 34, 16, "#071026", "#24366e", 1)', 'rounded_panel(30, height - 90, 266, height - 30, 16, "#071026", "#24366e", 1)')
pet = pet.replace('size = (30, 30)', 'size = (34, 34)')
pet = pet.replace('canvas.create_image(44, height - 68,', 'canvas.create_image(42, height - 80,')
pet = pet.replace('canvas.create_oval(44, height - 68, 74, height - 38,', 'canvas.create_oval(42, height - 80, 76, height - 46,')
pet = pet.replace('canvas.create_text(59, height - 53,', 'canvas.create_text(59, height - 63,')

# Brand logo - shift right
pet = pet.replace(
    'canvas.create_image(38, 50,',
    'canvas.create_image(48, 50,'
)
pet = pet.replace(
    'canvas.create_oval(38, 50, 82, 94,',
    'canvas.create_oval(48, 50, 92, 94,'
)
pet = pet.replace(
    'canvas.create_text(60, 72, text="AI",',
    'canvas.create_text(70, 72, text="AI",'
)
pet = pet.replace(
    'canvas.create_text(96, 56, anchor="nw", text="CLAUDY",',
    'canvas.create_text(106, 56, anchor="nw", text="CLAUDY",'
)
pet = pet.replace(
    'canvas.create_text(96, 82, anchor="nw", text="Tu asistente IA",',
    'canvas.create_text(106, 82, anchor="nw", text="Tu asistente IA",'
)

# Email font smaller to fit
pet = pet.replace(
    'canvas.create_text(88, height - 44, anchor="nw", text="jorge.castro@qcorespa.com", fill="#9fb2ff",\n                           font=("Bahnschrift", 8)',
    'canvas.create_text(88, height - 44, anchor="nw", text="jorge.castro@qcorespa.com", fill="#9fb2ff",\n                           font=("Bahnschrift", 9)'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(pet)

print("Sidebar widened OK")
