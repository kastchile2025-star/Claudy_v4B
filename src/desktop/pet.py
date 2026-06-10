import base64
import ctypes
import datetime
import json
import math
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import winreg
from ctypes import wintypes

# Declare DPI awareness before any window/screen query so work_area and Tk geometry
# share the same coordinate space (physical pixels). Without this, work_area is read
# in scaled coords but Tk (auto-enables SystemAware) positions windows in physical
# pixels, leaving Claudy short of the actual screen edge on high-DPI displays.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Claudy"

TTS_OK = False
_tts_loaded = False
_tts_real_speak = None
_tts_real_stop = None

def _ensure_tts_loaded():
    # Lazy: edge_tts import can hang on startup (network).
    global TTS_OK, _tts_loaded, _tts_real_speak, _tts_real_stop
    if _tts_loaded:
        return
    _tts_loaded = True
    try:
        from tts import speak as s, stop_speaking as st
        _tts_real_speak = s
        _tts_real_stop = st
        TTS_OK = True
    except Exception:
        TTS_OK = False

def _tts_speak(*a, **k):
    _ensure_tts_loaded()
    if _tts_real_speak: _tts_real_speak(*a, **k)

def _tts_stop():
    _ensure_tts_loaded()
    if _tts_real_stop: _tts_real_stop()

try:
    from model_router import pick_model as _route_model
except Exception:
    def _route_model(_prompt, _config, fallback): return fallback

try:
    import secure_store as _secure
except Exception:
    _secure = None

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"])
    from PIL import Image, ImageDraw, ImageFilter, ImageTk

try:
    import webview
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview", "--quiet"])
    import webview

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_FRAMES = [os.path.join(SCRIPT_DIR, f"claudy_orbit_frame_{i}.png") for i in range(6)]
TRANSPARENT_COLOR = "#ff00ff"

# --- Theme system with multiple visual styles ---
# Sprite colors stay constant across themes (the pet doesn't restyle on theme switch).
_SPRITE_COLORS = {
    "body": (110, 120, 230, 255),
    "body_dark": (60, 65, 140, 255),
    "screen": (18, 18, 32, 255),
    "outline": (255, 255, 255, 255),
    "eye_glow": (120, 255, 210, 255),
    "fin": (255, 190, 100, 255),
}

THEMES = {
    "minimal": {
        "name": "Obsidian Clean",
        "bg_bubble": "#0a0a0c",
        "bg_bubble_border": "#27272a",
        "bg_input": "#0f0f12",
        "bg_input_border": "#27272a",
        "text_primary": "#f4f4f5",
        "text_secondary": "#a1a1aa",
        "text_label": "#71717a",
        "accent": "#ffffff",
        "accent_glow": "#a1a1aa",
        "accent_dim": "#27272a",
        "divider": "#1f1f23",
        "panel_bg": "#0a0a0c",
        "panel_soft": "#0f0f12",
        "message_bot": "#0f0f12",
        "message_bot_border": "#27272a",
        "header_bg": "#0a0a0c",
        "header_chip": "#0f0f12",
        "button_bg": "#0a0a0c",
        "button_fg": "#a1a1aa",
        "button_hover": "#18181b",
        "style": "minimal",
        **_SPRITE_COLORS,
    },
    "glass": {
        "name": "Nocturne",
        "bg_bubble": "#070b1e",
        "bg_bubble_border": "#304f9e",
        "bg_input": "#0d1637",
        "bg_input_border": "#4866d7",
        "text_primary": "#f7f7ff",
        "text_secondary": "#cabdff",
        "text_label": "#8fa4ff",
        "accent": "#c02dff",
        "accent_glow": "#58c7ff",
        "accent_dim": "#18234f",
        "divider": "#4f2cc8",
        "panel_bg": "#050817",
        "panel_soft": "#0b1231",
        "message_bot": "#1a1838",
        "message_bot_border": "#6a37d7",
        "header_bg": "#081128",
        "header_chip": "#0a1331",
        "button_bg": "#18163a",
        "button_fg": "#e5deff",
        "button_hover": "#2a1f63",
        "style": "glass",
        **_SPRITE_COLORS,
    },
    "terminal": {
        "name": "Terminal",
        "bg_bubble": "#0b0d0b",
        "bg_bubble_border": "#1b211b",
        "bg_input": "#070907",
        "bg_input_border": "#243024",
        "text_primary": "#dfe6dc",
        "text_secondary": "#7a8e76",
        "text_label": "#4d5d49",
        "accent": "#a5e08a",
        "accent_glow": "#e9d977",
        "accent_dim": "#23331f",
        "divider": "#15191a",
        "style": "terminal",
        **_SPRITE_COLORS,
    },
    "editorial": {
        "name": "Editorial",
        # Warm paper (tinted toward red-brown).
        "bg_bubble": "#f7f3eb",
        "bg_bubble_border": "#ece2cc",
        "bg_input": "#fbf8f1",
        "bg_input_border": "#d9c9a8",
        "text_primary": "#1f1814",
        "text_secondary": "#6b5a4a",
        "text_label": "#8d7d6c",
        "accent": "#a13629",
        "accent_glow": "#d4762b",
        "accent_dim": "#e8d4cf",
        "divider": "#e3d6bd",
        "style": "editorial",
        **_SPRITE_COLORS,
    },
    "vintage": {
        "name": "Pergamino",
        "bg_bubble": "#3d3429",
        "bg_bubble_border": "#5a4e3d",
        "bg_input": "#2e2820",
        "bg_input_border": "#6b5d4a",
        "text_primary": "#2c1810",
        "text_secondary": "#6b5744",
        "input_fg": "#e6d5b8",
        "text_label": "#8a7b68",
        "accent": "#8b4513",
        "accent_glow": "#a0522d",
        "accent_dim": "#5a4e3d",
        "divider": "#a89878",
        "panel_bg": "#d4c5a0",
        "panel_soft": "#c4b590",
        "message_bot": "#cbb98f",
        "message_bot_border": "#a89878",
        "header_bg": "#b0a080",
        "header_chip": "#2e2820",
        "button_bg": "#a89878",
        "button_fg": "#2c1810",
        "button_hover": "#c4b590",
        "style": "vintage",
        **_SPRITE_COLORS,
    },
}

# Active theme — start with glass (Nocturne)
_THEME_KEYS = list(THEMES.keys())
_active_theme_idx = 1
THEME = dict(THEMES[_THEME_KEYS[_active_theme_idx]])

# Typography scale — clear hierarchy
FONT_TITLE = ("Segoe UI", 11, "bold")    # status / header
FONT_BODY = ("Segoe UI", 10)              # main chat text
FONT_INPUT = ("Segoe UI", 11)             # input field — slightly bigger
FONT_LABEL = ("Segoe UI", 8)              # captions / tiny hints
FONT_MONO = ("Cascadia Mono", 10)         # code-ish

# Memoria infinita: lógica y constantes viven en core/memory.py (refactor v5)
from core.memory import (
    MemoryMixin,
    MEMORY_MAX_MESSAGES,
    MEMORY_CONTEXT_MESSAGES,
    MEMORY_CONTEXT_CHARS,
)

BUBBLE_WIDTH = 880
BUBBLE_HEIGHT = 630
BUBBLE_MINI_SIZE = 72
# Ancho extra (px lógicos) que gana la ventana de chat al abrir cada panel lateral.
CALENDAR_PANEL_W = 330   # se abre hacia la DERECHA
HISTORY_PANEL_W = 330    # se abre hacia la IZQUIERDA
MOON_FRAME_COUNT = 6
# Idle sprite: beautiful animated moon with Zzz and stars.
MOON_FRAMES = [os.path.join(SCRIPT_DIR, f"claudy_moon_frame_{i}.png") for i in range(MOON_FRAME_COUNT)]

WEBCHAT_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claudy WebChat</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Segoe UI,sans-serif;background:#0d0d1a;color:#e8e8f0;display:flex;height:100vh}
#chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:12px 16px;border-radius:12px;line-height:1.5;white-space:pre-wrap;word-break:break-word}
.user{align-self:flex-end;background:#7c6bff;color:#fff;border-bottom-right-radius:4px}
.bot{align-self:flex-start;background:#161622;border:1px solid #2a2a40;border-bottom-left-radius:4px}
#input-area{display:flex;padding:12px;gap:8px;background:#0f0f1a;border-top:1px solid #2a2a40}
#msg{flex:1;padding:10px 14px;border-radius:8px;border:1px solid #2a2a40;background:#0f0f1a;color:#e8e8f0;font-size:14px;outline:none}
#msg:focus{border-color:#7c6bff}
#send{background:#7c6bff;color:#fff;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-weight:600}
#send:hover{background:#5e4be0}
.loading{color:#8a8aa3;font-style:italic;padding:8px}
</style>
</head>
<body>
<div style="display:flex;flex-direction:column;flex:1;max-width:700px;margin:0 auto">
<header style="padding:16px;text-align:center;border-bottom:1px solid #2a2a40">
  <h1 style="color:#7c6bff;font-size:20px">Claudy WebChat</h1>
</header>
<div id="chat"></div>
<div id="input-area">
  <input id="msg" placeholder="Escribe aqui..." onkeydown="if(event.key==='Enter')send()">
  <button id="send" onclick="send()">Enviar</button>
</div>
</div>
<script>
async function send(){
  const inp=document.getElementById('msg');
  const msg=inp.value.trim();
  if(!msg)return;
  inp.value='';
  addMsg(msg,'user');
  const ld=addMsg('...','loading');
  try{
    const r=await fetch('http://127.0.0.1:8720/api',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg})
    });
    const d=await r.json();
    ld.remove();
    addMsg(d.response,'bot');
  }catch(e){
    ld.remove();
    addMsg('Error: no se pudo conectar con Claudy. Asegurate de que la app este abierta.','bot');
  }
}
function addMsg(text,cls){
  const d=document.createElement('div');
  d.className='msg '+cls;
  d.textContent=text;
  document.getElementById('chat').appendChild(d);
  d.scrollIntoView({behavior:'smooth'});
  return d;
}
</script>
</body>
</html>"""

def generate_sprite():
    # If a custom skin flag exists, skip regeneration to preserve user-provided frames
    custom_flag = os.path.join(SCRIPT_DIR, "custom_skin.flag")
    if os.path.exists(custom_flag) and all(os.path.exists(p) for p in ASSET_FRAMES):
        return

    size = 128
    scale = 4

    for frame, path in enumerate(ASSET_FRAMES):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        def pixel(x, y, w, h, color):
            d.rectangle(
                [x * scale, y * scale, (x + w) * scale - 1, (y + h) * scale - 1],
                fill=color,
            )

        body = THEME["body"]
        body_dark = THEME["body_dark"]
        screen = THEME["screen"]
        outline = THEME["outline"]
        eye = THEME["eye_glow"]
        fin = THEME["fin"]
        accent = THEME["accent_glow"]

        bob = [0, -1, 0, 1, 0, -1][frame]
        arm_wave = [0, -1, -2, -1, 0, 1][frame]
        blink = frame == 3  # Parpadeo en frame 3

        # Shadow under the bot.
        shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse([24, 102, 104, 118], fill=(0, 0, 0, 60))
        img = Image.alpha_composite(img, shadow)
        d = ImageDraw.Draw(img)

        # Chunky outline (slightly smaller, cuter proportions).
        pixel(10, 10 + bob, 22, 2, outline)
        pixel(8, 12 + bob, 26, 3, outline)
        pixel(6, 15 + bob, 32, 22, outline)
        pixel(9, 37 + bob, 26, 4, outline)
        pixel(12, 41 + bob, 6, 3, outline)
        pixel(27, 41 + bob, 6, 3, outline)

        # Body.
        pixel(11, 12 + bob, 22, 3, body)
        pixel(9, 15 + bob, 26, 20, body)
        pixel(11, 35 + bob, 22, 4, body_dark)
        pixel(14, 39 + bob, 4, 4, body)
        pixel(27, 39 + bob, 4, 4, body)

        # Side fins.
        pixel(4, 20 + bob + arm_wave, 6, 5, outline)
        pixel(5, 21 + bob + arm_wave, 6, 3, fin)
        pixel(34, 20 + bob - arm_wave, 6, 5, outline)
        pixel(33, 21 + bob - arm_wave, 6, 3, fin)

        # Face screen.
        pixel(13, 17 + bob, 18, 11, screen)
        if blink:
            pixel(16, 20 + bob, 3, 1, eye)
            pixel(25, 20 + bob, 3, 1, eye)
        else:
            pixel(16, 18 + bob, 3, 3, eye)
            pixel(25, 18 + bob, 3, 3, eye)
        pixel(20, 24 + bob, 4, 1, accent)

        # Antenna.
        pixel(21, 7 + bob, 2, 4, outline)
        pixel(20, 5 + bob, 4, 2, eye)

        # Tiny sparkles.
        pixel(37, 8 + arm_wave, 1, 1, accent)
        pixel(39, 10 - arm_wave, 1, 1, eye)
        pixel(5, 8 - arm_wave, 1, 1, eye)

        img.save(path)


generate_sprite()

user32 = ctypes.windll.user32
SPI_GETWORKAREA = 0x0030


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


work_area = RECT()
user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work_area), 0)

# pywebview's window APIs (create_window, move) treat coordinates as DPI-unaware
# logical pixels, while this process is DPI-aware (work_area + Tk geometries are
# in physical pixels). Compute the system DPI scale so we can translate physical
# coords → pywebview-logical coords before calling webview.move() / sizing.
def _dpi_scale():
    try:
        hdc = user32.GetDC(0)
        try:
            LOGPIXELSX = 88
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, LOGPIXELSX)
        finally:
            user32.ReleaseDC(0, hdc)
        return max(1.0, dpi / 96.0)
    except Exception:
        return 1.0
DPI_SCALE = _dpi_scale()

def physical_to_webview(x, y):
    """Convert DPI-aware physical pixels → pywebview's logical pixels."""
    return int(round(x / DPI_SCALE)), int(round(y / DPI_SCALE))

# Actual physical size the WebView occupies on screen. pywebview creates the
# window at BUBBLE_WIDTH x BUBBLE_HEIGHT logical pixels; WebView2 renders that
# at roughly logical * DPI_SCALE physical pixels MINUS some chrome overhead
# that's invisible but counted by the OS. Empirically (Win11, WebView2 ~1.0.27xx
# at 125% scaling) the overhead is ~18 px wide / ~47 px tall — i.e. the visible
# render is shorter than the naive DPI projection. Subtracting it here makes the
# computed chat footprint match what the user actually sees, so the pet_gap is
# honored instead of being absorbed by the over-estimated height.
_CHAT_CHROME_W = int(round(18 * DPI_SCALE / 1.25))  # scale chrome with DPI too
_CHAT_CHROME_H = int(round(47 * DPI_SCALE / 1.25))
CHAT_WEBVIEW_PHYS_W = int(round(BUBBLE_WIDTH * DPI_SCALE)) - _CHAT_CHROME_W
CHAT_WEBVIEW_PHYS_H = int(round(BUBBLE_HEIGHT * DPI_SCALE)) - _CHAT_CHROME_H

import uuid

class WebViewApi:
    def __init__(self, pet):
        self._pet = pet
        self._callbacks = {}

    def set_focused(self, focused):
        self._pet._webview_focused = focused
        # When the webview loses focus (e.g., user clicked another window),
        # kick off the focus check so panels and bubble auto-hide.
        if not focused and getattr(self._pet, "_webview_visible", False):
            try:
                self._pet.after(150, self._pet._check_bubble_focus)
            except Exception:
                pass

    def _register_callback(self, cid, cb):
        if cid:
            self._callbacks[cid] = cb

    def trigger_callback(self, cid, *args):
        cb = self._callbacks.get(cid)
        if cb:
            threading.Thread(target=cb, args=args, daemon=True).start()

    def send_message(self, message):
        def _run():
            self._pet._handle_web_submit(message)
        threading.Thread(target=_run, daemon=True).start()

    def new_conversation(self):
        def _run():
            self._pet._handle_web_new_conversation()
        threading.Thread(target=_run, daemon=True).start()

    def select_product(self, product_name):
        def _run():
            self._pet._handle_web_product_switch(product_name)
        threading.Thread(target=_run, daemon=True).start()

    def analyze_folder(self):
        def _run():
            self._pet._handle_web_analyze_folder()
        threading.Thread(target=_run, daemon=True).start()

    def pick_attachment(self):
        def _run():
            self._pet._handle_web_pick_attachment()
        threading.Thread(target=_run, daemon=True).start()

    def open_last_location(self):
        def _run():
            self._pet._open_last_file_location()
        threading.Thread(target=_run, daemon=True).start()

    def minimize_window(self):
        self._pet.after(0, self._pet.hide_bubble)

    def cancel_processing(self):
        """Botón de pánico (doble ESC): interrumpe lo que Claudy esté haciendo
        (informe a medias, etc.) sin reiniciar la app."""
        try:
            self._pet._request_cancel()
        except Exception:
            pass

    def show_settings(self):
        """Open the history/settings window (alarms, themes, skins, API keys)."""
        self._pet.after(0, self._pet.show_history_window)

    # ── Google Calendar bridge ────────────────────────────────────────────
    def _gcal(self):
        import google_calendar as gcal
        return gcal

    def get_calendar_status(self):
        try:
            return self._gcal().status()
        except Exception as e:
            return {"connected": False, "reason": str(e)}

    def get_calendar_events(self):
        try:
            return self._gcal().list_upcoming()
        except Exception as e:
            return {"connected": False, "reason": str(e), "events": []}

    def calendar_connect(self):
        """Lanza el flujo OAuth (abre navegador 1 vez). Bloquea hasta autorizar."""
        try:
            return self._gcal().connect()
        except Exception as e:
            return {"connected": False, "reason": str(e)}

    def create_calendar_event(self, payload):
        try:
            p = payload or {}
            attendees = p.get("attendees") or []
            if isinstance(attendees, str):
                attendees = [a.strip() for a in attendees.replace(";", ",").split(",") if a.strip()]
            return self._gcal().create_event(
                summary=p.get("summary") or "Reunión",
                start_iso=p.get("start"),
                end_iso=p.get("end"),
                description=p.get("description", ""),
                attendees=attendees,
                location=p.get("location", ""),
                add_meet=bool(p.get("addMeet")),
            )
        except Exception as e:
            return {"ok": False, "reason": str(e)}

    def set_calendar_open(self, is_open):
        """Abre/cierra el panel Calendario (derecha): ensancha/reposiciona la ventana."""
        self._pet._calendar_open = bool(is_open)
        self._pet.after(0, lambda: self._pet._resize_webview_for_panels())
        return True

    # ── Panel Historial (izquierda) ───────────────────────────────────────
    def set_history_open(self, is_open):
        """Abre/cierra el panel Historial (izquierda): ensancha/reposiciona la ventana."""
        self._pet._history_panel_open = bool(is_open)
        self._pet.after(0, lambda: self._pet._resize_webview_for_panels())
        return True

    def get_history_archive(self, limit=200):
        """Devuelve el historial eterno de conversaciones para el panel."""
        try:
            msgs = self._pet._load_memory() or []
            out = []
            for m in msgs:
                role = m.get("role")
                shown = self._pet._tidy_history_text(role, m.get("text") or "")
                if shown is None:
                    continue  # ruido interno: no mostrar
                out.append({
                    "role": "user" if role == "Usuario" else "claudy",
                    "text": shown[:2000],
                    "time": m.get("time", "") or "",
                })
            # Límite tras compactar/filtrar: así se ven los últimos N mensajes limpios.
            if limit:
                out = out[-int(limit):]
            return out
        except Exception as e:
            return []

    def open_settings_window(self):
        """Abre la ventana clásica de Ajustes (alarmas, temas, skins, API keys)."""
        self._pet.after(0, self._pet.show_history_window)
        return True

    def speak_message(self, message):
        def _run():
            self._pet._speak_text(message)
        threading.Thread(target=_run, daemon=True).start()

    def set_voice_enabled(self, enabled):
        """Toggle global TTS desde el botón de voz del chat."""
        self._pet._voice_enabled = bool(enabled)
        return self._pet._voice_enabled

    def get_voice_enabled(self):
        return bool(getattr(self._pet, "_voice_enabled", False))

    def get_drive_status(self):
        return getattr(self._pet, "_drive_connected", True)

    def get_telegram_status(self):
        """Estado de conexión con Telegram para el indicador del sidebar.
        Devuelve el último valor verificado al instante y, si está viejo (>30s),
        dispara una re-verificación en segundo plano (no bloquea la UI)."""
        pet = self._pet
        try:
            last = getattr(pet, "_telegram_last_check", 0)
            if time.time() - last > 30:
                pet._telegram_last_check = time.time()  # evita ráfagas de checks
                threading.Thread(target=pet._verify_telegram_connection, daemon=True).start()
        except Exception:
            pass
        return getattr(pet, "_telegram_connected", False)

    def get_history(self):
        raw_msgs = getattr(self._pet, "_current_session_msgs", []) or []
        serializable = []
        for m in raw_msgs:
            serializable.append({
                "role": m.get("role", "system"),
                "text": m.get("text", "") or "",
                "ts": m.get("ts", time.time()),
                "fileCard": m.get("fileCard", None),
                "optionsCard": m.get("optionsCard", None),
                "summaryCard": m.get("summaryCard", None),
            })
        return serializable


class WebViewStatusWrapper:
    def __init__(self, pet):
        self.pet = pet

    def configure(self, text=None, fg=None, **kwargs):
        if text is not None:
            self.pet._eval_in_web(f"updateStatusText({json.dumps(text)})")
            # Show speech bubble when chat is hidden and a background task is running
            if not getattr(self.pet, '_webview_visible', False) and text.strip():
                try:
                    self.pet.show_pet_speech_bubble(text, duration=5000)
                except Exception:
                    pass


class WebViewEntryWrapper:
    def __init__(self, pet):
        self.pet = pet
        self._val = ""

    def get(self, *args):
        return self._val

    def delete(self, first, last=None):
        self._val = ""
        self.pet._eval_in_web("try { clearInputField(); } catch(e) {}")

    def insert(self, index, text):
        self._val = text
        self.pet._eval_in_web(f"try {{ insertInputText({json.dumps(text)}); }} catch(e) {{}}")

    def focus_set(self):
        self.pet._eval_in_web("try { focusInputField(); } catch(e) {}")

    def config(self, **kwargs):
        pass


class WebViewChatWrapper:
    def __init__(self, pet):
        self.pet = pet
        self._messages = list(getattr(pet, "_current_session_msgs", []) or [])

    def add_user(self, text, ts=None):
        ts = ts or time.time()
        self._messages.append({"role": "user", "text": text, "ts": ts})
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addUserMessage({json.dumps(text)}, {ts}); }} catch(e) {{}}")

    def add_bot(self, text, ts=None):
        ts = ts or time.time()
        self._messages.append({"role": "bot", "text": text, "ts": ts})
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addBotMessage({json.dumps(text)}, {ts}); }} catch(e) {{}}")

    def begin_stream(self, ts=None):
        ts = ts or time.time()
        self.pet._eval_in_web(f"try {{ beginBotStream({ts}); }} catch(e) {{}}")

    def update_stream(self, text):
        self.pet._eval_in_web(f"try {{ updateBotStream({json.dumps(text)}); }} catch(e) {{}}")

    def end_stream(self, text, ts=None):
        ts = ts or time.time()
        self._messages.append({"role": "bot", "text": text, "ts": ts})
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ endBotStream({json.dumps(text)}, {ts}); }} catch(e) {{}}")

    def add_system(self, text):
        self._messages.append({"role": "system", "text": text, "ts": time.time()})
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addSystemMessage({json.dumps(text)}); }} catch(e) {{}}")

    def show_typing(self):
        self.pet._eval_in_web("try { showTypingIndicator(); } catch(e) {}")

    def hide_typing(self):
        self.pet._eval_in_web("try { hideTypingIndicator(); } catch(e) {}")

    def clear(self):
        self._messages.clear()
        self.pet._current_session_msgs = []
        self.pet._eval_in_web("try { clearChat(); } catch(e) {}")

    def add_options(self, options, on_select):
        callback_id = f"opt_cb_{uuid.uuid4().hex}"
        self.pet.js_api._register_callback(callback_id, on_select)
        self._messages.append({
            "role": "bot",
            "ts": time.time(),
            "optionsCard": {"options": options, "callbackId": callback_id, "active": True}
        })
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addOptionsCard({json.dumps(options)}, {json.dumps(callback_id)}); }} catch(e) {{}}")

    def add_summary_card(self, topic, depth, images, references, style, language):
        self._messages.append({
            "role": "bot",
            "ts": time.time(),
            "summaryCard": {"topic": topic, "depth": depth, "images": images, "references": references, "style": style, "language": language}
        })
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addSummaryCard({json.dumps(topic)}, {json.dumps(depth)}, {json.dumps(images)}, {json.dumps(references)}, {json.dumps(style)}, {json.dumps(language)}); }} catch(e) {{}}")

    def add_file_card(self, filename, on_open_file=None, on_open_folder=None, message="Listo. Archivo generado"):
        open_file_id = f"file_cb_{uuid.uuid4().hex}" if on_open_file else None
        open_folder_id = f"folder_cb_{uuid.uuid4().hex}" if on_open_folder else None
        
        if on_open_file:
            self.pet.js_api._register_callback(open_file_id, on_open_file)
        if on_open_folder:
            self.pet.js_api._register_callback(open_folder_id, on_open_folder)

        self._messages.append({
            "role": "bot",
            "ts": time.time(),
            "fileCard": {"filename": filename, "message": message, "openFileId": open_file_id, "openFolderId": open_folder_id}
        })
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addFileCard({json.dumps(filename)}, {json.dumps(message)}, {json.dumps(open_file_id)}, {json.dumps(open_folder_id)}); }} catch(e) {{}}")

    def load_history(self, messages):
        self.clear()
        for m in messages:
            role = m.get("role", "")
            text = m.get("text", "")
            ts = m.get("ts", time.time())
            fileCard = m.get("fileCard", None)
            optionsCard = m.get("optionsCard", None)
            summaryCard = m.get("summaryCard", None)
            
            if fileCard:
                self.add_file_card(fileCard["filename"], None, None, fileCard["message"])
            elif optionsCard:
                self.add_options(optionsCard["options"], lambda x: None)
            elif summaryCard:
                self.add_summary_card(summaryCard["topic"], summaryCard["depth"], summaryCard["images"], summaryCard["references"], summaryCard["style"], summaryCard["language"])
            elif role in ("user", "Usuario") or role == "user":
                self.add_user(text, ts)
            elif role in ("bot", "Claudy") or role == "bot":
                self.add_bot(text, ts)
            else:
                self.add_system(text)


class ClawdPet(MemoryMixin, tk.Tk):
    BUBBLES = [
        "Estoy listo para ayudarte.",
        "Toca dos veces para hablar.",
        "Click derecho para opciones.",
        "Tengo una idea...",
        "Dime, que necesitas?",
    ]

    def __init__(self):
        super().__init__()
        self.title("Claw'D")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=TRANSPARENT_COLOR)
        self.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        # ===== One-time 3D Crab Skin Migration (hilo daemon — no bloquea arranque) =====
        threading.Thread(target=self._migrate_skin_if_needed, daemon=True, name="skin-migration").start()

        # Load frame 0 immediately so the pet appears fast, then load rest lazily
        self.frames = []
        self._frames_loaded = False
        try:
            first_path = ASSET_FRAMES[0]
            if os.path.exists(first_path):
                pil_img = Image.open(first_path).convert("RGBA")
                r, g, b, a = pil_img.split()
                binary_a = a.point(lambda p: 255 if p > 30 else 0)
                pil_img.putalpha(binary_a)
                self.frames.append(ImageTk.PhotoImage(pil_img))
            else:
                self.frames.append(tk.PhotoImage(file=first_path))
        except Exception:
            self.frames = [tk.PhotoImage(file=ASSET_FRAMES[0])]
        # Schedule lazy loading of frames 1-5 after the window is visible
        self.after(50, self._load_remaining_frames)

        self.frame_index = 0
        self.img = self.frames[self.frame_index]
        self.moon_frames = []
        self.label = tk.Label(self, image=self.img, bg=TRANSPARENT_COLOR, bd=0)
        self.label.pack()

        self.update_idletasks()
        self.width = self.winfo_reqwidth()
        self.height = self.winfo_reqheight()

        self.base_x = work_area.right - self.width
        self.base_y = work_area.bottom - self.height
        self.geometry(f"{self.width}x{self.height}+{self.base_x}+{self.base_y}")

        self.tick = 0
        self.state = "idle"
        # ---- Motion system: squash&stretch, throw physics, wander, per-skin profiles ----
        self._skin_name = self._detect_skin_name()
        self._facing = 1
        self._render_x = float(self.base_x)
        self._render_y = float(self.base_y)
        self._prev_render_y = float(self.base_y)
        self._base_xf = float(self.base_x)
        self._base_yf = float(self.base_y)
        self._throw_active = False
        self._vx = 0.0
        self._vy = 0.0
        self._drag_vx = 0.0
        self._drag_vy = 0.0
        self._wander_active = False
        self._wander_tx = self.base_x
        self._pil_frames = None
        self._scale_cache = {}
        self._cur_scaled_img = None
        self.after(60, self._rebuild_pil_frames)
        self.bubble_win = None
        self.bubble_interactive = False
        self._context_popup = None
        self._notebook_win = None
        self._notebook_state = None
        self.quick_session_id = None
        self.opencode_process = None
        self.history_win = None
        self._current_model = None  # Override model from /model command
        self._voice_enabled = False  # /voice on|off — TTS toggle
        self._streaming_enabled = False  # /stream on|off — live token streaming in the bubble
        self._streamed = False
        self._plan_mode = False  # /plan on|off — solo planea, no ejecuta
        self._checkpoint_history = []  # F3.1 stack para undo/redo
        self._checkpoint_undone = []
        self._last_file_artifact_path = None
        self._open_location_btn = None
        self._available_models = [
            "deepseek-chat", "deepseek-reasoner",
            "gpt-4o", "gpt-4o-mini", "gpt-4.1",
            "claude-sonnet-4-20250514", "claude-haiku-3-5",
            "gemini-2.5-pro", "gemini-2.5-flash",
        ]
        self._idle_hide_timer = None  # Auto-hide timer (60s)
        self._last_activity = time.time()  # Track last user interaction
        self.bubble_minimized = False

        self._dragging = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._snap_margin = 20  # pixels from edge to trigger snap
        self._snap_enabled = True

        self._telegram_bot_app = None
        self._telegram_allowed_users = set()
        self._telegram_connected = False   # ¿el token es aceptado por Telegram?
        self._telegram_last_check = 0      # throttle de la verificación getMe

        self._cron_jobs = []
        self._cron_file = os.path.join(os.path.expanduser("~"), ".claudy", "cron.json")

        self._voice_listening = False
        self._voice_active = False

        self._gateway_server = None
        self._gateway_port = 8720
        self._gateway_bind_ip = "127.0.0.1"
        self._gateway_auth_token = None

        # Self-improving skills loop (Hermes-style): guard + auto-refine threshold
        self._refining_skill = False
        self._skill_refine_threshold = 5  # auto-refine after N uses since last refine

        # Google Drive connection monitor
        self._drive_connected = True
        self._bubble_canvas = None
        self.after(4000, self._check_google_drive)

        # Webview initialization
        self.webview_win = None
        self.js_api = WebViewApi(self)
        self._webview_visible = False
        self._webview_thread = None
        self._webview_ready = False  # True once HTML is fully loaded in the webview

        self.animate()

        self.label.bind("<Enter>", self.on_enter)
        self.label.bind("<Leave>", self.on_leave)
        self.label.bind("<Button-1>", self._on_drag_start)
        self.label.bind("<Double-Button-1>", self.on_double_click)
        # Drag & drop bindings (label handles both click and drag)
        self.label.bind("<B1-Motion>", self._on_drag_motion)
        self.label.bind("<ButtonRelease-1>", self._on_drag_release)
        # Window-level bindings as fallback
        self.bind("<Button-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)
        self.bind("<ButtonRelease-1>", self._on_drag_release)

        self.menu = tk.Menu(
            self,
            tearoff=0,
            bg="#05091d",
            fg="#f7f9ff",
            activebackground="#172862",
            activeforeground="#58c7ff",
            disabledforeground="#6574a8",
            bd=1,
            relief="flat",
            borderwidth=1,
            activeborderwidth=0,
            font=("Bahnschrift SemiBold", 10),
        )
        self._rebuild_context_menu()
        self.label.bind("<Button-3>", self._show_context_popup)


        # Initialize system tray icon. — 200ms: aparece más rápido en la bandeja
        self._tray_icon = None
        self._in_tray = False
        self._chat_open_before_tray = False
        self._portfolio_mode = False
        self.after(200, self._create_tray_icon)
        # Start Telegram bot if configured
        self.after(1500, self._start_telegram_if_configured)
        # Start Cron engine
        self.after(3000, self._start_cron_engine)
        # Start Gateway HTTP server — inmediato en hilo daemon
        self.after(0, self._start_gateway)
        # Initialize SQLite memory
        self.after(2000, self._init_memory_db)
        # Encrypt config secrets at rest (idempotent, safe)
        self.after(2200, self._secure_migrate_config)
        # Register built-in tools
        self._register_builtin_tools()
        # Initialize Kanban board
        self.after(3500, self._init_kanban_db)
        # Saludo inicial — 3000ms: espera al webview loaded antes de abrir
        self.after(3000, self._show_welcome_bubble_when_ready)
        # Hotkey global Alt+Space para abrir/cerrar el bubble desde cualquier app
        self.after(5000, self._register_global_hotkey)
        # Loop de comportamientos idle dinamicos (bostezo, mirada, baile, etc.)
        self.after(12000, self._start_idle_behaviors)
        # Alarm badge — floating icon above Claudy when alarms are active
        self._alarm_badge_win = None
        self.after(4500, self._alarm_badge_refresh)

    def destroy(self):
        self._is_exiting = True
        try:
            super().destroy()
        except Exception:
            pass
        if getattr(self, "webview_win", None) is not None:
            try:
                self.webview_win.destroy()
            except Exception:
                pass
        import os
        os._exit(0)

    def _migrate_skin_if_needed(self):
        """One-time 3D Crab skin migration — runs in a daemon thread so it never blocks startup."""
        try:
            img_3d_path = "C:\\Users\\asus\\.gemini\\antigravity\\brain\\3b517328-c08b-49ef-bf4b-964cd9e198f6\\media__1779411206528.png"
            migration_flag = os.path.join(SCRIPT_DIR, "crab_3d_migrated.flag")

            is_migrated_v2 = False
            if os.path.exists(migration_flag):
                with open(migration_flag, "r") as f:
                    if "v2" in f.read():
                        is_migrated_v2 = True

            if os.path.exists(img_3d_path) and not is_migrated_v2:
                if SCRIPT_DIR not in sys.path:
                    sys.path.insert(0, SCRIPT_DIR)
                import skin_swap

                backup_dir = os.path.join(SCRIPT_DIR, "backup_original")
                os.makedirs(backup_dir, exist_ok=True)
                skin_swap.create_animated_frames(img_3d_path, backup_dir, frame_size=128)

                for i in range(6):
                    shutil.copy(
                        os.path.join(backup_dir, f"claudy_orbit_frame_{i}.png"),
                        os.path.join(SCRIPT_DIR, f"claudy_orbit_frame_{i}.png")
                    )

                flag_path = os.path.join(SCRIPT_DIR, "custom_skin.flag")
                with open(flag_path, "w") as f:
                    f.write("source: backup_original (crab)\n")
                with open(migration_flag, "w") as f:
                    f.write("3D Crab migration v2 completed successfully!\n")
        except Exception as e:
            print(f"Error migrating 3D crab skin: {e}")

    def _load_remaining_frames(self):
        """Lazily load frames 1-5 after the pet window is already visible with frame 0."""
        try:
            for path in ASSET_FRAMES[1:]:
                if os.path.exists(path):
                    pil_img = Image.open(path).convert("RGBA")
                    r, g, b, a = pil_img.split()
                    binary_a = a.point(lambda p: 255 if p > 30 else 0)
                    pil_img.putalpha(binary_a)
                    self.frames.append(ImageTk.PhotoImage(pil_img))
                else:
                    self.frames.append(tk.PhotoImage(file=path))
            self._frames_loaded = True
        except Exception as e:
            print(f"[lazy frames] error: {e}")
            # Fallback: fill remaining with tk.PhotoImage
            while len(self.frames) < len(ASSET_FRAMES):
                idx = len(self.frames)
                try:
                    self.frames.append(tk.PhotoImage(file=ASSET_FRAMES[idx]))
                except Exception:
                    break
            self._frames_loaded = True

    def _register_global_hotkey(self):
        def _worker():
            try:
                import keyboard
            except Exception:
                return
            try:
                keyboard.add_hotkey("alt+space", lambda: self.after(0, self._toggle_bubble_from_hotkey))
                keyboard.wait()  # blocks forever
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True, name="global-hotkey").start()

    def _toggle_bubble_from_hotkey(self):
        if self.bubble_win and self.bubble_interactive and not self.bubble_minimized:
            try:
                mf = getattr(self, "_minimize_bubble", None)
                if mf:
                    mf()
                    return
            except Exception:
                pass
            self.hide_bubble()
            return
        if self.bubble_minimized and hasattr(self, "_expand_bubble"):
            self._expand_bubble()
            return
        self.show_chat_bubble()

    def _generate_web_avatar(self):
        """Convert the chroma-key sprite (#ff00ff background) to a PNG with real
        alpha transparency so it renders cleanly in the webview HTML."""
        try:
            src = os.path.join(SCRIPT_DIR, "claudy_orbit_frame_0.png")
            dst = os.path.join(SCRIPT_DIR, "claudy_web_avatar.png")
            # Only regenerate if source is newer than destination
            if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
                return
            img = Image.open(src).convert("RGBA")
            pixels = img.load()
            w, h = img.size
            # Replace magenta (#ff00ff) pixels with full transparency
            for x in range(w):
                for y in range(h):
                    r, g, b, a = pixels[x, y]
                    if r > 240 and g < 15 and b > 240:
                        pixels[x, y] = (0, 0, 0, 0)
            img.save(dst, "PNG")
        except Exception as e:
            print(f"[web avatar] error: {e}")

    def _resize_webview_for_panels(self):
        """Ensancha/restaura la ventana de chat según los paneles abiertos:
        Historial crece hacia la IZQUIERDA y Calendario hacia la DERECHA, dejando
        la columna del chat anclada en su posición. Best-effort: nunca rompe el chat."""
        win = getattr(self, "webview_win", None)
        if win is None:
            return
        logical_w, logical_h, phys_x, phys_y, _, _ = self._webview_layout_for_panels()
        try:
            win.resize(logical_w, logical_h)
        except Exception:
            pass
        try:
            win.move(*physical_to_webview(phys_x, phys_y))
        except Exception:
            pass

    def _webview_layout_for_panels(self):
        """Return logical size plus physical position/footprint for open side panels.

        The chat column keeps its normal anchor when there is room. If the calendar
        would spill off the right edge, the whole WebView slides left; when a panel
        closes, the clamp naturally lets it slide right again.
        """
        hist = HISTORY_PANEL_W if getattr(self, "_history_panel_open", False) else 0
        cal = CALENDAR_PANEL_W if getattr(self, "_calendar_open", False) else 0
        requested_logical_w = BUBBLE_WIDTH + hist + cal
        work_w = max(1, work_area.right - work_area.left)
        max_logical_w = max(BUBBLE_WIDTH, int((work_w + _CHAT_CHROME_W) / DPI_SCALE))
        logical_w = min(requested_logical_w, max_logical_w)
        logical_h = BUBBLE_HEIGHT

        phys_w = int(round(logical_w * DPI_SCALE)) - _CHAT_CHROME_W
        phys_h = CHAT_WEBVIEW_PHYS_H

        base_x, base_y = self.bubble_position(CHAT_WEBVIEW_PHYS_W, CHAT_WEBVIEW_PHYS_H)
        desired_x = base_x - int(round(hist * DPI_SCALE))
        desired_y = base_y

        if desired_x + phys_w > work_area.right:
            desired_x = work_area.right - phys_w
        if desired_x < work_area.left:
            desired_x = work_area.left
        if desired_y + phys_h > work_area.bottom:
            desired_y = work_area.bottom - phys_h
        if desired_y < work_area.top:
            desired_y = work_area.top

        return logical_w, logical_h, int(desired_x), int(desired_y), int(phys_w), int(phys_h)

    def _run_webview_main_thread(self):
        try:
            # Generate web-friendly avatar with real transparency (no magenta chroma key)
            self._generate_web_avatar()
            
            html_path = os.path.abspath(os.path.join(SCRIPT_DIR, "chat.html"))
            html_url = f"file:///{html_path.replace(chr(92), '/')}"
            
            # Create window VISIBLE but OFF-SCREEN (-9999, -9999).
            # Using hidden=True + later show() causes black window on Windows
            # because WebView2 doesn't render transparent frameless windows
            # that were initially hidden.
            # pywebview treats width/height as DPI-unaware logical pixels.
            # Pass BUBBLE_WIDTH/HEIGHT directly so WebView2 renders the HTML at
            # its designed CSS pixel size. The window will end up *physically*
            # ~BUBBLE_WIDTH*DPI_SCALE x BUBBLE_HEIGHT*DPI_SCALE — see CHAT_WEBVIEW_PHYS_W/H.
            self.webview_win = webview.create_window(
                title="Claudy Chat",
                url=html_url,
                width=BUBBLE_WIDTH,
                height=BUBBLE_HEIGHT,
                frameless=True,
                transparent=True,
                background_color='#000000',
                js_api=self.js_api,
                hidden=False,
                on_top=True,
                x=-9999,
                y=-9999
            )
            
            # Signal when the HTML content is fully loaded and rendered
            def _on_webview_loaded():
                self._webview_ready = True
                print("[webview] HTML loaded successfully — _webview_ready = True")
            self.webview_win.events.loaded += _on_webview_loaded
            
            def _on_webview_closing():
                if getattr(self, "_is_exiting", False):
                    print("[webview] Exiting application, allowing webview to close.")
                    return True
                print("[webview] Close event intercepted — calling hide_bubble() instead.")
                self.after(0, self.hide_bubble)
                return False
            self.webview_win.events.closing += _on_webview_closing
            
            # Start pywebview loop
            print("[webview] Starting webview.start() on main thread...")
            webview.start()
        except Exception as e:
            print(f"[webview init] error starting webview: {e}")
            self.webview_win = None

    def _eval_in_web(self, script):
        if getattr(self, "webview_win", None) is not None:
            try:
                self.webview_win.evaluate_js(script)
            except Exception as e:
                pass

    def _handle_web_submit(self, prompt):
        # El input del webview es un textarea (permite saltos con Shift+Enter), pero
        # se inyecta en un Entry de una sola línea. Colapsamos los saltos a espacios
        # para que el prompt completo llegue intacto al dispatch (no se trunque).
        if prompt:
            prompt = " ".join(prompt.split())
        # Deep Research switch: el front prefija "[DEEP_RESEARCH] ...". Lo interiorizamos
        # aquí — guardamos la intención en una bandera y limpiamos el texto para que la
        # burbuja del usuario NO muestre el prefijo y el ruteo lo trate como informe.
        self._deep_research_pending = False
        if prompt:
            m = re.match(r"^\s*\[DEEP_RESEARCH\]\s*(.*)$", prompt, re.IGNORECASE | re.DOTALL)
            if m:
                self._deep_research_pending = True
                prompt = m.group(1).strip()
        self.after(0, lambda: self._trigger_submit_with_text(prompt))

    def _handle_web_new_conversation(self):
        try:
            self._compress_and_save_to_obsidian()
        except Exception as ex:
            print(f"[nueva conv] compress error: {ex}")
        self._current_session_msgs = []
        self._chat_view = WebViewChatWrapper(self)
        self._chat_view.clear()
        self._chat_view.add_system("Hola Felipe, ¿en qué te ayudo?")
        self._eval_in_web("focusInputField()")

    def _handle_web_product_switch(self, product_name):
        self._active_product = product_name
        self._portfolio_mode = (product_name == "Mi Portafolio")
        try:
            from qcore_products import build_context_prompt, PRODUCT_CONTEXTS
            self._product_context = build_context_prompt(product_name)
            pinfo = PRODUCT_CONTEXTS.get(product_name, {})
            desc = pinfo.get("description", "")
            mods = pinfo.get("modules", [])
            summary_lines = [f"🔄 Contexto: **{product_name}** ({pinfo.get('tag', '')})", f"_{desc}_"]
            if mods:
                summary_lines.append(f"\n📦 {len(mods)} módulos disponibles:")
                for m in mods[:8]:
                    summary_lines.append(f"  • {m}")
                if len(mods) > 8:
                    summary_lines.append(f"  ... y {len(mods) - 8} más")
            if pinfo.get("port"):
                summary_lines.append(f"\n💡 Di 'inicia {product_name.lower()}' para lanzar en puerto {pinfo['port']}")
            summary = "\n".join(summary_lines)
        except Exception:
            self._product_context = f"Producto activo: {product_name}"
            summary = f"Contexto cambiado a: {product_name}"
            
        self._chat_view = WebViewChatWrapper(self)
        self._chat_view.add_system(summary)

    def _handle_web_analyze_folder(self):
        def _dialog():
            self._is_picking_file = True
            try:
                from tkinter import filedialog
                path = filedialog.askdirectory(title="Carpeta para analizar (recursivo)")
                self._is_picking_file = False
                if not path:
                    return
                
                status = WebViewStatusWrapper(self)
                self._chat_view = WebViewChatWrapper(self)
                self._chat_entry = WebViewEntryWrapper(self)
                self._status_label = status
                
                self._chat_view.show_typing()
                status.configure(text="Iniciando analisis...")
                
                def _run():
                    try:
                        result = self._analyze_folder_deep(path, status)
                    except Exception as e:
                        result = (f"Error: {e}", "")
                        
                    def _show_result():
                        analysis_text, saved_path = result if isinstance(result, tuple) else (result, "")
                        self._chat_view.hide_typing()
                        self._chat_view.add_bot(analysis_text)
                        if saved_path and os.path.exists(saved_path):
                            self._remember_file_artifact(saved_path)
                            self._chat_view.add_file_card(
                                filename=os.path.basename(saved_path),
                                on_open_file=lambda p=saved_path: self._open_path_file(p),
                                on_open_folder=lambda p=saved_path: self._open_path_location(p),
                                message="Abrir reporte completo"
                            )
                        status.configure(text="Enter envía | Esc cierra")
                    self.after(0, _show_result)
                threading.Thread(target=_run, daemon=True).start()
            except Exception as e:
                self._is_picking_file = False
                print(f"[webview folder picker] error: {e}")
        self.after(0, _dialog)

    def _handle_web_pick_attachment(self):
        def _dialog():
            self._is_picking_file = True
            try:
                from tkinter import filedialog
                paths = filedialog.askopenfilenames(
                    title="Adjuntar archivo para analizar",
                    filetypes=[
                        ("Archivos compatibles", "*.pdf *.docx *.xlsx *.xls *.pptx *.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                        ("PDF", "*.pdf"),
                        ("Word", "*.docx"),
                        ("Excel", "*.xlsx *.xls"),
                        ("PowerPoint", "*.pptx"),
                        ("Imagenes", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                        ("Todos los archivos", "*.*"),
                    ],
                )
                self._is_picking_file = False
                if not paths:
                    return
                    
                status = WebViewStatusWrapper(self)
                entry = WebViewEntryWrapper(self)
                self._chat_view = WebViewChatWrapper(self)
                self._status_label = status
                self._chat_entry = entry
                
                question = self._entry_attachment_question(entry)
                for path in list(paths)[:6]:
                    self._analyze_attachment_file(path, status, None, question=question)
                if len(paths) > 6:
                    self._chat_view.add_system("Para no saturar la sesion, analizare solo los primeros 6 archivos.")
            except Exception as e:
                self._is_picking_file = False
                print(f"[webview attachment picker] error: {e}")
        self.after(0, _dialog)

    def _trigger_submit_with_text(self, text):
        entry = getattr(self, "_chat_entry_widget", None)
        submit_fn = getattr(self, "_submit_fn", None)
        if entry and submit_fn:
            try:
                if hasattr(entry, "original_delete"):
                    entry.original_delete(0, tk.END)
                else:
                    entry.delete(0, tk.END)
                if hasattr(entry, "original_insert"):
                    entry.original_insert(0, text)
                else:
                    entry.insert(0, text)
            except Exception as e:
                print(f"[webview trigger submit] text inject error: {e}")
            try:
                submit_fn()
            except Exception as e:
                print(f"[webview trigger submit] run submit error: {e}")

    def _show_welcome_bubble_when_ready(self, _attempts=0):
        """Wait for the webview HTML to be fully loaded before showing the welcome chat.
        Retries every 250ms for up to ~8 seconds, then opens anyway (Tkinter fallback)."""
        MAX_ATTEMPTS = 32  # 32 * 250ms = 8 seconds max wait
        if not self._webview_ready and _attempts < MAX_ATTEMPTS:
            self.after(250, lambda: self._show_welcome_bubble_when_ready(_attempts + 1))
            return
        self._show_welcome_bubble()

    def _show_welcome_bubble(self):
        saludos = [
            "Hola, soy Claudy, tu asistente personal. ¿En qué andas hoy?",
            "Buenas, soy Claudy. ¿Qué tema te tiene la cabeza ocupada hoy?",
            "Hey, soy Claudy. ¿Hay algo en lo que te pueda dar una mano ahora?",
            "Hola, Claudy aquí. ¿Qué pregunta llevas dando vueltas hoy?",
            "Soy Claudy, tu copiloto. ¿Qué quieres resolver primero?",
        ]
        try:
            self.show_chat_bubble(text=random.choice(saludos))
        except Exception:
            pass

    def _restart_app(self):
        """Re-launch pet.py with the current Python interpreter, then close this instance."""
        import sys
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 8)
            subprocess.Popen(
                [sys.executable, __file__] + sys.argv[1:],
                creationflags=flags,
                close_fds=True,
            )
        except Exception as e:
            print(f"Restart error: {e}")
        self.destroy()


    def _alarm_badge_refresh(self):
        """Check for pending alarms every 5s and show/hide the badge icon."""
        try:
            alarms = self._load_alarms()
            # Filter only future alarms
            import time as _t
            pending = [a for a in alarms if a.get("fire", 0) > _t.time()]
            if pending:
                self._alarm_badge_show(len(pending))
            else:
                self._alarm_badge_hide()
        except Exception:
            self._alarm_badge_hide()
        # Schedule next refresh
        self.after(5000, self._alarm_badge_refresh)

    def _alarm_badge_show(self, count=1):
        """Create or update the floating alarm badge above Claudy."""
        # Compute position: centered above the pet sprite
        try:
            pet_x = self.winfo_x()
            pet_y = self.winfo_y()
            pet_w = self.winfo_width()
        except Exception:
            return

        badge_size = 28
        bx = pet_x + pet_w // 2 - badge_size // 2
        by = pet_y - badge_size - 4  # 4px gap above pet

        if self._alarm_badge_win is None or not self._alarm_badge_win.winfo_exists():
            win = tk.Toplevel(self)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=TRANSPARENT_COLOR)
            win.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
            self._alarm_badge_win = win

            # Pulsing circular badge
            canvas = tk.Canvas(
                win,
                width=badge_size, height=badge_size,
                bg=TRANSPARENT_COLOR,
                highlightthickness=0,
            )
            canvas.pack()
            self._alarm_badge_canvas = canvas

            # Click → show alarm list in chat
            def _on_badge_click(e):
                msg = self._alarm_list()
                chat = getattr(self, "_chat_view", None)
                if chat:
                    if not (self.bubble_win and self.bubble_win.winfo_exists()):
                        self.show_chat_bubble()
                    chat.add_bot(msg)
                else:
                    self.show_chat_bubble(msg)

            canvas.bind("<Button-1>", _on_badge_click)
            canvas.bind("<Enter>", lambda e: canvas.configure(cursor="hand2"))
            canvas.bind("<Leave>", lambda e: canvas.configure(cursor=""))

            # Start pulse animation
            self._alarm_badge_pulse = 0
            self._alarm_badge_animate()
        else:
            win = self._alarm_badge_win

        # Update label (count)
        self._alarm_badge_count = count
        win.geometry(f"{badge_size}x{badge_size}+{bx}+{by}")
        win.deiconify()

    def _alarm_badge_animate(self):
        """Pulsing glow animation for the alarm badge."""
        if self._alarm_badge_win is None or not self._alarm_badge_win.winfo_exists():
            return
        try:
            canvas = self._alarm_badge_canvas
            canvas.delete("all")
            pulse = getattr(self, "_alarm_badge_pulse", 0)
            count = getattr(self, "_alarm_badge_count", 1)
            size = 28

            # Reposition to follow pet each frame
            try:
                pet_x = self.winfo_x()
                pet_y = self.winfo_y()
                pet_w = self.winfo_width()
                bx = pet_x + pet_w // 2 - size // 2
                by = pet_y - size - 4
                self._alarm_badge_win.geometry(f"{size}x{size}+{bx}+{by}")
            except Exception:
                pass

            # Pulse: alternate between bright/dim using sine
            import math as _m
            glow = 0.65 + 0.35 * _m.sin(pulse * 0.2)
            r = int(255 * glow)
            g = int(80 * glow)
            fill_col = f"#{r:02x}{g:02x}00"

            # Outer glow ring (pulsing radius)
            glow_r = int(11 + 3 * _m.sin(pulse * 0.2))
            canvas.create_oval(
                size // 2 - glow_r - 2, size // 2 - glow_r - 2,
                size // 2 + glow_r + 2, size // 2 + glow_r + 2,
                fill=fill_col, outline="",
            )
            # Solid circle
            canvas.create_oval(
                size // 2 - 11, size // 2 - 11,
                size // 2 + 11, size // 2 + 11,
                fill="#ff4500", outline="#ff8c00", width=1,
            )
            # Bell icon
            canvas.create_text(
                size // 2, size // 2,
                text="⏰", font=("Segoe UI", 11), fill="white",
            )
            # Count badge (if > 1)
            if count > 1:
                canvas.create_oval(size - 10, 0, size, 10, fill="#ff0000", outline="")
                canvas.create_text(size - 5, 5, text=str(count), font=("Segoe UI", 6, "bold"), fill="white")

            self._alarm_badge_pulse = pulse + 1
        except Exception:
            pass
        self.after(80, self._alarm_badge_animate)


    def _alarm_badge_hide(self):
        """Hide the alarm badge if no pending alarms."""
        if self._alarm_badge_win and self._alarm_badge_win.winfo_exists():
            try:
                self._alarm_badge_win.withdraw()
            except Exception:
                pass


    def _advance_frame(self, speed=4, mode="loop"):
        """Update self.frame_index with ping-pong or loop, respecting speed."""
        if not hasattr(self, "_frame_dir"):
            self._frame_dir = 1
        if self.tick % max(1, int(speed)) != 0:
            return
        n = len(self.frames)
        if mode == "pingpong":
            nxt = self.frame_index + self._frame_dir
            if nxt >= n:
                self._frame_dir = -1
                nxt = n - 2
            elif nxt < 0:
                self._frame_dir = 1
                nxt = 1
            self.frame_index = max(0, min(n - 1, nxt))
        elif mode == "reverse":
            self.frame_index = (self.frame_index - 1) % n
        else:
            self.frame_index = (self.frame_index + 1) % n
        self.img = self.frames[self.frame_index]
        self.label.configure(image=self.img)

    def _cursor_offset(self, max_pull=4):
        """Subtle lean toward cursor when it's within 220px."""
        try:
            mx = self.winfo_pointerx()
            my = self.winfo_pointery()
        except Exception:
            return 0, 0
        cx = self.base_x + self.width // 2
        cy = self.base_y + self.height // 2
        dx = mx - cx
        dy = my - cy
        dist = max(1, (dx * dx + dy * dy) ** 0.5)
        if dist > 220:
            return 0, 0
        pull = (220 - dist) / 220.0 * max_pull
        return int(dx / dist * pull), int(dy / dist * pull)

    # ------------------------------------------------------------------
    # Motion system: per-skin profiles, squash & stretch, throw, wander
    # ------------------------------------------------------------------
    def _detect_skin_name(self):
        """Read the skin flag once; returns 'crab' | 'custom' | 'robot'."""
        try:
            flag = os.path.join(SCRIPT_DIR, "custom_skin.flag")
            if not os.path.exists(flag):
                return "robot"
            with open(flag, "r", encoding="utf-8", errors="replace") as f:
                txt = f.read().lower()
            return "crab" if "crab" in txt else "custom"
        except Exception:
            return "robot"

    def _skin_kind(self):
        return getattr(self, "_skin_name", None) or "robot"

    def _motion_profile(self):
        """Per-skin motion constants (easing, physics, wander)."""
        if self._skin_kind() == "crab":
            return {
                "interval": 40, "ease": 0.40, "squash_gain": 0.009, "max_stretch": 0.08,
                "friction": 0.90, "restitution": 0.50, "gravity": 0.0,
                "wander_speed": 3.4, "wander_chance": 0.32,
            }
        return {
            "interval": 40, "ease": 0.35, "squash_gain": 0.011, "max_stretch": 0.11,
            "friction": 0.92, "restitution": 0.55, "gravity": 0.0,
            "wander_speed": 2.2, "wander_chance": 0.13,
        }

    def _rebuild_pil_frames(self):
        """(Re)load PIL source frames for squash/stretch from the current skin PNGs."""
        frames = []
        for p in ASSET_FRAMES:
            try:
                im = Image.open(p).convert("RGBA")
                _r, _g, _b, a = im.split()
                im.putalpha(a.point(lambda v: 255 if v > 30 else 0))
                frames.append(im)
            except Exception:
                frames.append(None)
        self._pil_frames = frames
        self._scale_cache = {}

    def _pil_frame(self, idx):
        if not self._pil_frames:
            self._rebuild_pil_frames()
        if not self._pil_frames or idx >= len(self._pil_frames):
            return None
        return self._pil_frames[idx]

    def _scaled_label_image(self, idx, sx, sy, flip):
        """ImageTk image (canvas-sized) with the sprite scaled and anchored
        bottom-center, optionally mirrored. Cached by bucketed params."""
        src = self._pil_frame(idx)
        if src is None:
            return None
        W, H = self.width, self.height
        key = (idx, round(sx, 2), round(sy, 2), bool(flip))
        cached = self._scale_cache.get(key)
        if cached is not None:
            return cached
        try:
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
            nw = max(1, int(round(W * sx)))
            nh = max(1, min(H, int(round(H * sy))))
            im = src
            if flip:
                flip_const = getattr(getattr(Image, "Transpose", Image), "FLIP_LEFT_RIGHT", 0)
                im = im.transpose(flip_const)
            im = im.resize((nw, nh), resample)
            canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            canvas.paste(im, ((W - nw) // 2, H - nh), im)
            photo = ImageTk.PhotoImage(canvas)
        except Exception:
            return None
        if len(self._scale_cache) > 240:
            self._scale_cache.clear()
        self._scale_cache[key] = photo
        return photo

    def _apply_sprite_transform(self, vy, prof):
        """Squash & stretch driven by vertical velocity + horizontal facing flip."""
        flip = self._facing < 0
        s = max(-prof["max_stretch"], min(prof["max_stretch"], -vy * prof["squash_gain"]))
        sy = 1.0 + s
        sx = 1.0 - s * 0.6
        if abs(sy - 1.0) < 0.025 and not flip:
            try:
                if 0 <= self.frame_index < len(self.frames):
                    self.label.configure(image=self.frames[self.frame_index])
            except Exception:
                pass
            return
        img = self._scaled_label_image(self.frame_index, sx, sy, flip)
        if img is not None:
            self._cur_scaled_img = img
            try:
                self.label.configure(image=img)
            except Exception:
                pass

    def _begin_throw(self, vx, vy):
        """Start inertial throw from a drag flick (small flicks just clamp)."""
        mag = (vx * vx + vy * vy) ** 0.5
        if mag < 2.0:
            try:
                self._snap_to_edge()
            except Exception:
                pass
            return
        cap = 60.0
        if mag > cap:
            vx = vx / mag * cap
            vy = vy / mag * cap
        self._base_xf = float(self.base_x)
        self._base_yf = float(self.base_y)
        self._vx = float(vx)
        self._vy = float(vy)
        self._throw_active = True
        self._wander_active = False
        self._facing = 1 if vx >= 0 else -1

    def _step_throw(self, prof):
        if not getattr(self, "_throw_active", False):
            return
        self._vx *= prof["friction"]
        self._vy = self._vy * prof["friction"] + prof["gravity"]
        self._base_xf += self._vx
        self._base_yf += self._vy
        left = work_area.left
        right = work_area.right - self.width
        top = work_area.top
        bottom = work_area.bottom - self.height
        if self._base_xf <= left:
            self._base_xf = left
            self._vx = -self._vx * prof["restitution"]
        elif self._base_xf >= right:
            self._base_xf = right
            self._vx = -self._vx * prof["restitution"]
        if self._base_yf <= top:
            self._base_yf = top
            self._vy = -self._vy * prof["restitution"]
        elif self._base_yf >= bottom:
            self._base_yf = bottom
            self._vy = -self._vy * prof["restitution"]
        self.base_x = int(round(self._base_xf))
        self.base_y = int(round(self._base_yf))
        if abs(self._vx) < 0.6 and abs(self._vy) < 0.6:
            self._throw_active = False
            self.base_x = int(round(max(left, min(self._base_xf, right))))
            self.base_y = int(round(max(top, min(self._base_yf, bottom))))
            self._base_xf = float(self.base_x)
            self._base_yf = float(self.base_y)
            try:
                self._sync_minimized_bubble()
            except Exception:
                pass

    def _start_wander(self):
        """Pick a destination on screen and walk to it (autonomous locomotion)."""
        try:
            import random as _r
            if getattr(self, "_throw_active", False) or self.bubble_interactive:
                return
            left = work_area.left
            right = max(left, work_area.right - self.width)
            tx = self.base_x
            for _ in range(6):
                cand = _r.randint(left, right)
                if abs(cand - self.base_x) >= 80:
                    tx = cand
                    break
            self._wander_tx = tx
            self._wander_active = True
            self._base_xf = float(self.base_x)
            self._facing = 1 if tx >= self.base_x else -1
            if self._skin_kind() == "crab":
                self.state = "scuttle" if _r.random() < 0.4 else "crab_walk"
            else:
                self.state = "walk"
            self._state_start_tick = self.tick
        except Exception:
            pass

    def _step_wander(self, prof):
        if getattr(self, "_throw_active", False):
            self._wander_active = False
            return
        if not getattr(self, "_wander_active", False):
            return
        if self.state not in ("walk", "crab_walk", "scuttle"):
            self._wander_active = False
            return
        dx = self._wander_tx - self._base_xf
        step = prof["wander_speed"]
        if abs(dx) <= step:
            self._base_xf = float(self._wander_tx)
            self._wander_active = False
            self.state = "idle"
        else:
            self._base_xf += step if dx > 0 else -step
            self._facing = 1 if dx > 0 else -1
        right = max(work_area.left, work_area.right - self.width)
        self._base_xf = max(work_area.left, min(self._base_xf, right))
        self.base_x = int(round(self._base_xf))

    def _is_crab(self):
        """Detecta si el skin actual es cangrejo (cacheado, sin I/O por frame)."""
        name = getattr(self, "_skin_name", None)
        if name is not None:
            return name == "crab"
        try:
            self._skin_name = self._detect_skin_name()
            return self._skin_name == "crab"
        except Exception:
            return False

    def animate(self):
        state = self.state
        # --- Frame update with per-state speed + mode ---
        if state == "thinking":
            self._advance_frame(speed=2, mode="loop")
        elif state == "happy":
            self._advance_frame(speed=2, mode="pingpong")
        elif state == "dance":
            self._advance_frame(speed=2, mode="pingpong")
        elif state == "talking":
            self._advance_frame(speed=2, mode="pingpong")
        elif state == "sleeping":
            self._advance_frame(speed=8, mode="pingpong")
        elif state == "hover":
            self._advance_frame(speed=2, mode="pingpong")
        elif state == "surprised":
            self._advance_frame(speed=2, mode="pingpong")
        elif state == "yawn":
            self._advance_frame(speed=6, mode="pingpong")
        elif state == "look":
            self._advance_frame(speed=8, mode="pingpong")
        elif state == "wave":
            self._advance_frame(speed=3, mode="loop")
        # --- Crab-specific frame timing ---
        elif state == "crab_walk":
            self._advance_frame(speed=2, mode="loop")
        elif state == "pinch":
            self._advance_frame(speed=3, mode="pingpong")
        elif state == "hide":
            self._advance_frame(speed=10, mode="pingpong")
        elif state == "bubble":
            self._advance_frame(speed=5, mode="loop")
        elif state == "dig":
            self._advance_frame(speed=2, mode="loop")
        elif state == "scuttle":
            self._advance_frame(speed=1, mode="loop")
        else:
            self._advance_frame(speed=4, mode="loop")

        # --- Cursor following (subtle lean) only when idle-ish ---
        cur_dx, cur_dy = (0, 0)
        if state in ("idle", "yawn", "look", "sleeping"):
            cur_dx, cur_dy = self._cursor_offset(max_pull=3)

        # --- Per-state motion: each branch only computes (offset_x, offset_y).
        #     Physics, wander, easing and squash/stretch are applied once below. ---
        offset_x, offset_y = 0, 0
        if state == "idle":
            offset_y = int(math.sin(self.tick / 30) * 2.5)
            offset_x = int(math.cos(self.tick / 50) * 1)
            # Random blink/jump every ~7-12s
            if not hasattr(self, "_next_blink") or self.tick >= self._next_blink:
                import random as _r
                self._next_blink = self.tick + _r.randint(180, 300)
                self._blink_until = self.tick + 6
            if hasattr(self, "_blink_until") and self.tick < self._blink_until:
                offset_y -= 5
            offset_x += cur_dx
            offset_y += cur_dy
        elif state == "hover":
            offset_y = int(math.sin(self.tick / 6) * 4.5) - 4
            offset_x = int(math.sin(self.tick / 3) * 2.5)
        elif state == "thinking":
            offset_y = int(math.sin(self.tick / 6) * 4) - 2
            offset_x = int(math.cos(self.tick / 8) * 3)
        elif state == "happy":
            offset_y = -int(abs(math.sin(self.tick / 4)) * 9)
            offset_x = int(math.sin(self.tick / 7) * 2)
        elif state == "talking":
            offset_x = int(math.sin(self.tick / 4) * 4.5)
            offset_y = -int(abs(math.sin(self.tick / 3.5)) * 5)
        elif state == "wave":
            offset_x = int(math.sin(self.tick / 4) * 8)
            offset_y = int(abs(math.sin(self.tick / 8)) * -2)
        elif state == "dance":
            offset_x = int(math.sin(self.tick / 4) * 6)
            offset_y = -int(abs(math.sin(self.tick / 3)) * 6)
        elif state == "sleeping":
            offset_y = int(math.sin(self.tick / 40) * 3.0) + 2
            offset_x = int(math.cos(self.tick / 80) * 1.0) + cur_dx
        elif state == "surprised":
            elapsed = self.tick - getattr(self, "_state_start_tick", self.tick)
            if elapsed < 10:
                offset_y = -int(elapsed * 1.6)
            else:
                offset_y = -int(max(0, 16 - (elapsed - 10) * 1.5))
            offset_x = 0
        elif state == "yawn":
            elapsed = self.tick - getattr(self, "_state_start_tick", self.tick)
            offset_y = int(-abs(math.sin(elapsed / 24)) * 6) + cur_dy
            offset_x = cur_dx
        elif state == "look":
            offset_x = int(math.sin(self.tick / 20) * 5)
            offset_y = int(math.cos(self.tick / 40) * 1.5)
        elif state == "shy":
            offset_y = int(math.sin(self.tick / 8) * 1) + 4
            offset_x = -3
        elif state == "notebook":
            offset_y = int(abs(math.sin(self.tick / 2.2)) * 2)
            offset_x = int(math.sin(self.tick / 5) * 1)
        elif state == "walk":
            # Walking bob; horizontal travel handled by _step_wander (base_x).
            offset_y = int(abs(math.sin(self.tick / 4)) * -3)
            offset_x = int(math.sin(self.tick / 7) * 1)
        # --- Crab-specific motions (lateral travel handled by _step_wander) ---
        elif state == "crab_walk":
            offset_x = int(math.sin(self.tick / 3) * 2)
            offset_y = int(abs(math.sin(self.tick / 2.5)) * -3)
        elif state == "pinch":
            elapsed = self.tick - getattr(self, "_state_start_tick", self.tick)
            offset_y = -int(abs(math.sin(elapsed / 3)) * 10)
            offset_x = int(math.sin(self.tick / 1.5) * 4)
        elif state == "hide":
            elapsed = self.tick - getattr(self, "_state_start_tick", self.tick)
            if elapsed < 8:
                offset_y = int(elapsed * 2)
            elif elapsed < 30:
                offset_y = 16 + int(math.sin(self.tick / 4) * 1)
            else:
                offset_y = max(0, 16 - int((elapsed - 30) * 1.5))
            offset_x = int(math.sin(self.tick / 5) * 1)
        elif state == "bubble":
            offset_y = -int(abs(math.sin(self.tick / 8)) * 4)
            offset_x = int(math.sin(self.tick / 12) * 2)
        elif state == "dig":
            offset_x = int(math.sin(self.tick / 2) * 5)
            offset_y = int(math.cos(self.tick / 2) * 3) + 2
        elif state == "scuttle":
            offset_x = int(math.sin(self.tick / 2) * 3)
            offset_y = int(abs(math.sin(self.tick / 2)) * -4)
        else:
            offset_y = int(math.sin(self.tick / 30) * 2.5)
            offset_x = int(math.cos(self.tick / 50) * 1)

        # --- Unified motion commit: physics + wander + easing + squash/stretch ---
        prof = self._motion_profile()
        if state == "bounce":
            # run_bounce owns the geometry while bouncing; just keep ticking.
            self.tick += 1
            self.after(prof["interval"], self.animate)
            return
        try:
            self._step_throw(prof)
            self._step_wander(prof)
        except Exception:
            pass
        target_x = self.base_x + offset_x
        target_y = self.base_y + offset_y
        if getattr(self, "_dragging", False):
            # Stick exactly to the cursor while dragging (no idle bob).
            self._render_x = float(self.base_x)
            self._render_y = float(self.base_y)
        elif getattr(self, "_throw_active", False):
            self._render_x = float(target_x)
            self._render_y = float(target_y)
        else:
            ease = prof["ease"]
            self._render_x += (target_x - self._render_x) * ease
            self._render_y += (target_y - self._render_y) * ease
        try:
            vy = self._render_y - self._prev_render_y
            self._prev_render_y = self._render_y
            self._apply_sprite_transform(vy, prof)
        except Exception:
            pass
        self.geometry(f"+{int(round(self._render_x))}+{int(round(self._render_y))}")
        self.tick += 1
        self.after(prof["interval"], self.animate)

    def _set_state_briefly(self, new_state, duration_ms=1200):
        """Set a transient state, then return to idle (unless interrupted)."""
        prev = self.state
        if prev == "bounce":
            return
        self.state = new_state
        self._state_start_tick = self.tick
        if new_state == "crab_walk":
            import random as _r
            self._crab_dir = _r.choice([-1, 1])
        if new_state == "sleeping":
            self.show_thought("Zzz...")
        def _restore():
            if self.state == new_state:
                self.state = "idle"
                if new_state == "sleeping":
                    self.hide_bubble()
        self.after(duration_ms, _restore)

    def _start_idle_behaviors(self):
        """Loop: while idle, occasionally pick a micro-animation (yawn/look/dance/shy)."""
        try:
            import random as _r
            if self.state == "idle" and not self.bubble_interactive:
                # Probabilities tuned to feel alive but not annoying
                pick = _r.random()
                # Autonomous wander: walk to a new spot on screen
                _prof = self._motion_profile()
                if _r.random() < _prof["wander_chance"]:
                    self._start_wander()
                    self.after(_r.randint(14000, 30000), self._start_idle_behaviors)
                    return
                # Robot skin: occasionally pull out a notebook and type
                if (not self._is_crab()) and _r.random() < 0.18:
                    self._start_notebook_animation()
                    self.after(_r.randint(20000, 40000), self._start_idle_behaviors)
                    return
                # Crab skin: bias toward crab-specific animations
                if self._is_crab() and _r.random() < 0.55:
                    crab_pick = _r.random()
                    if crab_pick < 0.30:
                        self._set_state_briefly("crab_walk", 2400)
                    elif crab_pick < 0.50:
                        self._set_state_briefly("pinch", 1500)
                    elif crab_pick < 0.65:
                        self._set_state_briefly("bubble", 2200)
                    elif crab_pick < 0.80:
                        self._set_state_briefly("dig", 1800)
                    elif crab_pick < 0.92:
                        self._set_state_briefly("scuttle", 2000)
                    else:
                        self._set_state_briefly("hide", 3500)
                    # Re-schedule and exit early so we don't double-pick
                    self.after(_r.randint(12000, 28000), self._start_idle_behaviors)
                    return
                # Time-of-day bias
                hr = datetime.datetime.now().hour
                if hr >= 23 or hr < 6:
                    # Late night: tend to sleep
                    if pick < 0.4:
                        self._set_state_briefly("sleeping", 6000)
                    elif pick < 0.55:
                        self._set_state_briefly("yawn", 1800)
                elif hr < 9:
                    if pick < 0.25:
                        self._set_state_briefly("yawn", 1600)
                    elif pick < 0.4:
                        self._set_state_briefly("look", 2000)
                elif 12 <= hr < 18:
                    if pick < 0.18:
                        self._set_state_briefly("dance", 2400)
                    elif pick < 0.32:
                        self._set_state_briefly("look", 1800)
                    elif pick < 0.42:
                        self._set_state_briefly("happy", 900)
                else:
                    if pick < 0.2:
                        self._set_state_briefly("look", 1600)
                    elif pick < 0.32:
                        self._set_state_briefly("yawn", 1500)
                    elif pick < 0.4:
                        self._set_state_briefly("shy", 1200)
        except Exception:
            pass
        # Re-schedule between 15-35 seconds
        try:
            import random as _r
            self.after(_r.randint(15000, 35000), self._start_idle_behaviors)
        except Exception:
            self.after(20000, self._start_idle_behaviors)

    def on_enter(self, _event=None):
        self.state = "hover"
        self.configure(cursor="hand2")
        if not self.bubble_interactive:
            self.show_thought(random.choice(self.BUBBLES))

    def on_leave(self, _event=None):
        self.state = "idle"
        self.configure(cursor="arrow")
        if not self.bubble_interactive:
            self.after(150, self.hide_bubble)

    def on_click(self, _event=None):
        if self._dragging:
            return

        # Prevent immediate reopening if closed by focus loss just now
        hidden_at = getattr(self, "_bubble_hidden_at", 0)
        if time.time() - hidden_at < 0.35:
            return

        # If webview is open, toggle it closed
        if getattr(self, "_webview_visible", False):
            self.hide_bubble()
            return

        # Surprised: micro-reaction al click
        try:
            self._set_state_briefly("surprised", 600)
        except Exception:
            pass
        # If minimized, expand instead of closing
        if self.bubble_minimized and hasattr(self, '_expand_bubble'):
            self._expand_bubble()
            return
        # If bubble is open and interactive, minimize it (keep conversation alive)
        if self.bubble_win is not None and self.bubble_interactive:
            minimize_fn = getattr(self, "_minimize_bubble", None)
            if minimize_fn is not None:
                try:
                    minimize_fn()
                    return
                except Exception:
                    pass
            self.hide_bubble()
            return
        self.state = "bounce"
        # Open bubble loading last conversation (text=None triggers preview load)
        self.show_chat_bubble()
        self.run_bounce(0)

    def on_double_click(self, _event=None):
        # Open or focus the modern chat bubble instead of launching command-line CLI
        self.show_chat_bubble()

    def _rebuild_context_menu(self):
        """Rebuild the desktop context menu using the Claudy AI visual style."""
        try:
            self.menu.delete(0, "end")
        except Exception:
            return
        self.menu.configure(
            bg="#05091d",
            fg="#f7f9ff",
            activebackground="#172862",
            activeforeground="#58c7ff",
            disabledforeground="#6574a8",
            relief="flat",
            bd=1,
            borderwidth=1,
            activeborderwidth=0,
            font=("Bahnschrift SemiBold", 10),
        )
        auto_start_label = "Desactivar inicio automatico" if self._is_auto_start_enabled() else "Activar inicio automatico"
        items = [
            ("Hablar aqui", lambda: self.show_chat_bubble("Que tienes en mente?")),
            ("Abrir terminal", self.launch_claudy),
            None,
            (auto_start_label, self._toggle_auto_start_menu),
            ("Ocultar a bandeja", self._hide_to_tray),
            None,
            ("Reiniciar", self._restart_app),
            ("Cerrar", self.destroy),
        ]
        for item in items:
            if item is None:
                self.menu.add_separator()
            else:
                label, command = item
                self.menu.add_command(label=label, command=command)

    def _context_menu_items(self):
        auto_start_label = "Desactivar inicio automatico" if self._is_auto_start_enabled() else "Activar inicio automatico"
        return [
            ("Hablar aqui", lambda: self.show_chat_bubble("Que tienes en mente?"), "primary"),
            ("Abrir terminal", self.launch_claudy, "primary"),
            None,
            (auto_start_label, self._toggle_auto_start_menu, "normal"),
            ("Ocultar a bandeja", self._hide_to_tray, "normal"),
            None,
            ("Reiniciar", self._restart_app, "normal"),
            ("Cerrar", self.destroy, "danger"),
        ]

    def _hide_context_popup(self, _event=None):
        popup = getattr(self, "_context_popup", None)
        self._context_popup = None
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass

    def _show_context_popup(self, event):
        self._hide_context_popup()
        try:
            popup = tk.Toplevel(self)
            popup.overrideredirect(True)
            popup.attributes("-topmost", True)
            popup.configure(bg="#58c7ff")

            frame = tk.Frame(
                popup,
                bg="#05091d",
                bd=0,
                highlightbackground="#58c7ff",
                highlightthickness=1,
            )
            frame.pack(fill="both", expand=True, padx=1, pady=1)

            def add_row(label, command, kind="normal"):
                normal_bg = "#05091d"
                hover_bg = "#172862"
                fg = "#f7f9ff"
                if kind == "danger":
                    hover_bg = "#1f367e"
                    fg = "#58c7ff"
                row = tk.Label(
                    frame,
                    text=label,
                    bg=normal_bg,
                    fg=fg,
                    anchor="w",
                    padx=22,
                    pady=5,
                    font=("Bahnschrift SemiBold", 10),
                    cursor="hand2",
                )
                row.pack(fill="x")

                def on_enter(_e):
                    row.configure(bg=hover_bg, fg="#ffffff" if kind != "danger" else "#58c7ff")

                def on_leave(_e):
                    row.configure(bg=normal_bg, fg=fg)

                def on_click(_e):
                    self._hide_context_popup()
                    try:
                        command()
                    except Exception as ex:
                        print(f"[context menu] action error: {ex}")

                row.bind("<Enter>", on_enter)
                row.bind("<Leave>", on_leave)
                row.bind("<Button-1>", on_click)

            def add_separator():
                sep = tk.Frame(frame, bg="#223a80", height=1)
                sep.pack(fill="x", padx=0, pady=2)

            for item in self._context_menu_items():
                if item is None:
                    add_separator()
                else:
                    add_row(*item)

            popup.update_idletasks()
            w = popup.winfo_reqwidth()
            h = popup.winfo_reqheight()
            x = max(work_area.left + 8, min(event.x_root, work_area.right - w - 8))
            y = max(work_area.top + 8, min(event.y_root, work_area.bottom - h - 8))
            popup.geometry(f"{w}x{h}+{x}+{y}")
            popup.bind("<Escape>", self._hide_context_popup)
            # Do not close on FocusOut: borderless Tk popups can lose focus
            # immediately on Windows, making the menu disappear before a click.
            popup.after(50, popup.focus_force)
            self._context_popup = popup
        except Exception:
            try:
                self.menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    self.menu.grab_release()
                except Exception:
                    pass

    def _toggle_auto_start_menu(self):
        """Toggle auto-start and update the menu label."""
        if self._is_auto_start_enabled():
            self._disable_auto_start()
            self._show_notification("Claudy", "Inicio automatico desactivado")
        else:
            self._enable_auto_start()
            self._show_notification("Claudy", "Inicio automatico activado")
        self._rebuild_context_menu()

    def _hide_to_tray(self):
        """Oculta TODO (chat + sprite) en la bandeja del sistema."""
        # Recordar si el chat estaba abierto para restaurarlo al mostrar.
        self._chat_open_before_tray = bool(
            (getattr(self, "webview_win", None) and getattr(self, "_webview_visible", False))
            or getattr(self, "bubble_win", None)
        )
        # Cerrar el chat (mueve el webview fuera de pantalla y destruye la burbuja).
        try:
            self.hide_bubble()
        except Exception:
            pass
        # Ocultar el badge de alarmas si está visible.
        try:
            self._alarm_badge_hide()
        except Exception:
            pass
        # Ocultar el sprite.
        self.withdraw()
        self._in_tray = True
        self._refresh_tray_menu()
        self._show_notification("Claudy", "Oculto en la bandeja. Click en el icono para mostrar.")

    def _show_from_tray(self):
        """Restaura Claudy desde la bandeja: vuelve el sprite y, si el chat estaba
        abierto al ocultar, lo reabre."""
        self._in_tray = False
        self._refresh_tray_menu()
        try:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
        except Exception:
            pass
        if getattr(self, "_chat_open_before_tray", False):
            self._chat_open_before_tray = False
            try:
                self.show_chat_bubble()
            except Exception:
                pass

    def _refresh_tray_menu(self):
        """Refresca el menú nativo de la bandeja para reflejar el estado actual."""
        icon = getattr(self, "_tray_icon", None)
        if icon is not None:
            try:
                icon.update_menu()
            except Exception:
                pass

    def _on_drag_start(self, event):
        self._dragging = True
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._drag_offset_x = event.x
        self._drag_offset_y = event.y
        self._drag_last_x = event.x_root
        self._drag_last_y = event.y_root
        self._drag_vx = 0.0
        self._drag_vy = 0.0
        self._throw_active = False
        self._wander_active = False
        self._cancel_idle_timer()

    def _on_drag_motion(self, event):
        if not self._dragging:
            return
        new_x = self.winfo_x() + event.x - self._drag_offset_x
        new_y = self.winfo_y() + event.y - self._drag_offset_y
        self.geometry(f"+{new_x}+{new_y}")
        self.base_x = new_x
        self.base_y = new_y
        # Keep render + physics position in sync while dragging, and track velocity
        self._base_xf = float(new_x)
        self._base_yf = float(new_y)
        self._render_x = float(new_x)
        self._render_y = float(new_y)
        self._prev_render_y = float(new_y)
        self._drag_vx = 0.55 * self._drag_vx + 0.45 * (event.x_root - getattr(self, "_drag_last_x", event.x_root))
        self._drag_vy = 0.55 * self._drag_vy + 0.45 * (event.y_root - getattr(self, "_drag_last_y", event.y_root))
        self._drag_last_x = event.x_root
        self._drag_last_y = event.y_root
        # Keep the minimized Zzz bubble glued to the pet as it moves
        self._sync_minimized_bubble()
        # If the webview chat is open, reposition it above the new Claudy position
        if getattr(self, "_webview_visible", False) and getattr(self, "webview_win", None) is not None:
            try:
                wx, wy = self.bubble_position(CHAT_WEBVIEW_PHYS_W, CHAT_WEBVIEW_PHYS_H)
                self.webview_win.move(*physical_to_webview(wx, wy))
            except Exception:
                pass

    def _on_drag_release(self, event):
        if not self._dragging:
            return
        self._dragging = False
        # Detectar si fue un click (poco movimiento) o un drag
        drag_distance = abs(event.x_root - getattr(self, '_drag_start_x', event.x_root)) + abs(event.y_root - getattr(self, '_drag_start_y', event.y_root))
        if drag_distance < 10:
            # Fue un click, no un drag
            self.on_click()
            return
        # Throw with inertia; tiny flicks just clamp to screen bounds.
        self._begin_throw(self._drag_vx, self._drag_vy)

    def _snap_to_edge(self):
        """Clamp Claudy inside screen bounds only — no forced edge-snapping.
        This lets the user place Claudy anywhere on screen and have it stay there."""
        x = self.winfo_x()
        y = self.winfo_y()
        w = self.winfo_width()
        h = self.winfo_height()
        margin = 0  # allow Claudy to sit flush with screen edges

        # Clamp to screen boundaries (using work_area coords)
        x = max(work_area.left + margin, min(x, work_area.right - w - margin))
        y = max(work_area.top + margin, min(y, work_area.bottom - h - margin))

        self.base_x = x
        self.base_y = y
        self.geometry(f"+{x}+{y}")
        # Re-sync the Zzz bubble after clamping
        self._sync_minimized_bubble()

    # ------------------------------------------------------------------
    # P1-6: Windows auto-start
    # ------------------------------------------------------------------
    def _is_auto_start_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False

    def _enable_auto_start(self):
        try:
            exe_path = sys.executable
            script_path = os.path.abspath(__file__)
            # Run python.exe with the script path as argument.
            value = f'"{exe_path}" "{script_path}"'
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, value)
            winreg.CloseKey(key)
        except Exception:
            pass

    def _disable_auto_start(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------------
    # P1-8: Native Windows notifications
    # ------------------------------------------------------------------
    def _show_notification(self, title, message):
        """Show a native Windows toast notification."""
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            # Use the first sprite as icon.
            icon_path = ASSET_FRAMES[0] if os.path.exists(ASSET_FRAMES[0]) else None
            toaster.show_toast(title, message, duration=3, icon_path=icon_path, threaded=True)
        except ImportError:
            # Fallback: no notification if win10toast not installed.
            pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # P1-7: System tray icon (pystray)
    # ------------------------------------------------------------------
    def _create_tray_icon(self):
        """Create a system tray icon with menu options."""
        try:
            import pystray
            from PIL import Image as PILImage
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pystray", "--quiet"])
            import pystray
            from PIL import Image as PILImage

        # Create a small icon image from the first sprite.
        sprite_path = ASSET_FRAMES[0]
        if os.path.exists(sprite_path):
            icon_image = PILImage.open(sprite_path).resize((16, 16))
        else:
            # Fallback: create a simple colored square.
            icon_image = PILImage.new("RGBA", (16, 16), (124, 107, 255, 255))

        def _show_all():
            self._show_from_tray()

        def _hide_all():
            self._hide_to_tray()

        def _toggle_all():
            try:
                if getattr(self, "_in_tray", False) or self.state() == "withdrawn":
                    _show_all()
                else:
                    _hide_all()
            except Exception:
                pass

        # Route to Tk mainloop (pystray runs in a separate thread; Tk is not thread-safe).
        def on_show_tray(icon, item):
            self.after(0, _show_all)

        def on_hide_tray(icon, item):
            self.after(0, _hide_all)

        def on_toggle_tray(icon, item):
            self.after(0, _toggle_all)

        def on_toggle_auto_start(icon, item):
            if self._is_auto_start_enabled():
                self._disable_auto_start()
                self._show_notification("Claudy", "Inicio automatico desactivado")
            else:
                self._enable_auto_start()
                self._show_notification("Claudy", "Inicio automatico activado")

        def on_quit(icon, item):
            try:
                self._run_backup_on_exit()
            except Exception:
                pass
            icon.stop()
            self.destroy()

        menu = pystray.Menu(
            pystray.MenuItem("Mostrar", on_toggle_tray, default=True, visible=False),
            # "Mostrar" solo cuando está oculto; "Ocultar" solo cuando está visible.
            pystray.MenuItem("Mostrar", on_show_tray, visible=lambda item: getattr(self, "_in_tray", False)),
            pystray.MenuItem("Ocultar", on_hide_tray, visible=lambda item: not getattr(self, "_in_tray", False)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Inicio automatico", on_toggle_auto_start, checked=lambda _: self._is_auto_start_enabled()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", on_quit),
        )

        self._tray_icon = pystray.Icon("claudy", icon_image, "Claudy", menu)
        # Run tray in daemon thread so it doesn't block the mainloop.
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _backup_flag_path(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", "backup_on_exit.enabled")

    def _backup_script_path(self):
        return os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "scripts", "backup-claudy-full.ps1",
        ))

    def _set_auto_backup(self, enabled):
        flag = self._backup_flag_path()
        os.makedirs(os.path.dirname(flag), exist_ok=True)
        if enabled:
            with open(flag, "w", encoding="utf-8") as f:
                f.write("1")
            return "Auto-backup al cerrar Claudy: ACTIVADO. Se respaldara en G:\\Mi unidad\\Claudy-Backups."
        else:
            try:
                os.remove(flag)
            except FileNotFoundError:
                pass
            return "Auto-backup al cerrar Claudy: DESACTIVADO."

    def _backup_status(self):
        enabled = os.path.exists(self._backup_flag_path())
        backup_dir = "G:\\Mi unidad\\Claudy-Backups"
        lines = [f"Auto-backup al cerrar: {'ACTIVADO' if enabled else 'desactivado'}"]
        if os.path.isdir(backup_dir):
            try:
                files = sorted(
                    [f for f in os.listdir(backup_dir) if f.startswith("claudy-full-") and f.endswith(".zip")],
                    reverse=True,
                )
                if files:
                    lines.append(f"Backups en {backup_dir}: {len(files)}")
                    last = os.path.join(backup_dir, files[0])
                    size_mb = round(os.path.getsize(last) / (1024 * 1024), 1)
                    lines.append(f"Mas reciente: {files[0]} ({size_mb} MB)")
                else:
                    lines.append(f"Sin backups aun en {backup_dir}.")
            except Exception as e:
                lines.append(f"Error leyendo {backup_dir}: {e}")
        else:
            lines.append(f"{backup_dir} no existe (Google Drive no montado?)")
        lines.append("")
        lines.append("Comandos: /backup [ahora] | /backup on | /backup off | /backup status")
        return "\n".join(lines)

    def _run_backup_now(self):
        script = self._backup_script_path()
        if not os.path.exists(script):
            return f"No encuentro el script: {script}"
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", script, "-Quiet"],
                capture_output=True, text=True, timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if r.returncode == 0:
                # Find the most recent zip
                d = "G:\\Mi unidad\\Claudy-Backups"
                try:
                    files = sorted(
                        [f for f in os.listdir(d) if f.startswith("claudy-full-") and f.endswith(".zip")],
                        reverse=True,
                    )
                    if files:
                        last = os.path.join(d, files[0])
                        size_mb = round(os.path.getsize(last) / (1024 * 1024), 1)
                        return f"Backup listo: {files[0]} ({size_mb} MB)\n[CLAUDY_PATH:{last}]"
                except Exception:
                    pass
                return "Backup completado."
            err = (r.stderr or r.stdout or "").strip()[-500:]
            if r.returncode == 2:
                return "Google Drive (G:) no esta disponible. Conecta Drive y reintenta."
            return f"Backup fallo (codigo {r.returncode}): {err}"
        except subprocess.TimeoutExpired:
            return "El backup tardo mas de 5 minutos. Revisa G:\\Mi unidad\\Claudy-Backups manualmente."
        except Exception as e:
            return f"Error ejecutando backup: {e}"

    def _run_backup_on_exit(self):
        """Fire-and-forget Google Drive backup on exit. Non-blocking, silent on failure."""
        try:
            # Flag file lets the user opt-out by deleting it; opt-in default = exists.
            flag = os.path.join(os.path.expanduser("~"), ".claudy", "backup_on_exit.enabled")
            if not os.path.exists(flag):
                return  # opt-in: not enabled
            script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "..", "scripts", "backup-claudy-full.ps1",
            )
            script = os.path.normpath(script)
            if not os.path.exists(script):
                return
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                 "-ExecutionPolicy", "Bypass",
                 "-File", script, "-Quiet"],
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    def run_bounce(self, frame):
        offsets = [0, -5, -10, -14, -8, -3, 0, 3, 0]
        if frame < len(offsets):
            self.geometry(f"+{self.base_x}+{self.base_y + offsets[frame]}")
            self.after(40, lambda: self.run_bounce(frame + 1))
        else:
            self.state = "idle"

    def _check_google_drive(self):
        """Check if Google Drive virtual folder is available in real-time."""
        is_connected = False
        try:
            drive_path = r"G:\Mi unidad"
            is_connected = os.path.isdir(drive_path)
            
            # Update UI if bubble_canvas is active
            canvas = getattr(self, "_bubble_canvas", None)
            if canvas:
                try:
                    # Find elements by tag
                    dots = canvas.find_withtag("drive_status_dot")
                    texts = canvas.find_withtag("drive_status_text")
                    
                    dot_color = "#00ff99" if is_connected else "#ff3838"
                    text_val = "Drive OK" if is_connected else "Drive OFF"
                    text_color = "#ffffff" if is_connected else "#ff8888"
                    
                    for dot in dots:
                        canvas.itemconfig(dot, fill=dot_color)
                    for txt in texts:
                        canvas.itemconfig(txt, text=text_val, fill=text_color)
                except Exception as e:
                    print(f"[drive check UI update] error: {e}")
                    
            # Handle warnings and notifications if status changed
            was_connected = getattr(self, "_drive_connected", True)
            self._drive_connected = is_connected
            self._eval_in_web(f"updateDriveConnected({json.dumps(is_connected)})")
            
            if was_connected and not is_connected:
                # Transition to disconnected: Show warnings
                try:
                    self.show_thought("⚠️ ¡Alerta! Google Drive se ha desconectado.\nPor favor, verifica la conexión para no perder datos.")
                    chat = getattr(self, "_chat_view", None)
                    if chat:
                        chat.add_system("⚠️ ADVERTENCIA: Se ha detectado una desconexión de Google Drive. Algunas funcionalidades comerciales y de contexto podrían no funcionar.")
                except Exception as ne:
                    print(f"[drive disconnect notification] error: {ne}")
            elif not was_connected and is_connected:
                # Transition to reconnected
                try:
                    self.show_thought("✅ Google Drive restablecido con éxito.")
                    chat = getattr(self, "_chat_view", None)
                    if chat:
                        chat.add_system("✅ Conexión con Google Drive restablecida.")
                except Exception as ne:
                    print(f"[drive reconnect notification] error: {ne}")
        except Exception as e:
            print(f"[check_google_drive] error: {e}")
            self._drive_connected = False
            # Try to force UI to OFF on check exception
            canvas = getattr(self, "_bubble_canvas", None)
            if canvas:
                try:
                    dots = canvas.find_withtag("drive_status_dot")
                    texts = canvas.find_withtag("drive_status_text")
                    for dot in dots:
                        canvas.itemconfig(dot, fill="#ff3838")
                    for txt in texts:
                        canvas.itemconfig(txt, text="Drive OFF", fill="#ff8888")
                except Exception:
                    pass
        finally:
            # Poll again every 5000 ms (5 seconds) — guaranteed to run
            self.after(5000, self._check_google_drive)

    def hide_bubble(self):
        self._cancel_idle_timer()
        self._stop_zzz_animation()
        if self.bubble_win:
            try:
                self.bubble_win.destroy()
            except Exception:
                pass
            self.bubble_win = None
        if self.webview_win:
            try:
                # Move off-screen instead of hide() to keep WebView2 rendered
                self.webview_win.move(-9999, -9999)
            except Exception:
                pass
        # Also close the Tkinter history window if it is open
        if self.history_win is not None:
            try:
                self.history_win.destroy()
            except Exception:
                pass
            self.history_win = None
        self._webview_visible = False
        self._bubble_hidden_at = time.time()
        self._bubble_canvas = None
        self._chat_view = None
        self.bubble_interactive = False
        self.bubble_minimized = False
        # Restore Claudy topmost now that the webview is hidden
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
            
        # Restore pre-chat pet position if saved
        if hasattr(self, "_pre_chat_pet_x") and self._pre_chat_pet_x is not None:
            try:
                self.geometry(f"+{self._pre_chat_pet_x}+{self._pre_chat_pet_y}")
                self.base_x = self._pre_chat_pet_x
                self.base_y = self._pre_chat_pet_y
            except Exception:
                pass
            self._pre_chat_pet_x = None
            self._pre_chat_pet_y = None

    def _on_bubble_focus_out(self, _event=None):
        # Delay check so focus can settle on the new widget
        self.after(50, self._check_bubble_focus)

    def _check_bubble_focus(self):
        if not self.bubble_win:
            return

        if getattr(self, "_webview_focused", False) or getattr(self, "_is_picking_file", False):
            self.after(200, self._check_bubble_focus)
            return

        # Grace period after opening: avoid auto-closing the welcome bubble
        # before the user has had a chance to move the mouse onto it.
        opened_at = getattr(self, "_bubble_opened_at", 0)
        if opened_at and (time.time() - opened_at) < 2.0:
            self.after(200, self._check_bubble_focus)
            return

        # If the pet is currently bouncing, its bounds are shifting rapidly.
        # Wait for the bounce to finish before checking focus bounds.
        if self.state == "bounce":
            self.after(50, self._check_bubble_focus)
            return

        # Use mouse position to decide: if the cursor is still over the
        # bubble or the pet we keep the chat open (the user is simply
        # clicking around inside the app). If the cursor is outside both,
        # the user clicked on another window/app and we close.
        mx = self.winfo_pointerx()
        my = self.winfo_pointery()

        # Bubble bounds
        if getattr(self, "webview_win", None) is not None and getattr(self, "_webview_visible", False):
            bx1, by1 = self.bubble_position(CHAT_WEBVIEW_PHYS_W, CHAT_WEBVIEW_PHYS_H)
            bx2 = bx1 + CHAT_WEBVIEW_PHYS_W
            by2 = by1 + CHAT_WEBVIEW_PHYS_H
        else:
            bx1 = self.bubble_win.winfo_rootx()
            by1 = self.bubble_win.winfo_rooty()
            bx2 = bx1 + self.bubble_win.winfo_width()
            by2 = by1 + self.bubble_win.winfo_height()

        if bx1 <= mx <= bx2 and by1 <= my <= by2:
            return

        # Pet bounds
        px1 = self.winfo_rootx()
        py1 = self.winfo_rooty()
        px2 = px1 + self.winfo_width()
        py2 = py1 + self.winfo_height()
        if px1 <= mx <= px2 and py1 <= my <= py2:
            return

        # History window bounds (keep chat open while browsing history)
        if self.history_win is not None:
            try:
                hx1 = self.history_win.winfo_rootx()
                hy1 = self.history_win.winfo_rooty()
                hx2 = hx1 + self.history_win.winfo_width()
                hy2 = hy1 + self.history_win.winfo_height()
                if hx1 <= mx <= hx2 and hy1 <= my <= hy2:
                    return
            except tk.TclError:
                pass

        # Cursor is outside both; close side panels and hide/minimize the chat.
        # Webview chat: close the in-HTML panels (Calendar/History) AND hide the
        # whole window. minimize() only resizes the (withdrawn) Tk bubble, so it
        # would leave the webview on-screen — for the webview we must hide_bubble().
        if getattr(self, "webview_win", None) is not None and getattr(self, "_webview_visible", False):
            try:
                # Fire-and-forget JS to hide the panels in the React state
                self.webview_win.evaluate_js("window.__claudy_close_panels && window.__claudy_close_panels();")
            except Exception:
                pass
            self.hide_bubble()
            return

        if self.bubble_minimized:
            return
        minimize_fn = getattr(self, "_minimize_bubble", None)
        if minimize_fn is not None:
            try:
                minimize_fn()
                return
            except Exception:
                pass
        self.hide_bubble()

    def bubble_position(self, width, height):
        margin = 18      # screen-edge breathing room
        pet_gap = 4      # gap between Claudy and the bubble/chat
        pet_x = self.base_x
        pet_y = self.base_y
        pet_w = self.width
        pet_h = self.height

        if width >= 500:
            # Large chat window: position ABOVE the pet so Claudy stays visible
            # below it. Anchor horizontally to the pet's side: if pet is near the
            # right edge, align chat's right edge with pet's right edge (and vice
            # versa). Fall back to side-by-side only when the chat is taller than
            # the available vertical space above the pet.
            available_above = pet_y - work_area.top - pet_gap
            if height <= available_above:
                # Anchor to whichever side the pet is closer to, so the chat
                # doesn't get clamped off-screen on the opposite edge.
                space_left = pet_x - work_area.left
                space_right = work_area.right - (pet_x + pet_w)
                if space_right <= space_left:
                    # Pet is near right edge → align chat's right edge to pet's right edge
                    x = (pet_x + pet_w) - width
                else:
                    # Pet near left edge → align chat's left edge to pet's left edge
                    x = pet_x
                y = pet_y - height - pet_gap
            else:
                # Chat doesn't fit above → fall back to side-by-side
                space_left = pet_x - work_area.left
                space_right = work_area.right - (pet_x + pet_w)
                if space_left >= space_right:
                    x = pet_x - width - pet_gap
                else:
                    x = pet_x + pet_w + pet_gap
                y = pet_y + pet_h - height
        else:
            # Position small thought bubble ABOVE Claudy, centered horizontally
            x = pet_x + pet_w // 2 - width // 2
            y = pet_y - height - pet_gap

            # If it doesn't fit above, try beside (left, then right)
            if y < work_area.top + margin:
                y = work_area.top + margin
                left_x = pet_x - width - pet_gap
                right_x = pet_x + pet_w + pet_gap
                if left_x >= work_area.left + margin:
                    x = left_x
                elif right_x + width <= work_area.right - margin:
                    x = right_x

        # Clamp to screen edges
        x = max(work_area.left + margin, min(x, work_area.right - width - margin))
        y = max(work_area.top + margin, min(y, work_area.bottom - height - margin))
        return x, y

    def minimized_position(self, size):
        """Position for the minimized Zzz bubble: floats just above pet's head."""
        pet_x = self.base_x
        pet_y = self.base_y
        pet_w = self.width
        # Center horizontally on pet, closer to its head
        x = pet_x + pet_w // 2 - size // 2
        y = pet_y - size + 42
        return x, y

    def _sync_minimized_bubble(self):
        """If chat is minimized, keep the Zzz bubble glued to the pet."""
        if not (self.bubble_win and self.bubble_minimized):
            return
        try:
            sz = BUBBLE_MINI_SIZE
            cx, cy = self.minimized_position(sz)
            self.bubble_win.geometry(f"{sz}x{sz}+{cx}+{cy}")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Bubble drawing helpers
    # ------------------------------------------------------------------
    def _rounded_bubble_path(self, w, h, r, tail_h=10, tail_w=14):
        """Return a list of (x,y) points for a speech-bubble polygon."""
        points = []
        # Top edge.
        points += self._arc_points(r, r, r, 180, 270)
        points += self._arc_points(w - r, r, r, 270, 360)
        # Right edge.
        points += self._arc_points(w - r, h - r - tail_h, r, 0, 45)
        # Tail.
        cx = w // 2
        points.append((cx + tail_w // 2, h - tail_h))
        points.append((cx, h))
        points.append((cx - tail_w // 2, h - tail_h))
        # Bottom-left rounding.
        points += self._arc_points(r, h - r - tail_h, r, 135, 180)
        return points

    @staticmethod
    def _arc_points(cx, cy, r, start_deg, end_deg, steps=8):
        pts = []
        for i in range(steps + 1):
            ang = math.radians(start_deg + (end_deg - start_deg) * i / steps)
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        return pts

    def _draw_bubble(self, canvas, w, h, bg, border):
        style = THEME.get("style", "glass")
        if style == "terminal":
            self._draw_bubble_terminal(canvas, w, h, bg, border)
        elif style == "editorial":
            self._draw_bubble_editorial(canvas, w, h, bg, border)
        elif style == "minimal":
            self._draw_bubble_minimal(canvas, w, h, bg, border)
        elif style == "vintage":
            self._draw_bubble_vintage(canvas, w, h, bg, border)
        else:
            self._draw_bubble_glass(canvas, w, h, bg, border)

    def _draw_bubble_vintage(self, canvas, w, h, bg, border):
        """Parchment paper background with grid lines and leather frame."""
        try:
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            radius = 16

            # 1. Leather/wood outer frame (dark brown rounded rect)
            frame_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            frame_mask = Image.new("L", (w, h), 0)
            ImageDraw.Draw(frame_mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
            frame_fill = Image.new("RGBA", (w, h), (61, 52, 41, 255))  # #3d3429
            frame_fill.putalpha(frame_mask)
            img = Image.alpha_composite(img, frame_fill)

            # 2. Inner parchment paper area (inset 8px)
            inset = 8
            paper_w, paper_h = w - inset * 2, h - inset * 2
            paper = Image.new("RGBA", (paper_w, paper_h), (0, 0, 0, 0))
            paper_mask = Image.new("L", (paper_w, paper_h), 0)
            ImageDraw.Draw(paper_mask).rounded_rectangle(
                (0, 0, paper_w - 1, paper_h - 1), radius=radius - 4, fill=255)
            # Paper color with subtle noise
            paper_base = Image.new("RGBA", (paper_w, paper_h), (212, 197, 160, 255))  # #d4c5a0
            paper_base.putalpha(paper_mask)
            img.paste(paper_base, (inset, inset), paper_base)

            # 3. Grid lines on paper
            draw = ImageDraw.Draw(img)
            grid_color = (204, 190, 156, 255)  # very faint
            grid_spacing = 20
            for gx in range(inset + grid_spacing, w - inset, grid_spacing):
                draw.line([(gx, inset + 4), (gx, h - inset - 4)], fill=grid_color, width=1)
            for gy in range(inset + grid_spacing, h - inset, grid_spacing):
                draw.line([(inset + 4, gy), (w - inset - 4, gy)], fill=grid_color, width=1)

            # 4. Leather frame border (2px)
            draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius,
                                   outline=(90, 78, 61, 255), width=2)
            # Inner border on paper edge
            draw.rounded_rectangle((inset - 1, inset - 1, w - inset, h - inset),
                                   radius=radius - 4, outline=(160, 145, 115, 255), width=1)

            # 5. Corner studs (small circles at corners)
            stud_r = 4
            stud_color = (120, 105, 82, 200)
            for sx, sy in [(14, 14), (w - 15, 14), (14, h - 15), (w - 15, h - 15)]:
                draw.ellipse((sx - stud_r, sy - stud_r, sx + stud_r, sy + stud_r),
                             fill=stud_color, outline=(80, 70, 55, 255))

            tk_img = ImageTk.PhotoImage(img)
            self._bg_photo_image_ref = tk_img
            canvas.create_image(0, 0, anchor="nw", image=tk_img, tags=("bubble_bg",))
        except Exception:
            canvas.create_rectangle(0, 0, w, h, fill="#d4c5a0", outline="#5a4e3d", width=2,
                                    tags=("bubble_bg",))

    def _draw_bubble_minimal(self, canvas, w, h, bg, border):
        """Matte solid background with clean 1px border — Obsidian Clean theme."""
        try:
            bg_rgb = (10, 10, 12)  # #0a0a0c
            border_rgb = (39, 39, 42)  # #27272a
            radius = 24
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            mask = Image.new("L", (w, h), 0)
            mask_d = ImageDraw.Draw(mask)
            mask_d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
            fill_layer = Image.new("RGBA", (w, h), (*bg_rgb, 255))
            fill_layer.putalpha(mask)
            img = Image.alpha_composite(img, fill_layer)
            draw_on = ImageDraw.Draw(img)
            draw_on.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius,
                                      outline=(*border_rgb, 255), width=1)
            tk_img = ImageTk.PhotoImage(img)
            self._bg_photo_image_ref = tk_img
            canvas.create_image(0, 0, anchor="nw", image=tk_img, tags=("bubble_bg",))
        except Exception:
            canvas.create_rectangle(0, 0, w, h, fill=bg, outline=border, width=1,
                                    tags=("bubble_bg",))

    def _draw_bubble_glass(self, canvas, w, h, bg, border):
        # Premium neon shell: deep gradient, vignette, dotted texture and soft dual glow.
        try:
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)

            top_rgb = _hex_to_rgb("#07142d")
            bottom_rgb = _hex_to_rgb("#070814")
            accent_left = _hex_to_rgb(THEME.get("accent_glow", "#58c7ff"))
            accent_right = _hex_to_rgb(THEME.get("accent", "#c02dff"))

            for y in range(h):
                t = y / h
                r = int(top_rgb[0] + (bottom_rgb[0] - top_rgb[0]) * t)
                g = int(top_rgb[1] + (bottom_rgb[1] - top_rgb[1]) * t)
                b = int(top_rgb[2] + (bottom_rgb[2] - top_rgb[2]) * t)
                d.line([(0, y), (w, y)], fill=(r, g, b, 255))

            for i in range(0, w, 12):
                for j in range(0, h, 12):
                    blend = i / max(1, w - 1)
                    dot_rgb = (
                        int(accent_left[0] * (1 - blend) + accent_right[0] * blend),
                        int(accent_left[1] * (1 - blend) + accent_right[1] * blend),
                        int(accent_left[2] * (1 - blend) + accent_right[2] * blend),
                    )
                    d.ellipse((i, j, i + 1, j + 1), fill=(*dot_rgb, 28))

            vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            vd = ImageDraw.Draw(vignette)
            vd.ellipse((-w * 0.25, -h * 0.1, w * 0.55, h * 0.7), fill=(*accent_left, 48))
            vd.ellipse((w * 0.45, h * 0.05, w * 1.15, h * 0.95), fill=(*accent_right, 42))
            vignette = vignette.filter(ImageFilter.GaussianBlur(52))
            img = Image.alpha_composite(img, vignette)

            mask = Image.new("L", (w, h), 0)
            mask_d = ImageDraw.Draw(mask)
            radius = 34
            mask_d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
            img.putalpha(mask)

            glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.rounded_rectangle((6, 6, w - 7, h - 7), radius=radius,
                                 outline=(*accent_left, 160), width=4)
            gd.rounded_rectangle((10, 10, w - 11, h - 11), radius=radius - 4,
                                 outline=(*accent_right, 140), width=3)
            glow = glow.filter(ImageFilter.GaussianBlur(10))
            img = Image.alpha_composite(glow, img)

            draw_on_img = ImageDraw.Draw(img)
            border_rgb = _hex_to_rgb(border)
            draw_on_img.rounded_rectangle((6, 6, w - 7, h - 7), radius=radius,
                                          outline=(*border_rgb, 255), width=2)
            draw_on_img.rounded_rectangle((14, 14, w - 15, h - 15), radius=26,
                                          outline=(*_hex_to_rgb(THEME.get("divider", "#4f2cc8")), 135), width=1)

            tk_img = ImageTk.PhotoImage(img)
            self._bg_photo_image_ref = tk_img
            canvas.create_image(0, 0, anchor="nw", image=tk_img, tags=("bubble_bg",))
        except Exception:
            outer = self._rounded_bubble_path(w, h, 22, tail_h=0, tail_w=0)
            canvas.create_polygon(outer, smooth=True, fill=bg, outline=border, width=2,
                                  tags=("bubble_bg",))

    def _draw_bubble_terminal(self, canvas, w, h, bg, border):
        # Sharp rectangle, scanlines, double border, CRT corner glow
        canvas.create_rectangle(0, 0, w, h, fill=bg, outline="", tags=("bubble_bg",))
        # Scanlines — horizontal faint lines every 3px
        for y in range(0, h, 3):
            canvas.create_line(0, y, w, y, fill=THEME["divider"], width=1, tags=("bubble_bg",))
        # Double border — outer thin, inner accent
        canvas.create_rectangle(0, 0, w - 1, h - 1, outline=border, width=1, tags=("bubble_bg",))
        canvas.create_rectangle(4, 4, w - 5, h - 5, outline=THEME["accent"], width=1, tags=("bubble_bg",))
        # Tail/pointer at bottom-center
        cx = w // 2
        canvas.create_polygon(
            [cx - 8, h - 1, cx, h + 8, cx + 8, h - 1],
            fill=bg, outline=THEME["accent"], width=1, tags=("bubble_bg",)
        )
        # Corner brackets (CRT corners)
        for (x0, y0, x1, y1, x2, y2) in [
            (8, 8, 8, 16, 16, 8),               # TL
            (w - 9, 8, w - 9, 16, w - 17, 8),    # TR
            (8, h - 9, 8, h - 17, 16, h - 9),    # BL
            (w - 9, h - 9, w - 9, h - 17, w - 17, h - 9),  # BR
        ]:
            canvas.create_line(x0, y0, x1, y1, fill=THEME["accent_glow"], width=2, tags=("bubble_bg",))
            canvas.create_line(x0, y0, x2, y2, fill=THEME["accent_glow"], width=2, tags=("bubble_bg",))

    def _draw_bubble_editorial(self, canvas, w, h, bg, border):
        # Paper-like: cream background, single hairline border, no shadow drama
        canvas.create_rectangle(0, 0, w, h, fill=bg, outline="", tags=("bubble_bg",))
        # A single accent line on top (editorial bar)
        canvas.create_rectangle(0, 0, w, 3, fill=THEME["accent"], outline="", tags=("bubble_bg",))
        # Hairline border
        canvas.create_rectangle(0, 0, w - 1, h - 1, outline=border, width=1, tags=("bubble_bg",))
        # Tail
        cx = w // 2
        canvas.create_polygon(
            [cx - 7, h - 1, cx, h + 7, cx + 7, h - 1],
            fill=bg, outline=border, width=1, tags=("bubble_bg",)
        )

    def show_thought(self, text):
        self.hide_bubble()
        self.bubble_interactive = False

        bub = tk.Toplevel(self)
        bub.overrideredirect(True)
        bub.attributes("-topmost", True)
        bub.configure(bg=TRANSPARENT_COLOR)
        bub.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        # Measure text to auto-size.
        temp = tk.Label(bub, text=text, font=("Bahnschrift SemiBold", 10), wraplength=220)
        temp.update_idletasks()
        tw, th = temp.winfo_reqwidth(), temp.winfo_reqheight()
        temp.destroy()

        pad_x, pad_y = 28, 20
        width = max(160, tw + pad_x * 2)
        height = max(70, th + pad_y * 2 + 10)

        canvas = tk.Canvas(bub, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        canvas.pack()

        try:
            img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.rounded_rectangle((4, 4, width - 5, height - 5), radius=22,
                                 outline=(192, 45, 255, 150), width=4)
            glow = glow.filter(ImageFilter.GaussianBlur(7))
            img = Image.alpha_composite(img, glow)
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((8, 8, width - 9, height - 9), radius=20,
                                fill=(5, 9, 29, 245), outline=(88, 199, 255, 190), width=1)
            d.ellipse((18, height - 16, 28, height - 6), fill=(5, 9, 29, 230),
                      outline=(88, 199, 255, 160), width=1)
            # Pre-composite onto magenta background so semi-transparent pixels
            # don't bleed pink through Tkinter's -transparentcolor.
            bg_layer = Image.new("RGBA", (width, height), (255, 0, 255, 255))
            composited = Image.alpha_composite(bg_layer, img)
            # Convert to RGB (drop alpha) since we're using chroma-key transparency
            final = composited.convert("RGB")
            # Snap near-magenta pixels to exact #FF00FF so chroma-key works
            px = final.load()
            for _y in range(final.height):
                for _x in range(final.width):
                    r, g, b = px[_x, _y]
                    if r > 200 and g < 55 and b > 200:
                        px[_x, _y] = (255, 0, 255)
            tk_img = ImageTk.PhotoImage(final)
            self._thought_bg_ref = tk_img
            canvas.create_image(0, 0, anchor="nw", image=tk_img)
        except Exception:
            canvas.create_polygon(
                self._rounded_bubble_path(width, height, 22, tail_h=0, tail_w=0),
                smooth=True, fill="#05091d", outline="#58c7ff", width=1,
            )

        canvas.create_text(
            width // 2, height // 2 - 4,
            text=text, width=width - pad_x * 2,
            fill="#f7f9ff",
            font=("Bahnschrift SemiBold", 10),
            justify="center",
        )

        cx, cy = self.bubble_position(width, height)
        bub.geometry(f"{width}x{height}+{cx}+{cy}")
        self.bubble_win = bub

    def show_chat_bubble(self, text=None):
        # If a non-interactive thought bubble is open, destroy it first
        if self.bubble_win is not None and not self.bubble_interactive:
            try:
                self.bubble_win.destroy()
            except tk.TclError:
                pass
            self.bubble_win = None

        # If already open, reposition above current pet location and bring it to front
        if self.bubble_win is not None:
            try:
                w = self.bubble_win.winfo_width() or BUBBLE_WIDTH
                h = self.bubble_win.winfo_height() or BUBBLE_HEIGHT
                cx, cy = self.bubble_position(w, h)
                self.bubble_win.geometry(f"{w}x{h}+{cx}+{cy}")
                self.bubble_win.lift()
                self.bubble_win.attributes("-topmost", True)
                self.lift()
                self.attributes("-topmost", True)
            except tk.TclError:
                self.bubble_win = None
            return

        self.bubble_interactive = True
        self.bubble_minimized = False
        if not hasattr(self, "_active_product"):
            self._active_product = "General"
        if not hasattr(self, "_current_session_msgs"):
            self._current_session_msgs = []

        # Load conversation history if no explicit text provided
        if text is None:
            text = self._get_last_chat_preview(n=4, max_len=120)
            if not text:
                text = "Escribe algo para empezar..."

        bub = tk.Toplevel(self)
        bub.overrideredirect(True)
        bub.attributes("-topmost", True)
        bub.configure(bg=TRANSPARENT_COLOR)
        bub.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        bub.bind("<FocusOut>", self._on_bubble_focus_out)

        width = BUBBLE_WIDTH
        height = BUBBLE_HEIGHT

        canvas = tk.Canvas(bub, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        # Dashboard layout inspired by the Claudy AI mockup.
        side_x0, side_x1 = 18, 278
        main_x0, main_x1 = 294, width - 18
        chat_theme = dict(THEME)
        chat_theme.update({
            "bg_bubble": "#030714",
            "bg_bubble_border": "#5b35d8",
            "bg_input": "#071026",
            "bg_input_border": "#20315f",
            "header_bg": "#071026",
            "header_chip": "#071026",
            "panel_bg": "#030714",
            "panel_soft": "#091333",
            "message_bot": "#101a42",
            "message_bot_border": "#324b9a",
            "button_bg": "#0b1538",
            "button_fg": "#dbe6ff",
            "button_hover": "#172862",
            "text_primary": "#f7f9ff",
            "text_secondary": "#9fb2ff",
            "text_label": "#9fb2ff",
            "input_fg": "#f7f9ff",
            "accent": "#7b3cff",
            "accent_glow": "#58c7ff",
            "accent_dim": "#17245a",
            "divider": "#273c85",
            "style": "glass",
        })
        self._dashboard_chat_theme = chat_theme

        def rounded_panel(x0, y0, x1, y1, radius=18, fill="#05091d", outline="#5b35d8", width_px=1):
            points = [
                x0 + radius, y0, x1 - radius, y0,
                x1, y0, x1, y0 + radius,
                x1, y1 - radius, x1, y1,
                x1 - radius, y1, x0 + radius, y1,
                x0, y1, x0, y1 - radius,
                x0, y0 + radius, x0, y0,
            ]
            return canvas.create_polygon(
                points, smooth=True, splinesteps=12,
                fill=fill, outline=outline, width=width_px,
                tags=("bubble_bg",)
            )

        try:
            bg_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            bg_draw = ImageDraw.Draw(bg_img)
            bg_draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=24,
                                      fill=(3, 7, 20, 245), outline=(91, 53, 216, 255), width=2)
            bg_draw.rounded_rectangle((8, 8, width - 9, height - 9), radius=18,
                                      outline=(88, 199, 255, 120), width=1)
            glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow)
            glow_draw.rounded_rectangle((2, 2, width - 3, height - 3), radius=24,
                                        outline=(192, 45, 255, 130), width=4)
            glow = glow.filter(ImageFilter.GaussianBlur(8))
            bg_img = Image.alpha_composite(glow, bg_img)
            dashboard_bg = ImageTk.PhotoImage(bg_img)
            self._dashboard_bg_ref = dashboard_bg
            canvas.create_image(0, 0, anchor="nw", image=dashboard_bg, tags=("bubble_bg",))
        except Exception:
            canvas.create_rectangle(0, 0, width, height, fill="#030714", outline="#5b35d8",
                                    width=2, tags=("bubble_bg",))
        rounded_panel(side_x0, 18, side_x1, height - 18, 22, "#05091d", "#5b35d8", 2)
        rounded_panel(main_x0, 18, main_x1, height - 18, 22, "#05091d", "#5b35d8", 2)
        rounded_panel(main_x0, 18, main_x1, 92, 20, "#071026", "#20315f", 1)
        rounded_panel(main_x0 + 8, 108, main_x1 - 8, 486, 20, "#030714", "#273c85", 1)
        rounded_panel(main_x0 + 12, 500, main_x1 - 12, 562, 22, "#071026", "#00c8ff", 2)

        for i in range(26):
            sx = main_x0 + 42 + (i * 73) % (main_x1 - main_x0 - 84)
            sy = 126 + (i * 47) % 330
            fill = "#7c6bff" if i % 3 else "#37d8ff"
            canvas.create_oval(sx, sy, sx + 2, sy + 2, fill=fill, outline="", tags=("bubble_bg",))

        # History button (left) – tiny toggle icon.
        # Brand label \u2014 small uppercase tag (left).
        # Draw Claudy header avatar (or fallback to text "AI")
        claudy_avatar_drawn = False
        try:
            from PIL import Image, ImageTk, ImageDraw
            claudy_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claudy_orbit_frame_0.png")
            if os.path.exists(claudy_path):
                img = Image.open(claudy_path).convert("RGBA")
                size = (44, 44)
                img = img.resize(size, Image.Resampling.LANCZOS)
                mask = Image.new("L", size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, size[0] - 1, size[1] - 1), fill=255)
                output = Image.new("RGBA", size, (0, 0, 0, 0))
                output.paste(img, (0, 0), mask=mask)
                self._claudy_header_photo = ImageTk.PhotoImage(output)
                canvas.create_image(48, 50, anchor="nw", image=self._claudy_header_photo, tags=("bubble_bg",))
                claudy_avatar_drawn = True
        except Exception as e:
            print(f"[claudy header avatar] error: {e}")

        if not claudy_avatar_drawn:
            canvas.create_oval(48, 50, 92, 94, outline="#8d4dff", width=3, fill="#0a1835", tags=("bubble_bg",))
            canvas.create_text(70, 72, text="AI", fill="#58c7ff", font=("Arial Black", 13), tags=("bubble_bg",))
        else:
            canvas.create_oval(48, 50, 92, 94, outline="#8d4dff", width=3, fill="", tags=("bubble_bg",))
        brand_id = canvas.create_text(
            96, 56, anchor="nw", text="CLAUDY",
            fill="#ffffff", font=("Arial Black", 15), tags=("bubble_bg",)
        )
        subtitle_id = canvas.create_text(
            96, 82, anchor="nw", text="Tu asistente IA",
            fill="#b8c6ff", font=("Bahnschrift", 8), tags=("bubble_bg",)
        )
        self._bubble_canvas = canvas
        rounded_panel(34, 128, 262, 182, 14, "#091333", "#24366e", 1)
        canvas.create_text(58, 144, anchor="nw", text="En linea", fill="#ffffff", font=("Bahnschrift SemiBold", 10), tags=("bubble_bg",))
        canvas.create_text(58, 166, anchor="nw", text="Memoria activa", fill="#9fb2ff", font=("Bahnschrift", 9), tags=("bubble_bg",))
        canvas.create_oval(44, 146, 52, 154, fill="#00ff99", outline="", tags=("bubble_bg",))

        # Real-time Google Drive Status indicator
        drive_status_color = "#00ff99" if getattr(self, "_drive_connected", True) else "#ff3838"
        drive_status_text = "Drive OK" if getattr(self, "_drive_connected", True) else "Drive OFF"
        drive_text_color = "#ffffff" if getattr(self, "_drive_connected", True) else "#ff8888"
        
        canvas.create_oval(154, 146, 162, 154, fill=drive_status_color, outline="", tags=("bubble_bg", "drive_status_dot"))
        canvas.create_text(168, 144, anchor="nw", text=drive_status_text, fill=drive_text_color, font=("Bahnschrift SemiBold", 10), tags=("bubble_bg", "drive_status_text"))
        nueva_bg = rounded_panel(34, 204, 262, 238, 16, "#803cff", "#58c7ff", 1)
        nueva_txt = canvas.create_text(148, 221, text="+ Nueva conversacion", fill="#ffffff", font=("Bahnschrift SemiBold", 10), tags=("bubble_bg",))
        def _nueva_conversacion(_e=None):
            # 1. Compress current session and save to Obsidian
            try:
                self._compress_and_save_to_obsidian()
            except Exception as ex:
                print(f"[nueva conv] compress error: {ex}")
            # 2. Clear current session messages
            self._current_session_msgs = []
            # 3. Clear chat view and show greeting
            chat = getattr(self, "_chat_view", None)
            if chat:
                chat.clear()
                chat.add_system("Hola Felipe, \u00bfen qu\u00e9 te ayudo?")
            try:
                status.configure(text="Nueva conversacion iniciada", fg="#58c7ff")
            except Exception:
                pass
        for _item in (nueva_bg, nueva_txt):
            canvas.tag_bind(_item, "<Button-1>", _nueva_conversacion)
            canvas.tag_bind(_item, "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
            canvas.tag_bind(_item, "<Leave>", lambda _e: canvas.configure(cursor=""))
        canvas.create_text(34, 270, anchor="nw", text="PRODUCTOS QCORE", fill="#58c7ff", font=("Bahnschrift SemiBold", 8), tags=("bubble_bg",))
        _qcore_products = [
            ("SmartStudent", "EDU", "#6c5ce7"),
            ("Roadix", "AUTO", "#00b894"),
            ("Luxium", "CORE", "#e17055"),
            ("UnitCore", "CLIN", "#0984e3"),
            ("Campaign Studio", "MKT", "#fdcb6e"),
            ("Mission Control", "OPS", "#a29bfe"),
        ]
        self._product_btns = []
        for idx, (title, tag, color) in enumerate(_qcore_products):
            y = 296 + idx * 36
            row_fill = "#211064" if idx == 0 else "#060c22"
            row_id = rounded_panel(30, y, 266, y + 30, 12, row_fill, "#182752", 1)
            dot_id = canvas.create_oval(38, y + 10, 48, y + 20, fill=color, outline="", tags=("bubble_bg",))
            txt_id = canvas.create_text(54, y + 7, anchor="nw", text=title, fill="#ffffff" if idx == 0 else "#c7d2ff",
                               font=("Bahnschrift SemiBold", 8), tags=("bubble_bg",))
            tag_id = canvas.create_text(254, y + 8, anchor="ne", text=tag, fill=color,
                               font=("Bahnschrift SemiBold", 8), tags=("bubble_bg",))
            # Click handler → switch context to this product with full knowledge
            def _switch_product(_e=None, name=title, c=color):
                self._active_product = name
                # Load rich product context
                try:
                    from qcore_products import build_context_prompt, PRODUCT_CONTEXTS
                    self._product_context = build_context_prompt(name)
                    pinfo = PRODUCT_CONTEXTS.get(name, {})
                    # Build a nice summary for the chat
                    desc = pinfo.get("description", "")
                    mods = pinfo.get("modules", [])
                    summary_lines = [f"🔄 Contexto: **{name}** ({pinfo.get('tag', '')})", f"_{desc}_"]
                    if mods:
                        summary_lines.append(f"\n📦 {len(mods)} módulos disponibles:")
                        for m in mods[:8]:
                            summary_lines.append(f"  • {m}")
                        if len(mods) > 8:
                            summary_lines.append(f"  ... y {len(mods) - 8} más")
                    if pinfo.get("port"):
                        summary_lines.append(f"\n💡 Di 'inicia {name.lower()}' para lanzar en puerto {pinfo['port']}")
                    summary = "\n".join(summary_lines)
                except Exception:
                    self._product_context = f"Producto activo: {name}"
                    summary = f"Contexto cambiado a: {name}"
                chat = getattr(self, "_chat_view", None)
                if chat:
                    chat.add_system(summary)
                try:
                    status.configure(text=f"Producto: {name}", fg=c)
                except Exception:
                    pass
            for item in (row_id, dot_id, txt_id, tag_id):
                canvas.tag_bind(item, "<Button-1>", _switch_product)
                canvas.tag_bind(item, "<Enter>", lambda _e, c=color: canvas.configure(cursor="hand2"))
                canvas.tag_bind(item, "<Leave>", lambda _e: canvas.configure(cursor=""))
            self._product_btns.append((title, tag, color))
        rounded_panel(30, height - 90, 266, height - 30, 16, "#071026", "#24366e", 1)
        # Draw avatar image (or fallback to text "JC")
        avatar_drawn = False
        try:
            from PIL import Image, ImageTk, ImageDraw
            avatar_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatar_developer.png")
            if os.path.exists(avatar_path):
                img = Image.open(avatar_path).convert("RGBA")
                size = (34, 34)
                img = img.resize(size, Image.Resampling.LANCZOS)
                mask = Image.new("L", size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, size[0] - 1, size[1] - 1), fill=255)
                output = Image.new("RGBA", size, (0, 0, 0, 0))
                output.paste(img, (0, 0), mask=mask)
                self._avatar_photo = ImageTk.PhotoImage(output)
                canvas.create_image(42, height - 80, anchor="nw", image=self._avatar_photo, tags=("bubble_bg",))
                avatar_drawn = True
        except Exception as e:
            print(f"[avatar] error: {e}")

        if not avatar_drawn:
            canvas.create_oval(42, height - 80, 76, height - 46, outline="#58c7ff", fill="#12194a", width=2, tags=("bubble_bg",))
            canvas.create_text(59, height - 63, text="JC", fill="#58c7ff", font=("Bahnschrift SemiBold", 10), tags=("bubble_bg",))
        else:
            canvas.create_oval(42, height - 80, 76, height - 46, outline="#58c7ff", fill="", width=2, tags=("bubble_bg",))
        canvas.create_text(88, height - 76, anchor="nw", text="Felipe Castro", fill="#ffffff",
                           font=("Bahnschrift SemiBold", 10), tags=("bubble_bg",))
        canvas.create_text(88, height - 56, anchor="nw", text="jorge.castro@qcorespa.com", fill="#9fb2ff",
                           font=("Bahnschrift", 8), tags=("bubble_bg",))

        canvas.create_text(main_x0 + 56, 42, anchor="nw", text="Asistente IA",
                           fill="#ffffff", font=("Bahnschrift SemiBold", 16), tags=("bubble_bg",))
        canvas.create_text(main_x0 + 56, 68, anchor="nw", text="Modelo Neural v4.0  •  Precision Avanzada",
                           fill="#aebdff", font=("Bahnschrift", 9), tags=("bubble_bg",))
        canvas.create_text(main_x0 + 24, 55, text="✦", fill="#58c7ff", font=("Segoe UI Symbol", 24), tags=("bubble_bg",))
        status_dot_id = canvas.create_text(
            side_x0 + 248, 138, anchor="nw", text="\u25cf",
            fill="#5ee6a1", font=("Segoe UI", 9, "bold"), tags=("bubble_bg",)
        )
        # History button
        history_btn = tk.Label(
            bub, text="\u2630", bg=chat_theme["button_bg"], fg=chat_theme["accent_glow"],
            font=("Segoe UI Symbol", 13), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["accent"], highlightthickness=2,
        )
        history_id = canvas.create_window(main_x1 - 174, 36, anchor="nw", width=30, height=28, window=history_btn)
        history_btn.bind("<Button-1>", lambda _e: self.show_history_window())
        history_btn.bind("<Enter>", lambda _e: (
            history_btn.config(fg=chat_theme["accent_glow"], bg=chat_theme["button_hover"], highlightbackground=chat_theme["accent"]),
            status.configure(text="Ver historial de chat (Ventana independiente)", fg=chat_theme["accent_glow"])
        ))
        history_btn.bind("<Leave>", lambda _e: (
            history_btn.config(fg=chat_theme["button_fg"], bg=chat_theme["button_bg"], highlightbackground=chat_theme["bg_input_border"]),
            status.configure(text="Enter envia  |  Shift+Enter salto  |  Esc cierra  |  Espacio 2s habla", fg=chat_theme["text_label"])
        ))

        # Folder analyzer button: pick a folder, analyze deep, save to Obsidian.
        folder_btn = tk.Label(
            bub, text="\U0001F4C1", bg=chat_theme["button_bg"], fg=chat_theme["accent_glow"],
            font=("Segoe UI Emoji", 12), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["accent"], highlightthickness=2,
        )
        folder_id = canvas.create_window(main_x1 - 138, 36, anchor="nw", width=30, height=28, window=folder_btn)

        def _on_analyze_folder(_e=None):
            from tkinter import filedialog
            path = filedialog.askdirectory(title="Carpeta para analizar (recursivo)")
            if not path:
                return
            self._set_response_text(f"Analizando profundamente:\n{path}\n\nEsto puede tomar 30-90s...")
            try:
                status.configure(text="Iniciando analisis...", fg=THEME["accent"])
            except Exception:
                pass
            def _run():
                try:
                    result = self._analyze_folder_deep(path, status)
                except Exception as e:
                    result = (f"Error: {e}", "")
                def _show_result():
                    analysis_text, saved_path = result if isinstance(result, tuple) else (result, "")
                    chat = getattr(self, "_chat_view", None)
                    if chat is not None:
                        try:
                            chat.hide_typing()
                        except Exception:
                            pass
                        chat.add_bot(analysis_text)
                        if saved_path and os.path.exists(saved_path):
                            self._remember_file_artifact(saved_path)
                            chat.add_file_card(
                                filename=os.path.basename(saved_path),
                                on_open_file=lambda p=saved_path: self._open_path_file(p),
                                on_open_folder=lambda p=saved_path: self._open_path_location(p),
                                message="Abrir reporte completo",
                            )
                    else:
                        self._set_response_text(analysis_text)
                    status.configure(text="Enter envia  ·  Esc cierra", fg=chat_theme["text_secondary"])
                self.after(0, _show_result)
            threading.Thread(target=_run, daemon=True).start()

        folder_btn.bind("<Button-1>", _on_analyze_folder)
        folder_btn.bind("<Enter>", lambda _e: (
            folder_btn.config(fg=chat_theme["accent_glow"], bg=chat_theme["button_hover"], highlightbackground=chat_theme["accent"]),
            status.configure(text="Analizar carpeta profundamente con IA", fg=chat_theme["accent_glow"])
        ))
        folder_btn.bind("<Leave>", lambda _e: (
            folder_btn.config(fg=chat_theme["button_fg"], bg=chat_theme["button_bg"], highlightbackground=chat_theme["bg_input_border"]),
            status.configure(text="Enter envia  |  Shift+Enter salto  |  Esc cierra  |  Espacio 2s habla", fg=chat_theme["text_label"])
        ))

        # Open last file/folder location button.
        open_location_btn = tk.Label(
            bub, text="\U0001F4C2", bg=chat_theme["button_bg"], fg=chat_theme["accent_glow"],
            font=("Segoe UI Emoji", 12), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["accent"], highlightthickness=2,
        )
        open_location_id = canvas.create_window(main_x1 - 102, 36, anchor="nw", width=30, height=28, window=open_location_btn)
        self._open_location_btn = open_location_btn
        open_location_btn.bind("<Button-1>", lambda _e: self._open_last_file_location())
        open_location_btn.bind("<Enter>", lambda _e: self._set_open_location_hover(True))
        open_location_btn.bind("<Leave>", lambda _e: self._set_open_location_hover(False))
        self._set_open_location_button_state()

        # Clear visible area button (history stays saved on disk).
        clear_btn = tk.Label(
            bub, text="\U0001F9F9", bg=chat_theme["button_bg"], fg=chat_theme["accent_glow"],
            font=("Segoe UI Emoji", 12), cursor="hand2",
            padx=6, pady=4, relief="flat", bd=0,
            highlightbackground=chat_theme["accent"], highlightthickness=2,
        )
        clear_id = canvas.create_window(main_x1 - 66, 36, anchor="nw", width=30, height=28, window=clear_btn)
        clear_btn.bind("<Button-1>", lambda _e: (self._chat_view.clear() if getattr(self, "_chat_view", None) else self._set_response_text("")))
        clear_btn.bind("<Enter>", lambda _e: (
            clear_btn.config(fg=chat_theme["accent_glow"], bg=chat_theme["button_hover"], highlightbackground=chat_theme["accent"]),
            status.configure(text="Limpiar conversación en pantalla", fg=chat_theme["accent_glow"])
        ))
        clear_btn.bind("<Leave>", lambda _e: (
            clear_btn.config(fg=chat_theme["button_fg"], bg=chat_theme["button_bg"], highlightbackground=chat_theme["bg_input_border"]),
            status.configure(text="Enter envia  |  Shift+Enter salto  |  Esc cierra  |  Espacio 2s habla", fg=chat_theme["text_label"])
        ))

        # Minimize button.
        minimize_btn = tk.Label(
            bub, text="\u2212", bg=chat_theme["button_bg"], fg=chat_theme["accent_glow"],
            font=("Bahnschrift SemiBold", 14), cursor="hand2",
            padx=6, pady=3, relief="flat", bd=0,
            highlightbackground=chat_theme["accent"], highlightthickness=2,
        )
        minimize_id = canvas.create_window(main_x1 - 28, 36, anchor="nw", width=22, height=26, window=minimize_btn)
        minimize_btn.bind("<Enter>", lambda _e: (
            minimize_btn.config(fg=chat_theme["accent_glow"], bg=chat_theme["button_hover"]),
            status.configure(text="Minimizar ventana de chat", fg=chat_theme["accent_glow"])
        ))
        minimize_btn.bind("<Leave>", lambda _e: (
            minimize_btn.config(fg=chat_theme["text_primary"], bg=chat_theme["header_bg"]),
            status.configure(text="Enter envia  |  Shift+Enter salto  |  Esc cierra  |  Espacio 2s habla", fg=chat_theme["text_label"])
        ))

        # Modern canvas-based chat view (bubbles, avatars, timestamps, animations).
        try:
            from chat_view import ChatView
        except Exception:
            ChatView = None
        if ChatView is not None:
            chat_shell = tk.Frame(
                bub, bg=chat_theme["panel_bg"], bd=0, highlightthickness=0,
                highlightbackground=chat_theme["divider"], highlightcolor=chat_theme["divider"]
            )
            chat = ChatView(chat_shell, theme=chat_theme, width=main_x1 - main_x0 - 48, height=342)
            chat.pack(fill="both", expand=True, padx=12, pady=12)
            self._chat_view = chat
            self._response_text_widget = None  # no legacy text widget
            # Fresh start: only show greeting. Memory stays in SQLite/Obsidian.
            # If re-opened mid-session, restore current session messages.
            if getattr(self, "_chat_history_buffer", None) is not None:
                chat.load_history(self._chat_history_buffer)
                self._chat_history_buffer = None
            elif getattr(self, "_current_session_msgs", None):
                chat.load_history(self._current_session_msgs)
            else:
                chat.add_system("Hola Felipe, \u00bfen qu\u00e9 te ayudo?")
            header_id = canvas.create_window(main_x0 + 16, 122, anchor="nw",
                                             width=main_x1 - main_x0 - 32, height=348,
                                             window=chat_shell)
        else:
            # Fallback: legacy text widget if chat_view fails to import.
            response_frame = tk.Frame(
                bub, bg=chat_theme["panel_bg"], bd=0, highlightthickness=0,
                highlightbackground=chat_theme["divider"], highlightcolor=chat_theme["divider"]
            )
            response_text = tk.Text(
                response_frame, bg=chat_theme["panel_bg"], fg=chat_theme["text_primary"],
                font=FONT_BODY, wrap="word", state="disabled",
                highlightthickness=0, bd=0, padx=14, pady=10, relief="flat",
            )
            response_text.pack(side="left", fill="both", expand=True)
            self._response_text_widget = response_text
            self._chat_view = None
            self._set_response_text(text)
            header_id = canvas.create_window(main_x0 + 16, 122, anchor="nw",
                                             width=main_x1 - main_x0 - 32, height=348,
                                             window=response_frame)

        # Dummy references for minimize/expand (pagination removed).
        prev_id = None
        next_id = None
        page_id = None
        self._pagination_ids = None
        self._pagination_btns = None
        self._bubble_canvas = canvas

        # Input area — simple placeholder via direct entry manipulation.
        _PLACEHOLDER = "Escribe tu mensaje..."

        attach_bg_id = rounded_panel(main_x0 + 28, 512, main_x0 + 70, 556, 14, "#0b1538", "#22386f", 1)
        attach_icon_id = canvas.create_text(main_x0 + 49, 534, text="\U0001F4CE", fill="#ffffff",
                                            font=("Segoe UI Emoji", 14), tags=("bubble_bg",))
        mic_bg_id = rounded_panel(main_x1 - 158, 512, main_x1 - 116, 556, 14, "#0b1538", "#22386f", 1)
        mic_icon_id = canvas.create_text(main_x1 - 137, 534, text="\U0001F399", fill="#ffffff",
                                         font=("Segoe UI Emoji", 14), tags=("bubble_bg",))

        entry = tk.Text(
            bub,
            bg="#0a1530", fg="#ffffff",
            insertbackground="#58c7ff", insertwidth=3,
            relief="flat", font=("Bahnschrift", 12),
            highlightthickness=1, highlightbackground="#3d5aab",
            highlightcolor="#58c7ff", bd=0,
            wrap="word", padx=10, pady=10,
        )

        # Override standard entry methods to make tk.Text act exactly like tk.Entry
        def text_get(index1=None, index2=None):
            if index1 is None:
                return entry.get("1.0", "end-1c")
            return tk.Text.get(entry, index1, index2)
        
        def text_delete(first, last=None):
            if first == 0 and last == tk.END:
                entry.delete("1.0", "end")
            else:
                tk.Text.delete(entry, first, last)
                
        def text_insert(index, chars, *tags):
            if index == 0:
                entry.insert("1.0", chars)
            else:
                tk.Text.insert(entry, index, chars, *tags)

        entry.get = text_get
        entry.delete = text_delete
        entry.insert = text_insert

        entry.insert(0, _PLACEHOLDER)
        entry.config(fg="#5a78cc")
        entry_id = canvas.create_window(main_x0 + 86, 512, anchor="nw",
                                        width=main_x1 - main_x0 - 214, height=44,
                                        window=entry)
        _btn_bg = "#8a2be2"
        _btn_fg = "#ffffff"
        _btn_hover = "#58c7ff"
        send_btn = tk.Label(
            bub, text="ENVIAR", bg=_btn_bg, fg=_btn_fg,
            font=("Arial Black", 10), cursor="hand2",
            padx=10, pady=8, relief="flat", bd=0,
            highlightbackground="#58c7ff", highlightthickness=2,
        )
        send_id = canvas.create_window(main_x1 - 104, 512, anchor="nw", width=82, height=44, window=send_btn)
        _pulse_on = [False]
        def _pulse_send():
            if not _pulse_on[0]:
                return
            try:
                cur = send_btn.cget("highlightbackground")
                nxt = "#c02dff" if cur == "#58c7ff" else "#58c7ff"
                send_btn.config(highlightbackground=nxt)
                bub.after(600, _pulse_send)
            except Exception:
                pass
        def _start_pulse(_e=None):
            send_btn.config(bg="#5b3cf5", highlightbackground="#58c7ff")
            _pulse_on[0] = True
            _pulse_send()
        def _stop_pulse(_e=None):
            _pulse_on[0] = False
            send_btn.config(bg=_btn_bg, highlightbackground="#8a2be2")
        send_btn.bind("<Enter>", lambda _e: (_start_pulse(), send_btn.config(bg=_btn_hover, fg="#06111f")))
        send_btn.bind("<Leave>", lambda _e: (_stop_pulse(), send_btn.config(bg=_btn_bg, fg=_btn_fg)))

        def _has_placeholder():
            return entry.get() == _PLACEHOLDER

        def _clear_placeholder(*_):
            if _has_placeholder():
                entry.delete(0, tk.END)
                entry.config(fg="#ffffff")

        def _restore_placeholder(*_):
            if not entry.get().strip():
                entry.delete(0, tk.END)
                entry.insert(0, _PLACEHOLDER)
                entry.config(fg="#5a78cc")

        entry.bind("<FocusIn>", _clear_placeholder, add=True)
        entry.bind("<Button-1>", lambda _e: entry.after_idle(_clear_placeholder))
        entry.bind("<Key>", _clear_placeholder, add=True)
        entry.bind("<FocusOut>", lambda _e: entry.after_idle(_restore_placeholder))

        status = tk.Label(
            bub, text="\u21b5 Enter envia   |   \u2191 Shift+Enter salto   |   Esc cierra   |   \U0001f3a4 Espacio 2s habla",
            bg="#030714", fg="#9fb2ff",
            font=("Bahnschrift", 8), padx=8, pady=2, anchor="w",
        )
        self._status_label = status
        status_id = canvas.create_window(main_x0 + 116, 576, anchor="nw",
                                         width=main_x1 - main_x0 - 232, window=status)

        for _attach_item in (attach_bg_id, attach_icon_id):
            canvas.tag_bind(
                _attach_item,
                "<Button-1>",
                lambda _e: self._pick_and_analyze_attachment(status, entry),
            )
            canvas.tag_bind(
                _attach_item,
                "<Enter>",
                lambda _e: (
                    canvas.configure(cursor="hand2"),
                    status.configure(
                        text="Adjuntar PDF, Excel, imagen, Word o PowerPoint",
                        fg=chat_theme["accent_glow"],
                    ),
                ),
            )
            canvas.tag_bind(
                _attach_item,
                "<Leave>",
                lambda _e: (
                    canvas.configure(cursor=""),
                    status.configure(
                        text="Enter envia  |  Shift+Enter salto  |  Esc cierra  |  Espacio 2s habla",
                        fg=chat_theme["text_label"],
                    ),
                ),
            )

        # Position for the minimized (sleep) state — centered in the mini window.
        mini_cx = BUBBLE_MINI_SIZE // 2
        mini_cy = BUBBLE_MINI_SIZE // 2

        # Sleep visual: animated vector Zzz text elements (100% transparent, NO pink backgrounds!)
        zzz_1 = canvas.create_text(mini_cx - 10, mini_cy + 15, text="z", fill=THEME["accent"], font=("Segoe UI", 12, "bold"))
        zzz_2 = canvas.create_text(mini_cx + 2, mini_cy + 2, text="Z", fill=THEME["accent"], font=("Segoe UI", 16, "bold"))
        zzz_3 = canvas.create_text(mini_cx - 4, mini_cy - 12, text="Z", fill=THEME["accent"], font=("Segoe UI", 20, "bold"))

        _idle_items = (zzz_1, zzz_2, zzz_3)
        for item in _idle_items:
            canvas.itemconfigure(item, state="hidden")

        self._canvas = canvas
        self._idle_items = _idle_items
        self._zzz_texts = [zzz_1, zzz_2, zzz_3]
        self._zzz_tick = 0
        self._zzz_anim_running = False

        def minimize():
            self.bubble_minimized = True
            self._reset_idle_timer()
            # Hide all UI chrome AND the bubble background
            for item in (header_id, entry_id, send_id, status_id, minimize_id, history_id, folder_id, open_location_id, clear_id, brand_id, subtitle_id, status_dot_id):
                canvas.itemconfigure(item, state="hidden")
            canvas.itemconfigure("bubble_bg", state="hidden")
            
            is_working = getattr(self, "_milestone_active", False)
            if is_working:
                # Keep sleep elements hidden while active task runs
                for item in _idle_items:
                    canvas.itemconfigure(item, state="hidden")
                self._stop_zzz_animation()
                
                # Instantly display the active status progress message
                status_text = status.cget("text")
                if "Enter" in status_text or not status_text:
                    status_text = "Redactando informe..."
                self.show_pet_speech_bubble(status_text, duration=None)
            else:
                for item in _idle_items:
                    canvas.itemconfigure(item, state="normal")
                self._start_zzz_animation()
                
            sz = BUBBLE_MINI_SIZE
            canvas.configure(width=sz, height=sz)
            cx, cy = self.minimized_position(sz)
            bub.geometry(f"{sz}x{sz}+{cx}+{cy}")

        def expand():
            self.bubble_minimized = False
            self._cancel_idle_timer()
            self._stop_zzz_animation()
            if hasattr(self, "_pet_speech_win") and self._pet_speech_win:
                try:
                    self._pet_speech_win.destroy()
                except Exception:
                    pass
                self._pet_speech_win = None
            for item in (header_id, entry_id, send_id, status_id, minimize_id, history_id, folder_id, open_location_id, clear_id, brand_id, subtitle_id, status_dot_id):
                canvas.itemconfigure(item, state="normal")
            canvas.itemconfigure("bubble_bg", state="normal")
            for item in _idle_items:
                canvas.itemconfigure(item, state="hidden")
            self._sync_pagination_visibility(canvas)
            canvas.configure(width=width, height=height)
            cx, cy = self.bubble_position(width, height)
            bub.geometry(f"{width}x{height}+{cx}+{cy}")
            try:
                self.lift()
                self.attributes("-topmost", True)
            except Exception:
                pass
            entry.focus_set()

        self._expand_bubble = expand
        self._minimize_bubble = minimize

        minimize_btn.bind("<Button-1>", lambda _e: minimize())
        for item in _idle_items:
            canvas.tag_bind(item, "<Button-1>", lambda _e: expand())

        # No mini_status widget — circle bubble replaces it.
        self._bubble_mini_status = None

        def submit(_event=None):
            prompt = entry.get().strip()
            if not prompt or prompt == _PLACEHOLDER:
                return
            entry.delete(0, tk.END)

            # If Guided Report Flow is active, process the current answer
            if getattr(self, "_guided_report_active", False):
                self._handle_guided_report_step(prompt, status, entry)
                return

            # If Guided Email Flow is active, process the current answer
            if getattr(self, "_guided_email_active", False):
                self._handle_guided_email_step(prompt, status, entry)
                return

            plow = prompt.lower().strip()

            # ── Mission Control: crear borrador de correo en el Inbox ─────
            # Va ANTES que el flujo de informe (y manda incluso con el switch
            # Deep Research activo): un "borrador de correo para X" es inequívoco
            # y no debe terminar como informe. Si toma el pedido, limpiamos la
            # bandera de Deep Research para que no contamine el siguiente paso.
            if self._try_seed_mc_draft(prompt, plow, status, entry):
                self._deep_research_pending = False
                return

            # Check if this is a new request to generate a report
            is_report_req = False
            topic = ""

            # Deep Research switch activo: forzamos el flujo guiado de informe
            # sin depender de las palabras gatillo. El tema es el prompt limpio
            # quitando muletillas tipo "crea un docx/informe sobre ...".
            if getattr(self, "_deep_research_pending", False):
                self._deep_research_pending = False
                is_report_req = True
                topic = re.sub(
                    r"^\s*(?:crea(?:me)?|cre[aá]|hazme|haz|genera(?:me)?|necesito|quiero|hac[eé]r?)\s+"
                    r"(?:un|una|el|la)?\s*"
                    r"(?:informe|reporte|documento|docx|doc|word|pdf|archivo|texto)?\s*"
                    r"(?:extenso|completo|detallado|profesional)?\s*"
                    r"(?:sobre|de|acerca de|del|sobre el|sobre la)?\s*",
                    "", prompt, flags=re.IGNORECASE,
                ).strip() or prompt.strip()

            if (not is_report_req) and (plow.startswith("/informe") or plow.startswith("/reporte")):
                is_report_req = True
                topic = prompt.split(None, 1)[1].strip() if len(prompt.split(None, 1)) > 1 else ""
            elif not is_report_req:
                triggers = [
                    "informe sobre", "informe de", "reporte sobre", "reporte de",
                    "crea un informe", "crear un informe", "hazme un informe", "quiero un informe",
                    "generame un informe", "necesito un informe", "hacer un informe", "haz un informe",
                    "hiciera un informe", "hiciese un informe", "hidice un informe", "hacer informe",
                    "crea un reporte", "crear un reporte", "hazme un reporte", "quiero un reporte",
                    "generame un reporte", "necesito un reporte", "hacer un reporte", "haz un reporte"
                ]
                for trig in triggers:
                    if trig in plow:
                        is_report_req = True
                        idx = plow.find(trig)
                        topic = prompt[idx + len(trig):].strip()
                        # Clean prefix "sobre" or "de"
                        if topic.lower().startswith("sobre "):
                            topic = topic[6:].strip()
                        elif topic.lower().startswith("de "):
                            topic = topic[3:].strip()
                        break
            
            if is_report_req:
                self._start_guided_report_flow(topic, status, entry)
                return

            # (El borrador de correo MC ya se evaluó arriba, antes del informe.)

            # ── Mi Portafolio: editar archivos locales del proyecto ───────
            if self._try_edit_portfolio(prompt, plow, status, entry):
                return

            # ── QCORE Product Launcher ────────────────────────────────────
            _QCORE_PRODUCTS = {
                "mission control": {
                    "path": r"C:\Users\Felipe\Documents\QCORE-LOCAL\MISSION-CONTROL",
                    "cmd": "npm run dev",
                    "port": 5200,
                    "name": "Mission Control",
                },
                "mision control": {  # Spanish variant (single 's')
                    "path": r"C:\Users\Felipe\Documents\QCORE-LOCAL\MISSION-CONTROL",
                    "cmd": "npm run dev",
                    "port": 5200,
                    "name": "Mission Control",
                },
                "smartstudent": {
                    "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\SMARTSTUDENT\APP",
                    "cmd": "npm run dev",
                    "port": 9002,
                    "name": "SmartStudent",
                },
                "smart student": {
                    "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\SMARTSTUDENT\APP",
                    "cmd": "npm run dev",
                    "port": 9002,
                    "name": "SmartStudent",
                },
                "roadix": {
                    "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\ROADIX\frontend",
                    "cmd": "npm run dev",
                    "port": 5173,
                    "name": "Roadix",
                },
                "campaign studio": {
                    "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\CAMPAIGN-STUDIO",
                    "cmd": "npm run dev",
                    "port": 5174,
                    "name": "Campaign Studio",
                },
                "unitcore": {
                    "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\UNITCORE",
                    "cmd": "npm run dev",
                    "port": 5175,
                    "name": "UnitCore",
                },
                "luxium": {
                    "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\LUXIUM\MONOREPO",
                    "cmd": "npm run dev",
                    "port": 5176,
                    "name": "Luxium",
                },
                "mi portafolio": {
                    "path": r"C:\Users\Felipe\Documents\CV_JorgeCastro_v3.5",
                    "cmd": "python -m http.server",
                    "port": 8080,
                    "name": "Mi Portafolio",
                },
                "portafolio": {
                    "path": r"C:\Users\Felipe\Documents\CV_JorgeCastro_v3.5",
                    "cmd": "python -m http.server",
                    "port": 8080,
                    "name": "Mi Portafolio",
                },
                "portfolio": {
                    "path": r"C:\Users\Felipe\Documents\CV_JorgeCastro_v3.5",
                    "cmd": "python -m http.server",
                    "port": 8080,
                    "name": "Mi Portafolio",
                },
            }
            # Clean politeness and conversational prefixes for robust QCORE matching
            cleaned_plow = plow
            try:
                import claudy_powers as cp
                cleaned_plow = cp.clean_politeness_prefixes(plow).strip()
            except Exception:
                pass

            _launch_triggers = [
                "inicia ", "iniciar ", "inicializa ", "inicializar ",
                "inciializa ", "inciializar ", "inicialisa ", "inicialisar ",
                "lanza ", "lanzar ", "abre ", "abrir ",
                "arranca ", "arrancar ", "levanta ", "levantar ",
                "ejecuta ", "ejecutar ", "corre ", "correr ",
                "start ", "launch ", "run ",
            ]
            _product_match = None
            for trig in _launch_triggers:
                if cleaned_plow.startswith(trig):
                    product_query = cleaned_plow[len(trig):].strip()
                    # Strip common Spanish prepositions: "inicializa a mission control" → "mission control"
                    import re as _re
                    product_query = _re.sub(r"^(?:a|el|la|al|de|del|los|las|panel\s+de|panel\s+del)\s+", "", product_query).strip()
                    product_query = product_query.replace("-", " ").replace("_", " ")
                    # Strip trailing politeness words like "por favor", "porfa", "plis"
                    product_query = _re.sub(r"\s+(?:por\s+favor|porfa|plis|please)$", "", product_query).strip()
                    # Skip-analysis hint anywhere in the prompt (rapido, sin analisis, no analices, skip)
                    _skip_analysis = any(s in plow for s in (
                        "rapido", "rápido", "sin analisis", "sin análisis",
                        "no analices", "no analizar", "no análisis",
                        "skip analysis", "skip-analysis",
                    ))
                    # Also strip the hint from the product query so "inicia mc rapido" matches "mc"
                    product_query = _re.sub(r"\s+(?:rapido|rápido|sin\s+an[aá]lisis|no\s+anali\w+|skip[- ]analysis)$", "", product_query).strip()
                    for key, info in _QCORE_PRODUCTS.items():
                        if key in product_query or product_query in key:
                            _product_match = info
                            break
                    if _product_match:
                        break

            # Fuzzy fallback for typos like "inciializa mission control".
            # Only activates when a known QCORE product is explicitly present.
            if not _product_match:
                import difflib as _difflib
                import re as _re
                normalized_plow = cleaned_plow.replace("-", " ").replace("_", " ")
                first_word = normalized_plow.split(None, 1)[0] if normalized_plow else ""
                launch_words = (
                    "inicia", "iniciar", "inicializa", "inicializar",
                    "lanza", "lanzar", "abre", "abrir", "arranca", "arrancar",
                    "levanta", "levantar", "ejecuta", "ejecutar", "corre", "correr",
                    "start", "launch", "run",
                )
                looks_like_launch = any(
                    _difflib.SequenceMatcher(None, first_word, word).ratio() >= 0.78
                    for word in launch_words
                )
                if looks_like_launch:
                    product_query = normalized_plow.split(None, 1)[1].strip() if " " in normalized_plow else ""
                    product_query = _re.sub(r"^(?:a|el|la|al|de|del|los|las|panel\s+de|panel\s+del)\s+", "", product_query).strip()
                    _skip_analysis = any(s in plow for s in (
                        "rapido", "rápido", "sin analisis", "sin análisis",
                        "no analices", "no analizar", "no análisis",
                        "skip analysis", "skip-analysis",
                    ))
                    product_query = _re.sub(r"\s+(?:rapido|rápido|sin\s+an[aá]lisis|no\s+anali\w+|skip[- ]analysis)$", "", product_query).strip()
                    for key, info in _QCORE_PRODUCTS.items():
                        if key in product_query or product_query in key:
                            _product_match = info
                            break

            if _product_match:
                pinfo = _product_match
                chat = getattr(self, "_chat_view", None)
                if chat:
                    chat.add_user(prompt)
                status.configure(text=f"Preparando {pinfo['name']}...", fg="#58c7ff")
                self._active_product = pinfo["name"]
                self._portfolio_mode = (pinfo["name"] == "Mi Portafolio")

                def _launch_product_with_analysis(info=pinfo, skip_analysis=_skip_analysis):
                    import webbrowser
                    import hashlib
                    import time as _time
                    product_name = info["name"]
                    product_path = info["path"]

                    # ====== STEP 1: Lanzar dev server PRIMERO (no esperar al análisis) ======
                    import socket
                    def _find_free_port(start_port):
                        port = start_port
                        while port < 65535:
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                try:
                                    s.bind(("127.0.0.1", port))
                                    return port
                                except socket.error:
                                    port += 1
                        return start_port

                    original_port = info["port"]
                    free_port = _find_free_port(original_port)
                    info["port"] = free_port

                    cmd = info["cmd"]
                    if "npm run dev" in cmd:
                        # Detectar el runner real desde el script "dev" del package.json.
                        # La presencia de next.config.* NO implica Next: Mission Control usa Vite
                        # con next.config sobrante, y Vite aborta con `-p` (Unknown option).
                        dev_script = ""
                        try:
                            import json as _json
                            with open(os.path.join(product_path, "package.json"), "r", encoding="utf-8", errors="replace") as _pf:
                                dev_script = ((_json.load(_pf).get("scripts") or {}).get("dev") or "")
                        except Exception:
                            pass
                        uses_next = "next" in dev_script.replace("&", " ").split()
                        # `-p` solo lo entiende Next; `--port` lo entienden Next y Vite.
                        port_flag = "-p" if uses_next else "--port"
                        cmd = f"npm run dev -- {port_flag} {free_port}"
                    elif "http.server" in cmd:
                        # Sitio estático (ej. Mi Portafolio): servir la carpeta con el puerto libre.
                        cmd = f"python -m http.server {free_port}"

                    def _notify_launching():
                        ch = getattr(self, "_chat_view", None)
                        if ch:
                            ch.add_system(f"🚀 Iniciando **{product_name}** en puerto {free_port}...")
                        try:
                            status.configure(text=f"Iniciando {product_name}...", fg="#58c7ff")
                        except Exception:
                            pass
                    self.after(0, _notify_launching)

                    launch_ok = False
                    try:
                        proc = subprocess.Popen(
                            cmd,
                            cwd=info["path"],
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        self._launched_processes = getattr(self, "_launched_processes", {})
                        self._launched_processes[info["name"]] = proc
                        url = f"http://localhost:{info['port']}"

                        # Esperar a que el dev server realmente acepte conexiones antes de abrir el navegador.
                        # npm run dev (Next.js, y más sobre Drive en G:\) puede tardar bastante en hacer bind.
                        def _port_ready(port, host="127.0.0.1"):
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cs:
                                cs.settimeout(1)
                                return cs.connect_ex((host, port)) == 0

                        deadline = _time.time() + 90  # hasta 90s para el cold start
                        server_up = False
                        while _time.time() < deadline:
                            if proc.poll() is not None:
                                break  # el proceso murió; no tiene sentido seguir esperando
                            if _port_ready(info["port"]):
                                server_up = True
                                break
                            self.after(0, lambda: status.configure(
                                text=f"Esperando a {info['name']} en {url}...", fg="#58c7ff"))
                            _time.sleep(1)

                        if not server_up:
                            def _fail():
                                ch = getattr(self, "_chat_view", None)
                                reason = "el proceso terminó" if proc.poll() is not None else "no respondió a tiempo"
                                if ch:
                                    ch.add_system(
                                        f"❌ **{info['name']}** no llegó a iniciarse ({reason}). "
                                        f"Revisa que `npm install` esté hecho en {info['path']}.")
                                try:
                                    status.configure(text=f"{info['name']} no inició", fg="#ff5555")
                                except Exception:
                                    pass
                            self.after(0, _fail)
                            return

                        webbrowser.open(url)
                        launch_ok = True
                        def _done():
                            ch = getattr(self, "_chat_view", None)
                            if ch:
                                ch.add_system(f"✅ **{info['name']}** corriendo en {url}")
                            try:
                                status.configure(text=f"{info['name']} activo — {url}", fg="#00ff99")
                            except Exception:
                                pass
                        self.after(0, _done)
                    except Exception as e:
                        def _err(ex=e):
                            ch = getattr(self, "_chat_view", None)
                            if ch:
                                ch.add_system(f"❌ Error al iniciar {info['name']}: {ex}")
                            try:
                                status.configure(text=f"Error: {ex}", fg="#ff5555")
                            except Exception:
                                pass
                        self.after(0, _err)

                    if not launch_ok:
                        return  # No tiene sentido analizar si no levantó

                    # ====== STEP 2: Análisis después, en background, opcional ======
                    if skip_analysis:
                        return

                    self._product_analyses = getattr(self, "_product_analyses", {})
                    if product_name in self._product_analyses:
                        return  # ya hay análisis en memoria para esta sesión

                    # Caché en disco: ~/.claudy/analyses/<hash>.md
                    cache_dir = os.path.join(os.path.expanduser("~"), ".claudy", "analyses")
                    try:
                        os.makedirs(cache_dir, exist_ok=True)
                    except Exception:
                        pass
                    cache_key = hashlib.md5(product_path.encode("utf-8", errors="replace")).hexdigest()[:16]
                    cache_file = os.path.join(cache_dir, f"{cache_key}.md")

                    def _src_changed_since(p, ts):
                        # Cualquier archivo (fuera de node_modules/.git) modificado tras `ts` invalida el caché.
                        try:
                            for root, dirs, files in os.walk(p):
                                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist", ".next", "build")]
                                for f in files:
                                    try:
                                        if os.path.getmtime(os.path.join(root, f)) > ts:
                                            return True
                                    except Exception:
                                        continue
                            return False
                        except Exception:
                            return True

                    try:
                        if os.path.exists(cache_file):
                            cache_mtime = os.path.getmtime(cache_file)
                            age = _time.time() - cache_mtime
                            if age < 7 * 86400 and not _src_changed_since(product_path, cache_mtime):
                                with open(cache_file, "r", encoding="utf-8", errors="replace") as cf:
                                    cached_text = cf.read()
                                self._product_analyses[product_name] = cached_text
                                def _show_cached(txt=cached_text):
                                    ch = getattr(self, "_chat_view", None)
                                    if ch:
                                        ch.add_system(f"📋 Análisis previo de **{product_name}** (caché):\n\n{txt}")
                                self.after(0, _show_cached)
                                return
                    except Exception:
                        pass

                    def _notify_analyzing():
                        ch = getattr(self, "_chat_view", None)
                        if ch:
                            ch.add_system(f"🔍 Analizando **{product_name}** en segundo plano...")
                    self.after(0, _notify_analyzing)

                    try:
                        analysis_result = self._analyze_folder_deep(product_path, status)
                        if isinstance(analysis_result, tuple):
                            analysis_text, saved_path = analysis_result
                        else:
                            analysis_text = analysis_result
                            saved_path = ""
                        self._product_analyses[product_name] = analysis_text
                        try:
                            with open(cache_file, "w", encoding="utf-8") as cf:
                                cf.write(analysis_text)
                        except Exception:
                            pass

                        def _show_analysis(txt=analysis_text, sp=saved_path):
                            ch = getattr(self, "_chat_view", None)
                            if ch:
                                ch.add_system(txt)
                                if sp and os.path.exists(sp):
                                    self._remember_file_artifact(sp)
                                    ch.add_file_card(
                                        filename=os.path.basename(sp),
                                        on_open_file=lambda p=sp: self._open_path_file(p),
                                        on_open_folder=lambda p=sp: self._open_path_location(p),
                                        message="Abrir reporte de análisis"
                                    )
                        self.after(0, _show_analysis)
                    except Exception as e:
                        def _analysis_err(ex=e):
                            ch = getattr(self, "_chat_view", None)
                            if ch:
                                ch.add_system(f"⚠️ No se pudo analizar {product_name}: {ex}")
                        self.after(0, _analysis_err)
                threading.Thread(target=_launch_product_with_analysis, daemon=True).start()
                return
            # ── NLP: gaming / retro ───────────────────────────────────────
            _nlp_game_triggers = [
                # Standard
                "quiero jugar", "quisiera jugar", "jugar a", "jugar el juego",
                "pon el juego", "busca el rom", "descarga el rom", "emular",
                "instala el emulador", "juguemos", "abre el juego",
                # Typo/partial variants ("quier" = "quiero" sin 'o')
                "quier jugar", "quiero juga", "quiero jueg",
                # System-named requests: "jugar ... nes/snes/gba"
                "jugar", "juego de nes", "juego de snes", "juego de gba",
                "rom de nes", "rom de snes", "rom de gba",
            ]
            # Only trigger on "jugar" if it appears with a system keyword (avoid false positives)
            _plow_has_system = any(s in plow for s in ["nes", "snes", "gba", "gameboy", "nintendo", "famicom", "megaman", "mario", "zelda", "sonic", "contra", "castlevania", "metroid", "donkey kong"])
            _game_hit = any(t in plow for t in _nlp_game_triggers if t != "jugar") or ("jugar" in plow and _plow_has_system)
            if _game_hit:
                chat = getattr(self, "_chat_view", None)
                if chat:
                    chat.add_user(prompt)
                    chat.show_typing()
                status.configure(text="\ud83c\udfae Buscando juego...", fg=THEME["accent"])

                def _game_worker(q=prompt, _st=status, _en=entry, _ch=chat):
                    try:
                        import claudy_gaming as cg
                    except Exception as e:
                        msg = f"\u274c Motor de gaming no disponible: {e}"
                        self.after(0, lambda m=msg: self._game_done(m, _st, _en, _ch))
                        return
                    def _prog(m):
                        self.after(0, lambda msg=m: _st.configure(text=msg, fg=THEME["accent"]))
                    result = cg.play_retro_game(q, progress_cb=_prog)
                    try:
                        lower_result = (result or "").lower()
                        if "no encontre el rom" in lower_result or "no encontré el rom" in lower_result:
                            system_hint, game_name = cg._detect_system_and_game(q)
                            if system_hint and game_name:
                                self.after(0, lambda: _st.configure(text="🌐 Probando búsqueda alternativa...", fg=THEME["accent"]))
                                alt_result = self._play_game(game_name, system_hint)
                                if alt_result and alt_result != result:
                                    result = alt_result
                    except Exception:
                        pass
                    self.after(0, lambda m=result: self._game_done(m, _st, _en, _ch))

                threading.Thread(target=_game_worker, daemon=True, name="gaming-worker").start()
                return

            # ── NLP: alarmas ──────────────────────────────────────────────
            _nlp_alarm_del_all = [
                "elimina todas las alarmas", "borra todas las alarmas",
                "cancela todas las alarmas", "quita todas las alarmas",
                "eliminar todas las alarmas", "borrar todas las alarmas",
            ]
            _nlp_alarm_del_one = [
                "elimina la alarma", "borra la alarma", "cancela la alarma",
                "quita la alarma", "eliminar alarma", "borrar alarma",
                "cancela alarma", "elimina alarma", "borra alarma",
            ]
            _nlp_alarm_list = [
                "mis alarmas", "ver mis alarmas", "muéstrame las alarmas",
                "mostrame las alarmas", "qué alarmas tengo", "que alarmas tengo",
                "lista de alarmas", "alarmas pendientes",
            ]
            _nlp_alarm_create = [
                "pon una alarma", "ponme una alarma", "crea una alarma", "crear alarma",
                "programa una alarma", "recuérdame en", "recuerdame en",
                "avísame en", "avisame en", "despiértame a", "despertarme a",
                "alarma para", "alarma a las", "alarma en",
            ]

            def _alarm_respond(msg):
                chat = getattr(self, "_chat_view", None)
                if chat:
                    chat.add_user(prompt)
                    chat.add_bot(msg)
                else:
                    self._set_response_text(msg)
                entry.configure(state="normal"); entry.focus_set()

            if any(t in plow for t in _nlp_alarm_del_all):
                msg = self._alarm_delete_all()
                _alarm_respond(msg)
                status.configure(text="🗑️ Alarmas eliminadas", fg=THEME["accent"]); return

            if any(t in plow for t in _nlp_alarm_del_one):
                msg = self._alarm_delete_by_text(prompt)
                _alarm_respond(msg)
                status.configure(text="🗑️ Alarma eliminada", fg=THEME["accent"]); return

            if any(t in plow for t in _nlp_alarm_list):
                msg = self._alarm_list()
                _alarm_respond(msg)
                status.configure(text="⏰ Alarmas", fg=THEME["accent"]); return

            if any(t in plow for t in _nlp_alarm_create):
                msg = self._alarm_set(prompt)
                _alarm_respond(msg)
                status.configure(text="⏰ Alarma configurada", fg=THEME["accent"]); return


            # ── NLP: actualizar memoria (Claudy + agentes + Obsidian) ─────
            _mem_hit, _mem_fact = self._extract_memory_fact(prompt, plow)
            if _mem_hit:
                chat = getattr(self, "_chat_view", None)
                if chat:
                    chat.add_user(prompt)
                    chat.show_typing()
                status.configure(text="🧠 Actualizando memoria...", fg=THEME["accent"])

                def _mem_worker(fact=_mem_fact):
                    try:
                        msg = self._remember_knowledge(fact)
                    except Exception as e:
                        msg = f"No pude actualizar la memoria: {e}"

                    def _done():
                        c = getattr(self, "_chat_view", None)
                        if c:
                            try:
                                c.hide_typing()
                            except Exception:
                                pass
                            c.add_bot(msg)
                        else:
                            self._set_response_text(msg)
                        try:
                            status.configure(text="🧠 Memoria actualizada", fg=THEME["accent"])
                            entry.configure(state="normal"); entry.focus_set()
                        except tk.TclError:
                            pass
                    self.after(0, _done)

                threading.Thread(target=_mem_worker, daemon=True).start()
                return

            # ── NLP: notas ────────────────────────────────────────────────
            _nlp_note_triggers = [
                "guarda una nota", "guarda esto", "anota esto", "anota que",
                "crear nota", "crea una nota", "guardar nota", "nota:", "nota sobre",
                "quiero recordar", "no olvides que", "recuerda que",
            ]
            _nlp_note_list_triggers = [
                "mis notas", "ver mis notas", "muéstrame mis notas", "mostrame mis notas",
                "qué notas tengo", "que notas tengo", "lista de notas",
            ]
            _note_nlp_hit = any(t in plow for t in _nlp_note_triggers)
            _note_list_hit = any(t in plow for t in _nlp_note_list_triggers)
            if _note_list_hit:
                msg = self._notes_list()
                chat = getattr(self, "_chat_view", None)
                if chat:
                    chat.add_user(prompt)
                    chat.add_bot(msg)
                else:
                    self._set_response_text(msg)
                status.configure(text="📝 Notas", fg=THEME["accent"])
                entry.configure(state="normal"); entry.focus_set(); return
            if _note_nlp_hit:
                # Strip the trigger prefix so we save just the note content
                note_content = prompt
                for t in sorted(_nlp_note_triggers, key=len, reverse=True):
                    if t in plow:
                        idx = plow.find(t)
                        note_content = prompt[idx + len(t):].strip(" :,-")
                        break
                if not note_content:
                    note_content = prompt
                msg = self._notes_add(note_content)
                chat = getattr(self, "_chat_view", None)
                if chat:
                    chat.add_user(prompt)
                    chat.add_bot(msg)
                else:
                    self._set_response_text(msg)
                status.configure(text="📝 Nota guardada", fg=THEME["accent"])
                entry.configure(state="normal"); entry.focus_set(); return


            chat = getattr(self, "_chat_view", None)
            if chat is not None:
                try:
                    chat.add_user(prompt)
                    chat.show_typing()
                except Exception:
                    pass

            # ==================== FASE 4 — todas las features ====================
            if prompt.startswith("/") :
                try:
                    import claudy_extras as ex
                except Exception:
                    ex = None
                if ex:
                    cmd = prompt.strip()
                    # Helper: simple text response + restore
                    def _respond(txt):
                        self._set_response_text(txt)
                        entry.configure(state="normal"); entry.focus_set()
                    def _async(fn):
                        def _wrap():
                            out = fn()
                            self.after(0, lambda: self._set_response_text(out))
                        threading.Thread(target=_wrap, daemon=True).start()
                        entry.configure(state="normal"); entry.focus_set()
                    # ---------- CLAUDY POWERS ----------
                    try:
                        import claudy_powers as cp
                    except Exception:
                        cp = None
                    if cp:
                        if cmd.startswith("/install "):
                            name = cmd[9:].strip()
                            self._set_response_text(f"Instalando: {name}\n(puede tomar varios minutos)")
                            status.configure(text="Instalando...", fg=THEME["accent"])
                            _async(lambda: cp.install_app(name)); return
                        if cmd.startswith("/uninstall "):
                            _async(lambda: cp.uninstall_app(cmd[11:].strip())); return
                        if cmd.startswith("/search-app "):
                            _async(lambda: cp.search_app(cmd[12:].strip())); return
                        if cmd.startswith("/installed"):
                            parts = cmd.split(None, 1); flt = parts[1] if len(parts) > 1 else ""
                            _async(lambda: cp.list_installed(flt)); return
                        if cmd.startswith("/launch "):
                            _respond(cp.launch_app(cmd[8:].strip())); return
                        if cmd.startswith("/find-app "):
                            _async(lambda: cp.find_app_path(cmd[10:].strip()) or "(no encontrado, prueba /find-app-deep)"); return
                        if cmd.startswith("/find-app-deep "):
                            self._set_response_text("Busqueda profunda en C:\\ (puede tardar)...")
                            _async(lambda: cp.deep_find_app(cmd[15:].strip()) or "(no encontrado en disco)"); return
                        if cmd.strip() == "/reindex-apps":
                            _async(lambda: cp.rebuild_app_index()); return
                        if cmd.strip() in ("/autostart on", "/autostart-folder on"):
                            _respond(cp.enable_startup_shortcut()); return
                        if cmd.strip() in ("/autostart off", "/autostart-folder off"):
                            _respond(cp.disable_startup_shortcut()); return
                        if cmd.strip() in ("/autostart", "/autostart status"):
                            _respond(f"Autostart (Startup folder): {'ON' if cp.is_startup_shortcut_enabled() else 'OFF'}\nRegistro Run: {'ON' if self._is_auto_start_enabled() else 'OFF'}"); return
                        if cmd.startswith("/close "):
                            _respond(cp.close_app(cmd[7:].strip())); return
                        if cmd.startswith("/running"):
                            parts = cmd.split(None, 1); flt = parts[1] if len(parts) > 1 else ""
                            _async(lambda: cp.list_running(flt)); return
                        if cmd.startswith("/download "):
                            rest = cmd[10:].strip()
                            parts = rest.split(None, 1)
                            url = parts[0]
                            save_as = parts[1] if len(parts) > 1 else ""
                            self._set_response_text(f"Descargando: {url}")
                            _async(lambda: cp.download_and_open(url, save_as)); return
                        if cmd.startswith("/install-url "):
                            url = cmd[13:].strip()
                            self._set_response_text(f"Descargando e instalando: {url}")
                            _async(lambda: cp.download_and_install(url)); return
                        # ---------- FILESYSTEM ----------
                        if cmd.startswith("/tree"):
                            parts = cmd.split(None, 1); p = parts[1].strip() if len(parts) > 1 else "."
                            _async(lambda: cp.folder_tree(p)); return
                        if cmd.startswith("/folder-info"):
                            parts = cmd.split(None, 1); p = parts[1].strip() if len(parts) > 1 else "."
                            _async(lambda: cp.folder_info(p)); return
                        if cmd.startswith("/files"):
                            parts = cmd.split(None, 2)
                            p = parts[1].strip() if len(parts) > 1 else "."
                            pat = parts[2].strip() if len(parts) > 2 else ""
                            _async(lambda: cp.list_files(p, pattern=pat)); return
                        if cmd.startswith("/find"):
                            parts = cmd.split(None, 2)
                            if len(parts) < 3:
                                _respond("Usa: /find <ruta> <texto>"); return
                            _async(lambda: cp.find_in_files(parts[1].strip(), parts[2].strip())); return
                        if cmd.startswith("/read "):
                            p = cmd[6:].strip().strip('"\'')
                            _async(lambda: cp.read_file(p)); return
                        if cmd.startswith("/mkdir ") or cmd.startswith("/crear-carpeta "):
                            p = cmd.split(None, 1)[1].strip() if " " in cmd else ""
                            _respond(cp.create_folder(p)); return
                        if cmd.startswith("/write ") or cmd.startswith("/crear-archivo "):
                            rest = cmd.split(None, 1)[1] if " " in cmd else ""
                            p, content = cp.parse_path_content_arg(rest)
                            if not p:
                                _respond("Usa: /write <ruta> | <contenido>")
                                return
                            _respond(cp.write_file(p, content)); return
                        if cmd.startswith("/append ") or cmd.startswith("/agregar-archivo "):
                            rest = cmd.split(None, 1)[1] if " " in cmd else ""
                            p, content = cp.parse_path_content_arg(rest)
                            if not p:
                                _respond("Usa: /append <ruta> | <contenido>")
                                return
                            _respond(cp.append_file(p, content)); return
                        if cmd.startswith("/replace ") or cmd.startswith("/edit-replace "):
                            rest = cmd.split(None, 1)[1] if " " in cmd else ""
                            parts = [x.strip() for x in rest.split(" | ", 2)]
                            if len(parts) < 3:
                                _respond("Usa: /replace <ruta> | <buscar> | <reemplazo>")
                                return
                            _respond(cp.replace_in_file(parts[0], parts[1], parts[2])); return
                        if cmd.startswith("/analyze"):
                            parts = cmd.split(None, 1); p = parts[1].strip().strip('"\'') if len(parts) > 1 else "."
                            self._set_response_text(f"Analizando: {p}\n(puede tomar un momento)")
                            def _do_analyze():
                                summary = cp.analyze_folder_summary(p)
                                if summary.startswith("No es"):
                                    return summary
                                # Pasarlo al LLM para interpretacion
                                return self.send_quick_message(
                                    f"Analiza esta carpeta y dame un reporte: tipo de proyecto, "
                                    f"tecnologias, archivos clave, estructura, posibles issues.\n\n"
                                    f"DATOS:\n{summary[:8000]}",
                                    _skip_skill_action=True)
                            _async(_do_analyze); return
                    # ---------- Bloque A ----------
                    if cmd.startswith("/ocr "):
                        path = cmd[5:].strip().strip('"\'')
                        _async(lambda: ex.ocr_image(path)); return
                    if cmd.startswith("/iva "):
                        parts = cmd.split()
                        try:
                            neto = "neto" in parts
                            amount = float([p for p in parts[1:] if p != "neto"][0])
                            _respond(ex.iva_calc(amount, neto=neto)); return
                        except Exception:
                            _respond("Usa: /iva <monto> [neto]"); return
                    if cmd.strip() in ("/uf", "/utm", "/indicadores"):
                        _async(lambda: ex.uf_utm()); return
                    if cmd.startswith("/conv "):
                        parts = cmd.split()
                        if len(parts) == 4:
                            _async(lambda: ex.conv_currency(float(parts[1]), parts[2], parts[3])); return
                        _respond("Usa: /conv <monto> <de> <a>  ej: /conv 100 USD CLP"); return
                    if cmd.startswith("/cotizar "):
                        # /cotizar Cliente | item1;1;1000 | item2;2;500
                        rest = cmd[9:].strip()
                        parts = [p.strip() for p in rest.split("|")]
                        if len(parts) < 2:
                            _respond('Usa: /cotizar <cliente> | <item>;<cant>;<precio> | <item>;<cant>;<precio>'); return
                        client = parts[0]
                        items = "\n".join(parts[1:])
                        _async(lambda: ex.generate_quote_pdf(client, items)); return
                    if cmd.startswith("/pomodoro"):
                        parts = cmd.split()
                        if "stop" in parts: _respond(ex.pomodoro_stop()); return
                        try: mins = int(parts[1]) if len(parts) > 1 else 25
                        except: mins = 25
                        _respond(ex.pomodoro_start(mins, on_done=lambda m: self.after(0, lambda: (self._notify("Claudy", m), self.show_chat_bubble(m))))); return
                    if cmd.startswith("/compras"):
                        parts = cmd.split(None, 2)
                        sub = parts[1] if len(parts) > 1 else "list"
                        if sub == "add" and len(parts) > 2: _respond(ex.shop_add(parts[2])); return
                        if sub == "check" and len(parts) > 2: _respond(ex.shop_check(parts[2])); return
                        if sub in ("clear", "limpiar"): _respond(ex.shop_clear()); return
                        _respond(ex.shop_list()); return
                    if cmd.startswith("/email "):
                        # /email <to> "subject" "body"
                        m = re.match(r'/email\s+(\S+)\s+"([^"]+)"\s+"([^"]+)"', cmd)
                        if not m: _respond('Usa: /email <to> "asunto" "cuerpo"'); return
                        cfg = self.load_claudy_config().get("email", {})
                        if not cfg.get("smtp_host"):
                            _respond('Falta config email en config.json: {"email":{"smtp_host":"smtp.gmail.com","smtp_port":465,"smtp_user":"x","smtp_pass":"app-pass","from":"x@gmail.com"}}'); return
                        _async(lambda: ex.send_email_smtp(m.group(1), m.group(2), m.group(3), cfg)); return
                    if cmd.startswith("/yt "):
                        url = cmd[4:].strip()
                        def _yt():
                            tr = ex.youtube_transcript(url)
                            if tr.startswith("Error") or tr.startswith("Instala") or tr.startswith("URL"):
                                return tr
                            return self.send_quick_message(f"Resume este transcript de YouTube:\n\n{tr[:6000]}", _skip_skill_action=True)
                        _async(_yt); return
                    if cmd.startswith("/news"):
                        parts = cmd.split(None, 1); topic = parts[1] if len(parts) > 1 else "chile"
                        _async(lambda: ex.news_today(topic)); return
                    if cmd.startswith("/track "):
                        parts = cmd.split(None, 2)
                        if len(parts) < 3: _respond("Usa: /track <correos|chilexpress|starken|dhl|fedex|ups> <codigo>"); return
                        _respond(ex.track_package(parts[1], parts[2])); return
                    # ---------- Bloque B ----------
                    if cmd.strip() == "/screenshot":
                        path = ex.screenshot_now()
                        _respond(f"Screenshot: {path}"); return
                    if cmd.startswith("/screenshot-ai"):
                        path = ex.screenshot_now()
                        def _scAi():
                            return self._analyze_image_native(path, "Describe en detalle lo que se ve en esta captura de pantalla.")
                        _async(_scAi); return
                    if cmd.startswith("/volumen "):
                        try: _respond(ex.set_volume(int(cmd.split()[1])))
                        except: _respond("Usa: /volumen 50")
                        return
                    if cmd.strip() == "/volumen":
                        _respond(ex.get_volume()); return
                    if cmd.startswith("/brillo "):
                        try: _respond(ex.set_brightness(int(cmd.split()[1])))
                        except: _respond("Usa: /brillo 50")
                        return
                    if cmd.startswith("/pegar "):
                        _respond(ex.paste_to_active_app(cmd[7:])); return
                    if cmd.startswith("/shutdown"):
                        parts = cmd.split()
                        if len(parts) > 1 and parts[1] == "cancel": _respond(ex.shutdown_cancel()); return
                        try: mins = int(parts[1]) if len(parts) > 1 else 10
                        except: mins = 10
                        _respond(ex.shutdown_at(mins)); return
                    if cmd.startswith("/wallpaper "):
                        _respond(ex.set_wallpaper(cmd[11:].strip().strip('"\''))); return
                    if cmd.strip() == "/gaming":
                        is_full = ex.detect_fullscreen()
                        _respond(f"Fullscreen app activa: {is_full}\n(Para modo silencio: /gaming on)"); return
                    # ---------- Bloque C ----------
                    if cmd.startswith("/clima"):
                        parts = cmd.split(None, 1); city = parts[1] if len(parts) > 1 else "Santiago"
                        _async(lambda: ex.weather_now(city)); return
                    if cmd.startswith("/pronostico"):
                        parts = cmd.split(None, 1); city = parts[1] if len(parts) > 1 else "Santiago"
                        _async(lambda: ex.weather_forecast(city)); return
                    if cmd.startswith("/ambient "):
                        _respond(ex.ambient_play(cmd[9:].strip())); return
                    if cmd.startswith("/ruta "):
                        _respond(ex.route_to(cmd[6:].strip())); return
                    if cmd.startswith("/quiz "):
                        topic = cmd[6:].strip()
                        _async(lambda: self.send_quick_message(
                            f"Genera 5 preguntas tipo quiz sobre: {topic}. Formato: pregunta, 4 opciones (A-D), respuesta correcta al final.",
                            _skip_skill_action=True)); return
                    if cmd.startswith("/corregir "):
                        # /corregir <rubrica> | <texto del alumno>
                        rest = cmd[10:].split("|", 1)
                        if len(rest) < 2: _respond("Usa: /corregir <rubrica> | <texto>"); return
                        rubric, work = rest[0].strip(), rest[1].strip()
                        _async(lambda: self.send_quick_message(
                            f"Corrige siguiendo esta rubrica:\n{rubric}\n\nTRABAJO:\n{work}\n\nDa nota 1-7 y feedback.",
                            _skip_skill_action=True)); return
                    if cmd.startswith("/plan-estudio "):
                        topic = cmd[14:].strip()
                        _async(lambda: self.send_quick_message(
                            f"Crea un plan de estudio de 4 semanas para: {topic}. Por semana: objetivos, recursos, ejercicios.",
                            _skip_skill_action=True)); return
                    if cmd.startswith("/resumir "):
                        target = cmd[9:].strip()
                        def _rsm():
                            if target.startswith("http"):
                                tr = ex.youtube_transcript(target)
                                if not tr.startswith("Error") and not tr.startswith("URL"):
                                    return self.send_quick_message(f"Resume:\n{tr[:6000]}", _skip_skill_action=True)
                                return tr
                            if os.path.isfile(target):
                                try:
                                    with open(target, "r", encoding="utf-8", errors="replace") as f:
                                        body = f.read()[:8000]
                                    return self.send_quick_message(f"Resume este texto:\n{body}", _skip_skill_action=True)
                                except Exception as e:
                                    return f"Error: {e}"
                            return self.send_quick_message(f"Resume: {target}", _skip_skill_action=True)
                        _async(_rsm); return
                    if cmd.startswith("/mentor "):
                        rest = cmd[8:].split(None, 1)
                        subj = rest[0] if rest else "general"
                        question = rest[1] if len(rest) > 1 else ""
                        _async(lambda: self.send_quick_message(
                            f"Eres profesor experto en {subj}. Explica paso a paso, con ejemplos. Pregunta del alumno: {question}",
                            _skip_skill_action=True)); return
                    # ---------- Bloque D ----------
                    if cmd.startswith("/video "):
                        _respond(ex.video_generate(cmd[7:])); return
                    if cmd.startswith("/mermaid "):
                        _async(lambda: ex.mermaid_render(cmd[9:])); return
                    if cmd.startswith("/pdf "):
                        # /pdf <titulo> | <cuerpo>
                        parts = cmd[5:].split("|", 1)
                        if len(parts) < 2: _respond("Usa: /pdf <titulo> | <cuerpo>"); return
                        _async(lambda: ex.generate_pdf_report(parts[0].strip(), parts[1].strip())); return
                    if cmd.startswith("/csv "):
                        path = cmd[5:].strip().strip('"\'')
                        _async(lambda: ex.csv_summary(path)); return
                    if cmd.startswith("/plot "):
                        # /plot <archivo.csv> <x> <y>
                        parts = cmd.split()
                        if len(parts) < 4: _respond("Usa: /plot <archivo.csv> <columna_x> <columna_y>"); return
                        _async(lambda: ex.csv_plot(parts[1], parts[2], parts[3])); return
                    if cmd.startswith("/recordar "):
                        # Semantic search across memory
                        query = cmd[10:].strip()
                        msgs = self._load_memory()
                        _async(lambda: ex.embed_search(query, msgs, top_k=8)); return
                    # ---------- Bloque E ----------
                    if cmd.startswith("/genpass"):
                        parts = cmd.split()
                        length = int(parts[1]) if len(parts) > 1 else 20
                        _respond(ex.gen_password(length)); return
                    if cmd.startswith("/vault "):
                        rest = cmd[7:].split(None, 2)
                        sub = rest[0] if rest else ""
                        if sub == "set" and len(rest) == 3: _respond(ex.vault_set(rest[1], rest[2])); return
                        if sub == "get" and len(rest) >= 2: _respond(ex.vault_get(rest[1])); return
                        if sub == "del" and len(rest) >= 2: _respond(ex.vault_del(rest[1])); return
                        if sub == "list" or not sub: _respond(ex.vault_list()); return
                        _respond("Usa: /vault set <name> <value> | /vault get <name> | /vault list | /vault del <name>"); return
                    if cmd.startswith("/phishing "):
                        _respond(ex.phishing_check(cmd[10:])); return
                    # ---------- Bloque F ----------
                    if cmd.strip() == "/sistema":
                        _async(lambda: ex.system_info()); return
                    if cmd.strip() == "/webcam":
                        _async(lambda: ex.webcam_snapshot()); return
            # F3.3 - Expand @file refs in the user prompt before sending
            if "@" in prompt and not prompt.startswith("/"):
                expanded = self._expand_file_refs(prompt)
                if expanded != prompt:
                    prompt = expanded
            # F3.1 /undo /redo
            if prompt.strip() == "/undo":
                self._set_response_text(self._undo_last())
                status.configure(text="Undo", fg=THEME["accent"])
                entry.configure(state="normal"); entry.focus_set(); return
            if prompt.strip() == "/redo":
                self._set_response_text(self._redo_last())
                status.configure(text="Redo", fg=THEME["accent"])
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.2 /plan on|off
            if prompt.startswith("/plan"):
                parts = prompt.split(None, 1); arg = parts[1].strip().lower() if len(parts) > 1 else ""
                if arg in ("on","1","true"): self._plan_mode = True; msg = "Plan mode ON. Claudy solo planeara, no ejecuta."
                elif arg in ("off","0","false"): self._plan_mode = False; msg = "Plan mode OFF."
                else: msg = f"Plan mode: {'ON' if self._plan_mode else 'OFF'}\nUsa: /plan on | /plan off"
                self._set_response_text(msg)
                status.configure(text=f"Plan: {'ON' if self._plan_mode else 'OFF'}", fg=THEME["accent"])
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.4 /init
            if prompt.startswith("/init"):
                parts = prompt.split(None, 1); root = parts[1].strip() if len(parts) > 1 else os.getcwd()
                self._set_response_text(f"Analizando: {root}")
                status.configure(text="Analizando proyecto...", fg=THEME["accent"])
                def _do_init():
                    ok, msg = self._init_project(root)
                    self.after(0, lambda: self._set_response_text(msg))
                    self.after(0, lambda: status.configure(text="Init listo" if ok else "Error", fg=THEME["accent"] if ok else "#ff6b6b"))
                threading.Thread(target=_do_init, daemon=True).start()
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.5 /share
            if prompt.startswith("/share"):
                self._set_response_text("Subiendo conversacion...")
                status.configure(text="Compartiendo...", fg=THEME["accent"])
                def _do_share():
                    ok, msg = self._share_conversation()
                    self.after(0, lambda: self._set_response_text(f"Link: {msg}" if ok else msg))
                threading.Thread(target=_do_share, daemon=True).start()
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.11 /exec <codigo python>
            if prompt.startswith("/exec "):
                code = prompt[6:]
                self._set_response_text("Ejecutando...")
                def _do_exec():
                    out = self._execute_python(code)
                    self.after(0, lambda: self._set_response_text(out))
                threading.Thread(target=_do_exec, daemon=True).start()
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.12 /git ...
            if prompt.startswith("/git "):
                args = prompt[5:].split()
                # Special case: /git commit "mensaje"
                if args and args[0] == "commit" and len(args) >= 2:
                    msg = " ".join(args[1:]).strip('"\'')
                    self._git_cmd(["add", "-A"])
                    out = self._git_cmd(["commit", "-m", msg])
                else:
                    out = self._git_cmd(args)
                self._set_response_text(out)
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.13 /test
            if prompt.strip() == "/test":
                self._set_response_text("Corriendo tests...")
                status.configure(text="Tests...", fg=THEME["accent"])
                def _do_test():
                    out = self._run_tests()
                    self.after(0, lambda: self._set_response_text(out))
                threading.Thread(target=_do_test, daemon=True).start()
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.15 /skill buscar  F3.16 /skill install
            if prompt.startswith("/skill buscar ") or prompt.startswith("/skill search "):
                q = prompt.split(None, 2)[2].strip()
                self._set_response_text(self._search_skills_registry(q))
                entry.configure(state="normal"); entry.focus_set(); return
            if prompt.startswith("/skill install "):
                src = prompt.split(None, 2)[2].strip()
                ok, msg = self._install_skill(src)
                self._set_response_text(msg)
                entry.configure(state="normal"); entry.focus_set(); return
            if prompt.startswith("/skill use ") or prompt.startswith("/skill usa "):
                q = prompt.split(None, 2)[2].strip()
                def _do_skill_use():
                    msg = self._skill_use(q)
                    self.after(0, lambda: self._set_response_text(msg))
                threading.Thread(target=_do_skill_use, daemon=True).start()
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.17 /play <query>
            if prompt.startswith("/play"):
                parts = prompt.split(None, 1); q = parts[1].strip() if len(parts) > 1 else ""
                self._set_response_text(self._spotify_play(q))
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.19 /board /task
            if prompt.strip() == "/board":
                self._set_response_text(self._kanban_list())
                entry.configure(state="normal"); entry.focus_set(); return
            if prompt.startswith("/task "):
                rest = prompt[6:].strip()
                if rest.startswith("add "):
                    txt = rest[4:].strip()
                    self._set_response_text(self._kanban_add(txt))
                elif rest.startswith("done "):
                    tid = rest[5:].strip()
                    self._set_response_text(self._kanban_move(tid, "done"))
                elif rest.startswith("del "):
                    tid = rest[4:].strip()
                    self._set_response_text(self._kanban_delete(tid))
                else:
                    self._set_response_text("Usa: /task add <texto> | /task done <id> | /task del <id>")
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.21 /delegate --as <personality> <tarea>
            if prompt.startswith("/delegate-as "):
                rest = prompt[13:].strip()
                parts = rest.split(None, 1)
                if len(parts) < 2:
                    self._set_response_text("Usa: /delegate-as <personality> <tarea>")
                    entry.configure(state="normal"); entry.focus_set(); return
                pname, task = parts[0], parts[1]
                full_task = f"[adopta personalidad: {pname}]\n{task}"
                ok, msg = self._spawn_subagent(full_task)
                self._set_response_text(msg)
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.22 /debate <tema>
            if prompt.startswith("/debate "):
                topic = prompt[8:].strip()
                self._set_response_text(f"Lanzando 2 subagentes para debatir: {topic}")
                self._spawn_subagent(f"[personalidad: brutal] Defiende a favor: {topic}")
                self._spawn_subagent(f"[personalidad: brutal] Defiende en contra: {topic}")
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.23 /detect-ai <texto>
            if prompt.startswith("/detect-ai "):
                txt = prompt[11:].strip()
                self._set_response_text("Analizando...")
                def _do_detect():
                    out = self._detect_ai_text(txt)
                    self.after(0, lambda: self._set_response_text(out))
                threading.Thread(target=_do_detect, daemon=True).start()
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.24 /exif <ruta>
            if prompt.startswith("/exif "):
                p = prompt[6:].strip().strip('"\'')
                self._set_response_text(self._read_exif(p))
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.8 /telegram-voice on|off  (TTS reply en Telegram)
            if prompt.startswith("/telegram-voice"):
                parts = prompt.split(None, 1); arg = parts[1].strip().lower() if len(parts) > 1 else ""
                cfg_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
                try:
                    with open(cfg_path, "r", encoding="utf-8-sig") as f:
                        d = json.load(f)
                except Exception:
                    d = {}
                d.setdefault("telegram", {})
                if arg in ("on","1","true"): d["telegram"]["ttsReply"] = True
                elif arg in ("off","0","false"): d["telegram"]["ttsReply"] = False
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(d, f, indent=2, ensure_ascii=False)
                state = "ON" if d["telegram"].get("ttsReply") else "OFF"
                self._set_response_text(f"Telegram TTS reply: {state}\nReinicia el bot para aplicar.")
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.18 /gmail
            if prompt.startswith("/gmail"):
                parts = prompt.split(); n = 5
                if len(parts) > 1:
                    try: n = max(1, min(20, int(parts[1])))
                    except Exception: pass
                self._set_response_text("Consultando Gmail...")
                def _do_gm():
                    out = self._gmail_inbox(n=n)
                    self.after(0, lambda: self._set_response_text(out))
                threading.Thread(target=_do_gm, daemon=True).start()
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.10 /lsp
            if prompt.strip() == "/lsp":
                self._set_response_text("Ejecutando diagnostics...")
                def _do_lsp():
                    out = self._lsp_diagnostics()
                    self.after(0, lambda: self._set_response_text(out))
                threading.Thread(target=_do_lsp, daemon=True).start()
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.7 /escucha — voice listen con wake word
            if prompt.strip() in ("/escucha", "/listen"):
                msg = self._start_voice_listen()
                self._set_response_text(msg)
                entry.configure(state="normal"); entry.focus_set(); return
            if prompt.strip() in ("/escucha stop", "/listen stop"):
                self._voice_listening = False
                self._set_response_text("Escucha detenida.")
                entry.configure(state="normal"); entry.focus_set(); return
            # F3.14 /skills-reload — reload SKILL.md compat
            if prompt.strip() == "/skills-reload":
                count = self._reload_skills_compat()
                self._set_response_text(f"Skills recargadas: {count}")
                entry.configure(state="normal"); entry.focus_set(); return
            # Handle /mcp commands.
            if prompt.startswith("/mcp"):
                parts = prompt.split(None, 3)
                sub = parts[1].strip() if len(parts) > 1 else ""
                self._set_response_text("MCP procesando...")
                status.configure(text="MCP...", fg=THEME["accent"])

                def _do_mcp():
                    try:
                        import mcp_client
                    except Exception as e:
                        self.after(0, lambda: self._set_response_text(f"MCP no disponible: {e}"))
                        return
                    if not sub or sub == "list":
                        msg = mcp_client.list_servers()
                    elif sub == "tools":
                        srv = parts[2] if len(parts) > 2 else ""
                        msg = mcp_client.list_tools(srv) if srv else "Usa: /mcp tools <server>"
                    elif sub == "call":
                        srv_tool = parts[2] if len(parts) > 2 else ""
                        args_str = parts[3] if len(parts) > 3 else "{}"
                        if "/" not in srv_tool:
                            msg = "Usa: /mcp call <server>/<tool> <json_args>"
                        else:
                            srv, tool = srv_tool.split("/", 1)
                            try:
                                args = json.loads(args_str) if args_str else {}
                            except Exception:
                                args = {"input": args_str}
                            msg = mcp_client.call_tool(srv, tool, args)
                    else:
                        msg = "Usa:\n/mcp list\n/mcp tools <server>\n/mcp call <server>/<tool> <json_args>"
                    self.after(0, lambda m=msg: self._set_response_text(m))
                    self.after(0, lambda: status.configure(text="MCP listo", fg=THEME["accent"]))
                threading.Thread(target=_do_mcp, daemon=True).start()
                entry.configure(state="normal")
                entry.focus_set()
                return
            # /gmail and /drive — high-level shortcuts over the MCP servers.
            if prompt.startswith("/gmail") or prompt.startswith("/drive"):
                server = "gmail" if prompt.startswith("/gmail") else "gdrive"
                parts = prompt.split(None, 2)
                sub = parts[1].strip().lower() if len(parts) > 1 else ""
                rest = parts[2] if len(parts) > 2 else ""
                self._set_response_text(f"{server} procesando...")
                status.configure(text=f"{server}...", fg=THEME["accent"])

                def _do_google():
                    try:
                        import mcp_client
                    except Exception as e:
                        self.after(0, lambda: self._set_response_text(f"MCP no disponible: {e}"))
                        return
                    if not sub or sub in ("help", "?"):
                        if server == "gmail":
                            msg = ("Gmail:\n"
                                   "  /gmail tools                 lista herramientas\n"
                                   "  /gmail search <query>        buscar correos\n"
                                   "  /gmail read <id>             leer correo por id\n"
                                   "  /gmail send <to>|<subj>|<body>  enviar correo\n"
                                   "  /gmail raw <tool> <json>     llamada directa")
                        else:
                            msg = ("Drive:\n"
                                   "  /drive tools                 lista herramientas\n"
                                   "  /drive search <query>        buscar archivos\n"
                                   "  /drive read <fileId>         leer archivo por id\n"
                                   "  /drive raw <tool> <json>     llamada directa")
                    elif sub == "tools":
                        msg = mcp_client.list_tools(server)
                    elif sub == "search":
                        tool = "search_emails" if server == "gmail" else "search"
                        msg = mcp_client.call_tool(server, tool, {"query": rest})
                    elif sub == "read":
                        if server == "gmail":
                            msg = mcp_client.call_tool(server, "read_email", {"messageId": rest.strip()})
                        else:
                            msg = mcp_client.call_tool(server, "read", {"fileId": rest.strip()})
                    elif sub == "send" and server == "gmail":
                        pieces = [p.strip() for p in rest.split("|", 2)]
                        if len(pieces) < 3:
                            msg = "Usa: /gmail send <to>|<subject>|<body>"
                        else:
                            msg = mcp_client.call_tool(server, "send_email", {
                                "to": [pieces[0]],
                                "subject": pieces[1],
                                "body": pieces[2],
                            })
                    elif sub == "raw":
                        rp = rest.split(None, 1)
                        tool = rp[0] if rp else ""
                        args_str = rp[1] if len(rp) > 1 else "{}"
                        try:
                            args = json.loads(args_str)
                        except Exception:
                            args = {"input": args_str}
                        msg = mcp_client.call_tool(server, tool, args) if tool else "Usa: /xxx raw <tool> <json>"
                    else:
                        msg = f"Subcomando desconocido: {sub}. Usa /{server} help"
                    self.after(0, lambda m=msg: self._set_response_text(m))
                    self.after(0, lambda: status.configure(text=f"{server} listo", fg=THEME["accent"]))
                threading.Thread(target=_do_google, daemon=True).start()
                entry.configure(state="normal")
                entry.focus_set()
                return
            # /docs and /sheets — Google Docs/Sheets via google_docs module.
            if prompt.startswith("/docs") or prompt.startswith("/sheets"):
                cmd_type = "docs" if prompt.startswith("/docs") else "sheets"
                parts = prompt.split(None, 2)
                sub = parts[1].strip().lower() if len(parts) > 1 else ""
                rest = parts[2] if len(parts) > 2 else ""
                self._set_response_text(f"{cmd_type} procesando...")
                status.configure(text=f"{cmd_type}...", fg=THEME["accent"])

                def _do_docs_sheets():
                    try:
                        import google_docs as gdocs
                    except Exception as e:
                        self.after(0, lambda: self._set_response_text(f"Google Docs no disponible: {e}"))
                        return
                    if not sub or sub in ("help", "?"):
                        if cmd_type == "docs":
                            msg = ("Docs:\n"
                                   "  /docs connect              conectar Google\n"
                                   "  /docs status               estado conexion\n"
                                   "  /docs search <query>       buscar documentos\n"
                                   "  /docs read <id>            leer documento\n"
                                   "  /docs create <title>|<content>  crear documento\n"
                                   "  /docs append <id>|<text>   agregar texto al final")
                        else:
                            msg = ("Sheets:\n"
                                   "  /sheets connect            conectar Google\n"
                                   "  /sheets status             estado conexion\n"
                                   "  /sheets search <query>     buscar hojas\n"
                                   "  /sheets read <id> [range]  leer hoja (default A1:Z1000)\n"
                                   "  /sheets create <title>|<headers>  crear hoja\n"
                                   "  /sheets append <id>|<range>|<data>  agregar filas")
                    elif sub == "connect":
                        result = gdocs.connect()
                        msg = "Conectado!" if result.get("connected") else f"Error: {result.get('reason')}"
                    elif sub == "status":
                        result = gdocs.status()
                        msg = "Conectado" if result.get("connected") else f"No conectado: {result.get('reason')}"
                    elif sub == "search":
                        doc_type = "document" if cmd_type == "docs" else "spreadsheet"
                        result = gdocs.search_docs(rest, doc_type=doc_type)
                        if result.get("connected"):
                            items = result.get("items", [])
                            if not items:
                                msg = "No se encontraron resultados."
                            else:
                                msg = f"Encontrados {len(items)}:\n"
                                for item in items:
                                    msg += f"  - {item['name']} (id: {item['id']})\n"
                        else:
                            msg = f"Error: {result.get('reason')}"
                    elif sub == "read":
                        read_parts = rest.split(None, 1)
                        doc_id = read_parts[0] if read_parts else ""
                        if not doc_id:
                            msg = f"Usa: /{cmd_type} read <id>"
                        elif cmd_type == "docs":
                            result = gdocs.read_doc(doc_id)
                            if result.get("ok"):
                                msg = f"Titulo: {result.get('title')}\n\n{result.get('content', '')[:5000]}"
                            else:
                                msg = f"Error: {result.get('reason')}"
                        else:
                            range_name = read_parts[1] if len(read_parts) > 1 else "A1:Z1000"
                            result = gdocs.read_sheet(doc_id, range_name)
                            if result.get("ok"):
                                values = result.get("values", [])
                                msg = f"Rango: {result.get('range')}\nFilas: {len(values)}\n\n"
                                for row in values[:50]:
                                    msg += " | ".join(str(c) for c in row) + "\n"
                                if len(values) > 50:
                                    msg += f"\n... y {len(values) - 50} filas mas"
                            else:
                                msg = f"Error: {result.get('reason')}"
                    elif sub == "create":
                        create_parts = rest.split("|", 1)
                        title = create_parts[0].strip() if create_parts else ""
                        if not title:
                            msg = f"Usa: /{cmd_type} create <titulo>"
                        elif cmd_type == "docs":
                            content = create_parts[1].strip() if len(create_parts) > 1 else ""
                            result = gdocs.create_doc(title, content)
                            if result.get("ok"):
                                msg = f"Creado: {result.get('title')}\nID: {result.get('id')}\nLink: {result.get('link')}"
                            else:
                                msg = f"Error: {result.get('reason')}"
                        else:
                            headers_str = create_parts[1].strip() if len(create_parts) > 1 else ""
                            headers = [h.strip() for h in headers_str.split(",")] if headers_str else None
                            result = gdocs.create_sheet(title, headers=headers)
                            if result.get("ok"):
                                msg = f"Creada: {result.get('title')}\nID: {result.get('id')}\nLink: {result.get('link')}"
                            else:
                                msg = f"Error: {result.get('reason')}"
                    elif sub == "append":
                        append_parts = rest.split("|", 2 if cmd_type == "sheets" else 1)
                        doc_id = append_parts[0].strip() if append_parts else ""
                        if not doc_id:
                            msg = f"Usa: /{cmd_type} append <id>|<text>"
                        elif cmd_type == "docs":
                            text = append_parts[1].strip() if len(append_parts) > 1 else ""
                            if not text:
                                msg = "Usa: /docs append <id>|<texto>"
                            else:
                                result = gdocs.append_to_doc(doc_id, "\n" + text)
                                msg = "Agregado!" if result.get("ok") else f"Error: {result.get('reason')}"
                        else:
                            range_name = append_parts[1].strip() if len(append_parts) > 1 else "A1"
                            data_str = append_parts[2].strip() if len(append_parts) > 2 else ""
                            if not data_str:
                                msg = "Usa: /sheets append <id>|<range>|<fila1;fila2>"
                            else:
                                rows = [r.split(",") for r in data_str.split(";")]
                                result = gdocs.append_to_sheet(doc_id, range_name, rows)
                                msg = f"Agregadas {result.get('updatedRows')} filas" if result.get("ok") else f"Error: {result.get('reason')}"
                    else:
                        msg = f"Subcomando desconocido: {sub}. Usa /{cmd_type} help"
                    self.after(0, lambda m=msg: self._set_response_text(m))
                    self.after(0, lambda: status.configure(text=f"{cmd_type} listo", fg=THEME["accent"]))
                threading.Thread(target=_do_docs_sheets, daemon=True).start()
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /browse <url> - fetch page and summarize.
            if prompt.startswith("/browse"):
                parts = prompt.split(None, 1)
                url = parts[1].strip() if len(parts) > 1 else ""
                if not url:
                    self._set_response_text("Usa: /browse <url>")
                    status.configure(text="Falta URL", fg="#ff6b6b")
                    entry.configure(state="normal")
                    entry.focus_set()
                    return
                if not url.startswith("http"):
                    url = "https://" + url
                self._set_response_text(f"Navegando a: {url}")
                status.configure(text="Navegando...", fg=THEME["accent"])

                def _do_browse():
                    try:
                        from browser import fetch
                    except Exception as e:
                        self.after(0, lambda: self._set_response_text(f"Browser no disponible: {e}"))
                        return
                    result = fetch(url)
                    if result.get("error"):
                        self.after(0, lambda: self._set_response_text(f"Error: {result['error']}"))
                        self.after(0, lambda: status.configure(text="Error", fg="#ff6b6b"))
                        return
                    summary = f"Titulo: {result.get('title','')}\nURL: {result.get('url')}\n"
                    if result.get("screenshot"):
                        summary += f"Screenshot: {result['screenshot']}\n"
                    summary += f"\n---\n{result.get('text','(sin texto)')[:3000]}"
                    self.after(0, lambda: self._set_response_text(summary))
                    self.after(0, lambda: status.configure(text="Listo", fg=THEME["accent"]))
                threading.Thread(target=_do_browse, daemon=True).start()
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /delegate command (subagent spawn).
            if prompt.startswith("/delegate"):
                parts = prompt.split(None, 1)
                task = parts[1].strip() if len(parts) > 1 else ""
                ok, msg = self._spawn_subagent(task)
                self._set_response_text(msg)
                status.configure(text="Subagente OK" if ok else "Error", fg=THEME["accent"] if ok else "#ff6b6b")
                entry.configure(state="normal")
                entry.focus_set()
                return
            if prompt.strip() == "/subagents":
                self._set_response_text(self._list_subagents())
                status.configure(text="Subagentes", fg=THEME["accent"])
                entry.configure(state="normal")
                entry.focus_set()
                return
            if prompt.startswith("/subagent "):
                sid = prompt.split(None, 1)[1].strip()
                self._set_response_text(self._get_subagent_result(sid))
                status.configure(text=f"Resultado {sid}", fg=THEME["accent"])
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /batch command.
            if prompt.startswith("/batch"):
                parts = prompt.split(None, 2)
                if len(parts) < 2:
                    self._set_response_text("Usa: /batch <archivo.txt> [concurrencia]\nEl archivo debe tener 1 prompt por linea.")
                    status.configure(text="Falta archivo", fg="#ff6b6b")
                    entry.configure(state="normal")
                    entry.focus_set()
                    return
                file_arg = parts[1]
                conc = 3
                if len(parts) > 2:
                    try:
                        conc = max(1, min(10, int(parts[2])))
                    except Exception:
                        pass
                self._set_response_text(f"Procesando batch: {file_arg}\nConcurrencia: {conc}")
                status.configure(text="Batch corriendo...", fg=THEME["accent"])

                def _do_batch():
                    ok, msg = self._run_batch(file_arg, concurrency=conc)
                    self.after(0, lambda: self._set_response_text(msg))
                    self.after(0, lambda: status.configure(
                        text="Batch listo" if ok else "Error batch",
                        fg=THEME["accent"] if ok else "#ff6b6b",
                    ))
                threading.Thread(target=_do_batch, daemon=True).start()
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /index command (RAG: index a folder of documents).
            if prompt.startswith("/index"):
                parts = prompt.split(None, 1)
                folder = parts[1].strip().strip('"') if len(parts) > 1 else ""
                if not folder:
                    self._set_response_text("Usa: /index <carpeta>\nIndexa tus documentos para luego preguntar con /docs.")
                    status.configure(text="Falta carpeta", fg="#ff6b6b")
                    entry.configure(state="normal")
                    entry.focus_set()
                    return
                self._set_response_text(f"Indexando: {folder}\n(esto puede tardar la primera vez)")
                status.configure(text="Indexando...", fg=THEME["accent"])

                def _do_index():
                    try:
                        import rag_index
                        res = rag_index.index_folder(folder)
                    except Exception as e:
                        res = {"ok": False, "error": f"Error: {e}"}
                    if res.get("ok"):
                        msg = (f"Listo. {res['files_indexed']} archivos, "
                               f"{res['chunks_added']} fragmentos nuevos.\n"
                               f"Total indexado: {res['total_chunks']} | motor: {res['backend']}\n"
                               f"Pregunta con: /docs <tu pregunta>")
                    else:
                        msg = res.get("error", "No pude indexar.")
                    self.after(0, lambda: self._set_response_text(msg))
                    self.after(0, lambda: status.configure(
                        text="Indexado" if res.get("ok") else "Error",
                        fg=THEME["accent"] if res.get("ok") else "#ff6b6b",
                    ))
                threading.Thread(target=_do_index, daemon=True).start()
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /docs command (RAG: answer using indexed documents).
            if prompt.startswith("/docs"):
                parts = prompt.split(None, 1)
                question = parts[1].strip() if len(parts) > 1 else ""
                if not question:
                    self._set_response_text("Usa: /docs <pregunta>\nResponde usando los documentos que indexaste con /index.")
                    status.configure(text="Falta pregunta", fg="#ff6b6b")
                    entry.configure(state="normal")
                    entry.focus_set()
                    return
                self._set_response_text("Buscando en tus documentos...")
                status.configure(text="Consultando docs...", fg=THEME["accent"])

                def _do_docs():
                    try:
                        import rag_index
                        hits = rag_index.search(question, k=4)
                    except Exception as e:
                        hits = []
                        self.after(0, lambda: self._set_response_text(f"Error RAG: {e}"))
                    if not hits:
                        self.after(0, lambda: self._set_response_text(
                            "No encontré nada relevante. ¿Indexaste una carpeta con /index?"))
                        self.after(0, lambda: status.configure(text="Sin resultados", fg=THEME["text_secondary"]))
                        return
                    context_parts = []
                    for h in hits:
                        name = os.path.basename(h["path"])
                        context_parts.append(f"[Fuente: {name}]\n{h['chunk']}")
                    context = "\n\n".join(context_parts)
                    enhanced = (
                        "Responde la pregunta del usuario usando EXCLUSIVAMENTE estos extractos de "
                        "sus documentos. Cita el archivo fuente entre paréntesis. Si los extractos no "
                        "alcanzan, dilo claramente.\n\n"
                        f"{context}\n\nPregunta: {question}"
                    )
                    try:
                        answer = self.send_quick_message(enhanced, _skip_skill_action=True)
                    except Exception as e:
                        answer = f"Error consultando el modelo: {e}"
                    sources = ", ".join(sorted({os.path.basename(h["path"]) for h in hits}))
                    answer = f"{answer}\n\n— Fuentes: {sources}"
                    self.after(0, lambda: self.finish_quick_answer(answer, status, entry))
                threading.Thread(target=_do_docs, daemon=True).start()
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /rag command (RAG index status / clear).
            if prompt.startswith("/rag"):
                parts = prompt.split()
                sub = parts[1].lower() if len(parts) > 1 else "status"
                try:
                    import rag_index
                    if sub == "clear":
                        rag_index.clear()
                        msg = "Índice RAG borrado."
                    else:
                        st = rag_index.status()
                        if not st.get("exists"):
                            msg = "No hay índice todavía. Usa: /index <carpeta>"
                        else:
                            folders = "\n".join(f"  • {f}" for f in st.get("folders", [])) or "  (ninguna)"
                            msg = (f"Índice RAG:\n{folders}\n"
                                   f"Archivos: {st.get('files', 0)} | Fragmentos: {st.get('chunks', 0)} | "
                                   f"Motor: {st.get('backend', '?')}")
                except Exception as e:
                    msg = f"Error RAG: {e}"
                self._set_response_text(msg)
                status.configure(text="RAG", fg=THEME["accent"])
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /stream command (toggle live token streaming in the bubble).
            if prompt.startswith("/stream"):
                arg = prompt[len("/stream"):].strip().lower()
                if arg in ("on", "1", "true", "si", "sí"):
                    self._streaming_enabled = True
                    msg = "Streaming activado: verás las respuestas escribirse en vivo."
                elif arg in ("off", "0", "false", "no"):
                    self._streaming_enabled = False
                    msg = "Streaming desactivado."
                else:
                    estado = "ON" if getattr(self, "_streaming_enabled", False) else "OFF"
                    msg = f"Streaming está {estado}. Usa: /stream on  |  /stream off"
                self._set_response_text(msg)
                status.configure(text="Streaming", fg=THEME["accent"])
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /img command.
            if prompt.startswith("/img"):
                parts = prompt.split(None, 1)
                img_prompt = parts[1].strip() if len(parts) > 1 else ""
                if not img_prompt:
                    self._set_response_text("Usa: /img <descripcion en ingles o espanol>")
                    status.configure(text="Falta prompt", fg="#ff6b6b")
                    entry.configure(state="normal")
                    entry.focus_set()
                    return
                self._set_response_text(f"Generando imagen: {img_prompt}\n(se abrira al terminar)")
                status.configure(text="Generando...", fg=THEME["accent"])

                def _do_gen():
                    ok, msg = self._generate_image(img_prompt)
                    if ok:
                        self.after(0, lambda: self._set_response_text(f"Imagen lista:\n{msg}"))
                        self.after(0, lambda: status.configure(text="Imagen lista", fg=THEME["accent"]))
                    else:
                        self.after(0, lambda: self._set_response_text(msg))
                        self.after(0, lambda: status.configure(text="Error", fg="#ff6b6b"))
                threading.Thread(target=_do_gen, daemon=True).start()
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /checkpoint command.
            if prompt.startswith("/checkpoint"):
                parts = prompt.split(None, 1)
                arg = parts[1].strip() if len(parts) > 1 else ""
                if not arg or arg.lower() == "list":
                    items = self._file_checkpoint_list()
                    if not items:
                        self._set_response_text("No hay checkpoints.\nUsa: /checkpoint <ruta_archivo>")
                        status.configure(text="0 checkpoints", fg=THEME["text_secondary"])
                    else:
                        lines = [f"{cid} -> {src}" for cid, src, _ts in items[:20]]
                        self._set_response_text("Checkpoints:\n" + "\n".join(lines))
                        status.configure(text=f"{len(items)} checkpoints", fg=THEME["accent"])
                else:
                    ok, msg = self._file_checkpoint_create(arg)
                    self._set_response_text(msg)
                    status.configure(text="Checkpoint creado" if ok else "Error", fg=THEME["accent"] if ok else "#ff6b6b")
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /rollback command.
            if prompt.startswith("/rollback"):
                parts = prompt.split(None, 1)
                arg = parts[1].strip() if len(parts) > 1 else ""
                if not arg:
                    items = self._file_checkpoint_list()
                    if not items:
                        self._set_response_text("No hay checkpoints para restaurar.")
                        status.configure(text="0 checkpoints", fg=THEME["text_secondary"])
                    else:
                        lines = [f"{cid} -> {src}" for cid, src, _ts in items[:20]]
                        self._set_response_text("Usa: /rollback <id>\n\n" + "\n".join(lines))
                        status.configure(text=f"{len(items)} disponibles", fg=THEME["accent"])
                else:
                    ok, msg = self._file_checkpoint_rollback(arg)
                    self._set_response_text(msg)
                    status.configure(text="Restaurado" if ok else "Error", fg=THEME["accent"] if ok else "#ff6b6b")
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /voice command.
            if prompt.startswith("/voice"):
                parts = prompt.split(None, 1)
                arg = parts[1].strip().lower() if len(parts) > 1 else ""
                if not TTS_OK:
                    self._set_response_text("TTS no disponible. Instala edge-tts: pip install edge-tts")
                    status.configure(text="TTS off", fg="#ff6b6b")
                    entry.configure(state="normal")
                    entry.focus_set()
                    return
                if arg in ("on", "1", "true", "si", "sí"):
                    self._voice_enabled = True
                    self._set_response_text("Voz activada. Lo que diga lo escuchas.")
                    status.configure(text="Voz: ON", fg=THEME["accent"])
                    _tts_speak("Voz activada.")
                elif arg in ("off", "0", "false", "no"):
                    self._voice_enabled = False
                    _tts_stop()
                    self._set_response_text("Voz desactivada.")
                    status.configure(text="Voz: OFF", fg=THEME["text_secondary"])
                elif arg == "stop":
                    _tts_stop()
                    self._set_response_text("Voz cortada.")
                    status.configure(text="Voz cortada", fg=THEME["text_secondary"])
                else:
                    state = "ON" if self._voice_enabled else "OFF"
                    self._set_response_text(f"Voz: {state}\nUsa: /voice on | /voice off | /voice stop")
                    status.configure(text=f"Voz: {state}", fg=THEME["accent"])
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /personality command.
            if prompt.startswith("/personality"):
                parts = prompt.split(None, 1)
                if len(parts) < 2:
                    available = self._list_personalities()
                    current = self._current_personality_name()
                    self._set_response_text(
                        f"Personalidad actual: {current}\n\nDisponibles:\n{', '.join(available)}\n\nUsa: /personality <nombre>"
                    )
                    status.configure(text=f"Personalidad: {current}", fg=THEME["accent"])
                    entry.configure(state="normal")
                    entry.focus_set()
                    return
                name = parts[1].strip().lower()
                ok, msg = self._apply_personality(name)
                if ok:
                    status.configure(text=f"Personalidad: {name}", fg=THEME["accent"])
                    self._set_response_text(msg)
                else:
                    status.configure(text="Personalidad no encontrada", fg="#ff6b6b")
                    self._set_response_text(msg)
                entry.configure(state="normal")
                entry.focus_set()
                return
            # Handle /model command.
            if prompt.startswith("/model"):
                parts = prompt.split(None, 1)
                if len(parts) < 2:
                    current = self._current_model or config["opencode"].get("defaultModel", "deepseek-chat")
                    status.configure(text=f"Modelo actual: {current}", fg=THEME["accent"])
                    self._set_response_text(f"Modelos disponibles:\n{', '.join(self._available_models)}\n\nUsa: /model <nombre>")
                    entry.configure(state="normal")
                    entry.focus_set()
                    return
                model_name = parts[1].strip().lower()
                # Match partial names.
                matched = None
                for m in self._available_models:
                    if model_name in m.lower():
                        matched = m
                        break
                if matched:
                    self._current_model = matched
                    status.configure(text=f"Modelo cambiado a: {matched}", fg=THEME["accent"])
                    self._set_response_text(f"Listo con {matched}")
                else:
                    status.configure(text=f"Modelo no encontrado: {model_name}", fg="#ff6b6b")
                    self._set_response_text(f"No conozco '{model_name}'.\nDisponibles: {', '.join(self._available_models)}")
                entry.configure(state="normal")
                entry.focus_set()
                return
            # ── ALARMAS ──────────────────────────────────────────────────
            if prompt.startswith("/alarma"):
                rest = prompt[7:].strip()
                if not rest or rest in ("list", "ver", "listar"):
                    self._set_response_text(self._alarm_list())
                elif rest.startswith("del ") or rest.startswith("borrar "):
                    aid = rest.split(None, 1)[1].strip()
                    self._set_response_text(self._alarm_delete(aid))
                else:
                    msg = self._alarm_set(rest)
                    self._set_response_text(msg)
                entry.configure(state="normal"); entry.focus_set(); return
            # ── NOTAS ─────────────────────────────────────────────────────
            if prompt.startswith("/nota"):
                rest = prompt[5:].strip()
                if not rest or rest in ("list", "ver", "listar", "mis notas"):
                    self._set_response_text(self._notes_list())
                elif rest.startswith("del ") or rest.startswith("borrar "):
                    nid = rest.split(None, 1)[1].strip()
                    self._set_response_text(self._notes_delete(nid))
                else:
                    msg = self._notes_add(rest)
                    self._set_response_text(msg)
                entry.configure(state="normal"); entry.focus_set(); return
            entry.configure(state="disabled")

            thinking = random.choice([
                "Pensando...", "Dándole vueltas...", "Conectando neuronas...",
                "Consultando al oráculo...", "Hablando con las estrellas...", "Esforzándome...",
            ])
            status.configure(text=thinking, fg=THEME["accent"])
            if not chat:
                self._set_response_text(f"> {prompt}")
            # Animacion: pasa a thinking mientras procesa
            try:
                if self.state != "bounce":
                    self.state = "thinking"
            except Exception:
                pass
            if self._plan_mode:
                prompt = (
                    "[PLAN MODE] Solo planea, NO ejecutes. Genera un plan paso a paso "
                    "(numerado, archivos a tocar, riesgos). No corras comandos.\n\n"
                    + prompt
                )
            self.ask_claudy(prompt, status, entry)

        def handle_return(event):
            # Check if Shift is pressed (state 0x0001 is Shift, 0x0003 is Shift+NumLock, etc.)
            if event.state & 0x0001:
                return None  # Let Tkinter insert the newline natively
            submit()
            return "break"   # Stop standard Return key from adding a newline

        send_btn.bind("<Button-1>", submit)
        send_btn.bind("<Enter>", lambda _e: send_btn.config(bg="#58c7ff", fg="#06111f"))
        send_btn.bind("<Leave>", lambda _e: send_btn.config(bg="#c02dff", fg="#ffffff"))
        entry.bind("<Return>", handle_return)
        entry.bind("<Escape>", lambda _e: self.hide_bubble())
        entry.bind("<FocusIn>", lambda _e: self._record_activity())

        # ===== Spacebar Walkie-Talkie Push-to-Talk (PTT) =====
        self._space_pressed_time = None
        self._ptt_active = False

        def on_space_press(event):
            # If already holding or if entry is disabled/submitting, ignore repeat key events
            if self._space_pressed_time is not None:
                return None
            self._space_pressed_time = time.time()
            self._ptt_active = False
            
            # Non-blocking check for hold duration
            def check_hold():
                if self._space_pressed_time is not None:
                    duration = time.time() - self._space_pressed_time
                    if duration >= 1.9:
                        self._ptt_active = True
                        self._start_ptt_recording(status)
            
            bub.after(2000, check_hold)
            return None

        def on_space_release(event):
            if self._space_pressed_time is None:
                return None
            
            self._space_pressed_time = None
            if self._ptt_active:
                self._ptt_active = False
                self._stop_ptt_recording()
                # Stop the space character from being inserted into the entry
                return "break"
            return None

        entry.bind("<KeyPress-space>", on_space_press)
        entry.bind("<KeyRelease-space>", on_space_release)

        def _on_paste(_e=None):
            handled = self._handle_pasted_image(status, entry)
            if handled:
                return "break"
            return None
        entry.bind("<Control-v>", _on_paste)
        entry.bind("<Control-V>", _on_paste)

        # F3.6 Drag & drop files onto the bubble
        # Skip TkinterDnD._require: it can hang the UI thread on some Windows setups.
        # Drop on the entry will still raise an error gracefully if DnD isn't initialized.
        try:
            from tkinterdnd2 import DND_FILES
            try:
                entry.drop_target_register(DND_FILES)
                entry.dnd_bind("<<Drop>>", lambda e: self._handle_dropped_file(e, status, entry))
            except Exception:
                pass
        except Exception:
            pass
        bub.bind("<Escape>", lambda _e: self.hide_bubble())

        # Use the WebView's actual physical footprint for positioning + overlap
        # checks (it's larger than BUBBLE_WIDTH x BUBBLE_HEIGHT on high-DPI
        # displays because pywebview renders CSS px at logical-pixel size).
        if self.webview_win is not None:
            web_logical_w, web_logical_h, cx, cy, chat_w, chat_h = self._webview_layout_for_panels()
        else:
            web_logical_w, web_logical_h = width, height
            chat_w = width
            chat_h = height
            cx, cy = self.bubble_position(chat_w, chat_h)

        # Collision avoidance: check if the pet overlaps with the chat bubble
        # and step aside to the left or right to remain fully visible!
        win_left = cx
        win_right = cx + chat_w
        win_top = cy
        win_bottom = cy + chat_h

        pet_left = self.base_x
        pet_right = self.base_x + self.width
        pet_top = self.base_y
        pet_bottom = self.base_y + self.height

        overlaps = (pet_left < win_right and pet_right > win_left and
                    pet_top < win_bottom and pet_bottom > win_top)

        if overlaps:
            # Save original position to restore later when chat closes
            if not hasattr(self, "_pre_chat_pet_x") or self._pre_chat_pet_x is None:
                self._pre_chat_pet_x = self.base_x
                self._pre_chat_pet_y = self.base_y
            
            # Determine which side has more space (left or right of the chat window)
            space_left = win_left - work_area.left
            space_right = work_area.right - win_right
            
            if space_left >= space_right:
                # Place pet to the left of the chat window
                new_pet_x = win_left - self.width - 12
            else:
                # Place pet to the right of the chat window
                new_pet_x = win_right + 12
                
            # Keep pet y near the bottom or at its current position, clamped
            new_pet_y = max(work_area.top, min(self.base_y, work_area.bottom - self.height))
            new_pet_x = max(work_area.left, min(new_pet_x, work_area.right - self.width))
            
            try:
                # Move the pet window!
                self.geometry(f"+{new_pet_x}+{new_pet_y}")
                self.base_x = new_pet_x
                self.base_y = new_pet_y
            except Exception:
                pass

        bub.geometry(f"{width}x{height}+{cx}+{cy}")
        try:
            self.lift()
            self.attributes("-topmost", True)
        except Exception:
            pass
        self.bubble_win = bub
        self._bubble_opened_at = time.time()
        self._reset_idle_timer()

        # Save submit function and entry reference for webview integration
        self._submit_fn = submit
        self._chat_entry_widget = entry
        self._status_widget = status

        # WebView redirection phase — only redirect if HTML is fully loaded
        if self.webview_win is not None and self._webview_ready:
            # Hide the native Tkinter window
            bub.withdraw()
            
            # Move the webview from off-screen to correct position
            # (window is always visible but parked at -9999,-9999 when "hidden")
            w_cx, w_cy = physical_to_webview(cx, cy)
            try:
                self.webview_win.resize(web_logical_w, web_logical_h)
                self.webview_win.move(w_cx, w_cy)
            except Exception as e:
                print(f"[webview show] error: {e}")
                # Fallback: show the tkinter window
                bub.deiconify()
                try:
                    bub.after(50, lambda: (bub.lift(), bub.focus_force(), entry.focus_set()))
                except Exception:
                    pass
                return

            self._webview_visible = True
            
            # Keep Claudy BELOW the webview while chat is open.
            # Topmost will be restored in hide_bubble() when chat closes.
            try:
                self.attributes("-topmost", False)
            except Exception:
                pass
            
            # Instanciate WebViewChatWrapper
            self._chat_view = WebViewChatWrapper(self)
            
            # Overrides for status
            status.original_configure = status.configure
            def _web_status_configure(text=None, fg=None, **kwargs):
                if text is not None:
                    self._eval_in_web(f"updateStatusText({json.dumps(text)})")
                    # Show speech bubble when chat is hidden and a background task is running
                    if not getattr(self, '_webview_visible', False) and text.strip():
                        try:
                            self.show_pet_speech_bubble(text, duration=5000)
                        except Exception:
                            pass
                try:
                    status.original_configure(text=text, **{k:v for k,v in kwargs.items() if k != 'fg'})
                except Exception:
                    pass
            status.configure = _web_status_configure
            status.config = _web_status_configure

            # Overrides for entry
            entry.original_delete = entry.delete
            def _web_entry_delete(first, last=None):
                self._eval_in_web("try { clearInputField(); } catch(e) {}")
                try:
                    entry.original_delete(first, last)
                except Exception:
                    pass
            entry.delete = _web_entry_delete

            entry.original_insert = entry.insert
            def _web_entry_insert(index, chars, *tags):
                self._eval_in_web(f"try {{ insertInputText({json.dumps(chars)}); }} catch(e) {{}}")
                try:
                    entry.original_insert(index, chars, *tags)
                except Exception:
                    pass
            entry.insert = _web_entry_insert

            def _web_entry_focus_set():
                self._eval_in_web("try { focusInputField(); } catch(e) {}")
                try:
                    entry.focus()
                except Exception:
                    pass
            entry.focus_set = _web_entry_focus_set

            entry.original_configure = entry.configure
            def _web_entry_configure(*args, **kwargs):
                pass
            entry.configure = _web_entry_configure
            entry.config = _web_entry_configure

            # NOTE: React loads history automatically via get_history() API on mount.
            # Only inject messages via Python when loading from an Obsidian buffer
            # (i.e. history imported from a previous session file).
            # Do NOT call add_system here — it would duplicate the React welcome message.
            if getattr(self, "_chat_history_buffer", None) is not None:
                self._chat_view.load_history(self._chat_history_buffer)
                self._chat_history_buffer = None
                
            self.after(100, lambda: self._eval_in_web("try { focusInputField(); } catch(e) {}"))
        else:
            # Foco automático en el input al abrir el chat — el usuario puede escribir directo
            try:
                bub.after(50, lambda: (bub.lift(), bub.focus_force(), entry.focus_set()))
            except Exception:
                pass

    def _normalize_existing_path(self, path):
        path = (path or "").strip().strip('"\'')
        if not path:
            return ""
        expanded = os.path.normpath(os.path.abspath(os.path.expanduser(path)))
        return expanded

    def _extract_artifact_path(self, text):
        text = str(text or "")
        marker = re.search(r"\[CLAUDY_PATH:(.+?)\]", text)
        if marker:
            candidate = marker.group(1).strip().strip('"\'')
            if candidate:
                return os.path.normpath(os.path.abspath(os.path.expanduser(candidate)))

        # Solo etiquetas que afirman EXPLÍCITAMENTE que se creó/actualizó un archivo.
        # (No "Ruta:"/"Archivo:"/"Ubicacion:" sueltas: aparecen también cuando Claudy
        #  ANALIZA o menciona un archivo existente y no debe mostrarse "archivo creado".)
        labels = ("Archivo creado:", "Archivo actualizado:")
        for line in text.splitlines():
            stripped = line.strip()
            for label in labels:
                if stripped.lower().startswith(label.lower()):
                    candidate = stripped[len(label):].strip()
                    if candidate:
                        normalized = os.path.normpath(os.path.abspath(os.path.expanduser(candidate)))
                        parent = os.path.dirname(normalized) if not os.path.isdir(normalized) else normalized
                        if os.path.exists(parent):
                            return normalized

        # Nota: NO se escanean rutas sueltas del texto. Una creación real SIEMPRE emite
        # el marcador [CLAUDY_PATH:...]; mencionar una ruta al analizar no es crear nada.
        return ""

    def _remember_file_artifact(self, path):
        if not path:
            return
        normalized = os.path.normpath(os.path.abspath(os.path.expanduser(path.strip().strip('"\''))))
        self._last_file_artifact_path = normalized
        self._set_open_location_button_state()

    def _set_open_location_button_state(self):
        btn = getattr(self, "_open_location_btn", None)
        if btn is None:
            return
        try:
            theme = getattr(self, "_dashboard_chat_theme", THEME)
            path = getattr(self, "_last_file_artifact_path", None)
            ready = bool(path)
            btn.configure(
                fg=theme["accent_glow"] if ready else theme["text_secondary"],
                bg=theme.get("button_bg", theme["bg_input"]),
                highlightbackground=theme["bg_input_border"],
                highlightthickness=1,
            )
        except tk.TclError:
            pass

    def _set_open_location_hover(self, active):
        btn = getattr(self, "_open_location_btn", None)
        if btn is None:
            return
        try:
            theme = getattr(self, "_dashboard_chat_theme", THEME)
            path = getattr(self, "_last_file_artifact_path", None)
            ready = bool(path)
            status = getattr(self, "_status_label", None)
            if active:
                if ready:
                    btn.configure(
                        fg=theme["accent_glow"],
                        bg=theme.get("button_hover", theme["bg_input"]),
                        highlightbackground=theme["accent"]
                    )
                    if status:
                        status.configure(text="Abrir ubicacion del ultimo reporte generado", fg=theme["accent_glow"])
                else:
                    btn.configure(
                        fg=theme["text_secondary"],
                        bg=theme.get("button_hover", theme["bg_input"]),
                        highlightbackground=theme["bg_input_border"]
                    )
                    if status:
                        status.configure(text="No hay reportes generados recientemente", fg="#ff6b6b")
            else:
                self._set_open_location_button_state()
                if status:
                    status.configure(text="Enter envia  |  Shift+Enter salto  |  Esc cierra  |  Espacio 2s habla", fg=theme["text_label"])
        except tk.TclError:
            pass

    def _open_path_location(self, path):
        if not path:
            return False, "Ruta vacía"
        normalized = os.path.normpath(os.path.abspath(os.path.expanduser(path.strip().strip('"\''))))
        # Ensure parent directory exists
        parent = os.path.dirname(normalized) if not os.path.isdir(normalized) else normalized
        if not os.path.exists(parent):
            parent = os.path.expanduser("~/Downloads")
            if not os.path.exists(parent):
                parent = os.getcwd()
        try:
            if os.path.isdir(normalized):
                os.startfile(normalized)
            else:
                try:
                    subprocess.run(
                        f'explorer /select,"{normalized}"',
                        shell=True, check=False,
                    )
                except Exception:
                    os.startfile(parent)
            # Ocultar el chat de Claudy para que se vea la carpeta del Explorador.
            try:
                self.after(120, self.hide_bubble)
            except Exception:
                pass
            return True, f"Ubicacion abierta: {normalized}"
        except Exception as e:
            return False, f"No pude abrir la ubicacion: {e}"

    def _open_path_file(self, path):
        """Open the file itself (not its folder)."""
        if not path:
            return
        normalized = os.path.normpath(os.path.abspath(os.path.expanduser(path.strip().strip('"\''))))
        try:
            os.startfile(normalized)
        except Exception:
            # Fallback: try opening its folder location if it is an unexecutable file type
            self._open_path_location(normalized)

    def _open_last_file_location(self):
        path = getattr(self, "_last_file_artifact_path", None)
        if not path:
            self._set_response_text("No hay archivo o carpeta reciente para abrir.")
            return
        ok, msg = self._open_path_location(path)
        if not ok:
            self._set_response_text(msg)

    def _set_response_text(self, text):
        """Push a response into the chat view (or fallback Text widget)."""
        # If Claudy is silently generating a report, NEVER write to chat
        if getattr(self, "_report_generating", False):
            # Only show lightweight bubble update when minimized
            if getattr(self, "bubble_minimized", False):
                clean_text = re.sub(r"\n?\[CLAUDY_PATH:.+?\]", "", str(text or "")).strip()
                if clean_text and len(clean_text) < 120:
                    self.show_pet_speech_bubble(clean_text, duration=None)
            return  # <-- block ALL chat writes during report generation

        if getattr(self, "bubble_minimized", False):
            clean_text = re.sub(r"\n?\[CLAUDY_PATH:.+?\]", "", str(text or "")).strip()
            artifact_path = self._extract_artifact_path(text)
            
            is_working = getattr(self, "_milestone_active", False)
            dur = None if is_working else 5000
            
            if artifact_path:
                clean_text = f"✨ ¡Terminado!\nHe creado:\n{os.path.basename(artifact_path)}"
                dur = 8000
            elif not clean_text:
                clean_text = "Trabajando..."
            self.show_pet_speech_bubble(clean_text, duration=dur)

        chat = getattr(self, "_chat_view", None)
        if chat is not None:
            try:
                chat.hide_typing()
            except Exception:
                pass
            artifact_path = self._extract_artifact_path(text)
            if artifact_path:
                self._remember_file_artifact(artifact_path)
            else:
                self._set_open_location_button_state()
            display_text = re.sub(r"\n?\[CLAUDY_PATH:.+?\]", "", str(text or "")).rstrip()
            if artifact_path:
                display_text = re.sub(
                    r"(?im)^\s*ubicaci[oó]n\s*:.*(?:\r?\n.*)?(?=\r?\n\S|\Z)",
                    "", display_text,
                ).strip()
            if artifact_path:
                chat.add_bot(f"¡Hemos terminado! Se ha creado el archivo:\n{os.path.basename(artifact_path)}")
                chat.add_file_card(
                    filename=os.path.basename(artifact_path),
                    on_open_file=lambda p=artifact_path: self._open_path_file(p),
                    on_open_folder=lambda p=artifact_path: self._open_path_location(p),
                    message="Haz clic en el nombre para abrir la carpeta",
                )
            elif display_text:
                is_system_status = len(display_text.splitlines()) == 1 and (
                    "buscando" in display_text.lower() or 
                    "instalando" in display_text.lower() or 
                    "descargando" in display_text.lower() or 
                    "ejecutando" in display_text.lower() or
                    "procesando" in display_text.lower() or
                    "abierta" in display_text.lower() or
                    "abierto" in display_text.lower()
                )
                if is_system_status:
                    chat.add_system(display_text)
                else:
                    chat.add_bot(display_text)
            return

        # Fallback legacy path.
        w = getattr(self, "_response_text_widget", None)
        artifact_path = self._extract_artifact_path(text)
        if artifact_path:
            self._remember_file_artifact(artifact_path)
        else:
            self._set_open_location_button_state()
        display_text = re.sub(r"\n?\[CLAUDY_PATH:.+?\]", "", str(text or "")).rstrip()
        if artifact_path:
            # Remove the "Ubicacion: ..." line — the icon below replaces it.
            display_text = re.sub(
                r"(?im)^\s*ubicaci[oó]n\s*:.*(?:\r?\n.*)?(?=\r?\n\S|\Z)",
                "",
                display_text,
            )
            display_text = re.sub(r"\n{3,}", "\n\n", display_text).rstrip()
        if w is None:
            return
        try:
            self._ensure_chat_tags(w)
            w.configure(state="normal")
            w.delete("1.0", "end")
            self._render_chat_content(w, display_text)
            if artifact_path:
                self._inject_open_location_link(w, artifact_path)
            w.configure(state="disabled")
            w.see("end")
        except tk.TclError:
            pass

    def show_pet_speech_bubble(self, text, duration=5000, on_click=None):
        """Show a premium floating speech bubble directly above the pet's head.

        If on_click is given, clicking the bubble runs it (e.g. reopen the chat
        to show the finished work).
        """
        if hasattr(self, "_pet_speech_win") and self._pet_speech_win:
            try:
                self._pet_speech_win.destroy()
            except Exception:
                pass
            self._pet_speech_win = None
            
        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        
        try:
            win.wm_attributes("-alpha", 0.0)
        except Exception:
            pass
            
        win.configure(bg=TRANSPARENT_COLOR)
        win.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        wraplength = 210
        temp = tk.Label(win, text=text, font=("Bahnschrift SemiBold", 9), wraplength=wraplength)
        temp.update_idletasks()
        bw = max(180, temp.winfo_reqwidth() + 34)
        bh = max(58, temp.winfo_reqheight() + 28)
        temp.destroy()

        canvas = tk.Canvas(win, width=bw, height=bh, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        try:
            img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            glow = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.rounded_rectangle((4, 4, bw - 5, bh - 5), radius=20,
                                 outline=(88, 199, 255, 145), width=4)
            gd.rounded_rectangle((8, 8, bw - 9, bh - 9), radius=18,
                                 outline=(192, 45, 255, 130), width=3)
            glow = glow.filter(ImageFilter.GaussianBlur(7))
            img = Image.alpha_composite(img, glow)
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((8, 8, bw - 9, bh - 9), radius=18,
                                fill=(5, 9, 29, 246), outline=(88, 199, 255, 180), width=1)
            d.polygon([(bw // 2 - 9, bh - 10), (bw // 2, bh - 1), (bw // 2 + 9, bh - 10)],
                      fill=(5, 9, 29, 246), outline=(88, 199, 255, 130))
            # Pre-composite onto magenta background so semi-transparent pixels
            # don't bleed pink through Tkinter's -transparentcolor.
            bg_layer = Image.new("RGBA", (bw, bh), (255, 0, 255, 255))
            composited = Image.alpha_composite(bg_layer, img)
            final = composited.convert("RGB")
            # Snap near-magenta pixels to exact #FF00FF so chroma-key works
            px = final.load()
            for _y in range(final.height):
                for _x in range(final.width):
                    r, g, b = px[_x, _y]
                    if r > 200 and g < 55 and b > 200:
                        px[_x, _y] = (255, 0, 255)
            tk_img = ImageTk.PhotoImage(final)
            win._speech_bg_ref = tk_img
            canvas.create_image(0, 0, anchor="nw", image=tk_img)
        except Exception:
            canvas.create_rectangle(0, 0, bw, bh, fill="#05091d", outline="#58c7ff", width=1)

        canvas.create_text(
            bw // 2, bh // 2 - 2,
            text=text,
            width=wraplength,
            fill="#f7f9ff",
            font=("Bahnschrift SemiBold", 9),
            justify="center",
        )
        
        win.update_idletasks()
        
        px = self.winfo_x()
        py = self.winfo_y()
        pw = self.winfo_width()
        
        cx = px + pw // 2
        bx = cx - bw // 2
        by = py - bh - 10
        
        win.geometry(f"{bw}x{bh}+{bx}+{by}")
        self._pet_speech_win = win

        # Click en la burbuja → ejecuta el callback (p.ej. reabrir el chat).
        if on_click is not None:
            def _do_click(_e=None):
                try:
                    win.destroy()
                except Exception:
                    pass
                if getattr(self, "_pet_speech_win", None) == win:
                    self._pet_speech_win = None
                try:
                    on_click()
                except Exception:
                    pass
            canvas.configure(cursor="hand2")
            canvas.bind("<Button-1>", _do_click)

        def fade_in(alpha=0.0, current_y=by+10):
            if not win.winfo_exists():
                return
            if alpha < 1.0:
                alpha += 0.15
                current_y -= 1.5
                win.attributes("-alpha", min(1.0, alpha))
                win.geometry(f"+{bx}+{int(current_y)}")
                self.after(20, lambda: fade_in(alpha, current_y))
            else:
                win.attributes("-alpha", 1.0)
                win.geometry(f"+{bx}+{by}")
                if duration is not None:
                    self.after(duration, lambda: fade_out())
                
        def fade_out(alpha=1.0):
            if not win.winfo_exists():
                return
            if alpha > 0.0:
                alpha -= 0.15
                win.attributes("-alpha", max(0.0, alpha))
                self.after(20, lambda: fade_out(alpha))
            else:
                try:
                    win.destroy()
                except Exception:
                    pass
                if getattr(self, "_pet_speech_win", None) == win:
                    self._pet_speech_win = None
                    
                # If minimized and no longer working, restore Zzz sleep visual elements
                if getattr(self, "bubble_minimized", False) and not getattr(self, "_milestone_active", False):
                    canvas = getattr(self, "_canvas", None)
                    idle_items = getattr(self, "_idle_items", None)
                    if canvas and idle_items:
                        for item in idle_items:
                            try:
                                canvas.itemconfigure(item, state="normal")
                            except Exception:
                                pass
                        self._start_zzz_animation()
                    
        fade_in()

    def _format_exchange(self, user_text, bot_text):
        """Build marker-tagged exchange. Prefers DB history if available, else inline."""
        preview = self._get_last_chat_preview(n=6, max_len=400)
        if preview and "[[" in preview:
            return preview
        parts = []
        if user_text:
            parts.append(f"[[USER]]{user_text.strip()}")
        if bot_text:
            parts.append(f"[[CLAUDY]]{bot_text.strip()}")
        return "\n".join(parts)

    def _ensure_chat_tags(self, w):
        """Configure styled tags for the chat text widget (idempotent)."""
        if getattr(w, "_claudy_chat_tags_ready", False) and getattr(w, "_claudy_chat_theme_key", None) == _THEME_KEYS[_active_theme_idx]:
            return
        bg = THEME.get("bg_bubble", "#0e0e1a")
        bg_border = THEME.get("bg_bubble_border", "#3b3b5c")
        bg_input = THEME.get("bg_input", "#15152a")
        accent = THEME.get("accent", "#8b7dff")
        accent_glow = THEME.get("accent_glow", "#ff8de8")
        accent_dim = THEME.get("accent_dim", "#5448a8")
        text_primary = THEME.get("text_primary", "#f2f2ff")
        text_secondary = THEME.get("text_secondary", "#9b9bb8")
        text_label = THEME.get("text_label", "#6c6c8a")
        divider = THEME.get("divider", "#22223a")

        w.configure(bg=bg, fg=text_primary, spacing1=2, spacing2=2, spacing3=4)

        # USER bubble — right-aligned, accent surface.
        w.tag_configure(
            "user_msg",
            background=bg_input, foreground=text_primary,
            lmargin1=60, lmargin2=60, rmargin=10,
            spacing1=4, spacing3=6, wrap="word",
            font=("Segoe UI", 10),
            relief="flat", borderwidth=0,
            justify="right",
        )
        w.tag_configure(
            "user_badge",
            background=accent, foreground="#ffffff",
            lmargin1=60, lmargin2=60, rmargin=10,
            font=("Segoe UI", 8, "bold"),
            spacing1=8, spacing3=2,
            justify="right",
        )
        # CLAUDY bubble — left-aligned, secondary surface.
        w.tag_configure(
            "bot_msg",
            background=bg_border, foreground=text_primary,
            lmargin1=10, lmargin2=10, rmargin=60,
            spacing1=4, spacing3=6, wrap="word",
            font=("Segoe UI", 10),
            relief="flat", borderwidth=0,
        )
        w.tag_configure(
            "bot_badge",
            background=accent_dim, foreground=accent_glow,
            lmargin1=10, lmargin2=10, rmargin=60,
            font=("Segoe UI", 8, "bold"),
            spacing1=8, spacing3=2,
        )
        # System / plain note (status updates, single messages).
        w.tag_configure(
            "sys_msg",
            foreground=text_secondary,
            lmargin1=14, lmargin2=14, rmargin=14,
            spacing1=4, spacing3=4, wrap="word",
            font=("Segoe UI", 10),
        )
        # Inline markdown tags.
        w.tag_configure("md_bold", font=("Segoe UI", 10, "bold"), foreground=accent_glow)
        w.tag_configure("md_code", background=bg, foreground=accent, font=("Cascadia Mono", 9))
        w.tag_configure(
            "md_codeblock",
            background=bg, foreground=text_primary,
            font=("Cascadia Mono", 9),
            lmargin1=18, lmargin2=18, rmargin=18,
            spacing1=4, spacing3=4, wrap="none",
        )
        w.tag_configure("md_bullet", foreground=accent, font=("Segoe UI", 10, "bold"))
        w.tag_configure("divider", foreground=divider, font=("Segoe UI", 6))
        w.tag_configure("timestamp", foreground=text_label, font=("Segoe UI", 7), justify="right")

        w._claudy_chat_tags_ready = True
        w._claudy_chat_theme_key = _THEME_KEYS[_active_theme_idx]

    def _render_chat_content(self, w, text):
        """Parse [[USER]]/[[CLAUDY]] markers and render styled bubbles.

        Plain text (no markers) is rendered as a system note.
        """
        text = (text or "").strip()
        if not text:
            return
        # Split on role markers while keeping them.
        parts = re.split(r"(\[\[USER\]\]|\[\[CLAUDY\]\])", text)
        # If no markers found -> plain system message.
        if not any(p in ("[[USER]]", "[[CLAUDY]]") for p in parts):
            self._render_md_block(w, text, "sys_msg")
            return

        # Walk marker/content pairs.
        i = 0
        first = True
        while i < len(parts):
            token = parts[i].strip()
            if token in ("[[USER]]", "[[CLAUDY]]"):
                body = parts[i + 1] if i + 1 < len(parts) else ""
                body = body.strip()
                i += 2
                if not body:
                    continue
                if not first:
                    w.insert("end", "\n", "divider")
                first = False
                if token == "[[USER]]":
                    w.insert("end", "  Tu  ", "user_badge")
                    w.insert("end", "\n", "user_badge")
                    self._render_md_block(w, body, "user_msg")
                else:
                    w.insert("end", "  ✦ Claudy  ", "bot_badge")
                    w.insert("end", "\n", "bot_badge")
                    self._render_md_block(w, body, "bot_msg")
                w.insert("end", "\n")
            else:
                # Stray text before first marker — treat as system.
                stray = parts[i].strip()
                if stray:
                    self._render_md_block(w, stray, "sys_msg")
                    w.insert("end", "\n")
                i += 1

    def _render_md_block(self, w, text, base_tag):
        """Render a single block applying lightweight markdown (bold, code, bullets, fences)."""
        # Code fences ```...```
        segments = re.split(r"```([\s\S]*?)```", text)
        for idx, seg in enumerate(segments):
            if idx % 2 == 1:
                code = seg.strip("\n")
                w.insert("end", code + "\n", ("md_codeblock",))
                continue
            for line in seg.split("\n"):
                bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
                if bullet:
                    w.insert("end", "  • ", ("md_bullet", base_tag))
                    self._render_md_inline(w, bullet.group(1), base_tag)
                else:
                    self._render_md_inline(w, line, base_tag)
                w.insert("end", "\n", (base_tag,))

    def _render_md_inline(self, w, text, base_tag):
        """Apply inline markdown: **bold** and `code`."""
        # Tokenize: alternating plain / **bold** / `code`
        pattern = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")
        pos = 0
        for m in pattern.finditer(text):
            if m.start() > pos:
                w.insert("end", text[pos:m.start()], (base_tag,))
            token = m.group(0)
            if token.startswith("**"):
                w.insert("end", token[2:-2], ("md_bold", base_tag))
            else:
                w.insert("end", token[1:-1], ("md_code", base_tag))
            pos = m.end()
        if pos < len(text):
            w.insert("end", text[pos:], (base_tag,))

    def _inject_open_location_link(self, w, path):
        """Append a beautiful clickable shortcut link/button to open the file's location."""
        try:
            tag = "open_loc_link"
            if tag not in w.tag_names():
                w.tag_configure(
                    tag,
                    foreground=THEME.get("accent", "#7c6bff"),
                    font=("Segoe UI", 9, "bold underline"),
                )
                w.tag_bind(tag, "<Enter>", lambda _e: w.configure(cursor="hand2"))
                w.tag_bind(tag, "<Leave>", lambda _e: w.configure(cursor=""))
            w.tag_bind(tag, "<Button-1>", lambda _e, p=path: self._open_path_location(p))
            
            # Insert a divider line followed by a beautiful, clear shortcut link
            w.insert("end", "\n\n───────────────────\n")
            w.insert("end", "📂 [Abrir ubicación del archivo]", tag)
            w.insert("end", "\n")
        except tk.TclError:
            pass

    def _append_response_text(self, text):
        """Append text to the scrollable response area (for live progress)."""
        chat = getattr(self, "_chat_view", None)
        if chat is not None:
            t = (text or "").strip()
            if t:
                chat.add_system(t)
            return
        w = getattr(self, "_response_text_widget", None)
        if w is None:
            return
        try:
            w.configure(state="normal")
            w.insert("end", text)
            w.configure(state="disabled")
            w.see("end")
        except tk.TclError:
            pass

    def _update_progress(self, msg):
        """Thread-safe: update response text with a progress message."""
        self.after(0, lambda: self._set_response_text(msg))

    def _append_progress(self, msg):
        """Thread-safe: append a line to response text."""
        self.after(0, lambda: self._append_response_text("\n" + msg))

    def _draw_round_rect(self, canvas, x1, y1, x2, y2, radius, **kwargs):
        pts = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return canvas.create_polygon(pts, smooth=True, **kwargs)

    # ------------------------------------------------------------------
    # Quick Ask logic (OpenCode)
    # ------------------------------------------------------------------
    def ask_claudy(self, prompt, status, entry):
        thinking = random.choice([
            "Consultando al oráculo...", "Conectando neuronas...", "Hablando con las estrellas...",
            "Corriendo a toda máquina...", "Esforzándome al máximo...",
        ])
        status.configure(text=thinking)
        self._last_prompt = prompt  # Guardar para fallback de acciones
        # Push user bubble + typing indicator immediately if not already added by submit()
        chat = getattr(self, "_chat_view", None)
        if chat is not None:
            try:
                has_prompt = False
                if chat._messages:
                    last = chat._messages[-1]
                    if last.get("role") == "user" and last.get("text") == prompt:
                        has_prompt = True
                if not has_prompt:
                    chat.clear()
                    chat.add_user(prompt)
                    chat.show_typing()
            except Exception:
                pass

        # Mensajes en cursiva dentro del input mientras procesa
        self._start_typing_progress(entry, prompt)

        # Hitos de progreso en la burbuja (mismas frases que Telegram)
        self._start_milestone_progress()

        def worker():
            self._streamed = False
            chat_v = getattr(self, "_chat_view", None)
            on_delta = None
            if getattr(self, "_streaming_enabled", False) and chat_v is not None:
                state = {"started": False, "buf": "", "last": 0.0}

                def on_delta(piece):
                    state["buf"] += piece
                    if not state["started"]:
                        state["started"] = True
                        self._streamed = True
                        self.after(0, chat_v.begin_stream)
                    now = time.time()
                    if now - state["last"] >= 0.05:
                        state["last"] = now
                        try:
                            shown = self._strip_markdown(state["buf"])
                        except Exception:
                            shown = state["buf"]
                        self.after(0, lambda b=shown: chat_v.update_stream(b))

            try:
                answer = self.send_quick_message(prompt, on_delta=on_delta)
            except Exception as error:
                answer = f"Mmm... algo falló en mi cabecita: {error}"
            self._stop_milestone_progress()
            streamed = getattr(self, "_streamed", False)
            self._streamed = False
            if streamed and chat_v is not None:
                try:
                    clean = self._strip_markdown(answer)
                except Exception:
                    clean = answer
                self.after(0, lambda: chat_v.end_stream(clean))
                self.after(0, lambda: self.finish_quick_answer(answer, status, entry, _already_shown=True))
            else:
                self.after(0, lambda: self.finish_quick_answer(answer, status, entry))

        threading.Thread(target=worker, daemon=True).start()

    # ============================================================
    # Mission Control — sembrar borrador de correo en el Inbox
    # ============================================================
    # Contactos conocidos: destinatario, copia y marca a usar.
    _MC_KNOWN_CONTACTS = {
        "combas": {
            "name": "Conservatorio COMBAS",
            "aliases": ["combas", "conservatorio"],
            "to": ["secretaria@combas.cl"],
            "cc": ["jeanpaul.harb@combas.cl"],
            "brand": "smartstudent",
        },
        "tentacion": {
            "name": "Tentación a Granel",
            "aliases": ["tentacion", "tentación", "granel", "marco", "gonzalez", "gonzález"],
            "to": ["agraneltentacion@gmail.com"],
            "cc": [],
            "brand": "point",
        },
    }
    # Marcas disponibles para el remitente y el estilo del correo.
    _MC_BRANDS = {
        "smartstudent": {
            "label": "SmartStudent (educativo)",
            "template": "smartstudent",
            "from": "SmartStudent <smartstudentweb@gmail.com>",
            "replyTo": "jorge.castro@qcorespa.com",
            "productId": "smartstudent",
            "primary": "#2563eb",
            "signature": "Equipo SmartStudent · www.smartstudent.cl",
            "guidance": "Marca SmartStudent (plataforma educativa SaaS). Tono cercano, claro y profesional, en español de Chile.",
        },
        "point": {
            "label": "Point (POS / comercio)",
            "template": "point",
            "from": "QCORE SPA <jorge.castro@qcorespa.com>",
            "replyTo": "jorge.castro@qcorespa.com",
            "productId": "",
            "primary": "#D81B60",
            "signature": "Equipo Point · QCORE SPA",
            "guidance": "Marca Point (sistema POS con control de inventario FEFO para comercios). Tono cercano, claro y práctico, orientado al dueño del negocio, en español de Chile.",
        },
        "qcore": {
            "label": "QCORE SPA (corporativo)",
            "from": "QCORE SPA <jorge.castro@qcorespa.com>",
            "replyTo": "jorge.castro@qcorespa.com",
            "productId": "",
            "primary": "#6c5ce7",
            "signature": "QCORE SPA · jorge.castro@qcorespa.com",
            "guidance": "Marca QCORE SPA (consultora tecnológica). Tono profesional corporativo, en español de Chile.",
        },
    }
    _MC_SEEDED_DRAFTS_PATH = r"C:\Users\Felipe\Documents\QCORE-LOCAL\MISSION-CONTROL\logs\seeded-drafts.json"

    # Dónde queda el correo dentro del Inbox de Mission Control (kind + origin).
    _MC_DRAFT_KINDS = {
        "1": ("general-reply",          "direct-email",  "Respuesta general",            "Borrador general que queda en la bandeja de pendientes del Inbox"),
        "2": ("implementation-follow-up","direct-email", "Seguimiento de implementación", "Para avisar avances / configuraciones aplicadas en la plataforma"),
        "3": ("meeting-reply",          "direct-email",  "Coordinación de reunión",       "Para agendar o confirmar una reunión o demo"),
        "4": ("receipt-confirmation",   "direct-email",  "Confirmación / recibo",         "Confirmaciones de recepción, pago o entrega"),
        "5": ("website-reply",          "website-lead",  "Respuesta a lead web",          "Respuesta a un contacto entrante desde el sitio web"),
    }

    def _try_seed_mc_draft(self, prompt, plow, status, entry=None):
        """Detecta pedidos de 'crear correo borrador' y lanza el flujo guiado que
        pregunta destinatario, ubicación en Mission Control y estilo antes de
        sembrarlo en el Inbox (logs/seeded-drafts.json). Devuelve True si tomó el pedido."""
        create_verbs = (
            "crea", "créa", "crear", "haz", "hazme", "redacta", "redáctame",
            "prepara", "prepárame", "genera", "escribe", "escríbeme", "arma", "ármame",
            "quiero", "necesito", "dame",
        )
        has_create = any(v in plow for v in create_verbs)
        mentions_draft = "borrador" in plow
        mentions_mail = any(w in plow for w in ("correo", "email", "e-mail", "mail"))
        mentions_mc = any(w in plow for w in ("mission control", "inbox", "casilla", "bandeja"))

        # Un borrador de correo SIEMPRE es para Mission Control. Señal fuerte:
        # "borrador" junto a correo/MC dispara aunque no haya verbo de creación.
        strong = mentions_draft and (mentions_mail or mentions_mc)
        if not (strong or (has_create and (mentions_mail or mentions_draft))):
            return False

        self._start_guided_email_flow(prompt, plow, status, entry)
        return True

    # ============================================================
    # Guided Email Flow (Asistente de Correos para Mission Control)
    # ============================================================
    def _detect_email_style(self, plow):
        """Detecta la marca/estilo mencionada en el texto. Devuelve la clave o None."""
        if "smart" in plow:
            return "smartstudent"
        if "point" in plow or " pos" in plow:
            return "point"
        if "qcore" in plow or "corporativo" in plow:
            return "qcore"
        return None

    def _extract_email_topic(self, prompt, plow):
        """Quita el 'andamiaje' (verbos, 'correo/borrador', destinatario, estilo, MC) y
        devuelve el tema restante. Sirve para decidir si hay contenido suficiente."""
        import re as _re
        t = " " + (prompt or "") + " "
        t = _re.sub(r'\b(crea|créa|crear|haz|hazme|redacta|redáctame|prepara|prepárame|genera|escribe|escríbeme|arma|ármame|quiero|necesito|dame)\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\b(un|una|el|la|los|las|de|del)\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\b(correo|email|e-mail|mail|borrador|mensaje)\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\bestilo\s+\w+\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\b(smartstudent|point|qcore|pos|corporativo)\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\b(mission\s+control|misi[oó]n\s+control|inbox|casilla|bandeja)\b', ' ', t, flags=_re.I)
        for c in self._MC_KNOWN_CONTACTS.values():
            for a in c.get("aliases", []):
                t = _re.sub(r'\b' + _re.escape(a) + r'\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\b(a\s+granel)\b', ' ', t, flags=_re.I)
        t = _re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', ' ', t)  # emails
        # conectores colgantes al inicio
        t = _re.sub(r'^\s*(para|a|que\s+sea|y\s+que\s+sea|y\s+que|que|sobre|avisando\s+que|avisando|diciendo\s+que|informando\s+que|informando|enviando)\s+', ' ', t, flags=_re.I)
        t = _re.sub(r'\s+', ' ', t).strip(" ,.;:-")
        return t

    def _start_guided_email_flow(self, prompt, plow, status, entry):
        # Detectar contacto conocido para ofrecerlo primero (sin auto-seleccionarlo).
        detected_key = None
        for key, c in self._MC_KNOWN_CONTACTS.items():
            if any(a in plow for a in c.get("aliases", [key])):
                detected_key = key
                break

        # ── ONE-SHOT: si ya hay destinatario + tema claro, saltamos las preguntas ──
        topic = self._extract_email_topic(prompt, plow)
        detected_style = self._detect_email_style(plow)
        if detected_key and topic and len(topic.split()) >= 3:
            c = self._MC_KNOWN_CONTACTS[detected_key]
            brand_key = detected_style or c.get("brand", "qcore")
            self._guided_email_active = False
            self._guided_email_step = 0
            self._guided_email_data = {
                "prompt": prompt,
                "content": prompt,  # el LLM se enfoca en el pedido real
                "recipient_name": c["name"],
                "contact_key": detected_key,
                "to_list": list(c.get("to", [])),
                "cc_list": list(c.get("cc", [])),
                "kind": "general-reply",
                "origin": "direct-email",
                "brand_key": brand_key,
            }
            chat = getattr(self, "_chat_view", None)
            if chat is not None:
                try:
                    last = chat._messages[-1] if getattr(chat, "_messages", None) else None
                    if not (last and last.get("role") == "user" and last.get("text") == prompt):
                        chat.add_user(prompt)
                except Exception:
                    pass
            self._finalize_and_seed_email(self._guided_email_data, status)
            return

        self._guided_email_active = True
        self._guided_email_step = 1
        self._guided_email_data = {
            "prompt": prompt,
            "content": None,
            "recipient_name": None,
            "contact_key": None,
            "to_list": [],
            "cc_list": [],
            "kind": "general-reply",
            "origin": "direct-email",
            "brand_key": "qcore",
            "style_label": None,
        }
        self._bubble_status = status
        self._bubble_entry = entry

        chat = getattr(self, "_chat_view", None)
        if chat is not None:
            try:
                last = chat._messages[-1] if getattr(chat, "_messages", None) else None
                if not (last and last.get("role") == "user" and last.get("text") == prompt):
                    chat.add_user(prompt)
            except Exception:
                pass
            chat.add_bot(
                "Vamos a preparar el borrador para el **Inbox de Mission Control**.\n\n"
                "**Pregunta 1/3: ¿A quién va dirigido el correo?**"
            )
            options = []
            for key, c in self._MC_KNOWN_CONTACTS.items():
                dest = ", ".join(c.get("to", [])) or "sin destinatario"
                label = f"{c['name']}" + (" ⭐" if key == detected_key else "")
                options.append((f"contact:{key}", label, dest))
            options.append(("otro", "Otro cliente / destinatario", "Escribe el correo del nuevo cliente o destinatario a continuación"))
            chat.add_options(options, self._handle_email_option_select)

        try:
            status.configure(text="Correo · Paso 1: Destinatario", fg=THEME["accent"])
        except Exception:
            pass
        if entry is not None:
            try:
                entry.configure(state="normal")
                entry.focus_set()
            except Exception:
                pass

    def _handle_email_option_select(self, option_value):
        status = getattr(self, "_bubble_status", None)
        entry = getattr(self, "_bubble_entry", None)
        self._handle_guided_email_step(option_value, status, entry)

    def _ask_email_content(self, chat, status):
        self._guided_email_step = 15
        chat.add_bot("**Pregunta 2/3: ¿De qué se trata el correo?** (escríbelo con tus palabras)")
        try:
            status.configure(text="Correo · Paso 2: Contenido", fg=THEME["accent"])
        except Exception:
            pass

    def _ask_email_style(self, chat, status):
        self._guided_email_step = 4
        chat.add_bot("**Pregunta 3/3: ¿Qué estilo / marca usamos para redactar?**")
        descs = {
            "smartstudent": "Plataforma educativa. Tono cercano y profesional (plantilla SmartStudent, azul)",
            "point": "POS / comercio. Tono cercano y práctico para el dueño del negocio (rosado Point)",
            "qcore": "Consultora tecnológica. Tono profesional corporativo (morado QCORE)",
        }
        suggested = self._guided_email_data.get("brand_key", "qcore")
        order = [suggested] + [k for k in ("smartstudent", "point", "qcore") if k != suggested]
        options = []
        for k in order:
            b = self._MC_BRANDS.get(k)
            if not b:
                continue
            label = b.get("label", k)
            if k == suggested:
                label += " ⭐"
            options.append((k, label, descs.get(k, "")))
        chat.add_options(options, self._handle_email_option_select)
        try:
            status.configure(text="Correo · Paso 3: Estilo", fg=THEME["accent"])
        except Exception:
            pass

    def _handle_guided_email_step(self, prompt, status, entry):
        chat = getattr(self, "_chat_view", None)
        if chat is None:
            return
        data = self._guided_email_data
        step = self._guided_email_step
        plow = (prompt or "").lower().strip()

        if step == 1:
            # Elegir destinatario.
            if prompt.startswith("contact:"):
                key = prompt.split(":", 1)[1]
                c = self._MC_KNOWN_CONTACTS.get(key)
                if c:
                    data["recipient_name"] = c["name"]
                    data["contact_key"] = key
                    data["to_list"] = list(c.get("to", []))
                    data["cc_list"] = list(c.get("cc", []))
                    data["brand_key"] = c.get("brand", "qcore")
                    chat.add_user(c["name"])
                    self._ask_email_content(chat, status)
                    return
            if prompt == "otro" or plow == "otro":
                self._guided_email_step = 2
                chat.add_bot("Escribe el **correo (o nombre)** del destinatario:")
                try:
                    status.configure(text="Correo · Destinatario personalizado", fg=THEME["accent"])
                except Exception:
                    pass
                return
            # Si escribió algo libre, intentar resolver contacto conocido o usarlo como destinatario.
            matched = None
            for key, c in self._MC_KNOWN_CONTACTS.items():
                if any(a in plow for a in c.get("aliases", [key])):
                    matched = (key, c)
                    break
            if matched:
                key, c = matched
                data["recipient_name"] = c["name"]
                data["contact_key"] = key
                data["to_list"] = list(c.get("to", []))
                data["cc_list"] = list(c.get("cc", []))
                data["brand_key"] = c.get("brand", "qcore")
                chat.add_user(c["name"])
            else:
                self._set_custom_recipient(data, prompt)
                chat.add_user(prompt)
            self._ask_email_content(chat, status)
            return

        if step == 2:
            # Destinatario personalizado escrito por el usuario.
            self._set_custom_recipient(data, prompt)
            chat.add_user(prompt)
            self._ask_email_content(chat, status)
            return

        if step == 15:
            # Contenido / tema del correo.
            content = (prompt or "").strip()
            data["content"] = content
            chat.add_user(content if len(content) <= 120 else content[:117] + "…")
            self._ask_email_style(chat, status)
            return

        if step == 4:
            # Estilo / marca.
            if prompt in self._MC_BRANDS:
                brand_key = prompt
            elif "smart" in plow:
                brand_key = "smartstudent"
            elif "point" in plow or "pos" in plow:
                brand_key = "point"
            elif "qcore" in plow or "corporativo" in plow:
                brand_key = "qcore"
            else:
                brand_key = data.get("brand_key", "qcore")
            data["brand_key"] = brand_key
            data["style_label"] = self._MC_BRANDS.get(brand_key, self._MC_BRANDS["qcore"]).get("label", brand_key)
            chat.add_user(data["style_label"])
            self._finalize_and_seed_email(data, status)
            return

    def _finalize_and_seed_email(self, data, status):
        """Cierra el flujo y dispara la redacción/siembra del borrador en el Inbox de MC.
        Los borradores SIEMPRE quedan en el Inbox (kind general-reply / origin direct-email)."""
        chat = getattr(self, "_chat_view", None)
        self._guided_email_active = False
        self._guided_email_step = 0
        brand_key = data.get("brand_key", "qcore")
        brand = self._MC_BRANDS.get(brand_key, self._MC_BRANDS["qcore"])
        data["style_label"] = brand.get("label", brand_key)
        dest = ", ".join(data.get("to_list") or []) or "(sin destinatario — complétalo en el Inbox)"
        if chat:
            chat.add_bot(
                "Listo, tengo todo. Redactando el borrador para el **Inbox de Mission Control**…\n\n"
                f"**Para:** {dest}\n"
                f"**Estilo:** {data.get('style_label')}"
            )
            chat.show_typing()
        try:
            status.configure(text="Redactando borrador para Mission Control...", fg="#58c7ff")
        except Exception:
            pass
        brief = data.get("content") or data.get("prompt") or ""
        threading.Thread(
            target=self._seed_mc_draft_worker,
            args=(brief, data.get("recipient_name") or "destinatario",
                  data.get("contact_key") or "contacto", brand,
                  list(data.get("to_list") or []), list(data.get("cc_list") or []), status,
                  data.get("kind", "general-reply"), data.get("origin", "direct-email"),
                  data.get("custom_reference")),
            daemon=True,
        ).start()

    def _set_custom_recipient(self, data, text):
        import re as _re
        emails = _re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text or "")
        if emails:
            data["to_list"] = emails
            data["recipient_name"] = emails[0].split("@")[0]
        else:
            data["to_list"] = []
            data["recipient_name"] = (text or "").strip() or "destinatario"
        data["cc_list"] = []
        data["contact_key"] = _re.sub(r"[^a-z0-9]+", "-", (data["recipient_name"] or "contacto").lower()).strip("-") or "contacto"

    # ============================================================
    # Mi Portafolio — edición directa de archivos locales del proyecto
    # ============================================================
    _PORTFOLIO_PATH = r"C:\Users\Felipe\Documents\CV_JorgeCastro_v3.5"
    _PORTFOLIO_EXTS = (".html", ".css", ".js", ".md")
    _PORTFOLIO_EDIT_VERBS = (
        "cambia", "cámbia", "cambiale", "cámbiale", "modifica", "edita", "edíta",
        "agrega", "añade", "anade", "quita", "elimina", "borra", "actualiza",
        "pon", "ponle", "reemplaza", "arregla", "ajusta", "corrige", "mejora",
        "saca", "renombra", "traduce",
    )

    def _try_edit_portfolio(self, prompt, plow, status, entry=None):
        """Si el portafolio está activo (o se menciona) y se pide un cambio, edita
        directamente los archivos locales del proyecto. Devuelve True si lo tomó."""
        is_portfolio = (
            getattr(self, "_portfolio_mode", False)
            or getattr(self, "_active_product", "") == "Mi Portafolio"
            or "portafolio" in plow or "portfolio" in plow
        )
        has_edit = any(v in plow for v in self._PORTFOLIO_EDIT_VERBS)
        if not (is_portfolio and has_edit):
            return False
        if not os.path.isdir(self._PORTFOLIO_PATH):
            return False
        chat = getattr(self, "_chat_view", None)
        if chat:
            try:
                last = chat._messages[-1] if getattr(chat, "_messages", None) else None
                if not (last and last.get("role") == "user" and last.get("text") == prompt):
                    chat.add_user(prompt)
                chat.show_typing()
            except Exception:
                pass
        try:
            status.configure(text="Editando el portafolio...", fg="#58c7ff")
        except Exception:
            pass
        threading.Thread(
            target=self._edit_portfolio_worker, args=(prompt, status), daemon=True
        ).start()
        return True

    def _portfolio_text_files(self):
        """Lista de archivos editables (rel paths) dentro del portafolio."""
        path = self._PORTFOLIO_PATH
        files = []
        for root, dirs, fnames in os.walk(path):
            dirs[:] = [d for d in dirs if d not in ("backups", "__pycache__", ".git", "node_modules")]
            for fn in fnames:
                if fn.lower().endswith(self._PORTFOLIO_EXTS):
                    files.append(os.path.relpath(os.path.join(root, fn), path))
        return sorted(files)

    def _edit_portfolio_worker(self, instruction, status):
        import datetime as _dt
        import shutil as _shutil
        import re as _re
        path = self._PORTFOLIO_PATH
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backups = os.path.join(path, "backups")

        def _say(msg, ok=True, system=False):
            def _f():
                ch = getattr(self, "_chat_view", None)
                if ch:
                    ch.hide_typing()
                    (ch.add_system if system else ch.add_bot)(msg)
                try:
                    status.configure(text=("Portafolio actualizado" if ok else "No se pudo editar"),
                                     fg=("#00ff99" if ok else "#ff5555"))
                except Exception:
                    pass
            self.after(0, _f)

        try:
            files = self._portfolio_text_files()
            if not files:
                _say("❌ No encontré archivos editables en el portafolio.", ok=False, system=True)
                return

            roles = {
                "index.html": "Home (hero, perfil, stack, showcase)",
                "experience.html": "Experiencia", "education.html": "Educación",
                "certifications.html": "Certificaciones", "portfolio.html": "Proyectos",
                "about.html": "Sobre mí / contacto", "styles.css": "Estilos / colores / diseño",
                "app.js": "Lógica: i18n, tema, navegación",
            }
            listing = "\n".join(f"- {f}" + (f" — {roles[f]}" if f in roles else "") for f in files)

            # ── Paso 1: pedir reemplazos LITERALES (ideal para nombres/textos repetidos
            #    en varias páginas: nav, hero, footer, etc.) ──
            rep_prompt = (
                "Eres editor de un sitio web estático (portafolio personal de Jorge Castro Segura). "
                "Genera reemplazos de texto LITERALES que se aplicarán en TODOS los archivos para lograr el cambio.\n"
                f"Cambio pedido: \"{instruction}\".\n"
                "Archivos del sitio:\n" + listing + "\n\n"
                "Devuelve SOLO JSON con esta forma:\n"
                "{\"replacements\":[{\"find\":\"texto EXACTO que está hoy en el sitio\",\"replace\":\"texto nuevo\"}], "
                "\"structural\": false, \"file\": \"\"}\n"
                "Reglas: usa cadenas exactas tal como aparecen (respeta mayúsculas/acentos). "
                "Para cambios de NOMBRE incluye TODAS las variantes (nombre completo, nombre+apellido, solo nombre, en mayúsculas si aplica). "
                "Si el cambio NO se puede hacer con find/replace (agregar/quitar secciones, cambiar diseño/color sin saber el valor), "
                "deja \"replacements\":[] , pon \"structural\": true y el archivo más probable en \"file\"."
            )
            data = self._extract_json(self._llm_structured(rep_prompt, expect_json=True)) or {}
            reps = [r for r in (data.get("replacements") or []) if isinstance(r, dict) and r.get("find")]

            os.makedirs(backups, exist_ok=True)
            changed = {}
            for rel in files:
                ap = os.path.join(path, rel)
                try:
                    with open(ap, "r", encoding="utf-8", errors="replace") as fh:
                        c = fh.read()
                except Exception:
                    continue
                orig = c
                n = 0
                for r in reps:
                    fnd = r.get("find") or ""
                    rpl = r.get("replace")
                    rpl = "" if rpl is None else str(rpl)
                    if fnd and fnd in c:
                        n += c.count(fnd)
                        c = c.replace(fnd, rpl)
                if n and c != orig:
                    _shutil.copy2(ap, os.path.join(backups, f"{rel.replace(os.sep, '_')}.{stamp}.bak"))
                    with open(ap, "w", encoding="utf-8", newline="") as fh:
                        fh.write(c)
                    changed[rel] = n

            if changed:
                resumen = ", ".join(f"{f} ({n})" for f, n in changed.items())
                _say(
                    f"✅ Apliqué el cambio en tu portafolio.\n\n"
                    f"Cambio: {instruction.strip()[:160]}\n"
                    f"Archivos modificados: {resumen}\n\n"
                    f"Respaldos en `backups/` (sello {stamp}). **Refresca el navegador (F5)** para verlo."
                )
                return

            # ── Paso 2 (fallback): edición estructural de UN archivo ──
            target = (data.get("file") or "").strip().replace("/", os.sep).replace("\\", os.sep)
            if target not in files:
                for f in files:
                    if f.lower() in instruction.lower():
                        target = f
                        break
            if target not in files:
                pick = self._extract_json(self._llm_structured(
                    "Portafolio web estático. Archivos:\n" + listing +
                    f"\n\nEl usuario pide: \"{instruction}\".\n¿Qué ÚNICO archivo modificar? SOLO JSON: {{\"file\":\"ruta\"}}",
                    expect_json=True)) or {}
                target = (pick.get("file") or "").strip().replace("/", os.sep).replace("\\", os.sep)
            if target not in files:
                _say("❌ No pude determinar qué cambiar. Sé más específico (ej. 'en certifications agrega...' "
                     "o 'cambia el texto X por Y').", ok=False, system=True)
                return

            abs_target = os.path.join(path, target)
            try:
                with open(abs_target, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                _say(f"❌ No pude leer {target}: {e}", ok=False, system=True)
                return
            if len(content) > 120000:
                _say(f"❌ {target} es muy grande para editarlo automáticamente.", ok=False, system=True)
                return

            edit_prompt = (
                f"Eres un editor de código preciso. Archivo del portafolio: {target}.\n"
                "Aplica EXACTAMENTE el cambio pedido y NO toques nada más.\n"
                f"Cambio pedido: \"{instruction}\".\n\n"
                "Contenido actual:\n<<<FILE\n" + content + "\nFILE\n\n"
                "Devuelve ÚNICAMENTE el contenido COMPLETO del archivo ya modificado, sin explicaciones y SIN fences ```."
            )
            new_content = self._llm_structured(edit_prompt, expect_json=False) or ""
            m = _re.search(r"```[a-zA-Z]*\s*(.+?)```", new_content, _re.S)
            if m:
                new_content = m.group(1)
            new_content = new_content.strip("\n")
            if not new_content or len(new_content) < max(20, len(content) * 0.3):
                _say("❌ La respuesta del modelo no parece un archivo válido; no apliqué cambios.", ok=False, system=True)
                return

            os.makedirs(backups, exist_ok=True)
            bak = os.path.join(backups, f"{target.replace(os.sep, '_')}.{stamp}.bak")
            _shutil.copy2(abs_target, bak)
            with open(abs_target, "w", encoding="utf-8", newline="") as f:
                f.write(new_content)
            _say(
                f"✅ Edité **{target}** en tu portafolio.\n\n"
                f"Cambio: {instruction.strip()[:160]}\n"
                f"Respaldo: `backups/{os.path.basename(bak)}`.\n\n"
                f"**Refresca el navegador (F5)** para verlo."
            )
        except Exception as e:
            _say(f"❌ Error inesperado editando el portafolio: {e}", ok=False, system=True)

    _SMARTSTUDENT_LOGO_URL = "https://smartstudent-web.vercel.app/img/logo4.png"

    def _structured_email_llm_prompt(self, role_desc, recipient_name, prompt, eyebrow_hint, tail_hint):
        """Prompt común para plantillas con contenido estructurado (SmartStudent / Point)."""
        return (
            f"{role_desc}\n"
            f"Destinatario: {recipient_name}.\n\n"
            "=== PEDIDO DEL USUARIO (este es el TEMA del correo, respétalo al pie de la letra) ===\n"
            f"{prompt}\n"
            "=== FIN DEL PEDIDO ===\n\n"
            "Redacta el correo SOBRE EXACTAMENTE ese pedido. El asunto, la intro y los items deben "
            "tratar ese tema concreto y nada más. Si el pedido es puntual (p. ej. avisar que el contrato "
            "quedó firmado por ambas partes), NO inventes un listado de features ni un pitch de producto: "
            "escribe solo lo que corresponde a ese mensaje.\n\n"
            "Devuelve UNICAMENTE un objeto JSON válido (sin texto antes ni después, sin fences) "
            "con esta forma exacta:\n"
            '{\n'
            '  "subject": "asunto breve y claro, sobre el tema del pedido",\n'
            '  "eyebrow": "ETIQUETA EN MAYÚSCULAS que resuma el tema del pedido",\n'
            '  "greeting_name": "nombre de pila del destinatario o \"\" si se desconoce",\n'
            '  "greeting_tail": "remate corto del saludo acorde al tema",\n'
            '  "intro": "párrafo introductorio de 1-2 frases sobre el tema",\n'
            '  "items": [ {"title": "título del punto", "body": "descripción (puede usar <strong> y <code>)", "featured": false} ],\n'
            '  "recommendation": "texto de recomendación final o \"\" si no aplica",\n'
            '  "closing": "frase de cierre breve"\n'
            '}\n'
            f"(Solo como referencia de FORMATO, no de tema: un eyebrow se ve así \"{eyebrow_hint}\" y un "
            f"remate así \"{tail_hint}\" — pero adáptalos al pedido real.)\n"
            "Reglas: 'items' es una lista de 1 a 6 puntos; si el pedido no amerita varios puntos, usa 1. "
            "Marca featured=true solo en un punto si hay uno destacado. No incluyas saludos ni firma dentro "
            "de los textos: eso lo arma la plantilla. No incluyas HTML completo, solo los campos pedidos. Solo el JSON."
        )

    def _build_point_email_html(self, data, recipient_name, prompt):
        """Arma el HTML del correo con la plantilla institucional Point
        (header magenta, eyebrow rosado, tarjetas numeradas con badge rosado,
        punto destacado en variante morada, callout morado, firma Jorge Castro · QCORE)."""
        import html as _html

        def esc(v):
            return _html.escape((v or "").strip())

        eyebrow = esc(data.get("eyebrow")) or "POINT · COMERCIO"
        greeting_name = esc(data.get("greeting_name"))
        greeting_tail = esc(data.get("greeting_tail")) or "acá va tu sistema"
        intro = esc(data.get("intro")) or "Te escribo con la información de tu sistema Point."
        closing = esc(data.get("closing")) or "Cualquier duda me escribes y te acompaño. ¡Saludos!"
        recommendation = (data.get("recommendation") or "").strip()

        items = data.get("items")
        if not isinstance(items, list) or not items:
            items = [{"title": "Detalle", "body": esc(prompt) or "Te comparto la información solicitada."}]

        if greeting_name:
            title = f"Hola {greeting_name} \U0001F44B — {greeting_tail}"
        else:
            title = f"\U0001F44B {greeting_tail}"

        cards = []
        for i, it in enumerate(items, start=1):
            it = it if isinstance(it, dict) else {}
            t = esc(it.get("title")) or f"Paso {i}"
            body = (it.get("body") or "").strip()  # permite <strong>/<code> del LLM
            featured = bool(it.get("featured"))
            box_bg = "#f5f3ff" if featured else "#fdf2f8"
            box_border = "#ddd6fe" if featured else "#fbcfe8"
            badge_bg = "#8E24AA" if featured else "#D81B60"
            cards.append(
                f'''          <tr>
            <td style="padding:0 40px 12px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="background:{box_bg};border:1px solid {box_border};border-radius:12px;">
                <tr>
                  <td style="padding:18px 20px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="width:40px;vertical-align:top;">
                          <div style="width:32px;height:32px;border-radius:8px;background:{badge_bg};color:#ffffff;font-size:15px;font-weight:800;text-align:center;line-height:32px;">{i}</div>
                        </td>
                        <td>
                          <div style="font-size:15px;font-weight:700;color:#0f172a;">{t}</div>
                          <div style="font-size:13px;color:#475569;margin-top:6px;line-height:1.6;">{body}</div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>'''
            )

        rec_html = ""
        if recommendation:
            rec_html = f'''          <tr>
            <td style="padding:0 40px 24px;">
              <div style="border-left:3px solid #8E24AA;background:#f8fafc;padding:14px 18px;border-radius:0 8px 8px 0;">
                <div style="font-size:12px;font-weight:700;color:#8E24AA;text-transform:uppercase;letter-spacing:1px;">Recomendación</div>
                <div style="font-size:13px;color:#475569;margin-top:4px;line-height:1.6;">{recommendation}</div>
              </div>
            </td>
          </tr>'''

        return f'''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(15,23,42,0.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#1a0a14 0%,#3d0f2e 50%,#5b1248 100%);padding:0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr><td style="height:4px;background:linear-gradient(90deg,#D81B60,#8E24AA,#D81B60);"></td></tr>
                <tr>
                  <td style="padding:32px 40px 24px;">
                    <div style="font-size:28px;font-weight:900;color:#ffffff;letter-spacing:1px;">Point<span style="color:#D81B60;"> POS</span></div>
                    <div style="font-size:12px;color:#e9b8d4;margin-top:4px;letter-spacing:2px;text-transform:uppercase;">Punto de venta + inventario · by QCORE</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:32px 40px 12px;">
              <div style="font-size:12px;color:#D81B60;font-weight:700;letter-spacing:2px;text-transform:uppercase;">{eyebrow}</div>
              <h1 style="margin:8px 0 0;font-size:22px;font-weight:800;color:#0f172a;line-height:1.3;">{title}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 40px 20px;">
              <p style="margin:0;font-size:14px;color:#475569;line-height:1.6;">{intro}</p>
            </td>
          </tr>
{chr(10).join(cards)}
{rec_html}
          <tr>
            <td style="padding:0 40px 32px;">
              <p style="margin:0 0 6px;font-size:14px;color:#475569;line-height:1.6;">{closing}</p>
              <table cellpadding="0" cellspacing="0" style="margin-top:24px;border-top:1px solid #e2e8f0;padding-top:20px;width:100%;">
                <tr>
                  <td style="padding-right:16px;vertical-align:middle;width:72px;">
                    {self._qcore_logo_badge_html(64, 34)}
                  </td>
                  <td style="vertical-align:middle;border-left:2px solid #e2e8f0;padding-left:16px;">
                    <div style="font-size:14px;font-weight:700;color:#1e293b;">Jorge Castro</div>
                    <div style="font-size:12px;color:#475569;margin-top:2px;">Account Director · QCORE</div>
                    <div style="font-size:12px;color:#64748b;margin-top:2px;">Santiago, Chile</div>
                    <div style="margin-top:4px;line-height:1.4;">
                      <a href="mailto:jorge.castro@qcorespa.com" style="color:#D81B60;text-decoration:none;font-size:12px;font-weight:500;">jorge.castro@qcorespa.com</a>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background:#f8fafc;padding:20px 40px;text-align:center;">
              <div style="font-size:10px;color:#94a3b8;line-height:1.6;">Point POS · Enviado por QCORE GROUP TECHNOLOGIES SPA · Santiago, Chile</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''

    def _qcore_logo_badge_html(self, size=64, font=34):
        """Badge institucional QCORE (cuadro morado redondeado con la 'Q' blanca).
        Se usa como logo en las firmas hasta que exista una imagen hospedada."""
        radius = round(size / 4)
        return (
            f'<table cellpadding="0" cellspacing="0" role="presentation" '
            f'style="width:{size}px;height:{size}px;border-radius:{radius}px;'
            f'background-color:#4f46e5;background:linear-gradient(135deg,#7b6ef0,#4f46e5);">'
            f'<tr><td align="center" valign="middle" style="font-size:{font}px;font-weight:800;'
            f'color:#ffffff;font-family:\'Segoe UI\',Arial,sans-serif;line-height:{size}px;">Q</td></tr>'
            f'</table>'
        )

    def _build_qcore_email_html(self, data, recipient_name, prompt):
        """Envuelve el cuerpo redactado en una tarjeta corporativa QCORE con la
        firma institucional fija (badge "Q", Jorge Castro · Account Director ·
        Santiago, Chile · www.qcorespa.com)."""
        import html as _html

        body_html = (data.get("body_html") or "").strip()
        if not body_html:
            safe = _html.escape((prompt or "").strip())
            body_html = (
                f'<p style="margin:0 0 12px;font-size:14px;color:#1e293b;line-height:1.6;">Estimado/a {_html.escape(recipient_name)},</p>'
                f'<p style="margin:0;font-size:14px;color:#475569;line-height:1.6;">{safe}</p>'
            )

        return f'''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(15,23,42,0.08);">
          <tr><td style="height:4px;background:linear-gradient(90deg,#6c5ce7,#4f46e5,#a29bfe);"></td></tr>
          <tr>
            <td style="padding:32px 40px 8px;font-size:14px;color:#1e293b;line-height:1.6;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:24px 40px 32px;">
              <p style="margin:0 0 18px;font-size:14px;color:#475569;line-height:1.6;">Saludos Cordiales,</p>
              <table cellpadding="0" cellspacing="0" style="width:100%;">
                <tr>
                  <td style="padding-right:16px;vertical-align:middle;width:72px;">
                    {self._qcore_logo_badge_html(64, 34)}
                  </td>
                  <td style="vertical-align:middle;border-left:2px solid #e2e8f0;padding-left:16px;">
                    <div style="font-size:16px;font-weight:700;color:#1e293b;">Jorge Castro</div>
                    <div style="font-size:13px;color:#64748b;margin-top:2px;">Account Director</div>
                    <div style="font-size:13px;color:#64748b;margin-top:2px;">Santiago, Chile</div>
                    <div style="margin-top:4px;line-height:1.2;">
                      <a href="https://www.qcorespa.com" style="color:#4f46e5;text-decoration:none;font-size:13px;font-weight:500;">www.qcorespa.com</a>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background:#f8fafc;padding:20px 40px;text-align:center;">
              <div style="font-size:10px;color:#94a3b8;line-height:1.6;">Este correo fue enviado por QCORE SPA · Santiago, Chile</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''

    def _build_smartstudent_email_html(self, data, recipient_name, prompt):
        """Arma el HTML del correo con la plantilla institucional SmartStudent
        (header navy, eyebrow azul, tarjetas numeradas con ✓, callout de
        recomendación, firma de Jorge Castro y footer QCORE)."""
        import html as _html

        def esc(v):
            return _html.escape((v or "").strip())

        eyebrow = esc(data.get("eyebrow")) or "ACTUALIZACIÓN PLATAFORMA"
        greeting_name = esc(data.get("greeting_name"))
        greeting_tail = esc(data.get("greeting_tail")) or "tu plataforma quedó al día"
        intro = esc(data.get("intro")) or (
            "Quería confirmarte que aplicamos las configuraciones que conversamos."
        )
        closing = esc(data.get("closing")) or "Cualquier ajuste me avisas. ¡Saludos!"
        recommendation = (data.get("recommendation") or "").strip()

        items = data.get("items")
        if not isinstance(items, list) or not items:
            items = [{"title": "Detalle", "body": esc(prompt) or "Te comparto la actualización solicitada."}]

        if greeting_name:
            title = f"Hola {greeting_name} \U0001F44B — {greeting_tail}"
        else:
            title = f"\U0001F44B {greeting_tail}"

        cards = []
        for i, it in enumerate(items, start=1):
            it = it if isinstance(it, dict) else {}
            t = esc(it.get("title")) or f"Punto {i}"
            body = (it.get("body") or "").strip()  # permite <strong>/<code> del LLM
            featured = bool(it.get("featured"))
            box_bg = "#eff6ff" if featured else "#f8fafc"
            box_border = "#bfdbfe" if featured else "#e2e8f0"
            badge_bg = "#2563eb" if featured else "#dcfce7"
            badge_fg = "#ffffff" if featured else "#16a34a"
            badge_char = "★" if featured else "✓"
            title_html = (
                f'<div style="font-size:15px;font-weight:700;color:#0f172a;">{i} · '
                f'<span style="color:#2563eb;">{t}</span></div>' if featured
                else f'<div style="font-size:15px;font-weight:700;color:#0f172a;">{i} · {t}</div>'
            )
            cards.append(
                f'''          <tr>
            <td style="padding:0 40px 16px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="background:{box_bg};border:1px solid {box_border};border-radius:12px;">
                <tr>
                  <td style="padding:18px 20px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="width:36px;vertical-align:top;">
                          <div style="width:32px;height:32px;border-radius:8px;background:{badge_bg};color:{badge_fg};font-size:16px;font-weight:800;text-align:center;line-height:32px;">{badge_char}</div>
                        </td>
                        <td>
                          {title_html}
                          <div style="font-size:13px;color:#475569;margin-top:4px;line-height:1.5;">{body}</div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>'''
            )

        rec_html = ""
        if recommendation:
            rec_html = f'''          <tr>
            <td style="padding:0 40px 24px;">
              <div style="border-left:3px solid #2563eb;background:#f8fafc;padding:14px 18px;border-radius:0 8px 8px 0;">
                <div style="font-size:12px;font-weight:700;color:#2563eb;text-transform:uppercase;letter-spacing:1px;">Recomendación</div>
                <div style="font-size:13px;color:#475569;margin-top:4px;line-height:1.6;">{recommendation}</div>
              </div>
            </td>
          </tr>'''

        logo = self._SMARTSTUDENT_LOGO_URL
        return f'''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(15,23,42,0.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#060d1a 0%,#0d1b2e 50%,#112240 100%);padding:0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr><td style="height:4px;background:linear-gradient(90deg,#2563eb,#3B82F6,#4ADE80);"></td></tr>
                <tr>
                  <td style="padding:32px 40px 24px;">
                    <table cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="vertical-align:middle;width:88px;padding-right:10px;">
                          <img src="{logo}" alt="SmartStudent" style="width:80px;height:80px;border-radius:16px;object-fit:contain;display:block;" />
                        </td>
                        <td>
                          <div style="font-size:28px;font-weight:900;color:#ffffff;letter-spacing:1px;">Smart<span style="color:#2563eb;">Student</span></div>
                          <div style="font-size:12px;color:#94a3b8;margin-top:4px;letter-spacing:2px;text-transform:uppercase;">Gestión Escolar con Inteligencia Artificial</div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:32px 40px 12px;">
              <div style="font-size:12px;color:#2563eb;font-weight:700;letter-spacing:2px;text-transform:uppercase;">{eyebrow}</div>
              <h1 style="margin:8px 0 0;font-size:22px;font-weight:800;color:#0f172a;line-height:1.3;">{title}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 40px 20px;">
              <p style="margin:0;font-size:14px;color:#475569;line-height:1.6;">{intro}</p>
            </td>
          </tr>
{chr(10).join(cards)}
{rec_html}
          <tr>
            <td style="padding:0 40px 32px;">
              <p style="margin:0 0 6px;font-size:14px;color:#475569;line-height:1.6;">{closing}</p>
              <table cellpadding="0" cellspacing="0" style="margin-top:24px;border-top:1px solid #e2e8f0;padding-top:20px;width:100%;">
                <tr>
                  <td style="padding-right:14px;vertical-align:top;width:90px;">
                    <img src="{logo}" alt="SmartStudent" style="width:80px;height:80px;border-radius:20px;object-fit:contain;display:block;" />
                  </td>
                  <td style="vertical-align:top;">
                    <div style="font-size:14px;font-weight:700;color:#1e293b;">Jorge Castro</div>
                    <div style="font-size:12px;color:#475569;margin-top:2px;">Account Director · SmartStudent</div>
                    <div style="font-size:12px;color:#64748b;margin-top:2px;">Santiago, Chile</div>
                    <div style="margin-top:4px;line-height:1.2;">
                      <a href="https://www.smartstudent.cl" style="color:#2563eb;text-decoration:none;font-size:12px;font-weight:500;">www.smartstudent.cl</a>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background:#f8fafc;padding:20px 40px;text-align:center;">
              <div style="font-size:10px;color:#94a3b8;line-height:1.6;">Este correo fue enviado por QCORE SPA · Santiago, Chile</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''

    def _seed_mc_draft_worker(self, prompt, recipient_name, contact_key, brand, to_list, cc_list, status,
                              kind="general-reply", origin="direct-email", custom_reference=None):
        import datetime as _dt
        import json as _json
        template = brand.get("template")
        try:
            if template == "smartstudent":
                llm_prompt = self._structured_email_llm_prompt(
                    "Eres redactor de correos de SmartStudent (plataforma educativa SaaS). "
                    "Tono cercano, claro y profesional, en español de Chile.",
                    recipient_name, prompt,
                    "ACTUALIZACIÓN PLATAFORMA · COMBAS", "tu plataforma quedó al día",
                )
                raw = self._llm_structured(llm_prompt, expect_json=True)
                data = self._extract_json(raw) or {}
                subject = (data.get("subject") or "").strip() or f"Actualización SmartStudent · {recipient_name}"
                html = self._build_smartstudent_email_html(data, recipient_name, prompt)
            elif template == "point":
                llm_prompt = self._structured_email_llm_prompt(
                    "Eres redactor de correos de Point (sistema POS con control de inventario FEFO para comercios). "
                    "Tono cercano, claro y práctico, orientado al dueño del negocio, en español de Chile.",
                    recipient_name, prompt,
                    "ENTREGA DE SOFTWARE · TENTACIÓN A GRANEL", "acá va tu sistema listo",
                )
                raw = self._llm_structured(llm_prompt, expect_json=True)
                data = self._extract_json(raw) or {}
                subject = (data.get("subject") or "").strip() or f"Point · {recipient_name}"
                html = self._build_point_email_html(data, recipient_name, prompt)
            else:
                llm_prompt = (
                    f"Eres redactor de correos profesionales. {brand['guidance']}\n"
                    f"Destinatario: {recipient_name}.\n"
                    f"Pedido del usuario: \"{prompt}\".\n\n"
                    "Redacta SOLO el cuerpo del correo en español (saludo inicial + párrafos). "
                    "NO incluyas despedida, ni firma, ni datos de contacto: eso se añade automáticamente. "
                    "Devuelve UNICAMENTE un objeto JSON válido, sin texto antes ni después y sin fences, "
                    "con esta forma exacta:\n"
                    '{"subject": "asunto breve", "body_html": "<p>saludo</p><p>párrafos del cuerpo en HTML</p>"}\n'
                    "El body_html debe usar etiquetas <p> con estilos inline simples y profesionales. "
                    "No incluyas comentarios ni explicaciones, solo el JSON."
                )
                raw = self._llm_structured(llm_prompt, expect_json=True)
                data = self._extract_json(raw) or {}
                subject = (data.get("subject") or "").strip() or f"Mensaje para {recipient_name}"
                html = self._build_qcore_email_html(data, recipient_name, prompt)

            now = _dt.datetime.now(_dt.timezone.utc)
            stamp = now.strftime("%Y%m%d%H%M%S")
            iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            seed_id = f"seed-claudy-{contact_key}-{stamp}"
            draft = {
                "id": seed_id,
                "kind": kind,
                "relatedMessageId": f"{seed_id}-msg",
                "createdAt": iso,
                "status": "pending-approval",
                "origin": origin,
                "reason": (custom_reference.strip()[:200] if custom_reference and custom_reference.strip()
                           else f"Borrador creado por Claudy a partir de: {prompt.strip()[:200]}"),
                "from": brand["from"],
                "to": to_list,
                "cc": cc_list,
                "replyTo": brand["replyTo"],
                "subject": subject,
                "html": html,
            }
            if brand.get("productId"):
                draft["productId"] = brand["productId"]

            path = self._MC_SEEDED_DRAFTS_PATH
            existing = []
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        loaded = _json.load(f)
                        if isinstance(loaded, list):
                            existing = loaded
            except Exception:
                existing = []
            existing.append(draft)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                _json.dump(existing, f, ensure_ascii=False, indent=2)

            dest = ", ".join(to_list) if to_list else "(sin destinatario — complétalo en el Inbox)"
            def _ok():
                ch = getattr(self, "_chat_view", None)
                if ch:
                    ch.hide_typing()
                    ch.add_system(
                        f"✅ Borrador creado en el **Inbox de Mission Control**.\n\n"
                        f"**Para:** {dest}\n**Asunto:** {subject}\n\n"
                        f"Aparecerá en *Borradores pendientes* en ~1 segundo si Mission Control está abierto."
                    )
                try:
                    status.configure(text="Borrador sembrado en Mission Control", fg="#00ff99")
                except Exception:
                    pass
            self.after(0, _ok)
        except Exception as e:
            def _err(ex=e):
                ch = getattr(self, "_chat_view", None)
                if ch:
                    ch.hide_typing()
                    ch.add_system(f"❌ No pude crear el borrador en Mission Control: {ex}")
                try:
                    status.configure(text=f"Error: {ex}", fg="#ff5555")
                except Exception:
                    pass
            self.after(0, _err)

    # ============================================================
    # Guided Report Flow (Asistente de Informes Interactivo)
    # ============================================================
    def _start_guided_report_flow(self, topic, status, entry):
        self._guided_report_active = True
        self._guided_report_step = 1
        self._guided_report_topic = topic or "Tema General"
        self._guided_report_data = {
            "topic": self._guided_report_topic,
            "depth": None,
            "images": None,
            "references": None,
            "style": None,
            "language": None
        }
        self._bubble_status = status
        self._bubble_entry = entry

        # Clear visible chat and show starting message
        chat = getattr(self, "_chat_view", None)
        if chat is not None:
            try:
                chat.clear()
            except Exception:
                pass
            chat.add_user(f"Quiero un informe sobre: {self._guided_report_topic}")
            
            chat.add_bot(
                f"Perfecto, vamos a estructurar un gran informe sobre:\n"
                f"**{self._guided_report_topic}**\n\n"
                f"Por defecto se creará en formato **DOCX** dentro de tu carpeta de documentos.\n\n"
                f"**Pregunta 1/5: ¿Qué alcance y profundidad deseas para el informe?**"
            )
            options = [
                ("1", "Resumen Ejecutivo", "Una síntesis concisa, al grano y directa al núcleo de la información"),
                ("2", "Extenso y Detallado", "Un desarrollo profundo con explicaciones exhaustivas e información completa"),
                ("3", "Actualizado al día", "Enfocado en las últimas tendencias y descubrimientos más recientes en internet")
            ]
            chat.add_options(options, self._handle_option_select)
            
        status.configure(text="Paso 1: Profundidad", fg=THEME["accent"])
        entry.configure(state="normal")
        entry.focus_set()

    def _handle_option_select(self, option_value):
        status = getattr(self, "_bubble_status", None)
        entry = getattr(self, "_bubble_entry", None)
        if status and entry:
            self._handle_guided_report_step(option_value, status, entry)

    def _handle_guided_report_step(self, prompt, status, entry):
        chat = getattr(self, "_chat_view", None)
        if chat is None:
            return
            
        step = self._guided_report_step
        plow = prompt.lower().strip()
        
        if step == 1:
            # Parse depth answer
            title_map = {
                "1": "Resumen Ejecutivo",
                "2": "Extenso y Detallado",
                "3": "Actualizado al día"
            }
            if prompt in title_map:
                ans = title_map[prompt]
                chat.add_user(ans)
            else:
                if "1" in plow or "resumen" in plow or "ejecutivo" in plow or "conciso" in plow:
                    ans = "Resumen Ejecutivo"
                elif "2" in plow or "extenso" in plow or "detallado" in plow or "profundo" in plow:
                    ans = "Extenso y Detallado"
                elif "3" in plow or "actualizado" in plow or "dia" in plow or "reciente" in plow:
                    ans = "Actualizado al día"
                else:
                    ans = prompt
                chat.add_user(prompt)
                
            self._guided_report_data["depth"] = ans
            
            # Go to step 2
            self._guided_report_step = 2
            chat.add_bot("**Pregunta 2/5: ¿Deseas incluir recursos visuales o imágenes?**")
            options = [
                ("1", "Sin imágenes", "Un documento puramente textual, limpio y minimalista"),
                ("2", "Pocas imágenes", "Un par de imágenes clave para ilustrar conceptos fundamentales"),
                ("3", "Muchas imágenes", "Un reporte visualmente enriquecido con ilustraciones en cada sección"),
                ("4", "Carpeta de recursos aparte", "Yo busco y descargo las imágenes y te las entrego organizadas en una carpeta aparte")
            ]
            chat.add_options(options, self._handle_option_select)
            status.configure(text="Paso 2: Imágenes", fg=THEME["accent"])
            
        elif step == 2:
            # Parse images answer
            title_map = {
                "1": "Sin imágenes",
                "2": "Pocas imágenes",
                "3": "Muchas imágenes",
                "4": "Carpeta de recursos aparte"
            }
            if prompt in title_map:
                ans = title_map[prompt]
                chat.add_user(ans)
            else:
                if "1" in plow or "sin" in plow or "ninguna" in plow:
                    ans = "Sin imágenes"
                elif "2" in plow or "pocas" in plow or "par" in plow:
                    ans = "Pocas imágenes"
                elif "3" in plow or "muchas" in plow or "ilustraciones" in plow:
                    ans = "Muchas imágenes"
                elif "4" in plow or "carpeta" in plow or "recursos" in plow or "aparte" in plow:
                    ans = "Carpeta de recursos aparte"
                else:
                    ans = prompt
                chat.add_user(prompt)
                
            self._guided_report_data["images"] = ans
            
            # Go to step 3
            self._guided_report_step = 3
            chat.add_bot("**Pregunta 3/5: ¿Cómo prefieres el manejo de fuentes y referencias?**")
            options = [
                ("1", "Sin citas", "Un reporte auto-explicativo sin referencias a pie de página ni bibliografía"),
                ("2", "Con referencias al final", "Una lista ordenada de fuentes y enlaces de consulta al final del documento"),
                ("3", "Citas con formato APA", "Citas académicas integradas en el texto siguiendo las normas oficiales de la APA"),
                ("4", "Citas con formato IEEE", "Citas numeradas entre corchetes, ideales para informes técnicos o de ingeniería")
            ]
            chat.add_options(options, self._handle_option_select)
            status.configure(text="Paso 3: Referencias", fg=THEME["accent"])
            
        elif step == 3:
            # Parse references answer
            title_map = {
                "1": "Sin citas",
                "2": "Con referencias al final",
                "3": "Citas con formato APA",
                "4": "Citas con formato IEEE"
            }
            if prompt in title_map:
                ans = title_map[prompt]
                chat.add_user(ans)
            else:
                if "1" in plow or "sin" in plow:
                    ans = "Sin citas"
                elif "2" in plow or "final" in plow or "lista" in plow:
                    ans = "Con referencias al final"
                elif "3" in plow or "apa" in plow:
                    ans = "Citas con formato APA"
                elif "4" in plow or "ieee" in plow:
                    ans = "Citas con formato IEEE"
                else:
                    ans = prompt
                chat.add_user(prompt)
                
            self._guided_report_data["references"] = ans
            
            # Go to step 4
            self._guided_report_step = 4
            chat.add_bot("**Pregunta 4/5: ¿Qué tono y estilo de maquetación deseas aplicar?**")
            options = [
                ("1", "Profesional Académico", "Texto formal, justificado, interlineado estándar y estructura sobria"),
                ("2", "Corporativo Elegante", "Con portada formal, índice interactivo, fuentes modernas y justificación limpia"),
                ("3", "Casual Creativo", "Un tono más cercano, diseño dinámico y enfoque de lectura ágil")
            ]
            chat.add_options(options, self._handle_option_select)
            status.configure(text="Paso 4: Estilo", fg=THEME["accent"])
            
        elif step == 4:
            # Parse style answer
            title_map = {
                "1": "Profesional Académico",
                "2": "Corporativo Elegante",
                "3": "Casual Creativo"
            }
            if prompt in title_map:
                ans = title_map[prompt]
                chat.add_user(ans)
            else:
                if "1" in plow or "profesional" in plow or "academico" in plow or "formal" in plow:
                    ans = "Profesional Académico"
                elif "2" in plow or "corporativo" in plow or "elegante" in plow or "portada" in plow:
                    ans = "Corporativo Elegante"
                elif "3" in plow or "casual" in plow or "creativo" in plow:
                    ans = "Casual Creativo"
                else:
                    ans = prompt
                chat.add_user(prompt)
                
            self._guided_report_data["style"] = ans
            
            # Go to step 5
            self._guided_report_step = 5
            chat.add_bot("**Pregunta 5/5: ¿En qué idioma deseas que redacte el informe?**")
            options = [
                ("1", "Español", "Redacción directa, natural y con ortografía impecable en español"),
                ("2", "Inglés", "Redacción fluida, técnica y profesional en inglés")
            ]
            chat.add_options(options, self._handle_option_select)
            status.configure(text="Paso 5: Idioma", fg=THEME["accent"])
            
        elif step == 5:
            # Parse language answer
            title_map = {
                "1": "Español",
                "2": "Inglés"
            }
            if prompt in title_map:
                ans = title_map[prompt]
                chat.add_user(ans)
            else:
                if "1" in plow or "espanol" in plow or "español" in plow or "spa" in plow:
                    ans = "Español"
                elif "2" in plow or "ingles" in plow or "inglés" in plow or "eng" in plow:
                    ans = "Inglés"
                else:
                    ans = prompt
                chat.add_user(prompt)
                
            self._guided_report_data["language"] = ans
            
            # End of questions
            self._guided_report_active = False
            self._guided_report_step = 0
            
            # Show premium summary card
            chat.add_bot("¡Excelente! Tengo todo configurado para tu informe:")
            chat.add_summary_card(
                topic=self._guided_report_data['topic'],
                depth=self._guided_report_data['depth'],
                images=self._guided_report_data['images'],
                references=self._guided_report_data['references'],
                style=self._guided_report_data['style'],
                language=self._guided_report_data['language']
            )
            status.configure(text="Investigando y redactando...", fg=THEME["accent"])

            # Capture report data locally for the thread closure
            rdata = dict(self._guided_report_data)

            # ── CRITICAL: suppress all chat display during background report build ──
            self._report_generating = True
            self._reset_cancel()  # limpiar cualquier cancelación previa

            # Start background processing thread
            self._start_milestone_progress()
            self._start_typing_progress(entry, rdata.get("topic", "Informe"))

            def worker():
                import re as _re
                import os as _os
                result = "Error inesperado en el pipeline."
                try:
                    topic = rdata.get("topic", "Tema General")
                    depth = rdata.get("depth", "Extenso y actualizado")
                    images_pref = rdata.get("images", "No")
                    references = rdata.get("references", "Sí, con citas APA")
                    style = rdata.get("style", "Profesional justificado con portada e índice")
                    language = rdata.get("language", "Español")

                    # ── Step 1: REAL web research (search + scrape) ──
                    if self._is_cancelled():
                        self._stop_milestone_progress()
                        return
                    self._report_progress(10, "Investigando en internet", status)

                    web_context = ""
                    web_sources = []
                    try:
                        _seen = {"n": 0}
                        def _on_src(u):
                            _seen["n"] += 1
                            # 10% → 30% repartido entre las páginas leídas (máx ~4).
                            pct = min(30, 10 + _seen["n"] * 5)
                            self._report_progress(pct, f"Leyendo fuente {_seen['n']}", status)
                        web_context, web_sources = self._gather_web_context(
                            topic, max_pages=4, on_status=_on_src)
                    except Exception:
                        web_context, web_sources = "", []

                    # Load professional formatting rules from skill file
                    _skill_rules = ""
                    try:
                        _skill_path = _os.path.join(
                            _os.path.dirname(_os.path.abspath(__file__)),
                            "..", "..", "skills", "professional-document-writer", "SKILL.md"
                        )
                        if _os.path.isfile(_skill_path):
                            with open(_skill_path, "r", encoding="utf-8") as _sf:
                                _skill_rules = _sf.read()
                    except Exception:
                        pass
                    if not _skill_rules:
                        _skill_rules = (
                            "FORMATO PROFESIONAL:\n"
                            "- Título con # TÍTULO. Introducción obligatoria.\n"
                            "- Secciones con ## y subsecciones con ###. Nunca saltes niveles.\n"
                            "- Usa **negritas** para conceptos clave, *cursivas* para énfasis secundario.\n"
                            "- Datos comparativos en TABLAS Markdown (| Col | Col |).\n"
                            "- Citas importantes con > formato.\n"
                            "- Termina con ## Conclusiones y ## Referencias.\n"
                            "- NO uses placeholders como [Insertar aquí]. Escribe contenido real.\n"
                            "- NO incluyas saludos ni comentarios fuera del documento."
                        )

                    # Objetivo de extensión según la profundidad elegida. Lo usa
                    # _write_report_by_sections para repartir palabras por sección.
                    _dl = (depth or "").lower()
                    if "extenso" in _dl or "detallado" in _dl or "profundo" in _dl:
                        min_words = 4000
                    elif "resumen" in _dl or "ejecutivo" in _dl or "conciso" in _dl:
                        min_words = 900
                    else:  # "Actualizado al día" u otros
                        min_words = 2000

                    # Directiva de citas según lo elegido por el usuario.
                    _rl = (references or "").lower()
                    if "apa" in _rl:
                        citation_directive = (
                            "FORMATO DE CITAS APA (OBLIGATORIO): inserta citas en el texto con el formato "
                            "(Autor/Organización, año) cuando uses un dato de una fuente. La sección final "
                            "'## Referencias' debe listar cada fuente en formato APA 7: "
                            "Autor/Organización. (Año). *Título del recurso*. Recuperado de URL. "
                            "Usa las URLs reales del bloque de fuentes; si no conoces el autor, usa el nombre del sitio."
                        )
                    elif "ieee" in _rl:
                        citation_directive = (
                            "FORMATO DE CITAS IEEE (OBLIGATORIO): numera las referencias entre corchetes [1], [2] "
                            "en el texto y lista al final en '## Referencias' como: [n] Autor, \"Título,\" Sitio, Año. URL. "
                            "Usa las URLs reales del bloque de fuentes."
                        )
                    elif "final" in _rl:
                        citation_directive = (
                            "Incluye una sección '## Referencias' al final con la lista de fuentes y sus URLs reales. "
                            "No es necesario citar en el cuerpo del texto."
                        )
                    else:  # "Sin citas"
                        citation_directive = "No incluyas sección de referencias ni citas."

                    # Build a web-evidence block from the scraped sources so the
                    # LLM redacts from REAL current data, not only its memory.
                    if web_context:
                        _src_list = "\n".join(
                            f"[{i+1}] {s['title']} — {s['url']}"
                            for i, s in enumerate(web_sources)
                        )
                        web_block = (
                            f"INFORMACION REAL Y ACTUAL RECOPILADA DE INTERNET (úsala como base factual; "
                            f"prioriza estos datos sobre tu memoria interna y cita las fuentes por su número [n]):\n\n"
                            f"{web_context}\n\n"
                            f"FUENTES DISPONIBLES PARA REFERENCIAS:\n{_src_list}\n\n"
                        )
                    else:
                        web_block = (
                            "NOTA: No se pudo recopilar información de internet; redacta con tu conocimiento "
                            "pero evita inventar cifras o fechas concretas que no puedas respaldar.\n\n"
                        )

                    # ── Redacción POR SECCIONES (varias llamadas cortas) ──
                    # Pedir 8000 tokens de un tirón ahogaba/colgaba a DeepSeek. En su
                    # lugar: 1 llamada para el índice + 1 llamada por sección. Cada
                    # llamada es corta (<150s) y el % avanza de verdad.
                    common_ctx = (
                        f"{web_block}"
                        f"{citation_directive}\n\n"
                        f"DIRECTRICES DE FORMATO PROFESIONAL:\n{_skill_rules}\n"
                    )
                    raw_content = self._write_report_by_sections(
                        topic=topic, depth=depth, style=style, language=language,
                        common_ctx=common_ctx, web_sources=web_sources,
                        references=references, min_words=min_words, status=status,
                    )

                    # Si el usuario interrumpió (doble ESC), abortar sin guardar.
                    if self._is_cancelled():
                        print("[report] cancelado por el usuario — no se guarda archivo")
                        self._stop_milestone_progress()
                        return

                    # Strip any accidental slash commands from the LLM response
                    raw_content = _re.sub(r'^/\S+.*$', '', raw_content, flags=_re.MULTILINE).strip()
                    if not raw_content or len(raw_content) < 100:
                        raw_content = (
                            f"# Informe: {topic}\n\n"
                            f"## Introducción\n"
                            f"Este informe presenta información sobre {topic}.\n\n"
                            f"## Desarrollo\n"
                            f"El tema de {topic} abarca múltiples aspectos relevantes para su comprensión.\n\n"
                            f"## Conclusiones\n"
                            f"En conclusión, {topic} es un tema de gran importancia.\n"
                        )

                    # ── Step 2: Optionally download images ──
                    # Queremos imágenes salvo que el usuario haya elegido "Sin imágenes".
                    image_paths = []
                    _ip = (images_pref or "").lower()
                    wants_images = bool(_ip) and not ("sin imágenes" in _ip or "sin imagenes" in _ip or _ip.strip() == "no")
                    if wants_images:
                        max_imgs = 5 if "muchas" in _ip else 3
                        self._report_progress(75, "Buscando imágenes", status)
                        try:
                            image_paths = self._download_report_images(topic, max_images=max_imgs)
                        except Exception:
                            image_paths = []

                    # ── Step 3: Build the docx locally (guaranteed) ──
                    self._report_progress(90, "Creando el archivo Word", status)
                    import claudy_powers as cp

                    # Nombre de archivo CORTO y limpio. En vez del prompt crudo
                    # ("infrome en docx sobre toda la historia...") usamos el título
                    # H1 que el propio informe ya generó, y si no, limpiamos el tema
                    # quitando muletillas. Capitalizado y recortado a palabras enteras.
                    def _clean_doc_name(raw):
                        s = (raw or "").strip()
                        # Quitar muletillas iniciales encadenadas tipo
                        # "crea un docx extenso sobre toda la historia ..." aplicando
                        # los patrones repetidamente hasta que no quede nada que pelar.
                        _patterns = [
                            r"^(?:crea(?:me)?|cre[aá]|hazme|haz|genera(?:me)?|necesito|quiero|dame|hac[eé]r?)\b",
                            r"^(?:un|una|el|la|los|las)\b",
                            r"^(?:informe|infrome|reporte|documento|docx|doc|word|pdf|archivo|texto)\b",
                            r"^en\s+\w+\b",
                            r"^(?:completo|extenso|detallado|profesional|breve|corto)\b",
                            r"^(?:sobre|de|acerca\s+de|del|toda|todo)\b",
                        ]
                        changed = True
                        while changed:
                            changed = False
                            for pat in _patterns:
                                new = _re.sub(pat, "", s, flags=_re.IGNORECASE).strip()
                                if new != s:
                                    s = new
                                    changed = True
                        s = _re.sub(r'[\\/*?:"<>|]', "", s)        # chars inválidos
                        s = _re.sub(r"\s+", " ", s).strip(" .-")
                        # recortar a ~50 chars sin cortar palabras
                        if len(s) > 50:
                            s = s[:50].rsplit(" ", 1)[0]
                        return (s[:1].upper() + s[1:]) if s else "Informe"

                    # Preferir el título H1 del contenido (idioma correcto, ya limpio).
                    _m_title = _re.search(r"^#\s+(.+)$", raw_content, _re.MULTILINE)
                    _title_src = _m_title.group(1) if _m_title else topic
                    safe_topic = _clean_doc_name(_title_src)
                    # Guardar en la carpeta de Claudy en Google Drive. Si Drive no
                    # está montado, caer a la carpeta local de Documentos.
                    drive_dir = r"G:\Mi unidad\claudy_files"
                    if _os.path.isdir(r"G:\Mi unidad"):
                        docx_dir = drive_dir
                    else:
                        docx_dir = _os.path.join(_os.path.expanduser("~"), "Documents", "Claudy", "Informes")
                    _os.makedirs(docx_dir, exist_ok=True)

                    def _is_locked(p):
                        if not _os.path.exists(p):
                            return False
                        lock = _os.path.join(_os.path.dirname(p), "~$" + _os.path.basename(p))
                        if _os.path.exists(lock):
                            return True
                        try:  # intentar abrir en modo append exclusivo
                            with open(p, "a"):
                                return False
                        except Exception:
                            return True

                    # Versionado: si ya existe un informe con ese nombre (o está
                    # abierto en Word), añadir (2), (3)... para distinguir versiones
                    # sin pisar el anterior ni fallar por archivo bloqueado.
                    docx_path = _os.path.join(docx_dir, f"{safe_topic}.docx")
                    _v = 2
                    while _os.path.exists(docx_path) or _is_locked(docx_path):
                        docx_path = _os.path.join(docx_dir, f"{safe_topic} ({_v}).docx")
                        _v += 1
                        if _v > 50:  # tope de seguridad
                            stamp = time.strftime("%Y%m%d_%H%M%S")
                            docx_path = _os.path.join(docx_dir, f"{safe_topic} {stamp}.docx")
                            break

                    result = cp.create_docx_with_images(docx_path, raw_content, image_paths)
                    print(f"[report] create_docx -> {str(result)[:200]}")
                    print(f"[report] raw_content len={len(raw_content)} chars, imgs={len(image_paths)}")
                    try:
                        self._debug_log("REPORT DOCX",
                            f"len={len(raw_content)} imgs={len(image_paths)} -> {str(result)[:160]}")
                    except Exception:
                        pass

                    # Avisar honestamente si se pidieron imágenes y no se encontró ninguna.
                    if wants_images and not image_paths:
                        result += (
                            "\n\n⚠️ No encontré imágenes reales en Wikimedia para este tema, "
                            "así que el informe quedó sin ilustraciones."
                        )
                    elif image_paths:
                        result += f"\n\n🖼️ Incrusté {len(image_paths)} imagen(es) de Wikimedia."

                except Exception as pipeline_err:
                    import traceback as _tb
                    tb = _tb.format_exc()
                    print(f"[report] PIPELINE ERROR: {pipeline_err}\n{tb}")
                    try:
                        self._debug_log("REPORT PIPELINE ERROR", tb)
                    except Exception:
                        pass
                    result = f"Error en el pipeline del informe: {pipeline_err}"

                self._report_progress(100, "Informe terminado", status)
                self._stop_milestone_progress()
                self.after(0, lambda: self._deliver_report_result(result, status, entry))

            threading.Thread(target=worker, daemon=True, name="report-worker").start()

    # ============================================================
    # Hitos de progreso ("dame un momento, sigo trabajando...")
    # ============================================================
    PROGRESS_MILESTONES = [
        (12, "Dame un momento, sigo procesando..."),
        (28, "Sigo trabajando, ya casi tengo algo para ti."),
        (50, "Esto tomo mas de lo esperado, no te abandone."),
        (80, "Aun aqui. Tarea larga, pero ahi vamos."),
        (120, "Sigo encima. Si esto sigue colgado, avisame."),
    ]

    def _start_milestone_progress(self):
        """Schedule milestone updates into the response bubble while worker runs."""
        self._milestone_active = True
        self._milestone_after_ids = []
        for delay_s, msg in self.PROGRESS_MILESTONES:
            aid = self.after(int(delay_s * 1000), lambda m=msg: self._emit_milestone(m))
            self._milestone_after_ids.append(aid)

    def _game_done(self, result, status, entry, chat=None):
        """Callback when the gaming worker finishes. Shows result in chat."""
        try:
            if chat:
                chat.hide_typing()
                chat.add_bot(result)
            else:
                self._set_response_text(result)
            status.configure(text="\ud83c\udfae Listo", fg=THEME.get("accent", "#c4b5fd"))
            # Show bubble if minimized
            first_line = result.splitlines()[0] if result else "Juego listo"
            if getattr(self, "bubble_minimized", False):
                self.show_pet_speech_bubble(first_line, duration=8000)
        except Exception:
            pass
        try:
            entry.configure(state="normal")
            entry.focus_set()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════
    # ALARMAS  ─  motor completo
    # ══════════════════════════════════════════════════════════════════
    def _alarms_path(self):
        p = os.path.join(os.path.expanduser("~"), ".claudy", "alarms.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def _load_alarms(self):
        try:
            with open(self._alarms_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_alarms(self, alarms):
        try:
            with open(self._alarms_path(), "w", encoding="utf-8") as f:
                json.dump(alarms, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _parse_alarm_time(self, text):
        """Parse Spanish natural language time from text.
        Returns (fire_ts, label) or (None, None) on failure.
        Examples: 'en 30 minutos', 'a las 15:30', 'mañana a las 9', '2 horas'.
        """
        import re as _re
        import time as _time
        now = _time.time()
        tl = text.lower()

        # en N minutos / en N horas / en N segundos
        m = _re.search(r'en\s+(\d+)\s*(minuto|minutos|min|hora|horas|h|segundo|segundos|seg)', tl)
        if m:
            qty = int(m.group(1))
            unit = m.group(2)
            if unit.startswith("s"):
                delta = qty
            elif unit.startswith("m"):
                delta = qty * 60
            else:
                delta = qty * 3600
            label = _re.sub(r'(/alarma|alarma\s*(para|en|a\s*las)?)', '', tl, flags=_re.IGNORECASE).strip()
            return now + delta, label or text

        # a las HH:MM  o  a las H (am/pm)
        m = _re.search(r'a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', tl)
        if m:
            import datetime as _dt
            h = int(m.group(1))
            mins = int(m.group(2)) if m.group(2) else 0
            ampm = (m.group(3) or "").lower()
            if ampm == "pm" and h < 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0
            target = _dt.datetime.now().replace(hour=h, minute=mins, second=0, microsecond=0)
            if target.timestamp() <= now:
                target += _dt.timedelta(days=1)  # next day if already past
            label = _re.sub(r'(/alarma|alarma\s*(para|en|a\s*las?)?)', '', tl, flags=_re.IGNORECASE).strip()
            label = _re.sub(r'a\s+las?\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?', '', label).strip(" ,-")
            return target.timestamp(), label or f"Alarma {h:02d}:{mins:02d}"

        # mañana a las HH:MM
        m = _re.search(r'mañana\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?', tl)
        if m:
            import datetime as _dt
            h = int(m.group(1))
            mins = int(m.group(2)) if m.group(2) else 0
            target = _dt.datetime.now().replace(hour=h, minute=mins, second=0, microsecond=0)
            target += _dt.timedelta(days=1)
            label = _re.sub(r'(/alarma|alarma\s*(para|mañana)?|mañana\s+a\s+las?\s+\d+(?::\d+)?)', '', tl).strip(" ,-")
            return target.timestamp(), label or f"Alarma mañana {h:02d}:{mins:02d}"

        return None, None

    def _alarm_set(self, text):
        """Create and schedule an alarm from natural language text."""
        import time as _time
        fire_ts, label = self._parse_alarm_time(text)
        if fire_ts is None:
            return (
                "⏰ No entendí la hora, Felipe. Prueba con:\n"
                "• \"en 30 minutos\"\n"
                "• \"en 2 horas\"\n"
                "• \"a las 15:30\"\n"
                "• \"mañana a las 9\""
            )
        alarms = self._load_alarms()
        alarm_id = str(int(_time.time() * 1000))[-6:]
        label = label or "Alarma"
        alarms.append({"id": alarm_id, "fire": fire_ts, "label": label, "created": _time.time()})
        self._save_alarms(alarms)
        self._schedule_alarm(alarm_id, fire_ts, label)

        import datetime as _dt
        dt = _dt.datetime.fromtimestamp(fire_ts)
        secs = fire_ts - _time.time()
        if secs < 3600:
            when = f"en {int(secs//60)} min {int(secs%60)} seg"
        else:
            when = dt.strftime("el %d/%m a las %H:%M")
        return f"⏰ Alarma #{alarm_id} configurada — {when}\n📌 {label}"

    def _schedule_alarm(self, alarm_id, fire_ts, label):
        """Spawn a background thread that fires the alarm at fire_ts."""
        import time as _time
        import threading as _th

        def _waiter():
            delay = fire_ts - _time.time()
            if delay > 0:
                _time.sleep(delay)
            # Fire! — update alarm to done
            alarms = self._load_alarms()
            alarms = [a for a in alarms if a.get("id") != alarm_id]
            self._save_alarms(alarms)
            # Notify in UI thread
            self.after(0, lambda: self._fire_alarm_notify(label))

        t = _th.Thread(target=_waiter, daemon=True, name=f"alarm-{alarm_id}")
        t.start()

    def _fire_alarm_notify(self, label):
        """Visual + audio alarm notification."""
        msg = f"⏰ ¡ALARMA, Felipe!\n{label}"
        self.show_pet_speech_bubble(msg, duration=30000)
        chat = getattr(self, "_chat_view", None)
        if chat:
            chat.add_bot(msg)
        try:
            import winsound
            for _ in range(3):
                winsound.Beep(1000, 400)
        except Exception:
            pass
        try:
            self._notify("⏰ Claudy", label)
        except Exception:
            pass

    def _alarm_list(self):
        import time as _time
        import datetime as _dt
        alarms = self._load_alarms()
        if not alarms:
            return "No tienes alarmas pendientes, Felipe.\nUsa: /alarma en 30 minutos [etiqueta]"
        lines = ["⏰ Alarmas pendientes:"]
        for a in sorted(alarms, key=lambda x: x["fire"]):
            dt = _dt.datetime.fromtimestamp(a["fire"])
            secs = a["fire"] - _time.time()
            if secs < 0:
                remain = "(pasada)"
            elif secs < 3600:
                remain = f"en {int(secs//60)} min"
            else:
                remain = dt.strftime("%d/%m %H:%M")
            lines.append(f"  #{a['id']} — {remain} — {a.get('label','')}")
        lines.append("\nUsa /alarma del <id> para borrar.")
        return "\n".join(lines)

    def _alarm_delete(self, alarm_id):
        alarms = self._load_alarms()
        before = len(alarms)
        alarms = [a for a in alarms if a.get("id") != alarm_id]
        self._save_alarms(alarms)
        if len(alarms) < before:
            return f"✅ Alarma #{alarm_id} eliminada."
        return f"⚠️ No encontré la alarma #{alarm_id}."

    def _alarm_delete_all(self):
        """Delete ALL pending alarms."""
        alarms = self._load_alarms()
        count = len(alarms)
        if count == 0:
            return "No tienes alarmas pendientes, Felipe."
        self._save_alarms([])
        self._alarm_badge_hide()
        return f"✅ Eliminé todas las alarmas ({count} en total)."

    def _alarm_delete_by_text(self, text):
        """Delete an alarm matching a time (HH:MM) or label keyword in the text."""
        import re as _re
        import datetime as _dt
        import time as _t
        alarms = self._load_alarms()
        if not alarms:
            return "No tienes alarmas pendientes, Felipe."

        tl = text.lower()

        # Try to match HH:MM or H.MM or H:MM from the text
        m = _re.search(r'(\d{1,2})[.:h](\d{2})', tl)
        if m:
            h, mins = int(m.group(1)), int(m.group(2))
            # Find alarm whose fire time matches hour+minute
            matched = []
            for a in alarms:
                dt = _dt.datetime.fromtimestamp(a["fire"])
                if dt.hour == h and dt.minute == mins:
                    matched.append(a)
            if matched:
                ids = [a["id"] for a in matched]
                remaining = [a for a in alarms if a["id"] not in ids]
                self._save_alarms(remaining)
                labels = ", ".join(a.get("label","") or f"#{a['id']}" for a in matched)
                return f"✅ Alarma(s) de las {h:02d}:{mins:02d} eliminada(s): {labels}"

        # Try to match by label keyword (any word > 3 chars from text that matches label)
        noise = {"alarma", "borra", "elimina", "cancela", "quita", "la", "el", "de", "las",
                 "eliminar", "borrar", "cancelar", "quitar", "que", "esta", "ese", "esa"}
        words = [w for w in _re.split(r'\W+', tl) if len(w) > 3 and w not in noise]
        if words:
            matched = []
            for a in alarms:
                label_low = (a.get("label") or "").lower()
                if any(w in label_low for w in words):
                    matched.append(a)
            if matched:
                ids = [a["id"] for a in matched]
                remaining = [a for a in alarms if a["id"] not in ids]
                self._save_alarms(remaining)
                labels = ", ".join(a.get("label","") or f"#{a['id']}" for a in matched)
                return f"✅ Alarma(s) eliminada(s): {labels}"

        # Last resort: show list and ask for ID
        lines = ["⚠️ No encontré qué alarma borrar. Estas son tus alarmas pendientes:"]
        for a in sorted(alarms, key=lambda x: x["fire"]):
            dt = _dt.datetime.fromtimestamp(a["fire"])
            lines.append(f"  #{a['id']} — {dt.strftime('%H:%M')} — {a.get('label','')}")
        lines.append("\nDi: \"elimina la alarma de las HH:MM\" o \"/alarma del <id>\"")
        return "\n".join(lines)

    def _restore_pending_alarms(self):
        """Call on startup to re-schedule any persisted alarms that haven't fired yet."""
        import time as _time
        alarms = self._load_alarms()
        active = []
        for a in alarms:
            if a["fire"] > _time.time():
                self._schedule_alarm(a["id"], a["fire"], a.get("label", "Alarma"))
                active.append(a)
        if len(active) != len(alarms):
            self._save_alarms(active)  # prune past alarms

    # ══════════════════════════════════════════════════════════════════
    # NOTAS  ─  motor completo
    # ══════════════════════════════════════════════════════════════════
    def _notes_path(self):
        p = os.path.join(os.path.expanduser("~"), ".claudy", "notes.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def _load_notes(self):
        try:
            with open(self._notes_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_notes(self, notes):
        try:
            with open(self._notes_path(), "w", encoding="utf-8") as f:
                json.dump(notes, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _notes_add(self, content):
        import time as _time
        import datetime as _dt
        content = content.strip()
        if not content:
            return "No me diste nada que guardar, Felipe."
        notes = self._load_notes()
        note_id = str(int(_time.time() * 1000))[-6:]
        dt_str = _dt.datetime.now().strftime("%d/%m/%Y %H:%M")
        notes.append({"id": note_id, "content": content, "created": _time.time(), "date": dt_str})
        self._save_notes(notes)
        return f"📝 Nota #{note_id} guardada:\n\"{content}\"\n\nTienes {len(notes)} nota(s) en total."

    def _notes_list(self):
        notes = self._load_notes()
        if not notes:
            return "No tienes notas guardadas, Felipe.\nPrueba: \"anota que debo llamar al médico\""
        lines = [f"📝 Tus notas ({len(notes)}):"]
        for n in sorted(notes, key=lambda x: x.get("created", 0), reverse=True):
            lines.append(f"\n  #{n['id']} — {n.get('date','')}\n  {n['content']}")
        lines.append("\nUsa /nota del <id> para borrar una nota.")
        return "\n".join(lines)

    def _notes_delete(self, note_id):
        notes = self._load_notes()
        before = len(notes)
        notes = [n for n in notes if n.get("id") != note_id]
        self._save_notes(notes)
        if len(notes) < before:
            return f"✅ Nota #{note_id} eliminada."
        return f"⚠️ No encontré la nota #{note_id}."

    def _emit_milestone(self, msg):

        if not getattr(self, "_milestone_active", False):
            return
            
        # Ensure sleep state visual elements are hidden while milestones are running
        canvas = getattr(self, "_canvas", None)
        idle_items = getattr(self, "_idle_items", None)
        if canvas and idle_items:
            for item in idle_items:
                try:
                    canvas.itemconfigure(item, state="hidden")
                except Exception:
                    pass
            self._stop_zzz_animation()
            
        try:
            self._set_response_text(msg)
        except Exception:
            pass

    def _stop_milestone_progress(self):
        self._milestone_active = False
        for aid in getattr(self, "_milestone_after_ids", []) or []:
            try:
                self.after_cancel(aid)
            except Exception:
                pass
        self._milestone_after_ids = []

    def _request_cancel(self):
        """Activa la bandera de cancelación. Los procesos largos (informe) la
        revisan en sus puntos de control y se detienen limpiamente. No mata
        threads a la fuerza (Python no lo permite), pero corta entre pasos."""
        self._cancel_requested = True
        # Detener animaciones/progreso visibles y avisar.
        try:
            self._stop_milestone_progress()
        except Exception:
            pass
        try:
            self._report_generating = False
        except Exception:
            pass
        def _notify():
            try:
                chat = getattr(self, "_chat_view", None)
                if chat:
                    chat.hide_typing()
                    chat.add_system("⛔ Proceso interrumpido por ti (doble ESC). Claudy sigue activa.")
            except Exception:
                pass
            try:
                if getattr(self, "bubble_minimized", False) or not getattr(self, "_webview_visible", True):
                    self.show_pet_speech_bubble("⛔ Interrumpido.\nClaudy sigue lista.", duration=4000)
            except Exception:
                pass
            try:
                self._stop_typing_progress(getattr(self, "_chat_entry_widget", None))
            except Exception:
                pass
        try:
            self.after(0, _notify)
        except Exception:
            pass

    def _is_cancelled(self):
        """True si el usuario pidió interrumpir. Limpia nada — el que arranca un
        proceso nuevo debe resetear la bandera con _reset_cancel()."""
        return bool(getattr(self, "_cancel_requested", False))

    def _reset_cancel(self):
        self._cancel_requested = False

    def _report_progress(self, pct, label, status=None):
        """Actualiza el avance del informe. Muestra el % en la barra de estado y,
        si el chat está oculto/minimizado, en una burbuja en cursiva sobre Claudy.
        Llamable desde el worker (usa self.after para tocar la UI de forma segura)."""
        pct = max(0, min(100, int(pct)))
        text = f"⏳ {label} ({pct}%)"

        def _ui():
            try:
                if status is not None:
                    status.configure(text=text, fg=THEME["accent"])
            except Exception:
                pass
            # Si el chat no está visible, ir mostrando el avance en burbuja.
            chat_hidden = getattr(self, "bubble_minimized", False) or not getattr(self, "_webview_visible", True)
            if chat_hidden:
                try:
                    self.show_pet_speech_bubble(f"Trabajando… {label}\n{pct}% completado", duration=None)
                except Exception:
                    pass

        try:
            self.after(0, _ui)
        except Exception:
            pass

    def _deliver_report_result(self, result, status, entry):
        """Final delivery of the report: show only the file card, never the content."""
        import os as _os
        import re as _re
        # ── Lift the chat-suppression flag BEFORE touching the chat ──
        self._report_generating = False
        try:
            chat = getattr(self, "_chat_view", None)

            # Extract the [CLAUDY_PATH:...] marker from result
            artifact_path = self._extract_artifact_path(result)

            if artifact_path and _os.path.isfile(artifact_path):
                # Save for the toolbar button
                self._remember_file_artifact(artifact_path)
                fname = _os.path.basename(artifact_path)

                # Show completion bubble when chat is hidden or minimized.
                # Al hacer click reabre el chat para ver el resultado.
                if getattr(self, "bubble_minimized", False) or not getattr(self, "_webview_visible", True):
                    self.show_pet_speech_bubble(
                        f"\u2728 Termin\u00e9 de trabajar.\nToca para ver:\n{fname}",
                        duration=None,
                        on_click=lambda: self.show_chat_bubble(),
                    )

                # Append file card to existing chat (preserves history and scrollbar)
                if chat:
                    chat.hide_typing()
                    chat.add_file_card(
                        filename=fname,
                        on_open_file=None,
                        on_open_folder=lambda p=artifact_path: self._open_path_location(p),
                        message="\ud83d\udcc2 Abrir carpeta",
                    )

                done_msg = "\u00a1Informe listo! \u00bfQu\u00e9 m\u00e1s necesitas, Felipe?"
            else:
                # Error path \u2014 show only a short message, never LLM content
                raw_err = _re.sub(r'\n?\[CLAUDY_PATH:.+?\]', '', str(result or "")).strip()
                first_line = (raw_err.splitlines() or [""])[0].strip()
                if len(first_line) > 120 or not first_line:
                    first_line = "No se pudo crear el archivo del informe."
                if chat:
                    chat.hide_typing()
                    chat.add_bot(f"\u26a0\ufe0f {first_line}")
                done_msg = "Algo sali\u00f3 mal. Intenta de nuevo."
                if getattr(self, "bubble_minimized", False) or not getattr(self, "_webview_visible", True):
                    self.show_pet_speech_bubble(f"\u26a0\ufe0f {first_line[:80]}", duration=7000)


            status.configure(text=done_msg, fg=THEME.get("text_secondary", "#aaa"))
            self._stop_typing_progress(entry)
            entry.focus_set()
        except Exception:
            try:
                status.configure(text="Error al mostrar resultado.", fg=THEME.get("accent", "#f55"))
            except Exception:
                pass

    def _gather_web_context(self, topic, max_pages=4, on_status=None):
        """Search the web for the topic and scrape the best pages.

        Returns (context_text, sources) where context_text is the concatenated
        scraped content (truncated) ready to inject into an LLM prompt, and
        sources is a list of {url, title} dicts for the References section.
        This is what makes the report use REAL, current web data instead of
        only the model's own memory.
        """
        from deep_research import scrape_url

        # Formulate a few complementary queries so we don't rely on a single one.
        queries = [
            topic,
            f"{topic} 2025 2026 datos estadisticas",
            f"{topic} analisis tendencias actuales",
        ]

        sources = []
        context_parts = []
        visited = set()

        for query in queries:
            if len([s for s in sources]) >= max_pages:
                break
            try:
                items = self._search_files_online(query, max_results=4)
            except Exception:
                items = []
            for item in items:
                url = (item or {}).get("url", "")
                if not url or url in visited:
                    continue
                if "duckduckgo.com" in url or "brave.com" in url:
                    continue
                visited.add(url)
                if on_status:
                    try:
                        on_status(url)
                    except Exception:
                        pass
                text = ""
                try:
                    text = scrape_url(url)
                except Exception:
                    text = ""
                if not text or text.startswith("Error al extraer"):
                    continue
                context_parts.append(
                    f"FUENTE: {url}\nTITULO: {item.get('title','')}\nCONTENIDO:\n{text[:5000]}\n---\n"
                )
                sources.append({"url": url, "title": item.get("title", "") or url})
                if len(sources) >= max_pages:
                    break

        context_text = "\n".join(context_parts)[:24000]
        return context_text, sources

    def _write_report_by_sections(self, topic, depth, style, language, common_ctx,
                                   web_sources, references, min_words, status):
        """Redacta el informe en varias llamadas cortas (índice + 1 por sección).
        Evita el cuelgue de pedir miles de tokens en una sola llamada a DeepSeek.
        Cada llamada usa timeout=150 y devuelve el Markdown ensamblado."""
        import re as _re

        # Número de secciones de desarrollo según profundidad. MENOS secciones
        # pero más grandes = menos llamadas = más rápido y robusto (antes 7
        # secciones = ~10 llamadas de 22s c/u y se atascaba antes de terminar).
        _dl = (depth or "").lower()
        if "extenso" in _dl or "detallado" in _dl or "profundo" in _dl:
            n_sections = 4
        elif "resumen" in _dl or "ejecutivo" in _dl or "conciso" in _dl:
            n_sections = 2
        else:
            n_sections = 3
        words_per_section = max(400, int(min_words / (n_sections + 1)))

        # Etiquetas localizadas: si el informe es en inglés, los encabezados fijos
        # (título, Introducción, Conclusiones, Referencias) y las instrucciones
        # también deben ir en inglés. Antes estaban hardcodeados en español.
        is_en = "ingl" in (language or "").lower() or "english" in (language or "").lower()
        if is_en:
            L = {
                "title": f"# Report on {topic}",
                "intro_h": "## Introduction", "intro_name": "Introduction",
                "concl_h": "## Conclusions", "concl_name": "Conclusions",
                "refs_h": "## References", "retrieved": "Retrieved from",
                "outline_instr": (
                    f"You are a report planner. Topic: '{topic}'.\n{common_ctx}\n"
                    f"Propose exactly {n_sections} development-section titles (NOT counting "
                    f"Introduction, Conclusions or References) for a professional report, "
                    f"logically ordered and specific to the topic.\n"
                    f"Reply ONLY with the {n_sections} titles, one per line, no numbering, bullets or markdown."
                ),
                "intro_instr": "State the objective, the current relevance of the topic and what the report will cover.",
                "concl_instr": "Synthesize the key findings and close with future perspectives.",
                "fallback_sec": [f"Aspect {i+1} of {topic}" for i in range(n_sections)],
            }
        else:
            L = {
                "title": f"# Informe sobre {topic}",
                "intro_h": "## Introducción", "intro_name": "Introducción",
                "concl_h": "## Conclusiones", "concl_name": "Conclusiones",
                "refs_h": "## Referencias", "retrieved": "Recuperado de",
                "outline_instr": (
                    f"Eres un planificador de informes. Tema: '{topic}'.\n{common_ctx}\n"
                    f"Propón exactamente {n_sections} títulos de secciones de desarrollo (sin contar "
                    f"Introducción, Conclusiones ni Referencias) para un informe profesional sobre el tema, "
                    f"ordenados lógicamente y específicos al tema.\n"
                    f"Responde SOLO con los {n_sections} títulos, uno por línea, sin numeración ni viñetas ni markdown."
                ),
                "intro_instr": "Plantea el objetivo, la relevancia actual del tema y qué cubrirá el informe.",
                "concl_instr": "Sintetiza los hallazgos clave y cierra con perspectivas futuras.",
                "fallback_sec": [f"Aspecto {i+1} de {topic}" for i in range(n_sections)],
            }

        # ── Paso 1: pedir el índice (rápido) ──
        self._report_progress(38, "Diseñando el índice", status)
        outline_prompt = L["outline_instr"]
        outline_resp = self.send_quick_message(
            outline_prompt, _skip_skill_action=True, timeout=150, max_tokens=600)
        section_titles = [
            _re.sub(r'^[\s\-\*\d\.\)]+', '', ln).strip()
            for ln in (outline_resp or "").splitlines() if ln.strip()
        ]
        section_titles = [t for t in section_titles if t][:n_sections]
        if not section_titles:
            section_titles = L["fallback_sec"]

        # Título principal del documento (en el idioma elegido).
        parts = [L["title"] + "\n"]
        written = []  # resúmenes para mantener coherencia entre secciones

        # Refuerzo de idioma en CADA llamada — el modelo derivaba a español.
        lang_rule = (
            f"WRITE THE ENTIRE SECTION IN ENGLISH. Do not use any Spanish."
            if is_en else
            f"ESCRIBE TODA LA SECCIÓN EN ESPAÑOL."
        )

        def _gen(section_heading, instructions, target_words):
            if self._is_cancelled():
                return ""
            prev = " | ".join(written[-4:]) if written else "—"
            p = (
                f"You are writing a professional REPORT about '{topic}' (style: {style}).\n"
                f"{lang_rule}\n"
                f"{common_ctx}\n"
                f"Sections already written: {prev}.\n"
                f"Now write ONLY this section. Start with the markdown heading: '{section_heading}'.\n"
                f"{instructions}\n"
                f"RULES: ~{target_words} words. Real, developed content (no placeholders). "
                f"Use **bold** for key concepts. If you add a table, ALL rows glued together "
                f"(header, |---| and data) with no blank lines and the same number of columns. "
                f"No comments outside the report. Do NOT repeat what other sections already said. "
                f"{lang_rule}"
            )
            import time as _t
            _t0 = _t.time()
            # Timeout por sección moderado: si DeepSeek se atasca en una, fallamos
            # rápido y seguimos con la siguiente en vez de colgar varios minutos.
            txt = self.send_quick_message(p, _skip_skill_action=True, timeout=100, max_tokens=2500)
            txt = _re.sub(r'^/\S+.*$', '', txt or '', flags=_re.MULTILINE).strip()
            msg = f"sección '{section_heading[:30]}' -> {len(txt)} chars en {round(_t.time()-_t0,1)}s"
            print(f"[report] {msg}")
            try:
                self._debug_log("REPORT SECTION", msg)  # persistir en debug.log
            except Exception:
                pass
            return txt

        # ── Paso 2: Introducción ──
        self._report_progress(42, "Redactando la introducción", status)
        intro = _gen(L["intro_h"], L["intro_instr"], words_per_section)
        if intro:
            parts.append(intro)
            written.append(L["intro_name"])

        # ── Paso 3: secciones de desarrollo ──
        for idx, st in enumerate(section_titles):
            if self._is_cancelled():
                break  # el usuario interrumpió: dejamos lo escrito hasta aquí
            pct = 45 + int((idx / max(1, len(section_titles))) * 25)  # 45→70%
            self._report_progress(pct, f"Sección {idx+1}/{len(section_titles)}", status)
            body = _gen(
                f"## {st}",
                ("Develop in depth with several paragraphs. Include a markdown table if it adds comparable data."
                 if is_en else
                 "Desarrolla a fondo con varios párrafos. Incluye una tabla markdown si aporta datos comparables."),
                words_per_section)
            if body:
                parts.append(body)
                written.append(st)

        # ── Paso 4: Conclusiones ──
        self._report_progress(71, "Redactando conclusiones", status)
        concl = _gen(L["concl_h"], L["concl_instr"], max(250, int(words_per_section * 0.7)))
        if concl:
            parts.append(concl)

        # ── Paso 5: Referencias (ensambladas localmente con URLs reales) ──
        _rl = (references or "").lower()
        if web_sources and ("apa" in _rl or "ieee" in _rl or "final" in _rl):
            self._report_progress(73, "Armando referencias", status)
            year = time.strftime("%Y")
            ref_lines = [L["refs_h"] + "\n"]
            for i, s in enumerate(web_sources):
                title = s.get("title") or s.get("url")
                url = s.get("url", "")
                if "ieee" in _rl:
                    ref_lines.append(f"[{i+1}] {title}. {L['retrieved']} {url}")
                else:  # APA o lista al final
                    ref_lines.append(f"- {title}. ({year}). {L['retrieved']} {url}")
            parts.append("\n".join(ref_lines))

        return "\n\n".join(parts)

    def _download_report_images(self, topic, max_images=3):
        """Download Wikimedia CC images for the report topic. Returns list of local file paths."""
        import urllib.request
        import urllib.parse
        import json
        import os
        import re as _re

        img_dir = os.path.join(os.path.expanduser("~"), "Documents", "Claudy", "Informes", "images")
        os.makedirs(img_dir, exist_ok=True)
        downloaded = []

        # Build progressively simpler search terms. El tema puede venir con
        # artículos/muletillas ("la historia de los mundiales hasta hoy") que no
        # matchean ningún título de Wikipedia; probamos variantes más simples y
        # en ambos idiomas (es y en) antes de rendirnos.
        base = (topic or "").strip()
        no_articles = _re.sub(
            r"\b(la|el|los|las|un|una|de|del|sobre|hasta|hoy|dia|día|the|of|history)\b",
            " ", base, flags=_re.IGNORECASE,
        )
        no_articles = _re.sub(r"\s+", " ", no_articles).strip()
        first_words = " ".join(base.split()[:3])
        candidates = []
        for q in (base, no_articles, first_words):
            q = q.strip()
            if q and q not in candidates:
                candidates.append(q)

        print(f"[imgs] candidatos de búsqueda: {candidates}")

        def _find_page(lang, query):
            """Return (lang, page_title) for the best Wikipedia match, or (None, None)."""
            try:
                search_url = (
                    f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
                    f"&srsearch={urllib.parse.quote(query)}&format=json&srlimit=1"
                )
                req = urllib.request.Request(
                    search_url, headers={"User-Agent": "Claudy/4.0 (educational)"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    sdata = json.loads(resp.read())
                results = sdata.get("query", {}).get("search", [])
                if results:
                    return lang, results[0]["title"]
            except Exception as e:
                print(f"[imgs] _find_page({lang}, {query!r}) error: {e}")
            return None, None

        try:
            # Step A: probar (idioma, consulta) hasta encontrar una página real.
            wiki_lang, page_title = None, None
            for query in candidates:
                for lang in ("es", "en"):
                    wiki_lang, page_title = _find_page(lang, query)
                    if page_title:
                        break
                if page_title:
                    break

            if not page_title:
                print("[imgs] ninguna página de Wikipedia encontrada para los candidatos")
                return []
            print(f"[imgs] página encontrada: {wiki_lang}:{page_title}")

            # Step B: Get ALL images listed on that page
            images_url = (
                f"https://{wiki_lang}.wikipedia.org/w/api.php?action=query"
                f"&titles={urllib.parse.quote(page_title)}"
                f"&prop=images&format=json&imlimit=20"
            )
            req2 = urllib.request.Request(
                images_url, headers={"User-Agent": "Claudy/4.0 (educational)"}
            )
            with urllib.request.urlopen(req2, timeout=15) as resp2:
                idata = json.loads(resp2.read())

            pages = idata.get("query", {}).get("pages", {})
            img_titles = []
            for page in pages.values():
                for img in page.get("images", []):
                    name = img.get("title", "")
                    # Filter: only jpg/png, skip icons/flags/small graphics
                    low = name.lower()
                    if any(low.endswith(ext) for ext in (".jpg", ".jpeg", ".png")):
                        if not any(skip in low for skip in ("flag", "icon", "logo", "symbol", "coat", "blank", "map")):
                            img_titles.append(name)
            
            print(f"[imgs] imágenes candidatas tras filtro: {len(img_titles)}")
            if not img_titles:
                return []

            # Step C: Get thumbnail URLs for the filtered images
            safe_base = _re.sub(r'[^\w]', '_', topic)[:30]
            for img_title in img_titles[:max_images * 2]:  # fetch extra in case some fail
                if len(downloaded) >= max_images:
                    break
                try:
                    info_url = (
                        f"https://{wiki_lang}.wikipedia.org/w/api.php?action=query"
                        f"&titles={urllib.parse.quote(img_title)}"
                        "&prop=imageinfo&iiprop=url&iiurlwidth=800&format=json"
                    )
                    req3 = urllib.request.Request(
                        info_url, headers={"User-Agent": "Claudy/4.0"}
                    )
                    with urllib.request.urlopen(req3, timeout=15) as resp3:
                        info = json.loads(resp3.read())

                    for pg in info.get("query", {}).get("pages", {}).values():
                        ii = pg.get("imageinfo", [{}])[0]
                        thumb_url = ii.get("thumburl") or ii.get("url", "")
                        if not thumb_url:
                            continue
                        # Fix protocol-relative URLs from Wikipedia (e.g. //upload.wikimedia.org/...)
                        if thumb_url.startswith("//"):
                            thumb_url = "https:" + thumb_url

                        ext = ".jpg" if ".jpg" in thumb_url.lower() else ".png"
                        local_path = os.path.join(img_dir, f"{safe_base}_{len(downloaded)+1}{ext}")

                        req4 = urllib.request.Request(
                            thumb_url, headers={"User-Agent": "Claudy/4.0"}
                        )
                        with urllib.request.urlopen(req4, timeout=20) as r4:
                            with open(local_path, "wb") as f:
                                f.write(r4.read())

                        # Validate: must be > 5KB (not a placeholder/tiny icon)
                        if os.path.getsize(local_path) > 5120:
                            downloaded.append(local_path)
                        else:
                            os.remove(local_path)
                        break  # one image per img_title iteration
                except Exception as e:
                    print(f"[imgs] descarga de {img_title!r} falló: {e}")
                    continue
        except Exception as e:
            print(f"[imgs] error general descargando imágenes: {e}")

        print(f"[imgs] descargadas finalmente: {len(downloaded)}")
        return downloaded


    # Mensajes de progreso animados dentro del input (cursiva)
    # ============================================================
    def _start_typing_progress(self, entry, prompt=""):
        """Show rotating italic progress messages inside the (disabled) entry."""
        try:
            import tkinter.font as tkfont
        except Exception:
            return
        # Save original font + colors once
        if not hasattr(self, "_entry_original_font"):
            try:
                cur_font = entry.cget("font")
                self._entry_original_font = cur_font
            except Exception:
                self._entry_original_font = None
        # Build an italic variant
        try:
            italic = tkfont.Font(family="Segoe UI", size=9, slant="italic")
            entry.configure(font=italic, fg="#000000", disabledforeground="#000000")
        except Exception:
            pass

        # Pick a rotating sequence biased by command type
        plow = (prompt or "").lower()
        sequences = self._progress_sequence_for(plow)
        self._progress_idx = 0
        self._progress_seq = sequences
        self._progress_active = True

        def _tick():
            if not getattr(self, "_progress_active", False):
                return
            try:
                msg = self._progress_seq[self._progress_idx % len(self._progress_seq)]
                entry.configure(state="normal")
                entry.delete(0, tk.END)
                entry.insert(0, msg)
                entry.configure(state="disabled")
                self._progress_idx += 1
            except Exception:
                pass
            self._progress_after_id = self.after(1600, _tick)

        _tick()

    def _progress_sequence_for(self, plow):
        """Pick contextual progress messages based on the prompt."""
        if any(k in plow for k in ("imagen", "/img", "foto", "dibuja", "ilustra")):
            return ["pintando pixeles...", "mezclando colores...", "afinando trazos...", "casi lista la imagen..."]
        if any(k in plow for k in ("/browse", "buscar en", "internet", "web ", "investigar")):
            return ["navegando la web...", "leyendo paginas...", "filtrando ruido...", "extrayendo lo bueno..."]
        if any(k in plow for k in ("/yt", "youtube", "video")):
            return ["abriendo el video...", "transcribiendo...", "resumiendo ideas..."]
        if any(k in plow for k in ("/ocr", "boleta", "factura")):
            return ["leyendo la imagen...", "reconociendo texto...", "identificando montos..."]
        if any(k in plow for k in ("/code", "codigo", "programa", "script", "funcion", "bug")):
            return ["analizando codigo...", "trazando logica...", "buscando soluciones...", "ensamblando respuesta..."]
        if any(k in plow for k in ("/delegate", "/debate")):
            return ["lanzando subagente...", "asignando contexto...", "iniciando proceso..."]
        if any(k in plow for k in ("/recordar", "recuerdas", "memoria")):
            return ["revisando memoria...", "calculando similitudes...", "ordenando recuerdos..."]
        if any(k in plow for k in ("/aprender", "skill")):
            return ["destilando conversacion...", "armando la skill...", "guardando habilidad..."]
        # Default sequence
        return [
            "leyendo tu mensaje...",
            "revisando contexto...",
            "consultando al modelo...",
            "pensando en la respuesta...",
            "redactando...",
            "casi listo...",
        ]

    def _stop_typing_progress(self, entry):
        """Stop the rotating progress and restore entry appearance."""
        self._progress_active = False
        try:
            aid = getattr(self, "_progress_after_id", None)
            if aid:
                self.after_cancel(aid)
        except Exception:
            pass
        try:
            entry.configure(state="normal")
            entry.delete(0, tk.END)
            if self._entry_original_font:
                entry.configure(font=self._entry_original_font)
            entry.configure(fg=THEME.get("text_primary", "#e8e8f0"))
        except Exception:
            pass

    def _split_answer_pages(self, text, chars_per_page=300):
        """Split answer into pages, trying to break at sentence boundaries."""
        if len(text) <= chars_per_page:
            return [text]
        pages = []
        while text:
            if len(text) <= chars_per_page:
                pages.append(text)
                break
            chunk = text[:chars_per_page]
            # Prefer breaking at sentence end.
            for delim in (". ", "\n", "? ", "! ", ", "):
                idx = chunk.rfind(delim)
                if idx > chars_per_page * 0.5:
                    chunk = chunk[:idx + len(delim)].rstrip()
                    break
            pages.append(chunk)
            text = text[len(chunk):].lstrip()
        return pages

    def _strip_markdown(self, text):
        """Remove markdown formatting for clean human-readable output."""
        import re
        # Bold: **text** or __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        # Italic: *text* or _text_
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
        # Headers: ### text
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Code blocks: ```code```
        text = re.sub(r'```[\w]*\n?(.*?)```', r'\1', text, flags=re.DOTALL)
        # Inline code: `code`
        text = re.sub(r'`(.+?)`', r'\1', text)
        # Links: [text](url)
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        # Horizontal rules
        text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
        # Blockquotes
        text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
        # Clean up excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # ------------------------------------------------------------------
    # Idle auto-hide timer
    # ------------------------------------------------------------------
    def _reset_idle_timer(self):
        """Reset the 60-second auto-hide timer."""
        self._cancel_idle_timer()
        self._last_activity = time.time()
        self._idle_hide_timer = self.after(60000, self._auto_hide_bubble)

    def _cancel_idle_timer(self):
        """Cancel any pending auto-hide timer."""
        if self._idle_hide_timer is not None:
            self.after_cancel(self._idle_hide_timer)
            self._idle_hide_timer = None

    def _auto_hide_bubble(self):
        """Hide the bubble after 60s of inactivity."""
        if self.bubble_win and self.bubble_minimized:
            self.hide_bubble()
        self._idle_hide_timer = None

    def _record_activity(self):
        """Reset idle timer on user activity."""
        if self.bubble_minimized:
            self._reset_idle_timer()

    def _start_zzz_animation(self):
        """Start the floating Zzz animation for minimized state."""
        if self._zzz_anim_running:
            return
        self._zzz_anim_running = True
        self._zzz_tick = 0
        self._animate_zzz()

    def _stop_zzz_animation(self):
        """Stop the Zzz animation."""
        self._zzz_anim_running = False

    NOTEBOOK_PHRASES = [
        "TODO: revisar PR",
        "idea: cache LLM",
        "bug: skin swap",
        "fix: scrollbar",
        "note: refactor",
        "log: build ok",
        "task: tests",
        "hint: parallel",
    ]

    def _start_notebook_animation(self):
        """Robot saca un notebook, teclea una frase y lo guarda."""
        if getattr(self, "_notebook_win", None) is not None:
            return
        if self.bubble_interactive or self.bubble_win is not None:
            return
        self.state = "notebook"
        self._state_start_tick = self.tick
        try:
            import random as _r
            phrase = _r.choice(self.NOTEBOOK_PHRASES)
        except Exception:
            phrase = "note..."

        nb_w, nb_h = 132, 86
        nb = tk.Toplevel(self)
        nb.overrideredirect(True)
        nb.attributes("-topmost", True)
        nb.configure(bg=TRANSPARENT_COLOR)
        try:
            nb.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        nx = self.base_x - nb_w + 14
        ny = self.base_y + 8
        if nx < 0:
            nx = self.base_x + self.width - 14
        nb.geometry(f"{nb_w}x{nb_h}+{nx}+{ny}")

        canvas = tk.Canvas(nb, width=nb_w, height=nb_h, bg=TRANSPARENT_COLOR,
                           highlightthickness=0, bd=0)
        canvas.pack()
        # Notebook body (rounded-ish via two rects)
        canvas.create_rectangle(6, 8, nb_w - 6, nb_h - 6, fill="#fff8c4",
                                outline="#3a3a3a", width=2)
        canvas.create_rectangle(6, 8, nb_w - 6, 20, fill="#e94f4f", outline="")
        # Spiral binding holes
        for i in range(6):
            cx = 16 + i * 18
            canvas.create_oval(cx - 2, 12, cx + 2, 16, fill="#3a3a3a", outline="")
        # Faint guide lines
        for ly in (38, 52, 66):
            canvas.create_line(14, ly, nb_w - 14, ly, fill="#d8cf9a")
        text_id = canvas.create_text(14, 30, anchor="nw", text="",
                                     fill="#1d1d1d", font=("Consolas", 9, "bold"))
        cursor_id = canvas.create_text(14, 30, anchor="nw", text="|",
                                       fill="#1d1d1d", font=("Consolas", 9, "bold"))

        self._notebook_win = nb
        self._notebook_state = {
            "canvas": canvas,
            "text_id": text_id,
            "cursor_id": cursor_id,
            "phrase": phrase,
            "i": 0,
            "saving": False,
        }
        self._tick_notebook()

    def _tick_notebook(self):
        st = getattr(self, "_notebook_state", None)
        if st is None or self._notebook_win is None:
            return
        canvas = st["canvas"]
        try:
            if st["i"] < len(st["phrase"]):
                shown = st["phrase"][: st["i"] + 1]
                canvas.itemconfigure(st["text_id"], text=shown)
                # Move blinking cursor to end of text
                x = 14 + len(shown) * 6
                canvas.coords(st["cursor_id"], x, 30)
                # Blink cursor every other tick
                cur_color = "#1d1d1d" if (st["i"] % 2 == 0) else "#fff8c4"
                canvas.itemconfigure(st["cursor_id"], fill=cur_color)
                st["i"] += 1
                self.after(110, self._tick_notebook)
                return
            if not st["saving"]:
                st["saving"] = True
                canvas.itemconfigure(st["cursor_id"], text="")
                # Flash "Saved" badge
                canvas.create_rectangle(46, 64, 116, 80, fill="#2ec27e",
                                        outline="#1a7a4f", width=1, tags="saved")
                canvas.create_text(81, 72, text="💾 Saved!",
                                   fill="white", font=("Segoe UI", 8, "bold"),
                                   tags="saved")
                self.after(900, self._tick_notebook)
                return
            self._end_notebook_animation()
        except tk.TclError:
            self._end_notebook_animation()

    def _end_notebook_animation(self):
        try:
            if self._notebook_win is not None:
                self._notebook_win.destroy()
        except Exception:
            pass
        self._notebook_win = None
        self._notebook_state = None
        if self.state == "notebook":
            self.state = "idle"

    def _animate_zzz(self):
        """Float vector Zzz text elements for 100% perfect transparent idle animation."""
        if not self._zzz_anim_running:
            return
        canvas = getattr(self, '_bubble_canvas', None)
        if canvas is None or not hasattr(self, '_zzz_texts'):
            return

        self._zzz_tick = (self._zzz_tick + 1) % 60
        t = self._zzz_tick / 60.0

        # 3 Zs floating up, each with its own delayed offset
        zs = [
            {"id": self._zzz_texts[0], "x_base": BUBBLE_MINI_SIZE // 2 - 10, "y_base": BUBBLE_MINI_SIZE // 2 + 15, "delay": 0.0},
            {"id": self._zzz_texts[1], "x_base": BUBBLE_MINI_SIZE // 2 + 2, "y_base": BUBBLE_MINI_SIZE // 2 + 2, "delay": 0.33},
            {"id": self._zzz_texts[2], "x_base": BUBBLE_MINI_SIZE // 2 - 4, "y_base": BUBBLE_MINI_SIZE // 2 - 12, "delay": 0.66},
        ]

        accent = THEME.get("accent", "#c4b5fd")
        secondary = THEME.get("text_secondary", "#8a8499")
        label_col = THEME.get("text_label", "#5f5a6f")

        for z in zs:
            phase = (t - z["delay"]) % 1.0
            rise = phase * 24
            # Gentle horizontal sway
            sway = math.sin(phase * math.tau * 1.5) * 4

            try:
                if phase > 0.8:
                    canvas.itemconfigure(z["id"], state="hidden")
                else:
                    canvas.itemconfigure(z["id"], state="normal")
                    # Smooth visual fade by shifting colors
                    if phase < 0.25:
                        color = accent
                    elif phase < 0.55:
                        color = secondary
                    else:
                        color = label_col
                    canvas.itemconfigure(z["id"], fill=color)

                # Apply position
                canvas.coords(z["id"], z["x_base"] + sway, z["y_base"] - rise)
            except Exception:
                pass

        self.after(60, self._animate_zzz)

    def _sync_pagination_visibility(self, canvas):
        pass  # Pagination removed — scrollbar handles overflow.

    def finish_quick_answer(self, answer, status, entry, _already_shown=False):
        import re
        try:
            clean_answer = self._strip_markdown(answer)

            # Detect explicit file mutation commands emitted by the model.
            write_match = re.search(r'/(?:write|crear-archivo)\s+(.+)', clean_answer, re.IGNORECASE | re.DOTALL)
            append_match = re.search(r'/(?:append|agregar-archivo)\s+(.+)', clean_answer, re.IGNORECASE | re.DOTALL)
            mkdir_match = re.search(r'/(?:mkdir|crear-carpeta)\s+(.+)', clean_answer, re.IGNORECASE | re.DOTALL)
            replace_match = re.search(r'/(?:replace|edit-replace)\s+(.+)', clean_answer, re.IGNORECASE | re.DOTALL)
            docx_match = re.search(r'/(?:docx|create-docx|crear-docx)\s+(.+)', clean_answer, re.IGNORECASE | re.DOTALL)
            xlsx_match = re.search(r'/(?:xlsx|create-xlsx|crear-xlsx|excel)\s+(.+)', clean_answer, re.IGNORECASE | re.DOTALL)
            pptx_match = re.search(r'/(?:pptx|create-pptx|crear-pptx|powerpoint)\s+(.+)', clean_answer, re.IGNORECASE | re.DOTALL)
            pdf_match = re.search(r'/(?:pdf|create-pdf|crear-pdf)\s+(.+)', clean_answer, re.IGNORECASE | re.DOTALL)

            if write_match or append_match or mkdir_match or replace_match or docx_match or xlsx_match or pptx_match or pdf_match:
                try:
                    import claudy_powers as cp
                    if mkdir_match:
                        result = cp.create_folder(mkdir_match.group(1).strip())
                    elif replace_match:
                        parts = [x.strip() for x in replace_match.group(1).split(" | ", 2)]
                        result = cp.replace_in_file(parts[0], parts[1], parts[2]) if len(parts) >= 3 else "Uso: /replace <ruta> | <buscar> | <reemplazo>"
                    elif docx_match:
                        raw = docx_match.group(1)
                        p, content = cp.parse_path_content_arg(raw)
                        result = cp.create_docx(p, content) if p else "Uso: /docx <ruta> | <contenido>"
                    elif pdf_match:
                        raw = pdf_match.group(1)
                        p, content = cp.parse_path_content_arg(raw)
                        result = cp.create_pdf(p, content) if p else "Uso: /pdf <ruta> | <contenido>"
                    elif xlsx_match:
                        raw = xlsx_match.group(1)
                        p, content = cp.parse_path_content_arg(raw)
                        import json
                        try:
                            data = json.loads(content)
                        except Exception:
                            data = [line.split(",") for line in content.split("\n") if line.strip()]
                        result = cp.create_xlsx(p, data) if p else "Uso: /xlsx <ruta> | <contenido CSV/JSON>"
                    elif pptx_match:
                        raw = pptx_match.group(1)
                        p, content = cp.parse_path_content_arg(raw)
                        import json
                        slides = None
                        title = ""
                        subtitle = ""
                        theme = "business"
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict):
                                slides = parsed.get("slides")
                                title = parsed.get("title", "")
                                subtitle = parsed.get("subtitle", "")
                                theme = parsed.get("theme", "business")
                            elif isinstance(parsed, list):
                                slides = parsed
                        except Exception:
                            slides = [{"title": s.strip(), "bullets": ["Detalle"]} for s in content.split("\n") if s.strip()]
                        result = cp.create_pptx(p, slides, title, subtitle, theme) if p else "Uso: /pptx <ruta> | <contenido JSON>"
                    else:
                        raw = (write_match or append_match).group(1)
                        p, content = cp.parse_path_content_arg(raw)
                        result = cp.write_file(p, content, append=bool(append_match)) if p else "Uso: /write <ruta> | <contenido>"
                except Exception as e:
                    result = f"Error aplicando cambio de archivo: {e}"
                self._set_response_text(result)
                status.configure(text="Archivo listo.", fg=THEME["text_secondary"])
                self._stop_typing_progress(entry)
                entry.focus_set()
                return

            # Detect explicit /buscar command
            buscar_match = re.search(r'/buscar\s+(.+)', clean_answer)
            if buscar_match:
                query = buscar_match.group(1).strip()
                self._set_response_text(f"Buscando: {query}...")
                status.configure(text="Buscando en internet...", fg=THEME["accent"])

                def search_worker():
                    try:
                        result = self._web_search_and_answer(query)
                    except Exception as e:
                        result = f"Error buscando: {e}"
                    self.after(0, lambda: self._finish_search_result(result, status, entry))

                threading.Thread(target=search_worker, daemon=True).start()
                return

            # Detect explicit /buscar_archivo command
            buscar_archivo_match = re.search(r'/buscar_archivo\s+(.+)', clean_answer)
            if buscar_archivo_match:
                query = buscar_archivo_match.group(1).strip()
                self._set_response_text(f"Buscando archivo: {query}...")
                status.configure(text="Buscando en tu sistema...", fg=THEME["accent"])

                def file_search_worker():
                    try:
                        result = self._search_files(query)
                    except Exception as e:
                        result = f"Error buscando archivo: {e}"
                    self.after(0, lambda: self._finish_search_result(result, status, entry))

                threading.Thread(target=file_search_worker, daemon=True).start()
                return

            # Detect explicit /webfetch commands (can be one or more)
            webfetch_urls = re.findall(r'/webfetch\s+(\S+)', clean_answer)
            if webfetch_urls:
                self._set_response_text(f"Recopilando datos de {len(webfetch_urls)} fuentes...")
                status.configure(text="Descargando páginas...", fg=THEME["accent"])

                def fetch_worker():
                    combined_results = ""
                    for idx, url in enumerate(webfetch_urls, start=1):
                        try:
                            import urllib.request
                            # Clean up the URL from any trailing punctuation/brackets
                            url_clean = url.strip().strip('"\'()[]').strip()
                            req = urllib.request.Request(url_clean, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(req, timeout=15) as response:
                                html = response.read().decode('utf-8', errors='replace')
                            try:
                                from bs4 import BeautifulSoup
                                soup = BeautifulSoup(html, "html.parser")
                                text = soup.get_text(separator="\n")
                            except Exception:
                                text = re.sub(r'<[^>]+>', '', html)

                            lines = [l.strip() for l in text.splitlines() if l.strip()]
                            clean_text = "\n".join(lines)[:6000]
                            combined_results += f"\n--- CONTENIDO DE FUENTE {idx} ({url_clean}) ---\n{clean_text}\n"
                        except Exception as e:
                            combined_results += f"\n--- ERROR AL ACCEDER A {url} ---\n{e}\n"

                    # Now feed the combined data back to the LLM to write the final report!
                    enhanced_prompt = (
                        f"A continuación tienes la información recopilada de las fuentes:\n"
                        f"{combined_results}\n\n"
                        f"INSTRUCCIONES:\n"
                        f"1. Con base en esta información y tus conocimientos, redacta e introduce el informe solicitado en su totalidad.\n"
                        f"2. Utiliza estrictamente el comando `/docx <ruta> | <contenido>` (o `/crear-docx`) en la primera línea de tu respuesta para crear el archivo Word físicamente en el disco.\n"
                        f"3. La ruta del informe debe ser: '{self._guided_report_data.get('topic', 'Informe')}.docx' (dentro de tu carpeta de documentos o descargas si no se especificó otra).\n"
                        f"4. Estructura el informe con títulos marcados con #, ##, ### para que la maquetación sea perfecta y profesional.\n"
                        f"5. NO omitas el comando `/docx` ni expliques el plan, escribe directamente el comando de creación en tu respuesta."
                    )

                    try:
                        answer = self.send_quick_message(enhanced_prompt, _skip_skill_action=True)
                    except Exception as e:
                        answer = f"Error sintetizando el informe: {e}"

                    self.after(0, lambda: self.finish_quick_answer(answer, status, entry))

                threading.Thread(target=fetch_worker, daemon=True).start()
                return

            # Detect explicit /leer or /read commands
            read_match = re.search(r'/(?:read|leer)\s+(\S+)', clean_answer)
            if read_match:
                path = read_match.group(1).strip().strip('"\'').strip()
                self._set_response_text(f"Leyendo archivo: {os.path.basename(path)}...")
                status.configure(text="Leyendo...", fg=THEME["accent"])

                def read_worker():
                    try:
                        import claudy_powers as cp
                        result = cp.read_file(path)
                    except Exception as e:
                        result = f"Error leyendo: {e}"

                    # Feed back to LLM
                    enhanced_prompt = (
                        f"Contenido del archivo '{path}':\n\n{result}\n\n"
                        f"Continúa con la tarea."
                    )
                    try:
                        answer = self.send_quick_message(enhanced_prompt, _skip_skill_action=True)
                    except Exception as e:
                        answer = f"Error: {e}"
                    self.after(0, lambda: self.finish_quick_answer(answer, status, entry))

                threading.Thread(target=read_worker, daemon=True).start()
                return

            # Fallback: AI said it will search but didn't use a command
            search_phrases = [
                "dame un momento", "voy a buscar", "voy a buscar eso",
                "voy a buscar ese archivo", "voy a buscar ese",
                "dejame buscar", "déjame buscar", "un momento",
                "voy a revisar", "voy a consultar", "voy a verificar",
                "voy a investigar", "dejame revisar", "déjame revisar",
                "te respondo en", "dame un segundo", "espera, dejame",
                "espera, déjame", "ire a buscar", "iré a buscar",
                "voy a checar", "voy a chequear", "voy a mirar",
                "para darte la respuesta", "para responderte",
                "permíteme buscar", "permiteme buscar",
            ]
            if any(p in clean_answer.lower() for p in search_phrases):
                last = getattr(self, '_last_prompt', '')
                # Try to extract search term from last prompt
                term = ""
                # Look for file name with extension
                file_m = re.search(r'\b\S+\.(dll|exe|pdf|txt|docx?|xlsx?|pptx?|zip|rar|7z|jpe?g|png|gif|mp3|mp4|avi|mov|csv|json|xml|py|js|ts|html|css|java|cpp|c|h|go|rs|php|rb|swift|kt|sql|md|log|ini|cfg|bat|ps1|msi|iso)\b', last, re.IGNORECASE)
                if file_m:
                    term = file_m.group(0)
                else:
                    # Try to extract text after search keywords
                    for kw in ["busca", "buscar", "encuentra", "donde esta", "dónde está"]:
                        if kw in last.lower():
                            part = last.lower().split(kw, 1)[1].strip()
                            # Take first meaningful word
                            words = [w for w in part.split() if w not in ("el", "la", "los", "las", "un", "una", "de", "del", "en", "mi", "este", "ese", "aqui", "aquí")]
                            if words:
                                term = words[0].strip(".,!?;:")
                            break
                if term:
                    self._set_response_text(f"Buscando: {term}...")
                    status.configure(text="Buscando...", fg=THEME["accent"])

                    def auto_search_worker():
                        try:
                            # Decide web vs file search based on whether term looks like a file
                            if "." in term:
                                result = self._search_files(term)
                            else:
                                result = self._web_search_and_answer(term)
                        except Exception as e:
                            result = f"Error buscando: {e}"
                        self.after(0, lambda: self._finish_search_result(result, status, entry))

                    threading.Thread(target=auto_search_worker, daemon=True).start()
                    return

            chat = getattr(self, "_chat_view", None)
            if chat is not None:
                try:
                    if not _already_shown:
                        chat.hide_typing()
                    artifact_path = self._extract_artifact_path(clean_answer)
                    if artifact_path:
                        self._remember_file_artifact(artifact_path)
                        if not _already_shown:
                            chat.add_bot(f"¡Hemos terminado! Se ha creado el archivo:\n{os.path.basename(artifact_path)}")
                        chat.add_file_card(
                            filename=os.path.basename(artifact_path),
                            on_open_file=lambda p=artifact_path: self._open_path_file(p),
                            on_open_folder=lambda p=artifact_path: self._open_path_location(p),
                            message="Haz clic en el nombre para abrir la carpeta",
                        )
                    elif not _already_shown:
                        chat.add_bot(clean_answer)
                except Exception:
                    pass
            elif not _already_shown:
                self._set_response_text(self._format_exchange(self._last_prompt, clean_answer))

            done_text = random.choice([
                "¿Qué más necesitas?", "Aquí estoy para lo que sea.", "Dime, ¿qué sigue?",
                "Listo para la siguiente.", "¿Algo más en mente?", "Te escucho.",
            ])
            status.configure(text=done_text, fg=THEME["text_secondary"])
            self._stop_typing_progress(entry)
            entry.focus_set()
        except tk.TclError:
            pass

    def _finish_search_result(self, result, status, entry):
        """Show search result and re-enable input."""
        try:
            clean = self._strip_markdown(result)
            chat = getattr(self, "_chat_view", None)
            if chat is not None:
                chat.hide_typing()
                chat.add_bot(clean)
            else:
                self._set_response_text(self._format_exchange(self._last_prompt, clean))
            status.configure(text="Búsqueda completada.", fg=THEME["text_secondary"])
            self._stop_typing_progress(entry)
            entry.focus_set()
        except tk.TclError:
            pass

    def _history_palette(self):
        """Paleta de la ventana de historial: misma estética navy/neón que la
        ventana de chat de Claudy. Reutiliza el tema del dashboard si ya existe,
        para que ambos paneles se vean idénticos."""
        base = getattr(self, "_dashboard_chat_theme", None)
        if base:
            return dict(base)
        ct = dict(THEME)
        ct.update({
            "bg_bubble": "#030714",
            "bg_bubble_border": "#5b35d8",
            "bg_input": "#071026",
            "bg_input_border": "#20315f",
            "header_bg": "#071026",
            "panel_soft": "#091333",
            "message_bot": "#101a42",
            "message_bot_border": "#324b9a",
            "button_bg": "#0b1538",
            "button_fg": "#dbe6ff",
            "button_hover": "#172862",
            "text_primary": "#f7f9ff",
            "text_secondary": "#9fb2ff",
            "text_label": "#9fb2ff",
            "accent": "#7b3cff",
            "accent_glow": "#58c7ff",
            "accent_dim": "#17245a",
            "divider": "#273c85",
        })
        return ct

    def show_history_window(self):
        # Toggle: if already open, close it.
        if self.history_win is not None:
            self._stop_history_refresh()
            try:
                if self.history_win.winfo_exists():
                    self.history_win.destroy()
            except tk.TclError:
                pass
            self.history_win = None
            return

        messages = self._load_memory()

        # Sombrea THEME localmente con la paleta del chat: todos los THEME[...]
        # de esta ventana adoptan la estética navy/neón sin tocar el tema global.
        THEME = self._history_palette()
        HFONT = "Bahnschrift"
        HFONT_SB = "Bahnschrift SemiBold"

        hist = tk.Toplevel(self)
        hist.title("Ajustes de Claudy")
        hist.configure(bg=THEME["bg_input"])
        hist.geometry("460x750")
        hist.attributes("-topmost", True)
        hist.resizable(False, False)
        self.history_win = hist

        # Apply Windows dark mode title bar native aesthetic
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(hist.winfo_id())
            if not hwnd:
                hwnd = hist.winfo_id()
            value = ctypes.c_int(1)
            res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)
            )
            if res != 0:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 19, ctypes.byref(value), ctypes.sizeof(value)
                )
        except Exception:
            pass

        def _on_close():
            self._stop_history_refresh()
            self.history_win = None
            hist.destroy()

        hist.protocol("WM_DELETE_WINDOW", _on_close)

        shell = tk.Frame(
            hist, bg=THEME["bg_bubble"], bd=0,
            highlightbackground=THEME.get("bg_bubble_border", THEME["accent"]), highlightthickness=1,
        )
        shell.pack(fill="both", expand=True, padx=12, pady=12)

        header_canvas = tk.Canvas(shell, height=74, bg=THEME["bg_bubble"], highlightthickness=0, bd=0)
        header_canvas.pack(fill="x")
        header_canvas.create_rectangle(0, 0, 460, 74, fill=THEME["bg_input"], outline="")
        header_canvas.create_oval(18, 15, 50, 47, fill="#0a1835", outline="#8d4dff", width=3)
        header_canvas.create_polygon(34, 20, 45, 31, 40, 43, 28, 43, 23, 31,
                                     fill=THEME["accent_glow"], outline="")
        header_canvas.create_text(
            66, 22, anchor="w", text="Ajustes y archivo de conversaciones",
            fill=THEME["text_primary"], font=(HFONT_SB, 13),
        )

        total_user = sum(1 for m in messages if m.get("role") == "Usuario")
        total_claudy = max(0, len(messages) - total_user)
        self._hist_header_canvas = header_canvas
        self._hist_count_item = header_canvas.create_text(
            66, 46, anchor="w",
            text=f"{len(messages)} mensajes  |  Tu {total_user}  |  Claudy {total_claudy}",
            fill=THEME["text_secondary"], font=(HFONT, 9),
        )

        # Helpers for interactive hover micro-animations
        def add_button_hover(btn, normal_bg=THEME["bg_bubble"], hover_bg=THEME.get("accent", "#c02dff"), normal_fg=THEME["text_primary"], hover_fg="#ffffff"):
            def on_enter(_e):
                btn.config(bg=hover_bg, fg=hover_fg)
            def on_leave(_e):
                btn.config(bg=normal_bg, fg=normal_fg)
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

        def add_header_hover(header_lbl):
            def on_enter(_e):
                header_lbl.config(bg=THEME.get("panel_soft", THEME.get("accent_dim", THEME["bg_input"])))
            def on_leave(_e):
                header_lbl.config(bg=THEME["bg_input"])
            header_lbl.bind("<Enter>", on_enter)
            header_lbl.bind("<Leave>", on_leave)

        # ── API Key Panel (Collapsible) ──
        api_frame = tk.Frame(
            shell, bg=THEME["bg_input"],
            highlightbackground=THEME.get("bg_bubble_border", THEME["accent"]), highlightthickness=1, bd=0,
        )
        api_frame.pack(side="bottom", fill="x", padx=12, pady=(4, 6))

        api_expanded = [False]

        api_header = tk.Label(
            api_frame, text="▶  🔑 Claves API (Configuración)",
            bg=THEME["bg_input"], fg=THEME["accent_glow"],
            font=(HFONT_SB, 11), cursor="hand2",
            anchor="w", padx=10, pady=8
        )
        api_header.pack(fill="x")
        add_header_hover(api_header)

        api_content = tk.Frame(api_frame, bg=THEME["bg_input"])

        cfg = self.load_claudy_config()
        
        def get_prov_key(cfg, prov):
            prov_cfg = cfg.get("providers", {}).get(prov, {})
            k = prov_cfg.get("key", "")
            if not k:
                keys = prov_cfg.get("keys", [])
                if keys:
                    k = keys[0]
            return k

        opencode_key_val = cfg.get("opencode", {}).get("apiKey", "")
        deepseek_key_val = get_prov_key(cfg, "deepseek")
        openai_key_val = get_prov_key(cfg, "openai")

        def make_key_row(parent, label_text, default_val):
            row = tk.Frame(parent, bg=THEME["bg_input"])
            row.pack(fill="x", padx=10, pady=2)
            lbl = tk.Label(row, text=label_text, bg=THEME["bg_input"], fg=THEME["text_primary"], font=("Segoe UI", 8, "bold"), width=12, anchor="w")
            lbl.pack(side="left")
            ent = tk.Entry(
                row, bg=THEME["bg_bubble"], fg=THEME["text_primary"],
                insertbackground=THEME["text_primary"], font=("Segoe UI", 8),
                relief="flat", bd=1,
                highlightbackground=THEME.get("bg_bubble_border", THEME["bg_bubble"]),
                highlightcolor=THEME["accent"], highlightthickness=1,
            )
            ent.insert(0, default_val)
            ent.pack(side="left", fill="x", expand=True, padx=(4, 0))
            return ent

        opencode_ent = make_key_row(api_content, "OpenCode Key:", opencode_key_val)
        deepseek_ent = make_key_row(api_content, "DeepSeek Key:", deepseek_key_val)
        openai_ent = make_key_row(api_content, "OpenAI Key:", openai_key_val)

        api_status = tk.Label(
            api_content, text="",
            bg=THEME["bg_input"], fg="#2fe6c8",
            font=("Segoe UI", 8, "italic"),
        )
        api_status.pack(anchor="w", padx=10, pady=(2, 2))

        def save_api_keys():
            try:
                new_cfg = self.load_claudy_config()
                if "opencode" not in new_cfg:
                    new_cfg["opencode"] = {}
                new_cfg["opencode"]["apiKey"] = opencode_ent.get().strip()

                if "providers" not in new_cfg:
                    new_cfg["providers"] = {}
                
                if "deepseek" not in new_cfg["providers"]:
                    new_cfg["providers"]["deepseek"] = {}
                ds_val = deepseek_ent.get().strip()
                new_cfg["providers"]["deepseek"]["key"] = ds_val
                new_cfg["providers"]["deepseek"]["keys"] = [ds_val] if ds_val else []

                if "openai" not in new_cfg["providers"]:
                    new_cfg["providers"]["openai"] = {}
                oa_val = openai_ent.get().strip()
                new_cfg["providers"]["openai"]["key"] = oa_val
                new_cfg["providers"]["openai"]["keys"] = [oa_val] if oa_val else []

                cfg_path = os.path.expanduser("~/.claudy/config.json")
                # Encrypt secrets at rest before writing.
                try:
                    if _secure is not None:
                        _secure.encrypt_config_secrets(new_cfg)
                except Exception:
                    pass
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(new_cfg, f, indent=2)

                api_status.config(text="¡Claves guardadas exitosamente!", fg="#2fe6c8")
            except Exception as e:
                api_status.config(text=f"Error al guardar: {e}", fg="#ff4e4e")

        save_btn = tk.Button(
            api_content, text="💾 Guardar Claves",
            command=save_api_keys,
            bg=THEME["bg_bubble"], fg=THEME["text_primary"],
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            activebackground=THEME["accent"], activeforeground="#ffffff",
            padx=10, pady=4, bd=0,
        )
        save_btn.pack(anchor="e", padx=10, pady=(2, 6))
        add_button_hover(save_btn)

        def toggle_api_content(_e=None):
            if api_expanded[0]:
                api_content.pack_forget()
                api_header.config(text="▶  🔑 Claves API (Configuración)")
                api_expanded[0] = False
            else:
                api_content.pack(fill="x")
                api_header.config(text="▼  🔑 Claves API (Configuración)")
                api_expanded[0] = True

        api_header.bind("<Button-1>", toggle_api_content)

        # ── Skin picker (Collapsible) ──
        skin_frame = tk.Frame(
            shell, bg=THEME["bg_input"],
            highlightbackground=THEME.get("bg_bubble_border", THEME["accent"]), highlightthickness=1, bd=0,
        )
        skin_frame.pack(side="bottom", fill="x", padx=12, pady=(4, 6))

        skin_expanded = [False]

        skin_header = tk.Label(
            skin_frame, text="▶  🎨 Skin de Claudy",
            bg=THEME["bg_input"], fg=THEME["accent_glow"],
            font=(HFONT_SB, 11), cursor="hand2",
            anchor="w", padx=10, pady=8
        )
        skin_header.pack(fill="x")
        add_header_hover(skin_header)

        skin_content = tk.Frame(skin_frame, bg=THEME["bg_input"])

        tk.Label(
            skin_content,
            text="Elige el aspecto de Claudy (cambio en vivo):",
            bg=THEME["bg_input"], fg=THEME["text_secondary"],
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=10, pady=(0, 6))

        btn_row = tk.Frame(skin_content, bg=THEME["bg_input"])
        btn_row.pack(fill="x", padx=10, pady=(0, 8))

        status_label = tk.Label(
            skin_content, text="",
            bg=THEME["bg_input"], fg=THEME["accent"],
            font=("Segoe UI", 8, "italic"),
        )
        status_label.pack(anchor="w", padx=10, pady=(0, 8))

        def make_skin_btn(parent, label, skin_name):
            btn = tk.Button(
                parent, text=label,
                command=lambda: self._switch_skin(skin_name, status_label),
                bg=THEME["bg_bubble"], fg=THEME["text_primary"],
                font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
                activebackground=THEME["accent"], activeforeground="#ffffff",
                padx=12, pady=6, bd=0,
            )
            add_button_hover(btn)
            return btn

        make_skin_btn(btn_row, "🤖 Robot", "robot").pack(side="left", padx=(0, 6))
        make_skin_btn(btn_row, "🦀 Cangrejo", "crab").pack(side="left", padx=(0, 6))
        make_skin_btn(btn_row, "🖼️ Custom...", "custom").pack(side="left")

        def toggle_skin_content(_e=None):
            if skin_expanded[0]:
                skin_content.pack_forget()
                skin_header.config(text="▶  🎨 Skin de Claudy")
                skin_expanded[0] = False
            else:
                skin_content.pack(fill="x")
                skin_header.config(text="▼  🎨 Skin de Claudy")
                skin_expanded[0] = True

        skin_header.bind("<Button-1>", toggle_skin_content)

        # ── Theme picker frame (Collapsible) ──
        theme_frame = tk.Frame(
            shell, bg=THEME["bg_input"],
            highlightbackground=THEME.get("bg_bubble_border", THEME["accent"]), highlightthickness=1, bd=0,
        )
        theme_frame.pack(side="bottom", fill="x", padx=12, pady=(4, 6))

        theme_expanded = [False]

        theme_header = tk.Label(
            theme_frame, text="▶  ✦ Tema de Claudy",
            bg=THEME["bg_input"], fg=THEME["accent_glow"],
            font=(HFONT_SB, 11), cursor="hand2",
            anchor="w", padx=10, pady=8
        )
        theme_header.pack(fill="x")
        add_header_hover(theme_header)

        theme_content = tk.Frame(theme_frame, bg=THEME["bg_input"])

        tk.Label(
            theme_content,
            text="Personaliza el estilo visual del chat bubble:",
            bg=THEME["bg_input"], fg=THEME["text_secondary"],
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=10, pady=(0, 6))

        theme_btn_row = tk.Frame(theme_content, bg=THEME["bg_input"])
        theme_btn_row.pack(fill="x", padx=10, pady=(0, 8))

        theme_status_label = tk.Label(
            theme_content, text="",
            bg=THEME["bg_input"], fg=THEME["accent"],
            font=("Segoe UI", 8, "italic"),
        )
        theme_status_label.pack(anchor="w", padx=10, pady=(0, 8))

        def _on_theme_select(theme_key):
            try:
                idx = _THEME_KEYS.index(theme_key)
                self._toggle_theme(specific_idx=idx)
                theme_status_label.config(text=f"Tema cambiado a: {theme_key.capitalize()} ✦")
                chat_view = getattr(self, "_chat_view", None)
                if chat_view is not None:
                    self._chat_history_buffer = list(chat_view._messages)
                try:
                    if getattr(self, "bubble_win", None) is not None:
                        self.bubble_win.destroy()
                        self.bubble_win = None
                except Exception:
                    pass
                self.after(50, self.show_chat_bubble)
                try:
                    hist.destroy()
                except Exception:
                    pass
                self.after(100, self.show_history_window)
            except Exception as e:
                theme_status_label.config(text=f"Error: {e}")

        def make_theme_btn(parent, label, theme_key):
            btn = tk.Button(
                parent, text=label,
                command=lambda: _on_theme_select(theme_key),
                bg=THEME["bg_bubble"], fg=THEME["text_primary"],
                font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
                activebackground=THEME["accent"], activeforeground="#ffffff",
                padx=12, pady=6, bd=0,
            )
            add_button_hover(btn)
            return btn

        make_theme_btn(theme_btn_row, "✦ Glass", "glass").pack(side="left", padx=(0, 6))
        make_theme_btn(theme_btn_row, ">_ Terminal", "terminal").pack(side="left", padx=(0, 6))
        make_theme_btn(theme_btn_row, "✍ Editorial", "editorial").pack(side="left")

        def toggle_theme_content(_e=None):
            if theme_expanded[0]:
                theme_content.pack_forget()
                theme_header.config(text="▶  ✦ Tema de Claudy")
                theme_expanded[0] = False
            else:
                theme_content.pack(fill="x")
                theme_header.config(text="▼  ✦ Tema de Claudy")
                theme_expanded[0] = True

        theme_header.bind("<Button-1>", toggle_theme_content)

        # ── Alarmas y recordatorios (Collapsible) ──
        alarms_frame = tk.Frame(
            shell, bg=THEME["bg_input"],
            highlightbackground=THEME.get("bg_bubble_border", THEME["accent"]), highlightthickness=1, bd=0,
        )
        alarms_frame.pack(side="bottom", fill="x", padx=12, pady=(4, 6))

        alarms_expanded = [False]
        alarms_data = self._load_alarms()
        alarms_count = len(alarms_data)

        alarms_header = tk.Label(
            alarms_frame,
            text=f"▶  ⏰ Alarmas y recordatorios ({alarms_count})",
            bg=THEME["bg_input"], fg=THEME["accent_glow"],
            font=(HFONT_SB, 11), cursor="hand2",
            anchor="w", padx=10, pady=8,
        )
        alarms_header.pack(fill="x")
        add_header_hover(alarms_header)

        alarms_content = tk.Frame(alarms_frame, bg=THEME["bg_input"])

        alarms_list_frame = tk.Frame(alarms_content, bg=THEME["bg_bubble"])
        alarms_list_frame.pack(fill="x", padx=10, pady=(4, 6))

        alarms_text = tk.Text(
            alarms_list_frame, bg=THEME["bg_bubble"], fg=THEME["text_primary"],
            font=("Consolas", 9), wrap="word", height=8,
            relief="flat", bd=0, padx=8, pady=6,
            highlightthickness=0, state="disabled",
            selectbackground=THEME["accent"], selectforeground="#ffffff",
        )
        alarms_text.pack(fill="both", expand=True)

        def _refresh_alarms_text():
            import time as _t, datetime as _dt
            alarms = self._load_alarms()
            alarms_text.configure(state="normal")
            alarms_text.delete("1.0", "end")
            if not alarms:
                alarms_text.insert("end", "Sin alarmas pendientes.\nUsa: /alarma en 30 minutos [etiqueta]")
            else:
                for a in sorted(alarms, key=lambda x: x.get("fire", 0)):
                    fire = a.get("fire", 0)
                    secs = fire - _t.time()
                    if secs < 0:
                        when = "(pasada)"
                    elif secs < 3600:
                        when = f"en {int(secs//60)} min"
                    else:
                        when = _dt.datetime.fromtimestamp(fire).strftime("%d/%m %H:%M")
                    label = a.get("label", "") or "(sin etiqueta)"
                    alarms_text.insert("end", f"#{a.get('id','?')}  {when}  —  {label}\n")
            alarms_text.configure(state="disabled")
            alarms_header.config(text=f"{'▼' if alarms_expanded[0] else '▶'}  ⏰ Alarmas y recordatorios ({len(alarms)})")

        _refresh_alarms_text()

        alarms_btn_row = tk.Frame(alarms_content, bg=THEME["bg_input"])
        alarms_btn_row.pack(fill="x", padx=10, pady=(0, 6))

        def _refresh_btn():
            _refresh_alarms_text()
        def _delete_all_btn():
            self._alarm_delete_all()
            _refresh_alarms_text()

        refresh_btn = tk.Button(
            alarms_btn_row, text="🔄 Refrescar", command=_refresh_btn,
            bg=THEME["bg_bubble"], fg=THEME["text_primary"],
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            activebackground=THEME["accent"], activeforeground="#ffffff",
            padx=10, pady=4, bd=0,
        )
        refresh_btn.pack(side="left", padx=(0, 6))
        add_button_hover(refresh_btn)

        delete_btn = tk.Button(
            alarms_btn_row, text="🗑️ Borrar todas", command=_delete_all_btn,
            bg=THEME["bg_bubble"], fg="#ff8888",
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            activebackground="#ff4e4e", activeforeground="#ffffff",
            padx=10, pady=4, bd=0,
        )
        delete_btn.pack(side="left")
        add_button_hover(delete_btn, normal_fg="#ff8888", hover_bg="#ff4e4e", hover_fg="#ffffff")

        def toggle_alarms_content(_e=None):
            alarms_expanded[0] = not alarms_expanded[0]
            if alarms_expanded[0]:
                alarms_content.pack(fill="x")
            else:
                alarms_content.pack_forget()
            _refresh_alarms_text()

        alarms_header.bind("<Button-1>", toggle_alarms_content)

        # ── Message frame (toma el espacio restante en el medio) ──
        frame = tk.Frame(
            shell, bg=THEME["bg_bubble"],
            highlightbackground=THEME.get("bg_bubble_border", THEME["accent"]), highlightthickness=1, bd=0,
        )
        frame.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        scrollbar = tk.Scrollbar(
            frame, width=7, bg=THEME["bg_bubble_border"],
            troughcolor=THEME["bg_input"], activebackground=THEME["accent"],
            relief="flat", bd=0, highlightthickness=0,
        )
        scrollbar.pack(side="right", fill="y")

        text_widget = tk.Text(
            frame, bg=THEME["bg_bubble"], fg=THEME["text_primary"],
            font=("Segoe UI", 9), wrap="word",
            yscrollcommand=scrollbar.set, state="disabled",
            highlightthickness=0, bd=0, padx=8, pady=8,
            cursor="arrow", relief="flat", spacing1=2, spacing2=2, spacing3=10,
            selectbackground=THEME["accent"], selectforeground="#ffffff",
        )
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text_widget.yview)

        user_bg_hex = THEME.get("accent_dim", "#18234f")
        claudy_bg_hex = THEME.get("message_bot", THEME["bg_input"])

        text_widget.tag_configure("user_name", foreground=THEME["text_primary"], font=(HFONT_SB, 9),
                                  background=user_bg_hex, lmargin1=12, lmargin2=12,
                                  rmargin=56, spacing1=8, spacing3=0)
        text_widget.tag_configure("user_body", foreground=THEME["text_secondary"], font=(HFONT, 10),
                                  background=user_bg_hex, lmargin1=12, lmargin2=12,
                                  rmargin=56, spacing3=10)
        text_widget.tag_configure("claudy_name", foreground=THEME["accent_glow"], font=(HFONT_SB, 9),
                                  background=claudy_bg_hex, lmargin1=56, lmargin2=56,
                                  rmargin=12, spacing1=8, spacing3=0)
        text_widget.tag_configure("claudy_body", foreground=THEME["text_primary"], font=(HFONT, 10),
                                  background=claudy_bg_hex, lmargin1=56, lmargin2=56,
                                  rmargin=12, spacing3=10)
        text_widget.tag_configure("time", foreground=THEME["text_secondary"], font=(HFONT, 7),
                                  lmargin1=12, lmargin2=12, rmargin=12, spacing3=3)
        text_widget.tag_configure("empty", foreground=THEME["text_secondary"], font=(HFONT_SB, 11),
                                  justify="center", spacing1=90)

        text_widget.configure(state="normal")
        if not messages:
            text_widget.insert("end", "Aun no hay conversaciones guardadas.\n", "empty")
        for msg in messages:
            is_user = msg["role"] == "Usuario"
            role_label = "Tu" if is_user else "Claudy"
            t = msg.get("time", "")
            if t:
                text_widget.insert("end", f"{t}\n", "time")
            text_widget.insert("end", f"  {role_label}  \n", "user_name" if is_user else "claudy_name")
            text_widget.insert("end", f"{msg['text']}\n\n", "user_body" if is_user else "claudy_body")
        text_widget.configure(state="disabled")
        text_widget.see("end")

        # Mantener el historial eterno actualizado EN VIVO mientras la ventana esté abierta.
        self._hist_text_widget = text_widget
        self._hist_rendered_count = len(messages)
        self._history_refresh_loop()

    def _history_append_new(self):
        """Agrega al historial solo los mensajes nuevos desde el último render
        (sin reconstruir todo, conservando el scroll si Felipe está al final)."""
        tw = getattr(self, "_hist_text_widget", None)
        if tw is None:
            return
        try:
            if not tw.winfo_exists():
                return
        except tk.TclError:
            return
        msgs = self._load_memory()
        start = getattr(self, "_hist_rendered_count", 0)
        if len(msgs) <= start:
            return
        try:
            at_bottom = tw.yview()[1] >= 0.999
        except tk.TclError:
            at_bottom = True
        tw.configure(state="normal")
        for msg in msgs[start:]:
            is_user = msg.get("role") == "Usuario"
            role_label = "Tu" if is_user else "Claudy"
            t = msg.get("time", "")
            if t:
                tw.insert("end", f"{t}\n", "time")
            tw.insert("end", f"  {role_label}  \n", "user_name" if is_user else "claudy_name")
            tw.insert("end", f"{msg.get('text','')}\n\n", "user_body" if is_user else "claudy_body")
        tw.configure(state="disabled")
        self._hist_rendered_count = len(msgs)
        if at_bottom:
            tw.see("end")
        # Actualizar el contador del encabezado.
        canvas = getattr(self, "_hist_header_canvas", None)
        item = getattr(self, "_hist_count_item", None)
        if canvas is not None and item is not None:
            total_user = sum(1 for m in msgs if m.get("role") == "Usuario")
            total_claudy = max(0, len(msgs) - total_user)
            try:
                canvas.itemconfigure(
                    item,
                    text=f"{len(msgs)} mensajes  |  Tu {total_user}  |  Claudy {total_claudy}",
                )
            except tk.TclError:
                pass

    def _history_refresh_loop(self):
        """Poll ligero (1.5s) que mantiene la ventana de historial sincronizada."""
        win = getattr(self, "history_win", None)
        if win is None:
            return
        try:
            if not win.winfo_exists():
                self.history_win = None
                return
        except tk.TclError:
            self.history_win = None
            return
        try:
            self._history_append_new()
        except Exception:
            pass
        self._hist_refresh_job = self.after(1500, self._history_refresh_loop)

    def _stop_history_refresh(self):
        job = getattr(self, "_hist_refresh_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass
            self._hist_refresh_job = None
        self._hist_text_widget = None

    def _reload_frames(self):
        """Recarga los PNG frames desde disco y actualiza el label en vivo."""
        try:
            new_frames = [tk.PhotoImage(file=path) for path in ASSET_FRAMES]
            self.frames = new_frames
            self.frame_index = 0
            self.img = self.frames[0]
            self.label.configure(image=self.img)
            self.update_idletasks()
        except Exception as e:
            print(f"[!] Error recargando frames: {e}")
        # Refresh motion system for the new skin (squash/stretch source + profile cache)
        try:
            self._skin_name = self._detect_skin_name()
            self._cur_scaled_img = None
            self._rebuild_pil_frames()
        except Exception:
            pass

    def _switch_skin(self, skin_name, status_label=None):
        """Cambia el skin de Claudy en vivo (sin reiniciar)."""
        import shutil
        flag_path = os.path.join(SCRIPT_DIR, "custom_skin.flag")
        backup_dir = os.path.join(SCRIPT_DIR, "backup_original")

        try:
            if skin_name == "robot":
                # Borrar flag y regenerar frames procedurales del robot
                if os.path.exists(flag_path):
                    os.remove(flag_path)
                # Forzar regeneración: borrar PNGs actuales y llamar generate_sprite
                for p in ASSET_FRAMES:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
                generate_sprite()
                self._reload_frames()
                msg = "🤖 Robot activado."
            elif skin_name == "crab":
                # Copiar frames del backup (cangrejo original)
                if not os.path.isdir(backup_dir):
                    msg = "No hay backup del cangrejo disponible."
                else:
                    for i in range(6):
                        src = os.path.join(backup_dir, f"claudy_orbit_frame_{i}.png")
                        dst = os.path.join(SCRIPT_DIR, f"claudy_orbit_frame_{i}.png")
                        if os.path.exists(src):
                            shutil.copy(src, dst)
                    with open(flag_path, "w") as f:
                        f.write("source: backup_original (crab)\n")
                    self._reload_frames()
                    msg = "🦀 Cangrejo activado."
            elif skin_name == "custom":
                from tkinter import filedialog
                path = filedialog.askopenfilename(
                    title="Elige una imagen para el skin",
                    filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp *.bmp")],
                )
                if not path:
                    return
                try:
                    from skin_swap import create_animated_frames
                except ImportError:
                    sys.path.insert(0, SCRIPT_DIR)
                    from skin_swap import create_animated_frames
                create_animated_frames(path, SCRIPT_DIR, frame_size=128)
                with open(flag_path, "w") as f:
                    f.write(f"source: {path}\n")
                self._reload_frames()
                msg = "🖼️ Skin custom aplicado."
            else:
                msg = f"Skin desconocido: {skin_name}"

            # Force the chat view to redraw all bot messages using the new skin avatar!
            chat = getattr(self, "_chat_view", None)
            if chat is not None:
                chat.apply_theme(THEME)
        except Exception as e:
            msg = f"Error al cambiar skin: {e}"

        if status_label is not None:
            try:
                status_label.configure(text=msg)
            except tk.TclError:
                pass

    def _subagents_dir(self):
        d = os.path.join(os.path.expanduser("~"), ".claudy", "subagents")
        os.makedirs(d, exist_ok=True)
        return d

    def _spawn_subagent(self, task):
        if not task:
            return False, "Falta tarea. Usa: /delegate <tarea>"
        # Limit concurrent subagents to 3
        active = [f for f in os.listdir(self._subagents_dir()) if f.endswith(".json")]
        running = 0
        for fn in active:
            try:
                with open(os.path.join(self._subagents_dir(), fn), "r", encoding="utf-8") as f:
                    if json.load(f).get("status") == "running":
                        running += 1
            except Exception:
                pass
        if running >= 3:
            return False, f"Limite alcanzado ({running}/3 subagentes corriendo). Usa /subagents."
        sid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_") + str(int(time.time() * 1000))[-4:]
        script = os.path.join(SCRIPT_DIR, "subagent_runner.py")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(
                [sys.executable, "-u", script, sid, task],
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            return False, f"Error spawn: {e}"
        return True, f"Subagente lanzado: {sid}\nUsa /subagents para ver estado."

    def _list_subagents(self):
        items = []
        for fn in sorted(os.listdir(self._subagents_dir()), reverse=True)[:15]:
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(self._subagents_dir(), fn), "r", encoding="utf-8") as f:
                    d = json.load(f)
                items.append((d.get("id", fn[:-5]), d.get("status", "?"), d.get("task", "")[:60]))
            except Exception:
                pass
        if not items:
            return "Sin subagentes."
        lines = [f"[{s}] {i}: {t}" for i, s, t in items]
        return "\n".join(lines)

    def _get_subagent_result(self, sid):
        path = os.path.join(self._subagents_dir(), f"{sid}.json")
        if not os.path.exists(path):
            return f"No existe: {sid}"
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("status") != "done":
                return f"Aun corriendo: {sid}"
            return d.get("result", "(vacio)")
        except Exception as e:
            return f"Error: {e}"

    def _batches_dir(self):
        d = os.path.join(os.path.expanduser("~"), ".claudy", "batches")
        os.makedirs(d, exist_ok=True)
        return d

    def _run_batch(self, file_path, concurrency=3):
        """
        Run prompts from a text file (one per line) in parallel.
        Output: ShareGPT-style JSONL to ~/.claudy/batches/<timestamp>.jsonl
        """
        path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.exists(path):
            return False, f"No existe: {path}"
        try:
            with open(path, "r", encoding="utf-8") as f:
                prompts = [ln.strip() for ln in f if ln.strip()]
        except Exception as e:
            return False, f"Error leyendo: {e}"
        if not prompts:
            return False, "Archivo vacio."

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(self._batches_dir(), f"{ts}.jsonl")
        results = [None] * len(prompts)

        from concurrent.futures import ThreadPoolExecutor

        def _one(i_p):
            i, p = i_p
            try:
                resp = self.send_quick_message(p, _skip_skill_action=True)
            except Exception as e:
                resp = f"ERROR: {e}"
            results[i] = {
                "conversations": [
                    {"from": "human", "value": p},
                    {"from": "gpt", "value": resp},
                ],
            }
            return i

        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            list(ex.map(_one, enumerate(prompts)))

        with open(out_path, "w", encoding="utf-8") as f:
            for r in results:
                if r:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

        return True, f"Batch listo: {len(prompts)} prompts\nSalida: {out_path}"

    # --- F3.6 attachment handling ---
    def _entry_attachment_question(self, entry_widget):
        """Return optional user guidance from the input without treating placeholders as text."""
        if entry_widget is None:
            return ""
        try:
            question = entry_widget.get().strip()
            if question in ("Escribe aqui...", "Escribe tu mensaje..."):
                return ""
            if question:
                entry_widget.delete(0, tk.END)
            return question
        except Exception:
            return ""

    def _attachment_status(self, status_widget, text, color=None):
        if status_widget is None:
            return
        theme = getattr(self, "_dashboard_chat_theme", THEME)
        def _apply():
            try:
                status_widget.configure(text=text, fg=color or theme.get("accent_glow", THEME["accent"]))
            except Exception:
                pass
        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    def _parse_dropped_paths(self, raw):
        raw = raw or ""
        try:
            return [p for p in self.tk.splitlist(raw) if p]
        except Exception:
            import shlex
            return [p for p in shlex.split(raw.replace("{", '"').replace("}", '"')) if p]

    def _pick_and_analyze_attachment(self, status_widget=None, entry_widget=None):
        try:
            from tkinter import filedialog
            paths = filedialog.askopenfilenames(
                title="Adjuntar archivo para analizar",
                filetypes=[
                    ("Archivos compatibles", "*.pdf *.docx *.xlsx *.xls *.pptx *.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                    ("PDF", "*.pdf"),
                    ("Word", "*.docx"),
                    ("Excel", "*.xlsx *.xls"),
                    ("PowerPoint", "*.pptx"),
                    ("Imagenes", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                    ("Todos los archivos", "*.*"),
                ],
            )
        except Exception as e:
            self._set_response_text(f"No pude abrir el selector de archivos: {e}")
            return
        if not paths:
            return
        question = self._entry_attachment_question(entry_widget)
        for path in list(paths)[:6]:
            self._analyze_attachment_file(path, status_widget, None, question=question)
        if len(paths) > 6:
            self._set_response_text("Para no saturar la sesion, analizare solo los primeros 6 archivos.")

    def _handle_dropped_file(self, event, status_widget, entry_widget):
        try:
            self._set_state_briefly("surprised", 700)
        except Exception:
            pass
        raw = event.data if event else ""
        paths = self._parse_dropped_paths(raw)
        if not paths:
            return
        question = self._entry_attachment_question(entry_widget)
        for path in paths[:6]:
            self._analyze_attachment_file(path, status_widget, None, question=question)
        if len(paths) > 6:
            self._set_response_text("Arrastraste muchos archivos. Analizare solo los primeros 6.")

    def _analyze_attachment_file(self, path, status_widget=None, entry_widget=None, question=None):
        path = os.path.abspath(os.path.expanduser(str(path or "").strip().strip('"').strip("'")))
        if not os.path.exists(path):
            self._set_response_text(f"No existe: {path}")
            return
        if os.path.isdir(path):
            self._set_response_text("Ese adjunto es una carpeta. Usa el boton de carpeta para analizarla completa.")
            return
        if question is None:
            question = self._entry_attachment_question(entry_widget)

        ext = os.path.splitext(path)[1].lower()
        basename = os.path.basename(path)
        image_exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
        doc_exts = (".pdf", ".docx", ".xlsx", ".xls", ".pptx")
        display_user = f"Adjunto: {basename}"
        if question:
            display_user += f"\nPregunta: {question}"

        chat = getattr(self, "_chat_view", None)
        if chat is not None:
            try:
                chat.add_user(display_user)
                chat.show_typing()
            except Exception:
                pass
        else:
            self._set_response_text(f"Analizando archivo: {basename}")

        self._attachment_status(status_widget, f"Analizando {basename}...")

        def _finish(answer, status_text="Archivo analizado"):
            def _show():
                try:
                    if chat is not None:
                        chat.hide_typing()
                except Exception:
                    pass
                self._set_response_text(answer)
                theme = getattr(self, "_dashboard_chat_theme", THEME)
                self._attachment_status(status_widget, status_text, theme.get("text_secondary", THEME["text_secondary"]))
                if getattr(self, "_voice_enabled", False):
                    try:
                        _tts_speak(str(answer)[:500])
                    except Exception:
                        pass
            self.after(0, _show)

        def _run():
            try:
                if ext in image_exts:
                    prompt = question or "Analiza esta imagen en espanol. Describe lo importante y extrae cualquier texto visible."
                    answer = self._analyze_image_native(path, prompt)
                    self._save_memory("Usuario", display_user)
                    self._save_memory("Claudy", answer)
                    _finish(answer, "Imagen analizada")
                    return

                if ext not in doc_exts:
                    self._attachment_status(status_widget, "Intentando leer archivo como texto...")

                text = self._extract_attachment_text(path)
                if not text.strip():
                    _finish(f"No pude extraer contenido legible de {basename}.")
                    return

                instruction = question or (
                    "Resume el archivo, identifica los puntos importantes, datos clave, "
                    "posibles problemas y acciones recomendadas."
                )
                prompt = (
                    "Felipe adjunto un archivo para analizar.\n"
                    f"Archivo: {basename}\n"
                    f"Tipo: {ext or 'sin extension'}\n\n"
                    "Contenido extraido del archivo (puede estar truncado):\n"
                    "```text\n"
                    f"{text}\n"
                    "```\n\n"
                    f"Instruccion del usuario: {instruction}\n\n"
                    "Responde en espanol claro. Si hay tablas, destaca patrones, totales, anomalias "
                    "y conclusiones utiles."
                )
                answer = self.send_quick_message(prompt, _skip_skill_action=True, timeout=120)
                # Persistir el análisis en memoria de agentes (+ Obsidian) para contexto futuro.
                try:
                    self._save_memory("Usuario", display_user)
                    self._save_memory("Claudy", f"[Análisis de archivo: {basename}] {answer}")
                except Exception:
                    pass
                _finish(answer)
            except Exception as e:
                _finish(f"Error analizando {basename}: {e}", "Error al analizar archivo")

        threading.Thread(target=_run, daemon=True).start()

    def _extract_attachment_text(self, path, max_chars=12000):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            text = self._read_pdf_text(path)
        elif ext == ".docx":
            text = self._read_docx_text(path)
        elif ext in (".xlsx", ".xls"):
            text = self._read_excel_text(path)
        elif ext == ".pptx":
            text = self._read_pptx_text(path)
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read(max_chars + 1)
        text = (text or "").strip()
        if len(text) > max_chars:
            return text[:max_chars] + "\n\n[Contenido truncado por longitud.]"
        return text

    def _read_docx_text(self, path):
        try:
            from docx import Document
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "python-docx"])
            from docx import Document
        doc = Document(path)
        parts = []
        for p in doc.paragraphs:
            txt = (p.text or "").strip()
            if txt:
                parts.append(txt)
        for idx, table in enumerate(doc.tables[:20], 1):
            rows = []
            for row in table.rows[:60]:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                parts.append(f"\nTabla {idx}\n" + "\n".join(rows))
        return "\n".join(parts)

    def _read_excel_text(self, path):
        try:
            import pandas as pd
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "pandas", "openpyxl", "xlrd"])
            import pandas as pd
        sheets = pd.read_excel(path, sheet_name=None)
        parts = []
        for idx, (sheet_name, df) in enumerate(sheets.items(), 1):
            if idx > 8:
                parts.append("\n[Se omitieron hojas adicionales por longitud.]")
                break
            preview = df.head(80).fillna("").to_csv(index=False)
            parts.append(
                f"Hoja: {sheet_name}\n"
                f"Filas: {len(df)} | Columnas: {len(df.columns)}\n"
                f"{preview}"
            )
        return "\n\n".join(parts)

    def _read_pptx_text(self, path):
        try:
            from pptx import Presentation
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "python-pptx"])
            from pptx import Presentation
        prs = Presentation(path)
        parts = []
        for slide_idx, slide in enumerate(prs.slides, 1):
            texts = []
            for shape in slide.shapes:
                try:
                    if getattr(shape, "has_table", False):
                        for row in shape.table.rows:
                            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                            if any(cells):
                                texts.append(" | ".join(cells))
                    elif hasattr(shape, "text"):
                        txt = (shape.text or "").strip()
                        if txt:
                            texts.append(txt)
                except Exception:
                    pass
            if texts:
                parts.append(f"Diapositiva {slide_idx}\n" + "\n".join(texts))
        return "\n\n".join(parts)

    def _read_pdf_text(self, path):
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "pypdf"])
                from pypdf import PdfReader
            except Exception:
                try:
                    from PyPDF2 import PdfReader
                except Exception:
                    return "[Para leer PDFs instala: pip install pypdf]"
        except Exception:
            try:
                from PyPDF2 import PdfReader
            except Exception:
                return "[Para leer PDFs instala: pip install pypdf]"
        reader = PdfReader(path)
        parts = []
        for page in reader.pages[:40]:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                pass
        return "\n".join(parts).strip()

    # --- F3.9 Notificaciones de escritorio Windows ---
    def _notify(self, title, message):
        try:
            import ctypes
            ctypes.windll.user32.MessageBeep(0x00000040)
        except Exception:
            pass
        try:
            # toast simple via balloon
            from ctypes import wintypes
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "open",
                "powershell",
                f'-NoProfile -WindowStyle Hidden -Command "[reflection.assembly]::loadwithpartialname(\'System.Windows.Forms\') | Out-Null; $n = New-Object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; $n.ShowBalloonTip(4000, \'{title}\', \'{message[:200]}\', \'Info\'); Start-Sleep -Seconds 5; $n.Dispose()"',
                None, 0,
            )
        except Exception:
            pass

    # --- F3.11 execute_code sandbox Python ---
    def _execute_python(self, code, timeout=15):
        import tempfile, subprocess as sp
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        tmp.write(code)
        tmp.close()
        try:
            r = sp.run([sys.executable, tmp.name], capture_output=True, text=True, timeout=timeout, encoding="utf-8")
            out = (r.stdout or "") + (("\nSTDERR: " + r.stderr) if r.stderr else "")
            return out.strip() or "(sin salida)"
        except sp.TimeoutExpired:
            return f"Timeout despues de {timeout}s"
        except Exception as e:
            return f"Error: {e}"
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    # --- F3.12 git ops ---
    def _git_cmd(self, args, cwd=None):
        import subprocess as sp
        try:
            r = sp.run(["git"] + args, capture_output=True, text=True, cwd=cwd, timeout=30, encoding="utf-8")
            return (r.stdout or r.stderr).strip()
        except Exception as e:
            return f"Error git: {e}"

    # --- F3.13 test runner ---
    def _run_tests(self, cwd=None):
        import subprocess as sp
        cwd = cwd or os.getcwd()
        # Detect project type
        if os.path.exists(os.path.join(cwd, "package.json")):
            cmd = ["npm", "test"]
        elif os.path.exists(os.path.join(cwd, "pyproject.toml")) or os.path.exists(os.path.join(cwd, "pytest.ini")):
            cmd = ["pytest", "-q"]
        else:
            return "No detecto tipo de proyecto (no hay package.json ni pyproject.toml)"
        try:
            r = sp.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=180, encoding="utf-8")
            out = (r.stdout or "") + (r.stderr or "")
            return out.strip()[-3000:]
        except Exception as e:
            return f"Error tests: {e}"

    # --- F3.24 EXIF reader ---
    def _read_exif(self, image_path):
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
            img = Image.open(image_path)
            exif = img._getexif() or {}
            data = {}
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == "GPSInfo":
                    gps = {}
                    for k, v in value.items():
                        gps[GPSTAGS.get(k, k)] = v
                    data[tag] = gps
                else:
                    data[tag] = str(value)[:200]
            if not data:
                return "Sin EXIF."
            lines = [f"{k}: {v}" for k, v in data.items() if k in ("Make", "Model", "DateTime", "GPSInfo", "Software", "ExposureTime", "FNumber", "ISOSpeedRatings", "FocalLength")]
            return "\n".join(lines) or json.dumps(data, default=str, ensure_ascii=False, indent=2)[:2000]
        except Exception as e:
            return f"Error EXIF: {e}"

    # --- F3.23 AI content detection (heuristic + LLM judge) ---
    def _detect_ai_text(self, text):
        if not text or len(text) < 30:
            return "Texto muy corto."
        prompt = (
            "Eres un detector de texto generado por IA. Analiza el siguiente texto y responde "
            "SOLO con: 'humano' o 'ia' seguido de un porcentaje de confianza (0-100) y 1 razon breve.\n\n"
            f"TEXTO:\n{text[:2000]}"
        )
        try:
            return self.send_quick_message(prompt, _skip_skill_action=True)
        except Exception as e:
            return f"Error: {e}"

    # --- F3.17 Spotify control ---
    def _spotify_play(self, query):
        import subprocess as sp
        if not query:
            try:
                sp.Popen(["cmd", "/c", "start", "spotify:"], shell=True)
                return "Spotify abierto."
            except Exception as e:
                return f"Error: {e}"
        try:
            sp.Popen(["cmd", "/c", "start", f"spotify:search:{query}"], shell=True)
            return f"Buscando en Spotify: {query}"
        except Exception as e:
            return f"Error: {e}"

    # --- F3.5 /share ---
    def _share_conversation(self, n=20):
        msgs = self._load_memory()[-n:]
        if not msgs:
            return False, "Sin conversacion para compartir."
        body_lines = []
        for m in msgs:
            role = m.get("role", "")
            text = m.get("text", "")
            body_lines.append(f"{role}: {text}")
        body = "\n\n".join(body_lines)
        try:
            req = urllib.request.Request(
                "https://0x0.st",
                data=urllib.parse.urlencode({"file": body[:50000]}).encode("utf-8"),
                method="POST",
            )
            # 0x0 expects multipart; use simpler dpaste
            data = urllib.parse.urlencode({
                "content": body[:50000],
                "syntax": "text",
                "expiry_days": "7",
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://dpaste.com/api/v2/",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Claudy/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                url = r.read().decode("utf-8").strip()
            return True, url
        except Exception as e:
            return False, f"Error: {e}"

    # --- F3.4 /init project analysis ---
    def _init_project(self, root):
        root = os.path.abspath(os.path.expanduser(root))
        if not os.path.isdir(root):
            return False, f"No es directorio: {root}"
        tree_lines = []
        for r, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "venv", "__pycache__", "dist", "build", ".git")]
            depth = r[len(root):].count(os.sep)
            if depth > 3:
                continue
            indent = "  " * depth
            tree_lines.append(f"{indent}{os.path.basename(r)}/")
            for fn in files[:25]:
                tree_lines.append(f"{indent}  {fn}")
            if len(tree_lines) > 200:
                break
        tree = "\n".join(tree_lines[:200])
        prompt = (
            f"Analiza este proyecto y genera un archivo CLAUDY.md conciso con:\n"
            f"- Descripcion del proyecto (1-2 lineas)\n"
            f"- Tecnologias detectadas\n"
            f"- Estructura principal\n"
            f"- Comandos utiles (build/test/run si los detectas)\n\n"
            f"Estructura:\n{tree[:5000]}"
        )
        try:
            content = self.send_quick_message(prompt, _skip_skill_action=True)
        except Exception as e:
            return False, f"Error LLM: {e}"
        out_path = os.path.join(root, "CLAUDY.md")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            return False, f"Error guardando: {e}"
        return True, f"CLAUDY.md generado en: {out_path}"

    # --- F3.3 @ file references ---
    def _expand_file_refs(self, text):
        """Replace @path/to/file with file contents inline."""
        import re as _re
        pattern = _re.compile(r"@([^\s@]+\.(?:py|ts|js|tsx|jsx|md|txt|json|yml|yaml|toml|html|css|sh|ps1|sql|rb|go|rs|java|c|cpp|h))")
        def _sub(m):
            p = m.group(1)
            candidates = [p, os.path.expanduser(p), os.path.join(os.getcwd(), p)]
            for c in candidates:
                if os.path.isfile(c):
                    try:
                        with open(c, "r", encoding="utf-8", errors="replace") as f:
                            body = f.read()[:6000]
                        return f"\n\n[archivo {p}]\n```\n{body}\n```\n"
                    except Exception:
                        return m.group(0)
            return m.group(0)
        return pattern.sub(_sub, text)

    # --- F3.16 /skill install <url|zip|gh-repo> ---
    def _install_skill(self, source):
        skills_dir = os.path.join(os.path.expanduser("~"), ".claudy", "skills")
        os.makedirs(skills_dir, exist_ok=True)
        try:
            # GitHub blob URL -> raw URL
            if "github.com" in source and "/blob/" in source:
                source = source.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            # GitHub shorthand: user/repo
            if "/" in source and "://" not in source and not source.endswith(".zip"):
                source = f"https://github.com/{source}/archive/refs/heads/main.zip"
            if source.endswith(".md") and "://" in source:
                # Single SKILL.md file
                req = urllib.request.Request(source, headers={"User-Agent": "Claudy/1.0"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read().decode("utf-8", "replace")
                import re as _re
                name = _re.search(r"name:\s*(\S+)", body)
                slug = name.group(1) if name else f"imported_{int(time.time())}"
                folder = os.path.join(skills_dir, slug)
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, "SKILL.md"), "w", encoding="utf-8") as f:
                    f.write(body)
                return True, f"Instalada: {slug}"
            if source.endswith(".zip") or "://" in source:
                import zipfile, io as _io
                req = urllib.request.Request(source, headers={"User-Agent": "Claudy/1.0"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                with zipfile.ZipFile(_io.BytesIO(data)) as z:
                    for name in z.namelist():
                        if name.endswith("SKILL.md"):
                            parts = name.split("/")
                            slug = parts[-2] if len(parts) >= 2 else f"imported_{int(time.time())}"
                            folder = os.path.join(skills_dir, slug)
                            os.makedirs(folder, exist_ok=True)
                            with z.open(name) as f:
                                with open(os.path.join(folder, "SKILL.md"), "wb") as out:
                                    out.write(f.read())
                            return True, f"Instalada: {slug}"
                return False, "No encontre SKILL.md en el paquete."
            return False, "Fuente desconocida. Usa URL .md, .zip o user/repo."
        except Exception as e:
            return False, f"Error: {e}"

    # --- F3.18 Gmail via IMAP (requires app password) ---
    def _gmail_inbox(self, n=5):
        cfg = self.load_claudy_config().get("gmail", {})
        user = cfg.get("user", "")
        app_pwd = cfg.get("appPassword", "")
        if not user or not app_pwd:
            return ("Configura Gmail en config.json:\n"
                    '  "gmail": {"user": "tu@gmail.com", "appPassword": "abcd efgh ijkl mnop"}\n'
                    "Crea app password: https://myaccount.google.com/apppasswords")
        try:
            import imaplib, email
            from email.header import decode_header
            M = imaplib.IMAP4_SSL("imap.gmail.com")
            M.login(user, app_pwd)
            M.select("inbox")
            _t, data = M.search(None, "ALL")
            ids = data[0].split()[-n:][::-1]
            lines = []
            for i in ids:
                _t, msg_data = M.fetch(i, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                subj_raw, enc = decode_header(msg.get("Subject", ""))[0]
                subj = subj_raw.decode(enc or "utf-8", "replace") if isinstance(subj_raw, bytes) else subj_raw
                frm = msg.get("From", "")[:50]
                lines.append(f"[{i.decode()}] {frm}\n  {subj[:80]}")
            M.logout()
            return "\n\n".join(lines) if lines else "Inbox vacio."
        except Exception as e:
            return f"Error Gmail: {e}"

    # --- F3.10 LSP diagnostics (minimal: lee output de tsc/eslint/ruff/mypy) ---
    def _lsp_diagnostics(self, cwd=None):
        import subprocess as sp
        cwd = cwd or os.getcwd()
        outputs = []
        cmds = []
        if os.path.exists(os.path.join(cwd, "tsconfig.json")):
            cmds.append(("tsc", ["npx", "--no-install", "tsc", "--noEmit"]))
        if os.path.exists(os.path.join(cwd, "package.json")):
            cmds.append(("eslint", ["npx", "--no-install", "eslint", ".", "--max-warnings=0"]))
        if os.path.exists(os.path.join(cwd, "pyproject.toml")) or os.path.exists(os.path.join(cwd, "ruff.toml")):
            cmds.append(("ruff", ["ruff", "check", "."]))
        if not cmds:
            return "No detecto archivos de configuracion (tsconfig, package.json, pyproject)."
        for name, cmd in cmds:
            try:
                r = sp.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=60, encoding="utf-8")
                out = (r.stdout or "") + (r.stderr or "")
                outputs.append(f"=== {name} ===\n{out.strip()[:2000]}")
            except FileNotFoundError:
                outputs.append(f"=== {name} === (no instalado)")
            except Exception as e:
                outputs.append(f"=== {name} === error: {e}")
        return "\n\n".join(outputs)

    # --- F3.14 agentskills.io compat ---
    def _reload_skills_compat(self):
        """Re-scan ~/.claudy/skills for any SKILL.md (also accepts agentskills.io frontmatter)."""
        skills_dir = os.path.join(os.path.expanduser("~"), ".claudy", "skills")
        if not os.path.isdir(skills_dir):
            return 0
        count = 0
        for folder in os.listdir(skills_dir):
            full = os.path.join(skills_dir, folder)
            if not os.path.isdir(full):
                continue
            for cand in ("SKILL.md", "skill.md", "Skill.md"):
                p = os.path.join(full, cand)
                if os.path.exists(p):
                    count += 1
                    break
        return count

    def _load_installed_skills(self, max_skills=20, max_chars_per_skill=400):
        """Read SKILL.md files from ~/.claudy/skills/* and return formatted context."""
        skills_dir = os.path.join(os.path.expanduser("~"), ".claudy", "skills")
        if not os.path.isdir(skills_dir):
            return ""
        chunks = []
        for folder in sorted(os.listdir(skills_dir))[:max_skills]:
            full = os.path.join(skills_dir, folder)
            if not os.path.isdir(full):
                continue
            for cand in ("SKILL.md", "skill.md", "Skill.md"):
                p = os.path.join(full, cand)
                if os.path.exists(p):
                    try:
                        with open(p, "r", encoding="utf-8", errors="replace") as f:
                            body = f.read(max_chars_per_skill * 2)
                        # Strip YAML frontmatter
                        if body.startswith("---"):
                            end = body.find("---", 3)
                            if end > 0:
                                body = body[end+3:].strip()
                        chunks.append(f"### {folder}\n{body[:max_chars_per_skill]}")
                    except Exception:
                        pass
                    break
        if not chunks:
            return ""
        return "[SKILLS INSTALADAS LOCALMENTE]\n" + "\n\n".join(chunks) + "\n[Fin skills locales]\n\n"

    def _skill_use(self, query):
        """Install a skill and return usage hint. Skill becomes available immediately
        for the next prompt via _load_installed_skills.
        Accepts: direct URL (.md, .zip, github blob), 'user/repo', or search query."""
        q = query.strip()
        # Direct URL or user/repo -> install directly, skip search
        is_url = "://" in q
        is_repo = ("/" in q) and (" " not in q) and not is_url
        if is_url or is_repo:
            ok, msg = self._install_skill(q)
            if not ok:
                return f"Falló instalar {q}: {msg}"
            count = self._reload_skills_compat()
            return (f"Skill instalada y activa: {q}\n"
                    f"Total skills locales: {count}\n"
                    f"Ya puedes pedirme algo que la use — la cargué en mi contexto.")
        try:
            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(q + ' hermes skill')}&per_page=5"
            req = urllib.request.Request(url, headers={"User-Agent": "Claudy/1.0", "Accept": "application/vnd.github.v3+json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            items = data.get("items", [])
            if not items:
                return f"Sin skills para '{query}'."
            top = items[0]
            repo = top.get("full_name")
            ok, msg = self._install_skill(repo)
            if not ok:
                return f"Encontré {repo} pero falló instalar: {msg}"
            count = self._reload_skills_compat()
            return (f"Skill instalada y activa: {repo}\n"
                    f"Stars: {top.get('stargazers_count', 0)} | {(top.get('description') or '')[:120]}\n"
                    f"Total skills locales: {count}\n"
                    f"Ya puedes pedirme algo que la use — la cargué en mi contexto.")
        except Exception as e:
            return f"Error: {e}"

    # --- F3.15 /skill buscar ---
    def _search_skills_registry(self, query):
        try:
            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query + ' hermes skill')}&per_page=10"
            req = urllib.request.Request(url, headers={"User-Agent": "Claudy/1.0", "Accept": "application/vnd.github.v3+json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            items = data.get("items", [])
            if not items:
                return "Sin resultados."
            lines = []
            for it in items[:10]:
                lines.append(f"- {it.get('full_name')} ({it.get('stargazers_count',0)}*): {(it.get('description') or '')[:80]}")
            lines.append("\nInstala con: /skill install <user/repo>")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    def _hooks_path(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", "hooks.py")

    def _load_hooks(self):
        """Load user-defined hooks from ~/.claudy/hooks.py."""
        if hasattr(self, "_hooks_module"):
            return self._hooks_module
        path = self._hooks_path()
        if not os.path.exists(path):
            self._hooks_module = None
            return None
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("claudy_user_hooks", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._hooks_module = mod
            print(f"[hooks] cargado: {path}")
            return mod
        except Exception as e:
            print(f"[hooks] error cargando: {e}")
            self._hooks_module = None
            return None

    def _fire_hook(self, event, **payload):
        """Call user hook if defined. Hooks: on_message, on_response, on_error, on_skill, on_cron."""
        mod = self._load_hooks()
        if not mod:
            return
        fn = getattr(mod, event, None)
        if not callable(fn):
            return
        try:
            fn(payload)
        except Exception as e:
            print(f"[hooks] error en {event}: {e}")

    def _images_dir(self):
        d = os.path.join(os.path.expanduser("~"), ".claudy", "images")
        os.makedirs(d, exist_ok=True)
        return d

    def _pasted_dir(self):
        d = os.path.join(os.path.expanduser("~"), ".claudy", "images", "pasted")
        os.makedirs(d, exist_ok=True)
        return d

    def _grab_clipboard_image(self):
        """Return PIL.Image from clipboard, or None."""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img is None:
                return None
            if isinstance(img, list):
                for p in img:
                    if isinstance(p, str) and os.path.isfile(p):
                        from PIL import Image as _Image
                        return _Image.open(p)
                return None
            return img
        except Exception:
            return None

    def _analyze_image_pollinations(self, image_path, question):
        """Call Pollinations vision API (free). Returns analysis text."""
        try:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            payload = {
                "model": "openai",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question or "Describe esta imagen en espanol con detalle."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        ],
                    }
                ],
                "max_tokens": 800,
            }
            req = urllib.request.Request(
                "https://text.pollinations.ai/openai",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Claudy/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or []
            if choices:
                msg = choices[0].get("message") or {}
                return msg.get("content", "").strip() or "(sin texto)"
            return data.get("response") or "(sin respuesta)"
        except Exception as e:
            return f"Error analizando imagen: {e}"

    def _analyze_image_native(self, image_path, question):
        """P3-1: Send image to the configured vision-capable provider (Anthropic/OpenAI).
        Falls back to Pollinations if no key or model lacks vision."""
        try:
            config = self.load_claudy_config()
            model = self._current_model or config.get("opencode", {}).get("defaultModel", "")
            mlow = (model or "").lower()
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            ext = os.path.splitext(image_path)[1].lower().lstrip(".") or "png"
            if ext == "jpg":
                ext = "jpeg"
            media_type = f"image/{ext}"
            prompt = question or "Describe esta imagen en espanol con detalle."

            # Anthropic Claude
            if "claude" in mlow or "anthropic" in mlow:
                keys = self._get_provider_keys(config, "anthropic")
                if not keys:
                    return self._analyze_image_pollinations(image_path, question)
                actual = model.partition("/")[2] if "/" in model else model
                payload = {
                    "model": actual,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                        {"type": "text", "text": prompt},
                    ]}],
                }
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": keys[0],
                    "anthropic-version": "2023-06-01",
                }
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = json.loads(resp.read())
                blocks = data.get("content", [])
                return "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip() or "(sin respuesta)"

            # OpenAI / OpenAI-compat (only if model supports vision: gpt-4o, gpt-4-vision, etc.)
            if any(k in mlow for k in ("gpt-4o", "gpt-4-vision", "gpt-4-turbo", "vision")):
                keys = self._get_provider_keys(config, "openai")
                if not keys:
                    return self._analyze_image_pollinations(image_path, question)
                actual = model.partition("/")[2] if "/" in model else model
                payload = {
                    "model": actual,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                    ]}],
                }
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {keys[0]}",
                }
                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = json.loads(resp.read())
                choices = data.get("choices") or []
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip() or "(sin respuesta)"
                return "(sin respuesta)"
        except Exception as e:
            return f"Error vision nativa: {e}. Intentando fallback...\n" + self._analyze_image_pollinations(image_path, question)
        # No vision-capable provider detected -> fallback
        return self._analyze_image_pollinations(image_path, question)

    def _handle_pasted_image(self, status_widget, entry_widget):
        """Called on Ctrl+V in bubble entry. If clipboard has image, save+analyze."""
        img = self._grab_clipboard_image()
        if img is None:
            return False
        try:
            self._set_state_briefly("surprised", 600)
        except Exception:
            pass
        try:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(self._pasted_dir(), f"{ts}.png")
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(path, "PNG")
        except Exception as e:
            self._set_response_text(f"Error guardando imagen: {e}")
            return True
        question = self._entry_attachment_question(entry_widget)
        self._set_response_text(f"Imagen pegada ({os.path.basename(path)}).\nAnalizando...")
        try:
            status_widget.configure(text="Analizando imagen...", fg=THEME["accent"])
        except Exception:
            pass

        def _run():
            answer = self._analyze_image_native(path, question)
            self._save_memory("Usuario", f"[imagen pegada] {question}".strip())
            self._save_memory("Claudy", answer)
            self.after(0, lambda: self._set_response_text(answer))
            try:
                self.after(0, lambda: status_widget.configure(text="Listo", fg=THEME["text_secondary"]))
            except Exception:
                pass
            if self._voice_enabled:
                _tts_speak(answer)
        threading.Thread(target=_run, daemon=True).start()
        return True

    def _generate_image(self, prompt):
        """Generate image via Pollinations.ai (free, no API key)."""
        if not prompt:
            return False, "Falta el prompt. Usa: /img <descripcion>"
        try:
            encoded = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out = os.path.join(self._images_dir(), f"{ts}.png")
            req = urllib.request.Request(url, headers={"User-Agent": "Claudy/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            with open(out, "wb") as f:
                f.write(data)
            try:
                os.startfile(out)
            except Exception:
                pass
            return True, out
        except Exception as e:
            return False, f"Error generando imagen: {e}"

    def _checkpoints_dir(self):
        d = os.path.join(os.path.expanduser("~"), ".claudy", "checkpoints")
        os.makedirs(d, exist_ok=True)
        return d

    def _file_checkpoint_create(self, file_path):
        src = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.exists(src):
            return False, f"No existe: {src}"
        if not os.path.isfile(src):
            return False, f"No es archivo: {src}"
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.basename(src)
        snap_dir = self._checkpoints_dir()
        snap_path = os.path.join(snap_dir, f"{ts}__{base}.bak")
        try:
            shutil.copy2(src, snap_path)
        except Exception as e:
            return False, f"Error guardando snapshot: {e}"
        meta_path = os.path.join(snap_dir, f"{ts}__{base}.json")
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"src": src, "snap": snap_path, "ts": ts}, f)
        except Exception:
            pass
        cid = f"{ts}__{base}"
        self._checkpoint_history.append(cid)
        self._checkpoint_undone = []
        return True, f"Snapshot: {cid}\nOrigen: {src}"

    def _undo_last(self):
        if not self._checkpoint_history:
            return "Nada que deshacer."
        cid = self._checkpoint_history.pop()
        ok, msg = self._file_checkpoint_rollback(cid)
        if ok:
            self._checkpoint_undone.append(cid)
        return msg

    def _redo_last(self):
        if not self._checkpoint_undone:
            return "Nada que rehacer."
        cid = self._checkpoint_undone.pop()
        self._checkpoint_history.append(cid)
        return f"Marcado para rehacer: {cid}\n(Aplica los cambios manualmente o crea otro checkpoint)"

    def _file_checkpoint_list(self):
        d = self._checkpoints_dir()
        items = []
        for fn in sorted(os.listdir(d), reverse=True):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(d, fn), "r", encoding="utf-8") as f:
                        m = json.load(f)
                    cid = fn[:-5]
                    items.append((cid, m.get("src", "?"), m.get("ts", "?")))
                except Exception:
                    pass
        return items

    def _file_checkpoint_rollback(self, cid):
        d = self._checkpoints_dir()
        meta_path = os.path.join(d, f"{cid}.json")
        if not os.path.exists(meta_path):
            return False, f"Checkpoint no existe: {cid}"
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                m = json.load(f)
            snap = m.get("snap")
            src = m.get("src")
            if not snap or not os.path.exists(snap):
                return False, "Snapshot perdido."
            # Safety: backup current state before overwriting
            if os.path.exists(src):
                pre_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                pre_snap = os.path.join(d, f"{pre_ts}__pre-rollback__{os.path.basename(src)}.bak")
                try:
                    shutil.copy2(src, pre_snap)
                except Exception:
                    pass
            shutil.copy2(snap, src)
            return True, f"Restaurado: {src}\nDesde: {cid}"
        except Exception as e:
            return False, f"Error: {e}"

    def _personalities_dir(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", "personalities")

    def _list_personalities(self):
        d = self._personalities_dir()
        if not os.path.isdir(d):
            return []
        names = []
        for fn in os.listdir(d):
            if fn.lower().endswith(".md"):
                names.append(os.path.splitext(fn)[0])
        return sorted(names)

    def _current_personality_name(self):
        config_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            return data.get("agent", {}).get("personality", "default")
        except Exception:
            return "default"

    def _apply_personality(self, name):
        path = os.path.join(self._personalities_dir(), f"{name}.md")
        if not os.path.exists(path):
            available = self._list_personalities()
            return False, f"No conozco '{name}'.\nDisponibles: {', '.join(available)}"
        try:
            with open(path, "r", encoding="utf-8") as f:
                prompt = f.read().strip()
        except Exception as e:
            return False, f"Error leyendo {name}: {e}"
        config_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception:
            data = {"opencode": {}, "agent": {}}
        data.setdefault("agent", {})
        data["agent"]["systemPrompt"] = prompt
        data["agent"]["personality"] = name
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            return False, f"Error guardando config: {e}"
        # Reset session so the model picks up the new system prompt
        self.quick_session_id = None
        return True, f"Listo. Personalidad cambiada a '{name}'."

    def load_claudy_config(self):
        config_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
        default = {
            "opencode": {
                "baseUrl": "http://127.0.0.1:4096",
                "defaultModel": "deepseek-chat",
                "apiKey": "",
                "username": "opencode",
                "password": "",
            },
            "agent": {
                "systemPrompt": "Eres Claudy, un asistente de IA personal. Responde breve y util.",
            },
        }
        if not os.path.exists(config_path):
            return default
        with open(config_path, "r", encoding="utf-8-sig") as file:
            loaded = json.load(file)
        default["opencode"].update(loaded.get("opencode", {}))
        default["agent"].update(loaded.get("agent", {}))
        # Pass through additional top-level sections (telegram, discord, etc.)
        for key, value in loaded.items():
            if key not in ("opencode", "agent"):
                default[key] = value
        # Transparently decrypt secrets so the rest of the app sees plaintext.
        try:
            if _secure is not None:
                _secure.decrypt_config_secrets(default)
        except Exception:
            pass
        return default

    def _secure_migrate_config(self):
        """Encrypt the secret fields in config.json at rest (idempotent + safe).
        Never raises: any problem leaves the file untouched."""
        try:
            if _secure is None or not _secure.available():
                return
            path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
            before = json.dumps(cfg, sort_keys=True)
            _secure.encrypt_config_secrets(cfg)
            after = json.dumps(cfg, sort_keys=True)
            if before == after:
                return  # already encrypted / nothing to migrate
            try:
                shutil.copy2(path, path + ".bak")
            except Exception:
                pass
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            pass

    def build_auth_headers(self, config):
        headers = {"Content-Type": "application/json"}
        opencode = config["opencode"]
        if opencode.get("apiKey"):
            headers["Authorization"] = f'Bearer {opencode["apiKey"]}'
        elif opencode.get("password"):
            user = opencode.get("username") or "opencode"
            token = base64.b64encode(f'{user}:{opencode["password"]}'.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        return headers

    def _debug_log(self, label, data):
        try:
            debug_path = os.path.join(os.path.expanduser("~"), ".claudy", "debug.log")
            with open(debug_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.datetime.now().isoformat()}] {label}\n{data}\n\n")
        except Exception:
            pass

    def request_json(self, url, payload, config, timeout=60):
        body = json.dumps(payload).encode("utf-8")
        headers = self.build_auth_headers(config)
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as error:
            raise RuntimeError("no pude conectar con el cerebro remoto") from error
        self._debug_log("RAW RESPONSE", raw)
        return json.loads(raw) if raw else {}

    def ping_opencode(self, base_url, config, timeout=1.5):
        headers = self.build_auth_headers(config)
        request = urllib.request.Request(f"{base_url}/provider", headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout):
                return True
        except Exception:
            return False

    def ensure_opencode_server(self, base_url, config):
        if self.ping_opencode(base_url, config):
            return
        opencode_path = self.find_opencode_command()
        if not opencode_path:
            raise RuntimeError("no encuentro al oráculo en este equipo")
        parsed = urllib.parse.urlparse(base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 4096
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.opencode_process = subprocess.Popen(
            [opencode_path, "serve", "--port", str(port), "--hostname", host],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags,
        )
        for _ in range(50):
            if self.ping_opencode(base_url, config):
                return
            time.sleep(0.2)
        raise RuntimeError("el cerebro remoto no despertó a tiempo")

    def find_opencode_command(self):
        return (
            shutil.which("opencode.exe")
            or shutil.which("opencode.cmd")
            or shutil.which("opencode.bat")
            or shutil.which("opencode")
        )

    # ------------------------------------------------------------------
    # Infinite memory (SQLite)
    # ------------------------------------------------------------------











    # Stopwords para la búsqueda por relevancia en el vault.




    def _get_user_location(self):
        try:
            req = urllib.request.Request(
                "http://ip-api.com/json/?fields=status,city,regionName,country,countryCode,timezone,lat,lon,zip,isp,org",
                headers={"User-Agent": "Claudy/1.0"}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                parts = [p for p in [data.get("city"), data.get("regionName"), data.get("country")] if p]
                loc = ", ".join(parts) if parts else "desconocida"
                tz = data.get("timezone", "desconocida")
                lat = data.get("lat", 0)
                lon = data.get("lon", 0)
                country_code = data.get("countryCode", "")
                zipcode = data.get("zip", "")
                # Build rich location context for the AI
                context_parts = []
                context_parts.append(f"Ubicación: {loc}")
                if country_code:
                    context_parts.append(f"Código de país: {country_code}")
                context_parts.append(f"Zona horaria: {tz}")
                if zipcode:
                    context_parts.append(f"Código postal: {zipcode}")
                context_parts.append(f"Coordenadas: {lat}, {lon}")
                # Add contextual guidance for the AI
                context_parts.append(
                    "Usa esta ubicación para responder preguntas sobre clima local, "
                    "leyes y regulaciones del país, horarios, moneda local, cultura, "
                    "festividades, y cualquier consulta que dependa de la ubicación del usuario."
                )
                return " | ".join(context_parts)
        except Exception:
            pass
        return "desconocida (no pude conectarme al servicio de geolocalización)"

    def _get_superpowers(self):
        now = datetime.datetime.now()
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        fecha = f"{dias[now.weekday()]} {now.day} de {meses[now.month - 1]} de {now.year}"
        hora = now.strftime("%H:%M:%S")
        ubicacion = getattr(self, "_cached_location", None)
        if ubicacion is None:
            ubicacion = self._get_user_location()
            self._cached_location = ubicacion
        tiene_memoria = os.path.exists(self._memory_db_path())
        memoria_nota = "Tienes memoria persistente de conversaciones anteriores. Úsala cuando aporte contexto." if tiene_memoria else "No hay historial previo todavía."

        return (
            "═══ IDENTIDAD ═══\n"
            "Eres Claudy, el asistente personal de Felipe. Hablas español natural, directo, sin formalidad excesiva — como un amigo técnico que sabe del tema.\n\n"

            "═══ CONTEXTO ACTUAL ═══\n"
            f"Fecha y hora: {fecha}, {hora}\n"
            f"Ubicación: {ubicacion}\n"
            f"Memoria: {memoria_nota}\n\n"

            "═══ PROTOCOLO DE RESPUESTA ═══\n"
            "Clasifica la pregunta y responde según su categoría:\n\n"

            "1. SALUDO / CHARLA RÁPIDA (hola, gracias, ok)\n"
            "   → 1-2 líneas, sin buscar.\n\n"

            "2. DEFINICIÓN / EXPLICACIÓN (qué es X, cómo funciona Y, explícame Z, para qué sirve W)\n"
            "   → BUSCA en internet primero (/buscar o webfetch) para tener info actualizada y precisa.\n"
            "   → Da respuesta ESTRUCTURADA y rica:\n"
            "     • 1-2 líneas de definición clara al inicio\n"
            "     • 3-5 puntos clave (con guiones, no markdown)\n"
            "     • 1 ejemplo concreto o caso de uso\n"
            "     • Fuente al final en 1 línea\n"
            "   → Longitud: 8-15 líneas. Densa en info, sin relleno.\n\n"

            "3. DATO ACTUAL (precio, clima, noticia, marcador, evento)\n"
            "   → BUSCA primero. Da:\n"
            "     • El dato concreto en 1 línea\n"
            "     • 1-2 líneas de contexto si ayuda (variación, tendencia, fecha)\n"
            "     • Fuente al final\n\n"

            "4. CÓDIGO / TÉCNICO\n"
            "   → Si requiere conocimiento actualizado (versiones, APIs, librerías nuevas) BUSCA primero.\n"
            "   → Estructura:\n"
            "     • 1 línea explicando qué hace\n"
            "     • El código completo (sin ``` markdown, pero indentado)\n"
            "     • 2-3 líneas explicando partes clave si no es obvio\n"
            "   → Usa /leer o /buscar_archivo si necesitas ver archivos del usuario.\n\n"

            "5. TAREA COMPLEJA / MULTI-PASO (instalar, configurar, debuggear)\n"
            "   → Plan en 1 línea: 'Plan: 1) X, 2) Y, 3) Z'\n"
            "   → Ejecuta CADA paso con su comando. No te detengas.\n"
            "   → Reporta resultado de cada paso.\n"
            "   → Final: 'Hecho. ¿Sigue algo?'\n\n"

            "6. OPINIÓN / RECOMENDACIÓN\n"
            "   → Recomendación directa (NO 'depende').\n"
            "   → 2-3 líneas de por qué (criterios concretos).\n"
            "   → Si aplica: 1 alternativa con su trade-off.\n\n"

            "═══ REGLAS ESTRICTAS ═══\n"
            "🚫 PROHIBIDO ANUNCIAR — EJECUTA Y RESPONDE EN UN SOLO MENSAJE:\n"
            "  Tu respuesta DEBE SER el resultado, NUNCA la promesa de buscarlo.\n"
            "  JAMÁS digas estas frases (usa la tool y da el resultado directo):\n"
            "  ✗ 'voy a revisar' / 'voy a buscar' / 'voy a consultar' / 'voy a verificar'\n"
            "  ✗ 'déjame buscar' / 'déjame revisar' / 'permíteme buscar'\n"
            "  ✗ 'dame un momento' / 'dame un segundo' / 'espera'\n"
            "  ✗ 'te respondo en un momento' / 'para darte la respuesta'\n"
            "  ✗ 'voy a checar' / 'voy a mirar' / 'iré a buscar'\n"
            "  Si necesitas info externa, USA la tool internamente y entrega SOLO el resultado.\n\n"

            "🚫 PROHIBIDO decir:\n"
            "  ✗ 'como modelo de IA' / 'soy un asistente virtual' / 'como inteligencia artificial'\n"
            "  ✗ 'no tengo acceso a' / 'no puedo hacer eso' (busca o usa una tool primero)\n"
            "  ✗ Preámbulos: '¡claro!', 'por supuesto', '¡interesante pregunta!', 'déjame explicarte'\n"
            "  ✗ 'te recomiendo buscar...' / 'puedes consultar...' (NO derives a otros sitios, RESUELVE)\n"
            "  ✗ Markdown: **negrita**, *cursiva*, `código`, ###titulos, ```bloques```\n\n"

            "OBLIGATORIO:\n"
            "  ✓ Si no sabes, di 'No sé' directo (sin disculparte)\n"
            "  ✓ Usa la memoria de conversaciones anteriores cuando sea relevante\n"
            "  ✓ Respuestas estructuradas y completas según la categoría (ver protocolo)\n"
            "  ✓ Usa formato plano legible: guiones para listas, líneas en blanco entre secciones\n"
            "  ✓ Cita la fuente (URL o nombre del sitio) cuando uses info de internet\n"
            "  ✓ Cada respuesta debe ACERCAR al objetivo de Felipe, no solo informar\n"
            "  ✓ Si la pregunta es ambigua, asume la interpretación más útil y procede\n\n"

            "═══ COMANDOS DISPONIBLES (úsalos directamente, no los expliques) ═══\n"
            "Web      → /buscar <tema>   |  webfetch <url>\n"
            "Archivos → /leer <ruta>  |  /write <ruta> | <contenido>  |  /append <ruta> | <contenido>\n"
            "           /replace <ruta> | <buscar> | <reemplazo>  |  /mkdir <ruta>  |  /buscar_archivo <nombre>  |  /descargar <url>\n"
            "           /docx <ruta> | <contenido>  |  /pdf <ruta> | <contenido>  |  /xlsx <ruta> | <contenido CSV/JSON>  |  /pptx <ruta> | <JSON de slides>\n"
            "           Tras crear o editar, el icono de carpeta abierta en la burbuja abre la ubicacion.\n"
            "Sistema  → /ejecutar <cmd>  |  /apps  |  /procesos  |  /disco\n"
            "Apps     → /instalar <app>\n"
            "Memoria  → /recordar <nota> |  /checkpoint  |  /rollback\n"
            "Skills   → /skills  |  /aprender <nombre>  |  /skill eliminar <nombre>\n"
            "Tareas   → /delegar <tarea> (subagente)  |  /kanban add/move/list\n"
            "Conexión → /vincular <id> (Telegram)\n\n"

            "═══ APRENDIZAJE AUTOMÁTICO (estilo Hermes Curator) ═══\n"
            "Cuando completes una tarea exitosa o aprendas un procedimiento nuevo:\n"
            "  • Si Felipe dice 'aprende esto', 'guarda esto como skill X', 'memoriza esto como X':\n"
            "    → se dispara automáticamente la creación de SKILL.md basada en los últimos mensajes.\n"
            "  • Manualmente: /aprender <nombre>\n"
            "  • Las skills aprendidas se cargan en cada conversación futura.\n"
            "Cuando termines una tarea compleja útil, OFRECE proactivamente:\n"
            "  '¿Quieres que aprenda esto como skill para reusarlo?'\n\n"

            "═══ DECISIÓN: CUÁNDO BUSCAR EN INTERNET ═══\n"
            "BUSCA (con /buscar o webfetch) cuando:\n"
            "  • Pregunta 'qué es X', 'cómo funciona Y', 'explícame Z', 'para qué sirve W'\n"
            "    (incluso si conoces algo, búscalo para dar info actualizada, precisa y completa)\n"
            "  • Datos que cambian: precios, clima, noticias, eventos, fechas, marcadores\n"
            "  • Tutoriales paso a paso, comparativas, recomendaciones de productos\n"
            "  • Cualquier tema donde una fuente confiable mejore tu respuesta\n\n"

            "NO busques cuando:\n"
            "  • Es saludo o charla simple\n"
            "  • Es matemática pura, lógica, o el usuario quiere TU opinión\n"
            "  • Es continuación de algo ya hablado (usa memoria)\n\n"

            "Para datos del usuario (sus archivos, su sistema): usa /leer, /buscar_archivo, /procesos antes de inventar.\n\n"

            "═══ ANTI-FORMATO MARKDOWN ═══\n"
            "Tkinter no renderiza markdown. Usa formato plano:\n"
            "  ✗ NO uses: **negrita**, *cursiva*, `código`, ###título, ```bloque```\n"
            "  ✓ SÍ usa: GUIONES para listas (- punto), líneas en blanco para separar secciones,\n"
            "    MAYÚSCULAS sutiles para destacar, indentación con 2 espacios para sub-puntos.\n"
            "  ✓ Para código: ponlo en líneas separadas, indentado, sin backticks.\n\n"

            "[Fin del system prompt]\n\n"

            f"{self._load_dynamic_skills()}"
            f"{self._get_skills_context()}"
        )

    def _load_dynamic_skills(self):
        """Load skills from ~/.claudy/skills/*/SKILL.md and return formatted context."""
        skills_dir = os.path.join(os.path.expanduser("~"), ".claudy", "skills")
        if not os.path.isdir(skills_dir):
            return ""
        parts = []
        try:
            for folder in sorted(os.listdir(skills_dir)):
                skill_path = os.path.join(skills_dir, folder, "SKILL.md")
                if not os.path.isfile(skill_path):
                    continue
                try:
                    with open(skill_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    if content:
                        # Truncate very large skills to avoid blowing up the prompt
                        if len(content) > 3000:
                            content = content[:3000] + "\n... [skill truncada]"
                        parts.append(f"[SKILL: {folder}]\n{content}\n[FIN SKILL: {folder}]")
                except Exception:
                    continue
        except Exception:
            return ""
        if not parts:
            return ""
        return "[SKILLS DINAMICAS - Usa esta informacion cuando sea relevante]\n\n" + "\n\n".join(parts) + "\n\n"

    # ------------------------------------------------------------------
    # Context compression
    # ------------------------------------------------------------------




    # ------------------------------------------------------------------
    # Checkpoints / Rollback
    # ------------------------------------------------------------------




    # ------------------------------------------------------------------
    # Tool Registry (auto-discovery pattern)
    # ------------------------------------------------------------------
    TOOL_REGISTRY = {}  # name -> {"handler": fn, "description": str, "schema": dict}

    @classmethod
    def register_tool(cls, name, handler, description, parameters=None):
        cls.TOOL_REGISTRY[name] = {
            "handler": handler,
            "description": description,
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters or {"type": "object", "properties": {}},
                },
            },
        }

    def _get_tool_schemas(self):
        """Return tool schemas for remote providers."""
        schemas = []
        for name, info in self.TOOL_REGISTRY.items():
            schemas.append(info["schema"])
        return schemas

    def _handle_tool_call(self, tool_call):
        """Execute a registered tool."""
        name = tool_call.get("function", {}).get("name", "") if isinstance(tool_call, dict) else getattr(tool_call, "function", {}).get("name", "")
        args_str = tool_call.get("function", {}).get("arguments", "{}") if isinstance(tool_call, dict) else getattr(getattr(tool_call, "function", None), "arguments", "{}")
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
        except (json.JSONDecodeError, TypeError):
            args = {}
        info = self.TOOL_REGISTRY.get(name)
        if not info:
            return f"Tool '{name}' not found."
        try:
            return info["handler"](self, **args)
        except Exception as e:
            return f"Error executing {name}: {e}"

    # Register built-in tools (class-level)
    def _tool_disk_space(_self):
        return _self._get_disk_space()
    def _tool_execute_cmd(_self, command=""):
        return _self._execute_command(command) if command else "No command provided."
    def _tool_search_files(_self, query=""):
        return _self._search_files(query) if query else "No query provided."
    def _tool_read_file(_self, path=""):
        return _self._read_local_file(path) if path else "No path provided."
    def _tool_write_file(_self, path="", content="", append=False):
        if not path:
            return "No path provided."
        import claudy_powers as cp
        return cp.write_file(path, content or "", append=bool(append))
    def _tool_append_file(_self, path="", content=""):
        if not path:
            return "No path provided."
        import claudy_powers as cp
        return cp.append_file(path, content or "")
    def _tool_replace_in_file(_self, path="", old="", new=""):
        if not path:
            return "No path provided."
        import claudy_powers as cp
        return cp.replace_in_file(path, old, new)
    def _tool_create_folder(_self, path=""):
        if not path:
            return "No path provided."
        import claudy_powers as cp
        return cp.create_folder(path)

    @classmethod
    def _register_builtin_tools(cls):
        cls.register_tool("get_disk_space", cls._tool_disk_space, "Get disk space info for all drives")
        cls.register_tool("execute_command", cls._tool_execute_cmd, "Execute a safe shell command", {
            "type": "object", "properties": {"command": {"type": "string", "description": "Shell command to execute"}},
            "required": ["command"]})
        cls.register_tool("search_files", cls._tool_search_files, "Search for files by name", {
            "type": "object", "properties": {"query": {"type": "string", "description": "File name to search"}},
            "required": ["query"]})
        cls.register_tool("read_file", cls._tool_read_file, "Read contents of a local file", {
            "type": "object", "properties": {"path": {"type": "string", "description": "File path to read"}},
            "required": ["path"]})
        cls.register_tool("write_file", cls._tool_write_file, "Create or overwrite a local text file", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to create or overwrite"},
                "content": {"type": "string", "description": "Text content to write"},
                "append": {"type": "boolean", "description": "Append instead of overwrite"},
            },
            "required": ["path", "content"]})
        cls.register_tool("append_file", cls._tool_append_file, "Append text to a local text file", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to append to"},
                "content": {"type": "string", "description": "Text content to append"},
            },
            "required": ["path", "content"]})
        cls.register_tool("replace_in_file", cls._tool_replace_in_file, "Replace text inside a local text file", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit"},
                "old": {"type": "string", "description": "Exact text to replace"},
                "new": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old", "new"]})
        cls.register_tool("create_folder", cls._tool_create_folder, "Create a local folder", {
            "type": "object", "properties": {"path": {"type": "string", "description": "Folder path to create"}},
            "required": ["path"]})

    # ------------------------------------------------------------------
    # Memory: checkpoints, rollback, search
    # ------------------------------------------------------------------
    def _list_dynamic_skills(self):
        """List installed dynamic skills."""
        skills_dir = os.path.join(os.path.expanduser("~"), ".claudy", "skills")
        if not os.path.isdir(skills_dir):
            return "No hay skills instaladas."
        found = []
        for folder in sorted(os.listdir(skills_dir)):
            skill_path = os.path.join(skills_dir, folder, "SKILL.md")
            if os.path.isfile(skill_path):
                try:
                    with open(skill_path, "r", encoding="utf-8") as f:
                        first_line = f.readline().replace("# ", "").strip() or folder
                    found.append(f"  {folder}: {first_line}")
                except Exception:
                    found.append(f"  {folder}")
        if not found:
            return "No hay skills instaladas en ~/.claudy/skills/"
        return f"Skills instaladas ({len(found)}):\n\n" + "\n".join(found) + "\n\nCrear nueva: /skill crear <nombre>\nCarpeta: ~/.claudy/skills/"

    def _create_skill_stub(self, name):
        """Create a new skill template."""
        skills_dir = os.path.join(os.path.expanduser("~"), ".claudy", "skills")
        skill_folder = os.path.join(skills_dir, name.lower().replace(" ", "_"))
        os.makedirs(skill_folder, exist_ok=True)
        skill_file = os.path.join(skill_folder, "SKILL.md")
        if os.path.exists(skill_file):
            return f"La skill '{name}' ya existe. Edita: {skill_file}"
        template = f"# {name}\n\nDescribe aqui que hace esta skill y como debe responder Claudy.\n"
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(template)
        return f"Skill '{name}' creada.\n\nEdita el archivo:\n{skill_file}\n\nReinicia Claudy para cargarla."

    def _learn_skill_from_conversation(self, name):
        """
        Estilo Hermes Curator: extrae las últimas N interacciones de la memoria
        y le pide al LLM que las destile en una SKILL.md reutilizable.
        """
        import re as _re
        slug = _re.sub(r'[^a-z0-9_-]+', '-', name.lower().strip()).strip('-') or "nueva-skill"
        skills_dir = os.path.join(os.path.expanduser("~"), ".claudy", "skills")
        skill_folder = os.path.join(skills_dir, slug)
        skill_file = os.path.join(skill_folder, "SKILL.md")

        if os.path.exists(skill_file):
            return f"Ya existe una skill '{slug}'. Eliminala primero con: /skill eliminar {slug}"

        # Cargar las últimas 30 interacciones de memoria
        try:
            messages = self._load_memory()[-30:]
        except Exception:
            messages = []

        if not messages:
            return "No hay conversación reciente para aprender."

        # Construir transcript
        transcript_lines = []
        for m in messages:
            role = "Usuario" if m.get("role") == "Usuario" else "Claudy"
            transcript_lines.append(f"{role}: {m.get('text','')}")
        transcript = "\n".join(transcript_lines)
        if len(transcript) > 6000:
            transcript = transcript[-6000:]

        # Pedir al LLM que destile la skill
        learn_prompt = (
            f"Vas a crear un archivo SKILL.md a partir de esta conversación. "
            f"El objetivo: que la próxima vez que aparezca una situación similar, sepas exactamente qué hacer.\n\n"
            f"Nombre de la skill: {slug}\n\n"
            f"Transcript de la conversación:\n{transcript}\n\n"
            f"Genera SOLO el contenido del archivo SKILL.md con este formato exacto (sin explicaciones extra):\n\n"
            f"---\n"
            f"name: {slug}\n"
            f"description: <una línea clara: cuándo usar esta skill>\n"
            f"---\n\n"
            f"# {name}\n\n"
            f"## Cuándo usarla\n"
            f"<2-3 líneas: qué tipo de situación o pregunta dispara esta skill>\n\n"
            f"## Pasos\n"
            f"1. <paso concreto>\n"
            f"2. <paso concreto>\n"
            f"3. <paso concreto>\n\n"
            f"## Reglas\n"
            f"- <regla aprendida de la conversación>\n"
            f"- <otra regla>\n\n"
            f"## Ejemplo\n"
            f"<un caso real de la conversación, anonimizado si tiene datos personales>"
        )

        try:
            skill_content = self.send_quick_message(learn_prompt, _skip_skill_action=True)
        except Exception as e:
            return f"Error al generar la skill: {e}"

        # Limpiar respuesta: quitar fences de markdown si los puso
        skill_content = _re.sub(r'^```[a-z]*\n', '', skill_content.strip())
        skill_content = _re.sub(r'\n```$', '', skill_content)

        # Validar que tenga frontmatter mínimo
        if not skill_content.startswith("---"):
            skill_content = (
                f"---\n"
                f"name: {slug}\n"
                f"description: Skill aprendida automáticamente sobre {name}\n"
                f"---\n\n"
                + skill_content
            )

        # Guardar
        try:
            os.makedirs(skill_folder, exist_ok=True)
            with open(skill_file, "w", encoding="utf-8") as f:
                f.write(skill_content)
        except Exception as e:
            return f"Error guardando skill: {e}"

        return (
            f"✓ Skill aprendida: {slug}\n"
            f"Guardada en: {skill_file}\n"
            f"Se cargará automáticamente en cada conversación."
        )

    def _delete_skill(self, name):
        """Elimina una skill del directorio del usuario."""
        import re as _re
        import shutil
        slug = _re.sub(r'[^a-z0-9_-]+', '-', name.lower().strip()).strip('-')
        skills_dir = os.path.join(os.path.expanduser("~"), ".claudy", "skills")
        skill_folder = os.path.join(skills_dir, slug)
        if not os.path.isdir(skill_folder):
            return f"No existe la skill '{slug}'."
        try:
            shutil.rmtree(skill_folder)
            return f"✓ Skill '{slug}' eliminada."
        except Exception as e:
            return f"Error eliminando skill: {e}"

    # ==============================================================
    # SELF-IMPROVING SKILLS (estilo Hermes: crear Y refinar solo)
    # ==============================================================

    def _skill_slug(self, name):
        import re as _re
        return _re.sub(r'[^a-z0-9_-]+', '-', (name or "").lower().strip()).strip('-')

    def _skill_dir(self, slug):
        return os.path.join(os.path.expanduser("~"), ".claudy", "skills", slug)

    def _skill_meta_path(self, slug):
        return os.path.join(self._skill_dir(slug), "_meta.json")

    def _load_skill_meta(self, slug):
        """Telemetría por skill. Crea valores por defecto si no existe."""
        path = self._skill_meta_path(slug)
        meta = {
            "slug": slug, "version": 1, "uses": 0, "uses_since_refine": 0,
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
            "last_used": None, "last_refined": None, "observations": [],
        }
        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    meta.update(json.load(f) or {})
        except Exception:
            pass
        return meta

    def _save_skill_meta(self, slug, meta):
        try:
            os.makedirs(self._skill_dir(slug), exist_ok=True)
            with open(self._skill_meta_path(slug), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _installed_skill_slugs(self):
        skills_dir = os.path.join(os.path.expanduser("~"), ".claudy", "skills")
        if not os.path.isdir(skills_dir):
            return []
        out = []
        for folder in sorted(os.listdir(skills_dir)):
            if os.path.isfile(os.path.join(skills_dir, folder, "SKILL.md")):
                out.append(folder)
        return out

    def _match_relevant_skills(self, prompt):
        """Devuelve los slugs de skills cuya descripción/nombre se solapan con el prompt.

        Heurística liviana de overlap de tokens — suficiente para contar 'usos'
        sin un segundo llamado al LLM."""
        import re as _re
        if not prompt:
            return []
        p_tokens = set(t for t in _re.findall(r"[a-záéíóúñ0-9]{4,}", prompt.lower()) if t)
        if not p_tokens:
            return []
        matched = []
        for slug in self._installed_skill_slugs():
            try:
                with open(os.path.join(self._skill_dir(slug), "SKILL.md"), "r", encoding="utf-8") as f:
                    head = f.read(600).lower()
            except Exception:
                continue
            s_tokens = set(_re.findall(r"[a-záéíóúñ0-9]{4,}", slug.replace("-", " ").lower()))
            for line in head.splitlines():
                if line.startswith("description:") or line.startswith("## cuándo") or line.startswith("## cuando"):
                    s_tokens |= set(_re.findall(r"[a-záéíóúñ0-9]{4,}", line.lower()))
            overlap = p_tokens & s_tokens
            # nombre directo en el prompt, o solapamiento de 2+ términos significativos
            if slug.replace("-", " ") in prompt.lower() or len(overlap) >= 2:
                matched.append(slug)
        return matched

    def _record_skill_usage(self, prompt):
        """Cuenta el uso de las skills relevantes a este prompt y dispara
        auto-refinamiento al cruzar el umbral. Pensado para correr en background."""
        if self._refining_skill:
            return
        try:
            slugs = self._match_relevant_skills(prompt)
        except Exception:
            slugs = []
        for slug in slugs:
            try:
                meta = self._load_skill_meta(slug)
                meta["uses"] = int(meta.get("uses", 0)) + 1
                meta["uses_since_refine"] = int(meta.get("uses_since_refine", 0)) + 1
                meta["last_used"] = datetime.datetime.now().isoformat(timespec="seconds")
                obs = meta.get("observations", [])
                obs.append(prompt[:200])
                meta["observations"] = obs[-10:]  # ventana rodante
                self._save_skill_meta(slug, meta)
                if meta["uses_since_refine"] >= self._skill_refine_threshold:
                    self._refine_skill(slug, auto=True)
            except Exception:
                continue

    def _refine_skill(self, slug, auto=False):
        """Refina una SKILL.md existente fusionando lo aprendido en usos recientes.

        Hace backup de la versión previa, sube el número de versión y resetea el
        contador. Este es el otro 50% del bucle de Hermes: no solo crear, también
        MEJORAR con la experiencia."""
        slug = self._skill_slug(slug)
        skill_file = os.path.join(self._skill_dir(slug), "SKILL.md")
        if not os.path.isfile(skill_file):
            return f"No existe la skill '{slug}'. Créala primero con /aprender {slug}"
        if self._refining_skill:
            return "Ya hay un refinamiento en curso, espera un momento."

        import re as _re
        self._refining_skill = True
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                current = f.read().strip()
            meta = self._load_skill_meta(slug)

            # Contexto: la skill actual + qué situaciones la dispararon últimamente
            obs = meta.get("observations", [])
            obs_block = "\n".join(f"- {o}" for o in obs[-10:]) or "(sin observaciones registradas)"
            try:
                recent = self._load_memory()[-16:]
                transcript = "\n".join(
                    f"{'Usuario' if m.get('role') == 'Usuario' else 'Claudy'}: {m.get('text','')}"
                    for m in recent
                )[-3500:]
            except Exception:
                transcript = ""

            refine_prompt = (
                "Eres un curador de skills. Vas a MEJORAR una skill existente (un archivo "
                "SKILL.md) usando la experiencia acumulada de cómo se usó realmente.\n\n"
                "=== SKILL ACTUAL ===\n" + current + "\n\n"
                "=== SITUACIONES RECIENTES QUE LA DISPARARON ===\n" + obs_block + "\n\n"
                "=== CONVERSACIÓN RECIENTE (contexto) ===\n" + (transcript or "(sin contexto)") + "\n\n"
                "Reescribe la skill COMPLETA, mejorándola: corrige pasos imprecisos, agrega "
                "reglas nuevas aprendidas, cubre los casos reales de arriba, y elimina lo que "
                "sobra. Mantén EXACTAMENTE el mismo formato (frontmatter ---, # título, "
                "## Cuándo usarla, ## Pasos, ## Reglas, ## Ejemplo). Conserva el mismo "
                "'name:' en el frontmatter. Devuelve SOLO el contenido del archivo, sin "
                "explicaciones ni fences de markdown."
            )

            try:
                improved = self.send_quick_message(refine_prompt, _skip_skill_action=True)
            except Exception as e:
                return f"Error al refinar la skill: {e}"

            improved = _re.sub(r'^```[a-z]*\n', '', (improved or "").strip())
            improved = _re.sub(r'\n```$', '', improved).strip()
            if not improved or len(improved) < 40 or not improved.startswith("---"):
                return f"El refinamiento no produjo una skill válida. '{slug}' queda igual."

            # Backup de la versión previa antes de sobrescribir
            old_ver = int(meta.get("version", 1))
            try:
                backup = os.path.join(self._skill_dir(slug), f"SKILL.v{old_ver}.bak.md")
                with open(backup, "w", encoding="utf-8") as f:
                    f.write(current)
            except Exception:
                pass

            with open(skill_file, "w", encoding="utf-8") as f:
                f.write(improved)

            meta["version"] = old_ver + 1
            meta["uses_since_refine"] = 0
            meta["last_refined"] = datetime.datetime.now().isoformat(timespec="seconds")
            self._save_skill_meta(slug, meta)

            msg = (
                f"✨ Skill '{slug}' refinada → v{meta['version']} "
                f"(tras {meta.get('uses', 0)} usos).\n"
                f"Backup: SKILL.v{old_ver}.bak.md"
            )
            if auto:
                # Aviso discreto: la mejora ocurrió sola en background
                try:
                    self.after(0, lambda: self._show_notification(
                        "Claudy aprendió", f"Mejoré la skill '{slug}' sola (v{meta['version']})."))
                except Exception:
                    pass
                self._debug_log("AUTO-REFINED SKILL", f"{slug} -> v{meta['version']}")
            return msg
        finally:
            self._refining_skill = False

    def _skill_stats(self):
        """Reporte de uso/versión de las skills — visibiliza el bucle de aprendizaje."""
        slugs = self._installed_skill_slugs()
        if not slugs:
            return "No hay skills instaladas todavía. Crea una con /aprender <nombre>."
        lines = []
        for slug in slugs:
            m = self._load_skill_meta(slug)
            usr = int(m.get("uses_since_refine", 0))
            falta = max(0, self._skill_refine_threshold - usr)
            lines.append(
                f"  {slug}  ·  v{m.get('version', 1)}  ·  {m.get('uses', 0)} usos"
                + (f"  ·  auto-mejora en {falta}" if falta else "  ·  lista para refinar")
            )
        return (
            f"Skills y su aprendizaje ({len(slugs)}):\n\n" + "\n".join(lines)
            + "\n\nRefinar manual: /skill mejorar <nombre>"
        )

    # ==============================================================
    # CRON ENGINE
    # ==============================================================

    def _load_cron_json(self):
        if not os.path.exists(self._cron_file):
            return []
        try:
            with open(self._cron_file, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_cron_json(self):
        os.makedirs(os.path.dirname(self._cron_file), exist_ok=True)
        with open(self._cron_file, "w", encoding="utf-8") as f:
            json.dump(self._cron_jobs, f, indent=2, ensure_ascii=False)

    def _start_cron_engine(self):
        self._cron_jobs = self._load_cron_json()

        def engine_loop():
            while True:
                try:
                    now = datetime.datetime.now()
                    for job in self._cron_jobs[:]:
                        if not job.get("enabled", True):
                            continue
                        last = job.get("last_fired", "")
                        fire = False
                        if job["type"] == "interval":
                            if not last:
                                fire = True
                            else:
                                try:
                                    last_dt = datetime.datetime.fromisoformat(last)
                                    elapsed = (now - last_dt).total_seconds() / 60
                                    if elapsed >= job["interval_min"]:
                                        fire = True
                                except Exception:
                                    fire = True
                        elif job["type"] == "daily":
                            if last and last[:10] == now.strftime("%Y-%m-%d"):
                                continue
                            h, m = job.get("hour", 0), job.get("minute", 0)
                            # Catch-up: dispara una vez al día si ya pasó la hora,
                            # aunque Claudy se haya abierto más tarde (no solo en el minuto exacto).
                            if now.hour > h or (now.hour == h and now.minute >= m):
                                fire = True
                        elif job["type"] == "weekly":
                            if last and last[:10] == now.strftime("%Y-%m-%d"):
                                continue
                            wd = job.get("weekday", 0)  # 0=lunes ... 6=domingo
                            h, m = job.get("hour", 0), job.get("minute", 0)
                            # Catch-up: dispara una vez si es el día objetivo y ya pasó la hora,
                            # aunque Claudy se haya abierto más tarde (no solo en el minuto exacto).
                            if now.weekday() == wd and (now.hour > h or (now.hour == h and now.minute >= m)):
                                fire = True
                        if fire:
                            job["last_fired"] = now.isoformat()
                            self._save_cron_json()
                            self.after(0, lambda j=job.copy(): self._execute_cron_job(j))
                    time.sleep(30)
                except Exception:
                    time.sleep(60)

        threading.Thread(target=engine_loop, daemon=True, name="cron-engine").start()

    def _execute_cron_job(self, job):
        # Trabajos de recordatorio: alarma de Claudy + correo, sin pasar por el LLM.
        if job.get("action") == "reminder":
            self._execute_cron_reminder(job)
            return
        # Trabajos de comando: ejecuta un programa/script externo (sin pasar por el LLM).
        if job.get("action") == "command":
            self._execute_cron_command(job)
            return
        msg = job.get("message", "")
        if not msg:
            return
        try:
            result = self.send_quick_message(msg)
            result = self._strip_markdown(result)
            notification = f"[CRON] {msg[:80]}\n\n{result}"
            # Show in desktop bubble
            self.show_chat_bubble(notification[:500])
            # F3.20 Native Windows toast
            try:
                self._notify("Claudy CRON", result[:200])
            except Exception:
                pass
            try:
                self.after(0, lambda: self._set_state_briefly("wave", 1500))
            except Exception:
                pass
            self._fire_hook("on_cron", message=msg, result=result)
            # Send to Telegram if available
            self._cron_notify_telegram(notification[:500])
        except Exception:
            pass

    def _execute_cron_command(self, job):
        """Ejecuta un comando/script externo programado.
        El job define: "command" (lista de args o string), "cwd" (opcional) y
        "label" (opcional, para la notificación). Pensado para automatizaciones
        como el correo de facturación QCORE SPA."""
        cmd = job.get("command")
        if not cmd:
            return
        label = job.get("label") or "Tarea programada"
        cwd = job.get("cwd") or None

        def _run():
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                shell = isinstance(cmd, str)
                proc = subprocess.run(
                    cmd, cwd=cwd, shell=shell, capture_output=True, text=True,
                    timeout=job.get("timeout", 180), creationflags=flags,
                )
                ok = proc.returncode == 0
                out = (proc.stdout or "").strip()[-200:]
                err = (proc.stderr or "").strip()[-200:]
                estado = "OK" if ok else f"ERROR (code {proc.returncode})"
                resumen = f"[CRON cmd] {label}: {estado}"
                if not job.get("silent"):
                    try:
                        self.after(0, lambda: self._notify("Claudy CRON", resumen[:200]))
                    except Exception:
                        pass
                # Telegram + log
                self._cron_notify_telegram(f"{resumen}\n{out or err}")
                self._fire_hook("on_cron", message=label, result=out or err)
            except Exception as e:
                try:
                    self._cron_notify_telegram(f"[CRON cmd] {label}: EXCEPTION {e}")
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True, name="cron-command").start()

    def _execute_cron_reminder(self, job):
        """Dispara un recordatorio: alarma visual/sonora de Claudy + (opcional) correo.
        Si el job trae "silent": true, NO muestra la alarma emergente y se entrega
        solo como correo (y Telegram), p.ej. para digests diarios por email."""
        msg = job.get("message") or "Recordatorio"
        silent = job.get("silent", False)
        # 1) Alarma de Claudy (burbuja + beep + toast + chat) — se omite si es silencioso.
        if not silent:
            try:
                self._fire_alarm_notify(msg)
            except Exception:
                pass
        # 2) Telegram, si está disponible
        try:
            self._cron_notify_telegram(msg)
        except Exception:
            pass
        # 3) Correo, si el job lo pide y hay SMTP configurado
        email = job.get("email")
        if email and email.get("to"):
            threading.Thread(
                target=self._send_reminder_email, args=(email,), daemon=True
            ).start()

    def _send_reminder_email(self, email):
        """Envía el correo del recordatorio por SMTP (config.json -> email).
        Si no hay credenciales, avisa en el chat sin romper la alarma."""
        try:
            import claudy_extras as ex
        except Exception:
            return
        try:
            cfg = self.load_claudy_config().get("email", {})
        except Exception:
            cfg = {}
        to_list = email.get("to") or []
        subject = email.get("subject") or "Recordatorio Claudy"
        body = email.get("body") or ""
        if not cfg.get("smtp_host"):
            chat = getattr(self, "_chat_view", None)
            if chat:
                self.after(0, lambda: chat.add_system(
                    "📧 Recordatorio listo, pero falta configurar el correo para enviarlo. "
                    "Agrega en `~/.claudy/config.json`:\n"
                    '`{"email":{"smtp_host":"smtp.gmail.com","smtp_port":465,'
                    '"smtp_user":"jorge.castro@qcorespa.com","smtp_pass":"APP_PASSWORD",'
                    '"from":"jorge.castro@qcorespa.com"}}`'
                ))
            return
        for to in to_list:
            try:
                ex.send_email_smtp(to, subject, body, cfg)
            except Exception:
                pass

    def _cron_notify_telegram(self, text):
        if not self._telegram_bot_app or not self._telegram_allowed_users:
            return
        import asyncio
        try:
            for uid in list(self._telegram_allowed_users)[:3]:
                async def send():
                    try:
                        await self._telegram_bot_app.bot.send_message(
                            chat_id=int(uid), text=f"[Claudy Cron]\n{text}"
                        )
                    except Exception:
                        pass
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(send())
                except Exception:
                    pass
        except Exception:
            pass

    def _parse_cron_nl(self, prompt):
        """
        Parse natural-language cron requests in Spanish.
        Returns (kind, params, message) or None.
          kind = "interval", params = minutes
          kind = "daily",    params = (hour, minute)
        """
        text = prompt.strip()
        low = text.lower()

        # Skip if not a scheduling request
        triggers = ("recuerdame", "recuérdame", "avisame", "avísame", "avisa",
                    "recordatorio", "programa", "agenda", "cada ", "todos los",
                    "todas las", "diariamente", "diario", "/cron")
        if not any(t in low for t in triggers):
            return None

        # ---- INTERVAL: "cada N min|hora|horas" ----
        m = re.search(r'cada\s+(\d+)\s*(minutos?|mins?|m\b|horas?|h\b|segundos?|s\b)', low)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            if unit.startswith("s"):
                interval_min = max(1, n // 60)
            elif unit.startswith("h"):
                interval_min = n * 60
            else:
                interval_min = n
            msg = self._cron_strip_prefix(text)
            msg = re.sub(r'cada\s+\d+\s*(minutos?|mins?|m\b|horas?|h\b|segundos?|s\b)\s*', '', msg, count=1, flags=re.IGNORECASE).strip()
            msg = re.sub(r'^[,:\-\s]+', '', msg)
            if msg:
                return ("interval", interval_min, msg)

        # ---- DAILY: "a las HH(:MM)? (am|pm)?" ----
        # "a las 9", "a las 9am", "a las 14:30", "a las 22 hrs", "a las 9 de la noche"
        dm = re.search(r'a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|hrs|h)?(?:\s+de\s+la\s+(manana|mañana|tarde|noche))?', low)
        if dm:
            h = int(dm.group(1))
            mins = int(dm.group(2) or 0)
            ampm = (dm.group(3) or "").lower()
            partofday = (dm.group(4) or "").lower()
            if ampm == "pm" and h < 12:
                h += 12
            if ampm == "am" and h == 12:
                h = 0
            if partofday in ("tarde", "noche") and h < 12:
                h += 12
            if partofday in ("manana", "mañana") and h == 12:
                h = 0
            if 0 <= h <= 23 and 0 <= mins <= 59:
                msg = self._cron_strip_prefix(text)
                msg = re.sub(r'a\s+las?\s+\d{1,2}(?::\d{2})?\s*(am|pm|hrs|h)?(\s+de\s+la\s+(manana|mañana|tarde|noche))?\s*', '', msg, count=1, flags=re.IGNORECASE).strip()
                msg = re.sub(r'\b(todos\s+los\s+d[ií]as|diariamente|diario|cada\s+d[ií]a)\b\s*', '', msg, flags=re.IGNORECASE).strip()
                msg = re.sub(r'^[,:\-\s]+', '', msg)
                if msg:
                    return ("daily", (h, mins), msg)

        return None

    def _cron_strip_prefix(self, text):
        """Remove leading trigger words like 'recuerdame', 'avisame', '/cron'."""
        t = text
        t = re.sub(r'^/cron\s+', '', t, flags=re.IGNORECASE)
        t = re.sub(r'^(recuerdame|recuérdame|avisame|avísame|avisa|agenda|programa|recordatorio[:\s]*|que)\s+', '', t, flags=re.IGNORECASE)
        return t.strip()

    def _generate_cron_expression(self, prompt):
        """Generate a standard 5-field cron expression from Spanish text."""
        text = (prompt or "").strip()
        low = text.lower()
        if not any(k in low for k in (
            "/cron expr", "/cronexp", "generar cron", "genera cron", "crear cron",
            "crea cron", "expresion cron", "expresión cron", "cron para", "cron de"
        )):
            return None

        spec = re.sub(
            r'^(/cron\s+expr|/cronexp|generar\s+cron|genera\s+cron|crear\s+cron|crea\s+cron|'
            r'expresi[oó]n\s+cron|cron\s+(?:para|de))\s*[:\-]?\s*',
            '',
            text,
            flags=re.IGNORECASE,
        ).strip()
        if not spec:
            return (
                "Dime el horario que quieres convertir a cron.\n\n"
                "Ejemplos:\n"
                "  /cron expr cada 15 minutos\n"
                "  genera cron lunes a viernes a las 9:30\n"
                "  cron para el dia 1 de cada mes a las 8"
            )

        low_spec = spec.lower()

        def parse_time(default_hour=9, default_minute=0):
            m = re.search(
                r'a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|hrs|h)?'
                r'(?:\s+de\s+la\s+(manana|mañana|tarde|noche))?',
                low_spec,
            )
            if not m:
                return default_hour, default_minute, "hora por defecto 09:00"
            h = int(m.group(1))
            minute = int(m.group(2) or 0)
            ampm = (m.group(3) or "").lower()
            partofday = (m.group(4) or "").lower()
            if ampm == "pm" and h < 12:
                h += 12
            if ampm == "am" and h == 12:
                h = 0
            if partofday in ("tarde", "noche") and h < 12:
                h += 12
            if partofday in ("manana", "mañana") and h == 12:
                h = 0
            if not (0 <= h <= 23 and 0 <= minute <= 59):
                raise ValueError("Hora invalida. Usa 0-23 para hora y 0-59 para minutos.")
            return h, minute, f"{h:02d}:{minute:02d}"

        day_names = {
            "domingo": "0", "domingos": "0",
            "lunes": "1",
            "martes": "2",
            "miercoles": "3", "miércoles": "3",
            "jueves": "4",
            "viernes": "5",
            "sabado": "6", "sábado": "6", "sabados": "6", "sábados": "6",
        }

        try:
            # Intervals.
            m = re.search(r'cada\s+(\d+)\s*(minutos?|mins?|m\b)', low_spec)
            if m:
                n = max(1, min(59, int(m.group(1))))
                expr = f"*/{n} * * * *"
                desc = f"cada {n} minuto(s)"
                return self._format_cron_expression_result(expr, desc, spec)

            m = re.search(r'cada\s+(\d+)\s*(horas?|hrs?|h\b)', low_spec)
            if m:
                n = max(1, min(23, int(m.group(1))))
                expr = f"0 */{n} * * *"
                desc = f"cada {n} hora(s)"
                return self._format_cron_expression_result(expr, desc, spec)

            if re.search(r'\bcada\s+minuto\b|\btodos\s+los\s+minutos\b', low_spec):
                return self._format_cron_expression_result("* * * * *", "cada minuto", spec)

            if re.search(r'\bcada\s+hora\b|\btodas\s+las\s+horas\b', low_spec):
                return self._format_cron_expression_result("0 * * * *", "cada hora", spec)

            # Monthly by day number.
            m = re.search(r'(?:dia|día)\s+(\d{1,2})\s+de\s+cada\s+mes|cada\s+mes\s+(?:el\s+)?(?:dia|día)\s+(\d{1,2})', low_spec)
            if m:
                day = int(m.group(1) or m.group(2))
                if not 1 <= day <= 31:
                    raise ValueError("Dia de mes invalido. Usa 1-31.")
                h, minute, time_desc = parse_time()
                expr = f"{minute} {h} {day} * *"
                return self._format_cron_expression_result(expr, f"el dia {day} de cada mes a las {time_desc}", spec)

            # Week ranges and named days.
            h, minute, time_desc = parse_time()
            if re.search(r'lunes\s+a\s+viernes|d[ií]as\s+h[aá]biles|entre\s+semana', low_spec):
                return self._format_cron_expression_result(f"{minute} {h} * * 1-5", f"lunes a viernes a las {time_desc}", spec)

            if re.search(r'fines?\s+de\s+semana|sabados?\s+y\s+domingos?|s[aá]bados?\s+y\s+domingos?', low_spec):
                return self._format_cron_expression_result(f"{minute} {h} * * 6,0", f"fines de semana a las {time_desc}", spec)

            selected_days = []
            for name, value in day_names.items():
                if re.search(rf'\b{name}\b', low_spec) and value not in selected_days:
                    selected_days.append(value)
            if selected_days:
                expr = f"{minute} {h} * * {','.join(selected_days)}"
                return self._format_cron_expression_result(expr, f"dias seleccionados a las {time_desc}", spec)

            # Daily fallback when time is present or text says daily.
            if re.search(r'todos\s+los\s+d[ií]as|diario|diariamente|cada\s+d[ií]a|a\s+las?', low_spec):
                expr = f"{minute} {h} * * *"
                return self._format_cron_expression_result(expr, f"todos los dias a las {time_desc}", spec)

        except ValueError as e:
            return f"No pude generar el cron: {e}"

        return (
            "No pude convertirlo a cron con seguridad.\n\n"
            "Prueba con algo como:\n"
            "  genera cron cada 10 minutos\n"
            "  genera cron todos los dias a las 8:30\n"
            "  genera cron lunes a viernes a las 18:00\n"
            "  genera cron dia 1 de cada mes a las 9"
        )

    def _format_cron_expression_result(self, expr, description, original):
        return (
            "Expresion cron generada:\n\n"
            f"  {expr}\n\n"
            f"Significado: {description}\n"
            f"Entrada: {original}\n\n"
            "Formato: minuto hora dia_mes mes dia_semana\n"
            "Nota: usa cron Unix de 5 campos."
        )

    def _add_cron_interval(self, interval_min, message):
        job = {
            "id": str(int(time.time())),
            "type": "interval",
            "interval_min": interval_min,
            "message": message,
            "last_fired": "",
            "enabled": True,
            "created": datetime.datetime.now().isoformat(),
        }
        self._cron_jobs.append(job)
        self._save_cron_json()
        return f"Tarea programada cada {interval_min} min: {message[:80]}"

    def _add_cron_daily(self, hour, minute, message):
        job = {
            "id": str(int(time.time())),
            "type": "daily",
            "hour": hour,
            "minute": minute,
            "message": message,
            "last_fired": "",
            "enabled": True,
            "created": datetime.datetime.now().isoformat(),
        }
        self._cron_jobs.append(job)
        self._save_cron_json()
        return f"Tarea diaria a las {hour:02d}:{minute:02d}: {message[:80]}"

    _WEEKDAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

    # Nombre de día -> índice de la semana del motor cron (0=lunes ... 6=domingo,
    # igual que datetime.weekday()). Incluye variantes con/sin acento y plurales.
    _WEEKDAY_MAP = {
        "lunes": 0,
        "martes": 1,
        "miercoles": 2, "miércoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sabado": 5, "sábado": 5, "sabados": 5, "sábados": 5,
        "domingo": 6, "domingos": 6,
    }

    def _add_cron_weekly(self, weekday, hour, minute, message, action=None, email=None):
        job = {
            "id": str(int(time.time())),
            "type": "weekly",
            "weekday": weekday,
            "hour": hour,
            "minute": minute,
            "message": message,
            "last_fired": "",
            "enabled": True,
            "created": datetime.datetime.now().isoformat(),
        }
        if action:
            job["action"] = action
        if email:
            job["email"] = email
        self._cron_jobs.append(job)
        self._save_cron_json()
        day = self._WEEKDAY_NAMES[weekday] if 0 <= weekday < 7 else "?"
        return f"Tarea semanal los {day} a las {hour:02d}:{minute:02d}: {message[:80]}"

    def _list_cron_jobs(self):
        if not self._cron_jobs:
            return ("No hay tareas programadas.\n\n"
                    "/cron cada 30 min <mensaje>\n"
                    "/cron a las 22:00 <mensaje>\n"
                    "/cron los martes a las 9 <mensaje>\n"
                    "/cron list\n"
                    "/cron editar <num> <campo> <valor>\n"
                    "/cron off|on <num>\n"
                    "/cron delete <num>")
        lines = ["Tareas programadas:", "=" * 40]
        for i, j in enumerate(self._cron_jobs, 1):
            t = j["type"]
            if t == "interval":
                schedule = f"cada {j['interval_min']} min"
            elif t == "weekly":
                wd = j.get("weekday", 0)
                day = self._WEEKDAY_NAMES[wd] if 0 <= wd < 7 else "?"
                schedule = f"los {day} a las {j.get('hour',0):02d}:{j.get('minute',0):02d}"
            else:
                schedule = f"diario a las {j.get('hour',0):02d}:{j.get('minute',0):02d}"
            enabled = "ON" if j.get("enabled", True) else "OFF"
            desc = j.get("message") or j.get("label") or (f"[{j.get('action')}]" if j.get("action") else "")
            lines.append(f"  [{i}] [{enabled}] {schedule}: {desc[:60]}")
        lines.append("")
        lines.append("Gestionar:")
        lines.append("  /cron editar <num> hora 22:30   (o: cada 45 min / dia martes / mensaje ...)")
        lines.append("  /cron off <num>   pausar      /cron on <num>   activar")
        lines.append("  /cron delete <num>   eliminar")
        return "\n".join(lines)

    def _delete_cron_job(self, idx):
        if idx < 0 or idx >= len(self._cron_jobs):
            return f"Numero invalido. Hay {len(self._cron_jobs)} tareas."
        removed = self._cron_jobs.pop(idx)
        self._save_cron_json()
        return f"Tarea eliminada: {removed.get('message','')[:60]}"

    def _toggle_cron_job(self, idx, enabled):
        """Pausa (enabled=False) o reanuda (enabled=True) una tarea."""
        if idx < 0 or idx >= len(self._cron_jobs):
            return f"Numero invalido. Hay {len(self._cron_jobs)} tareas."
        self._cron_jobs[idx]["enabled"] = bool(enabled)
        self._save_cron_json()
        estado = "activada" if enabled else "pausada"
        return f"Tarea {idx+1} {estado}: {self._cron_jobs[idx].get('message','')[:60]}"

    def _edit_cron_job(self, idx, *, message=None, hour=None, minute=None,
                       interval_min=None, weekday=None):
        """Modifica una tarea existente. Solo cambia los campos indicados."""
        if idx < 0 or idx >= len(self._cron_jobs):
            return f"Numero invalido. Hay {len(self._cron_jobs)} tareas."
        job = self._cron_jobs[idx]
        cambios = []
        if message is not None:
            job["message"] = message
            cambios.append(f"mensaje «{message[:50]}»")
        if interval_min is not None:
            job["type"] = "interval"
            job["interval_min"] = interval_min
            cambios.append(f"cada {interval_min} min")
        if weekday is not None:
            job["type"] = "weekly"
            job["weekday"] = weekday
            day = self._WEEKDAY_NAMES[weekday] if 0 <= weekday < 7 else "?"
            cambios.append(f"día {day}")
        if hour is not None:
            job["hour"] = hour
            if minute is not None:
                job["minute"] = minute
            # Cambiar la hora implica un horario fijo (diario salvo que ya sea semanal).
            if job.get("type") not in ("daily", "weekly"):
                job["type"] = "daily"
            cambios.append(f"hora {hour:02d}:{job.get('minute', 0):02d}")
        elif minute is not None:
            job["minute"] = minute
            cambios.append(f"minuto {minute:02d}")
        if not cambios:
            return ("No indicaste qué cambiar.\n"
                    "Ej: /cron editar 1 hora 22:30  |  /cron editar 1 mensaje nuevo texto  |  "
                    "/cron editar 1 cada 45 min  |  /cron editar 1 dia martes")
        # Reinicia el disparo para que el nuevo horario aplique limpio.
        job["last_fired"] = ""
        self._save_cron_json()
        return f"Tarea {idx+1} actualizada ({', '.join(cambios)})."

    def _apply_cron_edit_spec(self, idx, rest):
        """Interpreta el 'campo valor' de una edición y aplica el cambio."""
        rest = rest.strip()
        rlow = rest.lower()
        m = re.match(r'cada\s+(\d+)\s*(minutos?|mins?|m|horas?|hrs?|h)\b', rlow)
        if m:
            n = int(m.group(1))
            interval = n * 60 if m.group(2).startswith("h") else n
            return self._edit_cron_job(idx, interval_min=max(1, interval))
        m = re.search(r'(?:hora|a\s+las?)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', rlow)
        if m:
            h = int(m.group(1))
            minute = int(m.group(2) or 0)
            ampm = (m.group(3) or "")
            if ampm == "pm" and h < 12:
                h += 12
            if ampm == "am" and h == 12:
                h = 0
            if not (0 <= h <= 23 and 0 <= minute <= 59):
                return "Hora inválida. Usa 0-23 y 0-59."
            return self._edit_cron_job(idx, hour=h, minute=minute)
        m = re.match(r'(?:dia|día)\s+(\w+)', rlow)
        if m:
            wd = self._WEEKDAY_MAP.get(m.group(1))
            if wd is None:
                return "Día no reconocido. Usa lunes..domingo."
            return self._edit_cron_job(idx, weekday=wd)
        m = re.match(r'(?:mensaje|texto|msg)\s+(.+)', rest, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return self._edit_cron_job(idx, message=m.group(1).strip())
        # Sin campo explícito: se asume que es el nuevo mensaje.
        return self._edit_cron_job(idx, message=rest)

    def _manage_cron_command(self, prompt):
        """Gestión avanzada de tareas: editar, pausar/activar y crear semanales.
        Devuelve el texto de respuesta, o None si no es un comando de gestión."""
        text = (prompt or "").strip()
        low = text.lower()

        # Pausar: /cron off|pausar|desactivar <num>
        m = re.match(r'/cron\s+(?:off|pausar|pausa|desactivar)\s+(\d+)', low)
        if m:
            return self._toggle_cron_job(int(m.group(1)) - 1, False)
        # Activar: /cron on|activar|reanudar <num>
        m = re.match(r'/cron\s+(?:on|activar|activa|reanudar)\s+(\d+)', low)
        if m:
            return self._toggle_cron_job(int(m.group(1)) - 1, True)

        # Editar: /cron editar|edit|modificar|cambiar <num> <campo> <valor>
        m = re.match(r'/cron\s+(?:editar|edit|modificar|cambiar)\s+(\d+)\s+(.+)',
                     text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return self._apply_cron_edit_spec(int(m.group(1)) - 1, m.group(2))

        # Editar en lenguaje natural: "modifica/cambia/edita la tarea N ..."
        m = re.match(r'(?:cambia|cambiar|modifica|modificar|edita|editar)\s+(?:la\s+)?'
                     r'tarea\s+(\d+)\s+(?:a\s+|para\s+|por\s+)?(.+)',
                     text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return self._apply_cron_edit_spec(int(m.group(1)) - 1, m.group(2))

        # Pausar/activar en lenguaje natural.
        m = re.match(r'(?:pausa|pausar|desactiva|desactivar|detén|deten)\s+(?:la\s+)?tarea\s+(\d+)', low)
        if m:
            return self._toggle_cron_job(int(m.group(1)) - 1, False)
        m = re.match(r'(?:activa|activar|reanuda|reanudar)\s+(?:la\s+)?tarea\s+(\d+)', low)
        if m:
            return self._toggle_cron_job(int(m.group(1)) - 1, True)

        # Crear semanal: requiere intención explícita (/cron, o una palabra de
        # agenda como los/cada/todos los/programa/agenda/recuérdame/avísame) para
        # no capturar frases normales tipo "lunes a las 10 entrego el informe".
        m = re.match(
            r'(?:/cron\s+|los?\s+|cada\s+|todos\s+los\s+|'
            r'programa\s+|agenda\s+|recu[eé]rdame\s+(?:que\s+)?|av[ií]same\s+(?:que\s+)?)'
            r'(?:los?\s+|cada\s+)?'
            r'(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)'
            r'\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+(.+)',
            text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            wd = self._WEEKDAY_MAP.get(m.group(1).lower())
            if wd is None:
                return None
            h = int(m.group(2))
            minute = int(m.group(3) or 0)
            ampm = (m.group(4) or "")
            if ampm == "pm" and h < 12:
                h += 12
            if ampm == "am" and h == 12:
                h = 0
            if not (0 <= h <= 23 and 0 <= minute <= 59):
                return "Hora inválida. Usa 0-23 y 0-59."
            return self._add_cron_weekly(wd, h, minute, m.group(5).strip())

        return None

    def _get_skills_context(self):
        return (
            "[ECOSISTEMA DE SKILLS - 1417+ habilidades especializadas disponibles]\n"
            "Tienes acceso a un ecosistema de 1417+ skills que cubren TODOS estos dominios:\n"
            "- Programación: Python, JavaScript, TypeScript, Rust, Go, Java, C++, C#, Ruby, PHP, Swift, Kotlin, Haskell, Elixir, Scala\n"
            "- Frameworks: React, Next.js, Vue, Angular, Svelte, Django, FastAPI, Flask, Laravel, Rails, Spring Boot, .NET\n"
            "- Cloud: AWS, Azure, GCP, Terraform, Kubernetes, Docker, serverless\n"
            "- Bases de datos: PostgreSQL, MySQL, MongoDB, Redis, DynamoDB, CosmosDB, SQLite, Neo4j\n"
            "- IA/ML: RAG, LangChain, LangGraph, PyTorch, TensorFlow, scikit-learn, Hugging Face, MCP\n"
            "- DevOps: CI/CD, GitHub Actions, Jenkins, Prometheus, Grafana, observabilidad\n"
            "- Seguridad: pentesting, OWASP, auditoría, criptografía, ethical hacking\n"
            "- Marketing: SEO, contenido, email marketing, redes sociales, analytics\n"
            "- CRM: HubSpot, Salesforce, Pipedrive, Close, Freshdesk, Zendesk\n"
            "- Productividad: Notion, Obsidian, Linear, Jira, Asana, Trello, Slack\n"
            "- Diseño: UI/UX, Figma, Tailwind, shadcn, Apple HIG, accesibilidad\n"
            "- Blockchain: Solidity, Web3, DeFi, NFTs, smart contracts\n"
            "- Juegos: Unity, Unreal, Godot, Three.js, Phaser\n"
            "- Salud: sueño, nutrición, fitness, salud mental, análisis médico\n"
            "- Personas: simulaciones de Steve Jobs, Elon Musk, Warren Buffett, Yann LeCun\n"
            "\n"
            "HERRAMIENTAS LOCALES ACTIVAS:\n"
            "1. /buscar <tema> - Búsqueda web en tiempo real (DuckDuckGo, gratis).\n"
            "2. /screenshot - Captura la pantalla actual y analiza el contenido.\n"
            "3. /leer <ruta> - Lee archivos de texto, código, CSV, JSON, etc.\n"
            "4. /cmd <comando> - Ejecuta comandos de terminal de forma segura.\n"
            "5. /recordar <tiempo> <mensaje> - Crea recordatorios con notificación.\n"
            "6. /noticias - Resumen de noticias del día.\n"
            "7. /traducir <texto> a <idioma> - Traducción rápida.\n"
            "8. /calc <expresión> - Calculadora (2+2*3, sqrt(16), etc).\n"
            "9. /musica <acción> - Controla Spotify/Windows Media (play, pause, next, prev).\n"
            "10. /tema - Alterna entre modo oscuro y claro.\n"
            "11. /buscar_archivo <nombre> - Busca archivos en el sistema (Desktop, Downloads, Documents).\n"
            "12. /instalar <app> - Busca, descarga e instala aplicaciones de internet.\n"
            "13. /descargar <URL> - Descarga archivos de internet a ~/Downloads/Claudy.\n"
            "14. /ejecutar <ruta> - Abre/ejecuta archivos con el programa asociado.\n"
            "15. find-skills - Buscar e instalar skills del ecosistema.\n"
            "16. pdf - Crear, leer y analizar PDFs.\n"
            "17. ui-ux-pro-max - Diseño de interfaces profesionales.\n"
            "18. obsidian - Crear notas, buscar notas, gestionar vault.\n"
            "\n"
            "OBSIDIAN INTEGRADO: Puedes crear notas en Obsidian, buscar notas existentes, "
            "y gestionar tu vault. Las notas se guardan en el vault configurado.\n"
            "\n"
            "Para cualquier tema de los 1417+ skills, responde con tu conocimiento experto. "
            "Si el usuario pide algo específico de una skill, ofrece ayuda directa.\n"
            "[Fin de skills]\n\n"
        )

    def _resolve_last_folder_reference(self, prompt):
        """If prompt mentions 'esta carpeta'/'la carpeta anterior'/'esta ultima carpeta',
        return the absolute folder path (from _last_file_artifact_path). Otherwise ''.
        """
        text = (prompt or "").lower()
        refs = (
            "esta ultima carpeta", "esta última carpeta",
            "la ultima carpeta", "la última carpeta",
            "la carpeta anterior", "esta carpeta",
            "esa carpeta", "misma carpeta",
        )
        if not any(r in text for r in refs):
            return ""
        last = getattr(self, "_last_file_artifact_path", None)
        if not last:
            return ""
        return last if os.path.isdir(last) else os.path.dirname(last)

    def _try_handle_create_document(self, prompt):
        """Detect 'crea(me) (un) archivo X.docx/X.pdf [en CARPETA] con/sobre/del TEMA'
        and create the document with LLM-generated content. Returns (handled, result)."""
        text = prompt.strip()
        # Variant A: "crea(me) archivo|presentacion|excel docx|pdf|xlsx|pptx [NOMBRE] [en LOC] (con|sobre|...) TEMA"
        # Variant B: "crea(me) archivo NOMBRE.docx|.pdf|.xlsx|.pptx [en LOC] (con|sobre|...) TEMA"
        verb_re = r"(?:cr[eé]a(?:me|r)?|genera(?:me)?|haz(?:me)?|hacer|arma(?:me)?|prepara(?:me)?)"
        kind_re = r"(?:archivo|documento|doc|file|presentaci[oó]n|presentacion|diapositivas|slides|deck|excel|hoja(?:\s+de\s+c[aá]lculo)?|planilla|spreadsheet|libro)"
        connector_re = r"(?:con|sobre|del|de|acerca\s+de|que\s+(?:tenga|contenga|diga|incluya|muestre))"
        location_re = r"(?:en|dentro\s+de)"
        fmt_alts = r"(docx|pdf|word|xlsx|excel|pptx|powerpoint|ppt)"

        # Detect format hint also from kind word itself (excel/presentacion)
        kind_match = re.match(rf"^{verb_re}\s+(?:un[ao]?\s+|el\s+|la\s+)?({kind_re})\b", text, re.I)
        kind_word = kind_match.group(1).lower() if kind_match else ""

        # Variant A
        m = re.match(
            rf"^{verb_re}\s+(?:un[ao]?\s+|el\s+|la\s+)?{kind_re}\s+"
            rf"{fmt_alts}\b\s*"
            rf"(?:(?!{location_re}\s|{connector_re}\s)(\S.*?)\s+)?"
            rf"(?:{location_re}\s+(.+?)\s+)?"
            rf"{connector_re}\s+(.+)$",
            text, re.I,
        )
        if m:
            fmt_word = m.group(1)
            name_part = m.group(2) or ""
            location_part = m.group(3)
            topic = m.group(4)
        else:
            # Variant B: name has explicit extension
            m = re.match(
                rf"^{verb_re}\s+(?:un[ao]?\s+|el\s+|la\s+)?{kind_re}\s+"
                rf"(\S+\.(?:docx|pdf|xlsx|pptx))"
                rf"(?:\s+{location_re}\s+(.+?))?"
                rf"\s+{connector_re}\s+(.+)$",
                text, re.I,
            )
            if m:
                fmt_word = None
                name_part = m.group(1)
                location_part = m.group(2)
                topic = m.group(3)
            else:
                # Variant C: format implied by kind word (excel/presentacion sin docx/pdf)
                m = re.match(
                    rf"^{verb_re}\s+(?:un[ao]?\s+|el\s+|la\s+)?{kind_re}\s+"
                    rf"(?:(?!{location_re}\s|{connector_re}\s)(\S.*?)\s+)?"
                    rf"(?:{location_re}\s+(.+?)\s+)?"
                    rf"{connector_re}\s+(.+)$",
                    text, re.I,
                )
                if not m or not kind_word:
                    return False, ""
                fmt_word = None
                name_part = m.group(1) or ""
                location_part = m.group(2)
                topic = m.group(3)

        name_clean = (name_part or "").strip().strip('"\'')
        fmt = ""
        if fmt_word:
            fw = fmt_word.lower()
            if fw in ("docx", "word"):
                fmt = "docx"
            elif fw == "pdf":
                fmt = "pdf"
            elif fw in ("xlsx", "excel"):
                fmt = "xlsx"
            elif fw in ("pptx", "powerpoint", "ppt"):
                fmt = "pptx"
        elif name_clean.lower().endswith(".docx"):
            fmt = "docx"
        elif name_clean.lower().endswith(".pdf"):
            fmt = "pdf"
        elif name_clean.lower().endswith(".xlsx"):
            fmt = "xlsx"
        elif name_clean.lower().endswith(".pptx"):
            fmt = "pptx"
        elif kind_word:
            if "excel" in kind_word or "hoja" in kind_word or "planilla" in kind_word or "spreadsheet" in kind_word or "libro" in kind_word:
                fmt = "xlsx"
            elif "presentaci" in kind_word or "diapositiv" in kind_word or "slides" in kind_word or "deck" in kind_word:
                fmt = "pptx"
        if not fmt:
            return False, ""

        # Resolve location: explicit phrase, or 'esta carpeta' reference, or Downloads default
        folder = ""
        if location_part:
            ref = self._resolve_last_folder_reference(location_part)
            if ref:
                folder = ref
            else:
                low = location_part.lower()
                if any(w in low for w in ("esta carpeta", "ultima carpeta", "última carpeta", "carpeta anterior", "esa carpeta", "misma carpeta")):
                    # Reference but no memory available -> fall back to Downloads silently
                    folder = ""
                else:
                    folder = location_part.strip()
        else:
            ref = self._resolve_last_folder_reference(prompt)
            if ref:
                folder = ref
        if not folder:
            folder = os.path.expanduser("~/Downloads")

        # Strip extension from name to rebuild it cleanly; derive from topic if missing
        bare = re.sub(r"\.(docx|pdf)$", "", name_clean, flags=re.I).strip()
        if not bare:
            slug = re.sub(r"[^A-Za-z0-9_\- ]+", "", topic).strip()
            slug = re.sub(r"\s+", "_", slug)[:60] or "documento"
            bare = slug
        full_path = os.path.join(folder, f"{bare}.{fmt}")

        topic_clean = topic.strip().rstrip(".")

        try:
            import claudy_powers as cp
        except Exception as e:
            return True, f"Error: {e}"

        # ALL formats: try to ground content with web search first
        try:
            self.after(0, lambda: self._set_response_text(f"Buscando datos en internet sobre: {topic_clean}..."))
        except Exception:
            pass
        web_ctx = self._web_context_for_topic(topic_clean, max_results=8)

        # Load professional formatting rules from skill file
        _skill_rules = ""
        try:
            _skill_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "..", "skills", "professional-document-writer", "SKILL.md"
            )
            if os.path.isfile(_skill_path):
                with open(_skill_path, "r", encoding="utf-8") as _sf:
                    _skill_rules = _sf.read()
        except Exception:
            pass
        if not _skill_rules:
            _skill_rules = (
                "FORMATO PROFESIONAL:\n"
                "- Título con # TÍTULO. Introducción obligatoria.\n"
                "- Secciones con ## y subsecciones con ###. Nunca saltes niveles.\n"
                "- Usa **negritas** para conceptos clave, *cursivas* para énfasis secundario.\n"
                "- Datos comparativos en TABLAS Markdown (| Col | Col |).\n"
                "- Citas importantes con > formato.\n"
                "- Termina con ## Conclusiones y ## Referencias.\n"
                "- NO uses placeholders como [Insertar aquí]. Escribe contenido real.\n"
                "- NO incluyas saludos ni comentarios fuera del documento."
            )

        # Check if user wants images in natural language document creation
        _wants_images_nl = False
        _img_keywords = ("imagen", "imágenes", "imagenes", "foto", "fotos",
                         "ilustra", "ilustracion", "ilustraciones", "visual",
                         "gráfico", "grafico", "con imagen", "con fotos")
        if any(k in prompt.lower() for k in _img_keywords):
            _wants_images_nl = True

        # Format-specific LLM prompts
        if fmt in ("docx", "pdf"):
            llm_prompt = (
                (web_ctx + "\n\n" if web_ctx else "") +
                f"Escribe un documento profesional en espanol sobre: {topic_clean}.\n"
                + ("USA la informacion de internet de arriba como base factual. Cita fuentes al final cuando uses datos especificos. " if web_ctx else "") +
                f"\nDIRECTRICES DE FORMATO PROFESIONAL (sigue TODAS estas reglas):\n{_skill_rules}\n\n"
                "REGLAS ADICIONALES:\n"
                "- Escribe contenido COMPLETO y REAL. NO uses placeholders como [Introducción], [Sección], [Insertar aquí], etc.\n"
                "- Cada sección debe tener párrafos sustanciales (mínimo 2-3 párrafos).\n"
                "- Incluye al menos UNA tabla Markdown con datos relevantes.\n"
                "- Extensión: 500-900 palabras. Solo el contenido del documento, sin preambulo ni cierre."
            )
            content = self._llm_structured(llm_prompt, timeout=180)
            if not content:
                return True, f"No pude generar contenido para '{topic_clean}'."

            # Download and attach images if requested
            if _wants_images_nl and fmt == "docx":
                try:
                    self.after(0, lambda: self._set_response_text(f"Descargando imágenes para: {topic_clean}..."))
                    image_paths = self._download_report_images(topic_clean, max_images=3)
                except Exception:
                    image_paths = []
                if image_paths:
                    return True, cp.create_docx_with_images(full_path, content, image_paths)

            if fmt == "docx":
                return True, cp.create_docx(full_path, content)
            return True, cp.create_pdf(full_path, content)

        if fmt == "xlsx":
            llm_prompt = (
                (web_ctx + "\n\n" if web_ctx else "") +
                f"Genera datos de hoja de calculo profesional en espanol sobre: {topic_clean}.\n"
                + ("USA los datos de internet de arriba como base. Si los datos son incompletos, completa con cifras plausibles pero MARCA esas filas con '(estimado)' al final. " if web_ctx else "") +
                "Responde SOLO con un JSON valido (sin ```fences```) con esta forma exacta:\n"
                '{"name": "NombreHoja", "headers": ["Col1","Col2",...], "rows": [["v1","v2"],...]}\n'
                "Si el tema requiere varias hojas, usa: {\"sheets\": [{\"name\":..., \"headers\":..., \"rows\":...}, ...]}.\n"
                "Entre 8 y 20 filas con datos realistas y concretos. Incluye una columna 'Fuente' al final si usaste datos web. "
                "Sin texto fuera del JSON."
            )
            raw = self._llm_structured(llm_prompt, timeout=180, expect_json=True)
            data = self._extract_json(raw)
            if not data:
                # Last-ditch: build a sheet from the web search snippets themselves
                lines = [ln.strip() for ln in (raw or "").splitlines() if ln.strip() and not ln.strip().startswith("{")]
                rows = []
                if web_ctx:
                    for line in web_ctx.split("\n"):
                        s = line.strip().lstrip("- ").strip()
                        if s and not s.startswith("DATOS DE INTERNET") and not s.startswith("Fuente:"):
                            rows.append([s[:300]])
                if not rows and lines:
                    rows = [[ln[:300]] for ln in lines[:30]]
                if not rows:
                    return True, f"No pude generar datos para '{topic_clean}'. Intenta de nuevo o se mas especifico."
                data = {"name": (bare[:31] or "Datos"), "headers": ["Informacion"], "rows": rows[:40]}
            return True, cp.create_xlsx(full_path, data, title=bare[:31] or "Datos")

        if fmt == "pptx":
            llm_prompt = (
                (web_ctx + "\n\n" if web_ctx else "") +
                f"Genera una presentacion profesional en espanol sobre: {topic_clean}.\n"
                + ("USA los datos de internet de arriba como base factual. " if web_ctx else "") +
                "Responde SOLO con un JSON valido con esta forma exacta:\n"
                "{\n"
                '  "title": "Titulo principal",\n'
                '  "subtitle": "Subtitulo descriptivo",\n'
                '  "theme": "history|nature|tech|business|education|warm|dark|minimal",\n'
                '  "slides": [\n'
                '    {"title": "Titulo slide", "bullets": ["punto 1","punto 2","punto 3"], "image_query": "descripcion visual en INGLES para generar imagen"},\n'
                "    ...\n"
                "  ]\n"
                "}\n"
                "Reglas:\n"
                "- 6 a 10 slides. Cada slide con 3-5 bullets concisos (max 14 palabras).\n"
                "- `theme`: elige el que mejor encaje con el tema (history para historia, tech para tecnologia, nature para naturaleza, etc.).\n"
                "- `image_query`: SIEMPRE en INGLES, visual concreto y especifico, sin texto en la imagen. Ej: 'mapuche warriors traditional dress 19th century', 'santiago chile colonial architecture'.\n"
                "- Sin texto fuera del JSON. Sin ```fences```."
            )
            raw = self._llm_structured(llm_prompt, timeout=180)
            data = self._extract_json(raw) or {}
            if not data.get("slides"):
                return True, f"No pude generar la estructura para '{topic_clean}'. Intenta otra vez o se mas especifico."
            return True, cp.create_pptx(
                full_path,
                slides=data.get("slides") or [],
                title=data.get("title") or topic_clean,
                subtitle=data.get("subtitle") or "",
                theme=(data.get("theme") or "business").lower(),
                images=True,
            )

        return False, ""

    def _needs_real_data(self, topic):
        """Heuristic: does this topic require fresh/real-world data (not LLM-fabricated)?"""
        if not topic:
            return False
        t = topic.lower()
        keywords = (
            "venta", "ingreso", "facturaci", "ganancia", "utilidad", "revenue",
            "presupuesto", "balance", "accion", "bolsa", "stock", "precio",
            "poblacion", "habitante", "censo", "pib", "inflacion", "tasa", "tipo de cambio",
            "estadistic", "ranking", "top ", "lista de",
            "ultimo año", "ultimos año", "ultima decada", "historico", "histórico",
            "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026",
            "real", "actual", "reciente",
        )
        if any(k in t for k in keywords):
            return True
        # Proper noun-ish (likely company/person/place needing factual data)
        words = topic.split()
        proper = sum(1 for w in words if w and w[0].isupper() and len(w) > 2)
        return proper >= 1 and len(words) <= 12

    def _web_context_for_topic(self, topic, max_results=6, snippet_chars=400):
        """Fetch web search snippets formatted as plain context for the LLM."""
        try:
            items = self._search_files_online(topic, max_results=max_results)
        except Exception:
            items = []
        if not items:
            return ""
        chunks = []
        for it in items[:max_results]:
            title = (it.get("title") or "").strip()
            snip = (it.get("snippet") or "").strip()
            url = (it.get("url") or "").strip()
            if not (title or snip):
                continue
            chunks.append(f"- {title}\n  {snip[:snippet_chars]}\n  Fuente: {url}")
        return ("DATOS DE INTERNET sobre '" + topic + "':\n" + "\n".join(chunks)) if chunks else ""

    def _quick_text_pollinations(self, prompt, timeout=180):
        """Direct call to Pollinations text API (free, no key, no opencode roundtrip).
        Used as a fast/reliable fallback for structured generation when the main
        LLM provider times out or fails."""
        try:
            payload = {
                "model": "openai",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
                "temperature": 0.4,
            }
            req = urllib.request.Request(
                "https://text.pollinations.ai/openai",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Claudy/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or []
            if choices:
                msg = choices[0].get("message") or {}
                return msg.get("content", "").strip()
            return data.get("response") or ""
        except Exception as e:
            return f"__ERROR__: {e}"

    def _llm_structured(self, prompt, timeout=180, expect_json=True):
        """Get structured text from LLM with multi-provider fallback.
        Order: main provider -> Pollinations -> Pollinations with stricter retry."""
        candidates = []
        # 1) Main provider
        try:
            r = self.send_quick_message(prompt, _skip_skill_action=True)
            if r and not r.lower().startswith("mmm... algo fall"):
                candidates.append(r)
                if expect_json and "{" in r and "}" in r:
                    return r
        except Exception:
            pass
        # 2) Pollinations
        fb = self._quick_text_pollinations(prompt, timeout=timeout)
        if fb and not fb.startswith("__ERROR__"):
            candidates.append(fb)
            if not expect_json or ("{" in fb and "}" in fb):
                return fb
        # 3) Stricter retry: ask only for JSON, no preamble
        if expect_json:
            strict = (
                "Devuelve UNICAMENTE un objeto JSON valido, nada mas. Sin texto antes ni despues, "
                "sin fences ```. Si no puedes responder con JSON, devuelve {}.\n\n" + prompt
            )
            fb2 = self._quick_text_pollinations(strict, timeout=timeout)
            if fb2 and not fb2.startswith("__ERROR__"):
                return fb2
        return candidates[-1] if candidates else ""

    def _extract_json(self, text):
        """Try hard to parse JSON from a possibly noisy LLM response."""
        if not text:
            return None
        s = text.strip()
        # Strip markdown fences
        m = re.search(r"```(?:json)?\s*(.+?)```", s, re.S | re.I)
        if m:
            s = m.group(1).strip()
        # Direct parse
        try:
            return json.loads(s)
        except Exception:
            pass
        # Find first { ... } block
        first = s.find("{")
        last = s.rfind("}")
        if first != -1 and last > first:
            try:
                return json.loads(s[first:last + 1])
            except Exception:
                pass
        return None

    _LOCAL_LOC_KWS = [
        "en la carpeta", "en mi carpeta", "carpeta de descarga", "carpeta descarga",
        "carpeta de descargas", "en descargas", "en la descarga", "en las descargas",
        "en mi pc", "en mi computador", "en mi computadora", "en mi equipo",
        "en el escritorio", "en mis documentos", "en documentos", "localmente",
        "en local", "búscalo local", "buscalo local", "revisa la carpeta", "mira en la carpeta",
    ]

    def _try_local_file_action(self, prompt, lower):
        """Si el usuario indica una UBICACIÓN local + buscar/analizar un archivo:
        ubica el archivo por semejanza, lo analiza y devuelve un mensaje con el resumen.
        Devuelve (handled, result)."""
        if not any(kw in lower for kw in self._LOCAL_LOC_KWS):
            return False, None
        # 1) Nombre/consulta del archivo
        fp = re.search(r'[\w.\-]{2,}\.\w{1,5}', prompt)
        query = fp.group(0) if fp else ""
        if not query:
            m = re.search(r'(?:archivo|fichero)\s+(?:llamado\s+|que\s+se\s+llama\s+)?(.+)$', lower)
            if m:
                query = m.group(1).strip()
        if not query:
            cleaned = lower
            for w in self._LOCAL_LOC_KWS:
                cleaned = cleaned.replace(w, " ")
            cleaned = re.sub(
                r"\b(busca|buscar|búscalo|buscalo|encuentra|encuéntrame|encuentrame|esta|este|esto|ese|esa|eso|el|la|los|las|en|mi|archivo|fichero)\b",
                " ", cleaned)
            query = re.sub(r"\s+", " ", cleaned).strip()
        # Quitar comandos que se cuelan al final ("... y analízalo", "y dime de qué trata")
        query = re.sub(
            r'\s*\b(y|e|,)?\s*(anal[ií]za\w*|anal[ií]zam\w*|dime|mu[eé]stra\w*|res[uú]m\w*|abre\w*|lee\w*|de\s+qu[eé]\s+(se\s+)?trata|qu[eé]\s+trata|por\s+favor)\b.*$',
            '', query, flags=re.IGNORECASE)
        query = query.strip(" .,:;¿?¡!y").strip()
        if (not query or query in ("esta", "este", "esto", "ese", "esa", "eso")):
            last = (getattr(self, "_last_file_query", "") or "").strip()
            query = last.split()[0] if last else ""
        if not query or len(query) < 2:
            return True, "¿Qué archivo busco? Dime el nombre (o parte de él)."
        self._last_file_query = query

        # 2) Carpeta objetivo
        home = os.path.expanduser("~")
        if "descarga" in lower:
            dirs = [os.path.join(home, "Downloads")]
        elif "escritorio" in lower or "desktop" in lower:
            dirs = [os.path.join(home, "Desktop")]
        elif "documento" in lower:
            dirs = [os.path.join(home, "Documents")]
        else:
            dirs = [os.path.join(home, d) for d in ("Downloads", "Desktop", "Documents")] + [home]

        # 3) Buscar (fuzzy) y analizar el más parecido
        scored = self._find_local_files(query, dirs)
        if not scored:
            return True, (f"No encontré ningún archivo parecido a '{query}' en esa carpeta. "
                          "Prueba con otra parte del nombre.")
        ambiguous = len(scored) > 1 and (scored[0][0] - scored[1][0]) < 0.4
        if ambiguous:
            listado = "\n".join(f"  • {os.path.basename(p)}" for _, p in scored[:6])
            return True, (f"Encontré varios archivos parecidos a '{query}':\n{listado}\n\n"
                          "¿Cuál analizo? (dime el nombre)")
        return True, self._analyze_local_file_sync(scored[0][1])

    def _try_handle_skill_action(self, prompt):
        lower = prompt.lower().strip()

        # Clean politeness wrappers so natural language triggers match perfectly
        cleaned_prompt = prompt
        try:
            import claudy_powers as cp
            cleaned_prompt = cp.clean_politeness_prefixes(prompt)
        except Exception:
            pass

        # ===== Marcador directo para analizar un archivo por ruta (lo usa el bot de Telegram) =====
        if prompt.strip().startswith("[CLAUDY_ANALYZE_FILE:") and prompt.strip().endswith("]"):
            try:
                path = prompt.strip()[len("[CLAUDY_ANALYZE_FILE:"):-1].strip().strip('"\'')
                if os.path.exists(path):
                    return True, self._analyze_local_file_sync(path)
                return True, f"No encontré el archivo en {path}."
            except Exception as e:
                return True, f"No pude analizar el archivo: {e}"

        # ===== Actualizar memoria (Claudy + agentes + Obsidian) bajo orden explícita =====
        try:
            mem_hit, mem_fact = self._extract_memory_fact(prompt, lower)
            if mem_hit:
                return True, self._remember_knowledge(mem_fact)
        except Exception:
            pass

        # ===== Buscar + analizar un archivo LOCAL (debe ir ANTES de crear-documento,
        # porque "analiza el archivo X de la carpeta Y" NO es crear un documento) =====
        try:
            loc_handled, loc_result = self._try_local_file_action(prompt, lower)
            if loc_handled:
                return True, loc_result
        except Exception:
            pass

        # ===== Crear documento .docx/.pdf con contenido generado por LLM =====
        try:
            handled, result = self._try_handle_create_document(cleaned_prompt)
            if handled:
                return True, result
        except Exception:
            pass

        # ===== CLAUDY POWERS (intent detection lenguaje natural) =====
        try:
            import claudy_powers as cp
            intent, arg = cp.detect_intent(prompt)
            if intent:
                # Confirm sensitive actions in the response, then execute async
                return True, cp.execute_intent(intent, arg)
        except Exception:
            pass

        # 1. Web search
        if lower.startswith("/buscar ") or lower.startswith("/search "):
            query = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._web_search_and_answer(query) if query else "¿Qué quieres que busque?"

        # 2. Screenshot
        if lower.startswith("/screenshot") or lower.startswith("/captura") or lower.startswith("/screen"):
            return True, self._take_screenshot()

        # 3. Read file
        if lower.startswith("/leer ") or lower.startswith("/read ") or lower.startswith("/abrir "):
            path = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._read_local_file(path) if path else "Qué archivo quieres que lea?"

        # 3b. Explicit Document Creators
        if lower.startswith("/docx ") or lower.startswith("/create-docx ") or lower.startswith("/crear-docx "):
            rest = prompt.split(None, 1)[1] if " " in prompt.strip() else ""
            try:
                import claudy_powers as cp
                path, content = cp.parse_path_content_arg(rest)
                return True, cp.create_docx(path, content) if path else "Uso: /docx <ruta> | <contenido>"
            except Exception as e:
                return True, f"Error creando docx: {e}"

        if lower.startswith("/xlsx ") or lower.startswith("/create-xlsx ") or lower.startswith("/crear-xlsx ") or lower.startswith("/excel "):
            rest = prompt.split(None, 1)[1] if " " in prompt.strip() else ""
            try:
                import claudy_powers as cp
                path, content = cp.parse_path_content_arg(rest)
                import json
                try:
                    data = json.loads(content)
                except Exception:
                    data = [line.split(",") for line in content.split("\n") if line.strip()]
                return True, cp.create_xlsx(path, data) if path else "Uso: /xlsx <ruta> | <contenido CSV/JSON>"
            except Exception as e:
                return True, f"Error creando xlsx: {e}"

        if lower.startswith("/pptx ") or lower.startswith("/create-pptx ") or lower.startswith("/crear-pptx ") or lower.startswith("/powerpoint "):
            rest = prompt.split(None, 1)[1] if " " in prompt.strip() else ""
            try:
                import claudy_powers as cp
                path, content = cp.parse_path_content_arg(rest)
                import json
                slides = None
                title = ""
                subtitle = ""
                theme = "business"
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        slides = parsed.get("slides")
                        title = parsed.get("title", "")
                        subtitle = parsed.get("subtitle", "")
                        theme = parsed.get("theme", "business")
                    elif isinstance(parsed, list):
                        slides = parsed
                except Exception:
                    slides = [{"title": s.strip(), "bullets": ["Detalle"]} for s in content.split("\n") if s.strip()]
                return True, cp.create_pptx(path, slides, title, subtitle, theme) if path else "Uso: /pptx <ruta> | <contenido JSON>"
            except Exception as e:
                return True, f"Error creando pptx: {e}"

        if lower.startswith("/pdf ") or lower.startswith("/create-pdf ") or lower.startswith("/crear-pdf "):
            rest = prompt.split(None, 1)[1] if " " in prompt.strip() else ""
            try:
                import claudy_powers as cp
                path, content = cp.parse_path_content_arg(rest)
                return True, cp.create_pdf(path, content) if path else "Uso: /pdf <ruta> | <contenido>"
            except Exception as e:
                return True, f"Error creando pdf: {e}"

        # 3c. Create/edit files
        if lower.startswith("/mkdir ") or lower.startswith("/crear-carpeta "):
            path = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            try:
                import claudy_powers as cp
                return True, cp.create_folder(path) if path else "Uso: /mkdir <ruta>"
            except Exception as e:
                return True, f"Error creando carpeta: {e}"
        if lower.startswith("/write ") or lower.startswith("/crear-archivo "):
            rest = prompt.split(None, 1)[1] if " " in prompt.strip() else ""
            try:
                import claudy_powers as cp
                path, content = cp.parse_path_content_arg(rest)
                return True, cp.write_file(path, content) if path else "Uso: /write <ruta> | <contenido>"
            except Exception as e:
                return True, f"Error escribiendo archivo: {e}"
        if lower.startswith("/append ") or lower.startswith("/agregar-archivo "):
            rest = prompt.split(None, 1)[1] if " " in prompt.strip() else ""
            try:
                import claudy_powers as cp
                path, content = cp.parse_path_content_arg(rest)
                return True, cp.append_file(path, content) if path else "Uso: /append <ruta> | <contenido>"
            except Exception as e:
                return True, f"Error agregando contenido: {e}"
        if lower.startswith("/replace ") or lower.startswith("/edit-replace "):
            rest = prompt.split(None, 1)[1] if " " in prompt.strip() else ""
            parts = [x.strip() for x in rest.split(" | ", 2)]
            if len(parts) < 3:
                return True, "Uso: /replace <ruta> | <buscar> | <reemplazo>"
            try:
                import claudy_powers as cp
                return True, cp.replace_in_file(parts[0], parts[1], parts[2])
            except Exception as e:
                return True, f"Error editando archivo: {e}"

        # 4. Execute command
        if lower.startswith("/cmd ") or lower.startswith("/command ") or lower.startswith("/ejecutar "):
            cmd = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._execute_command(cmd) if cmd else "Qué comando quieres ejecutar?"

        # 5. Reminder
        if lower.startswith("/recordar ") or lower.startswith("/reminder ") or lower.startswith("/alarma "):
            text = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._set_reminder(text) if text else "Formato: /recordar 10 minutos comprar leche"

        # 6. News
        if lower.startswith("/noticias") or lower.startswith("/news") or lower.startswith("/noti"):
            return True, self._get_news()

        # 7. Translation
        if lower.startswith("/traducir ") or lower.startswith("/translate ") or lower.startswith("/trad"):
            text = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._translate_text(text) if text else "Formato: /traducir hello world a español"

        # 8. Calculator
        if lower.startswith("/calc ") or lower.startswith("/calcular ") or lower.startswith("/math "):
            expr = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._calculate(expr) if expr else "Qué quieres calcular? Ej: /calc 2+2*3"

        # 9. Music control
        if lower.startswith("/musica ") or lower.startswith("/music ") or lower.startswith("/media "):
            action = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._control_music(action) if action else "Acciones: play, pause, siguiente, anterior"

        # 10. Theme toggle
        if lower.startswith("/tema") or lower.startswith("/theme") or lower.startswith("/modo"):
            return True, self._toggle_theme()

        # 10.1 Backup commands
        if lower.startswith("/backup") or lower.startswith("/respaldo"):
            parts = prompt.strip().split()
            sub = parts[1].lower() if len(parts) > 1 else ""
            if sub in ("on", "auto", "activar", "enable"):
                return True, self._set_auto_backup(True)
            if sub in ("off", "desactivar", "disable"):
                return True, self._set_auto_backup(False)
            if sub in ("status", "estado"):
                return True, self._backup_status()
            if sub in ("restore", "restaurar"):
                return True, "Para restaurar usa: powershell -ExecutionPolicy Bypass -File scripts\\restore-claudy-full.ps1"
            # Default: run backup now
            return True, self._run_backup_now()

        # 10.5 Disk space
        if lower.startswith("/disco") or lower.startswith("/espacio") or lower.startswith("/disk") or lower.startswith("/space") or lower.startswith("/almacenamiento"):
            return True, self._get_disk_space()

        # 11. File search
        if lower.startswith("/buscar_archivo") or lower.startswith("/find_file") or lower.startswith("/buscar archivo"):
            query = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._search_files(query) if query else "Qué archivo buscas? Ej: /buscar_archivo reporte.pdf"

        # 12. Install app
        if lower.startswith("/instalar") or lower.startswith("/install"):
            app = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._install_app(app) if app else "Qué aplicación quieres instalar? Ej: /instalar winrar"

        # 13. Download file
        if lower.startswith("/descargar") or lower.startswith("/download") or lower.startswith("/bajar"):
            url = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._download_file(url) if url else "Qué URL quieres descargar? Ej: /descargar https://ejemplo.com/archivo.zip"

        # 14. Execute file
        if lower.startswith("/ejecutar") or lower.startswith("/run") or lower.startswith("/abrir archivo"):
            path = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._execute_file(path) if path else "Que archivo quieres ejecutar? Ej: /ejecutar C:\\Users\\felip\\Downloads\\app.exe"

        # 15. Checkpoint / Rollback
        if lower.startswith("/checkpoint") or lower.startswith("/guardar_punto"):
            label = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else "manual"
            return True, self._create_checkpoint(label)
        if lower.startswith("/rollback") or lower.startswith("/deshacer") or lower.startswith("/volver"):
            label = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else None
            return True, self._rollback_checkpoint(label)
        if lower.startswith("/checkpoints") or lower.startswith("/puntos"):
            return True, self._list_checkpoints()

        # 16. Memory search
        if lower.startswith("/recordar ") or lower.startswith("/buscar_memoria "):
            query = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._search_memory_cmd(query) if query else "Que quieres buscar en la memoria? Ej: /recordar python"

        # ---- Natural language routing (no / prefix) ----
        # 17. Subagentes
        if lower.startswith("/delegar ") or lower.startswith("/delegate "):
            task = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._spawn_subagent(task) if task else "Que tarea delego? Ej: /delegar analizar el codigo de pet.py"
        if lower.startswith("/resultado") or lower.startswith("/sub_result"):
            r = self._check_subagent_result()
            return True, r if r else "No hay resultados de subagente pendientes."

        # 18. Kanban
        if lower.startswith("/kanban add ") or lower.startswith("/kanban crear "):
            title = prompt.split(None, 2)[2].strip() if len(prompt.split(None)) > 2 else ""
            return True, self._kanban_add(title) if title else "Uso: /kanban add <titulo>"
        if lower.startswith("/kanban move ") or lower.startswith("/kanban mover "):
            parts = prompt.split(None)
            if len(parts) >= 4:
                try:
                    tid = int(parts[2])
                    status = parts[3]
                    return True, self._kanban_move(tid, status)
                except ValueError:
                    pass
            return True, "Uso: /kanban move <id> <backlog|todo|in_progress|done>"
        if lower.startswith("/kanban delete ") or lower.startswith("/kanban borrar "):
            parts = prompt.split(None)
            try:
                tid = int(parts[2])
                return True, self._kanban_delete(tid)
            except (ValueError, IndexError):
                return True, "Uso: /kanban delete <id>"
        if lower.startswith("/kanban") or lower.startswith("/board"):
            return True, self._kanban_list()

        # 19. Webhooks
        if lower.startswith("/webhook add ") or lower.startswith("/webhook crear "):
            parts = prompt.split(None, 2)
            if len(parts) >= 3:
                name = parts[2].split()[0] if len(parts[2].split()) > 0 else ""
                url = " ".join(parts[2].split()[1:]) if len(parts[2].split()) > 1 else ""
                return True, self._webhook_register(name, url) if name and url else "Uso: /webhook add <nombre> <url>"
            return True, "Uso: /webhook add <nombre> <url>"
        if lower.startswith("/webhook trigger") or lower.startswith("/webhook disparar"):
            return True, self._webhook_trigger_all()
        if lower.startswith("/webhook") or lower.startswith("/webhooks"):
            return True, self._webhook_list()

        # 20. Git Worktrees
        if lower.startswith("/worktree add ") or lower.startswith("/worktree crear "):
            parts = prompt.split(None)
            name = parts[2] if len(parts) > 2 else ""
            branch = parts[3] if len(parts) > 3 else "main"
            return True, self._worktree_create(name, branch) if name else "Uso: /worktree add <nombre> [branch]"
        if lower.startswith("/worktree remove ") or lower.startswith("/worktree borrar "):
            parts = prompt.split(None)
            name = parts[2] if len(parts) > 2 else ""
            return True, self._worktree_remove(name) if name else "Uso: /worktree remove <nombre>"
        if lower.startswith("/worktree") or lower.startswith("/worktrees"):
            return True, self._worktree_list()

        # ---- Natural language routing (no / prefix) ----

        # Weather/Clima: auto-search for weather queries
        weather_kws = ["clima ", "clima de ", "el clima en ", "tiempo en ", "pronóstico ",
                       "pronostico ", "weather ", "temperatura en ", "lluvia en ",
                       "va a llover", "hace frío", "hace calor", "clima para"]
        if any(kw in lower for kw in weather_kws):
            # Extract city name from the prompt
            city = ""
            city_kws = ["clima de ", "clima en ", "el clima en ", "tiempo en ", "pronóstico de ",
                        "pronostico de ", "pronóstico en ", "pronostico en ", "temperatura en ",
                        "lluvia en ", "clima para ", "weather in ", "weather for "]
            for ck in city_kws:
                if ck in lower:
                    city = prompt[lower.index(ck) + len(ck):].strip().strip(".!?")
                    break
            if not city:
                # Try to extract any location-like word after "clima"
                after = prompt[lower.index("clima") + 5:].strip() if "clima" in lower else prompt
                city = after.strip().strip(".!?")

            # Clean trailing time/duration phrases from city name
            trailing_phrases = [
                "para toda la semana", "toda la semana", "para la semana",
                "de esta semana", "esta semana", "la semana",
                "para hoy", "de hoy", "hoy",
                "para mañana", "de mañana", "mañana",
                "para los proximos dias", "para los próximos días",
                "de los proximos dias", "de los próximos días",
                "por favor", "porfavor", "porfa", "please",
                "para el fin de semana", "el fin de semana",
            ]
            city_lower = city.lower()
            for phrase in trailing_phrases:
                if phrase in city_lower:
                    idx = city_lower.index(phrase)
                    city = city[:idx].strip()
                    city_lower = city.lower()

            # Also remove leading filler words
            for art in ["dame ", "dime ", "cual es ", "cuál es ", "como esta ", "cómo está ",
                         "el ", "la ", "los ", "las ", "del ", "de ", "en "]:
                if city.lower().startswith(art):
                    city = city[len(art):]

            city = city.strip().strip(".!?,")

            # Check if city is a reference to current location
            local_kws = ["mi ubicacion", "mi ubicación", "mi ciudad", "aqui", "aquí", "aca", "acá", "donde estoy", "donde vivo", "mi zona"]
            if city.lower() in local_kws:
                city = ""

            return True, self._get_weather(city)

        # "busca en internet" / "busca en la web" — pasan al LLM para síntesis natural
        web_search_kws = ["busca en internet", "buscar en internet", "busca en la web",
                          "buscar en la web", "busca en google", "googleame", "googlea"]
        if any(kw in lower for kw in web_search_kws):
            query = prompt
            for kw in web_search_kws:
                if kw in lower:
                    query = prompt[lower.index(kw) + len(kw):].strip()
                    break
            return True, self._web_search_and_answer(query) if query else "¿Qué quieres que busque?"

        # Play game: "quiero jugar megaman de nes", "jugar super mario snes"
        play_kws = ["quiero jugar ", "jugar a ", "jugar ", "pon el juego ", "abre el juego ", "corre el juego "]
        if any(kw in lower for kw in play_kws):
            full_what = ""
            for kw in play_kws:
                if kw in lower:
                    full_what = prompt[lower.index(kw) + len(kw):].strip().strip('"').strip("'").strip(".!?")
                    break
            if full_what:
                # Try to extract console from "de nes", "en snes", "para gba"
                for c_kw in [" de ", " en ", " para ", " on ", " for "]:
                    if c_kw in full_what.lower():
                        parts = full_what.lower().split(c_kw)
                        game = parts[0].strip()
                        console = parts[1].strip()
                        # Handle trailing phrases like "para toda la semana" or similar junk
                        return True, self._play_game(game, console)
                return True, self._play_game(full_what)

        # Download: detect URLs + download intent
        url_pattern = re.compile(r'https?://[^\s<>"]+')
        urls_found = url_pattern.findall(prompt)
        download_keywords = ["descarga", "descargar", "bajar", "download", "trae este archivo", "consigue este archivo"]
        if urls_found and any(kw in lower for kw in download_keywords):
            return True, self._download_file(urls_found[0])

        # Download by name (no URL): "descarga megaman rom", "baja el emulador de snes"
        download_name_kws = ["descarga ", "descargar ", "bajar ", "bajame ", "bájame ",
                             "download ", "descárgame ", "descargame "]
        if any(kw in lower for kw in download_name_kws) and not urls_found:
            what = ""
            for kw in download_name_kws:
                if kw in lower:
                    what = prompt[lower.index(kw) + len(kw):].strip().strip('"').strip("'").strip(".!?")
                    for art in ["el ", "la ", "los ", "las ", "un ", "una ", "de ", "del "]:
                        if what.lower().startswith(art):
                            what = what[len(art):]
                            break
                    break
            if what:
                self._last_file_query = what
                return True, self._download_by_name(what)

        # File search: detect explicit keywords + file names with extensions + search intent
        # NOTA: NO incluir "donde está" / "donde esta" sin "el archivo" — son demasiado amplios
        # y rompen preguntas como "donde están ubicados ellos?"
        file_search_kws = ["busca el archivo", "buscar archivo", "busca archivo", "encuentra el archivo",
                           "encuentra archivo", "dónde está el archivo", "donde esta el archivo",
                           "dónde está el fichero", "donde esta el fichero",
                           "busca en mi pc", "buscar en mi pc",
                           "buscar en mi computadora", "find file", "buscando archivo",
                           "buscando el archivo", "buscando este archivo", "busca este archivo"]
        has_search_intent = any(kw in lower for kw in file_search_kws)

        # Also detect if prompt contains a file name with extension + search words
        file_pattern = re.search(r'\b\S+\.(dll|exe|pdf|txt|doc|docx|xls|xlsx|ppt|pptx|zip|rar|7z|jpg|jpeg|png|gif|mp3|mp4|avi|mov|csv|json|xml|py|js|ts|html|css|java|cpp|c|h|go|rs|php|rb|swift|kt|sql|md|log|ini|cfg|bat|ps1|msi|iso|torrent)\b', lower)
        search_words = ["busca", "buscar", "buscando", "encuentra", "donde", "dónde", "está", "esta", "quiero", "necesito"]
        has_file_and_intent = file_pattern and any(w in lower for w in search_words)

        if has_search_intent or has_file_and_intent:
            query = ""
            for kw in file_search_kws:
                if kw in lower:
                    query = prompt[lower.index(kw) + len(kw):].strip()
                    break
            if not query and file_pattern:
                query = file_pattern.group(0)
            if query:
                self._last_file_query = query
            return True, self._search_files(query) if query else "Qué archivo buscas?"

        # Execute: "abre", "ejecuta", "corre" + file path
        exec_kws = ["abre el archivo", "abrir archivo", "ejecuta", "ejecutar", "corre el archivo",
                     "run file", "abre este archivo"]
        if any(kw in lower for kw in exec_kws):
            for kw in exec_kws:
                if kw in lower:
                    path = prompt[lower.index(kw) + len(kw):].strip().strip('"').strip("'")
                    break
            # If path looks like a file path (has extension or starts with drive letter)
            if path and (os.path.splitext(path)[1] or path[1:3] == ":\\"):
                return True, self._execute_file(path)

        # Install app: "instala winrar", "quiero instalar vlc", etc.
        install_kws = ["instala ", "instalar ", "baja e instala ", "quiero instalar ",
                       "necesito instalar ", "me puedes instalar ", "podrias instalar ",
                       "podrías instalar ", "consígueme e instala ", "bájame e instala ",
                       "puedes instalar "]
        if any(kw in lower for kw in install_kws):
            app_name = ""
            for kw in install_kws:
                if kw in lower:
                    app_name = prompt[lower.index(kw) + len(kw):].strip().strip('"').strip("'").strip(".!?")
                    # Strip leading articles/prepositions
                    for art in ["el ", "la ", "los ", "las ", "un ", "una ", "de ", "del "]:
                        if app_name.lower().startswith(art):
                            app_name = app_name[len(art):]
                            break
                    break
            if app_name:
                return True, self._install_app(app_name)

        # Existing skill handlers
        kw_find = ["busca skill", "buscar skill", "busca skills", "buscar skills",
                    "busca una skill", "buscar una skill", "find skill", "instalar skill",
                    "skill para", "skill de"]
        if any(kw in lower for kw in kw_find):
            query = prompt
            for kw in ["skill para", "skill de", "skill sobre", "buscar skills", "busca skills",
                        "buscar skill", "busca skill", "buscar una skill", "busca una skill", "find skill"]:
                if kw in lower:
                    query = prompt[lower.index(kw) + len(kw):].strip()
                    break
            return True, self._execute_find_skills(query or "general")
        kw_pdf = ["crea un pdf", "crear un pdf", "crea pdf", "crear pdf",
                   "genera pdf", "generar pdf", "haz un pdf", "hacer un pdf"]
        if any(kw in lower for kw in kw_pdf):
            content = prompt
            for kw in kw_pdf:
                if kw in lower:
                    content = prompt[lower.index(kw) + len(kw):].strip()
                    break
            title = content.split("\n")[0].strip()[:80] or "Documento Claudy"
            return True, self._create_pdf_simple(title, content)
        kw_analyze = ["analiza", "leer", "extraer texto", "abrir", "lee el"]
        if any(kw in lower for kw in kw_analyze) and ".pdf" in lower:
            paths = re.findall(r'[A-Z]:[\\\/][^\s"\'<>]+\.pdf', prompt)
            if not paths:
                paths = re.findall(r'["\']?([^\s"\'<>]+\.pdf)["\']?', prompt, re.IGNORECASE)
            if paths:
                return True, self._analyze_pdf_text(paths[0])
            return True, "No encuentro la ruta del PDF. Dame la ruta completa."
        kw_obsidian = ["crea una nota", "crear una nota", "crea nota", "crear nota",
                        "guarda en obsidian", "guardar en obsidian", "nota en obsidian",
                        "nueva nota", "crear nota en"]
        if any(kw in lower for kw in kw_obsidian):
            content = prompt
            for kw in kw_obsidian:
                if kw in lower:
                    content = prompt[lower.index(kw) + len(kw):].strip()
                    break
            title = content.split("\n")[0].strip()[:80] or f"Nota_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            return True, self._create_obsidian_note(title, content)
        kw_obs_search = ["busca en obsidian", "buscar en obsidian", "buscar nota", "busca nota",
                          "mis notas", "notas de"]
        if any(kw in lower for kw in kw_obs_search):
            query = prompt
            for kw in kw_obs_search:
                if kw in lower:
                    query = prompt[lower.index(kw) + len(kw):].strip()
                    break
            return True, self._search_obsidian_notes(query or "")

        # ==============================================================
        # NEW SYSTEM COMMANDS
        # ==============================================================

        # PROCESOS: "dame los procesos", "que esta corriendo", "/procesos"
        procesos_kws = ["/procesos", "procesos", "que esta corriendo", "qué está corriendo",
                        "tareas activas", "procesos activos", "listame los procesos",
                        "aplicaciones abiertas", "programas abiertos", "que programas",
                        "dame los procesos", "muestrame los procesos", "ver procesos"]
        if any(kw in lower for kw in procesos_kws):
            return True, self._list_processes()

        # MATAR proceso: "mata el proceso 1234", "/matar 1234", "/kill 1234", "termina el proceso 1234"
        matar_match = re.search(r'(?:/matar\s+|/kill\s+|mata\s+(?:el\s+)?proceso\s+|termina\s+(?:el\s+)?proceso\s+|cerrar\s+proceso\s+|matar\s+proceso\s+)(\d+)', lower)
        if matar_match:
            return True, self._kill_process(int(matar_match.group(1)))

        # EXPLORAR: "explora descargas", "/explorar C:\Users", "que hay en", "listame archivos"
        explorar_kws = ["/explorar ", "/explore ", "explora ", "explorar ", "explorando ",
                        "que hay en ", "qué hay en ", "listame archivos en ", "lista archivos en ",
                        "dime que hay en ", "muestra archivos en ", "ver archivos en "]
        if any(kw in lower for kw in explorar_kws):
            ruta = ""
            for kw in explorar_kws:
                if kw in lower:
                    ruta = prompt[lower.index(kw) + len(kw):].strip().strip('"').strip("'")
                    break
            if not ruta or ruta.lower() in ["escritorio", "desktop"]:
                ruta = os.path.expanduser("~/Desktop")
            elif ruta.lower() in ["descargas", "downloads"]:
                ruta = os.path.expanduser("~/Downloads")
            elif ruta.lower() in ["documentos", "documents", "documentos"]:
                ruta = os.path.expanduser("~/Documents")
            return True, self._explore_dir(ruta)

        # APPS instaladas: "dame las apps instaladas", "/apps", "programas instalados"
        apps_kws = ["/apps", "aplicaciones instaladas", "apps instaladas", "programas instalados",
                     "que aplicaciones tengo", "que programas tengo", "dame las apps",
                     "dame los programas", "lista de programas", "lista de aplicaciones",
                     "aplicaciones que tengo", "programas que tengo", "software instalado"]
        if any(kw in lower for kw in apps_kws):
            return True, self._list_installed_apps()

        # WIFI: "ver wifi", "/wifi", "red wifi", "contraseña wifi"
        wifi_kws = ["/wifi", "ver wifi", "red wifi", "mi wifi", "conexion wifi", "conexión wifi",
                     "red inalambrica", "red inalámbrica", "redes disponibles",
                     "dame el wifi", "estado del wifi", "info wifi", "informacion wifi"]
        if any(kw in lower for kw in wifi_kws):
            return True, self._wifi_info()

        # BLUETOOTH: "ver bluetooth", "/bluetooth", "dispositivos bluetooth"
        bt_kws = ["/bluetooth", "ver bluetooth", "dispositivos bluetooth",
                   "dispositivos conectados bluetooth", "bluetooth dispositivos",
                   "dame el bluetooth", "que bluetooth tengo"]
        if any(kw in lower for kw in bt_kws):
            return True, self._bluetooth_info()

        # APAGAR/REINICIAR: "apaga en 10 minutos", "/apagar 10", "reinicia en 5"
        apagar_match = re.search(r'(?:apaga\s+en\s+|apagar\s+en\s+|/apagar\s+|reinicia\s+en\s+|/reiniciar\s+|reiniciar\s+en\s+|/restart\s+)(\d+)', lower)
        if apagar_match:
            minutos = int(apagar_match.group(1))
            is_reboot = lower.startswith("reinicia") or lower.startswith("/reiniciar") or lower.startswith("/restart")
            return True, self._shutdown_timer(minutos, reboot=is_reboot)

        # CANCELAR APAGADO: "cancela el apagado", "/noapagar"
        cancel_kws = ["cancela el apagado", "cancelar apagado", "cancela apagado",
                       "no apagues", "no apagar", "/noapagar", "detén el apagado", "deten el apagado"]
        if any(kw in lower for kw in cancel_kws):
            return True, self._cancel_shutdown()

        # NOTAS: "toma nota", "/notas", "apunta", "guarda esto", "nota rapida"
        notas_kws = ["/notas", "toma nota", "tomar nota", "apunta", "nota rápida", "nota rapida",
                     "guarda esto", "guardar esto", "anota esto", "anotar esto",
                     "quiero tomar una nota", "dame mis notas", "muestrame las notas",
                     "notas guardadas", "lee mis notas"]
        if any(kw in lower for kw in notas_kws):
            # Check if it's a read request
            read_notas = ["dame mis notas", "muestrame las notas", "notas guardadas",
                          "lee mis notas", "ver notas", "que notas tengo"]
            if any(kw in lower for kw in read_notas):
                return True, self._read_notes()
            # Extract note content
            for kw in notas_kws:
                if kw in lower and kw not in read_notas:
                    content = prompt[lower.index(kw) + len(kw):].strip()
                    if content:
                        return True, self._save_note(content)
                    break
            return True, self._save_note("")

        # CLIPBOARD: "copia al portapapeles", "/clipboard", "pegar", "copiar"
        clipboard_kws = ["/clipboard", "/portapapeles", "/copiar", "/pegar",
                         "copia al portapapeles", "copiar al portapapeles", "pegar del portapapeles",
                         "que hay en el portapapeles", "portapapeles", "lee el portapapeles",
                         "ver portapapeles", "muestra el portapapeles"]
        if any(kw in lower for kw in clipboard_kws):
            # Check if it's a write action (copiar algo específico)
            if any(kw in lower for kw in ["copia ", "copiar "]):
                text = prompt
                for kw in ["copia al portapapeles ", "copiar al portapapeles ", "copia ", "copiar "]:
                    if kw in lower:
                        text = prompt[lower.index(kw) + len(kw):].strip()
                        break
                return True, self._clipboard_copy(text) if text else self._clipboard_read()
            return True, self._clipboard_read()

        # EN VIVO (always on top): "ponte al frente", "/envivo", "modo siempre visible"
        envivo_kws = ["/envivo", "siempre visible", "ponte al frente", "ponte siempre visible",
                       "modo visible", "quedate al frente", "quédate al frente", "mantente visible",
                       "siempre al frente", "al frente"]
        if any(kw in lower for kw in envivo_kws):
            # Check if it's a disable request
            if any(kw in lower for kw in ["quita", "quitar", "desactiva", "no quiero", "sal del modo", "ya"]):
                return True, self._toggle_always_on_top(False)
            return True, self._toggle_always_on_top(True)

        # COMANDOS/AYUDA: "que comandos tienes", "/atajos", "/ayuda", "/comandos"
        help_kws = ["/atajos", "/ayuda", "/comandos", "/help", "/commands",
                     "que comandos tienes", "qué comandos tienes", "que puedes hacer",
                     "qué puedes hacer", "lista de comandos", "dame los comandos",
                     "comandos disponibles", "funciones", "que sabes hacer"]
        if any(kw in lower for kw in help_kws):
            return True, self._show_help()

        # VOZ: "usar voz", "/voz", "input por voz", "dictado", "escucha"
        voz_kws = ["/voz", "usar voz", "input por voz", "dictado", "hablar",
                    "reconocimiento de voz", "voz a texto", "escucha", "/escucha"]
        if any(kw in lower for kw in voz_kws):
            if lower.strip() in ("/voz stop", "deja de escuchar", "silencio", "dejar de escuchar", "para de escuchar"):
                return True, self._stop_voice_listen()
            return True, self._start_voice_listen()

        # TELEGRAM TOKEN: "/telegram-token <TOKEN>" — guarda el token y arranca el bot
        if lower.startswith("/telegram-token ") or lower.startswith("/telegram_token "):
            token = prompt.split(None, 1)[1].strip().strip('"\'')
            return True, self._set_telegram_token(token) if token else (
                "Uso: /telegram-token <TOKEN>\nPide el token a @BotFather en Telegram.")

        # TELEGRAM STATUS: "/telegram-status" — ver estado (token / usuarios / bot vivo)
        if lower.strip() in ("/telegram-status", "/telegram_status", "telegram status", "estado telegram"):
            return True, self._telegram_status()

        # VINCULAR Telegram: "/vincular <uid>"
        if lower.startswith("/vincular ") or lower.startswith("vincular "):
            uid = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._vincular_telegram_user(uid) if uid else "Uso: /vincular <ID_de_Telegram>"

        # SKILLS: listar / recargar
        if lower.strip() in ("/skills", "/skill list", "skills cargadas", "que skills tienes"):
            return True, self._list_dynamic_skills()
        if lower.startswith("/skill crear ") or lower.startswith("crear skill "):
            parts = prompt.split(None, 2)
            name = parts[2].strip() if len(parts) > 2 else ""
            return True, self._create_skill_stub(name) if name else "Uso: /skill crear <nombre>"

        # SKILLS: aprender de la conversación actual (estilo Hermes Curator)
        if lower.startswith("/aprender ") or lower.startswith("/learn "):
            parts = prompt.split(None, 1)
            name = parts[1].strip() if len(parts) > 1 else ""
            return True, self._learn_skill_from_conversation(name) if name else "Uso: /aprender <nombre-de-la-skill>"

        # SKILLS: estadísticas de uso / aprendizaje
        if lower.strip() in ("/skill stats", "/skills stats", "/skill estado", "estado de skills"):
            return True, self._skill_stats()

        # SKILLS: refinar/mejorar una skill existente (la otra mitad del bucle Hermes)
        if (lower.startswith("/skill mejorar ") or lower.startswith("/skill refinar ")
                or lower.startswith("/refinar ") or lower.startswith("/mejorar-skill ")):
            parts = prompt.split(None, 2) if lower.startswith("/skill") else prompt.split(None, 1)
            name = (parts[2] if lower.startswith("/skill") and len(parts) > 2
                    else parts[1] if len(parts) > 1 else "").strip()
            return True, self._refine_skill(name) if name else "Uso: /skill mejorar <nombre>"

        refine_match = re.search(
            r'(?:mejora|refina|actualiza)\s+(?:la\s+)?skill\s+([^\.\?!,]+)', lower, re.IGNORECASE)
        if refine_match:
            return True, self._refine_skill(refine_match.group(1).strip())

        # Auto-detección: "guarda esto como skill X", "aprende esto como X", "memoriza esto como X"
        learn_match = re.search(
            r'(?:guarda esto como|aprende esto como|aprende a|memoriza esto como|crea (?:una )?skill (?:de|para))\s+([^\.\?!,]+)',
            lower, re.IGNORECASE
        )
        if learn_match:
            name = learn_match.group(1).strip()
            return True, self._learn_skill_from_conversation(name)

        # SKILLS: eliminar
        if lower.startswith("/skill eliminar ") or lower.startswith("/skill delete ") or lower.startswith("eliminar skill "):
            parts = prompt.split(None, 2)
            name = parts[2].strip() if len(parts) > 2 else ""
            return True, self._delete_skill(name) if name else "Uso: /skill eliminar <nombre>"

        # CRON: programar / listar / eliminar tareas
        if lower.strip() in ("/cron list", "/cron listar", "cron list", "tareas programadas", "que tareas tienes"):
            return True, self._list_cron_jobs()

        # Gestión avanzada: editar, pausar/activar y crear tareas semanales.
        # Va antes del parser NL para que "los martes a las 9 ..." no se trate como diario.
        cron_mgmt = self._manage_cron_command(prompt)
        if cron_mgmt is not None:
            return True, cron_mgmt

        cron_expr = self._generate_cron_expression(prompt)
        if cron_expr:
            return True, cron_expr

        # CRON natural language: "recuerdame cada X" / "avisame a las HH" / etc.
        nl = self._parse_cron_nl(prompt)
        if nl:
            kind, params, msg = nl
            if kind == "interval":
                return True, self._add_cron_interval(params, msg)
            if kind == "daily":
                h, m = params
                return True, self._add_cron_daily(h, m, msg)

        cron_match = re.match(r'(?:/cron\s+cada\s+(\d+)\s+(min|minutos|minuto|h|horas|hora)\s+)(.+)', lower)
        if cron_match:
            n = int(cron_match.group(1))
            unit = cron_match.group(2)
            msg = cron_match.group(3).strip()
            interval_min = n if unit.startswith("min") else n * 60
            return True, self._add_cron_interval(interval_min, msg)

        cron_time_match = re.match(r'(?:/cron\s+a\s+las?\s+(\d{1,2}):?(\d{2})?\s+)(.+)', lower)
        if cron_time_match:
            h = int(cron_time_match.group(1))
            m = int(cron_time_match.group(2) or 0)
            msg = cron_time_match.group(3).strip()
            return True, self._add_cron_daily(h, m, msg)

        cron_del_match = re.match(r'(?:/cron\s+delete\s+(\d+)|/cron\s+eliminar\s+(\d+)|eliminar\s+tarea\s+(\d+))', lower)
        if cron_del_match:
            idx = int(cron_del_match.group(1) or cron_del_match.group(2) or cron_del_match.group(3)) - 1
            return True, self._delete_cron_job(idx)

        # AGENDA: crear reunión en Google Calendar
        if lower.startswith("/agendar") or re.search(r'\b(agenda|agendar|agéndame|agendame)\b.*\b(reuni[oó]n|meeting|cita|llamada|evento)\b', lower):
            return True, self._handle_agendar(prompt)

        return False, ""

    _MESES = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
        "noviembre": 11, "diciembre": 12,
    }

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

    def _execute_find_skills(self, query):
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                ["npx", "skills", "find", query],
                capture_output=True, text=True, timeout=30, creationflags=flags,
            )
            out = result.stdout.strip()
            if result.returncode == 0 and out:
                return f"Skills para '{query}':\n\n{out[:1500]}"
            err = result.stderr.strip()
            return f"No encontré skills para '{query}'. {err}" if err else f"No encontré skills para '{query}'."
        except subprocess.TimeoutExpired:
            return "Búsqueda de skills tardó demasiado."
        except FileNotFoundError:
            return "No encuentro 'npx skills'. Instala el CLI."
        except Exception as e:
            return f"Error buscando skills: {e}"

    def _create_pdf_simple(self, title, content):
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        except ImportError:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab", "--quiet"])
                from reportlab.lib.pagesizes import letter
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            except Exception:
                return "Necesito 'reportlab' para crear PDFs: pip install reportlab"
        out_dir = os.path.join(os.path.expanduser("~"), ".claudy", "pdfs")
        os.makedirs(out_dir, exist_ok=True)
        fname = f"claudy_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        fpath = os.path.join(out_dir, fname)
        try:
            doc = SimpleDocTemplate(fpath, pagesize=letter)
            styles = getSampleStyleSheet()
            story = [Paragraph(title, styles['Title']), Spacer(1, 12)]
            for line in content.split("\n"):
                if line.strip():
                    story.append(Paragraph(line.strip(), styles['Normal']))
                else:
                    story.append(Spacer(1, 6))
            doc.build(story)
            return f"PDF creado: {fpath}"
        except Exception as e:
            return f"Error creando PDF: {e}"

    def _analyze_pdf_text(self, path):
        if not os.path.exists(path):
            return f"No encuentro: {path}"
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf", "--quiet"])
                from pypdf import PdfReader
            except Exception:
                return "Necesito 'pypdf' para leer PDFs: pip install pypdf"
        try:
            reader = PdfReader(path)
            n_pages = len(reader.pages)
            text = ""
            for page in reader.pages[:5]:
                pt = page.extract_text()
                if pt:
                    text += pt + "\n"
            summary = text[:2000] if text else "No se pudo extraer texto."
            return f"PDF: {os.path.basename(path)}\nPáginas: {n_pages}\n\nContenido:\n{summary}"
        except Exception as e:
            return f"Error leyendo PDF: {e}"

    def _analyze_folder_deep(self, folder_path, status_widget=None):
        """Deep-analyze a folder: structure + key files + LLM interpretation, save to Obsidian.
        Runs in current thread — caller must wrap in threading.Thread."""
        if not folder_path or not os.path.isdir(folder_path):
            return f"No es un directorio valido: {folder_path}"

        def _status(msg):
            if status_widget is None:
                return
            try:
                self.after(0, lambda: status_widget.configure(text=msg, fg=THEME["accent"]))
            except Exception:
                pass

        _status("Escaneando estructura...")
        try:
            import claudy_powers as cp
            structure = cp.folder_tree(folder_path, max_depth=5, max_items=400)
            stats = cp.folder_info(folder_path)
        except Exception as e:
            return f"Error escaneando: {e}"

        _status("Leyendo archivos clave...")
        priority_files = (
            "README.md", "README", "readme.md", "package.json", "pyproject.toml",
            "requirements.txt", "Cargo.toml", "go.mod", "tsconfig.json", "Makefile",
            "docker-compose.yml", "Dockerfile", ".env.example", "setup.py", "setup.cfg",
        )
        key_contents = []
        try:
            for r, dirs, files in os.walk(folder_path):
                dirs[:] = [d for d in dirs if d not in cp.IGNORE_DIRS and not d.startswith(".")]
                for f in files:
                    if f in priority_files and len(key_contents) < 8:
                        full = os.path.join(r, f)
                        rel = os.path.relpath(full, folder_path)
                        body = cp.read_file(full, max_bytes=2500)
                        key_contents.append(f"--- {rel} ---\n{body}")
                if len(key_contents) >= 8:
                    break
        except Exception as e:
            key_contents.append(f"(error leyendo archivos clave: {e})")

        scan_block = (
            "=== ESTRUCTURA ===\n" + structure[:4000] +
            "\n\n=== STATS ===\n" + stats[:1500] +
            "\n\n=== ARCHIVOS CLAVE ===\n" + "\n\n".join(key_contents)[:8000]
        )

        _status("Consultando LLM...")
        config = self.load_claudy_config()
        opencode = config["opencode"]
        base_url = opencode.get("baseUrl", "").rstrip("/")
        model = self._current_model or opencode.get("defaultModel", "deepseek-chat")
        is_local = any(h in base_url for h in ("127.0.0.1", "localhost", "0.0.0.0"))

        analysis_prompt = (
            "Analiza esta carpeta y entrega un reporte profundo y estructurado en Markdown:\n"
            "1. **Resumen ejecutivo**: que es este proyecto/carpeta en 2-3 lineas.\n"
            "2. **Tipo de proyecto** y **tecnologias detectadas** (lenguajes, frameworks, herramientas).\n"
            "3. **Arquitectura/estructura**: como esta organizada la carpeta.\n"
            "4. **Archivos clave** y su rol.\n"
            "5. **Dependencias importantes** (si las hay).\n"
            "6. **Estado del proyecto**: madurez, actividad reciente (por tamano, recientes).\n"
            "7. **Riesgos / cosas a revisar**: vulnerabilidades, deuda tecnica, archivos sospechosos.\n"
            "8. **Recomendaciones** concretas y accionables.\n\n"
            f"DATOS DE LA CARPETA:\n{scan_block}"
        )

        llm_answer = ""
        llm_source = ""
        try:
            if is_local:
                self.ensure_opencode_server(base_url, config)
                if not self.quick_session_id:
                    created = self.request_json(f"{base_url}/session", {"title": "Claudy Desktop"}, config, timeout=12)
                    self.quick_session_id = created.get("id")
                provider_id, _, model_id = model.partition("/")
                payload = {
                    "model": {"providerID": provider_id, "modelID": model_id or provider_id},
                    "system": "Eres Claudy. Analiza carpetas y devuelves Markdown estructurado, conciso y accionable.",
                    "tools": {"bash": False, "read": False, "glob": False, "grep": False, "webfetch": False,
                              "edit": False, "task": False, "todowrite": False,
                              "websearch": False, "codesearch": False, "lsp": False, "skill": False},
                    "parts": [{"type": "text", "text": analysis_prompt}],
                }
                response = self.request_json(f"{base_url}/session/{self.quick_session_id}/message", payload, config, timeout=180)
                parts = response.get("parts") or []
                llm_answer = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
                llm_source = model
            else:
                response = self._call_remote_provider(model, "Eres Claudy. Analiza carpetas en Markdown.", "", analysis_prompt, config)
                # Extract text from any provider format
                if response.get("content") and isinstance(response["content"], list):
                    llm_answer = "\n".join(b.get("text", "") for b in response["content"] if b.get("type") == "text").strip()
                elif response.get("choices"):
                    llm_answer = response["choices"][0].get("message", {}).get("content", "").strip()
                llm_source = model
        except Exception as e:
            self._debug_log("ANALYZE_FOLDER LLM PRIMARY FAILED", str(e))
            # Fallback: try remote providers if local failed
            if is_local:
                try:
                    _status("OpenCode no disponible, probando proveedor remoto...")
                    response = self._call_remote_provider(model, "Eres Claudy. Analiza carpetas en Markdown.", "", analysis_prompt, config)
                    if response.get("content") and isinstance(response["content"], list):
                        llm_answer = "\n".join(b.get("text", "") for b in response["content"] if b.get("type") == "text").strip()
                    elif response.get("choices"):
                        llm_answer = response["choices"][0].get("message", {}).get("content", "").strip()
                    llm_source = f"{model} (remoto)"
                except Exception:
                    pass

        # Ultimate fallback: Pollinations API (free, no API key needed)
        if not llm_answer:
            try:
                _status("Usando Pollinations (fallback gratuito)...")
                poll_payload = {
                    "model": "openai",
                    "messages": [
                        {"role": "system", "content": "Eres Claudy, un asistente experto en analisis de codigo y proyectos. Responde en espanol. Devuelves Markdown estructurado, conciso y accionable."},
                        {"role": "user", "content": analysis_prompt[:12000]},
                    ],
                    "max_tokens": 2000,
                }
                req = urllib.request.Request(
                    "https://text.pollinations.ai/openai",
                    data=json.dumps(poll_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "Claudy/1.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    poll_data = json.loads(resp.read().decode("utf-8"))
                choices = poll_data.get("choices") or []
                if choices:
                    msg = choices[0].get("message") or {}
                    llm_answer = msg.get("content", "").strip()
                if not llm_answer:
                    llm_answer = poll_data.get("response", "").strip()
                llm_source = "Pollinations (fallback gratuito)"
            except Exception as poll_err:
                llm_answer = f"_(No se pudo consultar a ningun LLM. Ultimo error: {poll_err})_"
                llm_source = "ninguno"

        _status("Guardando analisis...")
        folder_name = os.path.basename(os.path.abspath(folder_path)) or "raiz"
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        md_content = (
            f"**Carpeta:** `{folder_path}`\n"
            f"**Analizada:** {ts}\n"
            f"**Modelo:** {llm_source or model}\n\n"
            f"## Analisis del LLM\n\n{llm_answer or '_(sin respuesta)_'}\n\n"
            f"---\n\n## Estructura\n\n```\n{structure[:6000]}\n```\n\n"
            f"## Estadisticas\n\n```\n{stats[:2000]}\n```\n\n"
            f"## Archivos clave (extracto)\n\n"
        )
        for kc in key_contents[:5]:
            md_content += f"```\n{kc[:1500]}\n```\n\n"

        title = f"Analisis carpeta - {folder_name} - {datetime.datetime.now().strftime('%Y%m%d_%H%M')}"

        # Save into Claudy/Analisis-Carpetas/ subfolder of the vault for organization.
        vault = self._get_obsidian_vault()
        note_info = ""
        result = ""
        if vault:
            subdir = os.path.join(vault, "Claudy", "Analisis-Carpetas")
            try:
                os.makedirs(subdir, exist_ok=True)
                safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:120]
                fname = f"{safe_title}.md"
                fpath = os.path.join(subdir, fname)
                counter = 1
                while os.path.exists(fpath):
                    fname = f"{safe_title}_{counter}.md"
                    fpath = os.path.join(subdir, fname)
                    counter += 1
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(f"---\ntags: [claudy, analisis-carpeta]\ncarpeta: {folder_path}\nfecha: {ts}\n---\n\n")
                    f.write(f"# {title}\n\n")
                    f.write(md_content)
                size_kb = round(os.path.getsize(fpath) / 1024, 1)
                result = f"Nota creada en Obsidian: Claudy/Analisis-Carpetas/{fname}"
                note_info = f"\n\nArchivo: {fpath}\nTamano: {size_kb} KB"
            except Exception as e:
                result = f"Error guardando nota: {e}"
        else:
            # Fallback: save locally in ~/.claudy/analisis/ when Obsidian is not configured
            local_dir = os.path.join(os.path.expanduser("~"), ".claudy", "analisis")
            try:
                os.makedirs(local_dir, exist_ok=True)
                safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:120]
                fname = f"{safe_title}.md"
                fpath = os.path.join(local_dir, fname)
                counter = 1
                while os.path.exists(fpath):
                    fname = f"{safe_title}_{counter}.md"
                    fpath = os.path.join(local_dir, fname)
                    counter += 1
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(f"# {title}\n\n")
                    f.write(md_content)
                size_kb = round(os.path.getsize(fpath) / 1024, 1)
                result = f"Analisis guardado en: {fpath}"
                note_info = f"\nTamano: {size_kb} KB"
            except Exception as e:
                result = f"Analisis generado (no se pudo guardar: {e})"

        word_count = len((llm_answer or "").split())
        char_count = len(llm_answer or "")

        _status("Listo.")
        # Build the display text (analysis only, no file paths that confuse _set_response_text)
        display_text = (
            f"Analisis de: {folder_name}\n"
            f"Fuente: {llm_source or model}\n"
            f"{word_count} palabras\n\n"
            f"{llm_answer or '_(sin respuesta del LLM)_'}"
        )
        # Persistir el análisis en la memoria de agentes (memory.db) + Obsidian
        # para que quede como contexto recuperable a futuro.
        try:
            resumen = " ".join((llm_answer or "").split())[:3000]
            if resumen:
                self._save_memory("claudy", f"[Análisis de carpeta: {folder_path}] {resumen}")
        except Exception:
            pass

        # Return (display_text, saved_file_path) so caller can show both separately
        saved_path = ""
        try:
            saved_path = fpath  # type: ignore[possibly-undefined]
        except NameError:
            pass
        return (display_text, saved_path)


    def _create_obsidian_note(self, title, content):
        vault = self._get_obsidian_vault()
        if not vault:
            return "No encuentro tu vault de Obsidian. Configura 'obsidian.vaultPath' en ~/.claudy/config.json o crea la carpeta ~/Obsidian."
        # Sanitize title for filename.
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:100]
        if not safe_title:
            safe_title = f"Nota_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        fname = f"{safe_title}.md"
        fpath = os.path.join(vault, fname)
        # Handle duplicate names.
        counter = 1
        while os.path.exists(fpath):
            fname = f"{safe_title}_{counter}.md"
            fpath = os.path.join(vault, fname)
            counter += 1
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                f.write(f"Creado por Claudy - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                f.write(content + "\n")
            return f"Nota creada en Obsidian: {fname}\nRuta: {fpath}\n[CLAUDY_PATH:{fpath}]"
        except Exception as e:
            return f"Error creando nota: {e}"

    # ------------------------------------------------------------------
    # Memoria deliberada: que Claudy actualice su memoria / agentes / Obsidian
    # ------------------------------------------------------------------
    # Frases que ordenan GUARDAR un conocimiento duradero (ordenadas de más
    # larga a más corta para recortar el prefijo correctamente).



    def _search_obsidian_notes(self, query):
        vault = self._get_obsidian_vault()
        if not vault:
            return "No encuentro tu vault de Obsidian."
        results = []
        query_lower = query.lower() if query else ""
        try:
            for root, dirs, files in os.walk(vault):
                # Skip hidden folders and .obsidian config.
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fname in files:
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, vault)
                    if query_lower:
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read().lower()
                            if query_lower in content or query_lower in fname.lower():
                                # Get first 200 chars as preview.
                                preview = content[:200].replace("\n", " ").strip()
                                results.append(f"- {rel}\n  Preview: {preview}...")
                        except Exception:
                            continue
                    else:
                        results.append(f"- {rel}")
                    if len(results) >= 15:
                        break
                if len(results) >= 15:
                    break
        except Exception as e:
            return f"Error buscando notas: {e}"
        if not results:
            return "No encontré notas" + (f" con '{query}'" if query else "") + " en tu vault."
        header = f"Notas en Obsidian" + (f" para '{query}'" if query else "") + f" ({len(results)} encontradas):\n\n"
        return header + "\n".join(results)

    # ------------------------------------------------------------------
    # 1. Web Search (DuckDuckGo - free, no API key)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Weather (wttr.in API - free, no API key needed)
    # ------------------------------------------------------------------
    def _get_weather(self, city):
        """Fetch real weather data from wttr.in API."""
        display_city = city if city else "tu ubicación"
        self._update_progress(f"Consultando clima de {display_city}...")
        city_encoded = urllib.parse.quote(city.strip())

        try:
            # Fetch JSON forecast
            req = urllib.request.Request(
                f"https://wttr.in/{city_encoded}?format=j1",
                headers={"User-Agent": "curl/7.68.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))

            # Current conditions
            curr = data.get("current_condition", [{}])[0]
            temp = curr.get("temp_C", "?")
            feels = curr.get("FeelsLikeC", "")
            humidity = curr.get("humidity", "")
            wind = curr.get("windspeedKmph", "")
            # Get description in Spanish if available
            desc_list = curr.get("lang_es", curr.get("weatherDesc", [{}]))
            desc = desc_list[0].get("value", "") if desc_list else ""

            # Area name
            area = data.get("nearest_area", [{}])[0]
            area_name = area.get("areaName", [{}])[0].get("value", city)
            country = area.get("country", [{}])[0].get("value", "")

            lines = [
                f"CLIMA EN {area_name.upper()}, {country.upper()}",
                f"",
                f"Ahora: {temp}C  {desc}",
            ]
            if feels:
                lines.append(f"Sensacion: {feels}C")
            if humidity:
                lines.append(f"Humedad: {humidity}%")
            if wind:
                lines.append(f"Viento: {wind} km/h")

            # Forecast days
            dias = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
            weather_days = data.get("weather", [])
            if weather_days:
                lines.append("")
                lines.append("PRONOSTICO:")
                for w in weather_days:
                    date_str = w.get("date", "")
                    max_t = w.get("maxtempC", "?")
                    min_t = w.get("mintempC", "?")
                    # Get midday description
                    hourly = w.get("hourly", [])
                    mid = hourly[len(hourly)//2] if hourly else {}
                    day_desc_list = mid.get("lang_es", mid.get("weatherDesc", [{}]))
                    day_desc = day_desc_list[0].get("value", "") if day_desc_list else ""
                    # Parse day of week
                    try:
                        from datetime import datetime as dt
                        d = dt.strptime(date_str, "%Y-%m-%d")
                        day_name = dias[d.weekday()]
                    except Exception:
                        day_name = date_str
                    lines.append(f"  {day_name} {date_str}: {min_t}C / {max_t}C - {day_desc}")

            return "\n".join(lines)

        except Exception as e:
            # Fallback: try simple text format
            try:
                req = urllib.request.Request(
                    f"https://wttr.in/{city_encoded}?format=4&lang=es",
                    headers={"User-Agent": "curl/7.68.0"},
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    return resp.read().decode("utf-8", errors="ignore").strip()
            except Exception:
                return f"No pude obtener el clima de '{city}'. Error: {e}"

    def _web_search(self, query):
        """Search DuckDuckGo HTML and return top results (raw, for internal use)."""
        try:
            items = self._search_files_online(query, max_results=8)
            if items:
                formatted = []
                for item in items:
                    formatted.append(f"- {item['title']}\n  URL: {item['url']}\n  {item['snippet']}\n")
                return f"Resultados web para '{query}':\n\n" + "\n".join(formatted)
            return f"No encontré resultados para '{query}' en DuckDuckGo."
        except Exception as e:
            return f"Error buscando en web: {e}"

    def _web_search_and_answer(self, query):
        """Busca en internet y sintetiza la respuesta vía LLM."""
        import re as _re
        # Limpiar comillas/extra del query
        clean_query = query.strip().strip('"').strip("'").strip()
        try:
            items = self._search_files_online(clean_query, max_results=5)
        except Exception:
            items = []

        if items:
            context = f"RESULTADOS DE INTERNET para \"{clean_query}\":\n"
            for item in items[:5]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                url = item.get("url", "")
                context += f"- {title}: {snippet}\n  Fuente: {url}\n"
            enhanced_prompt = (
                f"{context}\n"
                f"INSTRUCCIONES ESTRICTAS:\n"
                f"1. RESPONDE DIRECTAMENTE usando los datos de arriba. NO digas 'voy a buscar' ni emitas /buscar.\n"
                f"2. Si los resultados tienen la respuesta, dala con la fuente al final.\n"
                f"3. Si los resultados NO tienen suficiente info, di 'No encontré datos suficientes sobre X' y cita lo que sí encontraste.\n"
                f"4. NUNCA emitas comandos /buscar, /webfetch, /leer en esta respuesta. Ya buscaste, ahora responde.\n\n"
                f"Pregunta original: {clean_query}"
            )
        else:
            enhanced_prompt = (
                f"NO se encontraron resultados de internet para '{clean_query}'. "
                f"Responde según tu conocimiento general en 2-3 líneas. "
                f"NO emitas comandos /buscar."
            )

        try:
            answer = self.send_quick_message(enhanced_prompt, _skip_skill_action=True)
        except Exception as e:
            return f"Error sintetizando respuesta: {e}"

        # Si el LLM aún devuelve /buscar (no siguió la instrucción), mostrar resultados crudos como fallback
        if items and _re.search(r'/buscar\s+', answer):
            fallback = f"Encontré esto sobre '{clean_query}':\n\n"
            for item in items[:3]:
                fallback += f"• {item.get('title','')}\n  {item.get('snippet','')}\n  {item.get('url','')}\n\n"
            return fallback.strip()

        return answer

    # ------------------------------------------------------------------
    # 2. Screenshot
    # ------------------------------------------------------------------
    def _take_screenshot(self):
        """Take a screenshot and describe it."""
        try:
            from PIL import ImageGrab
            import base64
            import io
            img = ImageGrab.grab()
            # Save to temp
            tmp_dir = os.path.join(os.path.expanduser("~"), ".claudy", "screenshots")
            os.makedirs(tmp_dir, exist_ok=True)
            fname = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            fpath = os.path.join(tmp_dir, fname)
            img.save(fpath)
            # Resize for API
            img.thumbnail((1024, 1024))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            # Send to LLM for analysis
            config = self.load_claudy_config()
            opencode = config["opencode"]
            base_url = opencode.get("baseUrl", "http://127.0.0.1:4096").rstrip("/")
            model = self._current_model or opencode.get("defaultModel", "deepseek-chat")
            is_local = any(h in base_url for h in ("127.0.0.1", "localhost", "0.0.0.0"))
            if is_local:
                self.ensure_opencode_server(base_url, config)
                if not self.quick_session_id:
                    created = self.request_json(f"{base_url}/session", {"title": "Claudy Desktop"}, config, timeout=12)
                    self.quick_session_id = created.get("id")
                provider_id, _, model_id = model.partition("/")
                payload = {
                    "model": {"providerID": provider_id, "modelID": model_id or provider_id},
                    "system": "Describe la captura de pantalla en español de forma breve y útil.",
                    "parts": [{"type": "image", "image": b64}, {"type": "text", "text": "¿Qué se ve en esta captura de pantalla?"}],
                }
                endpoint = f"{base_url}/session/{self.quick_session_id}/message"
            else:
                if "/" in model:
                    _, _, model = model.partition("/")
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Describe la captura de pantalla en español de forma breve y útil."},
                        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}, {"type": "text", "text": "¿Qué se ve en esta captura?"}]},
                    ],
                    "max_tokens": 500,
                }
                endpoint = f"{base_url}/chat/completions"
            response = self.request_json(endpoint, payload, config, timeout=60)
            text = ""
            parts = response.get("parts")
            if parts:
                text = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
            if not text:
                choices = response.get("choices")
                if choices:
                    text = choices[0].get("message", {}).get("content", "").strip()
            return f"Captura guardada: {fpath}\n\n{text or 'No pude analizar la imagen.'}"
        except Exception as e:
            return f"Error tomando screenshot: {e}"

    # ------------------------------------------------------------------
    # 3. Read local file
    # ------------------------------------------------------------------
    def _read_local_file(self, path):
        """Read a local file and return its content."""
        path = path.strip().strip('"').strip("'")
        if not os.path.exists(path):
            # Try expanding
            expanded = os.path.expanduser(path)
            if os.path.exists(expanded):
                path = expanded
            else:
                return f"No encuentro el archivo: {path}"
        if os.path.isdir(path):
            try:
                entries = os.listdir(path)[:30]
                return f"Contenido de {path}:\n" + "\n".join(f"- {e}" for e in entries)
            except Exception as e:
                return f"Error leyendo directorio: {e}"
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico"):
                return f"Archivo de imagen: {os.path.basename(path)} ({os.path.getsize(path)} bytes). Usa /screenshot para analizarla."
            if ext in (".exe", ".dll", ".msi", ".zip", ".rar", ".7z", ".tar", ".gz"):
                return f"Archivo binario/comprimido: {os.path.basename(path)} ({os.path.getsize(path)} bytes)."
            # Text-based files
            max_bytes = 50000
            size = os.path.getsize(path)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            truncated = size > max_bytes
            header = f"Archivo: {os.path.basename(path)}\nRuta: {path}\nTamaño: {size} bytes\n"
            if truncated:
                header += f"(Mostrando primeros {max_bytes} bytes de {size})\n"
            return header + "\n" + content[:10000]
        except UnicodeDecodeError:
            return f"Archivo binario: {os.path.basename(path)} ({os.path.getsize(path)} bytes)."
        except Exception as e:
            return f"Error leyendo archivo: {e}"

    # ------------------------------------------------------------------
    # 4. Execute command (safe)
    # ------------------------------------------------------------------
    def _process_embedded_commands(self, text):
        """Detect and execute /cmd lines in AI response, replace with real output."""
        import re
        stripped_all = (text or "").strip()
        try:
            import claudy_powers as cp
            m = re.match(r'^/(?:mkdir|crear-carpeta)\s+(.+)$', stripped_all, re.IGNORECASE | re.DOTALL)
            if m:
                return cp.create_folder(m.group(1).strip())
            m = re.match(r'^/(?:write|crear-archivo)\s+(.+)$', stripped_all, re.IGNORECASE | re.DOTALL)
            if m:
                path, content = cp.parse_path_content_arg(m.group(1))
                return cp.write_file(path, content) if path else "Uso: /write <ruta> | <contenido>"
            m = re.match(r'^/(?:append|agregar-archivo)\s+(.+)$', stripped_all, re.IGNORECASE | re.DOTALL)
            if m:
                path, content = cp.parse_path_content_arg(m.group(1))
                return cp.append_file(path, content) if path else "Uso: /append <ruta> | <contenido>"
            m = re.match(r'^/(?:replace|edit-replace)\s+(.+)$', stripped_all, re.IGNORECASE | re.DOTALL)
            if m:
                parts = [x.strip() for x in m.group(1).split(" | ", 2)]
                return cp.replace_in_file(parts[0], parts[1], parts[2]) if len(parts) >= 3 else "Uso: /replace <ruta> | <buscar> | <reemplazo>"
        except Exception:
            pass
        lines = text.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if re.match(r"^/(cmd|command|ejecutar|run|exec|bash|shell)\s+", stripped, re.IGNORECASE):
                cmd = stripped.split(None, 1)[1].strip() if " " in stripped else ""
                if cmd:
                    output = self._execute_command(cmd)
                    result.append(output)
                else:
                    result.append(line)
            else:
                result.append(line)
        return "\n".join(result)

    def _execute_command(self, cmd):
        """Execute a safe command and return output."""
        blocked = [
            ("rm -rf", "rm -rf es peligroso"),
            ("del /f", "del /f es peligroso"),
            ("format ", "formatear discos esta bloqueado"),
            ("shutdown", "shutdown esta bloqueado"),
            ("restart", "restart esta bloqueado"),
            ("taskkill", "matar procesos esta bloqueado"),
            ("net user", "net user esta bloqueado"),
            ("passwd", "passwd esta bloqueado"),
            ("sudo", "sudo esta bloqueado"),
        ]
        cmd_lower = cmd.lower()
        for keyword, reason in blocked:
            if keyword in cmd_lower:
                return f"No puedo ejecutar ese comando por seguridad (bloqueado: {reason}).\nComando: {cmd[:150]}"
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30, creationflags=flags,
            )
            out = result.stdout.strip()
            err = result.stderr.strip()
            if out:
                return f"Comando ejecutado:\n$ {cmd}\n\n{out[:2000]}"
            if err:
                return f"Comando ejecutado:\n$ {cmd}\n\nError: {err[:500]}"
            return f"Comando ejecutado sin salida: {cmd}"
        except subprocess.TimeoutExpired:
            return "El comando tardó demasiado (>30s)."
        except Exception as e:
            return f"Error ejecutando: {e}"

    # ------------------------------------------------------------------
    # 5. Reminders
    # ------------------------------------------------------------------
    def _set_reminder(self, text):
        """Parse reminder like '10 minutos comprar leche' and set a timer."""
        import re
        match = re.match(r"(\d+)\s*(min|minuto|minutos|seg|segundo|segundos|hora|horas|h)\s+(.+)", text, re.IGNORECASE)
        if not match:
            return "Formato: /recordar <tiempo> <mensaje>\nEj: /recordar 10 minutos revisar email\nEj: /recordar 5 seg probar algo"
        amount = int(match.group(1))
        unit = match.group(2).lower()
        message = match.group(3).strip()
        if unit.startswith("seg"):
            seconds = amount
        elif unit.startswith("hora"):
            seconds = amount * 3600
        else:
            seconds = amount * 60
        if seconds > 86400:
            return "Máximo 24 horas para recordatorios."
        def notify():
            try:
                # Windows notification
                from winotify import Notification
                n = Notification(app_id="Claudy", title="Recordatorio Claudy", msg=message, duration="long")
                n.set_audio(default=True)
                n.show()
            except ImportError:
                # Fallback: just print
                pass
            # Also show in bubble if it exists
            if hasattr(self, "bubble_win") and self.bubble_win and self.bubble_win.winfo_exists():
                try:
                    for child in self.bubble_win.winfo_children():
                        if isinstance(child, tk.Label):
                            child.configure(text=f"RECORDATORIO: {message}")
                except Exception:
                    pass
        threading.Timer(seconds, notify).start()
        display = f"{amount} {'segundos' if unit.startswith('seg') else 'minutos' if unit.startswith('min') else 'horas'}"
        return f"Recordatorio en {display}: {message}"

    # ------------------------------------------------------------------
    # 6. News summary
    # ------------------------------------------------------------------
    def _get_news(self):
        """Fetch and summarize top news."""
        try:
            import xml.etree.ElementTree as ET
            feeds = [
                ("Google News ES", "https://news.google.com/rss?hl=es-419&gl=US&ceid=US:es-419"),
                ("BBC Mundo", "https://feeds.bbci.co.uk/mundo/rss.xml"),
            ]
            all_news = []
            for name, url in feeds:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        xml = resp.read().decode("utf-8", errors="ignore")
                    root = ET.fromstring(xml)
                    for item in root.findall(".//item")[:5]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        all_news.append(f"- {title}\n  {link}")
                except Exception:
                    continue
            if all_news:
                return f"Noticias del día:\n\n" + "\n\n".join(all_news[:10])
            return "No pude obtener noticias. Verifica tu conexión."
        except Exception as e:
            return f"Error obteniendo noticias: {e}"

    # ------------------------------------------------------------------
    # 7. Translation
    # ------------------------------------------------------------------
    def _translate_text(self, text):
        """Translate text using LLM."""
        # Parse: "hola mundo a ingles" or "translate hello to spanish"
        import re
        langs = {
            "ingles": "English", "español": "Spanish", "frances": "French", "aleman": "German",
            "portugues": "Portuguese", "italiano": "Italian", "japones": "Japanese", "chino": "Chinese",
            "coreano": "Korean", "ruso": "Russian", "arabe": "Arabic", "hindi": "Hindi",
            "english": "English", "spanish": "Spanish", "french": "French", "german": "German",
            "portuguese": "Portuguese", "italian": "Italian", "japanese": "Japanese", "chinese": "Chinese",
            "korean": "Korean", "russian": "Russian", "arabic": "Arabic",
        }
        match = re.search(r"\s+a\s+(.+)$", text, re.IGNORECASE)
        if not match:
            match = re.search(r"\s+to\s+(.+)$", text, re.IGNORECASE)
        if not match:
            return "Formato: /traducir <texto> a <idioma>\nEj: /traducir hello world a español"
        target_lang = match.group(1).strip().lower()
        lang_name = langs.get(target_lang, target_lang.capitalize())
        source_text = text[:match.start()].strip()
        # Use LLM for translation
        config = self.load_claudy_config()
        opencode = config["opencode"]
        base_url = opencode.get("baseUrl", "http://127.0.0.1:4096").rstrip("/")
        model = self._current_model or opencode.get("defaultModel", "deepseek-chat")
        is_local = any(h in base_url for h in ("127.0.0.1", "localhost", "0.0.0.0"))
        prompt = f"Translate to {lang_name}: {source_text}"
        if is_local:
            self.ensure_opencode_server(base_url, config)
            if not self.quick_session_id:
                created = self.request_json(f"{base_url}/session", {"title": "Claudy Desktop"}, config, timeout=12)
                self.quick_session_id = created.get("id")
            provider_id, _, model_id = model.partition("/")
            payload = {
                "model": {"providerID": provider_id, "modelID": model_id or provider_id},
                "system": f"You are a translator. Translate the following text to {lang_name}. Only output the translation, nothing else.",
                "parts": [{"type": "text", "text": prompt}],
            }
            endpoint = f"{base_url}/session/{self.quick_session_id}/message"
        else:
            if "/" in model:
                _, _, model = model.partition("/")
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": f"You are a translator. Translate to {lang_name}. Only output the translation."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 500,
            }
            endpoint = f"{base_url}/chat/completions"
        response = self.request_json(endpoint, payload, config, timeout=30)
        text_out = ""
        parts = response.get("parts")
        if parts:
            text_out = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
        if not text_out:
            choices = response.get("choices")
            if choices:
                text_out = choices[0].get("message", {}).get("content", "").strip()
        return f"Traducción a {lang_name}:\n\n{text_out or 'No pude traducir.'}"

    # ------------------------------------------------------------------
    # 8. Calculator
    # ------------------------------------------------------------------
    def _calculate(self, expr):
        """Safe calculator using ast."""
        import ast
        import math
        allowed = {
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "log": math.log, "log10": math.log10, "exp": math.exp, "pi": math.pi,
            "e": math.e, "abs": abs, "round": round, "pow": pow, "min": min, "max": max,
        }
        expr = expr.strip()
        try:
            node = ast.parse(expr, mode="eval")
            for subnode in ast.walk(node):
                if isinstance(subnode, ast.Call):
                    if isinstance(subnode.func, ast.Name) and subnode.func.id not in allowed:
                        return f"Función no permitida: {subnode.func.id}"
                elif isinstance(subnode, ast.Attribute):
                    return "Acceso a atributos no permitido."
            result = eval(compile(node, "<expr>", "eval"), {"__builtins__": {}}, allowed)
            return f"Resultado: {expr} = {result}"
        except Exception as e:
            return f"Error calculando '{expr}': {e}"

    # ------------------------------------------------------------------
    # 9. Music control
    # ------------------------------------------------------------------
    def _control_music(self, action):
        """Control media playback via Windows media keys."""
        import ctypes
        VK_MEDIA_PLAY_PAUSE = 0xB3
        VK_MEDIA_NEXT_TRACK = 0xB0
        VK_MEDIA_PREV_TRACK = 0xB1
        KEYEVENTF_KEYUP = 0x0002
        action = action.lower().strip()
        key_map = {
            "play": VK_MEDIA_PLAY_PAUSE, "pausa": VK_MEDIA_PLAY_PAUSE, "pause": VK_MEDIA_PLAY_PAUSE,
            "siguiente": VK_MEDIA_NEXT_TRACK, "next": VK_MEDIA_NEXT_TRACK, "skip": VK_MEDIA_NEXT_TRACK,
            "anterior": VK_MEDIA_PREV_TRACK, "prev": VK_MEDIA_PREV_TRACK, "previous": VK_MEDIA_PREV_TRACK,
            "atras": VK_MEDIA_PREV_TRACK,
        }
        vk = key_map.get(action)
        if not vk:
            return f"Acciones: play/pause, siguiente/next, anterior/prev\nUsa: /musica {action}"
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        action_name = {VK_MEDIA_PLAY_PAUSE: "Play/Pause", VK_MEDIA_NEXT_TRACK: "Siguiente", VK_MEDIA_PREV_TRACK: "Anterior"}
        return f"Media: {action_name.get(vk, action)}"

    # ------------------------------------------------------------------
    # 10. Theme toggle
    # ------------------------------------------------------------------
    def _toggle_theme(self, specific_idx=None):
        """Cycle through or set a specific available theme."""
        global THEME, _active_theme_idx
        if specific_idx is not None:
            _active_theme_idx = specific_idx
        else:
            _active_theme_idx = (_active_theme_idx + 1) % len(_THEME_KEYS)
        key = _THEME_KEYS[_active_theme_idx]
        THEME.clear()
        THEME.update(THEMES[key])
        return f"Tema: {THEME['name']}"

    # ------------------------------------------------------------------
    # 10.5 Disk Space
    # ------------------------------------------------------------------
    def _get_disk_space(self):
        """Return detailed disk space info."""
        try:
            # Use PowerShell for better formatting
            ps_cmd = (
                "powershell -Command \""
                "Get-PSDrive -PSProvider FileSystem | "
                "Select-Object Name, @{N='UsedGB';E={[math]::Round(($_.Used)/1GB,2)}}, "
                "@{N='FreeGB';E={[math]::Round(($_.Free)/1GB,2)}}, "
                "@{N='TotalGB';E={[math]::Round(($_.Used+$_.Free)/1GB,2)}}, "
                "@{N='Use%';E={if($_.Used+$_.Free -gt 0){[math]::Round(($_.Used/($_.Used+$_.Free))*100,1)}else{0}}} | "
                "Format-Table -AutoSize\""
            )
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            r = subprocess.run(
                ps_cmd, shell=True, capture_output=True, text=True, timeout=15, creationflags=flags,
            )
            out = r.stdout.strip()
            if out:
                # Filter out empty lines and CDROM drives
                lines = [l for l in out.split("\n") if l.strip()]
                return "Almacenamiento:\n" + "\n".join(lines[-20:])
            return "No se pudo obtener informacion de discos."
        except Exception as e:
            return f"Error al revisar discos: {e}"

    # ------------------------------------------------------------------
    # 11. File Search
    # ------------------------------------------------------------------
    def _find_local_files(self, query, dirs, max_results=8):
        """Busca archivos por SEMEJANZA (fuzzy) entre el nombre dado y el real.
        Combina tokens contenidos + similitud difflib, tolerando typos y separadores.
        Devuelve lista de (score, ruta) ordenada de mejor a peor."""
        import re as _re
        import difflib as _dl
        qn = _re.sub(r'[\s_\-.]+', ' ', (query or "").lower()).strip()
        qtoks = [t for t in qn.split() if t]
        results = []
        seen = set()
        for d in dirs:
            if not d or not os.path.isdir(d):
                continue
            for root, dnames, files in os.walk(d):
                if root[len(d):].count(os.sep) >= 3:
                    dnames[:] = []
                for f in files:
                    fp = os.path.join(root, f)
                    if fp in seen:
                        continue
                    base = os.path.splitext(f)[0]
                    nn = _re.sub(r'[\s_\-.]+', ' ', base.lower()).strip()
                    contained = sum(1 for t in qtoks if t and t in nn)
                    # Similitud global + mejor similitud token-a-token (para nombres largos)
                    ratio = _dl.SequenceMatcher(None, qn, nn).ratio()
                    tok_ratio = 0.0
                    ntoks = nn.split()
                    for qt in qtoks:
                        best = max((_dl.SequenceMatcher(None, qt, nt).ratio() for nt in ntoks), default=0.0)
                        tok_ratio = max(tok_ratio, best)
                    frac = (contained / len(qtoks)) if qtoks else 0
                    # Aceptar si contiene tokens, o si se parece lo suficiente
                    if contained == 0 and ratio < 0.45 and tok_ratio < 0.7:
                        continue
                    score = frac * 3 + ratio + tok_ratio
                    seen.add(fp)
                    results.append((round(score, 3), fp))
        results.sort(key=lambda x: (-x[0], len(os.path.basename(x[1]))))
        return results[:max_results]

    def _analyze_local_file_sync(self, path):
        """Lee, analiza y resume un archivo local; guarda el análisis en memoria
        de agentes + Obsidian. Devuelve el resumen (texto)."""
        name = os.path.basename(path)
        folder = os.path.dirname(path)
        try:
            size_kb = round(os.path.getsize(path) / 1024, 1)
        except Exception:
            size_kb = 0
        ext = os.path.splitext(path)[1].lower()
        image_exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
        try:
            if ext in image_exts:
                answer = self._analyze_image_native(
                    path, "Describe esta imagen en español y extrae el texto visible.")
            else:
                text = self._extract_attachment_text(path)
                if not text.strip():
                    return f"📄 Encontré **{name}** en {folder} ({size_kb} KB), pero no pude extraer contenido legible."
                prompt2 = (
                    f"Analiza este archivo y dime de qué trata.\nArchivo: {name}\n\n"
                    "Contenido (puede venir truncado):\n```\n" + text + "\n```\n\n"
                    "Responde en español: (1) de qué trata en 1-2 frases, (2) puntos/datos clave, "
                    "(3) si aplica, montos, fechas o totales relevantes."
                )
                answer = self.send_quick_message(prompt2, _skip_skill_action=True, timeout=120)
        except Exception as e:
            return f"Encontré **{name}** en {folder} pero falló el análisis: {e}"
        try:
            self._save_memory("Usuario", f"Analizar archivo local: {name} ({folder})")
            self._save_memory("Claudy", f"[Análisis de archivo: {name}] {answer}")
        except Exception:
            pass
        return f"📄 **{name}**  ·  {folder}  ·  {size_kb} KB\n\n{answer}"

    def _search_files(self, query):
        """Search for files on the system using Windows search."""
        import fnmatch
        query = query.strip().strip('"').strip("'")
        search_dirs = [
            os.path.expanduser("~"),
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~/Documents"),
        ]
        results = []
        max_results = 20
        max_depth = 4
        query_lower = query.lower()

        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue
            try:
                for root, dirs, files in os.walk(search_dir):
                    # Limit depth
                    depth = root.replace(search_dir, "").count(os.sep)
                    if depth > max_depth:
                        dirs.clear()
                        continue
                    # Skip system/hidden dirs
                    dirs[:] = [d for d in dirs if not d.startswith(("$", ".", "AppData", "Windows", "Program Files"))]
                    for fname in files:
                        if query_lower in fname.lower() or fnmatch.fnmatch(fname.lower(), f"*{query_lower}*"):
                            fpath = os.path.join(root, fname)
                            try:
                                size = os.path.getsize(fpath)
                                size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
                            except Exception:
                                size_str = "N/A"
                            results.append(f"- {fname}\n  Ruta: {fpath}\n  Tamaño: {size_str}")
                            if len(results) >= max_results:
                                break
                    if len(results) >= max_results:
                        break
            except PermissionError:
                continue
            if len(results) >= max_results:
                break

        if results:
            return f"Archivos encontrados para '{query}' ({len(results)}):\n\n" + "\n\n".join(results)
        return f"No encontré archivos con '{query}' en las carpetas principales."

    # ------------------------------------------------------------------
    # 12. Download File
    # ------------------------------------------------------------------
    def _download_file(self, url):
        """Download a file from URL to Downloads folder."""
        url = url.strip().strip('"').strip("'")
        if not url.startswith(("http://", "https://")):
            return "URL inválida. Debe empezar con http:// o https://"
        try:
            # Extract filename from URL
            parsed = urllib.parse.urlparse(url)
            filename = os.path.basename(parsed.path)
            if not filename or "." not in filename:
                # Try Content-Disposition header (HEAD request may fail on some servers)
                try:
                    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        cd = resp.headers.get("Content-Disposition", "")
                        # Also check if final URL has a filename
                        if hasattr(resp, "url") and resp.url != url:
                            final_fname = os.path.basename(urllib.parse.urlparse(resp.url).path)
                            if final_fname and "." in final_fname:
                                filename = final_fname
                    if not filename and "filename=" in cd:
                        # Handle both filename= and filename*=
                        if "filename*=" in cd:
                            # RFC 5987: filename*=UTF-8''encoded_name
                            filename = cd.split("filename*=")[-1].split("''")[-1]
                            filename = urllib.parse.unquote(filename)
                        else:
                            filename = cd.split("filename=")[-1].strip('"').strip("'")
                except Exception:
                    pass  # HEAD failed, fall back to default name
                if not filename:
                    filename = "descarga_claudy"
            # Sanitize filename
            safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
            if not safe_name:
                safe_name = "archivo_descargado"
            dest_dir = os.path.expanduser("~/Downloads/Claudy")
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, safe_name)
            # Handle duplicates
            counter = 1
            base, ext = os.path.splitext(dest_path)
            while os.path.exists(dest_path):
                dest_path = f"{base}_{counter}{ext}"
                counter += 1
            # Download with progress
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                content_type = resp.headers.get("Content-Type", "").lower()
                chunk_size = 8192
                downloaded = 0
                first_chunk = resp.read(chunk_size)
                if not first_chunk:
                    return f"Error: el servidor devolvió 0 bytes.\nURL: {url}"

                # Detect HTML mirror/redirect pages (e.g. VideoLAN mirrors)
                is_html = "text/html" in content_type
                if not is_html:
                    try:
                        first_chunk.decode("utf-8")
                        if first_chunk.strip().startswith(b"<") or b"<!DOCTYPE" in first_chunk[:100].upper():
                            is_html = True
                    except UnicodeDecodeError:
                        pass

                if is_html:
                    # Server returned HTML instead of the binary — try to extract real download
                    full_html = first_chunk
                    while True:
                        more = resp.read(chunk_size)
                        if not more:
                            break
                        full_html += more
                        if len(full_html) > 500_000:
                            break
                    html_text = full_html.decode("utf-8", errors="ignore")

                    # Strategy A: meta http-equiv="refresh" redirect
                    meta_match = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^"\']*URL=["\']?([^"\'\s>]+)', html_text, re.IGNORECASE)
                    if meta_match:
                        redirect_url = meta_match.group(1).rstrip("'\"")
                        if not redirect_url.startswith("http"):
                            if redirect_url.startswith("//"):
                                redirect_url = "https:" + redirect_url
                            elif redirect_url.startswith("/"):
                                redirect_url = parsed.scheme + "://" + parsed.netloc + redirect_url
                        return self._download_file(redirect_url)

                    # Strategy B: find direct download links in the page
                    hrefs = re.findall(r'href="([^"]+)"', html_text)
                    target_exts = (".exe", ".msi", ".zip", ".7z", ".rar",
                                   ".nes", ".smc", ".sfc", ".gba", ".rom", ".nds", ".gb", ".gbc")
                    dl_links = [h for h in hrefs if any(h.lower().endswith(e) for e in target_exts)]
                    if dl_links:
                        # Prefer 64-bit for exe/msi, or first match for ROMs
                        best = next((h for h in dl_links if "64" in h), dl_links[0])
                        if not best.startswith("http"):
                            if best.startswith("//"):
                                best = "https:" + best
                            elif best.startswith("/"):
                                best = parsed.scheme + "://" + parsed.netloc + best
                            else:
                                best = urllib.parse.urljoin(url, best)
                        return self._download_file(best)

                    # HTML page with no download links found — DON'T save as file
                    return f"Error: el servidor devolvió HTML en vez del archivo.\nURL: {url}"

                # Normal binary download
                with open(dest_path, "wb") as f:
                    f.write(first_chunk)
                    downloaded = len(first_chunk)
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

            # Check Content-Disposition for real filename after download
            size_str = f"{downloaded / 1024:.1f} KB" if downloaded < 1024 * 1024 else f"{downloaded / (1024 * 1024):.1f} MB"
            return f"Archivo descargado:\n{dest_path}\nTamaño: {size_str}\n\nPuedes ejecutarlo con: /ejecutar {dest_path}"
        except urllib.error.HTTPError as e:
            return f"Error descargando (HTTP {e.code}): {e.reason}\nURL: {url}"
        except urllib.error.URLError as e:
            return f"Error de conexión: {e.reason}\nURL: {url}"
        except Exception as e:
            return f"Error descargando: {type(e).__name__}: {e}\nURL: {url}"

    # ------------------------------------------------------------------
    # 13. Execute File
    # ------------------------------------------------------------------
    def _execute_file(self, path):
        """Open/execute a file using Windows default handler."""
        path = path.strip().strip('"').strip("'")
        # Expand ~ and check existence
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded):
            path = expanded
        elif not os.path.exists(path):
            # Search in common locations
            for base in [os.path.expanduser("~"), os.path.expanduser("~/Downloads"), os.path.expanduser("~/Desktop")]:
                candidate = os.path.join(base, path)
                if os.path.exists(candidate):
                    path = candidate
                    break
            else:
                return f"No encuentro el archivo: {path}"
        # Safety check - warn about executables
        ext = os.path.splitext(path)[1].lower()
        executable_exts = (".exe", ".bat", ".cmd", ".ps1", ".msi", ".vbs", ".js")
        if ext in executable_exts:
            # Allow but warn
            pass
        try:
            # Use Windows shell execute (opens with default handler)
            os.startfile(path)
            return f"Archivo abierto: {os.path.basename(path)}\nRuta: {path}"
        except OSError as e:
            return f"No se pudo abrir: {e}"
        except Exception as e:
            return f"Error ejecutando: {e}"

    # ------------------------------------------------------------------
    # 13c. Play Game (Game + Emulator workflow)
    # ------------------------------------------------------------------
    def _play_game(self, game_name, console_hint=None):
        """Full workflow: find/download game, find/download emulator, run together."""
        console_map = {
            "nes": "fceux",
            "snes": "snes9x",
            "gba": "mgba",
            "n64": "project64",
            "ps1": "duckstation",
            "psx": "duckstation",
            "genesis": "kega fusion",
            "megadrive": "kega fusion",
            "gameboy": "mgba",
            "gbc": "mgba",
            "nds": "desmume",
            "mame": "mame"
        }

        # Determine console
        console = (console_hint or "").lower().strip()
        if not console:
            # Try to find console keywords in game name
            for k in console_map:
                if k in game_name.lower():
                    console = k
                    break
        
        if not console:
            return "No pude determinar para qué consola es el juego. Por favor especifica la consola (ej: 'quiero jugar robocop de nes')."

        emu_name = console_map.get(console)
        self._update_progress(f"Iniciando flujo para jugar '{game_name}' en {console.upper()}...")

        claudy_dir = os.path.expanduser("~/Downloads/Claudy")
        os.makedirs(claudy_dir, exist_ok=True)

        # 1. Check/Download Game
        self._update_progress(f"Paso 1/3: Verificando juego '{game_name}'...")
        rom_path = None
        rom_exts = (".nes", ".smc", ".sfc", ".gba", ".rom", ".nds", ".gb", ".gbc", ".zip", ".7z", ".bin", ".iso")
        
        # Search local
        if os.path.exists(claudy_dir):
            for f in os.listdir(claudy_dir):
                if game_name.lower().replace(" ", "") in f.lower().replace(" ", "") and f.lower().endswith(rom_exts):
                    rom_path = os.path.join(claudy_dir, f)
                    break
        
        if not rom_path:
            self._update_progress(f"Juego no encontrado. Buscando '{game_name} {console} rom'...")
            res = self._download_by_name(f"{game_name} {console} rom")
            if "Archivo descargado:" in res:
                # Extract path from result text
                path_match = re.search(r'(?:[A-Za-z]:\\|/)[^:\n\r]+', res)
                if path_match:
                    rom_path = path_match.group(0).strip()
            
            if not rom_path or not os.path.exists(rom_path):
                return f"No pude conseguir el juego '{game_name}'.\n{res}"

        # 2. Check/Download Emulator
        self._update_progress(f"Paso 2/3: Verificando emulador {emu_name.upper()}...")
        emu_exe = None
        
        # Search in Claudy dir and subdirs
        for root, dirs, files in os.walk(claudy_dir):
            for f in files:
                if emu_name.replace(" ", "") in f.lower().replace(" ", "") and f.lower().endswith(".exe"):
                    emu_exe = os.path.join(root, f)
                    break
            if emu_exe: break

        if not emu_exe:
            self._update_progress(f"Emulador no encontrado. Descargando {emu_name}...")
            # Try to install/download
            res = self._install_app(emu_name)
            
            # Look for ZIP to extract (often emulators are portable zips)
            for f in os.listdir(claudy_dir):
                if emu_name.replace(" ", "") in f.lower().replace(" ", "") and f.lower().endswith(".zip"):
                    zip_path = os.path.join(claudy_dir, f)
                    self._update_progress(f"Extrayendo emulador {f}...")
                    try:
                        import zipfile
                        emu_extract_dir = os.path.join(claudy_dir, emu_name.replace(" ", "_"))
                        os.makedirs(emu_extract_dir, exist_ok=True)
                        with zipfile.ZipFile(zip_path, 'r') as z:
                            z.extractall(emu_extract_dir)
                        # Search again in extracted dir
                        for r, d, fls in os.walk(emu_extract_dir):
                            for ff in fls:
                                if ff.lower().endswith(".exe") and "debug" not in ff.lower():
                                    emu_exe = os.path.join(r, ff)
                                    break
                            if emu_exe: break
                    except Exception as e:
                        print(f"Error extracting emulator: {e}")
                    break
            
            # Final check in all Claudy dir
            if not emu_exe:
                for root, dirs, files in os.walk(claudy_dir):
                    for f in files:
                        if emu_name.replace(" ", "") in f.lower().replace(" ", "") and f.lower().endswith(".exe"):
                            emu_exe = os.path.join(root, f)
                            break
                    if emu_exe: break

        if not emu_exe:
            return f"No pude instalar el emulador '{emu_name}' para {console.upper()}. Por favor instálalo manualmente."

        # 3. Run
        self._update_progress(f"Paso 3/3: Abriendo {game_name} con {emu_name}...")
        try:
            # Open emulator with ROM as argument
            subprocess.Popen([emu_exe, rom_path])
            return f"¡A jugar! 🎮\n\nAbriendo '{game_name}' en {emu_name.upper()}.\n\nJuego: {os.path.basename(rom_path)}\nEmulador: {os.path.basename(emu_exe)}"
        except Exception as e:
            return f"Error al ejecutar: {e}"

    # ------------------------------------------------------------------
    # 13b-0. Download By Name (search + download)
    # ------------------------------------------------------------------
    def _download_by_name(self, what):
        """Search for a file/program by name, find download link, and download it."""
        self._update_progress(f"Buscando '{what}' en internet...")

        search_query = f"{what} download"
        results = self._search_files_online(search_query, max_results=10)
        if not results:
            search_query = f"{what} descargar"
            results = self._search_files_online(search_query, max_results=10)
        if not results:
            return f"No encontré '{what}' para descargar en internet."

        self._update_progress(f"Encontré {len(results)} resultados.\nAnalizando páginas...")

        # File extensions to look for
        file_exts = (
            ".exe", ".msi", ".zip", ".rar", ".7z", ".tar.gz",
            ".nes", ".snes", ".smc", ".sfc", ".gba", ".nds", ".rom", ".gb", ".gbc",
            ".iso", ".bin", ".img", ".dmg", ".apk",
            ".pdf", ".mp3", ".mp4", ".avi", ".mkv",
        )
        what_lower = what.lower().replace(" ", "")

        # Score search results
        scored = []
        for item in results:
            url = item["url"]
            url_lower = url.lower()
            score = 0
            # Direct file link = highest priority
            if any(url_lower.endswith(ext) for ext in file_exts):
                score += 50
            # URL contains the search term
            if what_lower in url_lower.replace("-", "").replace("_", "").replace("%20", ""):
                score += 10
            # Known ROM/download sites
            rom_sites = ["archive.org", "romspedia", "romsgames", "romsfun", "emuparadise",
                         "romhustler", "vimm.net", "freeroms", "nesfiles", "retrostic", "wowroms",
                         "emulatorgames", "github.com"]
            if any(s in url_lower for s in rom_sites):
                score += 8
            if "download" in url_lower or "rom" in url_lower:
                score += 5
            scored.append((score, url, item))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Try top results
        for idx, (score, url, item) in enumerate(scored[:5]):
            domain = urllib.parse.urlparse(url).netloc
            self._update_progress(f"Analizando ({idx+1}/{min(5, len(scored))}):\n{domain}...")

            # If it's a direct file link, download directly
            if any(url.lower().endswith(ext) for ext in file_exts):
                self._update_progress(f"Descargando archivo directo...\n{os.path.basename(urllib.parse.urlparse(url).path)}")
                result = self._download_file(url)
                if result.startswith("Archivo descargado:"):
                    return f"Descarga completada para '{what}'.\n\n{result}"
                continue

            # Otherwise, visit the page and scrape for download links
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                })
                with urllib.request.urlopen(req, timeout=12) as resp:
                    page_html = resp.read(500_000).decode("utf-8", errors="ignore")
                    final_url = resp.url

                # Extract all href links from the page
                hrefs = re.findall(r'href=["\']([^"\']+)["\']', page_html)
                # Also look for links in onclick, data-url, etc.
                hrefs += re.findall(r'data-(?:url|href|src)=["\']([^"\']+)["\']', page_html)

                # Filter for actual file links
                file_links = []
                for href in hrefs:
                    href_lower = href.lower()
                    if any(href_lower.endswith(ext) for ext in file_exts):
                        # Make absolute URL
                        if href.startswith("//"):
                            href = "https:" + href
                        elif href.startswith("/"):
                            parsed_base = urllib.parse.urlparse(final_url)
                            href = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                        elif not href.startswith("http"):
                            href = urllib.parse.urljoin(final_url, href)
                        file_links.append(href)

                if not file_links:
                    continue

                # Score file links - prefer ones matching the search term
                best_link = file_links[0]
                best_score = 0
                for fl in file_links:
                    fl_lower = fl.lower()
                    s = 0
                    if what_lower in fl_lower.replace("-", "").replace("_", "").replace("%20", ""):
                        s += 10
                    # Prefer common ROM/archive extensions
                    if any(fl_lower.endswith(ext) for ext in (".nes", ".smc", ".sfc", ".gba", ".zip", ".7z")):
                        s += 5
                    if s > best_score:
                        best_score = s
                        best_link = fl

                fname = os.path.basename(urllib.parse.urlparse(best_link).path)
                self._update_progress(f"Encontré archivo: {urllib.parse.unquote(fname)}\nDescargando...")
                result = self._download_file(best_link)
                if result.startswith("Archivo descargado:"):
                    return f"Descarga completada para '{what}'.\n\n{result}"

            except Exception:
                continue

        return f"No pude descargar '{what}'. Intenté {min(5, len(scored))} páginas pero no encontré archivos descargables."

    # ------------------------------------------------------------------
    # 13b. Search Files Online
    # ------------------------------------------------------------------
    def _search_files_online(self, query, max_results=8):
        """Search DuckDuckGo for download links. Returns list of dicts with url, title, snippet."""
        from html.parser import HTMLParser

        class DLParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.items = []
                self._in_title = False
                self._in_snippet = False
                self._curr_url = ""
                self._curr_title = ""
                self._curr_snippet = ""
            def handle_starttag(self, tag, attrs):
                ad = dict(attrs)
                if tag == "a":
                    cls = ad.get("class", "")
                    href = ad.get("href", "")
                    if "result__snippet" in cls:
                        self._in_snippet = True
                    elif "uddg=" in href and "result__url" not in cls:
                        self._curr_url = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                        self._in_title = True
                    elif "result-link" in cls or ("result__a" in cls):
                        if "uddg=" in href:
                            self._curr_url = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                            self._in_title = True
            def handle_data(self, data):
                if self._in_title:
                    self._curr_title += data
                elif self._in_snippet:
                    self._curr_snippet += data
            def handle_endtag(self, tag):
                if tag == "a":
                    if self._in_title:
                        self._in_title = False
                    elif self._in_snippet:
                        self._in_snippet = False
                        if self._curr_url and self._curr_title:
                            self.items.append({
                                "url": self._curr_url,
                                "title": self._curr_title.strip(),
                                "snippet": self._curr_snippet.strip()
                            })
                        self._curr_url = ""
                        self._curr_title = ""
                        self._curr_snippet = ""

        clean = lambda s: re.sub(r'<[^>]+>', '', s).strip()

        # Strategy 1: DuckDuckGo HTML (POST to avoid rate-limiting)
        try:
            post_data = urllib.parse.urlencode({"q": query}).encode("utf-8")
            req = urllib.request.Request(
                "https://html.duckduckgo.com/html/",
                data=post_data,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": "https://html.duckduckgo.com/",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            res = []
            seen = set()

            # Method A: Old format with uddg= redirect
            if "uddg=" in html:
                uddg_urls = re.findall(r'uddg=([^"&]+)', html)
                for raw in uddg_urls:
                    url = urllib.parse.unquote(raw)
                    domain = urllib.parse.urlparse(url).netloc
                    if domain not in seen and "duckduckgo.com" not in domain:
                        seen.add(domain)
                        res.append({"url": url, "title": domain, "snippet": ""})

            # Method B: New format with class="result__url" direct links
            if not res:
                result_urls = re.findall(r'class="result__url"[^>]*href="(https?://[^"]+)"', html)
                result_urls += re.findall(r'class="result__a"[^>]*href="(https?://[^"]+)"', html)
                for url in result_urls:
                    # Decode &amp; entities
                    url = url.replace("&amp;", "&")
                    domain = urllib.parse.urlparse(url).netloc
                    if domain not in seen and "duckduckgo.com" not in domain and "y.js" not in url:
                        seen.add(domain)
                        # Try to get title from nearby text
                        res.append({"url": url, "title": domain, "snippet": ""})

            if res[:max_results]:
                return res[:max_results]
        except Exception:
            pass

        # Strategy 2: DuckDuckGo Lite (POST)
        try:
            post_data = urllib.parse.urlencode({"q": query}).encode("utf-8")
            req = urllib.request.Request(
                "https://lite.duckduckgo.com/lite/",
                data=post_data,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            # Lite format: links in <a rel="nofollow" href="URL" class="result-link">Title</a>
            # and snippet in <td class="result-snippet">...</td>
            urls = re.findall(r'class="result-link"\s+href="([^"]+)"', html)
            titles = re.findall(r'class="result-link"[^>]*>(.+?)</a>', html, re.DOTALL)
            snippets_raw = re.findall(r'class="result-snippet">(.+?)</td>', html, re.DOTALL)
            res = []
            for i, url in enumerate(urls[:max_results]):
                title = clean(titles[i]) if i < len(titles) else ""
                snippet = clean(snippets_raw[i]) if i < len(snippets_raw) else ""
                if url.startswith("http"):
                    res.append({"url": url, "title": title, "snippet": snippet})
            if res:
                return res
        except Exception:
            pass

        # Strategy 3: Brave Search (most reliable for automated queries)
        try:
            search_url = f"https://search.brave.com/search?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            # Brave uses various link patterns
            raw_urls = re.findall(r'href="(https?://(?!search\.brave)[^"]+)"', html)
            res = []
            seen = set()
            skip_domains = {"brave.com", "bravesoftware.com", "youtube.com", "google.com"}
            for url in raw_urls:
                domain = urllib.parse.urlparse(url).netloc.lower()
                if domain in seen or any(d in domain for d in skip_domains):
                    continue
                seen.add(domain)
                res.append({"url": url, "title": domain, "snippet": ""})
                if len(res) >= max_results:
                    break
            if res:
                return res
        except Exception:
            pass

        # Strategy 4: Google fallback (simple scrape)
        try:
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num=10"
            req = urllib.request.Request(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html",
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            # Google wraps URLs in /url?q=ACTUAL_URL&sa=...
            raw_urls = re.findall(r'/url\?q=(https?://[^&"]+)', html)
            res = []
            seen = set()
            for raw in raw_urls:
                url = urllib.parse.unquote(raw)
                domain = urllib.parse.urlparse(url).netloc
                if domain in seen or "google.com" in domain or "youtube.com" in domain:
                    continue
                seen.add(domain)
                res.append({"url": url, "title": domain, "snippet": ""})
                if len(res) >= max_results:
                    break
            if res:
                return res
        except Exception:
            pass

        return []

    def _parse_winget_search(self, output, query):
        rows = []
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("-") or stripped.lower().startswith("name "):
                continue
            parts = re.split(r"\s{2,}", stripped)
            if len(parts) >= 2:
                if parts[1].strip().lower() == "id":
                    continue
                rows.append({"name": parts[0].strip(), "id": parts[1].strip(), "version": parts[2].strip() if len(parts) > 2 else ""})

        if not rows:
            return None

        query_words = [w for w in query.lower().split() if len(w) > 1]
        best = None
        best_score = -1
        for pkg in rows:
            haystack = f"{pkg['name']} {pkg['id']}".lower()
            score = 0
            if pkg["name"].lower() == query.lower():
                score += 50
            if pkg["id"].lower() == query.lower():
                score += 50
            for word in query_words:
                if word in haystack:
                    score += 10
            if query.lower() in ("rar", "winrar") and "winrar" in haystack:
                score += 30
            if score > best_score:
                best = pkg
                best_score = score
        return best

    def _install_with_winget(self, app_name):
        if os.name != "nt" or not shutil.which("winget"):
            return None

        try:
            search = subprocess.run(
                ["winget", "search", "--source", "winget", "--accept-source-agreements", app_name],
                capture_output=True, text=True, timeout=45, encoding="utf-8", errors="ignore",
            )
            if search.returncode != 0:
                return f"winget no pudo buscar '{app_name}': {search.stderr.strip() or search.stdout.strip()}"

            pkg = self._parse_winget_search(search.stdout, app_name)
            if not pkg:
                return f"winget no encontró un paquete claro para '{app_name}'."

            install = subprocess.run(
                [
                    "winget", "install",
                    "--id", pkg["id"],
                    "--exact",
                    "--source", "winget",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ],
                capture_output=True, text=True, timeout=15 * 60, encoding="utf-8", errors="ignore",
            )

            output = (install.stdout + "\n" + install.stderr).strip()
            if install.returncode != 0:
                return f"winget encontró {pkg['name']} ({pkg['id']}), pero falló la instalación:\n{output[-1200:]}"

            try:
                subprocess.Popen(["cmd", "/c", "start", "", pkg["name"]], shell=False)
            except Exception:
                pass

            tail = f"\n\nSalida:\n{output[-1200:]}" if output else ""
            return (f"Listo. Instalé '{pkg['name']}' usando winget.\n"
                    f"Paquete: {pkg['id']}\n"
                    f"También intenté abrir la aplicación al terminar.{tail}")
        except subprocess.TimeoutExpired:
            return f"winget tardó demasiado instalando '{app_name}'. Puede que el instalador siga esperando confirmación."
        except Exception as e:
            return f"winget falló: {type(e).__name__}: {e}"

    # ------------------------------------------------------------------
    # 13c. Install App (search + download + execute)
    # ------------------------------------------------------------------
    def _install_app(self, app_name):
        """Search, download and execute an app installer."""
        app_name = app_name.strip().strip('"').strip("'").strip(".!?")
        if not app_name:
            return "No especificaste qué aplicación instalar."

        self._update_progress(f"Buscando '{app_name}'...")

        # ----------------------------------------------------------
        # Known apps database (direct download URLs - most reliable)
        # ----------------------------------------------------------
        KNOWN_APPS = {
            "vlc": {
                "name": "VLC Media Player",
                "url": "https://get.videolan.org/vlc/3.0.23/win64/vlc-3.0.23-win64.exe",
                "page": "https://www.videolan.org/vlc/",
            },
            "7zip": {
                "name": "7-Zip",
                "url": "https://www.7-zip.org/a/7z2409-x64.exe",
                "page": "https://www.7-zip.org/download.html",
            },
            "7-zip": {
                "name": "7-Zip",
                "url": "https://www.7-zip.org/a/7z2409-x64.exe",
                "page": "https://www.7-zip.org/download.html",
            },
            "notepad++": {
                "name": "Notepad++",
                "url": "https://github.com/notepad-plus-plus/notepad-plus-plus/releases/download/v8.7.7/npp.8.7.7.Installer.x64.exe",
                "page": "https://notepad-plus-plus.org/downloads/",
            },
            "notepadplusplus": {
                "name": "Notepad++",
                "url": "https://github.com/notepad-plus-plus/notepad-plus-plus/releases/download/v8.7.7/npp.8.7.7.Installer.x64.exe",
                "page": "https://notepad-plus-plus.org/downloads/",
            },
            "notepad plus plus": {
                "name": "Notepad++",
                "url": "https://github.com/notepad-plus-plus/notepad-plus-plus/releases/download/v8.7.7/npp.8.7.7.Installer.x64.exe",
                "page": "https://notepad-plus-plus.org/downloads/",
            },
            "firefox": {
                "name": "Mozilla Firefox",
                "url": "https://download.mozilla.org/?product=firefox-latest&os=win64&lang=es-MX",
                "page": "https://www.mozilla.org/firefox/",
            },
            "chrome": {
                "name": "Google Chrome",
                "url": "https://dl.google.com/chrome/install/ChromeStandaloneSetup64.exe",
                "page": "https://www.google.com/chrome/",
            },
            "google chrome": {
                "name": "Google Chrome",
                "url": "https://dl.google.com/chrome/install/ChromeStandaloneSetup64.exe",
                "page": "https://www.google.com/chrome/",
            },
            "vscode": {
                "name": "Visual Studio Code",
                "url": "https://code.visualstudio.com/sha/download?build=stable&os=win32-x64",
                "page": "https://code.visualstudio.com/",
            },
            "visual studio code": {
                "name": "Visual Studio Code",
                "url": "https://code.visualstudio.com/sha/download?build=stable&os=win32-x64",
                "page": "https://code.visualstudio.com/",
            },
            "git": {
                "name": "Git",
                "url": "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.2/Git-2.47.1.2-64-bit.exe",
                "page": "https://git-scm.com/downloads/win",
            },
            "python": {
                "name": "Python",
                "url": "https://www.python.org/ftp/python/3.13.1/python-3.13.1-amd64.exe",
                "page": "https://www.python.org/downloads/",
            },
            "node": {
                "name": "Node.js",
                "url": "https://nodejs.org/dist/v22.12.0/node-v22.12.0-x64.msi",
                "page": "https://nodejs.org/",
            },
            "nodejs": {
                "name": "Node.js",
                "url": "https://nodejs.org/dist/v22.12.0/node-v22.12.0-x64.msi",
                "page": "https://nodejs.org/",
            },
            "obs": {
                "name": "OBS Studio",
                "url": "https://cdn-fastly.obsproject.com/downloads/OBS-Studio-31.0.1-Full-Installer-x64.exe",
                "page": "https://obsproject.com/",
            },
            "obs studio": {
                "name": "OBS Studio",
                "url": "https://cdn-fastly.obsproject.com/downloads/OBS-Studio-31.0.1-Full-Installer-x64.exe",
                "page": "https://obsproject.com/",
            },
            "gimp": {
                "name": "GIMP",
                "url": "https://download.gimp.org/gimp/v2.10/windows/gimp-2.10.38-setup.exe",
                "page": "https://www.gimp.org/downloads/",
            },
            "audacity": {
                "name": "Audacity",
                "url": "https://github.com/audacity/audacity/releases/download/Audacity-3.7.3/audacity-win-3.7.3-64bit.exe",
                "page": "https://www.audacityteam.org/download/",
            },
            "winrar": {
                "name": "WinRAR",
                "url": "https://www.win-rar.com/fileadmin/winrar-versions/winrar/winrar-x64-710es.exe",
                "page": "https://www.win-rar.com/download.html",
            },
            "fceux": {
                "name": "FCEUX (NES Emulator)",
                "url": "https://github.com/TASEmulators/fceux/releases/download/v2.6.6/fceux-2.6.6-win64.zip",
                "page": "https://fceux.com/web/download.html",
            },
            "snes9x": {
                "name": "Snes9x (SNES Emulator)",
                "url": "https://github.com/snes9xgit/snes9x/releases/download/1.62.3/snes9x-1.62.3-win32-x64.zip",
                "page": "https://www.snes9x.com/",
            },
            "mgba": {
                "name": "mGBA (GBA Emulator)",
                "url": "https://github.com/mgba-emu/mgba/releases/download/0.10.3/mGBA-0.10.3-win64.zip",
                "page": "https://mgba.io/",
            },
            "project64": {
                "name": "Project64 (N64 Emulator)",
                "url": "https://www.pj64-emu.com/download/project64-3.0.1",
                "page": "https://www.pj64-emu.com/",
            },
            "duckstation": {
                "name": "DuckStation (PS1 Emulator)",
                "url": "https://github.com/stenzek/duckstation/releases/download/latest/duckstation-windows-x64-release.zip",
                "page": "https://www.duckstation.org/",
            },
            "rar": {
                "name": "WinRAR",
                "url": "https://www.win-rar.com/fileadmin/winrar-versions/winrar/winrar-x64-710es.exe",
                "page": "https://www.win-rar.com/download.html",
            },
            "telegram": {
                "name": "Telegram",
                "url": "https://telegram.org/dl/desktop/win64",
                "page": "https://desktop.telegram.org/",
            },
            "discord": {
                "name": "Discord",
                "url": "https://discord.com/api/downloads/distributions/app/installers/latest?channel=stable&platform=win&arch=x64",
                "page": "https://discord.com/download",
            },
            "spotify": {
                "name": "Spotify",
                "url": "https://download.scdn.co/SpotifySetup.exe",
                "page": "https://www.spotify.com/download/windows/",
            },
            "steam": {
                "name": "Steam",
                "url": "https://cdn.fastly.steamstatic.com/client/installer/SteamSetup.exe",
                "page": "https://store.steampowered.com/about/",
            },
            "zoom": {
                "name": "Zoom",
                "url": "https://zoom.us/client/latest/ZoomInstaller.exe",
                "page": "https://zoom.us/download",
            },
            "putty": {
                "name": "PuTTY",
                "url": "https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-0.82-installer.msi",
                "page": "https://www.putty.org/",
            },
            "filezilla": {
                "name": "FileZilla",
                "url": "https://download.filezilla-project.org/client/FileZilla_3.68.1_win64_sponsored2-setup.exe",
                "page": "https://filezilla-project.org/download.php",
            },
            "obsidian": {
                "name": "Obsidian",
                "url": "https://github.com/obsidianmd/obsidian-releases/releases/download/v1.7.7/Obsidian.1.7.7.exe",
                "page": "https://obsidian.md/download",
            },
            "blender": {
                "name": "Blender",
                "url": "https://download.blender.org/release/Blender4.3/blender-4.3.2-windows-x64.msi",
                "page": "https://www.blender.org/download/",
            },
            "handbrake": {
                "name": "HandBrake",
                "url": "https://github.com/HandBrake/HandBrake/releases/download/1.9.1/HandBrake-1.9.1-x86_64-Win_GUI.exe",
                "page": "https://handbrake.fr/downloads.php",
            },
            "qbittorrent": {
                "name": "qBittorrent",
                "url": "https://downloads.sourceforge.net/project/qbittorrent/qbittorrent-win32/qbittorrent-5.0.3/qbittorrent_5.0.3_x64_setup.exe",
                "page": "https://www.qbittorrent.org/download",
            },
            "everything": {
                "name": "Everything Search",
                "url": "https://www.voidtools.com/Everything-1.4.1.1026.x64-Setup.exe",
                "page": "https://www.voidtools.com/downloads/",
            },
        }

        app_key = app_name.lower().strip()
        known = KNOWN_APPS.get(app_key)

        # Also try fuzzy match
        if not known:
            for key, val in KNOWN_APPS.items():
                if app_key in key or key in app_key or app_key in val["name"].lower():
                    known = val
                    break

        if known:
            # Direct download from known URL
            self._update_progress(f"Encontré {known['name']} en mi base de datos.\nDescargando...")
            result = self._download_file(known["url"])
            if result.startswith("Archivo descargado:"):
                lines = result.splitlines()
                path = lines[1].strip() if len(lines) >= 2 else ""
                if path and os.path.exists(path):
                    ext = os.path.splitext(path)[1].lower()
                    if ext in (".exe", ".msi", ".bat", ".cmd"):
                        self._update_progress(f"Descarga completada: {os.path.basename(path)}\nInstalando...")
                        exec_result = self._execute_file(path)
                        return (f"Listo. Descargué e instalé {known['name']}.\n\n"
                                f"Archivo: {os.path.basename(path)}\n"
                                f"Ruta: {path}\n\n"
                                f"{exec_result}")
                    # If the downloaded file is an HTML page, scrape for exe links
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            html_content = f.read()
                        hrefs = re.findall(r'href="([^"]+)"', html_content)
                        exe_links = [h for h in hrefs if h.lower().endswith((".exe", ".msi"))]
                        if exe_links:
                            exe_url = next((h for h in exe_links if "64" in h), exe_links[0])
                            if not exe_url.startswith("http"):
                                parsed_orig = urllib.parse.urlparse(known["url"])
                                if exe_url.startswith("//"):
                                    exe_url = "https:" + exe_url
                                elif exe_url.startswith("/"):
                                    exe_url = parsed_orig.scheme + "://" + parsed_orig.netloc + exe_url
                            res2 = self._download_file(exe_url)
                            if res2.startswith("Archivo descargado:"):
                                lines2 = res2.splitlines()
                                path2 = lines2[1].strip() if len(lines2) >= 2 else ""
                                if path2 and os.path.exists(path2) and os.path.splitext(path2)[1].lower() in (".exe", ".msi"):
                                    exec_result = self._execute_file(path2)
                                    return (f"Listo. Descargué e instalé {known['name']}.\n\n"
                                            f"Archivo: {os.path.basename(path2)}\n"
                                            f"Ruta: {path2}\n\n"
                                            f"{exec_result}")
                    except Exception:
                        pass
            # If direct known URL failed, try the page
            self._update_progress(f"Buscando instalador en la web de {known['name']}...")
            if known.get("page"):
                page_result = self._download_file(known["page"])
                if page_result.startswith("Archivo descargado:"):
                    lines = page_result.splitlines()
                    path = lines[1].strip() if len(lines) >= 2 else ""
                    if path and os.path.exists(path):
                        try:
                            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                                html_content = f.read()
                            hrefs = re.findall(r'href="([^"]+)"', html_content)
                            exe_links = [h for h in hrefs if h.lower().endswith((".exe", ".msi"))]
                            if exe_links:
                                exe_url = next((h for h in exe_links if "64" in h), exe_links[0])
                                if not exe_url.startswith("http"):
                                    parsed_orig = urllib.parse.urlparse(known["page"])
                                    if exe_url.startswith("//"):
                                        exe_url = "https:" + exe_url
                                    elif exe_url.startswith("/"):
                                        exe_url = parsed_orig.scheme + "://" + parsed_orig.netloc + exe_url
                                res3 = self._download_file(exe_url)
                                if res3.startswith("Archivo descargado:"):
                                    lines3 = res3.splitlines()
                                    path3 = lines3[1].strip() if len(lines3) >= 2 else ""
                                    if path3 and os.path.exists(path3) and os.path.splitext(path3)[1].lower() in (".exe", ".msi"):
                                        exec_result = self._execute_file(path3)
                                        return (f"Listo. Descargué e instalé {known['name']}.\n\n"
                                                f"Archivo: {os.path.basename(path3)}\n"
                                                f"Ruta: {path3}\n\n"
                                                f"{exec_result}")
                        except Exception:
                            pass

        # Try winget
        self._update_progress(f"Buscando '{app_name}' con winget...")
        winget_result = self._install_with_winget(app_name)
        if winget_result and winget_result.startswith("Listo."):
            return winget_result

        # Web search fallback
        self._update_progress(f"Buscando '{app_name}' en internet...")
        search_query = f"{app_name} download windows"
        results = self._search_files_online(search_query, max_results=10)
        if not results:
            search_query = f"{app_name} descargar"
            results = self._search_files_online(search_query, max_results=10)
        if not results:
            return f"No encontré descargas para '{app_name}' en internet."

        # 2. Score URLs
        trusted_domains = ["github.com", "sourceforge.net", "microsoft.com", "apps.microsoft.com",
                           "code.visualstudio.com", "obsidian.md", "notepad-plus-plus.org",
                           "videolan.org", "win-rar.com", "rarlab.com", "7-zip.org", "ninite.com"]
        app_lower = app_name.lower().replace(" ", "")
        scored = []
        for item in results:
            url = item["url"]
            score = 0
            url_lower = url.lower()
            # Prefer direct installers
            if url_lower.endswith(".exe"):
                score += 20
            elif url_lower.endswith(".msi"):
                score += 15
            elif url_lower.endswith(".zip"):
                score += 5
            # Trusted domain
            if any(td in url_lower for td in trusted_domains):
                score += 10
            # HTTPS
            if url_lower.startswith("https"):
                score += 3
            # App name in URL
            if app_lower in url_lower.replace("-", "").replace("_", ""):
                score += 5
            scored.append((score, url, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:3]
        if not top or top[0][0] < 0:
            return f"No encontré links confiables para instalar '{app_name}'."

        # 3. Try download top candidates
        self._update_progress(f"Encontré {len(top)} resultados. Descargando mejor opción...")
        last_error = ""
        for score, url, item in top:
            result = self._download_file(url)
            if result.startswith("Archivo descargado:"):
                lines = result.splitlines()
                path = lines[1].strip() if len(lines) >= 2 else ""
                if path and os.path.exists(path):
                    ext = os.path.splitext(path)[1].lower()
                    if ext not in (".exe", ".msi", ".bat", ".cmd"):
                        try:
                            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                                html_content = f.read()
                            hrefs = re.findall(r'href="([^"]+)"', html_content)
                            exe_links = [h for h in hrefs if h.lower().endswith((".exe", ".msi"))]
                            if exe_links:
                                exe_url = next((h for h in exe_links if "64" in h), exe_links[0])
                                if not exe_url.startswith("http"):
                                    parsed_orig = urllib.parse.urlparse(url)
                                    if exe_url.startswith("//"):
                                        exe_url = parsed_orig.scheme + ":" + exe_url
                                    elif exe_url.startswith("/"):
                                        exe_url = parsed_orig.scheme + "://" + parsed_orig.netloc + exe_url
                                    else:
                                        exe_url = url.rstrip("/") + "/" + exe_url
                                
                                res2 = self._download_file(exe_url)
                                if res2.startswith("Archivo descargado:"):
                                    lines2 = res2.splitlines()
                                    path2 = lines2[1].strip() if len(lines2) >= 2 else ""
                                    if path2 and os.path.exists(path2) and os.path.splitext(path2)[1].lower() in (".exe", ".msi"):
                                        exec_result = self._execute_file(path2)
                                        return (f"Listo. Busqué '{app_name}', encontré el instalador en la web y lo ejecuté.\n\n"
                                                f"Archivo: {os.path.basename(path2)}\n"
                                                f"Ruta: {path2}\n\n"
                                                f"{exec_result}")
                        except Exception:
                            pass
                        last_error = f"Descargué {path}, pero es un archivo {ext} y no encontré un instalador."
                        continue
                    exec_result = self._execute_file(path)
                    return (f"Listo. Busqué '{app_name}', descargué el instalador y lo ejecuté.\n\n"
                            f"Archivo: {os.path.basename(path)}\n"
                            f"Ruta: {path}\n\n"
                            f"{exec_result}")
            last_error = result

        return (f"No pude descargar ni instalar '{app_name}'.\n"
                f"Intenté con {len(top)} links pero ninguno funcionó.\n"
                f"{winget_result + chr(10) if winget_result else ''}"
                f"Último error: {last_error[:300]}")

    # ==============================================================
    # SYSTEM COMMAND HANDLERS
    # ==============================================================

    def _list_processes(self):
        """List running processes using tasklist."""
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=15, creationflags=flags,
            )
            lines = result.stdout.strip().splitlines()
            if not lines:
                return "No pude obtener la lista de procesos."
            # Parse CSV: "name","pid","session","session#","mem"
            output = ["Procesos activos:", "=" * 50]
            for line in lines[:40]:
                parts = line.strip('"').split('","')
                if len(parts) >= 5:
                    name = parts[0]
                    pid = parts[1]
                    mem = parts[4]
                    output.append(f"  PID {pid:>6}  {mem:>10}  {name}")
            if len(lines) > 40:
                output.append(f"  ... y {len(lines) - 40} más")
            output.append(f"\nTotal: {len(lines)} procesos")
            output.append("Usa /matar <PID> para terminar un proceso.")
            return "\n".join(output)
        except subprocess.TimeoutExpired:
            return "La lista de procesos tardó demasiado."
        except Exception as e:
            return f"Error obteniendo procesos: {e}"

    def _kill_process(self, pid):
        """Kill a process by PID using taskkill."""
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True, text=True, timeout=10, creationflags=flags,
            )
            if result.returncode == 0:
                return f"Proceso {pid} terminado correctamente."
            err = result.stderr.strip()
            if "not found" in err.lower():
                return f"No existe un proceso con PID {pid}."
            return f"No pude terminar el proceso {pid}. {err}"
        except Exception as e:
            return f"Error terminando proceso: {e}"

    def _explore_dir(self, ruta):
        """List files and folders in a directory."""
        ruta = os.path.expanduser(ruta.strip().strip('"').strip("'"))
        if not os.path.isdir(ruta):
            return f"La ruta no existe o no es un directorio: {ruta}"
        try:
            items = os.listdir(ruta)
            if not items:
                return f"El directorio está vacío:\n{ruta}"
            folders = []
            files = []
            for name in items:
                full = os.path.join(ruta, name)
                if os.path.isdir(full):
                    folders.append(f"[CARPETA]  {name}")
                else:
                    try:
                        size = os.path.getsize(full)
                        size_str = f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/(1024*1024):.1f}MB"
                    except Exception:
                        size_str = "?KB"
                    modified = datetime.datetime.fromtimestamp(os.path.getmtime(full)).strftime("%d/%m/%Y")
                    files.append(f"  {size_str:>8}  {modified}  {name}")
            output = [f"> {ruta}", f"  {len(folders)} carpetas, {len(files)} archivos", ""]
            if folders:
                output.append("Carpetas:")
                output.extend(folders[:30])
                output.append("")
            if files:
                output.append("Archivos:")
                output.extend(files[:50])
            if len(items) > 80:
                output.append(f"\n... y {len(items) - 80} elementos más")
            return "\n".join(output)
        except PermissionError:
            return f"No tengo permisos para leer: {ruta}"
        except Exception as e:
            return f"Error explorando {ruta}: {e}"

    def _list_installed_apps(self):
        """List installed applications from Windows Registry."""
        apps = []
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hkey, path in reg_paths:
            try:
                key = winreg.OpenKey(hkey, path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        try:
                            name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            if name and name.strip():
                                publisher = ""
                                try:
                                    publisher = winreg.QueryValueEx(subkey, "Publisher")[0]
                                except Exception:
                                    pass
                                entry = name.strip()
                                if publisher:
                                    entry += f" ({publisher})"
                                apps.append(entry)
                        except Exception:
                            pass
                        finally:
                            winreg.CloseKey(subkey)
                    except Exception:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass

        # Deduplicate and sort
        seen = set()
        unique = []
        for a in apps:
            if a.lower() not in seen:
                seen.add(a.lower())
                unique.append(a)
        unique.sort(key=str.lower)

        if not unique:
            return "No encontré aplicaciones instaladas en el registro."

        output = [f"Aplicaciones instaladas ({len(unique)}):", "=" * 50]
        for i, app in enumerate(unique, 1):
            output.append(f"  {i:>3}. {app}")
        return "\n".join(output)

    def _wifi_info(self):
        """Get WiFi network information."""
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            # Get current connection info
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=15, creationflags=flags,
            )
            interfaces = result.stdout.strip()
            if "no existe" in interfaces.lower() or "no está" in interfaces.lower() or not interfaces:
                return "No detecto ninguna interfaz WiFi activa."

            # Get IP info
            ip_result = subprocess.run(
                ["ipconfig"],
                capture_output=True, text=True, timeout=15, creationflags=flags,
            )
            ip_lines = ip_result.stdout.strip()

            output = ["WIFI - Informacion", "=" * 40]
            output.append("")

            # Parse interfaces for useful info
            for line in interfaces.splitlines():
                stripped = line.strip()
                if any(k in stripped for k in ["SSID", "Estado", "Tipo", "Perfil", "Señal", "Autenticación", "Cifrado", "Banda", "Canal"]):
                    output.append(f"  {stripped}")

            output.append("")
            output.append("Informacion IP")
            output.append("")

            # Extract IP from ipconfig
            in_wifi = False
            for line in ip_lines.splitlines():
                stripped = line.strip()
                if "wi-fi" in stripped.lower() or "wireless" in stripped.lower() or "inalámbrica" in stripped.lower():
                    in_wifi = True
                elif in_wifi and stripped.startswith("Dirección IPv4") or in_wifi and "IPv4" in stripped:
                    output.append(f"  {stripped}")
                    in_wifi = False

            # Also show all IPv4 addresses briefly
            output.append("")
            output.append("Redes guardadas:")
            profiles = subprocess.run(
                ["netsh", "wlan", "show", "profiles"],
                capture_output=True, text=True, timeout=10, creationflags=flags,
            )
            profile_count = len([l for l in profiles.stdout.splitlines() if "Perfil de todos" in l or "All User" in l])
            output.append(f"  {profile_count} redes conocidas")
            output.append("\nUsa /wifi pass <nombre> para ver la contraseña de una red.")

            return "\n".join(output)
        except subprocess.TimeoutExpired:
            return "La consulta WiFi tardó demasiado."
        except Exception as e:
            return f"Error obteniendo WiFi: {e}"

    def _bluetooth_info(self):
        """Get Bluetooth device information."""
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            # Use PowerShell to get Bluetooth info
            ps_cmd = (
                "Get-PnpDevice -Class Bluetooth | "
                "Select-Object FriendlyName, Status, Class, DeviceID | "
                "Format-Table -AutoSize | Out-String -Width 200"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15, creationflags=flags,
                encoding="utf-8", errors="replace",
            )
            output = result.stdout.strip()
            if not output or "no" in output.lower() and "bluetooth" in output.lower():
                # Try alternative query
                ps_cmd2 = "Get-PnpDevice | Where-Object {$_.Class -eq 'Bluetooth'} | Format-Table FriendlyName, Status -AutoSize | Out-String -Width 200"
                result2 = subprocess.run(
                    ["powershell", "-Command", ps_cmd2],
                    capture_output=True, text=True, timeout=15, creationflags=flags,
                    encoding="utf-8", errors="replace",
                )
                output = result2.stdout.strip()

            if not output or "no se encontraron" in output.lower() or "no hay" in output.lower():
                return "No detecto dispositivos Bluetooth."
            return "📡 Dispositivos Bluetooth:\n\n" + output
        except Exception as e:
            return f"Error obteniendo Bluetooth: {e}"

    def _shutdown_timer(self, minutos, reboot=False):
        """Schedule a shutdown or reboot after X minutes."""
        segundos = int(minutos) * 60
        accion = "reinicio" if reboot else "apagado"
        verbo = "Reiniciando" if reboot else "Apagando"
        comando = "shutdown"
        params = ["shutdown", "/r", "/t", str(segundos)] if reboot else ["shutdown", "/s", "/t", str(segundos)]
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.run(params, capture_output=True, text=True, timeout=10, creationflags=flags)
            return (f"[{verbo.upper()}] Programado en {minutos} minuto(s).\n"
                    f"Quedan {segundos} segundos.\n"
                    f"Usa /noapagar para cancelar.")
        except Exception as e:
            return f"Error programando {accion}: {e}"

    def _cancel_shutdown(self):
        """Cancel a scheduled shutdown."""
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                ["shutdown", "/a"],
                capture_output=True, text=True, timeout=10, creationflags=flags,
            )
            if result.returncode == 0:
                return "Apagado cancelado correctamente."
            return "No hay ningún apagado programado para cancelar."
        except Exception as e:
            return f"Error cancelando apagado: {e}"

    def _save_note(self, content):
        """Save a quick note to the notes file."""
        notes_dir = os.path.join(os.path.expanduser("~"), ".claudy", "notas")
        os.makedirs(notes_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        if not content:
            # Interactive mode - open the notes directory
            os.startfile(notes_dir)
            return f"Abrí la carpeta de notas:\n{notes_dir}"
        safe_title = re.sub(r'[^\w\s-]', '', title_part).strip() or "nota"
        safe_title = safe_title[:40]
        fname = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_title}.txt"
        fpath = os.path.join(notes_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(f"{content}\n\n-- Guardado el {ts}")
        return f"Nota guardada:\n{fpath}"

    def _read_notes(self):
        """Read saved notes."""
        notes_dir = os.path.join(os.path.expanduser("~"), ".claudy", "notas")
        if not os.path.isdir(notes_dir):
            return "No tienes notas guardadas todavía."
        try:
            files = sorted(os.listdir(notes_dir), reverse=True)[:20]
            if not files:
                return "No tienes notas guardadas todavía."
            output = ["Tus notas:", "=" * 40]
            for fname in files:
                fpath = os.path.join(notes_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        preview = f.read(100).strip()
                except Exception:
                    preview = ""
                modified = datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%d/%m %H:%M")
                output.append(f"\n  [{fname}]")
                output.append(f"     {modified} — {preview[:80]}{'...' if len(preview) > 80 else ''}")
            output.append(f"\n{len(files)} nota(s). Carpeta: {notes_dir}")
            return "\n".join(output)
        except Exception as e:
            return f"Error leyendo notas: {e}"

    def _clipboard_read(self):
        """Read text from clipboard using PowerShell."""
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=10, creationflags=flags,
                encoding="utf-8", errors="replace",
            )
            text = result.stdout.strip()
            if not text:
                return "El portapapeles está vacío."
            return f"Portapapeles:\n\n{text[:2000]}"
        except Exception as e:
            return f"Error leyendo portapapeles: {e}"

    def _clipboard_copy(self, text):
        """Copy text to clipboard using PowerShell."""
        if not text:
            return "No hay nada que copiar."
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            escaped = text.replace("'", "''")
            subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{escaped}'"],
                capture_output=True, text=True, timeout=10, creationflags=flags,
            )
            preview = text[:100]
            return f"Copiado al portapapeles:\n\n{preview}{'...' if len(text) > 100 else ''}"
        except Exception as e:
            return f"Error copiando al portapapeles: {e}"

    def _toggle_always_on_top(self, enable):
        """Toggle always-on-top mode for the window."""
        try:
            self.attributes('-topmost', enable)
            estado = "activado" if enable else "desactivado"
            return f"Modo siempre visible {estado}."
        except Exception as e:
            return f"Error cambiando modo visible: {e}"

    def _show_help(self):
        """Show all available commands."""
        help_text = """CLAUDY - Comandos Disponibles

ARCHIVOS Y NAVEGACION
  /buscar_archivo <nombre>    Buscar archivos en tu PC
  /explorar <ruta>            Explorar carpetas
  /leer <ruta>                Leer contenido de un archivo
  /write <ruta> | <contenido> Crear o sobrescribir archivo
  /append <ruta> | <contenido> Agregar texto a archivo
  /replace <ruta> | <buscar> | <reemplazo> Editar texto en archivo
  /mkdir <ruta>                Crear carpeta
  /ejecutar <ruta>            Ejecutar/abrir un archivo
  /descargar <url>            Descargar archivos

SISTEMA
  /procesos                   Ver procesos activos
  /matar <PID>               Terminar un proceso
  /apps                       Ver apps instaladas
  /apagar <min>               Apagar en X minutos
  /reiniciar <min>            Reiniciar en X minutos
  /noapagar                   Cancelar apagado

WIFI Y RED
  /wifi                       Informacion WiFi
  /bluetooth                  Dispositivos Bluetooth

NOTAS Y CLIPBOARD
  /notas                      Abrir/bloc de notas
  /portapapeles               Leer portapapeles
  /copia <texto>              Copiar al portapapeles

INTERFAZ
  /envivo                     Modo siempre visible
  /tema                       Cambiar tema
  /captura                    Tomar screenshot
  /voz                        Input por voz
  /atajos                     Mostrar esta ayuda

CONSULTAS
  /buscar <tema>              Buscar en internet
  /clima <ciudad>             Clima y temperatura
  /traducir <texto>           Traducir texto
  /calc <expr>                Calcular expresion
  /noticias                   Ultimas noticias
  /recordar <min> <msg>       Recordatorio
  /cron expr <horario>         Generar expresion cron
  /cron cada <n> min <msg>     Programar tarea recurrente
  /cron los <dia> a las <h>    Programar tarea semanal
  /cron editar <num> ...       Modificar una tarea existente
  /cron on|off <num>           Activar / pausar una tarea

MAS
  /instalar <app>             Instalar aplicacion
  /jugar <juego>              Jugar ROMs/NES/SNES
  /musica <accion>            Control de musica
  /export                     Exportar conversacion
  /search                     Buscar en historial

FASE 4 - AVANZADO
  /delegar <tarea>            Lanzar subagente
  /resultado                  Ver resultado de subagente
  /kanban add <titulo>        Crear tarea kanban
  /kanban move <id> <status>  Mover tarea (backlog/todo/in_progress/done)
  /kanban                     Ver tablero
  /kanban delete <id>         Eliminar tarea
  /webhook add <nombre> <url> Registrar webhook
  /webhook trigger            Disparar todos
  /webhooks                   Listar webhooks
  /worktree add <nombre>      Crear git worktree
  /worktrees                  Listar worktrees
  /worktree remove <nombre>   Eliminar worktree

Tambien puedes hablar naturalmente:
  "dame las apps instaladas"
  "mata el proceso 1234"
  "que hay en Descargas"
  "apaga en 10 minutos"
  "toma nota: comprar leche"
  "ponte al frente"
  "copia esto al portapapeles"
"""
        return help_text

    # ==============================================================
    # GATEWAY HTTP SERVER + WEBCHAT
    # ==============================================================

    def _start_gateway(self):
        """Start HTTP API server. Configurable bind and auth."""
        if self._gateway_server:
            return
        # Read gateway config
        try:
            config = self.load_claudy_config()
            gw = config.get("gateway", {})
            if gw.get("public", False):
                self._gateway_bind_ip = "0.0.0.0"
            self._gateway_auth_token = gw.get("authToken", None)
            port = gw.get("port", 8720)
            if port:
                self._gateway_port = port
        except Exception:
            pass
        import http.server

        pet = self

        class GatewayHandler(http.server.BaseHTTPRequestHandler):
            def _check_gateway_auth(_self):
                """Check auth token if configured. Returns True if authorized."""
                if not pet._gateway_auth_token:
                    return True
                auth = _self.headers.get("Authorization", "")
                return auth == f"Bearer {pet._gateway_auth_token}"

            def do_POST(_self):
                if not _self._check_gateway_auth():
                    _self.send_response(401)
                    _self.end_headers()
                    _self.wfile.write(json.dumps({"error": "Unauthorized"}).encode("utf-8"))
                    return
                try:
                    length = int(_self.headers.get("Content-Length", 0))
                    body = _self.rfile.read(length).decode("utf-8")
                    data = json.loads(body)
                    # OpenAI-compatible endpoint
                    if _self.path == "/v1/chat/completions":
                        msgs = data.get("messages", [])
                        user_msgs = [m for m in msgs if m.get("role") == "user"]
                        if not user_msgs:
                            raise ValueError("No user message in messages[]")
                        last_user = user_msgs[-1].get("content", "")
                        if isinstance(last_user, list):
                            last_user = " ".join(p.get("text", "") for p in last_user if isinstance(p, dict))
                        handled, result = pet._try_handle_skill_action(last_user)
                        if not handled:
                            result = pet.send_quick_message(last_user)
                        result = pet._process_embedded_commands(result)
                        result = pet._strip_markdown(result)
                        model_name = data.get("model", "claudy")
                        cmpl_id = f"chatcmpl-{int(time.time())}"
                        created = int(time.time())

                        # Streaming SSE (lo que Open WebUI / LobeChat esperan con stream:true)
                        if data.get("stream"):
                            _self.send_response(200)
                            _self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                            _self.send_header("Cache-Control", "no-cache")
                            _self.send_header("Connection", "keep-alive")
                            _self.send_header("Access-Control-Allow-Origin", "*")
                            _self.end_headers()

                            def _sse(payload):
                                _self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
                                _self.wfile.flush()

                            def _chunk(delta, finish=None):
                                return {
                                    "id": cmpl_id, "object": "chat.completion.chunk",
                                    "created": created, "model": model_name,
                                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                                }
                            try:
                                _sse(_chunk({"role": "assistant"}))
                                # trocea por palabras para un streaming fluido y fiable
                                tokens = re.findall(r"\S+\s*", result) or ([result] if result else [])
                                for tk in tokens:
                                    _sse(_chunk({"content": tk}))
                                _sse(_chunk({}, finish="stop"))
                                _self.wfile.write(b"data: [DONE]\n\n")
                                _self.wfile.flush()
                            except (BrokenPipeError, ConnectionResetError):
                                pass
                            return

                        resp = {
                            "id": cmpl_id,
                            "object": "chat.completion",
                            "created": created,
                            "model": model_name,
                            "choices": [{
                                "index": 0,
                                "message": {"role": "assistant", "content": result},
                                "finish_reason": "stop",
                            }],
                            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        }
                        _self.send_response(200)
                        _self.send_header("Content-Type", "application/json")
                        _self.send_header("Access-Control-Allow-Origin", "*")
                        _self.end_headers()
                        _self.wfile.write(json.dumps(resp).encode("utf-8"))
                        return
                    # Native Claudy endpoint
                    msg = data.get("message", "")
                    handled, result = pet._try_handle_skill_action(msg)
                    if not handled:
                        result = pet.send_quick_message(msg)
                    result = pet._process_embedded_commands(result)
                    result = pet._strip_markdown(result)
                    _self.send_response(200)
                    _self.send_header("Content-Type", "application/json")
                    _self.send_header("Access-Control-Allow-Origin", "*")
                    _self.end_headers()
                    _self.wfile.write(json.dumps({"response": result}).encode("utf-8"))
                except Exception as e:
                    _self.send_response(500)
                    _self.send_header("Access-Control-Allow-Origin", "*")
                    _self.end_headers()
                    _self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

            def do_OPTIONS(_self):
                _self.send_response(200)
                _self.send_header("Access-Control-Allow-Origin", "*")
                _self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
                _self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                _self.end_headers()

            def do_GET(_self):
                if _self.path == "/v1/models":
                    _self.send_response(200)
                    _self.send_header("Content-Type", "application/json")
                    _self.send_header("Access-Control-Allow-Origin", "*")
                    _self.end_headers()
                    _self.wfile.write(json.dumps({
                        "object": "list",
                        "data": [{"id": "claudy", "object": "model", "created": int(time.time()), "owned_by": "claudy"}],
                    }).encode("utf-8"))
                    return
                if _self.path == "/api/health":
                    _self.send_response(200)
                    _self.send_header("Content-Type", "application/json")
                    _self.send_header("Access-Control-Allow-Origin", "*")
                    _self.end_headers()
                    _self.wfile.write(json.dumps({"status": "ok", "gateway": "Claudy", "version": "3.0"}).encode("utf-8"))
                    return
                if _self.path == "/" or _self.path == "":
                    _self.send_response(200)
                    _self.send_header("Content-Type", "text/html; charset=utf-8")
                    _self.end_headers()
                    _self.wfile.write(WEBCHAT_HTML.encode("utf-8"))
                else:
                    _self.send_response(200)
                    _self.send_header("Content-Type", "application/json")
                    _self.send_header("Access-Control-Allow-Origin", "*")
                    _self.end_headers()
                    _self.wfile.write(json.dumps({"status": "ok", "endpoint": "/api"}).encode("utf-8"))

            def log_message(_self, *args):
                pass

        def run():
            try:
                bind_ip = pet._gateway_bind_ip
                port = pet._gateway_port
                server = http.server.HTTPServer((bind_ip, port), GatewayHandler)
                pet._gateway_server = server
                print(f"[Gateway] Listening on {bind_ip}:{port}")
                server.serve_forever()
            except Exception as e:
                print(f"[Gateway] Error: {e}")

        threading.Thread(target=run, daemon=True, name="gateway-server").start()

    def _start_voice_listen(self):
        """Start continuous voice listening with wake word 'Claudy'."""
        if self._voice_listening:
            return "Ya estoy escuchando. Di 'Claudy' para activarme."
        self._voice_listening = True
        self._voice_active = False
        self._speak_text("Modo escucha activado. Di Claudy para activarme.")

        def voice_loop():
            import speech_recognition as sr
            r = sr.Recognizer()
            try:
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=1)
                    while self._voice_listening:
                        try:
                            audio = r.listen(source, timeout=5, phrase_time_limit=5)
                            text = r.recognize_google(audio, language="es-ES").lower()
                            if not self._voice_active:
                                if any(w in text for w in ("claudy", "claudi", "claudio", "cloudy")):
                                    self._voice_active = True
                                    self._speak_text("Dime")
                                    time.sleep(0.3)
                            else:
                                self._voice_active = False
                                self.after(0, lambda t=text: self._process_voice_command(t))
                        except sr.WaitTimeoutError:
                            pass
                        except sr.UnknownValueError:
                            pass
                        except Exception:
                            time.sleep(1)
            except Exception:
                self._voice_listening = False

        threading.Thread(target=voice_loop, daemon=True, name="voice-listener").start()
        return "Modo escucha activado. Di 'Claudy' para activarme y luego tu pregunta.\nPara detener: /voz stop"

    def _stop_voice_listen(self):
        self._voice_listening = False
        self._voice_active = False
        return "Modo escucha desactivado."

    def _process_voice_command(self, text):
        """Process a voice command through the normal pipeline."""
        self.show_chat_bubble(text)
        try:
            handled, result = self._try_handle_skill_action(text)
            if not handled:
                result = self.send_quick_message(text)
            result = self._strip_markdown(result)
            # Show and speak
            self._set_response_text(result)
            self._speak_text(result[:500])
        except Exception:
            pass

    def _speak_text(self, text):
        """Speak text using Windows SAPI (non-blocking)."""
        text = text[:500].replace('"', "'")
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            ps_script = f'Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate=0; $s.SelectVoice("Microsoft Sabina Desktop"); $s.Speak("{text}")'
            subprocess.Popen(["powershell", "-Command", ps_script], creationflags=flags)
        except Exception:
            pass

    def _voice_input(self):
        return self._start_voice_listen()

    def _start_ptt_recording(self, status):
        self._ptt_recording = True
        self._ptt_frames = []
        self.state = "thinking"
        status.configure(text="🎙️ GRABANDO... Habla ahora", fg="#2fe6c8")
        
        # Wake notification
        self._speak_text("Dime")

        def record_worker():
            try:
                import speech_recognition as sr
                import threading
                r = sr.Recognizer()
                mic = sr.Microphone()
                with mic as source:
                    r.adjust_for_ambient_noise(source, duration=0.2)
                    while self._ptt_recording:
                        try:
                            # Read raw audio data from PyAudio stream
                            data = source.stream.read(source.CHUNK)
                            self._ptt_frames.append(data)
                        except Exception:
                            time.sleep(0.005)
                
                if not self._ptt_frames:
                    return
                
                self.after(0, lambda: status.configure(text="✨ Transcribiendo voz...", fg=THEME["accent"]))
                raw_data = b"".join(self._ptt_frames)
                audio = sr.AudioData(raw_data, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
                
                try:
                    text = r.recognize_google(audio, language="es-ES")
                    if text.strip():
                        self.after(0, lambda t=text: self._process_ptt_response(t, status))
                    else:
                        self.after(0, lambda: status.configure(text="Audio vacío", fg="#ff6b6b"))
                except sr.UnknownValueError:
                    self.after(0, lambda: status.configure(text="No logré entender el audio", fg="#ff6b6b"))
                except Exception as e:
                    self.after(0, lambda e_str=str(e): status.configure(text=f"Error: {e_str}", fg="#ff6b6b"))
            except Exception as e:
                print(f"[PTT] Microphone/Recording Error: {e}")
                self.after(0, lambda: status.configure(text="Error de Micrófono", fg="#ff6b6b"))

        threading.Thread(target=record_worker, daemon=True, name="ptt-worker").start()

    def _stop_ptt_recording(self):
        self._ptt_recording = False
        self.state = "idle"

    def _process_ptt_response(self, text, status):
        """Process transcribed voice input and speak the output."""
        self.show_chat_bubble(text)
        status.configure(text="Pensando...", fg=THEME["accent"])
        
        def run_pipeline():
            try:
                handled, result = self._try_handle_skill_action(text)
                if not handled:
                    result = self.send_quick_message(text)
                result = self._strip_markdown(result)
                
                # Render visual and output TTS
                self.after(0, lambda r=result: self._set_response_text(r))
                self.after(0, lambda r=result: status.configure(text="Listo", fg=THEME["accent"]))
                
                # Speak response aloud
                self._speak_text(result[:500])
            except Exception as e:
                self.after(0, lambda: status.configure(text="Error al procesar", fg="#ff6b6b"))
                
        import threading
        threading.Thread(target=run_pipeline, daemon=True).start()

    def send_quick_message(self, prompt, _skip_skill_action=False, timeout=90, on_delta=None, max_tokens=None):
        # Check for local skill commands first
        if not _skip_skill_action:
            handled, result = self._try_handle_skill_action(prompt)
            if handled:
                self._save_memory("Usuario", prompt)
                self._save_memory("Claudy", result)
                self._fire_hook("on_response", user=prompt, response=result, source="skill")
                try:
                    self.after(0, lambda: self._set_state_briefly("happy", 800))
                except Exception:
                    pass
                if self._voice_enabled:
                    _tts_speak(result)
                return result

        self._save_memory("Usuario", prompt)
        self._fire_hook("on_message", user=prompt)
        config = self.load_claudy_config()
        # Permitir subir el límite de tokens para respuestas largas (p.ej. informes
        # extensos de 4000+ palabras que con el default de 4096 se cortaban a la mitad).
        if max_tokens:
            try:
                config = dict(config)
                config["agent"] = dict(config.get("agent", {}))
                config["agent"]["maxTokens"] = int(max_tokens)
            except Exception:
                pass
        opencode = config["opencode"]
        base_url = opencode.get("baseUrl", "http://127.0.0.1:4096").rstrip("/")
        model = self._current_model or opencode.get("defaultModel", "deepseek-chat")
        # P3-2: Model router - swap to a category-specific model if router enabled
        model = _route_model(prompt, config, model)

        is_local = any(h in base_url for h in ("127.0.0.1", "localhost", "0.0.0.0"))
        context = self._build_memory_context(prompt)
        superpowers = self._get_superpowers()
        base_sys = config["agent"].get(
            "systemPrompt",
            "Eres Claudy, asistente personal de Felipe Castro (jorge.castro@qcorespa.com), "
            "CTO de QCORE SPA (QCORE Group Technologies SPA). "
            "SIEMPRE llama al usuario 'Felipe' — nunca 'usuario', 'tú' genérico ni lo ignores. "
            "Español natural, directo, sin formalidad excesiva. "
            "QCORE SPA tiene estos productos propios: "
            "SmartStudent (plataforma educativa SaaS, Next.js+Firebase+Gemini AI, 21 módulos, puerto 9002, cliente COMBAS), "
            "Roadix (SaaS para talleres automotrices, React+Supabase, 21 módulos, roadix.cl, puerto 5173), "
            "Mission Control (hub operativo central, React+Vite, 17 módulos, puerto 5200), "
            "UnitCore (Clinical Research Management, dashboard clínico, 195 contactos oncológicos), "
            "Campaign Studio (gestión Reels/Carruseles para Meta, React+Remotion), "
            "Point (POS + inventario FEFO para comercios, Python/Flask, cliente Tentación a Granel), "
            "Mi Portafolio (web personal/CV de Jorge Castro, jorgecastros.xyz, fuente en Documents/CV_JorgeCastro_v3.5), "
            "Luxium (monorepo/engine base compartido). "
            "Cuando Felipe pregunte por estos productos, SIEMPRE responde con info de los productos de QCORE SPA, "
            "NUNCA confundas con productos de otras empresas con nombres similares. "
            "Clasifica la pregunta: saludo/definición → 1-3 líneas sin buscar. "
            "Dato actual → busca + da dato. Código → código exacto. "
            "Tarea multi-paso → anuncia plan, ejecuta cada paso. "
            "PROHIBIDO: 'como modelo de IA', preámbulos, markdown innecesario, derivar a otros sitios. "
            "Si no sabes, di 'No sé, Felipe'. Resuelve, no informes."
        )
        local_skills = self._load_installed_skills()
        try:
            from qcore_products import build_company_context
            company_ctx = build_company_context() + "\n\n"
        except Exception:
            company_ctx = ""
        enhanced_sys = superpowers + local_skills + company_ctx + base_sys
        # Auto-detect product mention — robust matching with variations
        _detected_product = None
        try:
            from qcore_products import build_context_prompt, PRODUCT_CONTEXTS
            plow = prompt.lower().replace("-", " ").replace("_", " ")
            # Map of aliases → canonical product name
            _product_aliases = {
                "smartstudent": "SmartStudent",
                "smart student": "SmartStudent",
                "roadix": "Roadix",
                "luxium": "Luxium",
                "unitcore": "UnitCore",
                "unit core": "UnitCore",
                "campaign studio": "Campaign Studio",
                "campaignstudio": "Campaign Studio",
                "mission control": "Mission Control",
                "missioncontrol": "Mission Control",
                "point": "Point",
                "mi portafolio": "Mi Portafolio",
                "portafolio": "Mi Portafolio",
                "portfolio": "Mi Portafolio",
            }
            for alias, canonical in _product_aliases.items():
                if alias in plow:
                    _detected_product = canonical
                    self._active_product = canonical
                    self._product_context = build_context_prompt(canonical)
                    break
        except Exception:
            pass
        # Inject active QCORE product context (detailed) into system prompt
        product_ctx = getattr(self, "_product_context", "")
        if product_ctx:
            enhanced_sys += "\n\n" + product_ctx
        # Also inject into user prompt so the AI MUST use this info
        if _detected_product and product_ctx:
            prompt = f"[IMPORTANTE: Responde usando SOLO la información del producto {_detected_product} de QCORE SPA que tienes en tu contexto. NO busques información externa ni confundas con otros productos de otras empresas.]\n\n{prompt}"

        if is_local:
            try:
                self.ensure_opencode_server(base_url, config)
                if not self.quick_session_id:
                    created = self.request_json(
                        f"{base_url}/session", {"title": "Claudy Desktop"}, config, timeout=12,
                    )
                    self.quick_session_id = created.get("id")
                    if not self.quick_session_id:
                        raise RuntimeError("el oraculo no abrio la puerta")

                provider_id, _, model_id = model.partition("/")
                full_prompt = context + f"Usuario: {prompt}\nClaudy:" if context else prompt
                payload = {
                    "model": {"providerID": provider_id, "modelID": model_id or provider_id},
                    "system": enhanced_sys,
                    "tools": {
                        "bash": True, "read": True, "glob": True, "grep": True, "webfetch": True,
                        "edit": False, "task": False, "todowrite": False,
                        "websearch": True, "codesearch": True, "lsp": False, "skill": False,
                    },
                    "parts": [{"type": "text", "text": full_prompt}],
                }
                endpoint = f"{base_url}/session/{self.quick_session_id}/message"
                response = self.request_json(endpoint, payload, config, timeout=timeout)
                if response.get("info", {}).get("error"):
                    error = response["info"]["error"]
                    raise RuntimeError(error.get("data", {}).get("message") or error.get("name") or "el oraculo se quedo dormido")
            except Exception as local_err:
                self._debug_log("LOCAL OPENCODE FAILED, FALLING BACK TO REMOTE", str(local_err))
                # Auto-fallback to remote credentials if local server times out/fails
                response = self._call_remote_provider(model, enhanced_sys, context, prompt, config, on_delta=on_delta, timeout=timeout)
        else:
            # Multi-provider remote path
            response = self._call_remote_provider(model, enhanced_sys, context, prompt, config, on_delta=on_delta, timeout=timeout)

        # Robust text extraction: OpenCode native format, OpenAI format, or direct text.
        text = ""
        parts = response.get("parts")
        if parts:
            text = "\n".join(part.get("text", "") for part in parts if part.get("type") == "text").strip()
        if not text:
            choices = response.get("choices")
            if choices and isinstance(choices, list):
                msg = choices[0].get("message", {}) if choices else {}
                text = msg.get("content", "").strip()
        if not text:
            # Anthropic format
            content_list = response.get("content", [])
            if isinstance(content_list, list):
                text = "\n".join(b.get("text", "") for b in content_list if b.get("type") == "text").strip()
        if not text:
            text = response.get("text", "").strip()
        if not text:
            text = response.get("content", "").strip()

        # Dynamic fallback: If local server returned empty response, call remote provider
        if not text and is_local:
            self._debug_log("LOCAL OPENCODE RETURNED EMPTY TEXT, FALLING BACK TO REMOTE")
            try:
                response = self._call_remote_provider(model, enhanced_sys, context, prompt, config, timeout=timeout)
                parts = response.get("parts")
                if parts:
                    text = "\n".join(part.get("text", "") for part in parts if part.get("type") == "text").strip()
                if not text:
                    choices = response.get("choices")
                    if choices and isinstance(choices, list):
                        msg = choices[0].get("message", {}) if choices else {}
                        text = msg.get("content", "").strip()
                if not text:
                    content_list = response.get("content", [])
                    if isinstance(content_list, list):
                        text = "\n".join(b.get("text", "") for b in content_list if b.get("type") == "text").strip()
                if not text:
                    text = response.get("text", "").strip()
                if not text:
                    text = response.get("content", "").strip()
            except Exception as remote_err:
                text = ""
                self._debug_log("REMOTE FALLBACK ALSO FAILED", str(remote_err))

        # Ultimate fallback: Pollinations API (free, no API key needed)
        if not text or text.startswith("Error "):
            try:
                poll_payload = {
                    "model": "openai",
                    "messages": [
                        {"role": "system", "content": enhanced_sys[:3000]},
                        {"role": "user", "content": (context + prompt)[:12000] if context else prompt[:12000]},
                    ],
                    "max_tokens": 2000,
                }
                req = urllib.request.Request(
                    "https://text.pollinations.ai/openai",
                    data=json.dumps(poll_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "Claudy/1.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    poll_data = json.loads(resp.read().decode("utf-8"))
                choices = poll_data.get("choices") or []
                if choices:
                    msg = choices[0].get("message") or {}
                    poll_text = msg.get("content", "").strip()
                    if poll_text:
                        text = poll_text
                if not text:
                    text = poll_data.get("response", "").strip()
            except Exception as poll_err:
                self._debug_log("POLLINATIONS FALLBACK ALSO FAILED", str(poll_err))

        answer = text or "El oraculo me dejo en visto..."
        self._save_memory("Claudy", answer)
        self._fire_hook("on_response", user=prompt, response=answer, source="llm")
        # Bucle de auto-mejora: registra qué skills fueron relevantes y, al cruzar
        # el umbral, dispara un refinamiento solo (en background, sin bloquear).
        if not self._refining_skill:
            try:
                threading.Thread(
                    target=self._record_skill_usage, args=(prompt,), daemon=True,
                    name="skill-usage").start()
            except Exception:
                pass
        # Animacion: feliz brevemente, luego talking si hay voz, sino idle
        try:
            if self._voice_enabled:
                self.after(0, lambda: self._set_state_briefly("happy", 600))
                self.after(700, lambda: self._set_state_briefly("talking", max(1500, min(8000, len(answer) * 60))))
            else:
                self.after(0, lambda: self._set_state_briefly("happy", 1200))
        except Exception:
            pass
        if self._voice_enabled:
            _tts_speak(answer)
        return answer

    def _detect_provider(self, model):
        """Detect provider and return (provider_key, api_url, is_anthropic, is_openai_compat)."""
        m = model.lower()
        if "claude" in m or "anthropic" in m:
            return ("anthropic", "https://api.anthropic.com/v1/messages", True, False)
        if "deepseek" in m:
            return ("deepseek", "https://api.deepseek.com/v1/chat/completions", False, True)
        if "gemini" in m or "google" in m:
            return ("google", "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent", False, False)
        # Default: OpenAI or OpenAI-compatible
        return ("openai", "https://api.openai.com/v1/chat/completions", False, True)

    def _get_provider_keys(self, config, provider):
        """Get API keys for a provider with credential pooling support."""
        provider_cfg = config.get("providers", {}).get(provider, {})
        keys = provider_cfg.get("keys", [])
        if not keys:
            single = provider_cfg.get("key", "") or config.get(provider, {}).get("apiKey", "")
            if single:
                keys = [single]
        if not keys:
            # Fallback to opencode.apiKey (covers DeepSeek, etc.)
            opencode_key = config.get("opencode", {}).get("apiKey", "")
            if opencode_key:
                keys = [opencode_key]
        if not keys:
            env_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "google": "GOOGLE_API_KEY",
            }
            env_key = os.environ.get(env_map.get(provider, ""), "")
            if env_key:
                keys = [env_key]
        return keys

    def _call_remote_provider(self, model, system_prompt, context, user_prompt, config, on_delta=None, max_tokens_override=None, timeout=90):
        """Call remote AI provider with credential pooling, retry, and inter-provider fallback."""
        last_error = None

        # Build provider chain: primary model first, then fallback list from config.
        primary = (model, *self._detect_provider(model))
        chain = [primary]
        fallbacks = config.get("providers", {}).get("fallback", [])
        if isinstance(fallbacks, list):
            for fb_model in fallbacks:
                if not fb_model or fb_model == model:
                    continue
                chain.append((fb_model, *self._detect_provider(fb_model)))

        for fb_model, provider, api_url, is_anthropic, is_openai_compat in chain:
            keys = self._get_provider_keys(config, provider)
            if not keys:
                last_error = RuntimeError(f"No API key configured for {provider}")
                continue
            # Strip provider prefix for the actual API call
            actual_model = fb_model.partition("/")[2] if "/" in fb_model else fb_model
            for key in keys:
                try:
                    return self._call_provider_api(provider, api_url, is_anthropic, is_openai_compat, actual_model, system_prompt, context, user_prompt, key, config, on_delta=on_delta, timeout=timeout)
                except Exception as e:
                    last_error = e
                    continue

        raise RuntimeError(f"All providers/keys exhausted. Last error: {last_error}")

    def _call_provider_api(self, provider, api_url, is_anthropic, is_openai_compat, model, system_prompt, context, user_prompt, key, config, on_delta=None, timeout=90):
        """Make a single API call to a provider."""
        if is_anthropic:
            return self._call_anthropic(api_url, model, system_prompt, context, user_prompt, key, config, timeout=timeout)
        elif is_openai_compat:
            return self._call_openai_compat(api_url, model, system_prompt, context, user_prompt, key, config, on_delta=on_delta, timeout=timeout)
        else:
            return self._call_generic(api_url, model, system_prompt, context, user_prompt, key, provider, timeout=timeout)

    def _anthropic_tool_schemas(self):
        """Convert OpenAI-style registry to Anthropic tool format."""
        out = []
        for name, info in self.TOOL_REGISTRY.items():
            fn = info["schema"]["function"]
            out.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return out

    def _execute_tool_calls_and_followup(self, tool_calls, base_payload, headers, endpoint, is_anthropic):
        """Run each tool call and POST a follow-up with the tool results.
        Returns the final response JSON."""
        import urllib.request as r
        if is_anthropic:
            tool_result_blocks = []
            assistant_blocks = []
            for tc in tool_calls:
                tid = tc.get("id")
                name = tc.get("name")
                inp = tc.get("input", {}) or {}
                info = self.TOOL_REGISTRY.get(name)
                try:
                    result = info["handler"](self, **inp) if info else f"Tool '{name}' not found."
                except Exception as e:
                    result = f"Error: {e}"
                assistant_blocks.append({"type": "tool_use", "id": tid, "name": name, "input": inp})
                tool_result_blocks.append({"type": "tool_result", "tool_use_id": tid, "content": str(result)[:4000]})
            messages = list(base_payload.get("messages", []))
            messages.append({"role": "assistant", "content": assistant_blocks})
            messages.append({"role": "user", "content": tool_result_blocks})
            payload = dict(base_payload)
            payload["messages"] = messages
            req = r.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with r.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())
        else:
            messages = list(base_payload.get("messages", []))
            messages.append({"role": "assistant", "tool_calls": tool_calls, "content": None})
            for tc in tool_calls:
                tid = tc.get("id")
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments", "{}") or "{}")
                except Exception:
                    args = {}
                info = self.TOOL_REGISTRY.get(name)
                try:
                    result = info["handler"](self, **args) if info else f"Tool '{name}' not found."
                except Exception as e:
                    result = f"Error: {e}"
                messages.append({"role": "tool", "tool_call_id": tid, "content": str(result)[:4000]})
            payload = dict(base_payload)
            payload["messages"] = messages
            payload.pop("tools", None)  # avoid recursive tool use
            req = r.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with r.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())

    def _stream_openai_compat(self, endpoint, payload, headers, on_delta):
        """SSE streaming for OpenAI-compatible APIs. Calls on_delta(piece) for
        each token and returns a synthesized response dict with the full text."""
        import urllib.request as r
        spayload = dict(payload)
        spayload["stream"] = True
        req = r.Request(endpoint, data=json.dumps(spayload).encode("utf-8"), headers=headers)
        full = []
        with r.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    obj = json.loads(chunk)
                    piece = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                except Exception:
                    piece = None
                if piece:
                    full.append(piece)
                    try:
                        on_delta(piece)
                    except Exception:
                        pass
        text = "".join(full)
        if not text:
            raise RuntimeError("empty stream")
        return {"choices": [{"message": {"role": "assistant", "content": text}}]}

    def _call_openai_compat(self, api_url, model, system_prompt, context, user_prompt, key, config=None, on_delta=None, timeout=90):
        """Call OpenAI-compatible API."""
        endpoint = api_url
        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": user_prompt})
        max_tokens = (config or {}).get("agent", {}).get("maxTokens", 4096)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }
        # P2-2: native function calling
        tools_enabled = bool((config or {}).get("tools", {}).get("enableFunctionCalling", False))
        if tools_enabled and self.TOOL_REGISTRY:
            payload["tools"] = self._get_tool_schemas()
            payload["tool_choice"] = "auto"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }
        # Streaming path: only when a delta callback is provided and tools are off.
        if on_delta is not None and not (tools_enabled and self.TOOL_REGISTRY):
            try:
                return self._stream_openai_compat(endpoint, payload, headers, on_delta)
            except Exception:
                pass  # fall back to a normal blocking request on any streaming error
        import urllib.request as r
        req = r.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with r.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        if tools_enabled:
            choices = data.get("choices") or []
            if choices:
                msg = choices[0].get("message", {})
                tcs = msg.get("tool_calls") or []
                if tcs:
                    return self._execute_tool_calls_and_followup(tcs, payload, headers, endpoint, is_anthropic=False)
        return data

    def _call_anthropic(self, api_url, model, system_prompt, context, user_prompt, key, config=None, timeout=90):
        """Call Anthropic Messages API with prompt caching."""
        cache_control = {"type": "ephemeral"}
        max_tokens = (config or {}).get("agent", {}).get("maxTokens", 4096)
        payload = {
            "model": model,
            "system": [
                {"type": "text", "text": system_prompt, "cache_control": cache_control},
            ],
            "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
            "max_tokens": max_tokens,
        }
        if context:
            payload["system"].append({"type": "text", "text": context, "cache_control": cache_control})
        tools_enabled = bool((config or {}).get("tools", {}).get("enableFunctionCalling", False))
        if tools_enabled and self.TOOL_REGISTRY:
            payload["tools"] = self._anthropic_tool_schemas()
        headers = {
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "prompt-caching-2024-07-31",
        }
        import urllib.request as r
        req = r.Request(api_url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with r.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        if tools_enabled and data.get("stop_reason") == "tool_use":
            tool_uses = [b for b in data.get("content", []) if b.get("type") == "tool_use"]
            if tool_uses:
                return self._execute_tool_calls_and_followup(tool_uses, payload, headers, api_url, is_anthropic=True)
        return data

    def _call_generic(self, api_url, model, system_prompt, context, user_prompt, key, provider, timeout=90):
        """Generic API call for providers like Google."""
        raise RuntimeError(f"Provider {provider} not fully implemented yet. Use OpenAI-compatible providers like DeepSeek or Anthropic.")

    # ==============================================================
    # TELEGRAM BOT
    # ==============================================================

    def _verify_telegram_connection(self):
        """En segundo plano: confirma que el botToken es aceptado por Telegram
        (endpoint getMe). Actualiza self._telegram_connected. No bloquea la UI."""
        ok = False
        try:
            cfg = self.load_claudy_config()  # ya desencripta los secretos
            token = (cfg.get("telegram", {}) or {}).get("botToken", "") or ""
            if token and not token.startswith("enc:"):
                import urllib.request
                url = f"https://api.telegram.org/bot{token}/getMe"
                with urllib.request.urlopen(url, timeout=6) as r:
                    data = json.loads(r.read().decode("utf-8"))
                    ok = bool(data.get("ok"))
        except Exception:
            ok = False
        self._telegram_connected = ok
        self._telegram_last_check = time.time()

    def _start_telegram_if_configured(self):
        """Start the Telegram bot if a token is configured."""
        config = self.load_claudy_config()
        telegram_cfg = config.get("telegram", {})
        token = telegram_cfg.get("botToken", "")
        self._telegram_allowed_users = set(telegram_cfg.get("allowedUsers", []))
        if not token:
            return
        self._telegram_token = token
        self._run_telegram_bot(token)
        # Verificar el estado del token para el indicador de la UI (no bloquea).
        try:
            threading.Thread(target=self._verify_telegram_connection, daemon=True).start()
        except Exception:
            pass

    def _run_telegram_bot(self, token):
        """Launch standalone Telegram bot as a subprocess via the Gateway API."""
        script = os.path.join(SCRIPT_DIR, "bg_telegram_bot.py")
        if not os.path.exists(script):
            print("[TelegramBot] Script not found:", script)
            return
        try:
            bot_log = os.path.join(os.path.expanduser("~"), ".claudy", "telegram_bot.log")
            with open(bot_log, "a", encoding="utf-8") as log:
                log.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] Starting bot...\n")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                [sys.executable, "-u", script],
                creationflags=flags,
                stdout=open(bot_log, "a", encoding="utf-8", buffering=1),
                stderr=open(bot_log, "a", encoding="utf-8", buffering=1),
            )
        except Exception as e:
            print(f"[TelegramBot] Error starting: {e}")

    def _set_telegram_token(self, token):
        """Guarda el botToken en config y lanza el bot al instante. Sin reiniciar Claudy."""
        token = (token or "").strip().strip('"\'')
        if not re.match(r'^\d{6,12}:[A-Za-z0-9_-]{30,}$', token):
            return ("El token no tiene el formato esperado de Telegram.\n"
                    "Debe verse algo así: 1234567890:AAEx...AbC. Pide uno a @BotFather.")
        config_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                config = json.load(f)
        except Exception:
            config = {}
        config.setdefault("telegram", {})["botToken"] = token
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"No pude guardar el token: {e}"
        self._telegram_token = token
        try:
            self._run_telegram_bot(token)
        except Exception as e:
            return f"Token guardado, pero falló al arrancar el bot: {e}"
        try:
            threading.Thread(target=self._verify_telegram_connection, daemon=True).start()
        except Exception:
            pass
        bot_log = os.path.join(os.path.expanduser("~"), ".claudy", "telegram_bot.log")
        return ("Token guardado y bot lanzado ✓\n"
                "Ahora abre Telegram, busca tu bot y mándale /start.\n"
                "Si no estás autorizado, te dará tu ID — copia ese ID y aquí escribe:\n"
                "    /vincular <ID>\n"
                f"Log del bot: {bot_log}")

    def _telegram_status(self):
        """Devuelve un resumen del estado actual de la integración con Telegram."""
        config_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        tg = cfg.get("telegram", {}) or {}
        token = tg.get("botToken", "") or ""
        allowed = tg.get("allowedUsers", []) or []
        tts = bool(tg.get("ttsReply", False))
        # Estado de dependencias
        deps = []
        for mod, label in (("telegram", "python-telegram-bot"),
                           ("edge_tts", "edge-tts (voz salida)"),
                           ("faster_whisper", "faster-whisper (voz entrada)")):
            try:
                __import__(mod)
                deps.append(f"✓ {label}")
            except Exception:
                deps.append(f"✗ {label} (no instalado)")
        token_disp = (token[:6] + "…" + token[-4:]) if token else "(no configurado)"
        return (
            "Estado de Telegram\n"
            f"  Token:          {token_disp}\n"
            f"  Usuarios:       {', '.join(map(str, allowed)) if allowed else '(ninguno autorizado)'}\n"
            f"  Voz de salida:  {'ON' if tts else 'OFF'}  (/telegram-voice on|off)\n"
            "  Dependencias:\n    " + "\n    ".join(deps) + "\n"
            "Comandos: /telegram-token <TOKEN>  ·  /vincular <ID>  ·  /telegram-voice on|off"
        )

    def _vincular_telegram_user(self, uid):
        """Add a Telegram user ID to the allowed list."""
        uid = str(uid).strip()
        config_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
        if not os.path.exists(config_path):
            return "No encuentro la config. Ejecuta Claudy primero."
        with open(config_path, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
        if "telegram" not in config:
            config["telegram"] = {}
        if "allowedUsers" not in config["telegram"]:
            config["telegram"]["allowedUsers"] = []
        if uid not in config["telegram"]["allowedUsers"]:
            config["telegram"]["allowedUsers"].append(uid)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self._telegram_allowed_users.add(uid)
            return f"Usuario {uid} vinculado correctamente."
        return f"Usuario {uid} ya estaba vinculado."

    def launch_claudy(self):
        project_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
        command = f'cd /d "{project_dir}" && npx claudy chat'
        if shutil.which("wt"):
            subprocess.Popen(
                ["wt", "new-tab", "--title", "Claudy Chat", "cmd", "/k", command], shell=True,
            )
            return
        subprocess.Popen(
            ["cmd", "/c", "start", "Claudy Chat", "cmd", "/k", command], shell=True,
        )

    # ==============================================================
    # PHASE 4: SUBAGENTS, KANBAN, WEBHOOKS, WORKTREES
    # ==============================================================

    # --- Subagentes ---

    def _spawn_subagent(self, task, context=""):
        """Launch a subagent as an independent process via Gateway API."""
        subagent_script = os.path.join(SCRIPT_DIR, "bg_subagent.py")
        if not os.path.exists(subagent_script):
            # Create on-the-fly if missing
            with open(subagent_script, "w", encoding="utf-8") as f:
                f.write(r'''"""Claudy Subagent - ejecuta una tarea aislada via Gateway API."""
import asyncio, json, os, sys, urllib.request, time
GATEWAY = "http://127.0.0.1:8720/api"
task_file = os.path.join(os.path.expanduser("~"), ".claudy", "subagent_task.json")
with open(task_file, "r", encoding="utf-8") as f:
    task_data = json.load(f)
print(f"[Subagent] Tarea: {task_data.get('task','')[:80]}")
req = urllib.request.Request(GATEWAY,
    data=json.dumps({"message": task_data["task"]}).encode("utf-8"),
    headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=300)
    result = json.loads(resp.read()).get("response", "")
except Exception as e:
    result = f"Error: {e}"
result_path = os.path.join(os.path.expanduser("~"), ".claudy", "subagent_result.json")
with open(result_path, "w", encoding="utf-8") as f:
    json.dump({"task": task_data["task"], "result": result, "time": time.time()}, f)
print(f"[Subagent] Completado")
''')
        task_file = os.path.join(os.path.expanduser("~"), ".claudy", "subagent_task.json")
        os.makedirs(os.path.dirname(task_file), exist_ok=True)
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump({"task": task, "context": context}, f)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([sys.executable, "-u", subagent_script], creationflags=flags)
        return f"Subagente lanzado para: {task[:100]}...\nResultados en ~/.claudy/subagent_result.json"

    def _check_subagent_result(self):
        """Check if subagent completed and return result."""
        result_path = os.path.join(os.path.expanduser("~"), ".claudy", "subagent_result.json")
        if not os.path.exists(result_path):
            return None
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            os.remove(result_path)
            return data.get("result", "Sin resultado")
        except Exception:
            return None

    # --- Kanban Board ---

    def _kanban_db(self):
        drive_dir = r"G:\Mi unidad\QCORE-ECOSYSTEM\MEMORIAS\AGENTES-MEMORY\claudy_local"
        if os.path.isdir(drive_dir):
            return os.path.join(drive_dir, "kanban.db")
        return os.path.join(os.path.expanduser("~"), ".claudy", "kanban.db")

    def _init_kanban_db(self):
        db = self._kanban_db()
        os.makedirs(os.path.dirname(db), exist_ok=True)
        conn = sqlite3.connect(db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'todo',
                priority INTEGER DEFAULT 0,
                assigned_to TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kanban_status ON tasks(status)")
        conn.commit()
        conn.close()

    def _kanban_add(self, title, description="", priority=0):
        self._init_kanban_db()
        conn = sqlite3.connect(self._kanban_db())
        conn.execute(
            "INSERT INTO tasks (title, description, priority) VALUES (?, ?, ?)",
            (title, description, priority),
        )
        conn.commit()
        tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return f"Tarea kanban #{tid} creada: {title}"

    def _kanban_list(self, status=None):
        self._init_kanban_db()
        conn = sqlite3.connect(self._kanban_db())
        conn.row_factory = sqlite3.Row
        if status:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY priority DESC, id ASC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks ORDER BY status, priority DESC, id ASC").fetchall()
        conn.close()
        if not rows:
            return "Kanban vacio. Usa /kanban add <titulo>"
        by_status = {}
        for r in rows:
            s = r["status"]
            if s not in by_status:
                by_status[s] = []
            by_status[s].append(r)
        lines = ["Kanban:"]
        for s in ("backlog", "todo", "in_progress", "done"):
            if s in by_status:
                lines.append(f"  [{s.upper()}]")
                for r in by_status[s]:
                    lines.append(f"    #{r['id']} [{r['priority']}] {r['title'][:80]}")
        return "\n".join(lines)

    def _kanban_move(self, task_id, new_status):
        valid = ("backlog", "todo", "in_progress", "done")
        if new_status not in valid:
            return f"Estado invalido. Usa: {', '.join(valid)}"
        self._init_kanban_db()
        conn = sqlite3.connect(self._kanban_db())
        conn.execute(
            "UPDATE tasks SET status=?, updated_at=datetime('now','localtime') WHERE id=?",
            (new_status, task_id),
        )
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return f"Tarea #{task_id} movida a {new_status}" if affected else f"Tarea #{task_id} no encontrada"

    def _kanban_delete(self, task_id):
        self._init_kanban_db()
        conn = sqlite3.connect(self._kanban_db())
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return f"Tarea #{task_id} eliminada" if affected else f"Tarea #{task_id} no encontrada"

    # --- Webhooks ---

    def _webhooks_db(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", "webhooks.db")

    def _init_webhooks_db(self):
        db = self._webhooks_db()
        os.makedirs(os.path.dirname(db), exist_ok=True)
        conn = sqlite3.connect(db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                secret TEXT,
                last_called TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.commit()
        conn.close()

    def _webhook_register(self, name, url, secret=""):
        self._init_webhooks_db()
        conn = sqlite3.connect(self._webhooks_db())
        conn.execute(
            "INSERT INTO webhooks (name, url, secret) VALUES (?, ?, ?)",
            (name, url, secret),
        )
        conn.commit()
        wid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return f"Webhook #{wid} registrado: {name} -> {url}"

    def _webhook_list(self):
        self._init_webhooks_db()
        conn = sqlite3.connect(self._webhooks_db())
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM webhooks ORDER BY id ASC").fetchall()
        conn.close()
        if not rows:
            return "No hay webhooks. Usa /webhook add <nombre> <url>"
        lines = ["Webhooks:"]
        for r in rows:
            last = r["last_called"] or "nunca"
            lines.append(f"  #{r['id']} {r['name']} -> {r['url'][:60]} (ultimo: {last})")
        return "\n".join(lines)

    def _webhook_trigger_all(self, event_data=""):
        """Trigger all webhooks with event data."""
        self._init_webhooks_db()
        conn = sqlite3.connect(self._webhooks_db())
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM webhooks").fetchall()
        results = []
        for r in rows:
            try:
                payload = {"event": r["name"], "data": event_data, "timestamp": datetime.datetime.now().isoformat()}
                req = urllib.request.Request(
                    r["url"], data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "X-Webhook-Secret": r["secret"] or ""},
                )
                urllib.request.urlopen(req, timeout=10)
                conn.execute("UPDATE webhooks SET last_called=datetime('now','localtime') WHERE id=?", (r["id"],))
            except Exception as e:
                results.append(f"  {r['name']}: ERROR - {e}")
        conn.commit()
        conn.close()
        return "Webhooks disparados.\n" + "\n".join(results) if results else "Todos los webhooks ejecutados OK."

    # --- Git Worktree ---

    def _worktree_create(self, name, base_branch="main"):
        """Create a git worktree for isolated work."""
        project_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
        wt_path = os.path.join(os.path.expanduser("~"), ".claudy", "worktrees", name)
        os.makedirs(os.path.dirname(wt_path), exist_ok=True)
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            r = subprocess.run(
                ["git", "worktree", "add", wt_path, base_branch],
                cwd=project_dir, capture_output=True, text=True, timeout=30, creationflags=flags,
            )
            if r.returncode != 0:
                return f"Error: {r.stderr.strip()}"
            return f"Worktree creado: {wt_path}\nBranch: {base_branch}"
        except Exception as e:
            return f"Error creando worktree: {e}"

    def _worktree_list(self):
        project_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            r = subprocess.run(
                ["git", "worktree", "list"],
                cwd=project_dir, capture_output=True, text=True, timeout=10, creationflags=flags,
            )
            return r.stdout.strip() or "No hay worktrees."
        except Exception as e:
            return f"Error: {e}"

    def _worktree_remove(self, name):
        project_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
        wt_path = os.path.join(os.path.expanduser("~"), ".claudy", "worktrees", name)
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            r = subprocess.run(
                ["git", "worktree", "remove", wt_path, "--force"],
                cwd=project_dir, capture_output=True, text=True, timeout=30, creationflags=flags,
            )
            if r.returncode != 0:
                return f"Error: {r.stderr.strip()}"
            return f"Worktree {name} eliminado."
        except Exception as e:
            return f"Error: {e}"


if __name__ == "__main__":
    app_ready = threading.Event()
    app = None

    def run_app():
        global app
        app = ClawdPet()
        try:
            app._restore_pending_alarms()
        except Exception:
            pass
        app_ready.set()
        app.mainloop()

    t = threading.Thread(target=run_app, daemon=True, name="tkinter-mainloop")
    t.start()

    # Wait for the app to be initialized (with timeout to avoid indefinite blocking)
    app_ready.wait(timeout=10.0)

    # Now, run PyWebView on the main thread!
    app._run_webview_main_thread()
