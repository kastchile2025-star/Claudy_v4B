"""Claudy features.cleaner — Análisis y limpieza segura del PC.

Flujo en dos pasos (el botón 🧹 del sidebar dispara «/limpiar»):

  1. _cleanup_analyze(): escanea categorías SEGURAS de basura (temporales,
     cachés, papelera, instaladores viejos), calcula tamaños y devuelve una
     propuesta numerada. Guarda las propuestas en self._cleanup_proposals.
  2. _cleanup_execute("todo" | "1,3,5" | "cancelar"): ejecuta SOLO lo elegido.
     «todo» cubre las categorías seguras; los archivos personales (instaladores
     en Descargas) requieren selección explícita y van a la Papelera, no se
     borran directo.

Se usa como mixin: ClawdPet hereda de CleanerMixin. Depende de _debug_log.
"""
import os
import subprocess
import time


def _human(n):
    """Bytes → texto legible."""
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


def _walk_size(path, older_than_secs=None, max_files=80000):
    """(bytes, n_archivos) de un árbol, opcionalmente solo archivos viejos.
    Con tope de archivos visitados para no colgarse en árboles gigantes."""
    total, count, visited = 0, 0, 0
    cutoff = time.time() - older_than_secs if older_than_secs else None
    for root, dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            visited += 1
            if visited > max_files:
                return total, count
            fp = os.path.join(root, f)
            try:
                st = os.stat(fp)
                if cutoff and st.st_mtime > cutoff:
                    continue
                total += st.st_size
                count += 1
            except OSError:
                continue
    return total, count


def _clean_tree(path, older_than_secs=None):
    """Borra archivos (opcionalmente solo los viejos) y carpetas vacías.
    Ignora errores por archivo (en uso / sin permisos). Devuelve bytes liberados."""
    freed = 0
    cutoff = time.time() - older_than_secs if older_than_secs else None
    for root, dirs, files in os.walk(path, topdown=False, onerror=lambda e: None):
        for f in files:
            fp = os.path.join(root, f)
            try:
                st = os.stat(fp)
                if cutoff and st.st_mtime > cutoff:
                    continue
                os.remove(fp)
                freed += st.st_size
            except OSError:
                continue
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))  # solo si quedó vacía
            except OSError:
                continue
    return freed


