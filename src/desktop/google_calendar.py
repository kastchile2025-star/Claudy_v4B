"""
google_calendar.py — Integración de Claudy con Google Calendar.

Diseñado para fallar suave: si faltan las librerías de Google o el archivo de
credenciales, las funciones devuelven {"connected": False, "reason": ...} en vez
de romper. La UI muestra ese estado ("Conecta Google Calendar").

Credenciales (las pone el usuario):
  ~/.claudy/google_client_secret.json   ← cliente OAuth tipo "App de escritorio"
Token (se genera solo tras autorizar):
  ~/.claudy/google_calendar_token.json

Scopes: lectura + creación de eventos.
"""

import os
import datetime

SCOPES = ["https://www.googleapis.com/auth/calendar"]

CLAUDY_DIR = os.path.join(os.path.expanduser("~"), ".claudy")
CLIENT_SECRET_FILE = os.path.join(CLAUDY_DIR, "google_client_secret.json")
TOKEN_FILE = os.path.join(CLAUDY_DIR, "google_calendar_token.json")

PIP_HINT = "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"


def _import_google():
    """Importa las libs de Google de forma perezosa. Devuelve (mods, error)."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        return {
            "Credentials": Credentials,
            "InstalledAppFlow": InstalledAppFlow,
            "Request": Request,
            "build": build,
        }, None
    except Exception:
        return None, f"Faltan librerías de Google. Instala con:\n{PIP_HINT}"


def _load_creds(mods):
    """Carga credenciales válidas (refresca si expira). Devuelve (creds, error)."""
    Credentials = mods["Credentials"]
    Request = mods["Request"]
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            creds = None
    if creds and creds.valid:
        return creds, None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds, None
        except Exception as e:
            return None, f"No se pudo refrescar el token: {e}"
    return None, "no-autorizado"


def _save_token(creds):
    os.makedirs(CLAUDY_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def _service():
    """Devuelve (service, error). service=None si no se puede conectar."""
    mods, err = _import_google()
    if err:
        return None, err
    if not os.path.exists(CLIENT_SECRET_FILE):
        return None, (
            "Falta el archivo de credenciales. Crea un cliente OAuth 'App de escritorio' "
            "en Google Cloud Console y guárdalo como:\n" + CLIENT_SECRET_FILE
        )
    creds, err = _load_creds(mods)
    if err == "no-autorizado":
        return None, "no-autorizado"
    if err:
        return None, err
    try:
        service = mods["build"]("calendar", "v3", credentials=creds, cache_discovery=False)
        return service, None
    except Exception as e:
        return None, f"Error creando el servicio de Calendar: {e}"


def status():
    """Estado de la conexión, sin abrir navegador."""
    mods, err = _import_google()
    if err:
        return {"connected": False, "reason": err, "needs_libs": True}
    if not os.path.exists(CLIENT_SECRET_FILE):
        return {"connected": False, "reason": "falta-credencial", "client_secret_path": CLIENT_SECRET_FILE}
    creds, err = _load_creds(mods)
    if err == "no-autorizado":
        return {"connected": False, "reason": "no-autorizado"}
    if err:
        return {"connected": False, "reason": err}
    return {"connected": True}


def connect():
    """Lanza el flujo OAuth (abre el navegador una vez) y guarda el token.
    Devuelve {"connected": True} o {"connected": False, "reason": ...}."""
    mods, err = _import_google()
    if err:
        return {"connected": False, "reason": err}
    if not os.path.exists(CLIENT_SECRET_FILE):
        return {"connected": False, "reason": "falta-credencial", "client_secret_path": CLIENT_SECRET_FILE}
    # Si ya hay token válido, no relanzar.
    st = status()
    if st.get("connected"):
        return st
    try:
        flow = mods["InstalledAppFlow"].from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        _save_token(creds)
        return {"connected": True}
    except Exception as e:
        return {"connected": False, "reason": f"Fallo al autorizar: {e}"}


def _fmt_event(ev):
    start = ev.get("start", {})
    end = ev.get("end", {})
    start_val = start.get("dateTime") or start.get("date") or ""
    end_val = end.get("dateTime") or end.get("date") or ""
    return {
        "id": ev.get("id"),
        "summary": ev.get("summary", "(sin título)"),
        "start": start_val,
        "end": end_val,
        "allDay": "date" in start and "dateTime" not in start,
        "location": ev.get("location", ""),
        "htmlLink": ev.get("htmlLink", ""),
        "attendees": [a.get("email") for a in ev.get("attendees", []) if a.get("email")],
        "hangoutLink": ev.get("hangoutLink", ""),
    }


def list_upcoming(max_results=15, days_ahead=30):
    """Lista próximos eventos. Devuelve {"connected": bool, "events": [...], "reason": ...}."""
    service, err = _service()
    if err:
        return {"connected": False, "reason": err, "events": []}
    try:
        now = datetime.datetime.utcnow().isoformat() + "Z"
        end = (datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)).isoformat() + "Z"
        res = service.events().list(
            calendarId="primary", timeMin=now, timeMax=end,
            maxResults=max_results, singleEvents=True, orderBy="startTime",
        ).execute()
        events = [_fmt_event(e) for e in res.get("items", [])]
        return {"connected": True, "events": events}
    except Exception as e:
        return {"connected": False, "reason": f"Error listando eventos: {e}", "events": []}


def create_event(summary, start_iso, end_iso=None, description="", attendees=None,
                 location="", timezone="America/Santiago", add_meet=False):
    """Crea un evento. start_iso/end_iso en ISO local (ej. '2026-06-10T15:00:00').
    Si no hay end, dura 1 hora. attendees = lista de correos.
    Devuelve {"ok": bool, "htmlLink": ..., "reason": ...}."""
    service, err = _service()
    if err:
        return {"ok": False, "reason": err}
    try:
        if not end_iso:
            try:
                st = datetime.datetime.fromisoformat(start_iso)
                end_iso = (st + datetime.timedelta(hours=1)).isoformat()
            except Exception:
                end_iso = start_iso
        body = {
            "summary": summary,
            "description": description or "",
            "start": {"dateTime": start_iso, "timeZone": timezone},
            "end": {"dateTime": end_iso, "timeZone": timezone},
        }
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees if a]
        params = {"calendarId": "primary", "body": body, "sendUpdates": "all"}
        if add_meet:
            import uuid
            body["conferenceData"] = {
                "createRequest": {
                    "requestId": uuid.uuid4().hex,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
            params["conferenceDataVersion"] = 1
        ev = service.events().insert(**params).execute()
        return {
            "ok": True,
            "id": ev.get("id"),
            "htmlLink": ev.get("htmlLink", ""),
            "hangoutLink": ev.get("hangoutLink", ""),
            "summary": ev.get("summary", summary),
        }
    except Exception as e:
        return {"ok": False, "reason": f"Error creando el evento: {e}"}
