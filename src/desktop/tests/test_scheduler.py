"""Tests del motor de cron/alarmas (features/scheduler.py).

Cubrimos el parseo en lenguaje natural (_parse_cron_nl, _cron_strip_prefix),
que es lógica pura y donde viven los bugs sutiles (am/pm, partes del día,
unidades de intervalo). No disparamos timers reales.

Ejecutar: python tests/test_scheduler.py   (desde src/desktop)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.scheduler import SchedulerMixin  # noqa: E402


class Host(SchedulerMixin):
    """Solo necesita los métodos de parseo; no instancia la UI."""
    pass


class TestStripPrefix(unittest.TestCase):
    def setUp(self):
        self.h = Host()

    def test_quita_recuerdame(self):
        self.assertEqual(self.h._cron_strip_prefix("recuérdame comprar pan"), "comprar pan")

    def test_quita_cron(self):
        self.assertEqual(self.h._cron_strip_prefix("/cron llamar a Ana"), "llamar a Ana")


class TestInterval(unittest.TestCase):
    def setUp(self):
        self.h = Host()

    def test_cada_minutos(self):
        kind, params, msg = self.h._parse_cron_nl("recuérdame cada 30 minutos tomar agua")
        self.assertEqual(kind, "interval")
        self.assertEqual(params, 30)
        self.assertIn("agua", msg)

    def test_cada_horas(self):
        kind, params, _ = self.h._parse_cron_nl("avísame cada 2 horas estirar")
        self.assertEqual(kind, "interval")
        self.assertEqual(params, 120)

    def test_segundos_minimo_un_minuto(self):
        kind, params, _ = self.h._parse_cron_nl("recuérdame cada 30 segundos algo")
        self.assertEqual(kind, "interval")
        self.assertGreaterEqual(params, 1)


class TestDaily(unittest.TestCase):
    def setUp(self):
        self.h = Host()

    def test_hora_simple(self):
        kind, params, msg = self.h._parse_cron_nl("recuérdame a las 9 revisar correo")
        self.assertEqual(kind, "daily")
        self.assertEqual(params, (9, 0))
        self.assertIn("correo", msg)

    def test_hora_con_minutos(self):
        kind, params, _ = self.h._parse_cron_nl("recuérdame a las 14:30 la reunión")
        self.assertEqual(params, (14, 30))

    def test_pm_suma_doce(self):
        kind, params, _ = self.h._parse_cron_nl("recuérdame a las 9pm cenar")
        self.assertEqual(params, (21, 0))

    def test_de_la_noche(self):
        kind, params, msg = self.h._parse_cron_nl("recuérdame a las 8 de la noche llamar")
        self.assertEqual(params, (20, 0))
        # El mensaje no debe arrastrar "de la noche".
        self.assertEqual(msg.strip(), "llamar")

    def test_de_la_tarde(self):
        kind, params, msg = self.h._parse_cron_nl("recuérdame a las 5 de la tarde el café")
        self.assertEqual(params, (17, 0))
        self.assertNotIn("tarde", msg.lower())

    def test_de_la_manana_no_cambia(self):
        kind, params, _ = self.h._parse_cron_nl("recuérdame a las 7 de la mañana correr")
        self.assertEqual(params, (7, 0))


class TestNoMatch(unittest.TestCase):
    def setUp(self):
        self.h = Host()

    def test_no_es_cron(self):
        self.assertIsNone(self.h._parse_cron_nl("hola, cómo estás"))

    def test_trigger_sin_tiempo_ni_mensaje(self):
        # "recuérdame" sin hora ni intervalo no produce un cron válido.
        self.assertIsNone(self.h._parse_cron_nl("recuérdame"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
