"""Claudy super-powers: gestion de aplicaciones, instalacion y descargas.

Todas las funciones devuelven dict con {ok, message, ...} para uso programatico
o str legible para mostrar en el bubble.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
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
            except ImportError:
                import sys, subprocess
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
                    from pypdf import PdfReader
                except Exception as e:
                    return f"Falta pypdf y no se pudo auto-instalar: {e}"
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
            except ImportError:
                import sys, subprocess
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
                    from docx import Document
                except Exception as e:
                    return f"Falta python-docx y no se pudo auto-instalar: {e}"
            except Exception:
                return "Instala: pip install python-docx"
            doc = Document(path)
            text = "\n".join(p.text for p in doc.paragraphs)
            return text[:max_bytes] + ("\n...[truncado]" if len(text) > max_bytes else "")
        if ext in (".xlsx", ".xls"):
            try:
                import pandas as pd
            except ImportError:
                import sys, subprocess
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "openpyxl"])
                    import pandas as pd
                except Exception as e:
                    return f"Falta pandas/openpyxl y no se pudo auto-instalar: {e}"
            try:
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


def _clean_user_path(path):
    path = (path or "").strip().strip('"\'')
    natural = _natural_path_to_path(path)
    if natural:
        return natural
    path = _strip_named_prefix(path)
    aliases = {
        "desktop": os.path.expanduser("~/Desktop"),
        "escritorio": os.path.expanduser("~/Desktop"),
        "downloads": os.path.expanduser("~/Downloads"),
        "descargas": os.path.expanduser("~/Downloads"),
        "documents": os.path.expanduser("~/Documents"),
        "documentos": os.path.expanduser("~/Documents"),
    }
    low = path.lower()
    if low in aliases:
        return aliases[low]
    return os.path.abspath(os.path.expanduser(path))


def _normalize_label(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[.!?]+$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    for prefix in (
        "el ", "la ", "los ", "las ", "mi ", "mis ",
        "en el ", "en la ", "en mi ", "dentro de ",
        "carpeta ", "directorio ", "folder ",
    ):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text


_FUZZY_LOCATION_ALIASES = (
    ("desktop", "~/Desktop", ("desktop", "escritorio", "escritori")),
    ("downloads", "~/Downloads", ("downloads", "download", "dowloads", "dowload", "descargas", "descrgas", "descarga", "descrga")),
    ("documents", "~/Documents", ("documents", "document", "documentos", "documento", "docs")),
    ("home", "~", ("home", "inicio", "usuario", "user")),
    ("pictures", "~/Pictures", ("pictures", "picture", "imagenes", "imagen", "fotos", "foto")),
    ("music", "~/Music", ("music", "musica")),
    ("videos", "~/Videos", ("videos", "video")),
)


def _fuzzy_match_alias(label):
    """Return the home-relative path for a fuzzy-matched location label, or ''."""
    if not label:
        return ""
    for _, base, keys in _FUZZY_LOCATION_ALIASES:
        if label in keys:
            return os.path.expanduser(base)
    # Substring match (e.g. "carpeta dowload" -> contains "dowload")
    for _, base, keys in _FUZZY_LOCATION_ALIASES:
        for k in keys:
            if len(k) >= 4 and k in label:
                return os.path.expanduser(base)
    return ""


def _location_alias_path(location):
    location = (location or "").strip().strip('"\'')
    if not location:
        return ""
    norm = _normalize_label(location)
    hit = _fuzzy_match_alias(norm)
    if hit:
        return hit
    cleaned = location
    cleaned = re.sub(r"^(?:en\s+)?(?:el|la|mi|mis)\s+", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"^(?:carpeta|directorio|folder)\s+", "", cleaned, flags=re.I).strip()
    cleaned_norm = _normalize_label(cleaned)
    hit = _fuzzy_match_alias(cleaned_norm)
    if hit:
        return hit
    if _looks_like_explicit_path(cleaned):
        return os.path.abspath(os.path.expanduser(cleaned))
    if "\\" in cleaned or "/" in cleaned:
        return os.path.abspath(os.path.expanduser(cleaned))
    if _looks_like_explicit_path(norm):
        return os.path.abspath(os.path.expanduser(norm))
    return ""


def _looks_like_explicit_path(path):
    path = (path or "").strip().strip('"\'')
    if not path:
        return False
    if re.match(r"^[A-Za-z]:[\\/]", path):
        return True
    if path.startswith(("~", "./", "../", "/", "\\")):
        return True
    return False


def _strip_named_prefix(name):
    name = (name or "").strip().strip('"\'')
    name = re.sub(r"[.!?]+$", "", name).strip()
    name = re.sub(
        r"^(?:llamad[ao]|con\s+nombre|nombre|que\s+se\s+llame|llamarla|llamarlo)\s+",
        "",
        name,
        flags=re.I,
    ).strip()
    return name.strip('"\'')


def _safe_child_name(name):
    name = _strip_named_prefix(name)
    name = re.sub(r'[<>:"/\\|?*]+', "_", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name.strip(" .")


def _natural_path_to_path(raw):
    raw = (raw or "").strip().strip('"\'')
    if not raw:
        return ""
    if _looks_like_explicit_path(raw):
        return os.path.abspath(os.path.expanduser(raw))

    # "en el escritorio llamada pruebas"
    m = re.match(
        r"^(?:en|dentro\s+de)\s+(.+?)\s+(?:llamad[ao]|con\s+nombre|nombre|que\s+se\s+llame)\s+(.+)$",
        raw,
        re.I,
    )
    if m:
        base = _location_alias_path(m.group(1))
        name = _safe_child_name(m.group(2))
        if base and name:
            return os.path.join(base, name)

    # "llamada pruebas en el escritorio" or "pruebas en descargas"
    named = _strip_named_prefix(raw)
    m = re.match(r"^(.+?)\s+(?:en|dentro\s+de)\s+(.+)$", named, re.I)
    if m:
        base = _location_alias_path(m.group(2))
        name = _safe_child_name(m.group(1))
        if base and name:
            return os.path.join(base, name)

    direct_location = _location_alias_path(raw)
    if direct_location:
        return direct_location

    if "\\" in raw or "/" in raw:
        return os.path.abspath(os.path.expanduser(raw))

    # "llamada pruebas" -> relative to current working directory.
    named = _strip_named_prefix(raw)
    if named != raw:
        return os.path.abspath(os.path.expanduser(_safe_child_name(named)))
    return ""


def _artifact_marker(path):
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    return f"Ubicacion: {folder}\n[CLAUDY_PATH:{path}]"


def _resolve_existing_path(path):
    target = _clean_user_path(path)
    if not target:
        return ""
    if os.path.exists(target):
        return target
    return ""


def _unique_destination(dest):
    if not os.path.exists(dest):
        return dest
    base, ext = os.path.splitext(dest)
    i = 1
    while True:
        candidate = f"{base} ({i}){ext}"
        if not os.path.exists(candidate):
            return candidate
        i += 1


def _parse_two_paths(raw):
    raw = (raw or "").strip()
    for sep in (" -> ", " => ", " | "):
        if sep in raw:
            left, right = raw.split(sep, 1)
            return left.strip().strip('"\''), right.strip().strip('"\'')
    m = re.match(r"(.+?)\s+(?:a|hacia|en|dentro de|to)\s+(.+)$", raw, re.I)
    if m:
        return m.group(1).strip().strip('"\''), m.group(2).strip().strip('"\'')
    return raw.strip().strip('"\''), ""


def _prepare_copy_move_paths(src, dest):
    src_path = _resolve_existing_path(src)
    if not src_path:
        return "", "", f"No encuentro el origen: {src}"
    dest_path = _clean_user_path(dest)
    if not dest_path:
        return "", "", "Falta la ruta destino."
    if os.path.isdir(dest_path):
        dest_path = os.path.join(dest_path, os.path.basename(src_path))
    elif not os.path.splitext(os.path.basename(dest_path))[1] and os.path.isdir(os.path.dirname(dest_path) or "."):
        # Treat a destination without extension as a folder-like target when it exists.
        pass
    return src_path, _unique_destination(dest_path), ""


def search_local_files(query, root="", max_results=80):
    """Find files/folders by name on this PC. Defaults to the user's home folder."""
    query = (query or "").strip().strip('"\'')
    if not query:
        return "Dime que archivo o carpeta quieres buscar."
    root_path = _clean_user_path(root) if root else os.path.expanduser("~")
    if not os.path.isdir(root_path):
        return f"No es directorio: {root_path}"
    qlow = query.lower()
    results = []
    for r, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for name in sorted(dirs + files):
            if qlow in name.lower():
                full = os.path.join(r, name)
                try:
                    kind = "carpeta" if os.path.isdir(full) else "archivo"
                    size = "" if os.path.isdir(full) else f" {_human_size(os.path.getsize(full))}"
                    results.append(f"{kind}: {full}{size}")
                except Exception:
                    results.append(full)
                if len(results) >= int(max_results):
                    return "\n".join(results) + f"\n\n[truncado a {max_results} resultados]"
    return "\n".join(results) if results else f"Sin resultados para '{query}' en {root_path}."