class CleanerMixin:

    # ──────────────────────────────────────────────────────────
    # Análisis: propuestas numeradas
    # ──────────────────────────────────────────────────────────
    def _cleanup_analyze(self):
        proposals = []

        def add(label, kind, size, count=None, detail=None, explicit=False):
            proposals.append({
                "id": len(proposals) + 1, "label": label, "kind": kind,
                "size": size, "count": count, "detail": detail or [],
                "explicit": explicit,
            })

        day = 24 * 3600

        # 1. Temporales del usuario (%TEMP%), solo >24 h (los recientes pueden estar en uso)
        tmp = os.environ.get("TEMP") or os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp")
        if os.path.isdir(tmp):
            size, count = _walk_size(tmp, older_than_secs=day)
            if size:
                add(f"Archivos temporales del usuario (>24 h) — {count:,} archivos", "user_temp", size)

        # 2. Temporales de Windows (puede requerir permisos; se limpia lo que deje)
        wtmp = r"C:\Windows\Temp"
        if os.path.isdir(wtmp):
            try:
                size, count = _walk_size(wtmp, older_than_secs=day)
                if size:
                    add(f"Temporales de Windows (>24 h) — {count:,} archivos", "win_temp", size)
            except Exception:
                pass

        # 3. Caché de pip
        pip_cache = os.path.join(os.path.expanduser("~"), "AppData", "Local", "pip", "cache")
        if os.path.isdir(pip_cache):
            size, count = _walk_size(pip_cache)
            if size:
                add("Caché de pip (paquetes Python descargados)", "pip_cache", size)

        # 4. Caché de npm
        npm_cache = os.path.join(os.path.expanduser("~"), "AppData", "Local", "npm-cache")
        if os.path.isdir(npm_cache):
            size, count = _walk_size(npm_cache)
            if size:
                add("Caché de npm (paquetes Node descargados)", "npm_cache", size)

        # 5. Papelera de reciclaje (tamaño vía Shell COM; vaciado con Clear-RecycleBin)
        try:
            ps = ("$s=(New-Object -ComObject Shell.Application).NameSpace(0xA).Items()"
                  "|Measure-Object -Property Size -Sum; [int64]$s.Sum")
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=25,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            rb_size = int((out.stdout or "0").strip() or 0)
            if rb_size > 0:
                add("Papelera de reciclaje (vaciar — no recuperable)", "recycle_bin", rb_size)
        except Exception:
            pass

        # 6. Cachés de Claudy (screenshots temporales)
        shots = os.path.join(os.path.expanduser("~"), ".claudy", "screenshots")
        if os.path.isdir(shots):
            size, count = _walk_size(shots, older_than_secs=7 * day)
            if size:
                add(f"Capturas temporales de Claudy (>7 días) — {count:,} archivos", "claudy_cache", size)

        # 7. Instaladores viejos en Descargas (>30 días) — SOLO con selección explícita
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        if os.path.isdir(downloads):
            cutoff = time.time() - 30 * day
            installers, inst_size = [], 0
            try:
                for f in os.listdir(downloads):
                    if not f.lower().endswith((".exe", ".msi")):
                        continue
                    fp = os.path.join(downloads, f)
                    try:
                        st = os.stat(fp)
                    except OSError:
                        continue
                    if os.path.isfile(fp) and st.st_mtime < cutoff:
                        installers.append(fp)
                        inst_size += st.st_size
            except OSError:
                pass
            if installers:
                add(f"Instaladores viejos en Descargas (>30 días) — {len(installers)} archivos",
                    "old_installers", inst_size, detail=installers, explicit=True)

        self._cleanup_proposals = proposals
        if not proposals:
            return "🧹 Analicé el PC y está limpio: no encontré basura recuperable en las categorías seguras."

        total = sum(p["size"] for p in proposals)
        lines = ["🧹 **Análisis de limpieza del PC** — esto es lo que puedo recuperar:\n"]
        for p in proposals:
            mark = " ⚠️ (solo si la eliges explícitamente; va a la Papelera)" if p["explicit"] else ""
            lines.append(f"**{p['id']}.** {p['label']} — **{_human(p['size'])}**{mark}")
            for fp in (p["detail"] or [])[:8]:
                lines.append(f"      · {os.path.basename(fp)}")
            if p["detail"] and len(p["detail"]) > 8:
                lines.append(f"      · ... y {len(p['detail']) - 8} más")
        lines.append(f"\n**Total recuperable: ~{_human(total)}**\n")
        lines.append("Para ejecutar: `/limpiar todo` (categorías seguras), "
                     "`/limpiar 1,3` (elegir), o `/limpiar cancelar`.")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    # Archivos grandes: "limpia los archivos de más de 1 GB"
    # ──────────────────────────────────────────────────────────
    def _cleanup_big_files(self, min_bytes):
        """Busca archivos personales que pesan >= min_bytes y los propone para
        enviar a la Papelera (recuperables). No borra nada sin aprobación."""
        home = os.path.expanduser("~")
        roots = [os.path.join(home, d) for d in
                 ("Downloads", "Documents", "Desktop", "Videos", "Music", "Pictures")]
        skip = {".git", "node_modules", "AppData", "$RECYCLE.BIN", "__pycache__"}
        found, visited = [], 0
        for root_dir in roots:
            if not os.path.isdir(root_dir):
                continue
            for root, dirs, files in os.walk(root_dir, onerror=lambda e: None):
                dirs[:] = [d for d in dirs if d not in skip and not d.startswith((".", "$"))]
                for f in files:
                    visited += 1
                    if visited > 150000:
                        break
                    fp = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(fp)
                    except OSError:
                        continue
                    if sz >= min_bytes:
                        found.append((sz, fp))
                if visited > 150000:
                    break

        found.sort(reverse=True)
        found = found[:25]
        if not found:
            return (f"Busqué en Descargas, Documentos, Escritorio, Videos, Música e "
                    f"Imágenes y no encontré archivos de más de {_human(min_bytes)}.")

        proposals = []
        for i, (sz, fp) in enumerate(found, 1):
            proposals.append({
                "id": i, "label": f"{os.path.basename(fp)} ({os.path.dirname(fp)})",
                "kind": "big_file", "size": sz, "count": 1, "detail": [fp],
                "explicit": False,
            })
        self._cleanup_proposals = proposals
        total = sum(p["size"] for p in proposals)
        lines = [f"🧹 **Archivos de más de {_human(min_bytes)}** — encontré "
                 f"{len(proposals)} (irían a la **Papelera**, recuperables):\n"]
        for p in proposals:
            lines.append(f"**{p['id']}.** {os.path.basename(p['detail'][0])} — **{_human(p['size'])}**")
            lines.append(f"      · {p['detail'][0]}")
        lines.append(f"\n**Total: ~{_human(total)}**\n")
        lines.append("Para enviarlos a la Papelera: `/limpiar todo`, `/limpiar 1,3` "
                     "(elegir), «limpia el 1 y el 3», o `/limpiar cancelar`.")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    # Ejecución de lo elegido
    # ──────────────────────────────────────────────────────────
    def _cleanup_execute(self, selection):
        selection = (selection or "").strip().lower()
        if selection in ("cancelar", "cancel", "no"):
            self._cleanup_proposals = []
            return "Limpieza cancelada. No toqué nada."
        if selection in ("analizar", "analiza", "propuestas"):
            return self._cleanup_analyze()

        proposals = getattr(self, "_cleanup_proposals", None)
        if not proposals:
            return ("No hay un análisis vigente. Ejecuta primero `/limpiar` para ver "
                    "las propuestas y luego elige qué limpiar.")

        if selection in ("todo", "all", "si", "sí", "ok", "dale"):
            chosen = [p for p in proposals if not p["explicit"]]
        else:
            try:
                ids = {int(x) for x in selection.replace(" ", "").split(",") if x}
            except ValueError:
                return "No entendí la selección. Usa `/limpiar todo` o `/limpiar 1,3`."
            chosen = [p for p in proposals if p["id"] in ids]
            if not chosen:
                return "Esos números no están en la propuesta vigente. Ejecuta `/limpiar` de nuevo."

        day = 24 * 3600
        freed_total, results = 0, []
        # Si el usuario eligió instaladores Y vaciar papelera, reciclar primero
        chosen.sort(key=lambda p: 0 if p["kind"] == "old_installers" else 1)
        for p in chosen:
            freed = 0
            try:
                if p["kind"] == "user_temp":
                    tmp = os.environ.get("TEMP") or os.path.join(
                        os.path.expanduser("~"), "AppData", "Local", "Temp")
                    freed = _clean_tree(tmp, older_than_secs=day)
                elif p["kind"] == "win_temp":
                    freed = _clean_tree(r"C:\Windows\Temp", older_than_secs=day)
                elif p["kind"] == "pip_cache":
                    freed = _clean_tree(os.path.join(
                        os.path.expanduser("~"), "AppData", "Local", "pip", "cache"))
                elif p["kind"] == "npm_cache":
                    freed = _clean_tree(os.path.join(
                        os.path.expanduser("~"), "AppData", "Local", "npm-cache"))
                elif p["kind"] == "claudy_cache":
                    freed = _clean_tree(os.path.join(
                        os.path.expanduser("~"), ".claudy", "screenshots"), older_than_secs=7 * day)
                elif p["kind"] == "recycle_bin":
                    subprocess.run(
                        ["powershell", "-NoProfile", "-Command",
                         "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                        capture_output=True, timeout=60,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    freed = p["size"]
                elif p["kind"] in ("old_installers", "big_file"):
                    for fp in p["detail"]:
                        sz = 0
                        try:
                            sz = os.path.getsize(fp)
                        except OSError:
                            pass
                        if self._send_to_recycle_bin(fp):
                            freed += sz
                results.append(f"✓ {p['label']}: liberé {_human(freed)}")
                freed_total += freed
            except Exception as e:
                results.append(f"✗ {p['label']}: {e}")

        self._cleanup_proposals = []  # propuesta consumida
        try:
            self._debug_log("CLEANUP", f"liberados {_human(freed_total)}")
        except Exception:
            pass
        return ("🧹 **Limpieza terminada**\n\n" + "\n".join(results)
                + f"\n\n**Espacio recuperado: ~{_human(freed_total)}**")

    def _send_to_recycle_bin(self, path):
        """Manda un archivo a la Papelera (no borra directo). True si salió."""
        try:
            safe = path.replace("'", "''")
            ps = ("Add-Type -AssemblyName Microsoft.VisualBasic; "
                  "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
                  f"'{safe}', 'OnlyErrorDialogs', 'SendToRecycleBin')")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return not os.path.exists(path)
        except Exception:
            return False
