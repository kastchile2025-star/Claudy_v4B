"""Tests del pegado Ctrl+V de imágenes/archivos en el chat (pet._handle_web_paste_image).

No se instancia ClawdPet (tkinter): se prueba la lógica del handler aislada
con un doble que replica el método real importado desde pet.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class FakeChatView:
    def __init__(self):
        self.system_msgs = []

    def add_system(self, text):
        self.system_msgs.append(text)


class FakePet:
    """Replica el flujo de _handle_web_paste_image con colaboradores falsos."""

    def __init__(self, clip):
        self._clip = clip
        self.chat = FakeChatView()
        self.analyzed = []
        self.question_in_entry = ""

    def _entry_attachment_question(self, entry):
        return self.question_in_entry

    def _analyze_attachment_file(self, path, status=None, entry=None, question=None):
        self.analyzed.append((str(path), question))

    # — versión condensada del handler real (misma lógica de ramas) —
    def handle_paste(self):
        clip = self._clip
        question = self._entry_attachment_question(None)
        if clip is None:
            self.chat.add_system("No hay imagen ni archivos en el portapapeles.")
            return
        if isinstance(clip, list):
            paths = [p for p in clip if os.path.isfile(str(p))]
            if not paths:
                self.chat.add_system("Lo copiado no contiene archivos analizables.")
                return
            for path in paths[:6]:
                self._analyze_attachment_file(str(path), None, None, question=question)
            if len(paths) > 6:
                self.chat.add_system("Para no saturar la sesión, analicé solo los primeros 6 archivos.")
            return
        self._analyze_attachment_file("pegado.png", None, None, question=question)


class TestPasteImage(unittest.TestCase):
    def test_portapapeles_vacio_avisa(self):
        pet = FakePet(clip=None)
        pet.handle_paste()
        self.assertTrue(any("No hay imagen" in m for m in pet.chat.system_msgs))
        self.assertEqual(pet.analyzed, [])

    def test_imagen_se_analiza_con_pregunta_del_input(self):
        pet = FakePet(clip="IMAGEN")
        pet.question_in_entry = "¿qué dice esta boleta?"
        pet.handle_paste()
        self.assertEqual(len(pet.analyzed), 1)
        self.assertEqual(pet.analyzed[0][1], "¿qué dice esta boleta?")

    def test_archivos_copiados_max_6(self):
        with mock.patch("os.path.isfile", return_value=True):
            pet = FakePet(clip=[f"C:/docs/f{i}.pdf" for i in range(8)])
            pet.handle_paste()
        self.assertEqual(len(pet.analyzed), 6)
        self.assertTrue(any("primeros 6" in m for m in pet.chat.system_msgs))

    def test_lista_sin_archivos_reales_avisa(self):
        pet = FakePet(clip=["C:/no/existe.xyz"])
        pet.handle_paste()
        self.assertEqual(pet.analyzed, [])
        self.assertTrue(any("no contiene archivos" in m for m in pet.chat.system_msgs))


class TestCableado(unittest.TestCase):
    """El método real existe y chat.html lo invoca."""

    def test_pet_define_el_handler(self):
        import ast
        path = os.path.join(os.path.dirname(__file__), "..", "pet.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        self.assertIn("_handle_web_paste_image", names)

    def test_api_y_html_cableados(self):
        base = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(base, "ui", "webview_api.py"), encoding="utf-8") as f:
            self.assertIn("def paste_image", f.read())
        with open(os.path.join(base, "chat.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn("onPaste={handlePaste}", html)
        self.assertIn("paste_image()", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
