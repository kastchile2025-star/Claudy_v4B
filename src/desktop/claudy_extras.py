"""All Phase-4 capabilities for Claudy bundled in one module.
Each function returns a string (response text) to keep handlers simple.
"""
import base64
import csv
import datetime
import io
import json
import os
import random
import re
import shutil
import smtplib
import socket
import string
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

# ============================================================
# UTIL
# ============================================================
def _data_dir(sub):
    d = os.path.join(os.path.expanduser("~"), ".claudy", sub)
    os.makedirs(d, exist_ok=True)
    return d


def _http_get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Claudy/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _http_post(url, data, headers=None, timeout=30):
    if isinstance(data, dict):
        data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers or {"Content-Type": "application/json", "User-Agent": "Claudy/1.0"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ============================================================
# BLOQUE A — Negocio Chile + util
# ============================================================
def ocr_image(path):
    """OCR de boleta/documento usando Pollinations vision (gratis)."""
    if not os.path.exists(path):
        return f"No existe: {path}"
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        payload = {
            "model": "openai",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extrae TODO el texto de esta imagen tal cual aparece. Si es una boleta o factura, identifica: total, IVA, RUT emisor, fecha, items."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }],
            "max_tokens": 1500,
        }
        data = _http_post("https://text.pollinations.ai/openai", payload, timeout=90)
        d = json.loads(data)
        return d.get("choices", [{}])[0].get("message", {}).get("content", "(sin texto)")
    except Exception as e:
        return f"Error OCR: {e}"


def iva_calc(amount, neto=False):
    """Calcula IVA Chile (19%). Si neto=True, amount es neto; sino amount es total."""
    a = float(amount)
    if neto:
        iva = a * 0.19
        return f"Neto: ${a:,.0f}\nIVA: ${iva:,.0f}\nTotal: ${a+iva:,.0f}"
    n = a / 1.19
    return f"Total: ${a:,.0f}\nIVA: ${a-n:,.0f}\nNeto: ${n:,.0f}"


def uf_utm():
    """UF y UTM actual via mindicador.cl (gratis)."""
    try:
        data = json.loads(_http_get("https://mindicador.cl/api"))
        uf = data.get("uf", {}).get("valor", 0)
        utm = data.get("utm", {}).get("valor", 0)
        usd = data.get("dolar", {}).get("valor", 0)
        eur = data.get("euro", {}).get("valor", 0)
        return f"UF: ${uf:,.2f}\nUTM: ${utm:,.0f}\nUSD: ${usd:,.2f}\nEUR: ${eur:,.2f}"
    except Exception as e:
        return f"Error: {e}"


def conv_currency(amount, src, dst):
    try:
        data = json.loads(_http_get(f"https://api.exchangerate-api.com/v4/latest/{src.upper()}"))
        rate = data.get("rates", {}).get(dst.upper())
        if not rate:
            return f"Sin tasa {src}->{dst}"
        return f"{amount} {src.upper()} = {amount * rate:,.2f} {dst.upper()}"
    except Exception as e:
        return f"Error: {e}"


def generate_quote_pdf(client, items_csv):
    """Genera PDF cotizacion. items_csv: 'item;cantidad;precio_unit' por linea."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception:
        return "Instala: pip install reportlab"
    out = os.path.join(_data_dir("cotizaciones"), f"cotizacion_{int(time.time())}.pdf")
    rows = []
    total = 0
    for line in items_csv.strip().split("\n"):
        parts = [p.strip() for p in line.split(";")]
        if len(parts) >= 3:
            try:
                desc = parts[0]
                cant = int(parts[1])
                precio = int(parts[2])
                rows.append((desc, cant, precio, cant * precio))
                total += cant * precio
            except Exception:
                pass
    c = canvas.Canvas(out, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "COTIZACION")
    c.setFont("Helvetica", 11)
    c.drawString(50, 725, f"Cliente: {client}")
    c.drawString(50, 710, f"Fecha: {datetime.date.today().isoformat()}")
    y = 670
    c.drawString(50, y, "Item")
    c.drawString(280, y, "Cant")
    c.drawString(340, y, "Precio")
    c.drawString(440, y, "Subtotal")
    y -= 20
    for desc, cant, precio, sub in rows:
        c.drawString(50, y, desc[:40])
        c.drawString(280, y, str(cant))
        c.drawString(340, y, f"${precio:,}")
        c.drawString(440, y, f"${sub:,}")
        y -= 18
    iva = int(total * 0.19)
    y -= 20
    c.drawString(340, y, "Neto:")
    c.drawString(440, y, f"${total:,}")
    y -= 16
    c.drawString(340, y, "IVA (19%):")
    c.drawString(440, y, f"${iva:,}")
    y -= 16
    c.setFont("Helvetica-Bold", 11)
    c.drawString(340, y, "Total:")
    c.drawString(440, y, f"${total + iva:,}")
    c.save()
    try:
        os.startfile(out)
    except Exception:
        pass
    return f"Cotizacion lista: {out}"


# Pomodoro state (singleton)
_pomodoro = {"running": False, "thread": None}
def pomodoro_start(minutes=25, on_done=None):
    if _pomodoro["running"]:
        return "Pomodoro ya corriendo."
    _pomodoro["running"] = True
    end = time.time() + minutes * 60
    def _run():
        while _pomodoro["running"] and time.time() < end:
            time.sleep(2)
        _pomodoro["running"] = False
        if callable(on_done):
            try:
                on_done(f"Pomodoro de {minutes} min terminado.")
            except Exception:
                pass
    t = threading.Thread(target=_run, daemon=True)
    _pomodoro["thread"] = t
    t.start()
    return f"Pomodoro de {minutes} min iniciado. Te aviso al terminar."


def pomodoro_stop():
    if not _pomodoro["running"]:
        return "No hay pomodoro corriendo."
    _pomodoro["running"] = False
    return "Pomodoro detenido."


# Shopping list (JSON file)
def _shop_path():
    return os.path.join(_data_dir("."), "shopping.json")


def shop_load():
    try:
        with open(_shop_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def shop_save(items):
    with open(_shop_path(), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def shop_add(item):
    items = shop_load()
    items.append({"id": int(time.time() * 1000) % 100000, "item": item, "done": False})
    shop_save(items)
    return f"Agregado: {item}"


def shop_list():
    items = shop_load()
    if not items:
        return "Lista vacia."
    return "\n".join(f"[{'x' if i['done'] else ' '}] {i['id']} {i['item']}" for i in items)


def shop_check(item_id):
    items = shop_load()
    for it in items:
        if str(it["id"]) == str(item_id):
            it["done"] = not it["done"]
            shop_save(items)
            return f"OK: {it['item']}"
    return f"ID no encontrado: {item_id}"


def shop_clear():
    shop_save([])
    return "Lista limpiada."


def send_email_smtp(to, subject, body, config):
    """Send email via SMTP. config must have: smtp_host, smtp_port, smtp_user, smtp_pass, from."""
    try:
        msg_text = f"Subject: {subject}\nFrom: {config['from']}\nTo: {to}\n\n{body}"
        with smtplib.SMTP_SSL(config["smtp_host"], int(config.get("smtp_port", 465))) as s:
            s.login(config["smtp_user"], config["smtp_pass"])
            s.sendmail(config["from"], [to], msg_text.encode("utf-8"))
        return f"Email enviado a {to}"
    except Exception as e:
        return f"Error: {e}"


def youtube_transcript(url):
    """Get YouTube transcript and return text."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:
        return "Instala: pip install youtube-transcript-api"
    m = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})", url)
    if not m:
        return "URL no parece de YouTube"
    vid = m.group(1)
    try:
        tr = YouTubeTranscriptApi.get_transcript(vid, languages=["es", "en"])
        text = " ".join(x["text"] for x in tr)
        return text[:8000]
    except Exception as e:
        try:
            tr = YouTubeTranscriptApi.list_transcripts(vid).find_transcript(["es","en","auto"]).fetch()
            return " ".join(x["text"] for x in tr)[:8000]
        except Exception:
            return f"Error: {e}"


