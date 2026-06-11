"""Claudy core.command_guard — Filtro de seguridad de comandos (A3+B5).

Tres modos de ejecución (config.json → agent.commandMode):

  manual : todo comando pide confirmación, salvo los de solo lectura.
  smart  : (default) los de solo lectura pasan solos; el resto lo evalúa un
           LLM barato (tier="fast"). SEGURO → ejecuta; cualquier otra cosa,
           timeout o error → pide confirmación (fail-closed).
  yolo   : ejecuta sin preguntar… excepto la lista negra.

La LISTA NEGRA es permanente: comandos catastróficos (formatear, borrar
raíces, fork bombs, shadow copies, registro HKLM, download-and-run
ofuscado) NO se ejecutan en NINGÚN modo, ni siquiera en yolo.

B5 (lección de OpenClaw): lo no destructivo se auto-aprueba — READONLY_PATTERNS
define los comandos de solo lectura. Un comando compuesto (&&, |, ;) solo es
readonly si TODOS sus tramos lo son y no redirige salida a archivo (>).

Se usa como mixin: ClawdPet hereda de CommandGuardMixin. Depende de
_execute_command_raw (el ejecutor real en pet.py) y send_quick_message
(evaluación smart). La confirmación pendiente la resuelve
_guard_try_confirm, llamado al inicio de _try_handle_skill_action.
"""
import json
import os
import re
import time

GUARD_MODES = ("manual", "smart", "yolo")
DEFAULT_MODE = "smart"
CONFIRM_TTL = 120  # segundos de validez de una confirmación pendiente

# ── Lista negra permanente: (regex, motivo). Fail-closed en TODOS los modos ──
BLOCKED_PATTERNS = [
    (r"\brm\s+(?:-[a-zA-Z]+\s+)*-[a-zA-Z]*(?:rf|fr)[a-zA-Z]*\s+[\"']?(?:/|~|\*|[a-zA-Z]:[\\/]?)[\"']?\s*$",
     "rm -rf sobre la raíz, el home o todo (*)"),
    (r"--no-preserve-root", "rm sin protección de raíz"),
    (r"\b(?:del|erase)\b.*\s/s\b.*\s[\"']?[a-zA-Z]:\\?[\"']?\s*$",
     "del /s sobre la raíz de una unidad"),
    (r"\b(?:rd|rmdir)\b.*\s/s\b.*\s[\"']?[a-zA-Z]:\\?[\"']?\s*$",
     "rmdir /s sobre la raíz de una unidad"),
    (r"\bremove-item\b.*-recurse\b.*[\"']?[a-zA-Z]:\\[\"']?(?:\s|$)",
     "Remove-Item -Recurse sobre la raíz de una unidad"),
    (r"\bformat(?:\.com)?\s+[a-zA-Z]:", "formatear una unidad"),
    (r"\bmkfs(?:\.\w+)?\b", "crear un sistema de archivos (mkfs)"),
    (r"\bdd\b.*\bof=/dev/", "escribir directo a un dispositivo (dd)"),
    (r":\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:", "fork bomb (bash)"),
    (r"%0\s*\|\s*%0", "fork bomb (batch)"),
    (r"\bvssadmin\b.*\bdelete\b", "borrar shadow copies (vssadmin)"),
    (r"\bwbadmin\b.*\bdelete\b", "borrar copias de seguridad (wbadmin)"),
    (r"\bbcdedit\b", "modificar la configuración de arranque"),
    (r"\bcipher\s+/w", "borrado irrecuperable (cipher /w)"),
    (r"\bdiskpart\b", "edición de particiones (diskpart)"),
    (r"\breg(?:\.exe)?\s+delete\s+[\"']?hk(?:lm|ey_local_machine)",
     "borrar claves del registro HKLM"),
    (r"\bset-mppreference\b.*disable", "desactivar Windows Defender"),
    (r"\bnetsh\b.*firewall\b.*\b(?:off|disable)\b", "apagar el firewall"),
    (r"\bpowershell(?:\.exe)?\b.*\s-e(?:c|nc|ncodedcommand)?\s+[A-Za-z0-9+/=]{16,}",
     "PowerShell con comando codificado (ofuscación)"),
    (r"\b(?:iwr|invoke-webrequest|curl|wget)\b.*\|\s*(?:iex|invoke-expression|sh|bash|cmd)\b",
     "descargar y ejecutar al vuelo"),
    (r"\bshutdown(?:\.exe)?\b", "apagar/reiniciar el equipo"),
    (r"\b(?:restart|stop)-computer\b", "apagar/reiniciar el equipo"),
    (r"\btaskkill\b.*\s/f\b", "matar procesos a la fuerza"),
    (r"\bnet\s+user\b.*\s/(?:add|delete|active)", "crear/borrar/alterar usuarios"),
    (r"\bnet\s+localgroup\s+administrators\b.*\s/add", "escalar privilegios de administrador"),
    (r"\bschtasks\b.*\s/delete\b.*\s/f\b", "borrar tareas programadas a la fuerza"),
    (r"\btakeown\b.*/f\s+[\"']?[a-zA-Z]:\\[\"']?(?:\s|$)", "apropiarse de la raíz de una unidad"),
]
_BLOCKED = [(re.compile(p, re.IGNORECASE), reason) for p, reason in BLOCKED_PATTERNS]