def copy_path(src, dest):
    src_path, dest_path, err = _prepare_copy_move_paths(src, dest)
    if err:
        return err
    try:
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path)
        else:
            shutil.copy2(src_path, dest_path)
        return f"Copiado:\nOrigen: {src_path}\nDestino: {dest_path}\n{_artifact_marker(dest_path)}"
    except Exception as e:
        return f"Error copiando: {e}"


def move_path(src, dest):
    """Move is the filesystem equivalent of cut/paste. It never deletes extra targets."""
    src_path, dest_path, err = _prepare_copy_move_paths(src, dest)
    if err:
        return err
    try:
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        final_path = shutil.move(src_path, dest_path)
        return f"Cortado/movido:\nOrigen anterior: {src_path}\nDestino: {final_path}\n{_artifact_marker(final_path)}"
    except Exception as e:
        return f"Error moviendo: {e}"


_PENDING_DELETE = {}


def _delete_token(path):
    base = os.path.basename(path) or "ruta"
    return re.sub(r"[^A-Za-z0-9]+", "", base).upper()[:12] or "RUTA"


def _describe_delete_impact(path):
    if os.path.isdir(path):
        count = 0
        for _, _, files in os.walk(path):
            count += len(files)
            if count > 500:
                return "carpeta con mas de 500 archivos"
        return f"carpeta con {count} archivos"
    try:
        return f"archivo de {_human_size(os.path.getsize(path))}"
    except Exception:
        return "archivo/carpeta"


def request_delete_double_confirmation(path):
    target = _resolve_existing_path(path)
    if not target:
        return f"No encuentro la ruta a borrar: {path}"
    token = _delete_token(target)
    _PENDING_DELETE[token] = {"path": target, "stage": 1, "ts": time.time()}
    impact = _describe_delete_impact(target)
    return (
        "Borrado bloqueado por seguridad.\n"
        f"Ruta: {target}\n"
        f"Impacto: esto eliminaria {impact} y podria no recuperarse.\n\n"
        "Confirmacion 1 de 2 requerida. Si realmente es necesario, responde exactamente:\n"
        f"CONFIRMO BORRAR {token}"
    )


def confirm_delete(text):
    cleaned = (text or "").strip()
    m1 = re.match(r"^CONFIRMO BORRAR ([A-Z0-9]+)$", cleaned, re.I)
    if m1:
        token = m1.group(1).upper()
        pending = _PENDING_DELETE.get(token)
        if not pending:
            return "No hay una solicitud de borrado pendiente con ese codigo."
        pending["stage"] = 2
        target = pending["path"]
        return (
            "Confirmacion 1 recibida. Aun no borro nada.\n"
            f"Ruta: {target}\n"
            "Confirmacion 2 de 2 requerida. Esto es irreversible o dificil de recuperar.\n"
            f"Responde exactamente: CONFIRMO DEFINITIVO BORRAR {token}"
        )
    m2 = re.match(r"^CONFIRMO DEFINITIVO BORRAR ([A-Z0-9]+)$", cleaned, re.I)
    if m2:
        token = m2.group(1).upper()
        pending = _PENDING_DELETE.get(token)
        if not pending or pending.get("stage") != 2:
            return "Falta la primera confirmacion o no hay solicitud pendiente."
        target = pending["path"]
        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
            _PENDING_DELETE.pop(token, None)
            return f"Borrado ejecutado tras doble confirmacion: {target}"
        except Exception as e:
            return f"No pude borrar: {e}"
    return ""


