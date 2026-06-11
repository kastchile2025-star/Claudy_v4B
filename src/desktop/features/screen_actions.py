"""Claudy features.screen_actions — Screenshot accionable (C3/C4, estilo Siri AI).

"Agenda lo que está en pantalla" → Claudy captura la pantalla, la lee con el
modelo de visión (con fallback a Pollinations) y crea el evento en Google
Calendar. Caso estrella: un flyer, un correo o un WhatsApp visible con
fecha/hora se convierte en cita sin tipear nada.

Flujo (_screen_to_calendar):
  1. screenshot (PIL ImageGrab → ~/.claudy/screenshots/)
  2. visión: extraer el evento como JSON estricto (la fecha de HOY va en el
     prompt para resolver "mañana", "este viernes", etc.)
  3. parse_event_json + event_to_iso (helpers puros, testeables)
  4. google_calendar.create_event; si Calendar no está conectado, entrega
     igual lo que leyó para no perder el dato.

Se usa como mixin: ClawdPet hereda de ScreenActionsMixin. Depende de
_analyze_image_native y _debug_log de la clase compuesta.
"""
import datetime
import json
import os
import re

# Pide "evento" + referencia a la pantalla: así no choca con el NL normal de
# calendario ("agenda reunión mañana a las 10" sigue su camino de siempre).
SCREEN_EVENT_RX = re.compile(
    r"(?:ag[eé]nd\w*|crea\w*\s+(?:un\s+)?evento|"
    r"(?:agrega|añade|anota)\w*\s+(?:esto\s+)?(?:al?\s+)?calendario)"
    r".{0,60}?(?:pantalla|lo\s+que\s+(?:ves|se\s+ve|estoy\s+viendo)|esta\s+imagen)"
    r"|(?:pantalla|lo\s+que\s+ves).{0,40}?(?:ag[eé]nd\w*|al?\s+calendario)",
    re.IGNORECASE)

VISION_PROMPT = (
    "Hoy es {hoy}. Mira esta captura de pantalla y extrae UN evento agendable "
    "(reunión, cita, partido, concierto, vencimiento, clase...).\n"
    "Responde SOLO un JSON en una línea, sin texto extra ni fences:\n"
    '{{"found": true, "summary": "título corto", "date": "YYYY-MM-DD", '
    '"start": "HH:MM", "end": "HH:MM o null", "location": "lugar o vacío", '
    '"description": "detalle breve"}}\n'
    'Si la pantalla NO contiene nada agendable responde: {{"found": false}}\n'
    "Resuelve fechas relativas (mañana, este viernes) usando la fecha de hoy. "
    "Si no hay hora visible usa start=null."
)


def parse_event_json(text):
    """Extrae el dict del evento desde la respuesta del modelo de visión.
    Tolera fences, texto alrededor y JSON multilínea. None si no hay JSON."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def event_to_iso(data, now=None):
    """(start_iso, end_iso, aviso) desde el JSON del evento.
    Sin hora → 09:00 (con aviso); sin fin → +1 hora; fecha pasada este año no
    se corrige (el modelo ya recibió la fecha de hoy)."""
    now = now or datetime.datetime.now()
    fecha = (data.get("date") or "").strip()
    try:
        d = datetime.date.fromisoformat(fecha)
    except Exception:
        d = now.date()
    aviso = ""
    start_s = (data.get("start") or "").strip() if data.get("start") else ""
    if re.match(r"^\d{1,2}:\d{2}$", start_s):
        h, m = map(int, start_s.split(":"))
    else:
        h, m = 9, 0
        aviso = "No vi hora en pantalla: lo dejé a las 09:00, muévelo si corresponde."
    start = datetime.datetime(d.year, d.month, d.day, h, m)
    end_s = (data.get("end") or "").strip() if data.get("end") else ""
    if re.match(r"^\d{1,2}:\d{2}$", end_s):
        h2, m2 = map(int, end_s.split(":"))
        end = datetime.datetime(d.year, d.month, d.day, h2, m2)
        if end <= start:
            end += datetime.timedelta(days=1)
    else:
        end = start + datetime.timedelta(hours=1)
    return start.isoformat(), end.isoformat(), aviso


class ScreenActionsMixin:

    def _grab_screen(self):
        """Captura la pantalla a ~/.claudy/screenshots/ y devuelve la ruta."""
        from PIL import ImageGrab
        img = ImageGrab.grab()
        folder = os.path.join(os.path.expanduser("~"), ".claudy", "screenshots")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(
            folder, f"screen_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        img.save(path)
        return path

    def _screen_to_calendar(self, prompt=""):
        """'Agenda lo que está en pantalla' → screenshot → visión → evento GCal."""
        try:
            path = self._grab_screen()
        except Exception as e:
            return f"No pude capturar la pantalla: {e}"

        _dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        now = datetime.datetime.now()
        hoy = f"{_dias[now.weekday()]} {now.strftime('%d-%m-%Y')}"
        try:
            raw = self._analyze_image_native(path, VISION_PROMPT.format(hoy=hoy))
        except Exception as e:
            return f"No pude leer la pantalla con el modelo de visión: {e}"

        data = parse_event_json(raw)
        if not data:
            return ("Leí la pantalla pero no pude estructurar un evento. "
                    f"Esto fue lo que vi:\n{(raw or '')[:400]}")
        if not data.get("found"):
            return ("Miré la pantalla y no encontré nada agendable "
                    "(fecha + actividad). ¿Está visible el evento?")

        summary = (data.get("summary") or "Evento desde pantalla").strip()
        start_iso, end_iso, aviso = event_to_iso(data, now)
        location = (data.get("location") or "").strip()
        description = ((data.get("description") or "").strip()
                       + "\n\n(Creado por Claudy desde una captura de pantalla)")

        try:
            import google_calendar as gcal
            st = gcal.status()
            if not st.get("connected"):
                raise RuntimeError(st.get("reason") or "Calendar no conectado")
            result = gcal.create_event(
                summary=summary, start_iso=start_iso, end_iso=end_iso,
                description=description.strip(), location=location)
        except Exception as e:
            result = {"ok": False, "reason": str(e)}

        fecha_h = datetime.datetime.fromisoformat(start_iso).strftime("%d-%m-%Y %H:%M")
        detalle = (f"📅 {summary}\n🕐 {fecha_h}"
                   + (f"\n📍 {location}" if location else "")
                   + (f"\n⚠️ {aviso}" if aviso else ""))
        if result.get("ok"):
            link = result.get("htmlLink", "")
            return ("✅ Evento creado en tu Google Calendar:\n" + detalle
                    + (f"\n🔗 {link}" if link else ""))
        return ("Leí el evento en pantalla pero NO pude crearlo en Calendar "
                f"({result.get('reason', '?')}):\n" + detalle
                + "\n\nConecta Google Calendar desde el panel 📅 y vuelve a intentar.")
