"""A10 — Emparejamiento seguro de canales (core/pairing.py).

Toda la lógica es pura y con reloj inyectable, así que se prueba sin red ni
Telegram: TTL, un solo uso, rate-limit, lockout y persistencia.

Ejecutar: python tests/test_pairing.py   (desde src/desktop)
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import pairing  # noqa: E402


class TestCodeLifecycle(unittest.TestCase):
    def test_genera_codigo_de_longitud_correcta(self):
        state = {}
        code = pairing.generate_code(state, now=1000)
        self.assertEqual(len(code), pairing.CODE_LENGTH)
        self.assertTrue(code.isdigit())
        self.assertIn("pending", state)

    def test_codigo_correcto_autoriza(self):
        state = {}
        code = pairing.generate_code(state, now=1000)
        ok, msg = pairing.verify_code(state, "U1", code, now=1010)
        self.assertTrue(ok)
        self.assertIn("U1", state["authorized"])
        # Un solo uso: el pending se consumió.
        self.assertNotIn("pending", state)

    def test_codigo_expira(self):
        state = {}
        code = pairing.generate_code(state, now=1000, ttl=300)
        ok, msg = pairing.verify_code(state, "U1", code, now=1000 + 301)
        self.assertFalse(ok)
        self.assertIn("código", msg.lower())

    def test_codigo_es_de_un_solo_uso(self):
        state = {}
        code = pairing.generate_code(state, now=1000)
        pairing.verify_code(state, "U1", code, now=1010)
        # Reusar el mismo código (otro uid) ya no funciona: no hay pending.
        ok, _ = pairing.verify_code(state, "U2", code, now=1011)
        self.assertFalse(ok)


class TestRateLimitLockout(unittest.TestCase):
    def test_codigo_incorrecto_descuenta_intentos(self):
        state = {}
        pairing.generate_code(state, now=1000)
        ok, msg = pairing.verify_code(state, "U1", "000000", now=1001)
        self.assertFalse(ok)
        self.assertIn("intentos", msg.lower())

    def test_lockout_tras_max_intentos(self):
        state = {}
        pairing.generate_code(state, now=1000)
        for i in range(pairing.MAX_ATTEMPTS):
            pairing.verify_code(state, "U1", "000000", now=1000 + i)
        self.assertTrue(pairing.is_locked(state, "U1", now=1000 + pairing.MAX_ATTEMPTS))
        # Aun con el código correcto, el lockout manda.
        code = state.get("pending", {}).get("code", "")
        if code:
            ok, msg = pairing.verify_code(state, "U1", code, now=1000 + pairing.MAX_ATTEMPTS)
            self.assertFalse(ok)
            self.assertIn("espera", msg.lower())

    def test_lockout_expira(self):
        state = {}
        pairing.generate_code(state, now=1000)
        last_attempt_at = 1000 + pairing.MAX_ATTEMPTS - 1  # momento del intento que bloquea
        for i in range(pairing.MAX_ATTEMPTS):
            pairing.verify_code(state, "U1", "000000", now=1000 + i)
        # Sigue bloqueado justo antes de que venza el lockout...
        self.assertTrue(pairing.is_locked(
            state, "U1", now=last_attempt_at + pairing.LOCKOUT_SECONDS - 1))
        # ...y libre después.
        self.assertFalse(pairing.is_locked(
            state, "U1", now=last_attempt_at + pairing.LOCKOUT_SECONDS + 1))

    def test_otro_uid_no_se_afecta(self):
        state = {}
        pairing.generate_code(state, now=1000)
        for i in range(pairing.MAX_ATTEMPTS):
            pairing.verify_code(state, "U1", "000000", now=1000 + i)
        # U2 no está bloqueado por los fallos de U1.
        self.assertFalse(pairing.is_locked(state, "U2", now=1000 + pairing.MAX_ATTEMPTS))


class TestPersistence(unittest.TestCase):
    def test_save_y_load(self):
        tmp = tempfile.mkdtemp(prefix="claudy_pair_")
        path = os.path.join(tmp, "pairing.json")
        state = {"authorized": ["U9"]}
        self.assertTrue(pairing.save_state(state, path))
        loaded = pairing.load_state(path)
        self.assertEqual(loaded.get("authorized"), ["U9"])

    def test_load_inexistente_devuelve_vacio(self):
        self.assertEqual(pairing.load_state("/no/existe/pairing.json"), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
