"""Tests del modo conversación por voz (features/voice_chat.py)."""
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from features.voice_chat import VoiceChatMixin, EXIT_PHRASES  # noqa: E402


class FakePet(VoiceChatMixin):
    def __init__(self):
        self.js_calls = []
        self.submitted = []

    def _eval_in_web(self, script):
        self.js_calls.append(script)

    def _handle_web_submit(self, text):
        self.submitted.append(text)

    def _debug_log(self, *a):
        pass


class TestVoiceChatToggle(unittest.TestCase):
    def test_stop_sin_iniciar_queda_off(self):
        pet = FakePet()
        self.assertEqual(pet._voice_chat_stop(), "off")
        self.assertFalse(getattr(pet, "_voice_chat_on", False))

    def test_stop_apaga_y_destraba_el_loop(self):
        pet = FakePet()
        pet._voice_chat_on = True
        pet._voice_answer_event = threading.Event()
        out = pet._voice_chat_stop()
        self.assertEqual(out, "off")
        self.assertFalse(pet._voice_chat_on)
        self.assertTrue(pet._voice_answer_event.is_set())
        # estado "off" empujado al chat web
        self.assertTrue(any("setVoiceState" in c and '"off"' in c for c in pet.js_calls))

    def test_toggle_desde_on_apaga(self):
        pet = FakePet()
        pet._voice_chat_on = True
        self.assertEqual(pet._voice_chat_toggle(), "off")


class TestVoiceCapture(unittest.TestCase):
    def test_captura_respuesta_solo_en_modo_voz(self):
        pet = FakePet()
        pet._voice_chat_on = False
        pet._voice_capture_answer("hola")
        self.assertEqual(getattr(pet, "_voice_last_answer", ""), "")

        pet._voice_chat_on = True
        pet._voice_answer_event = threading.Event()
        pet._voice_capture_answer("la respuesta")
        self.assertEqual(pet._voice_last_answer, "la respuesta")
        self.assertTrue(pet._voice_answer_event.is_set())


class TestExitPhrases(unittest.TestCase):
    def test_frases_de_despedida(self):
        for phrase in ("adiós claudy", "ya está, termina la conversación",
                       "deja de escuchar por favor"):
            self.assertTrue(any(p in phrase.lower() for p in EXIT_PHRASES), phrase)

    def test_frase_normal_no_corta(self):
        normal = "cuánto vale el dólar hoy"
        self.assertFalse(any(p in normal for p in EXIT_PHRASES))


class TestVoiceStatus(unittest.TestCase):
    def test_status_escapa_json(self):
        pet = FakePet()
        pet._voice_chat_status("error", 'detalle con "comillas"')
        self.assertEqual(len(pet.js_calls), 1)
        self.assertIn('setVoiceState("error"', pet.js_calls[0])


class TestDictation(unittest.TestCase):
    def test_segundo_clic_detiene_la_grabacion(self):
        pet = FakePet()
        pet._dictating = True
        out = pet._dictation_toggle()
        self.assertEqual(out, "stopping")
        self.assertFalse(pet._dictating)

    def test_status_se_empuja_al_chat(self):
        pet = FakePet()
        pet._dictation_status("recording")
        self.assertTrue(any('setDictationState("recording"' in c for c in pet.js_calls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