def _file_backups_dir():
    d = os.path.join(os.path.expanduser("~"), ".claudy", "file_backups")
    os.makedirs(d, exist_ok=True)
    return d


def _snapshot_file(path):
    if not os.path.isfile(path):
        return ""
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(path))
    backup = os.path.join(_file_backups_dir(), f"{ts}__{safe_name}.bak")
    shutil.copy2(path, backup)
    return backup


def _is_text_editable(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in BINARY_EXTS:
        return False
    return not ext or ext in TEXT_EXTS


def parse_path_content_arg(raw):
    """Parse '<path> | <content>', '<path>\\n<content>', or '<path> con <content>'."""
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    if "\n" in raw:
        path, content = raw.split("\n", 1)
        return path.strip().strip('"\'').strip(), content
    if " | " in raw:
        path, content = raw.split(" | ", 1)
        return path.strip().strip('"\'').strip(), content
    match = re.match(
        r"(.+?)\s+(?:con(?:\s+el)?(?:\s+contenido)?|que diga|con texto)\s+(.+)$",
        raw,
        re.I,
    )
    if match:
        return match.group(1).strip().strip('"\''), match.group(2)
    return raw.strip().strip('"\''), ""


def create_folder(path):
    target = _clean_user_path(path)
    if not target:
        return "Falta la ruta de la carpeta."
    try:
        existed = os.path.isdir(target)
        os.makedirs(target, exist_ok=True)
        status = "Carpeta ya existia" if existed else "Carpeta creada"
        return f"{status}: {target}\n{_artifact_marker(target)}"
    except Exception as e:
        return f"Error creando carpeta: {e}"


def create_docx(path, content=""):
    """Create a .docx file with given content. Appends .docx if missing."""
    target = _clean_user_path(path)
    if not target:
        return "Falta la ruta del archivo."
    if not target.lower().endswith(".docx"):
        target += ".docx"
    try:
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
    except ImportError:
        import sys, subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
            from docx import Document
            from docx.shared import Inches, Pt, RGBColor
        except Exception as e:
            return f"Falta python-docx y no se pudo auto-instalar: {e}"
    except Exception:
        return "Falta python-docx (pip install python-docx)"
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        doc = Document()
        
        # Set professional standard 1-inch margins
        for section in doc.sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)
            
        # Define modern professional colors & typography
        # Base/Normal body style
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)
        font.color.rgb = RGBColor(0x33, 0x33, 0x33) # Elegant charcoal text
        
        # Style Heading 1
        h1_style = doc.styles['Heading 1']
        h1_font = h1_style.font
        h1_font.name = 'Georgia'
        h1_font.size = Pt(20)
        h1_font.bold = True
        h1_font.color.rgb = RGBColor(0x1F, 0x4E, 0x78) # Dark blue accent
        
        # Style Heading 2
        h2_style = doc.styles['Heading 2']
        h2_font = h2_style.font
        h2_font.name = 'Georgia'
        h2_font.size = Pt(14)
        h2_font.bold = True
        h2_font.color.rgb = RGBColor(0x2E, 0x75, 0xB6) # Medium blue accent
        
        # Style Heading 3
        h3_style = doc.styles['Heading 3']
        h3_font = h3_style.font
        h3_font.name = 'Georgia'
        h3_font.size = Pt(12)
        h3_font.bold = True
        h3_font.italic = True
        h3_font.color.rgb = RGBColor(0x56, 0x56, 0x56) # Charcoal/grey accent
        
        for line in (content or "").split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                doc.add_heading(stripped[2:], level=1)
            elif stripped.startswith("## "):
                doc.add_heading(stripped[3:], level=2)
            elif stripped.startswith("### "):
                doc.add_heading(stripped[4:], level=3)
            else:
                p = doc.add_paragraph(line)
                # Add elegant paragraph spacing
                p.paragraph_format.space_after = Pt(6)
                
        doc.save(target)
        size = os.path.getsize(target)
        return f"Archivo creado: {target}\nTamano: {size} bytes\n{_artifact_marker(target)}"
    except Exception as e:
        return f"Error creando docx: {e}"


def create_docx_with_images(path, content="", image_paths=None):
    """Create a .docx file with Markdown content and optionally embed local images."""
    target = _clean_user_path(path) if not os.path.isabs(path) else path
    if not target:
        return "Falta la ruta del archivo."
    if not target.lower().endswith(".docx"):
        target += ".docx"
    try:
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
    except ImportError:
        import sys, subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
            from docx import Document
            from docx.shared import Inches, Pt, RGBColor
        except Exception as e:
            return f"Falta python-docx y no se pudo auto-instalar: {e}"
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        doc = Document()

        # Professional margins
        for section in doc.sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1.25)
            section.right_margin = Inches(1.25)

        # Typography
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(11)
        font.color.rgb = RGBColor(0x33, 0x33, 0x33)

        h1_style = doc.styles["Heading 1"]
        h1_style.font.name = "Georgia"
        h1_style.font.size = Pt(20)
        h1_style.font.bold = True
        h1_style.font.color.rgb = RGBColor(0x1F, 0x4E, 0x78)

        h2_style = doc.styles["Heading 2"]
        h2_style.font.name = "Georgia"
        h2_style.font.size = Pt(14)
        h2_style.font.bold = True
        h2_style.font.color.rgb = RGBColor(0x2E, 0x75, 0xB6)

        h3_style = doc.styles["Heading 3"]
        h3_style.font.name = "Georgia"
        h3_style.font.size = Pt(12)
        h3_style.font.bold = True
        h3_style.font.italic = True
        h3_style.font.color.rgb = RGBColor(0x56, 0x56, 0x56)

        # Parse and write content
        for line in (content or "").split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                doc.add_heading(stripped[2:], level=1)
            elif stripped.startswith("## "):
                doc.add_heading(stripped[3:], level=2)
            elif stripped.startswith("### "):
                doc.add_heading(stripped[4:], level=3)
            elif stripped.startswith("- ") or stripped.startswith("* "):
                p = doc.add_paragraph(stripped[2:], style="List Bullet")
                p.paragraph_format.space_after = Pt(3)
            elif stripped.startswith("**") and stripped.endswith("**"):
                p = doc.add_paragraph()
                run = p.add_run(stripped.strip("*"))
                run.bold = True
                p.paragraph_format.space_after = Pt(4)
            else:
                p = doc.add_paragraph(line)
                p.paragraph_format.space_after = Pt(6)

        # Embed images if provided
        if image_paths:
            doc.add_page_break()
            doc.add_heading("Imágenes de Referencia", level=2)
            for img_path in (image_paths or []):
                if img_path and os.path.isfile(img_path):
                    try:
                        doc.add_picture(img_path, width=Inches(5.5))
                        cap = doc.add_paragraph(os.path.splitext(os.path.basename(img_path))[0].replace("_", " "))
                        cap.alignment = 1  # centered
                        cap.paragraph_format.space_after = Pt(12)
                    except Exception:
                        pass

        doc.save(target)
        size = os.path.getsize(target)
        return f"Archivo creado: {target}\nTamano: {size} bytes\n{_artifact_marker(target)}"
    except Exception as e:
        return f"Error creando docx: {e}"

