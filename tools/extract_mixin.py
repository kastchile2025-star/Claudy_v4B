"""Extractor de mixins para el refactor v5 de Claudy.

Mueve métodos/atributos de la clase ClawdPet (pet.py) a un módulo nuevo
como clase Mixin, preservando el código byte a byte. Uso:

    python tools/extract_mixin.py <names.txt> <salida.py> <NombreMixin> <header.py>

- names.txt: un nombre de método/atributo de clase por línea.
- header.py: contenido inicial del módulo (docstring + imports + constantes).

No toca el `class ClawdPet(...)` ni los imports de pet.py: eso se edita aparte.
"""
import ast
import sys

PET = "src/desktop/pet.py"


def main():
    names_file, out_path, mixin_name, header_file = sys.argv[1:5]
    names = {n.strip() for n in open(names_file, encoding="utf-8") if n.strip()}
    header = open(header_file, encoding="utf-8").read()

    src = open(PET, encoding="utf-8").read()
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "ClawdPet")

    ranges, found = [], set()
    for node in cls.body:
        name = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in names:
            if name in found:
                raise SystemExit(f"DUPLICADO en ClawdPet: {name} (resolver antes)")
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            ranges.append((start, node.end_lineno, name))
            found.add(name)

    missing = names - found
    if missing:
        raise SystemExit(f"NO ENCONTRADOS en ClawdPet: {sorted(missing)}")

    chunks = ["".join(lines[s - 1:e]) for s, e, _ in sorted(ranges)]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header.rstrip() + "\n\n\nclass " + mixin_name + ":\n")
        f.write("\n".join(chunks))
        f.write("\n")

    for s, e, _ in sorted(ranges, reverse=True):
        del lines[s - 1:e]
    with open(PET, "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))

    print(f"OK: {len(ranges)} bloques -> {out_path}; pet.py reducido en "
          f"{sum(e - s + 1 for s, e, _ in ranges)} líneas")


if __name__ == "__main__":
    main()
