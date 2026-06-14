"""C8 — Filtrado inteligente de notificaciones (features/digest.py).

Prueba la clasificación de prioridad, la agrupación por origen y el flush, más
el comportamiento del mixin (encolar vs enviar) con un host stub.

Ejecutar: python tests/test_digest.py   (desde src/desktop)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.digest import (  # noqa: E402
    NotificationDigest, classify_priority, DigestMixin)


class TestClassify(unittest.TestCase):
    def test_urgencia_es_alta(self):
        for t in ("el dólar bajó de 900", "ERROR en el backup",
                  "la factura está vencida", "stock agotado", "timeout al cargar"):
            self.assertEqual(classify_priority(t), "alta", t)

    def test_rutina_es_baja(self):
        for t in ("sin cambios en la página", "heartbeat ok",
                  "revisión completada, todo en orden"):
            self.assertEqual(classify_priority(t), "baja", t)


class TestDigest(unittest.TestCase):
    def test_cuenta_y_render(self):
        d = NotificationDigest()
        d.add("ERROR crítico en X", source="cron", now=1)
        d.add("sin cambios", source="watcher", now=2)
        d.add("sin cambios otra vez", source="watcher", now=3)
        out = d.render()
        self.assertIn("1 importantes", out)
        self.assertIn("2 de rutina", out)
        self.assertIn("ERROR", out)

    def test_agrupa_por_origen(self):
        d = NotificationDigest()
        for i in range(4):
            d.add(f"heartbeat {i}", source="watcher", now=i)
        out = d.render()
        # 4 avisos de rutina del mismo origen → una línea con conteo.
        self.assertIn("[watcher] 4 avisos", out)

    def test_flush_vacia(self):
        d = NotificationDigest()
        d.add("algo", now=1)
        self.assertEqual(d.pending_count(), 1)
        d.flush()
        self.assertEqual(d.pending_count(), 0)

    def test_has_high_priority(self):
        d = NotificationDigest()
        d.add("rutina", now=1)
        self.assertFalse(d.has_high_priority())
        d.add("error grave", now=2)
        self.assertTrue(d.has_high_priority())

    def test_render_vacio(self):
        self.assertEqual(NotificationDigest().render(), "")


class _Host(DigestMixin):
    def __init__(self, enabled):
        self._enabled = enabled
        self.raw_sent = []

    def load_claudy_config(self):
        return {"telegram": {"digestNotifications": self._enabled}}

    def _cron_send_telegram_raw(self, text):
        self.raw_sent.append(text)


class TestMixin(unittest.TestCase):
    def test_digest_off_no_encola(self):
        h = _Host(enabled=False)
        self.assertFalse(h._queue_or_notify("algo", source="cron"))
        self.assertEqual(h._get_digest().pending_count(), 0)

    def test_digest_on_encola_rutina(self):
        h = _Host(enabled=True)
        self.assertTrue(h._queue_or_notify("sin cambios", source="watcher"))
        self.assertEqual(h._get_digest().pending_count(), 1)
        # Rutina no se envía al instante.
        self.assertEqual(h.raw_sent, [])

    def test_digest_on_entrega_urgente_al_instante(self):
        h = _Host(enabled=True)
        h._queue_or_notify("sin cambios", source="watcher")
        encolado = h._queue_or_notify("ERROR crítico", source="cron")
        self.assertTrue(encolado)
        # Lo urgente dispara un flush inmediato que envía TODO lo acumulado.
        self.assertEqual(len(h.raw_sent), 1)
        self.assertIn("ERROR", h.raw_sent[0])
        self.assertEqual(h._get_digest().pending_count(), 0)

    def test_deliver_digest_manual(self):
        h = _Host(enabled=True)
        self.assertIn("No hay avisos", h._deliver_digest())
        h._queue_or_notify("sin cambios", source="watcher")
        out = h._deliver_digest()
        self.assertIn("rutina", out.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