def create_xlsx(path, data=None, title=""):
    """Create a styled .xlsx workbook.

    `data` can be:
      - list[list]: first row treated as header
      - dict with optional keys: sheets=[{name, headers, rows}], or {headers, rows}
      - list[dict]: rows; headers inferred from first dict
    """
    target = _clean_user_path(path)

    if not target:
        return "Falta la ruta del archivo."
    if not target.lower().endswith(".xlsx"):
        target += ".xlsx"
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        import sys, subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except Exception as e:
            return f"Falta openpyxl y no se pudo auto-instalar: {e}"
    except Exception:
        return "Falta openpyxl (pip install openpyxl)"
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        wb = Workbook()
        wb.remove(wb.active)

        # Normalize input into list of sheets [{name, headers, rows}]
        sheets = []
        if isinstance(data, dict) and "sheets" in data:
            sheets = data["sheets"]
        elif isinstance(data, dict) and "rows" in data:
            sheets = [{
                "name": data.get("name", title or "Hoja1"),
                "headers": data.get("headers") or [],
                "rows": data.get("rows") or [],
            }]
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = [[d.get(h, "") for h in headers] for d in data]
            sheets = [{"name": title or "Hoja1", "headers": headers, "rows": rows}]
        elif isinstance(data, list) and data and isinstance(data[0], list):
            sheets = [{"name": title or "Hoja1", "headers": data[0], "rows": data[1:]}]
        else:
            sheets = [{"name": title or "Hoja1", "headers": [], "rows": []}]

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="1F4E78")
        thin = Side(border_style="thin", color="BFBFBF")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        body_align = Alignment(vertical="top", wrap_text=True)
        zebra = PatternFill("solid", fgColor="F2F2F2")

        for sh in sheets:
            ws = wb.create_sheet(title=(sh.get("name") or "Hoja")[:31])
            headers = sh.get("headers") or []
            rows = sh.get("rows") or []
            if headers:
                ws.append(headers)
                for col_idx, _ in enumerate(headers, start=1):
                    cell = ws.cell(row=1, column=col_idx)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = center
                    cell.border = border
                ws.row_dimensions[1].height = 22
                ws.freeze_panes = "A2"
            for r_idx, row in enumerate(rows, start=(2 if headers else 1)):
                for c_idx, val in enumerate(row, start=1):
                    cell = ws.cell(row=r_idx, column=c_idx, value=val)
                    cell.alignment = body_align
                    cell.border = border
                    if r_idx % 2 == 0:
                        cell.fill = zebra
            # Auto-width
            ncols = max([len(headers)] + [len(r) for r in rows] + [0])
            for col_idx in range(1, ncols + 1):
                letter = get_column_letter(col_idx)
                max_len = 10
                for row_idx in range(1, ws.max_row + 1):
                    v = ws.cell(row=row_idx, column=col_idx).value
                    if v is not None:
                        max_len = max(max_len, min(50, len(str(v)) + 2))
                ws.column_dimensions[letter].width = max_len
            if headers:
                ws.auto_filter.ref = ws.dimensions

        if not wb.sheetnames:
            wb.create_sheet("Hoja1")
        wb.save(target)
        size = os.path.getsize(target)
        return f"Archivo creado: {target}\nTamano: {size} bytes\n{_artifact_marker(target)}"
    except Exception as e:
        return f"Error creando xlsx: {e}"


_PPTX_PALETTES = {
    "history":   {"accent": (0x6B, 0x4A, 0x2E), "accent2": (0xA0, 0x6E, 0x44), "bg": (0xF7, 0xF1, 0xE8), "ink": (0x2B, 0x1F, 0x12)},
    "nature":    {"accent": (0x2F, 0x6E, 0x3B), "accent2": (0x6E, 0xA8, 0x4F), "bg": (0xEF, 0xF6, 0xEB), "ink": (0x1B, 0x2E, 0x1B)},
    "tech":      {"accent": (0x12, 0x33, 0x6E), "accent2": (0x2E, 0x84, 0xE6), "bg": (0xEE, 0xF3, 0xFB), "ink": (0x0F, 0x1A, 0x35)},
    "business":  {"accent": (0x1F, 0x4E, 0x78), "accent2": (0x2E, 0x75, 0xB6), "bg": (0xF5, 0xF7, 0xFA), "ink": (0x1A, 0x1A, 0x1A)},
    "education": {"accent": (0x5B, 0x2E, 0x86), "accent2": (0x9B, 0x6E, 0xD3), "bg": (0xF5, 0xEE, 0xFB), "ink": (0x29, 0x18, 0x42)},
    "warm":      {"accent": (0xB0, 0x3A, 0x2E), "accent2": (0xE2, 0x7A, 0x3E), "bg": (0xFA, 0xF1, 0xE8), "ink": (0x33, 0x1B, 0x12)},
    "dark":      {"accent": (0xE6, 0xC2, 0x6F), "accent2": (0xB0, 0x8A, 0x3E), "bg": (0x15, 0x18, 0x21), "ink": (0xE8, 0xE6, 0xDE)},
    "minimal":   {"accent": (0x1A, 0x1A, 0x1A), "accent2": (0x6B, 0x6B, 0x6B), "bg": (0xFA, 0xFA, 0xFA), "ink": (0x1A, 0x1A, 0x1A)},
}


