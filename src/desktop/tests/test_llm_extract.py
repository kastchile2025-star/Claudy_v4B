"""Tests de core/llm.py — extracción de texto multi-formato."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import extract_text


class TestExtractText(unittest.TestCase):
    def test_opencode_parts(self):
        r = {"parts": [{"type": "text", "text": "hola"}, {"type": "tool", "text": "x"}]}
        self.assertEqual(extract_text(r), "hola")

    def test_openai_choices(self):
        r = {"choices": [{"message": {"role": "assistant", "content": "respuesta"}}]}
        self.assertEqual(extract_text(r), "respuesta")

    def test_anthropic_content(self):
        r = {"content": [{"type": "text", "text": "claude dice"}]}
        self.assertEqual(extract_text(r), "claude dice")

    def test_content_string(self):
        self.assertEqual(extract_text({"content": "directo"}), "directo")

    def test_text_key(self):
        self.assertEqual(extract_text({"text": "plano"}), "plano")

    def test_vacio(self):
        self.assertEqual(extract_text({}), "")
        self.assertEqual(extract_text(None), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