def news_today(topic="chile"):
    """Lista headlines via Google News RSS (sin API)."""
    try:
        from xml.etree import ElementTree as ET
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(topic)}&hl=es-419&gl=CL&ceid=CL:es-419"
        data = _http_get(url)
        root = ET.fromstring(data)
        items = root.findall(".//item")[:10]
        lines = []
        for it in items:
            title = (it.findtext("title") or "")[:90]
            source = ""
            src = it.find("{http://www.w3.org/2005/Atom}source") or it.find("source")
            if src is not None:
                source = (src.text or "")[:30]
            lines.append(f"- {title} ({source})")
        return "\n".join(lines) or "Sin noticias."
    except Exception as e:
        return f"Error: {e}"


def track_package(carrier, code):
    """Apertura de tracking en navegador (no scrapea para evitar bloqueos)."""
    tpls = {
        "correos": f"https://www.correos.cl/seguimiento-en-linea?codigo={code}",
        "chilexpress": f"https://centrodeayuda.chilexpress.cl/seguimiento/{code}",
        "starken": f"https://www.starken.cl/seguimiento?codigo={code}",
        "dhl": f"https://www.dhl.com/cl-es/home/tracking/tracking-express.html?submit=1&tracking-id={code}",
        "fedex": f"https://www.fedex.com/fedextrack/?trknbr={code}",
        "ups": f"https://www.ups.com/track?tracknum={code}",
    }
    url = tpls.get(carrier.lower())
    if not url:
        return f"Carrier no soportado. Usa: {', '.join(tpls.keys())}"
    try:
        os.startfile(url)
    except Exception:
        pass
    return f"Abriendo: {url}"