def _fetch_image_pollinations(query, out_path, width=1280, height=720, timeout=30):
    """Generate an AI image from a text prompt (free, no key). Returns path or ''."""
    try:
        prompt = urllib.parse.quote(query)
        url = f"https://image.pollinations.ai/prompt/{prompt}?width={width}&height={height}&nologo=true&model=flux"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Claudy/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        if len(data) < 1000:
            return ""
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path
    except Exception:
        return ""


def create_pptx(path, slides=None, title="", subtitle="", theme="business", images=True):
    """Create a styled .pptx presentation with optional AI-generated images per slide.

    `slides`: list of dicts. Each slide:
      { "title": str, "bullets": [str, ...], "body": str, "image_query": str }
    `theme`: key from _PPTX_PALETTES (history|nature|tech|business|education|warm|dark|minimal).
    `images`: if True, fetch one AI image per slide using `image_query` (or slide title as fallback).
    """
    target = _clean_user_path(path)
    if not target:
        return "Falta la ruta del archivo."
    if not target.lower().endswith(".pptx"):
        target += ".pptx"
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from pptx.dml.color import RGBColor
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.enum.text import PP_ALIGN
    except ImportError:
        import sys, subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "python-pptx"])
            from pptx import Presentation
            from pptx.util import Inches, Pt, Emu
            from pptx.dml.color import RGBColor
            from pptx.enum.shapes import MSO_SHAPE
            from pptx.enum.text import PP_ALIGN
        except Exception as e:
            return f"Falta python-pptx y no se pudo auto-instalar: {e}"
    except Exception:
        return "Falta python-pptx (pip install python-pptx)"

    palette = _PPTX_PALETTES.get(theme, _PPTX_PALETTES["business"])

    def C(rgb):
        return RGBColor(*rgb)

    ACCENT = C(palette["accent"])
    ACCENT2 = C(palette["accent2"])
    BG = C(palette["bg"])
    INK = C(palette["ink"])
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    bg_is_dark = sum(palette["bg"]) < 380
    cover_ink = WHITE if sum(palette["accent"]) < 450 else INK
    footer_color = RGBColor(0xBF, 0xBF, 0xBF) if bg_is_dark else RGBColor(0x88, 0x88, 0x88)

    img_dir = ""
    if images:
        img_dir = os.path.join(tempfile.gettempdir(), f"claudy_pptx_{int(time.time())}")
        os.makedirs(img_dir, exist_ok=True)

    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        SW, SH = prs.slide_width, prs.slide_height

        def _solid_rect(slide, left, top, width, height, color):
            shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
            shape.line.fill.background()
            shape.fill.solid()
            shape.fill.fore_color.rgb = color
            shape.shadow.inherit = False
            return shape

        def _add_text(slide, left, top, width, height, text, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT, font="Calibri"):
            box = slide.shapes.add_textbox(left, top, width, height)
            tf = box.text_frame
            tf.word_wrap = True
            tf.margin_left = Pt(4)
            tf.margin_right = Pt(4)
            p = tf.paragraphs[0]
            p.alignment = align
            run = p.add_run()
            run.text = text
            run.font.name = font
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color
            return box

        def _fetch(query, idx):
            if not images or not query:
                return ""
            safe = re.sub(r"[^A-Za-z0-9]+", "_", query)[:40] or f"img_{idx}"
            out = os.path.join(img_dir, f"{idx:02d}_{safe}.jpg")
            return _fetch_image_pollinations(query, out, width=1280, height=720)

        slides = slides or []

        # ---------- COVER ----------
        if title:
            blank = prs.slide_layouts[6]
            s = prs.slides.add_slide(blank)
            _solid_rect(s, 0, 0, SW, SH, BG)
            cover_q = (slides[0].get("image_query") if slides else "") or title
            cover_img = _fetch(f"{cover_q} cinematic editorial photography", 0)
            if cover_img:
                # Full-bleed image with darkened overlay
                s.shapes.add_picture(cover_img, 0, 0, width=SW, height=SH)
                overlay = _solid_rect(s, 0, 0, SW, SH, RGBColor(*palette["accent"]))
                overlay.fill.transparency = 0  # python-pptx doesn't expose alpha cleanly; emulate w/ panel
                # Instead overlay a translucent dark panel via lower-half gradient (simple band)
                band = _solid_rect(s, 0, Inches(4.2), SW, Inches(3.3), RGBColor(0, 0, 0))
                _set_shape_alpha(band, 55)
                # Side accent bar
                _solid_rect(s, 0, 0, Inches(0.45), SH, ACCENT2)
                _add_text(s, Inches(0.9), Inches(4.6), Inches(11.5), Inches(1.5),
                          title, size=52, bold=True, color=WHITE, font="Calibri")
                if subtitle:
                    _add_text(s, Inches(0.9), Inches(6.0), Inches(11.5), Inches(0.7),
                              subtitle, size=22, color=WHITE)
            else:
                _solid_rect(s, 0, 0, SW, SH, ACCENT)
                _solid_rect(s, 0, 0, Inches(0.5), SH, ACCENT2)
                _add_text(s, Inches(1.0), Inches(2.6), Inches(11.5), Inches(1.5),
                          title, size=52, bold=True, color=cover_ink)
                if subtitle:
                    _add_text(s, Inches(1.0), Inches(4.0), Inches(11.5), Inches(0.8),
                              subtitle, size=22, color=cover_ink)

        # ---------- CONTENT SLIDES ----------
        for idx, sl in enumerate(slides, start=1):
            blank = prs.slide_layouts[6]
            s = prs.slides.add_slide(blank)
            _solid_rect(s, 0, 0, SW, SH, BG)
            # Top accent bar
            _solid_rect(s, 0, 0, SW, Inches(0.25), ACCENT)
            # Side accent
            _solid_rect(s, 0, Inches(0.25), Inches(0.12), SH - Inches(0.25), ACCENT2)

            stitle = sl.get("title", "")
            bullets = sl.get("bullets") or []
            body = sl.get("body") or ""
            img_q = sl.get("image_query") or stitle
            img_path = _fetch(f"{img_q} editorial photography high quality", idx)

            if img_path:
                # Two-column layout: text 55% left, image 40% right
                img_w = Inches(5.2)
                img_h = Inches(5.4)
                img_left = SW - img_w - Inches(0.5)
                img_top = Inches(1.4)
                # Frame
                frame = _solid_rect(s, img_left - Emu(40000), img_top - Emu(40000),
                                    img_w + Emu(80000), img_h + Emu(80000), ACCENT)
                s.shapes.add_picture(img_path, img_left, img_top, width=img_w, height=img_h)
                text_left = Inches(0.6)
                text_w = img_left - Inches(0.6) - Inches(0.3)
            else:
                text_left = Inches(0.6)
                text_w = Inches(12.1)

            if stitle:
                _add_text(s, text_left, Inches(0.5), text_w, Inches(0.9),
                          stitle, size=30, bold=True, color=ACCENT)
                # Underline accent
                _solid_rect(s, text_left, Inches(1.35),
                            min(Inches(1.8), text_w), Inches(0.06), ACCENT2)

            top = Inches(1.7)
            if bullets:
                box = s.shapes.add_textbox(text_left, top, text_w, Inches(5.0))
                tf = box.text_frame
                tf.word_wrap = True
                for i, b in enumerate(bullets):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.alignment = PP_ALIGN.LEFT
                    p.space_after = Pt(10)
                    run = p.add_run()
                    run.text = f"•  {b}"
                    run.font.name = "Calibri"
                    run.font.size = Pt(18)
                    run.font.color.rgb = INK
            elif body:
                box = s.shapes.add_textbox(text_left, top, text_w, Inches(5.0))
                tf = box.text_frame
                tf.word_wrap = True
                for i, line in enumerate(body.split("\n")):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.space_after = Pt(6)
                    run = p.add_run()
                    run.text = line
                    run.font.name = "Calibri"
                    run.font.size = Pt(16)
                    run.font.color.rgb = INK

            # Footer
            _add_text(s, Inches(0.6), Inches(7.05), Inches(8.0), Inches(0.35),
                      title or "Claudy", size=10, color=footer_color)
            _add_text(s, Inches(11.5), Inches(7.05), Inches(1.5), Inches(0.35),
                      f"{idx} / {len(slides)}", size=10, color=footer_color, align=PP_ALIGN.RIGHT)

        if not prs.slides:
            blank = prs.slide_layouts[6]
            s = prs.slides.add_slide(blank)
            _solid_rect(s, 0, 0, SW, SH, BG)
            _solid_rect(s, 0, 0, SW, Inches(0.25), ACCENT)
            _add_text(s, Inches(0.7), Inches(3.0), Inches(12.0), Inches(1.0),
                      title or "Presentacion", size=40, bold=True, color=ACCENT)

        prs.save(target)
        size = os.path.getsize(target)
        return f"Archivo creado: {target}\nTamano: {size} bytes\n{_artifact_marker(target)}"
    except Exception as e:
        return f"Error creando pptx: {e}"


