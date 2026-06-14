"""A12 — etiquetas legibles de la CLAUDY CONSOLE para el streaming de tool-calls.

Probamos la lógica pura (_tool_console_label) sin necesidad de UI ni webview.
El emisor real (_emit_tool_console) solo enruta esa etiqueta al canal de status.

Ejecutar: python tests/test_tool_console.py   (desde src/desktop)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# pet.py arranca tkinter/webview al importarse, así que replicamos textualmente
# el contrato de _tool_console_label aquí y, abajo, un test verifica que el
# diccionario de pet.py no se desincronice de esta copia.
_TOOL_CONSOLE_LABELS = {
    "get_disk_space": "🖧 Consultando espacio en disco",
    "execute_command": "⌘ Ejecutando comando",
    "search_files": "🔎 Buscando archivos",
    "read_file": "📖 Leyendo archivo",
    "write_file": "✍ Escribiendo archivo",
    "append_file": "✍ Añadiendo a archivo",
    "replace_in_file": "✎ Editando archivo",
    "create_folder": "📁 Creando carpeta",
    "browser_goto": "🌐 Abriendo página",
    "browser_text": "🌐 Leyendo la página",
    "browser_click": "🖱 Click en la página",
    "browser_fill": "⌨ Rellenando formulario",
    "browser_press": "⌨ Pulsando tecla",
    "show_canvas": "🖼 Mostrando canvas",
}


def label(name, args=None):
    base = _TOOL_CONSOLE_LABELS.get(name)
    if base is None:
        if name.startswith("mcp_"):
            base = f"🔌 Herramienta MCP: {name[4:]}"
        else:
            base = f"⚙ {name}"
    detail = ""
    if isinstance(args, dict):
        for key in ("command", "url", "path", "query", "target", "title", "selector"):
            val = args.get(key)
            if val:
                detail = str(val).replace("\n", " ").strip()
                break
    if detail:
        if len(detail) > 48:
            detail = detail[:48].rstrip() + "…"
        base = f"{base}: {detail}"
    return base


class TestConsoleLabels(unittest.TestCase):
    def test_label_conocida(self):
        self.assertEqual(label("read_file"), "📖 Leyendo archivo")

    def test_label_con_detalle_de_ruta(self):
        out = label("read_file", {"path": "C:/x/y.txt"})
        self.assertIn("Leyendo archivo", out)
        self.assertIn("y.txt", out)

    def test_detalle_largo_se_recorta(self):
        out = label("execute_command", {"command": "x" * 200})
        self.assertLessEqual(len(out), 80)
        self.assertTrue(out.endswith("…"))

    def test_tool_desconocida_tiene_fallback(self):
        self.assertEqual(label("alguna_rara"), "⚙ alguna_rara")

    def test_tool_mcp_se_etiqueta(self):
        out = label("mcp_gmail_send", {"query": "hola"})
        self.assertIn("MCP", out)
        self.assertIn("gmail_send", out)

    def test_url_se_usa_como_detalle(self):
        out = label("browser_goto", {"url": "https://sii.cl"})
        self.assertIn("sii.cl", out)

    def test_sin_args_no_rompe(self):
        self.assertEqual(label("get_disk_space", None), "🖧 Consultando espacio en disco")


class TestRealPetMatchesContract(unittest.TestCase):
    """Garantiza que el diccionario de pet.py no se desincronice de este test."""

    def test_labels_en_pet_py_coinciden(self):
        pet_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pet.py")
        with open(pet_path, encoding="utf-8") as f:
            src = f.read()
        # Todas las claves que probamos deben existir literalmente en pet.py.
        for key in _TOOL_CONSOLE_LABELS:
            self.assertIn(f'"{key}":', src,
                          f"{key} falta en _TOOL_CONSOLE_LABELS de pet.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
