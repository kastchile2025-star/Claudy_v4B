import os

filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pet.py')
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Revert global replace
content = content.replace('fg=THEME.get("input_fg", THEME["text_secondary"])', 'fg=THEME["text_secondary"]')

# 2. Add it back ONLY for the input field and text box config
old_entry = '''        entry = tk.Text(
            bub,
            bg=THEME.get("header_chip", THEME["bg_input"]), fg=THEME["text_secondary"],'''

new_entry = '''        entry = tk.Text(
            bub,
            bg=THEME.get("header_chip", THEME["bg_input"]), fg=THEME.get("input_fg", THEME["text_secondary"]),'''
content = content.replace(old_entry, new_entry)

old_entry_config = '''                entry.config(fg=THEME["text_secondary"])'''
new_entry_config = '''                entry.config(fg=THEME.get("input_fg", THEME["text_secondary"]))'''
content = content.replace(old_entry_config, new_entry_config)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Text colors fixed.")
