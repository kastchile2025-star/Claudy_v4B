"""Tests for secure_store: encryption-at-rest for Claudy config secrets.

Run from anywhere:
    python -m unittest discover -s src/desktop/tests -p "test_*.py"
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secure_store  # noqa: E402


class SecureStoreTest(unittest.TestCase):
    def setUp(self):
        # Isolate the key file in a temp dir and reset the cached cipher.
        self._tmp = tempfile.mkdtemp(prefix="claudy_sec_")
        secure_store.CLAUDY_DIR = self._tmp
        secure_store.KEY_PATH = os.path.join(self._tmp, ".secret.key")
        secure_store._fernet = None
        secure_store._fernet_tried = False

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_roundtrip(self):
        enc = secure_store.encrypt_str("sk-supersecret-123")
        self.assertEqual(secure_store.decrypt_str(enc), "sk-supersecret-123")

    def test_idempotent_encrypt(self):
        enc1 = secure_store.encrypt_str("token-abc")
        enc2 = secure_store.encrypt_str(enc1)  # encrypting ciphertext is a no-op
        self.assertEqual(enc1, enc2)
        self.assertEqual(secure_store.decrypt_str(enc2), "token-abc")

    def test_empty_and_nonstring_passthrough(self):
        self.assertEqual(secure_store.encrypt_str(""), "")
        self.assertEqual(secure_store.encrypt_str(None), None)
        self.assertEqual(secure_store.encrypt_str(123), 123)

    def test_decrypt_plaintext_is_noop(self):
        self.assertEqual(secure_store.decrypt_str("plain-text"), "plain-text")

    def test_prefix_only_when_available(self):
        enc = secure_store.encrypt_str("hello")
        if secure_store.available():
            self.assertTrue(secure_store.is_encrypted(enc))
            self.assertNotIn("hello", enc)
        else:
            # No cryptography installed -> graceful passthrough.
            self.assertEqual(enc, "hello")

    def test_config_walk_roundtrip(self):
        cfg = {
            "opencode": {"apiKey": "sk-oc", "baseUrl": "http://x", "password": "pw"},
            "telegram": {"botToken": "123:ABC", "enabled": True},
            "providers": {
                "deepseek": {"key": "dk-1", "keys": ["dk-1", "dk-2"]},
                "openai": {"key": "", "keys": []},
            },
            "email": {"smtp_pass": "app-pass", "smtp_user": "me"},
            "agent": {"systemPrompt": "not a secret"},
        }
        import copy
        original = copy.deepcopy(cfg)

        secure_store.encrypt_config_secrets(cfg)
        # Non-secret fields are untouched.
        self.assertEqual(cfg["opencode"]["baseUrl"], "http://x")
        self.assertEqual(cfg["agent"]["systemPrompt"], "not a secret")
        self.assertTrue(cfg["telegram"]["enabled"])
        if secure_store.available():
            self.assertTrue(secure_store.is_encrypted(cfg["opencode"]["apiKey"]))
            self.assertTrue(all(secure_store.is_encrypted(k) for k in cfg["providers"]["deepseek"]["keys"]))

        # Decrypting restores the exact original config.
        secure_store.decrypt_config_secrets(cfg)
        self.assertEqual(cfg, original)

    def test_empty_secret_not_encrypted(self):
        cfg = {"providers": {"openai": {"key": "", "keys": []}}}
        secure_store.encrypt_config_secrets(cfg)
        self.assertEqual(cfg["providers"]["openai"]["key"], "")
        self.assertEqual(cfg["providers"]["openai"]["keys"], [])

    def test_missing_paths_are_safe(self):
        cfg = {"agent": {"systemPrompt": "x"}}  # no secret sections at all
        secure_store.encrypt_config_secrets(cfg)  # must not raise
        secure_store.decrypt_config_secrets(cfg)
        self.assertEqual(cfg, {"agent": {"systemPrompt": "x"}})


if __name__ == "__main__":
    unittest.main()
