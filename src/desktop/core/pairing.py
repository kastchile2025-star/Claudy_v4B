"""Claudy core.pairing — Emparejamiento seguro de canales (A10).

Endurece la vinculación de usuarios nuevos al bot de Telegram. En vez de editar
allowedUsers a mano, Felipe genera en Desktop un código efímero y se lo da al
usuario, que lo envía al bot con "/vincular <código>". Al validarse, el uid se
agrega a la lista de autorizados.

Defensas (estilo Hermes):
  - Código de un solo uso con TTL corto (default 5 min).
  - Rate-limit: máximo N intentos por uid en una ventana.
  - Lockout temporal del uid tras demasiados intentos fallidos.
  - Estado en ~/.claudy/pairing.json con permisos 0600 (solo el dueño lee).

Este módulo es PURO (sin red ni Telegram): trabaja sobre un dict de estado y
relojes inyectables, lo que lo hace 100% testeable. El bot y Desktop solo lo
invocan.
"""
import json
import os
import secrets
import time

PAIRING_PATH = os.path.join(os.path.expanduser("~"), ".claudy", "pairing.json")

CODE_TTL = 300            # validez de un código de vinculación (5 min)
CODE_LENGTH = 6           # dígitos del código
MAX_ATTEMPTS = 5          # intentos fallidos antes del lockout
ATTEMPT_WINDOW = 600      # ventana de conteo de intentos (10 min)
LOCKOUT_SECONDS = 900     # duración del lockout (15 min)


def _now():
    return time.time()


def generate_code(state, ttl=CODE_TTL, now=None, length=CODE_LENGTH):
    """Crea un código de un solo uso y lo guarda en el estado. Devuelve el código.
    Reemplaza cualquier código pendiente anterior (solo uno activo a la vez)."""
    now = now if now is not None else _now()
    code = "".join(secrets.choice("0123456789") for _ in range(length))
    state["pending"] = {"code": code, "expires": now + ttl}
    return code


def _record_attempt(state, uid, now):
    attempts = state.setdefault("attempts", {})
    rec = attempts.get(str(uid))
    if not rec or now - rec.get("first", now) > ATTEMPT_WINDOW:
        rec = {"count": 0, "first": now}
    rec["count"] += 1
    rec["last"] = now
    attempts[str(uid)] = rec
    return rec


def is_locked(state, uid, now=None):
    """True si el uid está en lockout vigente."""
    now = now if now is not None else _now()
    lock = state.get("lockouts", {}).get(str(uid))
    return bool(lock and now < lock)


def verify_code(state, uid, code, now=None):
    """Valida un intento de vinculación. Devuelve (ok, mensaje). Muta el estado:
    consume el código si acierta, cuenta intentos y aplica lockout si falla mucho."""
    now = now if now is not None else _now()
    uid = str(uid)

    if is_locked(state, uid, now):
        remaining = int(state["lockouts"][uid] - now)
        return False, f"Demasiados intentos. Espera {remaining // 60 + 1} min e inténtalo de nuevo."

    pending = state.get("pending")
    code = (code or "").strip()

    # Sin código pendiente o expirado.
    if not pending or now > pending.get("expires", 0):
        _maybe_lock(state, _record_attempt(state, uid, now), uid, now)
        return False, "No hay un código de vinculación válido. Pide uno nuevo al dueño."

    if code and secrets.compare_digest(code, pending["code"]):
        # Acierto: consume el código y limpia el historial de intentos del uid.
        state.pop("pending", None)
        state.get("attempts", {}).pop(uid, None)
        state.get("lockouts", {}).pop(uid, None)
        authorized = state.setdefault("authorized", [])
        if uid not in authorized:
            authorized.append(uid)
        return True, "✅ Vinculación exitosa. Ya puedes conversar conmigo."

    # Fallo: cuenta el intento y quizá bloquea.
    rec = _record_attempt(state, uid, now)
    locked = _maybe_lock(state, rec, uid, now)
    if locked:
        return False, "Demasiados intentos fallidos. Quedaste bloqueado temporalmente."
    left = MAX_ATTEMPTS - rec["count"]
    return False, f"Código incorrecto. Te quedan {max(0, left)} intentos."


def _maybe_lock(state, rec, uid, now):
    """Aplica lockout si el uid superó MAX_ATTEMPTS en la ventana. Devuelve True
    si quedó bloqueado."""
    if rec["count"] >= MAX_ATTEMPTS:
        state.setdefault("lockouts", {})[str(uid)] = now + LOCKOUT_SECONDS
        state.get("attempts", {}).pop(str(uid), None)
        return True
    return False


# ── Persistencia con permisos restringidos ─────────────────────────────────
def load_state(path=PAIRING_PATH):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state, path=PAIRING_PATH):
    """Escritura atómica + chmod 0600 (best-effort en Windows)."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass  # En Windows chmod es limitado; el archivo vive en el perfil del usuario.
        return True
    except Exception:
        return False