# ── Solo lectura (B5): se auto-aprueban en cualquier modo. Anclados al inicio ──
READONLY_PATTERNS = [
    r"dir(?:\s|$)", r"ls(?:\s|$)", r"tree(?:\s|$)", r"type\s", r"more\s", r"cat\s",
    r"where(?:\.exe)?\s", r"whoami(?:\s|$)", r"hostname(?:\s|$)", r"systeminfo(?:\s|$)",
    r"ver(?:\s|$)", r"vol(?:\s|$)", r"echo\s", r"tasklist(?:\s|$)", r"ipconfig(?:\s|$)",
    r"ping\s", r"tracert\s", r"netstat(?:\s|$)", r"nslookup\s", r"arp\s",
    r"findstr\s", r"find\s", r"fc\s", r"comp\s", r"date\s+/t", r"time\s+/t",
    r"git\s+(?:status|log|diff|show|branch|remote|tag|describe|stash\s+list)\b",
    r"get-\w+", r"select-string\s", r"test-path\s", r"measure-object",
    r"python3?\s+--version", r"pip3?\s+(?:list|show|freeze)\b",
    r"node\s+(?:--version|-v)\b", r"npm\s+(?:ls|list|view|outdated)\b",
    r"wmic\s+\w+\s+get\b",
]
_READONLY = [re.compile(p, re.IGNORECASE) for p in READONLY_PATTERNS]

_CONFIRM_WORDS = {
    "si", "sí", "yes", "dale", "ok", "okey", "hazlo", "ejecuta", "ejecutalo",
    "ejecútalo", "confirmo", "confirmar", "/confirmar", "si, ejecuta",
    "sí, ejecuta", "si ejecutalo", "sí ejecútalo", "adelante",
}
_CANCEL_WORDS = {
    "no", "cancela", "cancelar", "/cancelar", "no lo hagas", "mejor no", "para",
}


def check_blocked(cmd):
    """Motivo del bloqueo permanente, o None si el comando no está en la lista."""
    text = (cmd or "").strip()
    for rx, reason in _BLOCKED:
        if rx.search(text):
            return reason
    return None


def is_readonly(cmd):
    """True solo si TODOS los tramos del comando son de solo lectura.

    Un `>` o `>>` escribe a archivo → no es readonly. Los tramos se separan
    por &&, ||, |, ; y & (en cmd.exe encadenan comandos).
    """
    text = (cmd or "").strip()
    if not text or ">" in text:
        return False
    for segment in re.split(r"&&|\|\||\||;|&", text):
        segment = segment.strip()
        if not segment:
            return False
        if not any(rx.match(segment) for rx in _READONLY):
            return False
    return True


