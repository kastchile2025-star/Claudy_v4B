"""A11 — persistencia del gestor visual de configuración (_save_config_section).

La construcción de widgets (tkinter) no se testea aquí; sí la lógica de guardado:
que aplique el mutator, escriba config.json y no pierda otras secciones.

Ejecutar: python tests/test_config_panels.py   (desde src/desktop)
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_json(path):
    """Lee y CIERRA el fichero (evita ResourceWarning de json.load(open(...)))."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def make_host():
    tmp = tempfile.mkdtemp(prefix="claudy_cfgtest_")
    cfg_path = os.path.join(tmp, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump({
            "opencode": {"defaultModel": "deepseek-chat", "apiKey": "SECRETO"},
            "telegram": {"ttsReply": False, "token": "TKN"},
            "agent": {"systemPrompt": "soy claudy"},
        }, f)

    # Replicamos _save_config_section sin arrastrar pet.py (UI). El contrato:
    # load → mutate → escribir json preservando todo lo demás.
    class Host:
        def load_claudy_config(self):
            with open(cfg_path, encoding="utf-8-sig") as f:
                return json.load(f)

        def _save_config_section(self, mutator):
            try:
                cfg = self.load_claudy_config()
                mutator(cfg)
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
                return True, "Guardado ✓"
            except Exception as e:
                return False, f"Error al guardar: {e}"

    return Host(), cfg_path


class TestSaveConfigSection(unittest.TestCase):
    def test_cambia_modelo_sin_perder_otras_secciones(self):
        host, path = make_host()
        ok, _ = host._save_config_section(
            lambda c: c.setdefault("opencode", {}).__setitem__("defaultModel", "claude-opus-4-8"))
        self.assertTrue(ok)
        cfg = _read_json(path)
        self.assertEqual(cfg["opencode"]["defaultModel"], "claude-opus-4-8")
        # No se perdieron otras claves de opencode ni otras secciones.
        self.assertEqual(cfg["opencode"]["apiKey"], "SECRETO")
        self.assertEqual(cfg["agent"]["systemPrompt"], "soy claudy")

    def test_toggle_tts_telegram(self):
        host, path = make_host()
        host._save_config_section(
            lambda c: c.setdefault("telegram", {}).__setitem__("ttsReply", True))
        cfg = _read_json(path)
        self.assertTrue(cfg["telegram"]["ttsReply"])
        self.assertEqual(cfg["telegram"]["token"], "TKN")  # token intacto

    def test_usuarios_telegram_se_normalizan_a_int(self):
        host, path = make_host()

        def _mut(c):
            users = ["123", "-456", "alias"]
            norm = [int(u) if u.lstrip("-").isdigit() else u for u in users]
            c.setdefault("telegram", {})["authorizedUsers"] = norm
        host._save_config_section(_mut)
        cfg = _read_json(path)
        self.assertEqual(cfg["telegram"]["authorizedUsers"], [123, -456, "alias"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
