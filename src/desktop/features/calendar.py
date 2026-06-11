"""Claudy features.calendar — Intent /agendar con Google Calendar (refactor v5).

Interpreta "agéndame reunión con X el jueves a las 15" y crea el evento vía
google_calendar.py (OAuth). El panel de calendario de la UI usa WebViewApi.

Se usa como mixin: ClawdPet hereda de CalendarMixin.
"""
import datetime
import re


class CalendarMixin:
    def _handle_agendar(self, prompt):
        """Crea una reunión en Google Calendar desde texto en español.
        Ej: /agendar Reunión con Jean Paul el 10 de junio a las 15:30 jeanpaul.harb@combas.cl"""
        try:
            import google_calendar as gcal
        except Exception as e:
            return f"No pude cargar el módulo de calendario: {e}"
        st = gcal.status()
        if not st.get("connected"):
            reason = st.get("reason")
            if reason == "falta-credencial":
                return ("Aún no conectas Google Calendar. Crea un cliente OAuth de escritorio y guarda "
                        f"el client_secret en:\n{gcal.CLIENT_SECRET_FILE}\n"
                        "Luego abre el panel Calendario (botón) y pulsa 'Conectar'.")
            if reason == "no-autorizado":
                return "Falta autorizar Google Calendar. Abre el panel Calendario y pulsa 'Conectar Google Calendar'."
            return f"Google Calendar no está disponible: {reason}"

        text = prompt
        low = text.lower()
        now = datetime.datetime.now()

        # ── Fecha ──
        date = None
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
        if m:
            try:
                date = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except Exception:
                date = None
        if not date:
            m = re.search(r'\b(\d{1,2})\s*/\s*(\d{1,2})(?:\s*/\s*(\d{2,4}))?\b', text)
            if m:
                d, mo = int(m.group(1)), int(m.group(2))
                y = int(m.group(3)) if m.group(3) else now.year
                if y < 100:
                    y += 2000
                try:
                    date = datetime.date(y, mo, d)
                except Exception:
                    date = None
        if not date:
            m = re.search(r'\b(\d{1,2})\s+de\s+([a-záéíóú]+)', low)
            if m and m.group(2) in self._MESES:
                d, mo = int(m.group(1)), self._MESES[m.group(2)]
                try:
                    date = datetime.date(now.year, mo, d)
                    if date < now.date():
                        date = datetime.date(now.year + 1, mo, d)
                except Exception:
                    date = None
        if not date:
            if "mañana" in low or "manana" in low:
                date = (now + datetime.timedelta(days=1)).date()
            elif "hoy" in low:
                date = now.date()

        # ── Hora ──
        hh = mm = None
        m = re.search(r'a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', low)
        if m:
            hh, mm = int(m.group(1)), int(m.group(2) or 0)
            ampm = (m.group(3) or "")
            if ampm == "pm" and hh < 12:
                hh += 12
            if ampm == "am" and hh == 12:
                hh = 0
        else:
            m = re.search(r'\b(\d{1,2}):(\d{2})\b', low)
            if m:
                hh, mm = int(m.group(1)), int(m.group(2))

        if not date or hh is None:
            return ("Para agendar dime al menos fecha y hora. Ej:\n"
                    "/agendar Reunión con Jean Paul el 10 de junio a las 15:30 correo@dominio.cl")

        # ── Invitados ──
        attendees = re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', text)

        # ── Título (limpia disparadores, fecha, hora, correos) ──
        title = re.sub(r'^/agendar\s*', '', text, flags=re.IGNORECASE)
        title = re.sub(r'\b(ag[eé]ndame|agendame|agenda|agendar)\b', '', title, flags=re.IGNORECASE)
        for a in attendees:
            title = title.replace(a, '')
        title = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '', title)
        title = re.sub(r'\b\d{1,2}\s*/\s*\d{1,2}(?:\s*/\s*\d{2,4})?\b', '', title)
        title = re.sub(r'\bel\s+', ' ', title, flags=re.IGNORECASE)
        title = re.sub(r'\b\d{1,2}\s+de\s+[a-záéíóú]+', '', title, flags=re.IGNORECASE)
        title = re.sub(r'a\s+las?\s+\d{1,2}(?::\d{2})?\s*(am|pm)?', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\b(mañana|manana|hoy)\b', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+', ' ', title).strip(" .,-")
        if not title:
            title = "Reunión"

        start_iso = f"{date.isoformat()}T{hh:02d}:{(mm or 0):02d}:00"
        res = gcal.create_event(summary=title, start_iso=start_iso, attendees=attendees, add_meet=True)
        if res.get("ok"):
            cuando = f"{date.strftime('%d/%m/%Y')} {hh:02d}:{(mm or 0):02d}"
            inv = (" · invitados: " + ", ".join(attendees)) if attendees else ""
            link = res.get("hangoutLink") or res.get("htmlLink") or ""
            return f"✅ Reunión agendada: «{title}» el {cuando}{inv}.\n{link}"
        return f"No pude agendar: {res.get('reason', 'error')}"

