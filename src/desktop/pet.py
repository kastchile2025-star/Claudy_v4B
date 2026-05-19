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

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Claudy"

try:
    from tts import speak as _tts_speak, stop_speaking as _tts_stop
    TTS_OK = True
except Exception:
    TTS_OK = False
    def _tts_speak(*_a, **_k): pass
    def _tts_stop(): pass

try:
    from model_router import pick_model as _route_model
except Exception:
    def _route_model(_prompt, _config, fallback): return fallback

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"])
    from PIL import Image, ImageDraw, ImageFilter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_FRAMES = [os.path.join(SCRIPT_DIR, f"claudy_orbit_frame_{i}.png") for i in range(6)]
TRANSPARENT_COLOR = "#ff00ff"

THEME = {
    "bg_bubble": "#161622",
    "bg_bubble_border": "#2a2a40",
    "bg_input": "#0f0f1a",
    "bg_input_border": "#2a2a40",
    "text_primary": "#e8e8f0",
    "text_secondary": "#8a8aa3",
    "accent": "#7c6bff",
    "accent_glow": "#ff7edb",
    "body": (110, 120, 230, 255),
    "body_dark": (60, 65, 140, 255),
    "screen": (18, 18, 32, 255),
    "outline": (255, 255, 255, 255),
    "eye_glow": (120, 255, 210, 255),
    "fin": (255, 190, 100, 255),
}

MEMORY_MAX_MESSAGES = 200
MEMORY_CONTEXT_MESSAGES = 20
MEMORY_CONTEXT_CHARS = 6000

BUBBLE_WIDTH = 300
BUBBLE_HEIGHT = 340
BUBBLE_MINI_SIZE = 44

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


