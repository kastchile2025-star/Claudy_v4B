"""Claudy core.skill_vetting — Validación de skills de terceros (B6).

Lección de OpenClaw: instalar skills sin validar terminó en CVEs y plugins
maliciosos. El SKILL.md instalado se inyecta al SYSTEM PROMPT de Claudy en
cada conversación — es el vector perfecto para secuestrar al asistente.

vet_skill(md_text) → (verdict, reasons)
  "block" : intentos de inyección de prompts (core/injection_guard) o
            comandos catastróficos (core/command_guard). No se instala
            salvo «confiar» explícito del usuario.
  "warn"  : estructura sospechosa (sin frontmatter, blobs base64, URLs
            con IP pelada). Se instala, pero avisando.
  "ok"    : pasa limpia.

La defensa es en capas: aunque una skill instruya comandos, el guard
Manual/Smart/YOLO los gatea en ejecución; aquí se corta lo que apunta a
reescribir las directrices del modelo.
"""
import re

MAX_SKILL_BYTES = 60_000


def vet_skill(md_text):
    """(verdict, reasons) para el contenido de un SKILL.md de terceros."""
    text = md_text or ""
    block, warn = [], []

    if len(text.encode("utf-8", "ignore")) > MAX_SKILL_BYTES:
        block.append(f"tamaño excesivo (> {MAX_SKILL_BYTES // 1000} KB)")

    try:
        from core.injection_guard import scan_injection
        hits = scan_injection(text)
        for cat, frag in hits[:5]:
            block.append(f"inyección de prompt ({cat}): «{frag[:80]}»")
    except Exception:
        warn.append("no pude correr el filtro anti-inyección")

    try:
        from core.command_guard import check_blocked
        for line in text.splitlines():
            reason = check_blocked(line)
            if reason:
                block.append(f"comando catastrófico: {reason}")
    except Exception:
        warn.append("no pude correr el filtro de comandos")

    if not re.search(r"^name:\s*\S+", text, re.M):
        warn.append("sin frontmatter 'name:' (no parece una skill estándar)")
    if re.search(r"[A-Za-z0-9+/=]{120,}", text):
        warn.append("contiene un blob tipo base64 (posible payload ofuscado)")
    if re.search(r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", text):
        warn.append("apunta a una IP pelada en vez de un dominio")

    if block:
        return "block", block
    if warn:
        return "warn", warn
    return "ok", []


def format_vet_report(verdict, reasons):
    if verdict == "block":
        return ("⛔ Skill RECHAZADA por seguridad:\n  - " + "\n  - ".join(reasons)
                + "\n\nSi confías plenamente en la fuente: /skill install <fuente> confiar")
    if verdict == "warn":
        return "⚠️ Instalada con advertencias:\n  - " + "\n  - ".join(reasons)
    return ""
