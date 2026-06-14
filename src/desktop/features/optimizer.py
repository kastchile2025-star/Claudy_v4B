"""Claudy features.optimizer — Optimización evolutiva ligera de prompts (A9).

Versión acotada del enfoque DSPy/GEPA: en vez de un loop de optimización
automático, un comando `/optimizar` lee las trazas recientes de debug.log,
agrupa los fallos recurrentes y le pide al LLM sugerencias concretas para
mejorar el system prompt y las SKILL.md. No aplica cambios solo: propone, y
Felipe decide.

El debug.log tiene bloques con el formato que escribe pet._debug_log:
    [ISO-timestamp] LABEL
    <data multilinea>
    <línea en blanco>

Mixin de ClawdPet: usa send_quick_message, load_claudy_config,
_skill_catalog_brief y el path estándar ~/.claudy/debug.log.
"""
import os
import re
from collections import Counter

# Labels que denotan un problema (no ruido informativo). Se comparan en mayúsculas.
_ERROR_HINTS = ("ERROR", "FAIL", "RETRY", "EXCEPTION", "TIMEOUT", "DENIED",
                "NO DISPONIBLE", "NOT FOUND", "INVALID")

_BLOCK_RX = re.compile(
    r"^\[(?P<ts>[\d\-T:\.]+)\]\s*(?P<label>.+?)\n(?P<data>.*?)(?=^\[\d{4}-|\Z)",
    re.S | re.M)


def parse_debug_blocks(text):
    """Devuelve [(timestamp, label, data)] de un volcado de debug.log."""
    out = []
    for m in _BLOCK_RX.finditer(text or ""):
        out.append((m.group("ts"), m.group("label").strip(), m.group("data").strip()))
    return out


def summarize_failures(blocks):
    """Agrupa los bloques que parecen fallos. Devuelve (conteo_por_label, ejemplos)."""
    counter = Counter()
    examples = {}
    for ts, label, data in blocks:
        blob = f"{label} {data}".upper()
        if any(h in blob for h in _ERROR_HINTS):
            counter[label] += 1
            if label not in examples:
                examples[label] = data[:300]
    return counter, examples


class OptimizerMixin:

    def _debug_log_path(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", "debug.log")

    def _read_recent_debug(self, max_bytes=60000):
        """Lee la cola del debug.log (los bloques más recientes)."""
        path = self._debug_log_path()
        if not os.path.isfile(path):
            return ""
        try:
            size = os.path.getsize(path)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                if size > max_bytes:
                    f.seek(size - max_bytes)
                    f.readline()  # descarta la línea parcial inicial
                return f.read()
        except Exception:
            return ""

    def _optimize_prompts(self):
        """Comando /optimizar: analiza fallos recientes y sugiere mejoras.
        Devuelve el texto a mostrar en el chat (no aplica cambios)."""
        raw = self._read_recent_debug()
        if not raw.strip():
            return ("No hay trazas en debug.log todavía. Úsame un rato y vuelve a "
                    "intentar /optimizar para que tenga fallos reales que analizar.")
        blocks = parse_debug_blocks(raw)
        counter, examples = summarize_failures(blocks)
        if not counter:
            return (f"Revisé {len(blocks)} trazas recientes y no veo fallos "
                    "recurrentes. Los prompts parecen estar funcionando bien. 👍")

        # Resumen de los fallos más frecuentes para el LLM.
        top = counter.most_common(6)
        failures_txt = "\n".join(
            f"- {label}: {n} veces. Ejemplo: {examples.get(label, '')[:200]}"
            for label, n in top)

        try:
            system_prompt = (self.load_claudy_config()
                             .get("agent", {}).get("systemPrompt", ""))[:1500]
        except Exception:
            system_prompt = ""
        try:
            catalog = self._skill_catalog_brief()
        except Exception:
            catalog = "(no disponible)"

        prompt = (
            "Eres un optimizador de prompts (estilo DSPy/GEPA, versión ligera). "
            "Analiza estos FALLOS RECURRENTES extraídos de las trazas de ejecución "
            "de un asistente personal y propón mejoras CONCRETAS y accionables.\n\n"
            f"SYSTEM PROMPT ACTUAL (extracto):\n{system_prompt or '(vacío)'}\n\n"
            f"SKILLS INSTALADAS:\n{catalog}\n\n"
            f"FALLOS RECURRENTES (label: veces):\n{failures_txt}\n\n"
            "Para cada problema relevante, indica: (1) causa probable, (2) un "
            "ajuste específico al system prompt o a una SKILL.md (cita el texto a "
            "añadir/cambiar). Sé conciso y práctico. Si un fallo es de "
            "infraestructura (red, API) y no de prompt, dilo y no inventes un "
            "cambio de prompt. No reescribas el prompt entero; propón parches."
        )
        try:
            suggestion = self.send_quick_message(
                prompt, _skip_skill_action=True, timeout=120,
                max_tokens=1500, tier="fast")
        except Exception as e:
            return f"No pude generar sugerencias: {e}"

        total_fails = sum(counter.values())
        return (f"🔧 Optimización de prompts — analicé {len(blocks)} trazas, "
                f"{total_fails} fallos en {len(counter)} categorías:\n\n"
                f"{(suggestion or '').strip()}\n\n"
                "— Son propuestas; ningún cambio se aplicó solo. "
                "Dime cuáles aplico.")
