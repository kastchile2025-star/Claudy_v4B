"""Claudy super-powers: gestion de aplicaciones, instalacion y descargas.

Todas las funciones devuelven dict con {ok, message, ...} para uso programatico
o str legible para mostrar en el bubble.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request


# ============================================================
# WINGET (Windows Package Manager) — instalar/desinstalar
# ============================================================
def _run(cmd, timeout=600, shell=False):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=shell, encoding="utf-8", errors="replace")
        return (r.stdout or "") + (("\n" + r.stderr) if r.stderr else ""), r.returncode
    except subprocess.TimeoutExpired:
        return f"Timeout despues de {timeout}s", -1
    except Exception as e:
        return f"Error: {e}", -1


def install_app(name):
    """Install an app via winget. Returns the install log."""
    out, code = _run(["winget", "install", "-e", "--name", name, "--accept-source-agreements", "--accept-package-agreements", "--silent"], timeout=600)
    if code != 0:
        # Try by id as fallback
        out2, code2 = _run(["winget", "install", "-e", "--id", name, "--accept-source-agreements", "--accept-package-agreements", "--silent"], timeout=600)
        return out2 if code2 == 0 else (out + "\n\n--- intento por id ---\n" + out2)
    return out[-2500:] if out else f"Instalado: {name}"


def search_app(query):
    """Search winget for apps matching query."""
    out, code = _run(["winget", "search", query], timeout=60)
    if code != 0:
        return out or "Sin resultados"
    return out[:3000]


def uninstall_app(name):
    out, code = _run(["winget", "uninstall", "-e", "--name", name, "--silent"], timeout=300)
    return out[-2000:] if out else f"Desinstalado: {name}"


def list_installed(filter_text=""):
    out, _ = _run(["winget", "list"], timeout=60)
    if not filter_text:
        return out[-3000:] if out else "(vacio)"
    lines = [ln for ln in out.split("\n") if filter_text.lower() in ln.lower()]
    return "\n".join(lines[:50]) or f"Nada que coincida con '{filter_text}'"


# ============================================================
# Lanzar / cerrar apps
# ============================================================
KNOWN_APPS = {
    "chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "firefox": ["firefox.exe"],
    "spotify": ["Spotify.exe"],
    "vscode": ["Code.exe"],
    "code": ["Code.exe"],
    "notepad": ["notepad.exe"],
    "calculadora": ["calc.exe"],
    "calc": ["calc.exe"],
    "telegram": ["Telegram.exe"],
    "whatsapp": ["WhatsApp.exe"],
    "discord": ["Discord.exe"],
    "explorer": ["explorer.exe"],
    "paint": ["mspaint.exe"],
    "obs": ["obs64.exe"],
    "steam": ["steam.exe"],
    "zoom": ["Zoom.exe"],
    "teams": ["Teams.exe", "ms-teams.exe"],
    "outlook": ["OUTLOOK.EXE"],
}


_LAUNCH_DEBOUNCE = {}  # exe_basename -> last_launch_ts


def _is_process_running(exe_basename):
    """True if a process with this exe name is running."""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_basename}", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        return exe_basename.lower() in (r.stdout or "").lower()
    except Exception:
        return False


def launch_app(name):
    """Launch by alias, Start Menu, Downloads, Program Files (cascade) with cache.

    Skips launch if the target exe is already running or was launched in the
    last 3 seconds (debounce against duplicate intents from chat+voice+telegram).
    """
    name = (name or "").strip().strip('"\'')
    if not name:
        return "Que app quieres abrir?"
    low = name.lower()

    def _should_skip(exe):
        key = exe.lower()
        now = time.time()
        last = _LAUNCH_DEBOUNCE.get(key, 0)
        if now - last < 3.0:
            return True, f"Ignorado (lanzamiento duplicado <3s): {exe}"
        if _is_process_running(exe):
            _LAUNCH_DEBOUNCE[key] = now
            return True, f"{exe} ya esta corriendo. No abro otra instancia."
        _LAUNCH_DEBOUNCE[key] = now
        return False, ""

    # 1) Known aliases (canonical exe name) — quick path
    if low in KNOWN_APPS:
        for exe in KNOWN_APPS[low]:
            skip, msg = _should_skip(exe)
            if skip:
                return msg
            try:
                subprocess.Popen(["cmd", "/c", "start", "", exe], shell=False)
                return f"Abriendo: {exe}"
            except Exception:
                continue

    # 2) Resolve to an actual path (cache + cascade search)
    path = find_app_path(low)
    if path:
        skip, msg = _should_skip(os.path.basename(path))
        if skip:
            return msg
        try:
            os.startfile(path)
            return f"Abriendo: {os.path.basename(path)}\n{path}"
        except Exception as e:
            return f"Error abriendo {path}: {e}"

    # 3) URI handler fallback
    if ":" not in name and low in ("spotify", "telegram", "whatsapp"):
        try:
            subprocess.Popen(["cmd", "/c", "start", "", f"{low}:"], shell=False)
            return f"Abriendo {low} (URI)"
        except Exception:
            pass

    # 4) Last resort: hand off to Windows Start
    try:
        subprocess.Popen(["cmd", "/c", "start", "", name], shell=False)
        return f"No encontre {name} en mi indice. Intentando via Windows Start..."
    except Exception as e:
        return f"No encontre '{name}'. Error: {e}"


def close_app(name):
    """Force-kill processes by name."""
    name = name.strip().lower()
    targets = KNOWN_APPS.get(name, [name if name.endswith(".exe") else name + ".exe"])
    closed = []
    for t in targets:
        out, code = _run(["taskkill", "/F", "/IM", t], timeout=15)
        if code == 0 or "SUCCESS" in out.upper() or "CORRECTAMENTE" in out.upper():
            closed.append(t)
    return f"Cerrados: {', '.join(closed)}" if closed else f"No estaba corriendo: {name}"


def list_running(filter_text=""):
    out, _ = _run(["tasklist"], timeout=15)
    if not filter_text:
        return out[:3000]
    lines = [ln for ln in out.split("\n") if filter_text.lower() in ln.lower()]
    return "\n".join(lines[:30]) or f"Nada que coincida"


# ============================================================
# Descargas
# ============================================================
def _downloads_dir():
    p = os.path.join(os.path.expanduser("~"), "Downloads", "Claudy")
    os.makedirs(p, exist_ok=True)
    return p


def download_file(url, save_as=""):
    """Download URL to ~/Downloads/Claudy/. Auto-detects extension if not given."""
    if not url.startswith(("http://", "https://")):
        return f"URL invalida: {url}"
    if not save_as:
        # Try to extract from URL
        path = urllib.parse.urlparse(url).path
        save_as = os.path.basename(path) or f"descarga_{int(time.time())}"
    out_path = os.path.join(_downloads_dir(), save_as)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Claudy/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            with open(out_path, "wb") as f:
                while True:
                    chunk = r.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        size_mb = round(os.path.getsize(out_path) / (1024 * 1024), 2)
        return f"Descargado: {out_path} ({size_mb} MB)"
    except Exception as e:
        return f"Error descargando: {e}"


def download_and_open(url, save_as=""):
    """Download then open with system default."""
    msg = download_file(url, save_as)
    if msg.startswith("Descargado:"):
        path = msg.split("Descargado: ")[1].split(" (")[0]
        try:
            os.startfile(path)
        except Exception:
            pass
    return msg


def download_and_install(url):
    """Download an installer and run it silently if possible."""
    msg = download_file(url)
    if not msg.startswith("Descargado:"):
        return msg
    path = msg.split("Descargado: ")[1].split(" (")[0]
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".msi":
            subprocess.Popen(["msiexec", "/i", path, "/qb"])
            return f"Iniciado instalador MSI: {path}"
        if ext == ".exe":
            subprocess.Popen([path, "/S"], shell=False)
            return f"Iniciado instalador EXE (silent): {path}"
        if ext == ".zip":
            import zipfile
            extract_to = path[:-4]
            os.makedirs(extract_to, exist_ok=True)
            with zipfile.ZipFile(path) as z:
                z.extractall(extract_to)
            return f"Descomprimido en: {extract_to}"
        os.startfile(path)
        return f"Archivo abierto: {path}"
    except Exception as e:
        return f"Error: {e}"


# ============================================================
# FILESYSTEM SUPER-POWERS — analizar carpetas, leer archivos, buscar
# ============================================================
IGNORE_DIRS = {
    "node_modules", "__pycache__", ".git", ".venv", "venv", "env",
    "dist", "build", ".next", ".cache", ".idea", ".vscode",
    "target", "Pods", ".gradle", "DerivedData", ".pytest_cache",
}
TEXT_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".sass",
    ".md", ".txt", ".rst", ".log", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".conf", ".env", ".sh", ".ps1", ".bat", ".cmd",
    ".c", ".cpp", ".h", ".hpp", ".java", ".kt", ".swift", ".go", ".rs",
    ".rb", ".php", ".lua", ".sql", ".csv", ".tsv", ".xml", ".vue", ".svelte",
}
BINARY_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg",
    ".mp3", ".wav", ".ogg", ".mp4", ".avi", ".mkv",
    ".zip", ".tar", ".gz", ".7z", ".rar",
}


def _human_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} PB"


def folder_tree(path, max_depth=4, max_items=300):
    """Return ASCII tree of files/folders up to max_depth."""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return f"No es directorio: {path}"
    lines = [f"{os.path.basename(path) or path}/"]
    count = 0
    for r, dirs, files in os.walk(path):
        depth = r[len(path):].count(os.sep)
        if depth >= max_depth:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for d in sorted(dirs):
            count += 1
            if count > max_items:
                lines.append(f"... [+{max_items}+ items, truncado]")
                return "\n".join(lines)
            lines.append(f"{'  ' * (depth+1)}{d}/")
        for f in sorted(files):
            count += 1
            if count > max_items:
                lines.append(f"... [+{max_items}+ items, truncado]")
                return "\n".join(lines)
            lines.append(f"{'  ' * (depth+1)}{f}")
    return "\n".join(lines)


def folder_info(path):
    """Stats: total files, by ext, total size, biggest files, recent files."""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return f"No es directorio: {path}"
    total_files = 0
    total_size = 0
    by_ext = {}
    biggest = []
    recent = []
    for r, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in files:
            try:
                full = os.path.join(r, f)
                st = os.stat(full)
                total_files += 1
                total_size += st.st_size
                ext = os.path.splitext(f)[1].lower() or "(sin)"
                by_ext[ext] = by_ext.get(ext, 0) + 1
                biggest.append((st.st_size, full))
                recent.append((st.st_mtime, full))
            except Exception:
                pass
    biggest.sort(reverse=True)
    recent.sort(reverse=True)
    top_ext = sorted(by_ext.items(), key=lambda x: -x[1])[:10]
    lines = [
        f"Carpeta: {path}",
        f"Archivos totales: {total_files}",
        f"Tamano total: {_human_size(total_size)}",
        "",
        "Por extension (top 10):",
    ]
    for ext, n in top_ext:
        lines.append(f"  {ext:8s} {n}")
    lines.append("")
    lines.append("Archivos mas grandes:")
    for size, full in biggest[:5]:
        lines.append(f"  {_human_size(size):>10s}  {full[len(path)+1:]}")
    lines.append("")
    lines.append("Modificados recientes:")
    import datetime
    for mt, full in recent[:5]:
        when = datetime.datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M")
        lines.append(f"  {when}  {full[len(path)+1:]}")
    return "\n".join(lines)


def list_files(path, pattern="", recursive=True, max_results=100):
    """List files matching a glob pattern."""
    import fnmatch
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return f"No es directorio: {path}"
    results = []
    if recursive:
        for r, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
            for f in files:
                if not pattern or fnmatch.fnmatch(f, pattern):
                    rel = os.path.relpath(os.path.join(r, f), path)
                    results.append(rel)
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break
    else:
        for f in os.listdir(path):
            full = os.path.join(path, f)
            if os.path.isfile(full) and (not pattern or fnmatch.fnmatch(f, pattern)):
                results.append(f)
    return "\n".join(results) if results else "Sin resultados."


def find_in_files(path, query, max_hits=50, max_per_file=3):
    """Recursive text search (grep)."""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return f"No es directorio: {path}"
    hits = []
    qlow = query.lower()
    for r, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in TEXT_EXTS:
                continue
            full = os.path.join(r, f)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fp:
                    file_hits = 0
                    for ln_no, line in enumerate(fp, 1):
                        if qlow in line.lower():
                            rel = os.path.relpath(full, path)
                            hits.append(f"{rel}:{ln_no}: {line.strip()[:160]}")
                            file_hits += 1
                            if file_hits >= max_per_file:
                                break
                            if len(hits) >= max_hits:
                                return "\n".join(hits) + f"\n\n[+{max_hits} hits, truncado]"
            except Exception:
                pass
    return "\n".join(hits) if hits else f"Sin coincidencias para '{query}'."


def read_file(path, max_bytes=8000):
    """Read text file or extract from PDF/DOCX. Returns content (truncated)."""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        return f"No existe: {path}"
    if os.path.isdir(path):
        return f"Es directorio. Usa /tree o /analyze. {path}"
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            try:
                from pypdf import PdfReader
            except Exception:
                return "Instala: pip install pypdf"
            reader = PdfReader(path)
            parts = []
            for page in reader.pages[:30]:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    pass
            text = "\n".join(parts)
            return text[:max_bytes] + ("\n...[truncado]" if len(text) > max_bytes else "")
        if ext == ".docx":
            try:
                from docx import Document
            except Exception:
                return "Instala: pip install python-docx"
            doc = Document(path)
            text = "\n".join(p.text for p in doc.paragraphs)
            return text[:max_bytes] + ("\n...[truncado]" if len(text) > max_bytes else "")
        if ext in (".xlsx", ".xls"):
            try:
                import pandas as pd
                df = pd.read_excel(path)
                return df.head(50).to_string()[:max_bytes]
            except Exception as e:
                return f"Error excel: {e}"
        # Default: text
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read(max_bytes + 1)
        if len(data) > max_bytes:
            return data[:max_bytes] + "\n...[truncado]"
        return data
    except Exception as e:
        return f"Error leyendo: {e}"


def analyze_folder_summary(path, max_files_sample=20):
    """Build a structured summary (tree + key files content) for LLM consumption."""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return f"No es directorio: {path}"
    parts = ["=== ESTRUCTURA ===", folder_tree(path, max_depth=4, max_items=200)]
    parts.append("\n=== STATS ===")
    parts.append(folder_info(path))
    # Pick the most informative files: README, package.json, pyproject.toml, etc.
    priority = ("README.md", "README", "readme.md", "package.json", "pyproject.toml",
                "requirements.txt", "Cargo.toml", "go.mod", "tsconfig.json", "Makefile",
                "docker-compose.yml", "Dockerfile", ".env.example")
    found_priority = []
    for r, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in files:
            if f in priority and len(found_priority) < 6:
                full = os.path.join(r, f)
                found_priority.append(full)
        if len(found_priority) >= 6:
            break
    if found_priority:
        parts.append("\n=== ARCHIVOS CLAVE ===")
        for fp in found_priority:
            parts.append(f"\n--- {os.path.relpath(fp, path)} ---")
            parts.append(read_file(fp, max_bytes=2000))
    return "\n".join(parts)


def analyze_folder_with_llm(path, llm_callable):
    """Full analysis: build summary then ask LLM to interpret it.
    llm_callable: function(prompt: str) -> str
    """
    summary = analyze_folder_summary(path)
    if summary.startswith("No es"):
        return summary
    prompt = (
        f"Analiza esta carpeta y dame un reporte conciso:\n"
        f"- Tipo de proyecto / contenido\n"
        f"- Tecnologias detectadas\n"
        f"- Archivos importantes y su rol\n"
        f"- Estructura general\n"
        f"- Posibles issues / cosas a revisar\n\n"
        f"DATOS:\n{summary[:8000]}"
    )
    try:
        return llm_callable(prompt)
    except Exception as e:
        return f"Error LLM: {e}\n\n{summary[:3000]}"


# ============================================================
# Intent detection — para que Claudy responda lenguaje natural
# ============================================================
INTENT_PATTERNS = [
    # APPS
    (re.compile(r"^(?:instala(?:me|r)?|install|instalar)\s+(.+)$", re.I), "install"),
    (re.compile(r"^(?:desinstala(?:me|r)?|quitame|borra(?:me)?|uninstall)\s+(.+)$", re.I), "uninstall"),
    (re.compile(r"^(?:abre(?:me)?|abrir|lanza|launch|inicia|inicializa|ejecuta)\s+(.+)$", re.I), "launch"),
    (re.compile(r"^(?:cierra(?:me)?|cerrar|kill|mata|termina|cierralo)\s+(.+)$", re.I), "close"),
    (re.compile(r"^(?:descarga(?:me|r)?|baja(?:me|r)?|download)\s+(\S+)\s*$", re.I), "download"),
    (re.compile(r"^(?:descarga(?:me|r)?\s+e\s+instala(?:me|r)?|baja\s+e\s+instala)\s+(\S+)\s*$", re.I), "download_install"),
    (re.compile(r"^(?:busca|search)\s+(?:app(?:s)?\s+)?(.+?)\s*$", re.I), "search_app_maybe"),
    (re.compile(r"^(?:que\s+(?:apps|aplicaciones)\s+tengo|listame\s+(?:apps|aplicaciones)|/?installed)\s*$", re.I), "list_installed"),
    (re.compile(r"^(?:que\s+esta\s+corriendo|procesos|/?running)\s*$", re.I), "list_running"),
    # SCREENSHOT (envia la imagen, no solo describe)
    (re.compile(r"^(?:env[ií]a(?:me)?|m[aá]nda(?:me)?|toma(?:me)?|saca(?:me)?|hazme|haceme|hac[eé]me|p[aá]same|comp[aá]rteme|dame)\s+(?:un(?:a|os|as)?\s+|el\s+|la\s+|los\s+|las\s+)?(?:print(?:\s+de\s+pantalla)?|pantallazo|captura(?:\s+de\s+pantalla)?|screenshot|screencap|recorte)(?:\s+(?:por|al|via|con)\s+\w+)?\s*$", re.I), "screenshot_send"),
    (re.compile(r"^(?:print(?:\s+de\s+pantalla)?|pantallazo|captura(?:\s+de\s+pantalla)?|screenshot|recorte)\s*$", re.I), "screenshot_send"),
    # FILESYSTEM
    (re.compile(r"^(?:analiza(?:me)?|analizar|revisa(?:me)?|explora(?:me)?|escanea(?:me)?)\s+(?:la\s+)?(?:carpeta|directorio|folder)?\s*(.+)$", re.I), "analyze_folder"),
    (re.compile(r"^(?:que\s+hay\s+en|listame\s+(?:la\s+)?(?:carpeta|directorio)|listar?)\s+(.+)$", re.I), "list_folder"),
    (re.compile(r"^(?:arbol|tree|estructura)\s+(?:de\s+)?(.+)$", re.I), "tree"),
    (re.compile(r"^(?:info\s+de|stats?\s+de|tamano\s+de|peso\s+de)\s+(.+)$", re.I), "folder_info"),
    (re.compile(r"^(?:lee(?:me)?|leer|abre(?:me)?|mostrar?|cat)\s+(?:el\s+)?(?:archivo\s+)?[\"']?([A-Za-z]:[\\/].+?|[~/].+?|\S+\.\w+)[\"']?\s*$", re.I), "read_file"),
    (re.compile(r"^(?:busca(?:r)?|encuentra|find|grep)\s+[\"']?(.+?)[\"']?\s+en\s+(.+)$", re.I), "find_in"),
]


def detect_intent_filesystem_smart(prompt):
    """Special handling for 'busca X en Y' to return two args."""
    m = re.match(r"^(?:busca(?:r)?|encuentra|find|grep)\s+[\"']?(.+?)[\"']?\s+en\s+(.+)$", prompt.strip(), re.I)
    if m:
        return ("find_in", (m.group(1).strip(), m.group(2).strip()))
    return None


def detect_intent(prompt):
    """Returns (intent_name, arg_or_tuple) or (None, None)."""
    text = prompt.strip()
    # Special two-arg case: find_in
    fi = detect_intent_filesystem_smart(text)
    if fi:
        return fi
    for pat, intent in INTENT_PATTERNS:
        m = pat.match(text)
        if m:
            arg = m.group(1).strip() if m.groups() else ""
            if intent == "search_app_maybe":
                if any(k in arg.lower() for k in ("video", "youtube", "google", "noticia", "como", "que es")):
                    return None, None
                return "search_app", arg
            # Filter false positives for filesystem intents: require a path-like arg
            if intent in ("analyze_folder", "list_folder", "tree", "folder_info"):
                if not _looks_like_path(arg):
                    return None, None
            return intent, arg
    return None, None


def _looks_like_path(s):
    """Heuristic: True if s looks like a filesystem path."""
    if not s:
        return False
    s = s.strip().strip('"\'')
    # Windows: C:\ or C:/
    if re.match(r"^[A-Za-z]:[\\/]", s):
        return True
    # Unix-style
    if s.startswith(("/", "~", "./", "../")):
        return True
    # Has backslash or slash and looks like path
    if (("\\" in s or "/" in s) and not s.startswith("http")) and " " not in s.split("\\")[0].split("/")[0]:
        return True
    # Dot in current dir
    if s == ".":
        return True
    return False


def execute_intent(intent, arg):
    if intent == "install":
        return install_app(arg)
    if intent == "uninstall":
        return uninstall_app(arg)
    if intent == "launch":
        return launch_app(arg)
    if intent == "close":
        return close_app(arg)
    if intent == "download":
        return download_and_open(arg)
    if intent == "download_install":
        return download_and_install(arg)
    if intent == "search_app":
        return search_app(arg)
    if intent == "list_installed":
        return list_installed()
    if intent == "list_running":
        return list_running()
    if intent == "screenshot_send":
        return screenshot_for_send()
    # FILESYSTEM intents
    if intent == "analyze_folder":
        return analyze_folder_summary(arg)
    if intent == "list_folder":
        return list_files(arg, recursive=False)
    if intent == "tree":
        return folder_tree(arg)
    if intent == "folder_info":
        return folder_info(arg)
    if intent == "read_file":
        return read_file(arg)
    if intent == "find_in":
        # arg is tuple (query, path)
        if isinstance(arg, tuple):
            return find_in_files(arg[1], arg[0])
        return "Usa: 'busca X en C:/ruta'"
    return f"Intent desconocido: {intent}"


# ============================================================
# APP FINDER — busqueda en cascada (Start Menu, Downloads, Program Files)
# ============================================================
_APP_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".claudy", "app_index.json")


def _load_app_cache():
    try:
        with open(_APP_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_app_cache(cache):
    try:
        os.makedirs(os.path.dirname(_APP_CACHE_FILE), exist_ok=True)
        with open(_APP_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _match_name(query, candidate):
    """True if candidate matches query (substring, case-insensitive, no ext)."""
    q = query.lower().replace(" ", "").replace("-", "").replace("_", "")
    c = os.path.splitext(os.path.basename(candidate))[0].lower()
    c_norm = c.replace(" ", "").replace("-", "").replace("_", "")
    return q in c_norm or c_norm in q


def _scan_start_menu():
    """Return list of (name, target_path) from Start Menu shortcuts."""
    import pythoncom  # noqa: F401
    found = []
    appdata = os.environ.get("APPDATA", "")
    pdata = os.environ.get("PROGRAMDATA", "")
    roots = []
    if appdata:
        roots.append(os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs"))
    if pdata:
        roots.append(os.path.join(pdata, "Microsoft", "Windows", "Start Menu", "Programs"))
    for root in roots:
        if not os.path.isdir(root):
            continue
        for r, _, files in os.walk(root):
            for f in files:
                if f.lower().endswith(".lnk"):
                    lnk = os.path.join(r, f)
                    target = _resolve_lnk(lnk)
                    if target and target.lower().endswith(".exe") and os.path.exists(target):
                        found.append((os.path.splitext(f)[0], target))
    return found


def _resolve_lnk(lnk_path):
    """Resolve a .lnk shortcut to its target exe (Windows)."""
    try:
        import win32com.client  # type: ignore
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortcut(lnk_path)
        return sc.TargetPath
    except Exception:
        # Fallback via PowerShell (no pywin32 dependency)
        try:
            ps = (
                f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{lnk_path}');"
                "Write-Output $s.TargetPath"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=10,
            )
            return (r.stdout or "").strip()
        except Exception:
            return ""


def _scan_dir_for_exe(root, query, max_depth=3):
    """Walk root up to max_depth, return list of matching .exe paths."""
    matches = []
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        return matches
    for r, dirs, files in os.walk(root):
        depth = r[len(root):].count(os.sep)
        if depth >= max_depth:
            dirs[:] = []
        for f in files:
            if f.lower().endswith(".exe") and _match_name(query, f):
                # Skip uninstallers and updaters
                fl = f.lower()
                if any(s in fl for s in ("unins", "setup", "update", "crash")):
                    continue
                matches.append(os.path.join(r, f))
    return matches


def find_app_path(query):
    """Find an .exe matching query. Returns path or '' if not found.

    Cascade: cache -> Start Menu -> Downloads -> Program Files -> Desktop.
    Result cached in ~/.claudy/app_index.json.
    """
    query = (query or "").strip().lower()
    if not query:
        return ""

    cache = _load_app_cache()
    if query in cache and os.path.exists(cache[query]):
        return cache[query]

    # 1) Start Menu (.lnk targets) — fast, most reliable
    try:
        for name, target in _scan_start_menu():
            if _match_name(query, name) or _match_name(query, target):
                cache[query] = target
                _save_app_cache(cache)
                return target
    except Exception:
        pass

    # 2) Downloads + Desktop (user said anydesk is in Downloads)
    home = os.path.expanduser("~")
    for sub in ("Downloads", "Desktop"):
        d = os.path.join(home, sub)
        for hit in _scan_dir_for_exe(d, query, max_depth=4):
            cache[query] = hit
            _save_app_cache(cache)
            return hit

    # 3) Program Files (x86 + 64)
    for env in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        d = os.environ.get(env, "")
        if d:
            for hit in _scan_dir_for_exe(d, query, max_depth=3):
                cache[query] = hit
                _save_app_cache(cache)
                return hit

    # 4) LocalAppData (Spotify, Discord, Teams instalan aqui)
    lad = os.environ.get("LOCALAPPDATA", "")
    if lad:
        for hit in _scan_dir_for_exe(lad, query, max_depth=4):
            cache[query] = hit
            _save_app_cache(cache)
            return hit

    return ""


def rebuild_app_index():
    """Force rebuild of the Start Menu index. Returns count."""
    try:
        items = _scan_start_menu()
    except Exception as e:
        return f"Error escaneando Start Menu: {e}"
    cache = _load_app_cache()
    for name, target in items:
        key = name.lower().strip()
        cache[key] = target
    _save_app_cache(cache)
    return f"Indice reconstruido: {len(items)} apps en Start Menu, {len(cache)} en cache total."


def deep_find_app(query):
    """Fallback: deep scan of C:\\ for the exe. Slow but thorough."""
    query = (query or "").strip().lower()
    if not query:
        return ""
    for hit in _scan_dir_for_exe("C:\\", query, max_depth=6):
        cache = _load_app_cache()
        cache[query] = hit
        _save_app_cache(cache)
        return hit
    return ""


# ============================================================
# STARTUP FOLDER — shortcut en shell:startup (alternativa a RUN_KEY)
# ============================================================
def _startup_folder():
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup") if appdata else ""


def _claudy_startup_lnk_path():
    return os.path.join(_startup_folder(), "Claudy.lnk")


def enable_startup_shortcut(target_script=None, pythonw=True):
    """Create Claudy.lnk in shell:startup. Returns status message."""
    startup = _startup_folder()
    if not startup or not os.path.isdir(startup):
        return f"No encuentro la carpeta Startup: {startup}"
    if not target_script:
        # Default: pet.py in this same directory
        target_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "pet.py"))
    # Use pythonw.exe so no console window appears
    py_exe = sys.executable
    if pythonw:
        cand = py_exe.replace("python.exe", "pythonw.exe")
        if os.path.exists(cand):
            py_exe = cand
    lnk = _claudy_startup_lnk_path()
    ps = (
        f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{lnk}');"
        f"$s.TargetPath='{py_exe}';"
        f"$s.Arguments='\"{target_script}\"';"
        f"$s.WorkingDirectory='{os.path.dirname(target_script)}';"
        f"$s.WindowStyle=7;"
        f"$s.Save()"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and os.path.exists(lnk):
            return f"Autostart activado: {lnk}\n-> {py_exe} \"{target_script}\""
        return f"Error creando shortcut: {r.stderr or r.stdout}"
    except Exception as e:
        return f"Error: {e}"


def disable_startup_shortcut():
    lnk = _claudy_startup_lnk_path()
    if not os.path.exists(lnk):
        return "Autostart ya estaba desactivado (no hay Claudy.lnk en Startup)."
    try:
        os.remove(lnk)
        return "Autostart desactivado: Claudy.lnk eliminado de Startup."
    except Exception as e:
        return f"Error eliminando shortcut: {e}"


def is_startup_shortcut_enabled():
    return os.path.exists(_claudy_startup_lnk_path())


# ============================================================
# SCREENSHOT — captura monitor principal y devuelve path con marker
# ============================================================
def screenshot_for_send():
    """Capture primary monitor. Returns text with [CLAUDY_IMAGE:<path>] marker
    so the Telegram bot (or any consumer) can detect and forward the file."""
    try:
        from PIL import ImageGrab
    except Exception:
        return "Falta Pillow (pip install Pillow)"
    out_dir = os.path.join(os.path.expanduser("~"), ".claudy", "screenshots")
    os.makedirs(out_dir, exist_ok=True)
    fname = f"shot_{time.strftime('%Y%m%d_%H%M%S')}.png"
    fpath = os.path.join(out_dir, fname)
    try:
        # all_screens=False -> solo monitor principal (recorte requerido)
        img = ImageGrab.grab(all_screens=False)
        img.save(fpath, format="PNG", optimize=True)
        size_kb = round(os.path.getsize(fpath) / 1024, 1)
        return f"Listo, captura del monitor principal ({img.size[0]}x{img.size[1]}, {size_kb} KB)\n[CLAUDY_IMAGE:{fpath}]"
    except Exception as e:
        return f"Error capturando: {e}"