def _set_shape_alpha(shape, percent):
    """Apply alpha (0=opaque, 100=transparent) to a shape's solid fill via XML hack."""
    try:
        from pptx.oxml.ns import qn
        from lxml import etree
        sp = shape.fill._xPr
        # Find or create solidFill > srgbClr > alpha
        solidFill = sp.find(qn("a:solidFill"))
        if solidFill is None:
            return
        srgb = solidFill.find(qn("a:srgbClr"))
        if srgb is None:
            return
        # Remove any existing alpha
        for a in srgb.findall(qn("a:alpha")):
            srgb.remove(a)
        alpha_val = max(0, min(100000, int((100 - percent) * 1000)))
        alpha = etree.SubElement(srgb, qn("a:alpha"))
        alpha.set("val", str(alpha_val))
    except Exception:
        pass


def create_pdf(path, content=""):
    """Create a styled PDF document using ReportLab Platypus flowables."""
    target = _clean_user_path(path)
    if not target:
        return "Falta la ruta del archivo."
    if not target.lower().endswith(".pdf"):
        target += ".pdf"
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor
    except ImportError:
        import sys, subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.colors import HexColor
        except Exception as e:
            return f"Falta reportlab y no se pudo auto-instalar: {e}"
    except Exception:
        return "Falta reportlab (pip install reportlab)"
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        
        # Professional standard margins (0.75 in / 54pt)
        doc = SimpleDocTemplate(
            target,
            pagesize=letter,
            rightMargin=54, leftMargin=54,
            topMargin=54, bottomMargin=54
        )
        
        styles = getSampleStyleSheet()
        
        # Define premium matching corporate theme styles
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=24,
            leading=28,
            textColor=HexColor('#1F4E78'),
            spaceAfter=15
        )
        
        h1_style = ParagraphStyle(
            'DocH1',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=15,
            leading=18,
            textColor=HexColor('#2E75B6'),
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True
        )
        
        h2_style = ParagraphStyle(
            'DocH2',
            parent=styles['Heading3'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=15,
            textColor=HexColor('#565656'),
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=True
        )
        
        body_style = ParagraphStyle(
            'DocBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=HexColor('#333333'),
            spaceAfter=8
        )
        
        story = []
        
        lines = (content or "").split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, 6))
                continue
                
            if stripped.startswith("# "):
                story.append(Paragraph(stripped[2:], title_style))
                story.append(Spacer(1, 10))
            elif stripped.startswith("## "):
                story.append(Paragraph(stripped[3:], h1_style))
            elif stripped.startswith("### "):
                story.append(Paragraph(stripped[4:], h2_style))
            else:
                story.append(Paragraph(line, body_style))
                
        doc.build(story)
        size = os.path.getsize(target)
        return f"Archivo creado: {target}\nTamano: {size} bytes\n{_artifact_marker(target)}"
    except Exception as e:
        return f"Error creando pdf: {e}"