# ============================================================
# BLOQUE B — Sistema Windows + QoL
# ============================================================
def screenshot_now():
    """Take screenshot and save."""
    try:
        import mss
        with mss.mss() as sct:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(_data_dir("screenshots"), f"{ts}.png")
            sct.shot(output=path)
            return path
    except Exception as e:
        return f"Error: {e}"


def set_volume(pct):
    """Set system volume 0-100."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
        vol.SetMasterVolumeLevelScalar(max(0, min(100, int(pct))) / 100.0, None)
        return f"Volumen: {pct}%"
    except Exception as e:
        return f"Error: {e}"


def get_volume():
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
        return f"Volumen actual: {int(vol.GetMasterVolumeLevelScalar() * 100)}%"
    except Exception as e:
        return f"Error: {e}"


def set_brightness(pct):
    try:
        import ctypes
        # Use WMI via PowerShell (more reliable than ctypes)
        cmd = f'powershell -NoProfile -Command "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {int(pct)})"'
        subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
        return f"Brillo: {pct}%"
    except Exception as e:
        return f"Error: {e}"


def paste_to_active_app(text):
    """Copy text and send Ctrl+V to whatever has focus."""
    try:
        import ctypes
        # Set clipboard
        import tkinter as tk
        root = tk._default_root or tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        time.sleep(0.1)
        # Send Ctrl+V via keybd_event
        user32 = ctypes.windll.user32
        VK_CONTROL = 0x11
        VK_V = 0x56
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 2, 0)
        user32.keybd_event(VK_CONTROL, 0, 2, 0)
        return "Pegado."
    except Exception as e:
        return f"Error: {e}"


def shutdown_at(minutes):
    try:
        subprocess.run(["shutdown", "/s", "/t", str(int(minutes) * 60)], shell=True)
        return f"Apagado programado en {minutes} min. Cancelar: /shutdown cancel"
    except Exception as e:
        return f"Error: {e}"


def shutdown_cancel():
    try:
        subprocess.run(["shutdown", "/a"], shell=True)
        return "Apagado cancelado."
    except Exception as e:
        return f"Error: {e}"


def set_wallpaper(path):
    try:
        import ctypes
        SPI_SETDESKWALLPAPER = 20
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, path, 3)
        return f"Wallpaper: {path}"
    except Exception as e:
        return f"Error: {e}"


def detect_fullscreen():
    """Returns True if a fullscreen app is currently in foreground (gaming mode trigger)."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        h = user32.GetForegroundWindow()
        if not h:
            return False
        # Rect
        from ctypes import wintypes
        rect = wintypes.RECT()
        user32.GetWindowRect(h, ctypes.byref(rect))
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        return (rect.right - rect.left) >= sw and (rect.bottom - rect.top) >= sh
    except Exception:
        return False


# ============================================================
# BLOQUE C — Vida + Educacion
# ============================================================
def weather_now(city="Santiago"):
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=3&lang=es"
        return _http_get(url).decode("utf-8")
    except Exception as e:
        return f"Error: {e}"


