"""Tests del screenshot accionable (features/screen_actions.py)."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from features.screen_actions import (  # noqa: E402
    ScreenActionsMixin, SCREEN_EVENT_RX, parse_event_json, event_to_iso,
)


class FakePet(ScreenActionsMixin):
    def __init__(self, vision_reply=""):
        self.vision_reply = vision_reply
        self.grabbed = 0

    def _grab_screen(self):
        self.grabbed += 1
        return "C:/fake/screen.png"

    def _analyze_image_native(self, path, question):
        return self.vision_reply

    def _debug_log(self, *a):
        pass


class TestIntentRegex(unittest.TestCase):
    def test_frases_que_disparan(self):
        for p in ("agenda lo que está en pantalla",
                  "agéndame esto que está en pantalla",
                  "crea un evento con lo que ves en pantalla",
                  "agrega esto al calendario, está en pantalla",
                  "anota al calendario lo que se ve en pantalla"):
            self.assertTrue(SCREEN_EVENT_RX.search(p), p)

    def test_calendario_normal_no_dispara(self):
        for p in ("agenda reunión con Marco mañana a las 10",
                  "crea un evento para el viernes",
                  "qué hay en pantalla",
                  "agrega al calendario la cena del sábado"):
            self.assertFalse(SCREEN_EVENT_RX.search(p), p)


class TestParseEventJson(unittest.TestCase):
    def test_json_limpio(self):
        d = parse_event_json('{"found": true, "summary": "Dentista"}')
        self.assertEqual(d["summary"], "Dentista")

    def test_json_con_fences_y_texto(self):
        d = parse_event_json('Claro:\n```json\n{"found": true, "summary": "X"}\n```')
        self.assertTrue(d["found"])

    def test_sin_json(self):
        self.assertIsNone(parse_event_json("no veo nada agendable"))
        self.assertIsNone(parse_event_json(""))


class TestEventToIso(unittest.TestCase):
    NOW = datetime.datetime(2026, 6, 11, 14, 0)

    def test_completo(self):
        s, e, aviso = event_to_iso(
            {"date": "2026-06-13", "start": "19:30", "end": "21:00"}, self.NOW)
        self.assertEqual(s, "2026-06-13T19:30:00")
        self.assertEqual(e, "2026-06-13T21:00:00")
        self.assertEqual(aviso, "")

    def test_sin_fin_dura_una_hora(self):
        s, e, _ = event_to_iso({"date": "2026-06-13", "start": "19:30"}, self.NOW)
        self.assertEqual(e, "2026-06-13T20:30:00")

    def test_sin_hora_va_a_las_9_con_aviso(self):
        s, e, aviso = event_to_iso({"date": "2026-06-13", "start": None}, self.NOW)
        self.assertEqual(s, "2026-06-13T09:00:00")
        self.assertIn("09:00", aviso)

    def test_fin_pasado_medianoche(self):
        s, e, _ = event_to_iso(
            {"date": "2026-06-13", "start": "23:00", "end": "01:00"}, self.NOW)
        self.assertEqual(e, "2026-06-14T01:00:00")

    def test_fecha_invalida_usa_hoy(self):
        s, _, _ = event_to_iso({"date": "mañana", "start": "10:00"}, self.NOW)
        self.assertTrue(s.startswith("2026-06-11"))


class TestScreenToCalendar(unittest.TestCase):
    def test_nada_agendable(self):
        pet = FakePet('{"found": false}')
        out = pet._screen_to_calendar()
        self.assertIn("no encontré nada agendable", out)
        self.assertEqual(pet.grabbed, 1)

    def test_vision_ilegible(self):
        pet = FakePet("la pantalla muestra un documento de texto")
        out = pet._screen_to_calendar()
        self.assertIn("no pude estructurar", out)

    def test_evento_sin_calendar_conectado_entrega_lo_leido(self):
        pet = FakePet('{"found": true, "summary": "Reunión QCORE", '
                      '"date": "2026-06-13", "start": "10:00", "end": null, '
                      '"location": "Oficina", "description": "Revisión mensual"}')
        out = pet._screen_to_calendar()
        # Sin google_calendar conectado en el entorno de test: igual entrega el evento leído
        self.assertIn("Reunión QCORE", out)
        self.assertIn("13-06-2026 10:00", out)
        self.assertIn("Oficina", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