def write_file(path, content="", append=False):
    target = _clean_user_path(path)
    if not target:
        return "Falta la ruta del archivo."
    if os.path.isdir(target):
        return f"Es una carpeta, no un archivo: {target}"
    if not _is_text_editable(target):
        return f"No edito binarios desde aqui: {target}"
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        existed = os.path.exists(target)
        backup = _snapshot_file(target) if existed else ""
        mode = "a" if append else "w"
        with open(target, mode, encoding="utf-8", newline="") as f:
            f.write(content or "")
        verb = "Archivo actualizado" if existed else "Archivo creado"
        if append:
            verb = "Contenido agregado" if existed else "Archivo creado"
        size = os.path.getsize(target)
        lines = [f"{verb}: {target}", f"Tamano: {size} bytes"]
        if backup:
            lines.append(f"Backup: {backup}")
        lines.append(_artifact_marker(target))
        return "\n".join(lines)
    except Exception as e:
        return f"Error escribiendo archivo: {e}"


def append_file(path, content=""):
    return write_file(path, content, append=True)


def replace_in_file(path, old, new, max_replacements=0):
    target = _clean_user_path(path)
    old = "" if old is None else str(old)
    new = "" if new is None else str(new)
    if not target:
        return "Falta la ruta del archivo."
    if not old:
        return "Falta el texto a reemplazar."
    if not os.path.isfile(target):
        return f"No existe el archivo: {target}"
    if not _is_text_editable(target):
        return f"No edito binarios desde aqui: {target}"
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
        count = data.count(old)
        if count == 0:
            return f"No encontre el texto indicado en: {target}\n{_artifact_marker(target)}"
        backup = _snapshot_file(target)
        limit = int(max_replacements or 0)
        updated = data.replace(old, new, limit if limit > 0 else -1)
        replaced = min(count, limit) if limit > 0 else count
        with open(target, "w", encoding="utf-8", newline="") as f:
            f.write(updated)
        lines = [
            f"Archivo editado: {target}",
            f"Reemplazos: {replaced}",
        ]
        if backup:
            lines.append(f"Backup: {backup}")
        lines.append(_artifact_marker(target))
        return "\n".join(lines)
    except Exception as e:
        return f"Error editando archivo: {e}"


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
    (re.compile(r"^(?:desinstala(?:me|r)?|uninstall)\s+(.+)$", re.I), "uninstall"),
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
    (re.compile(r"^(?:busca(?:me|r)?|encuentra|find)\s+(?:el\s+|la\s+)?(?:archivo|carpeta|file|folder)?\s*[\"']?(.+?)[\"']?\s+(?:en\s+)?(?:este\s+pc|mi\s+pc|la\s+computadora|el\s+computador|todo\s+el\s+pc)\s*$", re.I), "search_local"),
    (re.compile(r"^(?:analiza(?:me)?|analizar|revisa(?:me)?|explora(?:me)?|escanea(?:me)?)\s+(?:la\s+)?(?:carpeta|directorio|folder)?\s*(.+)$", re.I), "analyze_folder"),
    (re.compile(r"^(?:que\s+hay\s+en|listame\s+(?:la\s+)?(?:carpeta|directorio)|listar?)\s+(.+)$", re.I), "list_folder"),
    (re.compile(r"^(?:arbol|tree|estructura)\s+(?:de\s+)?(.+)$", re.I), "tree"),
    (re.compile(r"^(?:info\s+de|stats?\s+de|tamano\s+de|peso\s+de)\s+(.+)$", re.I), "folder_info"),
    (re.compile(r"^(?:lee(?:me)?|leer|abre(?:me)?|mostrar?|cat)\s+(?:el\s+)?(?:archivo\s+)?[\"']?([A-Za-z]:[\\/].+?|[~/].+?|\S+\.\w+)[\"']?\s*$", re.I), "read_file"),
    (re.compile(r"^(?:busca(?:r)?|encuentra|find|grep)\s+[\"']?(.+?)[\"']?\s+en\s+(.+)$", re.I), "find_in"),
]


