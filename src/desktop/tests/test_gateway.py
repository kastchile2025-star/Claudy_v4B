"""Tests del gateway HTTP (core/gateway.py) — contrato de autenticación.

El servidor en sí necesita sockets; aquí probamos la lógica pura de auth que
extrajimos a check_bearer_auth (función de módulo), que es donde está la
decisión de seguridad.

Ejecutar: python tests/test_gateway.py   (desde src/desktop)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gateway import check_bearer_auth  # noqa: E402


class TestBearerAuth(unittest.TestCase):
    def test_sin_token_todo_pasa(self):
        # Modo abierto local: sin token configurado, cualquier request entra.
        self.assertTrue(check_bearer_auth(None, ""))
        self.assertTrue(check_bearer_auth("", "lo que sea"))

    def test_con_token_correcto(self):
        self.assertTrue(check_bearer_auth("s3cr3t", "Bearer s3cr3t"))

    def test_con_token_incorrecto(self):
        self.assertFalse(check_bearer_auth("s3cr3t", "Bearer otro"))

    def test_con_token_sin_header(self):
        self.assertFalse(check_bearer_auth("s3cr3t", ""))

    def test_sin_prefijo_bearer(self):
        # El token a secas (sin "Bearer ") no autoriza.
        self.assertFalse(check_bearer_auth("s3cr3t", "s3cr3t"))

    def test_header_none_no_rompe(self):
        self.assertFalse(check_bearer_auth("s3cr3t", None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