class ClawdPet(tk.Tk):
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

        self.frames = [tk.PhotoImage(file=path) for path in ASSET_FRAMES]
        self.frame_index = 0
        self.img = self.frames[self.frame_index]
        self.label = tk.Label(self, image=self.img, bg=TRANSPARENT_COLOR, bd=0)
        self.label.pack()

        self.update_idletasks()
        self.width = self.winfo_reqwidth()
        self.height = self.winfo_reqheight()

        self.base_x = work_area.right - self.width - 20
        self.base_y = work_area.bottom - self.height - 14
        self.geometry(f"{self.width}x{self.height}+{self.base_x}+{self.base_y}")

        self.tick = 0
        self.state = "idle"
        self.bubble_win = None
        self.bubble_interactive = False
        self.quick_session_id = None
        self.opencode_process = None
        self.history_win = None
        self._current_model = None  # Override model from /model command
        self._voice_enabled = False  # /voice on|off — TTS toggle
        self._plan_mode = False  # /plan on|off — solo planea, no ejecuta
        self._checkpoint_history = []  # F3.1 stack para undo/redo
        self._checkpoint_undone = []
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

        self._cron_jobs = []
        self._cron_file = os.path.join(os.path.expanduser("~"), ".claudy", "cron.json")

        self._voice_listening = False
        self._voice_active = False

        self._gateway_server = None
        self._gateway_port = 8720
        self._gateway_bind_ip = "127.0.0.1"
        self._gateway_auth_token = None

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
            bg=THEME["bg_bubble"],
            fg=THEME["text_primary"],
            activebackground=THEME["accent"],
            activeforeground="#ffffff",
            bd=0,
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.menu.add_command(label="Hablar aqui", command=lambda: self.show_chat_bubble("Que tienes en mente?"))
        self.menu.add_command(label="Abrir terminal", command=self.launch_claudy)
        self.menu.add_separator()
        auto_start_label = "Desactivar inicio automatico" if self._is_auto_start_enabled() else "Activar inicio automatico"
        self.menu.add_command(label=auto_start_label, command=self._toggle_auto_start_menu)
        self.menu.add_command(label="Cerrar", command=self.destroy)
        self.label.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))

        # Initialize system tray icon.
        self._tray_icon = None
        self.after(1000, self._create_tray_icon)
        # Start Telegram bot if configured
        self.after(1500, self._start_telegram_if_configured)
        # Start Discord bot if configured
        self.after(2500, self._start_discord_if_configured)
        # Start Cron engine
        self.after(3000, self._start_cron_engine)
        # Start Gateway HTTP server
        self.after(500, self._start_gateway)
        # Initialize SQLite memory
        self.after(2000, self._init_memory_db)
        # Register built-in tools
        self._register_builtin_tools()
        # Initialize Kanban board
        self.after(3500, self._init_kanban_db)
        # Saludo inicial: abrir bubble con presentacion + pregunta abierta
        self.after(4000, self._show_welcome_bubble)
        # Hotkey global Alt+Space para abrir/cerrar el bubble desde cualquier app
        self.after(5000, self._register_global_hotkey)
        # Loop de comportamientos idle dinamicos (bostezo, mirada, baile, etc.)
        self.after(12000, self._start_idle_behaviors)

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

    def _show_welcome_bubble(self):
        import random
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

    def _is_crab(self):
        """Detecta si el skin actual es cangrejo."""
        try:
            flag = os.path.join(SCRIPT_DIR, "custom_skin.flag")
            if not os.path.exists(flag):
                return False
            with open(flag, "r", encoding="utf-8", errors="replace") as f:
                return "crab" in f.read().lower()
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
            self._advance_frame(speed=3, mode="loop")
        elif state == "sleeping":
            self._advance_frame(speed=14, mode="loop")
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

        # --- Motion per state ---
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
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "hover":
            offset_y = int(math.sin(self.tick / 10) * 3.5)
            offset_x = int(math.sin(self.tick / 16) * 1.5)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y - 3}")
            self.tick += 1
        elif state == "thinking":
            offset_y = int(math.sin(self.tick / 6) * 4)
            offset_x = int(math.cos(self.tick / 8) * 3)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y - 2}")
            self.tick += 1
        elif state == "happy":
            offset_y = -int(abs(math.sin(self.tick / 4)) * 9)
            offset_x = int(math.sin(self.tick / 7) * 2)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "talking":
            offset_x = int(math.sin(self.tick / 5) * 3)
            offset_y = int(math.sin(self.tick / 11) * 1.5)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "wave":
            # Bigger horizontal wave
            offset_x = int(math.sin(self.tick / 4) * 8)
            offset_y = int(abs(math.sin(self.tick / 8)) * -2)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "dance":
            # Hip sway + small bob, like a beat
            beat = self.tick // 6
            x_amp = 6
            offset_x = int(math.sin(self.tick / 4) * x_amp)
            offset_y = -int(abs(math.sin(self.tick / 3)) * 6)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "sleeping":
            # Slow deep breathing
            offset_y = int(math.sin(self.tick / 60) * 1.5)
            offset_x = cur_dx
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y + 2}")
            self.tick += 1
        elif state == "surprised":
            # Sharp upward jump then settle
            elapsed = self.tick - getattr(self, "_state_start_tick", self.tick)
            if elapsed < 10:
                offset_y = -int(elapsed * 1.6)
            else:
                offset_y = -int(max(0, 16 - (elapsed - 10) * 1.5))
            self.geometry(f"+{self.base_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "yawn":
            # Slow stretch up then down
            elapsed = self.tick - getattr(self, "_state_start_tick", self.tick)
            offset_y = int(-abs(math.sin(elapsed / 24)) * 6) + cur_dy
            offset_x = cur_dx
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "look":
            # Look around: slow horizontal scan
            offset_x = int(math.sin(self.tick / 20) * 5)
            offset_y = int(math.cos(self.tick / 40) * 1.5)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "shy":
            # Small backward shrink (simulated with downward drift)
            offset_y = int(math.sin(self.tick / 8) * 1) + 4
            offset_x = -3
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        # --- Crab-specific motions ---
        elif state == "crab_walk":
            # Sideways march: zigzag amplio en X, mini-bobbing en Y
            elapsed = self.tick - getattr(self, "_state_start_tick", self.tick)
            direction = getattr(self, "_crab_dir", 1)
            offset_x = int(math.sin(self.tick / 6) * 2) + direction * (elapsed // 6) % 24 - 12
            offset_y = int(abs(math.sin(self.tick / 3)) * -3)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "pinch":
            # Pinzas al aire: rebote vertical agresivo + temblor horizontal
            elapsed = self.tick - getattr(self, "_state_start_tick", self.tick)
            offset_y = -int(abs(math.sin(elapsed / 3)) * 10)
            offset_x = int(math.sin(self.tick / 1.5) * 4)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "hide":
            # Esconderse: hundirse rapido en Y, vibracion leve, luego asomarse
            elapsed = self.tick - getattr(self, "_state_start_tick", self.tick)
            if elapsed < 8:
                offset_y = int(elapsed * 2)
            elif elapsed < 30:
                offset_y = 16 + int(math.sin(self.tick / 4) * 1)
            else:
                offset_y = max(0, 16 - int((elapsed - 30) * 1.5))
            offset_x = int(math.sin(self.tick / 5) * 1)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "bubble":
            # Burbujear: rebote suave hacia arriba como si soltara burbujas
            offset_y = -int(abs(math.sin(self.tick / 8)) * 4)
            offset_x = int(math.sin(self.tick / 12) * 2)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "dig":
            # Cavar: oscilacion fuerte X-Y rapida, simula movimiento de patas escarbando
            offset_x = int(math.sin(self.tick / 2) * 5)
            offset_y = int(math.cos(self.tick / 2) * 3) + 2
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        elif state == "scuttle":
            # Carrera lateral rapida (huida) — un solo trip ida y vuelta
            elapsed = self.tick - getattr(self, "_state_start_tick", self.tick)
            phase = (elapsed % 60) / 60.0
            if phase < 0.5:
                offset_x = int(phase * 60) - 15
            else:
                offset_x = int((1.0 - phase) * 60) - 15
            offset_y = int(abs(math.sin(self.tick / 2)) * -4)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        else:
            # Unknown state: fall back to idle motion
            offset_y = int(math.sin(self.tick / 30) * 2.5)
            offset_x = int(math.cos(self.tick / 50) * 1)
            self.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
            self.tick += 1
        self.after(40, self.animate)

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
        def _restore():
            if self.state == new_state:
                self.state = "idle"
        self.after(duration_ms, _restore)

    def _start_idle_behaviors(self):
        """Loop: while idle, occasionally pick a micro-animation (yawn/look/dance/shy)."""
        try:
            import random as _r
            if self.state == "idle" and not self.bubble_interactive:
                # Probabilities tuned to feel alive but not annoying
                pick = _r.random()
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
        self.launch_claudy()

    def _toggle_auto_start_menu(self):
        """Toggle auto-start and update the menu label."""
        if self._is_auto_start_enabled():
            self._disable_auto_start()
            self._show_notification("Claudy", "Inicio automatico desactivado")
        else:
            self._enable_auto_start()
            self._show_notification("Claudy", "Inicio automatico activado")
        # Rebuild menu with updated label.
        self.menu.delete(0, "end")
        self.menu.add_command(label="Hablar aqui", command=lambda: self.show_chat_bubble("Que tienes en mente?"))
        self.menu.add_command(label="Abrir terminal", command=self.launch_claudy)
        self.menu.add_separator()
        auto_start_label = "Desactivar inicio automatico" if self._is_auto_start_enabled() else "Activar inicio automatico"
        self.menu.add_command(label=auto_start_label, command=self._toggle_auto_start_menu)
        self.menu.add_command(label="Cerrar", command=self.destroy)

    def _on_drag_start(self, event):
        self._dragging = True
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._drag_offset_x = event.x
        self._drag_offset_y = event.y
        self._cancel_idle_timer()

    def _on_drag_motion(self, event):
        if not self._dragging:
            return
        new_x = self.winfo_x() + event.x - self._drag_offset_x
        new_y = self.winfo_y() + event.y - self._drag_offset_y
        self.geometry(f"+{new_x}+{new_y}")
        self.base_x = new_x
        self.base_y = new_y
        # Keep the minimized Zzz bubble glued to the pet as it moves
        self._sync_minimized_bubble()

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
        if self._snap_enabled:
            self._snap_to_edge()

    def _snap_to_edge(self):
        x = self.winfo_x()
        y = self.winfo_y()
        w = self.winfo_width()
        h = self.winfo_height()
        screen_w = work_area.right - work_area.left
        screen_h = work_area.bottom - work_area.top
        margin = self._snap_margin

        # Snap to bottom-right corner (default resting position).
        if x + w > screen_w - margin:
            x = screen_w - w - 10
        if y + h > screen_h - margin:
            y = screen_h - h - 10
        # Snap to left edge.
        if x < work_area.left + margin:
            x = work_area.left + 10
        # Snap to top edge.
        if y < work_area.top + margin:
            y = work_area.top + 10
        # Snap to right edge.
        if x + w > screen_w - margin:
            x = screen_w - w - 10

        self.base_x = x
        self.base_y = y
        self.geometry(f"+{x}+{y}")
        # Re-sync the Zzz bubble after snapping
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

        def on_show_tray(icon, item):
            self.deiconify()
            self.lift()

        def on_hide_tray(icon, item):
            self.withdraw()

        def on_toggle_auto_start(icon, item):
            if self._is_auto_start_enabled():
                self._disable_auto_start()
                self._show_notification("Claudy", "Inicio automatico desactivado")
            else:
                self._enable_auto_start()
                self._show_notification("Claudy", "Inicio automatico activado")

        def on_quit(icon, item):
            icon.stop()
            self.destroy()

        menu = pystray.Menu(
            pystray.MenuItem("Mostrar", on_show_tray),
            pystray.MenuItem("Ocultar", on_hide_tray),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Inicio automatico", on_toggle_auto_start, checked=lambda _: self._is_auto_start_enabled()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", on_quit),
        )

        self._tray_icon = pystray.Icon("claudy", icon_image, "Claudy", menu)
        # Run tray in daemon thread so it doesn't block the mainloop.
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def run_bounce(self, frame):
        offsets = [0, -5, -10, -14, -8, -3, 0, 3, 0]
        if frame < len(offsets):
            self.geometry(f"+{self.base_x}+{self.base_y + offsets[frame]}")
            self.after(40, lambda: self.run_bounce(frame + 1))
        else:
            self.state = "idle"

    def hide_bubble(self):
        self._cancel_idle_timer()
        self._stop_zzz_animation()
        if self.bubble_win:
            self.bubble_win.destroy()
            self.bubble_win = None
        self.bubble_interactive = False
        self.bubble_minimized = False

    def _on_bubble_focus_out(self, _event=None):
        # Delay check so focus can settle on the new widget
        self.after(50, self._check_bubble_focus)

    def _check_bubble_focus(self):
        if not self.bubble_win:
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

        # Cursor is outside both; minimize bubble (keep conversation alive)
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
        margin = 14
        # base_x/base_y are tracked manually on init, drag, and snap.
        # They are always the pet's resting position in absolute screen coords.
        # This is more reliable than winfo_rootx() under overrideredirect(True).
        pet_x = self.base_x
        pet_y = self.base_y
        pet_w = self.width
        pet_h = self.height
        x = pet_x + pet_w // 2 - width // 2
        # Place bubble so its bottom (tail) sits just above the pet
        y = pet_y - height + 30
        x = max(work_area.left + margin, min(x, work_area.right - width - margin))
        y = max(work_area.top + margin, y)
        return x, y

    def minimized_position(self, size):
        """Position for the minimized Zzz bubble: floats just above pet's head."""
        pet_x = self.base_x
        pet_y = self.base_y
        pet_w = self.width
        # Center horizontally on pet, just above its head
        x = pet_x + pet_w // 2 - size // 2
        y = pet_y - size + 10
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
        """Draw a clean rounded bubble with soft shadow and tail."""
        # Soft shadow (simulated with offset dark polygon).
        shadow_pts = self._rounded_bubble_path(w, h, 16, tail_h=10, tail_w=16)
        shadow_pts = [(x + 2, y + 3) for x, y in shadow_pts]
        canvas.create_polygon(shadow_pts, smooth=True, fill="#000000", outline="",
                              stipple="gray25", tags=("bubble_bg",))

        # Main bubble.
        pts = self._rounded_bubble_path(w, h, 16, tail_h=10, tail_w=16)
        canvas.create_polygon(pts, smooth=True, fill=bg, outline=border, width=1,
                              tags=("bubble_bg",))

    def show_thought(self, text):
        self.hide_bubble()
        self.bubble_interactive = False

        bub = tk.Toplevel(self)
        bub.overrideredirect(True)
        bub.attributes("-topmost", True)
        bub.configure(bg=TRANSPARENT_COLOR)
        bub.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        # Measure text to auto-size.
        temp = tk.Label(bub, text=text, font=("Segoe UI", 10, "bold"), wraplength=220)
        temp.update_idletasks()
        tw, th = temp.winfo_reqwidth(), temp.winfo_reqheight()
        temp.destroy()

        pad_x, pad_y = 24, 18
        width = max(160, tw + pad_x * 2)
        height = max(70, th + pad_y * 2 + 10)

        canvas = tk.Canvas(bub, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        canvas.pack()

        self._draw_bubble(canvas, width, height, THEME["bg_bubble"], THEME["bg_bubble_border"])

        canvas.create_text(
            width // 2, height // 2 - 4,
            text=text, width=width - pad_x * 2,
            fill=THEME["text_primary"],
            font=("Segoe UI", 10, "bold"),
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
            except tk.TclError:
                self.bubble_win = None
            return

        self.bubble_interactive = True
        self.bubble_minimized = False

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
        self._draw_bubble(canvas, width, height, THEME["bg_bubble"], THEME["bg_bubble_border"])

        # History button (left) – tiny toggle icon.
        history_btn = tk.Label(
            bub, text="\u2630", bg=THEME["bg_bubble_border"], fg=THEME["text_primary"],
            font=("Segoe UI", 7), cursor="hand2",
            padx=3, pady=1, relief="flat", bd=0,
            highlightbackground=THEME["accent"], highlightthickness=0,
        )
        history_id = canvas.create_window(18, 14, anchor="nw", window=history_btn)
        history_btn.bind("<Button-1>", lambda _e: self.show_history_window())
        history_btn.bind("<Enter>", lambda _e: history_btn.config(fg=THEME["accent"], bg=THEME["bg_input"]))
        history_btn.bind("<Leave>", lambda _e: history_btn.config(fg=THEME["text_primary"], bg=THEME["bg_bubble_border"]))

        # Folder analyzer button: pick a folder, analyze deep, save to Obsidian.
        folder_btn = tk.Label(
            bub, text="\U0001F4C1", bg=THEME["bg_bubble_border"], fg=THEME["text_primary"],
            font=("Segoe UI Emoji", 8), cursor="hand2",
            padx=3, pady=1, relief="flat", bd=0,
        )
        folder_id = canvas.create_window(48, 14, anchor="nw", window=folder_btn)

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
                    result = f"Error: {e}"
                self.after(0, lambda: self._set_response_text(result))
                self.after(0, lambda: status.configure(text="Enter envia  ·  Esc cierra", fg=THEME["text_secondary"]))
            threading.Thread(target=_run, daemon=True).start()

        folder_btn.bind("<Button-1>", _on_analyze_folder)
        folder_btn.bind("<Enter>", lambda _e: folder_btn.config(fg=THEME["accent"], bg=THEME["bg_input"]))
        folder_btn.bind("<Leave>", lambda _e: folder_btn.config(fg=THEME["text_primary"], bg=THEME["bg_bubble_border"]))

        # Clear visible area button (history stays saved on disk).
        clear_btn = tk.Label(
            bub, text="\U0001F9F9", bg=THEME["bg_bubble_border"], fg=THEME["text_primary"],
            font=("Segoe UI Emoji", 8), cursor="hand2",
            padx=3, pady=1, relief="flat", bd=0,
        )
        clear_id = canvas.create_window(78, 14, anchor="nw", window=clear_btn)
        clear_btn.bind("<Button-1>", lambda _e: self._set_response_text(""))
        clear_btn.bind("<Enter>", lambda _e: clear_btn.config(fg=THEME["accent"], bg=THEME["bg_input"]))
        clear_btn.bind("<Leave>", lambda _e: clear_btn.config(fg=THEME["text_primary"], bg=THEME["bg_bubble_border"]))

        # Minimize button.
        minimize_btn = tk.Label(
            bub, text="\u2014", bg=THEME["bg_bubble"], fg=THEME["text_secondary"],
            font=("Segoe UI", 10), cursor="hand2",
        )
        minimize_id = canvas.create_window(width - 14, 10, anchor="ne", window=minimize_btn)

        # Scrollable response area.
        response_frame = tk.Frame(bub, bg=THEME["bg_bubble"], bd=0, highlightthickness=0)
        response_scroll = tk.Scrollbar(
            response_frame, orient="vertical", width=6,
            bg=THEME["bg_bubble_border"], troughcolor=THEME["bg_bubble"],
            activebackground=THEME["accent"], highlightthickness=0, bd=0,
            relief="flat",
        )
        response_text = tk.Text(
            response_frame, bg=THEME["bg_bubble"], fg=THEME["text_primary"],
            font=("Segoe UI", 10), wrap="word",
            yscrollcommand=response_scroll.set, state="disabled",
            highlightthickness=0, bd=0, padx=8, pady=4,
            cursor="arrow", relief="flat", spacing1=2, spacing3=2,
            selectbackground=THEME["accent"], selectforeground="#ffffff",
        )
        response_scroll.config(command=response_text.yview)
        response_scroll.pack(side="right", fill="y")
        response_text.pack(side="left", fill="both", expand=True)
        self._response_text_widget = response_text
        self._set_response_text(text)
        header_id = canvas.create_window(14, 34, anchor="nw", width=width - 28, height=200, window=response_frame)

        # Dummy references for minimize/expand (pagination removed).
        prev_id = None
        next_id = None
        page_id = None
        self._pagination_ids = None
        self._pagination_btns = None
        self._bubble_canvas = canvas

        # Input area — simple placeholder via direct entry manipulation.
        _PLACEHOLDER = "Escribe aqui..."

        entry = tk.Entry(
            bub,
            bg=THEME["bg_input"], fg=THEME["text_secondary"],
            insertbackground=THEME["accent"], insertwidth=2,
            relief="flat", font=("Segoe UI", 10),
            highlightthickness=1, highlightbackground=THEME["bg_input_border"],
            highlightcolor=THEME["accent"], bd=0,
        )
        entry.insert(0, _PLACEHOLDER)
        entry_id = canvas.create_window(22, 244, anchor="nw", width=width - 44, height=28, window=entry)

        def _has_placeholder():
            return entry.get() == _PLACEHOLDER

        def _clear_placeholder(*_):
            if _has_placeholder():
                entry.delete(0, tk.END)
                entry.config(fg=THEME["text_primary"])

        def _restore_placeholder(*_):
            if not entry.get().strip():
                entry.delete(0, tk.END)
                entry.insert(0, _PLACEHOLDER)
                entry.config(fg=THEME["text_secondary"])

        entry.bind("<FocusIn>", _clear_placeholder, add=True)
        entry.bind("<Button-1>", lambda _e: entry.after_idle(_clear_placeholder))
        entry.bind("<Key>", _clear_placeholder, add=True)
        entry.bind("<FocusOut>", lambda _e: entry.after_idle(_restore_placeholder))

        status = tk.Label(
            bub, text="Enter envia  \u00b7  Esc cierra",
            bg=THEME["bg_bubble"], fg=THEME["text_secondary"],
            font=("Segoe UI", 8), padx=10, pady=2, anchor="w",
        )
        status_id = canvas.create_window(14, 280, anchor="nw", width=width - 28, window=status)

        # Position for the minimized (Zzz) state — centered in the mini window.
        mini_cx = BUBBLE_MINI_SIZE // 2
        mini_cy = BUBBLE_MINI_SIZE // 2

        # Sleep state visual — a single floating blue "Zzz" (no bubble, no shadow).
        zzz_text_id = canvas.create_text(
            mini_cx, mini_cy,
            text="Zzz", fill="#4a9eff", font=("Segoe UI", 14, "bold")
        )
        canvas.itemconfigure(zzz_text_id, state="hidden")

        _idle_items = (zzz_text_id,)

        self._zzz_text_id = zzz_text_id
        self._zzz_shadow_id = None  # No shadow anymore
        self._zzz_tick = 0
        self._zzz_anim_running = False

        def minimize():
            self.bubble_minimized = True
            self._reset_idle_timer()
            # Hide all UI chrome AND the bubble background — only Zzz remains
            for item in (header_id, entry_id, status_id, minimize_id, history_id, folder_id, clear_id):
                canvas.itemconfigure(item, state="hidden")
            canvas.itemconfigure("bubble_bg", state="hidden")
            for item in _idle_items:
                canvas.itemconfigure(item, state="normal")
            sz = BUBBLE_MINI_SIZE
            canvas.configure(width=sz, height=sz)
            cx, cy = self.minimized_position(sz)
            bub.geometry(f"{sz}x{sz}+{cx}+{cy}")
            self._start_zzz_animation()

        def expand():
            self.bubble_minimized = False
            self._cancel_idle_timer()
            self._stop_zzz_animation()
            for item in (header_id, entry_id, status_id, minimize_id, history_id, folder_id, clear_id):
                canvas.itemconfigure(item, state="normal")
            canvas.itemconfigure("bubble_bg", state="normal")
            for item in _idle_items:
                canvas.itemconfigure(item, state="hidden")
            self._sync_pagination_visibility(canvas)
            canvas.configure(width=width, height=height)
            cx, cy = self.bubble_position(width, height)
            bub.geometry(f"{width}x{height}+{cx}+{cy}")
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
                    items = self._list_checkpoints()
                    if not items:
                        self._set_response_text("No hay checkpoints.\nUsa: /checkpoint <ruta_archivo>")
                        status.configure(text="0 checkpoints", fg=THEME["text_secondary"])
                    else:
                        lines = [f"{cid} -> {src}" for cid, src, _ts in items[:20]]
                        self._set_response_text("Checkpoints:\n" + "\n".join(lines))
                        status.configure(text=f"{len(items)} checkpoints", fg=THEME["accent"])
                else:
                    ok, msg = self._create_checkpoint(arg)
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
                    items = self._list_checkpoints()
                    if not items:
                        self._set_response_text("No hay checkpoints para restaurar.")
                        status.configure(text="0 checkpoints", fg=THEME["text_secondary"])
                    else:
                        lines = [f"{cid} -> {src}" for cid, src, _ts in items[:20]]
                        self._set_response_text("Usa: /rollback <id>\n\n" + "\n".join(lines))
                        status.configure(text=f"{len(items)} disponibles", fg=THEME["accent"])
                else:
                    ok, msg = self._rollback_checkpoint(arg)
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
            entry.configure(state="disabled")
            thinking = random.choice([
                "Pensando...", "Dándole vueltas...", "Conectando neuronas...",
                "Consultando al oráculo...", "Hablando con las estrellas...", "Esforzándome...",
            ])
            status.configure(text=thinking, fg=THEME["accent"])
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

        entry.bind("<Return>", submit)
        entry.bind("<Escape>", lambda _e: self.hide_bubble())
        entry.bind("<FocusIn>", lambda _e: self._record_activity())

        def _on_paste(_e=None):
            handled = self._handle_pasted_image(status, entry)
            if handled:
                return "break"
            return None
        entry.bind("<Control-v>", _on_paste)
        entry.bind("<Control-V>", _on_paste)

        # F3.6 Drag & drop files onto the bubble
        try:
            from tkinterdnd2 import TkinterDnD, DND_FILES
            try:
                TkinterDnD._require(bub)
            except Exception:
                pass
            try:
                entry.drop_target_register(DND_FILES)
                entry.dnd_bind("<<Drop>>", lambda e: self._handle_dropped_file(e, status, entry))
            except Exception:
                pass
        except Exception:
            pass
        bub.bind("<Escape>", lambda _e: self.hide_bubble())

        cx, cy = self.bubble_position(width, height)
        bub.geometry(f"{width}x{height}+{cx}+{cy}")
        self.bubble_win = bub
        self._reset_idle_timer()

        # Foco automático en el input al abrir el chat — el usuario puede escribir directo
        try:
            bub.after(50, lambda: (bub.lift(), bub.focus_force(), entry.focus_set()))
        except Exception:
            pass

    def _set_response_text(self, text):
        """Set the scrollable response text in the chat bubble."""
        w = getattr(self, "_response_text_widget", None)
        if w is None:
            return
        try:
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.insert("1.0", text)
            w.configure(state="disabled")
            w.see("1.0")
        except tk.TclError:
            pass

    def _append_response_text(self, text):
        """Append text to the scrollable response area (for live progress)."""
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
            "Corriendo a toda máquina...", "Esforzándome al máximo...", "Buscando inspiración...",
        ])
        status.configure(text=thinking)
        self._last_prompt = prompt  # Guardar para fallback de acciones

        # Mensajes en cursiva dentro del input mientras procesa
        self._start_typing_progress(entry, prompt)

        # Hitos de progreso en la burbuja (mismas frases que Telegram)
        self._start_milestone_progress()

        def worker():
            try:
                answer = self.send_quick_message(prompt)
            except Exception as error:
                answer = f"Mmm... algo falló en mi cabecita: {error}"
            self._stop_milestone_progress()
            self.after(0, lambda: self.finish_quick_answer(answer, status, entry))

        threading.Thread(target=worker, daemon=True).start()

    # ============================================================
    # Hitos de progreso ("dame un momento, sigo trabajando...")
    # ============================================================
    PROGRESS_MILESTONES = [
        (12, "Dame un momento, estoy buscando..."),
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

    def _emit_milestone(self, msg):
        if not getattr(self, "_milestone_active", False):
            return
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

    # ============================================================
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

    def _animate_zzz(self):
        """Gentle floating blue Zzz animation for sleep state."""
        if not self._zzz_anim_running:
            return
        if not hasattr(self, '_zzz_text_id'):
            return

        self._zzz_tick += 1
        # Slow gentle cycle: 90 frames (~3.6s) for relaxed feel
        cycle = self._zzz_tick % 90
        progress = cycle / 90.0

        # Soft sine wave floating
        float_y = -int(math.sin(progress * math.pi * 2) * 4)
        float_x = int(math.sin(progress * math.pi * 1.5) * 2)

        # Breathing font size
        scale = 0.9 + 0.15 * math.sin(progress * math.pi * 2)
        font_size = max(11, int(14 * scale))

        # Blue color breathing — from soft blue to bright blue
        brightness = 0.7 + 0.3 * math.sin(progress * math.pi * 2)
        color = "#{:02x}{:02x}{:02x}".format(
            int(74 * brightness),
            int(158 * brightness),
            int(255 * brightness)
        )

        try:
            canvas = getattr(self, '_bubble_canvas', None)
            if canvas is None:
                return

            base_x = BUBBLE_MINI_SIZE // 2
            base_y = BUBBLE_MINI_SIZE // 2

            canvas.itemconfigure(
                self._zzz_text_id,
                text="Zzz",
                fill=color,
                font=("Segoe UI", font_size, "bold")
            )
            canvas.coords(
                self._zzz_text_id,
                base_x + float_x,
                base_y + float_y
            )
        except tk.TclError:
            self._zzz_anim_running = False
            return

        self.after(40, self._animate_zzz)

    def _sync_pagination_visibility(self, canvas):
        pass  # Pagination removed — scrollbar handles overflow.

    def finish_quick_answer(self, answer, status, entry):
        import re
        try:
            clean_answer = self._strip_markdown(answer)

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

            self._set_response_text(clean_answer)

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
            self._set_response_text(self._strip_markdown(result))
            status.configure(text="Búsqueda completada.", fg=THEME["text_secondary"])
            self._stop_typing_progress(entry)
            entry.focus_set()
        except tk.TclError:
            pass

    def show_history_window(self):
        # Toggle: if already open, close it.
        if self.history_win is not None:
            try:
                if self.history_win.winfo_exists():
                    self.history_win.destroy()
            except tk.TclError:
                pass
            self.history_win = None
            return

        messages = self._load_memory()

        hist = tk.Toplevel(self)
        hist.title("Historial de conversaciones")
        hist.configure(bg=THEME["bg_input"])
        hist.geometry("460x680")
        hist.attributes("-topmost", True)
        hist.resizable(False, False)
        self.history_win = hist

        def _on_close():
            self.history_win = None
            hist.destroy()

        hist.protocol("WM_DELETE_WINDOW", _on_close)

        shell = tk.Frame(
            hist, bg=THEME["bg_bubble"], bd=0,
            highlightbackground=THEME["accent"], highlightthickness=1,
        )
        shell.pack(fill="both", expand=True, padx=12, pady=12)

        header_canvas = tk.Canvas(shell, height=74, bg=THEME["bg_bubble"], highlightthickness=0, bd=0)
        header_canvas.pack(fill="x")
        header_canvas.create_rectangle(0, 0, 460, 74, fill=THEME["bg_input"], outline="")
        header_canvas.create_oval(18, 15, 50, 47, fill="#7c6bff", outline="#f7f4ff", width=1)
        header_canvas.create_polygon(34, 20, 45, 31, 40, 43, 28, 43, 23, 31,
                                     fill="#2fe6c8", outline="")
        header_canvas.create_text(
            66, 22, anchor="w", text="Archivo de conversaciones",
            fill=THEME["text_primary"], font=("Segoe UI", 12, "bold"),
        )

        total_user = sum(1 for m in messages if m.get("role") == "Usuario")
        total_claudy = max(0, len(messages) - total_user)
        header_canvas.create_text(
            66, 46, anchor="w",
            text=f"{len(messages)} mensajes  |  Tu {total_user}  |  Claudy {total_claudy}",
            fill=THEME["text_secondary"], font=("Segoe UI", 8),
        )

        # ── Skin picker (anclado al fondo ANTES del message frame para que reciba su espacio) ──
        skin_frame = tk.Frame(
            shell, bg=THEME["bg_input"],
            highlightbackground=THEME["accent"], highlightthickness=2, bd=0,
        )
        skin_frame.pack(side="bottom", fill="x", padx=12, pady=(8, 12))

        tk.Label(
            skin_frame, text="🎨 Skin de Claudy",
            bg=THEME["bg_input"], fg=THEME["accent"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(8, 2))

        tk.Label(
            skin_frame,
            text="Elige el aspecto de Claudy (cambio en vivo):",
            bg=THEME["bg_input"], fg=THEME["text_secondary"],
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=10, pady=(0, 6))

        btn_row = tk.Frame(skin_frame, bg=THEME["bg_input"])
        btn_row.pack(fill="x", padx=10, pady=(0, 8))

        status_label = tk.Label(
            skin_frame, text="",
            bg=THEME["bg_input"], fg=THEME["accent"],
            font=("Segoe UI", 8, "italic"),
        )
        status_label.pack(anchor="w", padx=10, pady=(0, 8))

        def make_skin_btn(parent, label, skin_name):
            return tk.Button(
                parent, text=label,
                command=lambda: self._switch_skin(skin_name, status_label),
                bg=THEME["bg_bubble"], fg=THEME["text_primary"],
                font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
                activebackground=THEME["accent"], activeforeground="#ffffff",
                padx=12, pady=6, bd=0,
            )

        make_skin_btn(btn_row, "🤖 Robot", "robot").pack(side="left", padx=(0, 6))
        make_skin_btn(btn_row, "🦀 Cangrejo", "crab").pack(side="left", padx=(0, 6))
        make_skin_btn(btn_row, "🖼️ Custom...", "custom").pack(side="left")

        # ── Message frame (toma el espacio restante en el medio) ──
        frame = tk.Frame(shell, bg=THEME["bg_bubble"])
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

        text_widget.tag_configure("user_name", foreground="#ffffff", font=("Segoe UI", 9, "bold"),
                                  background="#5d56d8", lmargin1=12, lmargin2=12,
                                  rmargin=56, spacing1=8, spacing3=0)
        text_widget.tag_configure("user_body", foreground="#f2efff", font=("Segoe UI", 9),
                                  background="#5d56d8", lmargin1=12, lmargin2=12,
                                  rmargin=56, spacing3=10)
        # Convert RGBA tuple to hex for tkinter Text tags (canvas accepts tuples, Text tags do not).
        eye_glow_hex = "#{:02x}{:02x}{:02x}".format(*THEME["eye_glow"][:3])
        text_widget.tag_configure("claudy_name", foreground=eye_glow_hex, font=("Segoe UI", 9, "bold"),
                                  background=THEME["bg_input"], lmargin1=56, lmargin2=56,
                                  rmargin=12, spacing1=8, spacing3=0)
        text_widget.tag_configure("claudy_body", foreground=THEME["text_primary"], font=("Segoe UI", 9),
                                  background=THEME["bg_input"], lmargin1=56, lmargin2=56,
                                  rmargin=12, spacing3=10)
        text_widget.tag_configure("time", foreground=THEME["text_secondary"], font=("Segoe UI", 7),
                                  lmargin1=12, lmargin2=12, rmargin=12, spacing3=3)
        text_widget.tag_configure("empty", foreground=THEME["text_secondary"], font=("Segoe UI", 10, "bold"),
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

    # --- F3.6 dropped file handler ---
    def _handle_dropped_file(self, event, status_widget, entry_widget):
        try:
            self._set_state_briefly("surprised", 700)
        except Exception:
            pass
        raw = event.data if event else ""
        # tkinterdnd2 returns paths possibly wrapped in {}; can be multiple
        import shlex
        paths = []
        for p in shlex.split(raw.replace("{", '"').replace("}", '"')):
            if p:
                paths.append(p)
        if not paths:
            return
        path = paths[0]
        if not os.path.exists(path):
            self._set_response_text(f"No existe: {path}")
            return
        ext = os.path.splitext(path)[1].lower()
        question = ""
        try:
            question = entry_widget.get().strip()
            if question == "Escribe aqui...":
                question = ""
            entry_widget.delete(0, tk.END)
        except Exception:
            pass
        # Imagen -> usar pipeline de vision
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
            self._set_response_text(f"Analizando imagen: {os.path.basename(path)}")
            try:
                status_widget.configure(text="Analizando imagen...", fg=THEME["accent"])
            except Exception:
                pass
            def _run_img():
                answer = self._analyze_image_native(path, question)
                self._save_memory("Usuario", f"[archivo: {os.path.basename(path)}] {question}".strip())
                self._save_memory("Claudy", answer)
                self.after(0, lambda: self._set_response_text(answer))
            threading.Thread(target=_run_img, daemon=True).start()
            return
        # PDF -> extraer texto y mandar como contexto
        if ext == ".pdf":
            try:
                text = self._read_pdf_text(path)
            except Exception as e:
                self._set_response_text(f"Error leyendo PDF: {e}")
                return
        else:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception as e:
                self._set_response_text(f"Error leyendo archivo: {e}")
                return
        if not text.strip():
            self._set_response_text(f"Archivo vacio: {path}")
            return
        text = text[:8000]
        prompt = f"[archivo: {os.path.basename(path)}]\n```\n{text}\n```\n\n{question or 'Resume el contenido.'}"
        self._set_response_text(f"Procesando: {os.path.basename(path)}")
        def _run_txt():
            answer = self.send_quick_message(prompt, _skip_skill_action=True)
            self.after(0, lambda: self._set_response_text(answer))
        threading.Thread(target=_run_txt, daemon=True).start()

    def _read_pdf_text(self, path):
        try:
            from pypdf import PdfReader
        except Exception:
            try:
                from PyPDF2 import PdfReader
            except Exception:
                return "[Para leer PDFs instala: pip install pypdf]"
        reader = PdfReader(path)
        parts = []
        for page in reader.pages[:30]:
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
        question = ""
        try:
            question = entry_widget.get().strip()
            if question == "Escribe aqui...":
                question = ""
            entry_widget.delete(0, tk.END)
        except Exception:
            pass
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

    def _create_checkpoint(self, file_path):
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
        ok, msg = self._rollback_checkpoint(cid)
        if ok:
            self._checkpoint_undone.append(cid)
        return msg

    def _redo_last(self):
        if not self._checkpoint_undone:
            return "Nada que rehacer."
        cid = self._checkpoint_undone.pop()
        self._checkpoint_history.append(cid)
        return f"Marcado para rehacer: {cid}\n(Aplica los cambios manualmente o crea otro checkpoint)"

    def _list_checkpoints(self):
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

    def _rollback_checkpoint(self, cid):
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
        return default

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
    def _memory_db_path(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", "memory.db")

    def _memory_jsonl_path(self):
        return os.path.join(os.path.expanduser("~"), ".claudy", "memory.jsonl")

    def _init_memory_db(self):
        """Initialize SQLite database and migrate existing JSONL data."""
        db_path = self._memory_db_path()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                memory_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (memory_id) REFERENCES memory(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_role ON memory(role)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_created ON memory(created_at)")
        conn.commit()
        conn.close()
        self._migrate_jsonl_to_sqlite()

    def _migrate_jsonl_to_sqlite(self):
        """One-time migration from memory.jsonl to SQLite."""
        jl_path = self._memory_jsonl_path()
        if not os.path.exists(jl_path):
            return
        db_path = self._memory_db_path()
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
        if count > 0:
            conn.close()
            return  # Already has data, skip migration
        try:
            with open(jl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if isinstance(msg, dict) and "role" in msg and "text" in msg:
                            conn.execute(
                                "INSERT INTO memory (role, text, created_at) VALUES (?, ?, ?)",
                                (msg["role"], msg["text"], msg.get("time", datetime.datetime.now().isoformat())),
                            )
                    except json.JSONDecodeError:
                        continue
            conn.commit()
            # Rename old file as backup
            backup = jl_path + ".bak"
            os.rename(jl_path, backup)
        except Exception:
            pass
        finally:
            conn.close()

    def _load_memory(self):
        """Load all messages from SQLite."""
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return []
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, text, created_at as time FROM memory ORDER BY id ASC"
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _search_memory(self, query, limit=10):
        """Search memory by keyword."""
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return []
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, text, created_at as time FROM memory WHERE text LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _get_last_chat_preview(self, n=4, max_len=120):
        """Return a formatted string with the last n messages for the chat preview."""
        messages = self._load_memory()
        if not messages:
            return ""
        recent = messages[-n:]
        lines = []
        for msg in recent:
            role = msg.get("role", "")
            text = msg.get("text", "")
            label = "Tu" if role == "Usuario" else "Claudy"
            if len(text) > max_len:
                text = text[:max_len].rstrip() + "..."
            lines.append(f"{label}: {text}")
        return "\n\n".join(lines)

    def _save_memory_sqlite(self, role, text):
        """Save a message to SQLite (always runs)."""
        db_path = self._memory_db_path()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO memory (role, text) VALUES (?, ?)",
                (role, text),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
        self._prune_memory()
        self._save_count = getattr(self, "_save_count", 0) + 1
        if self._save_count % 50 == 0:
            self._compress_context()

    def _save_memory(self, role, text):
        """Save to SQLite + mirror to external provider + Obsidian vault if configured."""
        self._save_memory_sqlite(role, text)
        # Optional mirror to external provider
        try:
            cfg = self.load_claudy_config()
            if (cfg.get("memory", {}).get("provider") or "sqlite") != "sqlite":
                if not hasattr(self, "_mem_provider"):
                    try:
                        import memory_providers
                        self._mem_provider = memory_providers.get_provider(cfg, self)
                    except Exception:
                        self._mem_provider = None
                if self._mem_provider and not isinstance(self._mem_provider, type(self)):
                    try:
                        self._mem_provider.save(role, text)
                    except Exception:
                        pass
            # Mirror to Obsidian vault if configured
            vault = (cfg.get("obsidian", {}) or {}).get("vault", "")
            if vault and os.path.isdir(vault):
                try:
                    import obsidian_export as ox
                    ox.append_today(vault, role, text)
                except Exception as e:
                    print(f"[obsidian] error: {e}")
        except Exception:
            pass

    def _prune_memory(self):
        """Keep DB from growing infinitely large."""
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return
        try:
            conn = sqlite3.connect(db_path)
            total = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
            if total > MEMORY_MAX_MESSAGES * 4:
                # Archive old rows to memory_archive table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_archive (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        role TEXT, text TEXT, created_at TEXT
                    )
                """)
                excess = total - MEMORY_MAX_MESSAGES * 2
                conn.execute("""
                    INSERT INTO memory_archive (role, text, created_at)
                    SELECT role, text, created_at FROM memory ORDER BY id ASC LIMIT ?
                """, (excess,))
                conn.execute("DELETE FROM memory WHERE id IN (SELECT id FROM memory ORDER BY id ASC LIMIT ?)", (excess,))
                conn.commit()
            conn.close()
        except Exception:
            pass

    def _build_memory_context(self):
        messages = self._load_memory()
        if not messages:
            return ""
        recent = messages[-MEMORY_CONTEXT_MESSAGES * 2:]
        context_parts = []
        total_chars = 0
        for msg in reversed(recent):
            line = f"{msg['role']}: {msg['text']}\n"
            if total_chars + len(line) > MEMORY_CONTEXT_CHARS:
                break
            context_parts.insert(0, line)
            total_chars += len(line)
        chat_context = "[Contexto de conversaciones anteriores]\n" + "".join(context_parts) + "\n[Fin del contexto]\n\n" if context_parts else ""

        # Add compressed summaries if available
        try:
            db_path = self._memory_db_path()
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                summaries = conn.execute(
                    "SELECT text FROM memory_summaries ORDER BY id DESC LIMIT 3"
                ).fetchall()
                conn.close()
                if summaries:
                    sum_text = "\n".join(s[0] for s in summaries)
                    chat_context += f"[Historial resumido]\n{sum_text}\n[/Historial resumido]\n\n"
        except Exception:
            pass

        # Add recent Obsidian context to memory
        obs_context = ""
        try:
            vault = self._get_obsidian_vault()
            if vault:
                md_files = []
                for root, dirs, files in os.walk(vault):
                    if '.obsidian' in dirs:
                        dirs.remove('.obsidian')
                    for f in files:
                        if f.endswith('.md'):
                            fpath = os.path.join(root, f)
                            md_files.append((fpath, os.path.getmtime(fpath)))
                
                if md_files:
                    md_files.sort(key=lambda x: x[1], reverse=True)
                    obs_parts = []
                    obs_chars = 0
                    for fpath, _ in md_files[:3]:
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            note_name = os.path.basename(fpath)
                            snippet = f"--- Nota: {note_name} ---\n{content}\n"
                            if obs_chars + len(snippet) > 4000:
                                snippet = snippet[:4000 - obs_chars] + "...\n"
                            obs_parts.append(snippet)
                            obs_chars += len(snippet)
                            if obs_chars >= 4000:
                                break
                        except Exception:
                            continue
                    
                    if obs_parts:
                        obs_context = "[Contexto de notas recientes en Obsidian]\n" + "".join(obs_parts) + "\n[Fin de notas de Obsidian]\n\n"
        except Exception as e:
            print(f"Error reading Obsidian context: {e}")

        return chat_context + obs_context

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
            "Archivos → /leer <ruta>     |  /buscar_archivo <nombre>   |  /descargar <url>\n"
            "Sistema  → /ejecutar <cmd>  |  /apps  |  /procesos  |  /disco\n"
            "Apps     → /instalar <app>\n"
            "Memoria  → /recordar <nota> |  /checkpoint  |  /rollback\n"
            "Skills   → /skills  |  /aprender <nombre>  |  /skill eliminar <nombre>\n"
            "Tareas   → /delegar <tarea> (subagente)  |  /kanban add/move/list\n"
            "Conexión → /vincular <id> (Telegram)  |  /vincular_discord <id>\n\n"

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
    def _compress_context(self):
        """Summarize old messages to save token budget."""
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return
        try:
            conn = sqlite3.connect(db_path)
            total = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
            if total < MEMORY_MAX_MESSAGES * 3:
                conn.close()
                return
            # Find the oldest checkpoint to protect its range
            oldest_cp = conn.execute(
                "SELECT MIN(memory_id) FROM checkpoints"
            ).fetchone()[0]
            # Keep last 200 messages, but protect checkpointed messages
            keep = MEMORY_MAX_MESSAGES * 2
            if oldest_cp:
                # Don't delete messages that are part of any checkpoint
                conn.close()
                return  # Skip compression if checkpoints exist (simpler approach)
            old = conn.execute(
                "SELECT id, role, text FROM memory ORDER BY id ASC LIMIT ?",
                (total - keep,),
            ).fetchall()
            if not old:
                conn.close()
                return
            summary = self._summarize_messages(old)
            if summary:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        text TEXT NOT NULL,
                        range_start INTEGER, range_end INTEGER,
                        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                    )
                """)
                conn.execute(
                    "INSERT INTO memory_summaries (text, range_start, range_end) VALUES (?, ?, ?)",
                    (summary, old[0][0], old[-1][0]),
                )
                ids = [row[0] for row in old]
                conn.executemany("DELETE FROM memory WHERE id = ?", [(i,) for i in ids])
                conn.commit()
            conn.close()
        except Exception:
            pass

    def _summarize_messages(self, messages):
        """Create a brief summary of messages."""
        if not messages:
            return ""
        parts = []
        for mid, role, text in messages:
            short = text[:200].replace("\n", " ") if text else ""
            parts.append(f"[{role}]: {short}")
        if len(parts) > 50:
            parts = parts[:50]
        return "Resumen de conversacion anterior: " + "; ".join(parts)

    # ------------------------------------------------------------------
    # Checkpoints / Rollback
    # ------------------------------------------------------------------
    def _create_checkpoint(self, label="manual"):
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return "No hay memoria activa para guardar un checkpoint."
        try:
            conn = sqlite3.connect(db_path)
            last_id = conn.execute("SELECT MAX(id) FROM memory").fetchone()[0]
            if last_id is None:
                conn.close()
                return "No hay mensajes en la memoria."
            conn.execute(
                "INSERT INTO checkpoints (label, memory_id) VALUES (?, ?)",
                (label, last_id),
            )
            conn.commit()
            conn.close()
            return f"Checkpoint '{label}' guardado en el mensaje #{last_id}."
        except Exception as e:
            return f"Error al guardar checkpoint: {e}"

    def _rollback_checkpoint(self, label=None):
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return "No hay memoria activa para hacer rollback."
        try:
            conn = sqlite3.connect(db_path)
            if label:
                cp = conn.execute(
                    "SELECT id, label, memory_id, created_at FROM checkpoints WHERE label = ? ORDER BY id DESC LIMIT 1",
                    (label,),
                ).fetchone()
            else:
                cp = conn.execute(
                    "SELECT id, label, memory_id, created_at FROM checkpoints ORDER BY id DESC LIMIT 1",
                ).fetchone()
            if not cp:
                conn.close()
                return "No hay checkpoints guardados. Usa /checkpoint para crear uno."
            # Delete all messages after the checkpoint
            conn.execute("DELETE FROM memory WHERE id > ?", (cp[2],))
            # Delete this checkpoint and any newer ones
            conn.execute("DELETE FROM checkpoints WHERE id >= ?", (cp[0],))
            conn.commit()
            conn.close()
            return f"Rollback al checkpoint '{cp[1]}' (mensaje #{cp[2]}, {cp[3]}). Se eliminaron los mensajes posteriores."
        except Exception as e:
            return f"Error en rollback: {e}"

    def _list_checkpoints(self):
        db_path = self._memory_db_path()
        if not os.path.exists(db_path):
            return "No hay memoria activa."
        try:
            conn = sqlite3.connect(db_path)
            cps = conn.execute(
                "SELECT id, label, memory_id, created_at FROM checkpoints ORDER BY id DESC LIMIT 10"
            ).fetchall()
            conn.close()
            if not cps:
                return "No hay checkpoints guardados."
            lines = ["Checkpoints:"]
            for cid, label, mid, cat in cps:
                lines.append(f"  [{cat}] {label} — mensaje #{mid}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    def _search_memory_cmd(self, query):
        results = self._search_memory(query)
        if not results:
            return f"No encontre '{query}' en la memoria."
        lines = [f"Resultados para '{query}':"]
        for r in results[:5]:
            text = r["text"][:200].replace("\n", " ")
            lines.append(f"  [{r['role']}] ({r['time']}): {text}...")
        return "\n".join(lines)

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
                            if now.hour == h and now.minute == m:
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

    def _list_cron_jobs(self):
        if not self._cron_jobs:
            return "No hay tareas programadas.\n\n/cron cada 30 min <mensaje>\n/cron a las 22:00 <mensaje>\n/cron list\n/cron delete <num>"
        lines = ["Tareas programadas:", "=" * 40]
        for i, j in enumerate(self._cron_jobs, 1):
            t = j["type"]
            if t == "interval":
                schedule = f"cada {j['interval_min']} min"
            else:
                schedule = f"diario a las {j.get('hour',0):02d}:{j.get('minute',0):02d}"
            enabled = "ON" if j.get("enabled", True) else "OFF"
            lines.append(f"  [{i}] [{enabled}] {schedule}: {j.get('message','')[:60]}")
        lines.append(f"\n/cron delete <num> para eliminar")
        return "\n".join(lines)

    def _delete_cron_job(self, idx):
        if idx < 0 or idx >= len(self._cron_jobs):
            return f"Numero invalido. Hay {len(self._cron_jobs)} tareas."
        removed = self._cron_jobs.pop(idx)
        self._save_cron_json()
        return f"Tarea eliminada: {removed.get('message','')[:60]}"

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

    def _try_handle_skill_action(self, prompt):
        lower = prompt.lower().strip()

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

        # VINCULAR Telegram: "/vincular <uid>"
        if lower.startswith("/vincular ") or lower.startswith("vincular "):
            uid = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._vincular_telegram_user(uid) if uid else "Uso: /vincular <ID_de_Telegram>"

        # VINCULAR Discord: "/vincular_discord <uid>"
        if lower.startswith("/vincular_discord ") or lower.startswith("vincular discord "):
            uid = prompt.split(None, 1)[1].strip() if " " in prompt.strip() else ""
            return True, self._vincular_discord_user(uid) if uid else "Uso: /vincular_discord <ID_de_Discord>"

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

        return False, ""

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
            else:
                response = self._call_remote_provider(model, "Eres Claudy. Analiza carpetas en Markdown.", "", analysis_prompt, config)
                # Extract text from any provider format
                if response.get("content") and isinstance(response["content"], list):
                    llm_answer = "\n".join(b.get("text", "") for b in response["content"] if b.get("type") == "text").strip()
                elif response.get("choices"):
                    llm_answer = response["choices"][0].get("message", {}).get("content", "").strip()
        except Exception as e:
            llm_answer = f"_(No se pudo consultar al LLM: {e})_"

        _status("Guardando en Obsidian...")
        folder_name = os.path.basename(os.path.abspath(folder_path)) or "raiz"
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        md_content = (
            f"**Carpeta:** `{folder_path}`\n"
            f"**Analizada:** {ts}\n"
            f"**Modelo:** {model}\n\n"
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
            result = "No encuentro tu vault de Obsidian. Configura 'obsidian.vaultPath' en ~/.claudy/config.json."

        word_count = len((llm_answer or "").split())
        char_count = len(llm_answer or "")
        completion_status = (
            f"\nAnalisis completado: {word_count} palabras, {char_count} caracteres.\n"
            f"MD total: {len(md_content)} caracteres."
        )

        _status("Listo.")
        full_text = (
            f"{result}{note_info}\n"
            f"{completion_status}\n\n"
            f"=== ANALISIS COMPLETO ===\n\n"
            f"{llm_answer or '_(sin respuesta del LLM)_'}"
        )
        return full_text

    def _get_obsidian_vault(self):
        """Find Obsidian vault path from config or common locations."""
        config_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
            vault = cfg.get("obsidian", {}).get("vaultPath", "")
            if vault and os.path.isdir(vault):
                return vault
        except Exception:
            pass
        # Common default locations.
        defaults = [
            os.path.join(os.path.expanduser("~"), "Obsidian"),
            os.path.join(os.path.expanduser("~"), "Documents", "Obsidian"),
            os.path.join(os.path.expanduser("~"), "OneDrive", "Obsidian"),
        ]
        for d in defaults:
            if os.path.isdir(d):
                return d
        return None

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
            return f"Nota creada en Obsidian: {fname}"
        except Exception as e:
            return f"Error creando nota: {e}"

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
    def _toggle_theme(self):
        """Toggle between dark and light theme."""
        global THEME
        if THEME["bg_bubble"] == "#161622":
            THEME.update({
                "bg_bubble": "#f5f5f5", "bg_bubble_border": "#e0e0e0",
                "bg_input": "#ffffff", "bg_input_border": "#d0d0d0",
                "text_primary": "#1a1a2e", "text_secondary": "#666680",
                "accent": "#5b4bd5", "accent_glow": "#e84393",
                "body": (80, 90, 200, 255), "body_dark": (50, 55, 120, 255),
                "screen": (240, 240, 250, 255), "outline": (30, 30, 50, 255),
                "eye_glow": (40, 180, 140, 255), "fin": (255, 160, 60, 255),
            })
            return "Tema cambiado a CLARO. Reinicia Claudy para aplicar."
        else:
            THEME.update({
                "bg_bubble": "#161622", "bg_bubble_border": "#2a2a40",
                "bg_input": "#0f0f1a", "bg_input_border": "#2a2a40",
                "text_primary": "#e8e8f0", "text_secondary": "#8a8aa3",
                "accent": "#7c6bff", "accent_glow": "#ff7edb",
                "body": (110, 120, 230, 255), "body_dark": (60, 65, 140, 255),
                "screen": (18, 18, 32, 255), "outline": (255, 255, 255, 255),
                "eye_glow": (120, 255, 210, 255), "fin": (255, 190, 100, 255),
            })
            return "Tema cambiado a OSCURO. Reinicia Claudy para aplicar."

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
            # Default to NES if nothing found but game name is like 'megaman'
            if any(x in game_name.lower() for x in ["megaman", "mario", "zelda", "metroid"]):
                console = "nes"
            else:
                return "No pude determinar para qué consola es el juego. Por favor especifica (ej: 'quiero jugar megaman de nes')."

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
                        resp = {
                            "id": f"chatcmpl-{int(time.time())}",
                            "object": "chat.completion",
                            "created": int(time.time()),
                            "model": data.get("model", "claudy"),
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

    def send_quick_message(self, prompt, _skip_skill_action=False):
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
        opencode = config["opencode"]
        base_url = opencode.get("baseUrl", "http://127.0.0.1:4096").rstrip("/")
        model = self._current_model or opencode.get("defaultModel", "deepseek-chat")
        # P3-2: Model router - swap to a category-specific model if router enabled
        model = _route_model(prompt, config, model)

        is_local = any(h in base_url for h in ("127.0.0.1", "localhost", "0.0.0.0"))
        context = self._build_memory_context()
        superpowers = self._get_superpowers()
        base_sys = config["agent"].get(
            "systemPrompt",
            "Eres Claudy, asistente personal de Felipe. Español natural, directo, sin formalidad. "
            "Clasifica la pregunta: saludo/definición → 1-3 líneas sin buscar. "
            "Dato actual → busca + da dato. Código → código exacto. "
            "Tarea multi-paso → anuncia plan, ejecuta cada paso. "
            "PROHIBIDO: 'como modelo de IA', preámbulos, markdown, derivar a otros sitios. "
            "Si no sabes, di 'No sé'. Resuelve, no informes."
        )
        local_skills = self._load_installed_skills()
        enhanced_sys = superpowers + local_skills + base_sys

        if is_local:
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
            response = self.request_json(endpoint, payload, config, timeout=90)
            if response.get("info", {}).get("error"):
                error = response["info"]["error"]
                raise RuntimeError(error.get("data", {}).get("message") or error.get("name") or "el oraculo se quedo dormido")
        else:
            # Multi-provider remote path
            response = self._call_remote_provider(model, enhanced_sys, context, prompt, config)

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

        answer = text or "El oraculo me dejo en visto..."
        self._save_memory("Claudy", answer)
        self._fire_hook("on_response", user=prompt, response=answer, source="llm")
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

    def _call_remote_provider(self, model, system_prompt, context, user_prompt, config):
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
                    return self._call_provider_api(provider, api_url, is_anthropic, is_openai_compat, actual_model, system_prompt, context, user_prompt, key, config)
                except Exception as e:
                    last_error = e
                    continue

        raise RuntimeError(f"All providers/keys exhausted. Last error: {last_error}")

    def _call_provider_api(self, provider, api_url, is_anthropic, is_openai_compat, model, system_prompt, context, user_prompt, key, config):
        """Make a single API call to a provider."""
        if is_anthropic:
            return self._call_anthropic(api_url, model, system_prompt, context, user_prompt, key, config)
        elif is_openai_compat:
            return self._call_openai_compat(api_url, model, system_prompt, context, user_prompt, key, config)
        else:
            return self._call_generic(api_url, model, system_prompt, context, user_prompt, key, provider)

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

    def _call_openai_compat(self, api_url, model, system_prompt, context, user_prompt, key, config=None):
        """Call OpenAI-compatible API."""
        endpoint = api_url
        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": user_prompt})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
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
        import urllib.request as r
        req = r.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with r.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
        if tools_enabled:
            choices = data.get("choices") or []
            if choices:
                msg = choices[0].get("message", {})
                tcs = msg.get("tool_calls") or []
                if tcs:
                    return self._execute_tool_calls_and_followup(tcs, payload, headers, endpoint, is_anthropic=False)
        return data

    def _call_anthropic(self, api_url, model, system_prompt, context, user_prompt, key, config=None):
        """Call Anthropic Messages API with prompt caching."""
        cache_control = {"type": "ephemeral"}
        payload = {
            "model": model,
            "system": [
                {"type": "text", "text": system_prompt, "cache_control": cache_control},
            ],
            "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
            "max_tokens": 1024,
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
        with r.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
        if tools_enabled and data.get("stop_reason") == "tool_use":
            tool_uses = [b for b in data.get("content", []) if b.get("type") == "tool_use"]
            if tool_uses:
                return self._execute_tool_calls_and_followup(tool_uses, payload, headers, api_url, is_anthropic=True)
        return data

    def _call_generic(self, api_url, model, system_prompt, context, user_prompt, key, provider):
        """Generic API call for providers like Google."""
        raise RuntimeError(f"Provider {provider} not fully implemented yet. Use OpenAI-compatible providers like DeepSeek or Anthropic.")

    # ==============================================================
    # TELEGRAM BOT
    # ==============================================================

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
    # DISCORD BOT
    # ==============================================================

    def _start_discord_if_configured(self):
        """Start the Discord bot if a token is configured."""
        config = self.load_claudy_config()
        discord_cfg = config.get("discord", {})
        token = discord_cfg.get("botToken", "")
        self._discord_allowed_users = set(discord_cfg.get("allowedUsers", []))
        if not token:
            return
        self._run_discord_bot(token)

    def _run_discord_bot(self, token):
        """Launch standalone Discord bot as a subprocess via the Gateway API."""
        script = os.path.join(SCRIPT_DIR, "bg_discord_bot.py")
        if not os.path.exists(script):
            print("[DiscordBot] Script not found:", script)
            return
        try:
            bot_log = os.path.join(os.path.expanduser("~"), ".claudy", "discord_bot.log")
            with open(bot_log, "a", encoding="utf-8") as log:
                log.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] Starting Discord bot...\n")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                [sys.executable, "-u", script],
                creationflags=flags,
                stdout=open(bot_log, "a", encoding="utf-8", buffering=1),
                stderr=open(bot_log, "a", encoding="utf-8", buffering=1),
            )
        except Exception as e:
            print(f"[DiscordBot] Error starting: {e}")

    def _vincular_discord_user(self, uid):
        """Add a Discord user ID to the allowed list."""
        uid = str(uid).strip()
        config_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
        if not os.path.exists(config_path):
            return "No encuentro la config."
        with open(config_path, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
        if "discord" not in config:
            config["discord"] = {}
        if "allowedUsers" not in config["discord"]:
            config["discord"]["allowedUsers"] = []
        if uid not in config["discord"]["allowedUsers"]:
            config["discord"]["allowedUsers"].append(uid)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self._discord_allowed_users.add(uid)
            return f"Usuario Discord {uid} vinculado correctamente."
        return f"Usuario Discord {uid} ya estaba vinculado."


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
    app = ClawdPet()
    app.mainloop()