def detect_intent_filesystem_smart(prompt):
    """Special handling for 'busca X en Y' to return two args."""
    text = prompt.strip()

    delete_confirm = confirm_delete(text)
    if delete_confirm:
        return ("delete_confirm", delete_confirm)

    create_verb = r"(?:cr[eé]a(?:me|r)?|nuevo|nueva|genera|haz(?:me)?|hacer)"

    m = re.match(
        r"^(?:copia(?:me|r)?|duplic(?:a|ar)|copy)\s+(.+)$",
        text,
        re.I,
    )
    if m:
        src, dest = _parse_two_paths(m.group(1))
        return ("copy_path", (src, dest))

    m = re.match(
        r"^(?:corta(?:me|r)?|mueve(?:me|r)?|traslada(?:me|r)?|move|cut)\s+(.+)$",
        text,
        re.I,
    )
    if m:
        src, dest = _parse_two_paths(m.group(1))
        return ("move_path", (src, dest))

    m = re.match(
        r"^(?:borra(?:me|r)?|elimina(?:me|r)?|delete|remove|quita(?:me|r)?)\s+(.+)$",
        text,
        re.I,
    )
    if m:
        return ("request_delete", m.group(1).strip())

    # "dentro de X / en X, crea (una) carpeta Y"
    m = re.match(
        rf"^(?:dentro\s+de|en)\s+(.+?)[,\s]+{create_verb}\s+(?:un\s+|una\s+|el\s+|la\s+)?(?:carpeta|directorio|folder)\s+(.+)$",
        text,
        re.I,
    )
    if m:
        location = m.group(1).strip()
        name = m.group(2).strip()
        return ("create_folder", f"{name} en {location}")

    # "dentro de X / en X, crea (un) archivo Y[ con Z]"
    m = re.match(
        rf"^(?:dentro\s+de|en)\s+(.+?)[,\s]+{create_verb}\s+(?:un\s+|una\s+|el\s+|la\s+)?(?:archivo|file)\s+(.+)$",
        text,
        re.I,
    )
    if m:
        location = m.group(1).strip()
        rest = m.group(2).strip()
        fname, content = parse_path_content_arg(rest)
        return ("write_file", (f"{fname} en {location}", content, False))

    m = re.match(
        rf"^{create_verb}\s+(?:un\s+|una\s+|el\s+|la\s+)?(?:carpeta|directorio|folder)\s*$",
        text,
        re.I,
    )
    if m:
        return ("create_folder", "")

    m = re.match(
        rf"^{create_verb}\s+(?:un\s+|una\s+|el\s+|la\s+)?(?:carpeta|directorio|folder)\s+(.+)$",
        text,
        re.I,
    )
    if m:
        return ("create_folder", m.group(1).strip())

    m = re.match(
        rf"^{create_verb}\s+(?:un\s+|una\s+|el\s+|la\s+)?(?:archivo|file)\s+(.+)$",
        text,
        re.I,
    )
    if m:
        path, content = parse_path_content_arg(m.group(1).strip())
        return ("write_file", (path, content, False))

    m = re.match(
        r"^(?:escribe|guarda|guardar|save)\s+(.+?)\s+(?:en|dentro de)\s+(?:el\s+)?(?:archivo\s+|file\s+)?(.+)$",
        text,
        re.I,
    )
    if m and _looks_like_file_target(m.group(2)):
        return ("write_file", (m.group(2).strip(), m.group(1), False))

    m = re.match(
        r"^(?:agrega|anade|append)\s+(.+?)\s+(?:al|a)\s+(?:el\s+)?(?:archivo\s+|file\s+)?(.+)$",
        text,
        re.I,
    )
    if m and _looks_like_file_target(m.group(2)):
        return ("append_file", (m.group(2).strip(), m.group(1)))

    m = re.match(
        r"^(?:reemplaza|replace)\s+[\"']?(.+?)[\"']?\s+(?:por|with)\s+[\"']?(.+?)[\"']?\s+(?:en|in)\s+(?:el\s+)?(?:archivo\s+|file\s+)?(.+)$",
        text,
        re.I,
    )
    if m and _looks_like_file_target(m.group(3)):
        return ("replace_in_file", (m.group(3).strip(), m.group(1), m.group(2)))

    m = re.match(
        r"^(?:edita|editar|modifica|modificar)\s+(?:el\s+)?(?:archivo\s+|file\s+)?(.+?)\s+(?:reemplaza|cambia)\s+[\"']?(.+?)[\"']?\s+(?:por|a)\s+[\"']?(.+?)[\"']?$",
        text,
        re.I,
    )
    if m and _looks_like_file_target(m.group(1)):
        return ("replace_in_file", (m.group(1).strip(), m.group(2), m.group(3)))

    m = re.match(
        r"^(?:edita|editar|modifica|modificar)\s+(?:el\s+)?(?:archivo\s+|file\s+)?(.+?)\s+(?:con|contenido)\s+(.+)$",
        text,
        re.I,
    )
    if m and _looks_like_file_target(m.group(1)):
        return ("write_file", (m.group(1).strip(), m.group(2), False))

    m = re.match(r"^(?:busca(?:r)?|encuentra|find|grep)\s+[\"']?(.+?)[\"']?\s+en\s+(.+)$", text, re.I)
    if m:
        location = m.group(2).strip()
        if re.match(r"^(?:este\s+pc|mi\s+pc|la\s+computadora|el\s+computador|todo\s+el\s+pc)$", location, re.I):
            return ("search_local", m.group(1).strip())
        return ("find_in", (m.group(1).strip(), m.group(2).strip()))
    return None


def clean_politeness_prefixes(text):
    text = text.strip()
    prev = None
    while prev != text:
        prev = text
        # Remove Spanish/English politeness and query prefix wrappers
        text = re.sub(
            r"^(?:hola\s+claudy|hola|hey|claudy|oye|escucha|por\s+favor|puedes|podr[ií]as|quiero|necesito|podemos|vamos\s+a|ay[uú]dame\s+a|hazme\s+el\s+favor\s+de|me\s+gustar[ií]a\s+que\s+crearas|me\s+gustar[ií]a\s+crear|me\s+gustar[ií]a|crear[ií]as)\s+",
            "",
            text,
            flags=re.I
        ).strip()
    return text


def detect_intent(prompt):
    """Returns (intent_name, arg_or_tuple) or (None, None)."""
    text = prompt.strip()
    # Clean politeness and conversational wrappers
    cleaned = clean_politeness_prefixes(text)
    # Special two-arg case: find_in
    fi = detect_intent_filesystem_smart(cleaned)
    if fi:
        return fi
    # Also try matching on original text if cleaned didn't work
    fi_orig = detect_intent_filesystem_smart(text)
    if fi_orig:
        return fi_orig

    for pat, intent in INTENT_PATTERNS:
        m = pat.match(cleaned)
        if not m:
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
            # QCORE products are handled by pet.py's specialized launcher (with analysis)
            if intent == "launch":
                _qcore_names = [
                    "mission control", "missioncontrol", "mision control", "misioncontrol",
                    "smartstudent", "smart student", "roadix", "luxium",
                    "unitcore", "unit core", "campaign studio", "campaignstudio",
                ]
                if any(q in arg.lower() for q in _qcore_names):
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


def _looks_like_file_target(s):
    s = (s or "").strip().strip('"\'')
    if _looks_like_path(s):
        return True
    if os.path.splitext(s)[1]:
        return True
    if "\\" in s or "/" in s:
        return True
    return False


def execute_intent(intent, arg):
    if intent == "delete_confirm":
        return arg
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
    if intent == "search_local":
        return search_local_files(arg)
    if intent == "copy_path":
        if isinstance(arg, tuple):
            return copy_path(arg[0], arg[1] if len(arg) > 1 else "")
        src, dest = _parse_two_paths(arg)
        return copy_path(src, dest)
    if intent == "move_path":
        if isinstance(arg, tuple):
            return move_path(arg[0], arg[1] if len(arg) > 1 else "")
        src, dest = _parse_two_paths(arg)
        return move_path(src, dest)
    if intent == "request_delete":
        return request_delete_double_confirmation(arg)
    if intent == "create_folder":
        return create_folder(arg)
    if intent == "write_file":
        if isinstance(arg, tuple):
            return write_file(arg[0], arg[1] if len(arg) > 1 else "", append=bool(arg[2]) if len(arg) > 2 else False)
        path, content = parse_path_content_arg(arg)
        return write_file(path, content)
    if intent == "append_file":
        if isinstance(arg, tuple):
            return append_file(arg[0], arg[1] if len(arg) > 1 else "")
        path, content = parse_path_content_arg(arg)
        return append_file(path, content)
    if intent == "replace_in_file":
        if isinstance(arg, tuple) and len(arg) >= 3:
            return replace_in_file(arg[0], arg[1], arg[2])
        return "Usa: reemplaza <texto> por <texto nuevo> en <archivo>"
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