def weather_forecast(city="Santiago"):
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?lang=es&n&Q&T"
        return _http_get(url).decode("utf-8")[:2000]
    except Exception as e:
        return f"Error: {e}"


# Ambient sounds (open URL to pre-curated free streams)
def ambient_play(sound):
    urls = {
        "lluvia": "https://www.youtube.com/watch?v=mPZkdNFkNps",
        "cafe": "https://www.youtube.com/watch?v=h2zkV-l_TbY",
        "bosque": "https://www.youtube.com/watch?v=eKFTSSKCzWA",
        "blanco": "https://www.youtube.com/watch?v=nMfPqeZjc2c",
        "mar": "https://www.youtube.com/watch?v=Nq3xZirxqyw",
    }
    url = urls.get(sound.lower())
    if not url:
        return f"Sonidos: {', '.join(urls.keys())}"
    try:
        os.startfile(url)
    except Exception:
        pass
    return f"Reproduciendo {sound}..."


# Routes: opens Google Maps
def route_to(destination, origin="mi ubicacion"):
    try:
        url = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(origin)}&destination={urllib.parse.quote(destination)}"
        os.startfile(url)
        return f"Abriendo ruta a: {destination}"
    except Exception as e:
        return f"Error: {e}"


# ============================================================
# BLOQUE D — Generacion + Analisis
# ============================================================
def video_generate(prompt):
    """Pollinations video (limited). Returns URL to download."""
    try:
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?model=video&width=1024&height=576"
        return f"Pollinations no soporta video estable aun. Genero imagen animada via prompt cinematic:\n{url}"
    except Exception as e:
        return f"Error: {e}"


def mermaid_render(code):
    """Save mermaid code and open render URL."""
    try:
        encoded = base64.urlsafe_b64encode(code.encode("utf-8")).decode("ascii").rstrip("=")
        url = f"https://mermaid.ink/img/{encoded}?type=png"
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(_data_dir("diagrams"), f"mermaid_{ts}.png")
        with open(out, "wb") as f:
            f.write(_http_get(url, timeout=30))
        os.startfile(out)
        return f"Diagrama: {out}"
    except Exception as e:
        return f"Error: {e}"


def generate_pdf_report(title, body):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    except Exception:
        return "Instala: pip install reportlab"
    out = os.path.join(_data_dir("reports"), f"reporte_{int(time.time())}.pdf")
    doc = SimpleDocTemplate(out, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    for para in body.split("\n\n"):
        story.append(Paragraph(para.replace("\n", "<br/>"), styles["BodyText"]))
        story.append(Spacer(1, 8))
    doc.build(story)
    os.startfile(out)
    return f"PDF: {out}"


def csv_summary(path):
    try:
        import pandas as pd
    except Exception:
        return "Instala: pip install pandas"
    if not os.path.exists(path):
        return f"No existe: {path}"
    df = pd.read_csv(path)
    out = []
    out.append(f"Filas: {len(df)}  Columnas: {len(df.columns)}")
    out.append(f"Columnas: {', '.join(df.columns)}")
    out.append("\nResumen numerico:")
    try:
        out.append(df.describe().to_string()[:2000])
    except Exception:
        pass
    out.append("\nPrimeras filas:")
    out.append(df.head(5).to_string()[:1500])
    return "\n".join(out)


def csv_plot(path, x, y):
    try:
        import pandas as pd
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return "Instala: pip install pandas matplotlib"
    df = pd.read_csv(path)
    if x not in df.columns or y not in df.columns:
        return f"Columnas no encontradas. Disponibles: {', '.join(df.columns)}"
    fig, ax = plt.subplots(figsize=(8, 5))
    df.plot(x=x, y=y, ax=ax)
    out = os.path.join(_data_dir("plots"), f"plot_{int(time.time())}.png")
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)
    os.startfile(out)
    return f"Grafico: {out}"


# Embeddings semantic search over memory
_embedder = None
def _get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        except Exception as e:
            return None
    return _embedder


