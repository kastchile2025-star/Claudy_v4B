"""Encryption-at-rest for Claudy's secrets in ``~/.claudy/config.json``.

Tokens (DeepSeek/OpenAI/Anthropic/Telegram/Discord keys, SMTP password, etc.)
were previously stored in plaintext. This module encrypts those specific fields
with Fernet (AES-128-CBC + HMAC) using a per-machine key kept in
``~/.claudy/.secret.key``.

Design goals — must NEVER lock the user out:
  - Transparent: callers always work with plaintext in memory.
    :func:`decrypt_config_secrets` is applied right after the config is loaded.
  - Idempotent: encrypting an already-encrypted value is a no-op.
  - Graceful: if ``cryptography`` isn't installed, every function becomes a
    pass-through (values stay plaintext) instead of raising.
  - Format-tagged: encrypted values are prefixed ``enc:v1:`` so we can always
    tell ciphertext from plaintext and migrate safely.
"""

from __future__ import annotations

import os

PREFIX = "enc:v1:"
CLAUDY_DIR = os.path.join(os.path.expanduser("~"), ".claudy")
KEY_PATH = os.path.join(CLAUDY_DIR, ".secret.key")

# Config locations that hold secrets. A leaf may be a string or a list of
# strings (e.g. rotating key pools). Adjust here if new secret fields appear.
SECRET_PATHS = [
    ("opencode", "apiKey"),
    ("opencode", "password"),
    ("telegram", "botToken"),
    ("discord", "botToken"),
    ("discord", "token"),
    ("email", "smtp_pass"),
    ("openai", "key"),
    ("deepseek", "key"),
    ("anthropic", "key"),
    ("providers", "deepseek", "key"),
    ("providers", "deepseek", "keys"),
    ("providers", "openai", "key"),
    ("providers", "openai", "keys"),
    ("providers", "anthropic", "key"),
    ("providers", "anthropic", "keys"),
]

_fernet = None
_fernet_tried = False


def _harden_key_file(path: str) -> None:
    """Best-effort: hide the key file and restrict it to the current user."""
    try:
        import ctypes
        FILE_ATTRIBUTE_HIDDEN = 0x02
        ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        pass
    try:
        import getpass
        import subprocess
        user = getpass.getuser()
        subprocess.run(
            ["icacls", path, "/inheritance:r", "/grant:r", f"{user}:F"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


def _get_fernet():
    """Return a Fernet instance, creating the key on first use. None if the
    ``cryptography`` package isn't available."""
    global _fernet, _fernet_tried
    if _fernet_tried:
        return _fernet
    _fernet_tried = True
    try:
        from cryptography.fernet import Fernet
    except Exception:
        _fernet = None
        return None
    try:
        os.makedirs(CLAUDY_DIR, exist_ok=True)
        if os.path.exists(KEY_PATH):
            with open(KEY_PATH, "rb") as f:
                key = f.read().strip()
        else:
            key = Fernet.generate_key()
            with open(KEY_PATH, "wb") as f:
                f.write(key)
            _harden_key_file(KEY_PATH)
        _fernet = Fernet(key)
    except Exception:
        _fernet = None
    return _fernet


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt_str(value):
    """Encrypt a plaintext string. Returns the value unchanged if it's empty,
    already encrypted, not a string, or if encryption is unavailable."""
    if not isinstance(value, str) or not value or is_encrypted(value):
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        token = f.encrypt(value.encode("utf-8")).decode("ascii")
        return PREFIX + token
    except Exception:
        return value


def decrypt_str(value):
    """Decrypt a value produced by :func:`encrypt_str`. Returns the value
    unchanged if it isn't encrypted or can't be decrypted."""
    if not is_encrypted(value):
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        token = value[len(PREFIX):].encode("ascii")
        return f.decrypt(token).decode("utf-8")
    except Exception:
        return value


def _get_node(cfg, keys):
    node = cfg
    for k in keys[:-1]:
        if not isinstance(node, dict) or k not in node:
            return None, None
        node = node[k]
    if not isinstance(node, dict):
        return None, None
    return node, keys[-1]


def _apply(cfg, fn):
    """Apply ``fn`` (encrypt_str/decrypt_str) to every configured secret path.
    Mutates and returns ``cfg``. Handles both string leaves and list-of-strings."""
    if not isinstance(cfg, dict):
        return cfg
    for path in SECRET_PATHS:
        node, leaf = _get_node(cfg, path)
        if node is None or leaf not in node:
            continue
        val = node[leaf]
        if isinstance(val, list):
            node[leaf] = [fn(v) for v in val]
        else:
            node[leaf] = fn(val)
    return cfg


def encrypt_config_secrets(cfg):
    """Encrypt all secret fields in-place (idempotent)."""
    return _apply(cfg, encrypt_str)


def decrypt_config_secrets(cfg):
    """Decrypt all secret fields in-place (safe on plaintext)."""
    return _apply(cfg, decrypt_str)


def available() -> bool:
    """True if real encryption is active (the ``cryptography`` package loaded)."""
    return _get_fernet() is not None
