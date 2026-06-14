"""Claudy features.digest — Filtrado inteligente de notificaciones (C8).

Inspirado en Hold Assist / Call Screening de Apple: en vez de un goteo de
avisos sueltos (cron, watcher), Claudy los ACUMULA y los entrega en un solo
digest priorizado: "3 importantes, 5 ruido". Reduce la fatiga de notificaciones.

Pieza pura y testeable: una cola en memoria + clasificación heurística +
render del resumen. El bot/scheduler decide cuándo vaciar la cola (flush) y
mandar el texto resultante.

Clasificación (sin LLM, barata y predecible):
  - "alta"  : palabras de urgencia (error, falló, bajó/subió de umbral, caducó,
              vencido, pago, factura, alerta, crítico, stock).
  - "baja"  : el resto (heartbeats, "sin cambios", confirmaciones rutinarias).

Agrupa avisos repetidos del mismo origen (source) en una sola línea con conteo,
al estilo "resúmenes de cámaras del hogar": N avisos del mismo origen → 1 línea.
"""
import re
import time

_HIGH_PRIORITY_RX = re.compile(
    r"\b(error|fall[oó]|fallaron|cay[oó]|baj[oó]|subi[oó]|super[oó]|umbral|"
    r"caduc|venc|venci[oó]|pago|factura|alerta|cr[ií]tic|urgent|stock|agotad|"
    r"disponible|bloquead|exception|timeout)\w*", re.IGNORECASE)


def classify_priority(text):
    """'alta' si el aviso tiene señales de urgencia; 'baja' en caso contrario."""
    return "alta" if _HIGH_PRIORITY_RX.search(text or "") else "baja"


class NotificationDigest:
    """Cola de notificaciones con clasificación y agrupación por origen."""

    def __init__(self):
        self._items = []  # [{"text", "source", "priority", "ts"}]

    def add(self, text, source="general", now=None):
        text = (text or "").strip()
        if not text:
            return
        self._items.append({
            "text": text,
            "source": source or "general",
            "priority": classify_priority(text),
            "ts": now if now is not None else time.time(),
        })

    def pending_count(self):
        return len(self._items)

    def has_high_priority(self):
        return any(it["priority"] == "alta" for it in self._items)

    def render(self):
        """Texto del digest (sin vaciar la cola). '' si no hay nada."""
        if not self._items:
            return ""
        high = [it for it in self._items if it["priority"] == "alta"]
        low = [it for it in self._items if it["priority"] == "baja"]
        lines = [f"🔔 Resumen de avisos: {len(high)} importantes, {len(low)} de rutina."]

        if high:
            lines.append("\n⚠️ Importantes:")
            for it in high:
                lines.append(f"  • {it['text'][:160]}")

        if low:
            lines.append("\n· Rutina (agrupados):")
            # Agrupa los de baja prioridad por origen, con conteo.
            by_source = {}
            for it in low:
                by_source.setdefault(it["source"], []).append(it["text"])
            for source, texts in by_source.items():
                if len(texts) == 1:
                    lines.append(f"  • [{source}] {texts[0][:120]}")
                else:
                    lines.append(f"  • [{source}] {len(texts)} avisos "
                                 f"(último: {texts[-1][:80]})")
        return "\n".join(lines)

    def flush(self):
        """Devuelve el digest y vacía la cola."""
        out = self.render()
        self._items = []
        return out


class DigestMixin:
    """Engancha el digest al flujo de notificaciones del cron/watcher.

    Si telegram.digestNotifications está activo en config, las notificaciones
    de cron/watcher se acumulan en vez de enviarse sueltas, y se entregan con
    /avisos (manual) o cuando aparece un aviso de alta prioridad."""

    def _get_digest(self):
        if not hasattr(self, "_notification_digest"):
            self._notification_digest = NotificationDigest()
        return self._notification_digest

    def _digest_enabled(self):
        try:
            cfg = self.load_claudy_config()
            return bool(cfg.get("telegram", {}).get("digestNotifications", False))
        except Exception:
            return False

    def _queue_or_notify(self, text, source="cron"):
        """Punto de entrada del cron/watcher. Devuelve True si se encoló (no se
        envió ahora), False si debe enviarse de inmediato (modo digest off)."""
        if not self._digest_enabled():
            return False
        digest = self._get_digest()
        digest.add(text, source=source)
        # Entrega inmediata si llegó algo importante: no hacemos esperar lo urgente.
        if classify_priority(text) == "alta":
            out = digest.flush()
            try:
                # Envío directo (raw) para no re-encolar en _cron_notify_telegram.
                self._cron_send_telegram_raw(out)
            except Exception:
                pass
        return True

    def _deliver_digest(self):
        """Comando /avisos: entrega el digest acumulado ahora mismo."""
        digest = self._get_digest()
        if digest.pending_count() == 0:
            return "No hay avisos acumulados. 🎉"
        return digest.flush()