def embed_search(query, messages, top_k=5):
    m = _get_embedder()
    if m is None:
        return "Embeddings no disponibles (instala: pip install sentence-transformers)"
    if not messages:
        return "Sin memoria."
    try:
        import numpy as np
        texts = [msg.get("text", "") for msg in messages]
        embs = m.encode(texts, show_progress_bar=False)
        q = m.encode([query], show_progress_bar=False)[0]
        sims = np.dot(embs, q) / (np.linalg.norm(embs, axis=1) * np.linalg.norm(q) + 1e-10)
        top = sims.argsort()[-top_k:][::-1]
        lines = []
        for i in top:
            role = messages[i].get("role", "")
            text = messages[i].get("text", "")[:200]
            lines.append(f"[{sims[i]:.2f}] {role}: {text}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


# ============================================================
# BLOQUE E — Seguridad + Voz + Web
# ============================================================
def gen_password(length=20, symbols=True):
    chars = string.ascii_letters + string.digits
    if symbols:
        chars += "!@#$%^&*()-_=+"
    return "".join(random.choice(chars) for _ in range(int(length)))


def _vault_path():
    return os.path.join(_data_dir("."), "vault.enc")


def _vault_key():
    """Derive key from machine + user. NOT cryptographically perfect but blocks casual access."""
    try:
        from cryptography.fernet import Fernet
        import hashlib
        seed = (os.environ.get("USERNAME", "") + socket.gethostname()).encode()
        h = hashlib.sha256(seed).digest()
        key = base64.urlsafe_b64encode(h)
        return Fernet(key)
    except Exception:
        return None


def vault_load():
    f = _vault_key()
    if not f or not os.path.exists(_vault_path()):
        return {}
    try:
        with open(_vault_path(), "rb") as file:
            enc = file.read()
        plain = f.decrypt(enc).decode("utf-8")
        return json.loads(plain)
    except Exception:
        return {}


def vault_save(data):
    f = _vault_key()
    if not f:
        return False
    enc = f.encrypt(json.dumps(data).encode("utf-8"))
    with open(_vault_path(), "wb") as file:
        file.write(enc)
    return True


def vault_set(name, value):
    v = vault_load()
    v[name] = value
    vault_save(v)
    return f"Guardado: {name}"


def vault_get(name):
    v = vault_load()
    if name not in v:
        return f"No existe: {name}"
    return v[name]


def vault_list():
    v = vault_load()
    if not v:
        return "Vault vacio."
    return "\n".join(f"- {k}" for k in sorted(v.keys()))


def vault_del(name):
    v = vault_load()
    if name in v:
        del v[name]
        vault_save(v)
        return f"Borrado: {name}"
    return f"No existe: {name}"


def phishing_check(text):
    """Heuristic + LLM. Looks for suspicious patterns."""
    suspicious = []
    urls = re.findall(r"https?://[^\s<>]+", text)
    for u in urls:
        if re.search(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+", u):
            suspicious.append(f"IP cruda: {u}")
        if re.search(r"-bank|verify|account|secure|login", u, re.I) and any(x in u for x in (".tk", ".ml", ".ga", ".cf", "-")):
            suspicious.append(f"URL sospechosa: {u}")
    triggers = ["verify your account", "verifique su cuenta", "urgent", "urgente", "click here", "act now", "limited time"]
    for t in triggers:
        if t in text.lower():
            suspicious.append(f"Frase tipica: '{t}'")
    if suspicious:
        return "POSIBLE PHISHING:\n" + "\n".join(f"- {s}" for s in suspicious)
    return "Sin indicadores obvios de phishing."


# ============================================================
# BLOQUE F — Hardware + stubs
# ============================================================
def system_info():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:" if os.name == "nt" else "/")
        batt = psutil.sensors_battery()
        out = [
            f"CPU: {cpu}%",
            f"RAM: {mem.percent}% ({mem.used // (1024**3)} / {mem.total // (1024**3)} GB)",
            f"Disco C: {disk.percent}% ({disk.used // (1024**3)} / {disk.total // (1024**3)} GB)",
        ]
        if batt:
            out.append(f"Bateria: {batt.percent}% {'(cargando)' if batt.power_plugged else ''}")
        return "\n".join(out)
    except Exception as e:
        return f"Error: {e}"


def webcam_snapshot():
    try:
        import cv2
    except Exception:
        return "Instala: pip install opencv-python"
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "No hay webcam."
        time.sleep(1)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            return "Error capturando."
        out = os.path.join(_data_dir("webcam"), f"snap_{int(time.time())}.png")
        cv2.imwrite(out, frame)
        os.startfile(out)
        return f"Foto: {out}"
    except Exception as e:
        return f"Error: {e}"