class CommandGuardMixin:

    # ── Modo: lectura/escritura en config.json (agent.commandMode) ──
    def _guard_config_path(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", "config.json")

    def _guard_get_mode(self):
        cached = getattr(self, "_guard_mode_value", None)
        if cached in GUARD_MODES:
            return cached
        try:
            with open(self._guard_config_path(), "r", encoding="utf-8-sig") as f:
                mode = (json.load(f).get("agent", {}).get("commandMode") or "").lower()
        except Exception:
            mode = ""
        self._guard_mode_value = mode if mode in GUARD_MODES else DEFAULT_MODE
        return self._guard_mode_value

    def _guard_set_mode(self, mode):
        mode = (mode or "").strip().lower()
        if mode not in GUARD_MODES:
            return f"Modo desconocido: '{mode}'. Usa: manual | smart | yolo"
        path = self._guard_config_path()
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data.setdefault("agent", {})["commandMode"] = mode
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"No pude guardar el modo en config.json: {e}"
        self._guard_mode_value = mode
        avisos = {
            "manual": "Todo comando pedirá tu confirmación (salvo los de solo lectura).",
            "smart": "Un evaluador rápido decide; lo dudoso pide tu OK (fail-closed).",
            "yolo": "⚠️ Los comandos se ejecutan sin preguntar. La lista negra sigue activa.",
        }
        return f"Modo de comandos: {mode}. {avisos[mode]}"

    def _guard_cmd(self, arg):
        """Slash /permisos: sin argumento muestra el estado; con argumento cambia el modo."""
        arg = (arg or "").strip().lower()
        if not arg:
            return (f"Modo de comandos actual: {self._guard_get_mode()}\n\n"
                    "  manual — todo comando pide confirmación (salvo solo lectura)\n"
                    "  smart  — un LLM rápido evalúa el riesgo; lo dudoso pide OK\n"
                    "  yolo   — ejecuta sin preguntar (la lista negra sigue activa)\n\n"
                    "Cambiar: /permisos manual | smart | yolo")
        return self._guard_set_mode(arg)

    # ── Puerta de ejecución ──
    def _guard_execute(self, cmd):
        """Única puerta hacia _execute_command_raw. Decide según lista negra,
        solo-lectura (B5) y el modo activo."""
        cmd = (cmd or "").strip()
        if not cmd:
            return "No hay comando que ejecutar."
        reason = check_blocked(cmd)
        if reason:
            return ("⛔ Comando bloqueado por la lista negra de seguridad: "
                    f"{reason}. No se ejecuta en ningún modo.\n  $ {cmd[:200]}")
        if is_readonly(cmd):
            return self._execute_command_raw(cmd)
        mode = self._guard_get_mode()
        if mode == "yolo":
            return self._execute_command_raw(cmd)
        if mode == "smart":
            safe, why = self._guard_smart_assess(cmd)
            if safe:
                return self._execute_command_raw(cmd)
            return self._guard_request_confirmation(cmd, why)
        return self._guard_request_confirmation(cmd, "modo manual: todo comando requiere tu OK")

    def _guard_smart_assess(self, cmd):
        """(seguro, motivo) usando el LLM rápido. Fail-closed: error, timeout
        o respuesta ambigua cuentan como NO seguro."""
        prompt = (
            "Eres un filtro de seguridad. Evalúa si este comando de consola de "
            "Windows es seguro para ejecutarse automáticamente en el PC del usuario.\n"
            "SEGURO = solo lee información o hace cambios triviales y reversibles.\n"
            "RIESGOSO = borra o modifica archivos, instala software, cambia "
            "configuración del sistema, mata procesos, toca el registro, descarga "
            "y ejecuta, o tienes cualquier duda.\n\n"
            f"Comando: {cmd}\n\n"
            "Responde UNA sola palabra: SEGURO o RIESGOSO."
        )
        try:
            out = self.send_quick_message(
                prompt, _skip_skill_action=True, timeout=25, max_tokens=12, tier="fast") or ""
        except Exception:
            return False, "no pude evaluar el riesgo (fail-closed)"
        word = out.strip().split()[0].upper().strip(".,:;!¡\"'") if out.strip() else ""
        if word == "SEGURO":
            return True, ""
        if word == "RIESGOSO":
            return False, "el evaluador lo marcó como riesgoso"
        return False, "respuesta ambigua del evaluador (fail-closed)"

    def _guard_request_confirmation(self, cmd, why=""):
        self._guard_pending = {"cmd": cmd, "ts": time.time()}
        extra = f"\nMotivo: {why}." if why else ""
        return ("⚠️ Este comando necesita tu confirmación "
                f"(modo {self._guard_get_mode()}):{extra}\n\n"
                f"  $ {cmd}\n\n"
                "Responde «sí» (o /confirmar) para ejecutarlo, «no» para cancelar. "
                "Expira en 2 minutos.")

    def _guard_try_confirm(self, prompt, lower):
        """Resuelve una confirmación pendiente. Se llama al inicio del ruteo de
        intents. Devuelve (True, resultado) si el mensaje era el sí/no."""
        pending = getattr(self, "_guard_pending", None)
        if not pending:
            return False, None
        norm = lower.strip().strip(".!¡¿?")
        if norm in _CANCEL_WORDS:
            self._guard_pending = None
            return True, "Cancelado. No ejecuté nada."
        if norm in _CONFIRM_WORDS:
            self._guard_pending = None
            if time.time() - pending["ts"] > CONFIRM_TTL:
                return True, ("La confirmación expiró (pasaron más de 2 minutos). "
                              "Vuelve a pedir el comando si aún lo quieres.")
            return True, self._execute_command_raw(pending["cmd"])
        return False, None
