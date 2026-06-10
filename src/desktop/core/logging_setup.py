"""Claudy core.logging_setup — Logging real con rotación (refactor v5).

Antes el diagnóstico era print() perdidos en consola y un debug.log manual.
Ahora: ~/.claudy/logs/claudy.log con rotación (1 MB x 5 archivos).

Uso:
    from core.logging_setup import get_logger
    log = get_logger("memoria")
    log.info("FTS5 inicializado")
"""
import logging
import logging.handlers
import os

_LOG_DIR = os.path.join(os.path.expanduser("~"), ".claudy", "logs")
_configured = False


def setup_logging(level=logging.INFO):
    """Configura el logger raíz de Claudy. Idempotente."""
    global _configured
    if _configured:
        return logging.getLogger("claudy")
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            os.path.join(_LOG_DIR, "claudy.log"),
            maxBytes=1_000_000, backupCount=5, encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root = logging.getLogger("claudy")
        root.setLevel(level)
        root.addHandler(handler)
        _configured = True
        return root
    except Exception:
        # Si el disco/permiso falla, degradar a consola sin romper la app
        logging.basicConfig(level=level)
        _configured = True
        return logging.getLogger("claudy")


def get_logger(name=""):
    setup_logging()
    return logging.getLogger(f"claudy.{name}" if name else "claudy")
