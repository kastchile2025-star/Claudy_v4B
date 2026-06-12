"""Claudy features.browser — Browser automation con Playwright (plan Hermes 2.2).

Claudy puede navegar webs de verdad: abrir páginas, hacer clic, llenar
formularios, extraer texto y sacar capturas. Casos de uso: portales que
requieren login (el perfil persiste en ~/.claudy/browser_profile, así la
sesión iniciada una vez se mantiene), descargar facturas, extraer datos
de páginas con JavaScript que el scraper simple no ve.

Arquitectura — hilo actor:
  La API síncrona de Playwright solo puede usarse desde el hilo que la
  creó. Un hilo dedicado ("browser") procesa una cola de órdenes; el
  resto de Claudy (intents, tools del LLM) encola con _browser_call y
  espera el resultado. La sesión se crea perezosa con la primera orden
  y "close" la destruye (la siguiente orden relanza).

Superficie:
  - /navegar <url> · ver <url> (ventana visible, útil para logins) ·
    clic <texto|selector> · escribe <selector> | <valor> · tecla <Enter> ·
    texto · captura · cerrar
  - Lenguaje natural: «entra a <url> y dime los precios» → navega,
    extrae el texto y responde la pregunta con el LLM.
  - Tools para function-calling del LLM: browser_goto/text/click/fill/
    press/screenshot (registradas en pet.py).

Seguridad: el texto extraído es contenido de terceros → pasa por el
filtro anti-inyección (core/injection_guard) antes de llegar al LLM.

Se usa como mixin: ClawdPet hereda de BrowserMixin. Depende de
send_quick_message y _debug_log de la clase compuesta.
"""
import datetime
import os
import queue
import re
import threading

INSTALL_HELP = ("El navegador automatizado no está instalado. En una consola:\n"
                "  pip install playwright\n"
                "  python -m playwright install chromium\n"
                "y vuelve a intentarlo.")

NAV_NL_RX = re.compile(
    r"^(?:entra|navega|ingresa|m[eé]tete)\s+(?:a|en)\s+"
    r"(https?://\S+|www\.\S+)[\s,]*(?:y\s+(.+))?$",
    re.IGNORECASE | re.DOTALL)


def parse_navigate_request(prompt):
    """«entra a <url> y dime X» → {"url", "question"} · None si no aplica."""
    m = NAV_NL_RX.match((prompt or "").strip())
    if not m:
        return None
    url = m.group(1).rstrip(").,;!?")
    if url.lower().startswith("www."):
        url = "https://" + url
    return {"url": url, "question": (m.group(2) or "").strip()}


class _PlaywrightSession:
    """Envoltura síncrona de un Chromium persistente. Vive SOLO dentro del
    hilo actor — nadie más debe tocar self.page directamente."""

    def __init__(self, headless=True):
        from playwright.sync_api import sync_playwright
        profile = os.path.join(os.path.expanduser("~"), ".claudy", "browser_profile")
        os.makedirs(profile, exist_ok=True)
        self._pw = sync_playwright().start()
        self.context = self._pw.chromium.launch_persistent_context(
            user_data_dir=profile, headless=headless,
            viewport={"width": 1280, "height": 900})
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(20000)

    def goto(self, url):
        url = (url or "").strip()
        if not url:
            return "Falta la URL."
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass  # páginas con polling eterno: el DOM ya está usable
        return f"📄 {self.page.title()}\n🔗 {self.page.url}"

    def text(self, max_chars=6000):
        t = self.page.inner_text("body")
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
        return t[:max_chars]

    def click(self, target):
        target = (target or "").strip()
        try:
            self.page.click(target, timeout=8000)
        except Exception:
            # No era selector CSS: probar por texto visible
            self.page.get_by_text(target, exact=False).first.click(timeout=8000)
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=6000)
        except Exception:
            pass
        return f"✓ Clic en «{target}» → {self.page.url}"

    def fill(self, selector, value):
        try:
            self.page.fill(selector, value, timeout=8000)
        except Exception:
            # No era selector: probar por placeholder y por label
            try:
                self.page.get_by_placeholder(selector).first.fill(value, timeout=6000)
            except Exception:
                self.page.get_by_label(selector).first.fill(value, timeout=6000)
        return f"✓ Escribí en «{selector}»"

    def press(self, key="Enter"):
        self.page.keyboard.press(key or "Enter")
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        return f"✓ Tecla {key} → {self.page.url}"

    def screenshot(self):
        folder = os.path.join(os.path.expanduser("~"), ".claudy", "screenshots")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(
            folder, f"web_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        self.page.screenshot(path=path)
        return path

    def close(self):
        try:
            self.context.close()
        finally:
            self._pw.stop()
        return "Navegador cerrado."


class BrowserMixin:

    def _browser_make_session(self):
        """Fábrica de la sesión real (overrideable en tests)."""
        return _PlaywrightSession(headless=getattr(self, "_browser_headless", True))

    # ── hilo actor ──
    def _browser_call(self, method, *args, timeout=90, **kwargs):
        """Encola una orden al hilo del navegador y espera el resultado.
        Lanza RuntimeError si la orden falló."""
        if not getattr(self, "_browser_thread", None) or not self._browser_thread.is_alive():
            self._browser_queue = queue.Queue()
            self._browser_thread = threading.Thread(
                target=self._browser_worker, daemon=True, name="browser")
            self._browser_thread.start()
        box, done = {}, threading.Event()
        self._browser_queue.put((method, args, kwargs, box, done))
        if not done.wait(timeout):
            raise RuntimeError(f"el navegador no respondió en {timeout}s ({method})")
        if "error" in box:
            raise RuntimeError(box["error"])
        return box.get("result")

    def _browser_worker(self):
        session = None
        while True:
            item = self._browser_queue.get()
            if item is None:
                break
            method, args, kwargs, box, done = item
            try:
                if session is None:
                    if method == "close":
                        box["result"] = "El navegador ya estaba cerrado."
                        done.set()
                        continue
                    session = self._browser_make_session()
                box["result"] = getattr(session, method)(*args, **kwargs)
            except ModuleNotFoundError:
                box["error"] = INSTALL_HELP
            except Exception as e:
                box["error"] = str(e).splitlines()[0][:300]
            done.set()
            if method == "close":
                session = None  # la próxima orden relanza el navegador

    # ── tools para el LLM (envoltura segura que devuelve strings) ──
    def _browser_tool(self, method, *args):
        try:
            out = self._browser_call(method, *args)
        except Exception as e:
            return f"Error de navegador: {e}"
        if method == "text":
            # Contenido de terceros → filtro anti-inyección antes del LLM
            try:
                from core.injection_guard import sanitize_external
                out, hits = sanitize_external(out or "", source="web")
                if hits:
                    self._debug_log("INJECTION GUARD", f"browser text: {len(hits)} hits")
            except Exception:
                pass
        return out if isinstance(out, str) else str(out)

    # ── lenguaje natural: «entra a <url> y dime X» ──
    def _browser_navigate_nl(self, url, question=""):
        try:
            header = self._browser_call("goto", url)
            content = self._browser_tool("text")
        except Exception as e:
            return f"No pude navegar a {url}: {e}"
        if not question:
            resumen = content[:900].strip()
            return f"{header}\n\n{resumen}{'…' if len(content) > 900 else ''}"
        prompt = (
            f"Navegué a {url} y este es el texto visible de la página:\n\n"
            f"{content}\n\n"
            f"Con SOLO esa información responde: {question}\n"
            "Si el dato no está en la página, dilo claramente."
        )
        try:
            return self.send_quick_message(prompt, _skip_skill_action=True, timeout=120)
        except Exception as e:
            return f"{header}\n\nLeí la página pero falló la síntesis: {e}"

    # ── slash /navegar ──
    def _browser_cmd(self, arg):
        arg = (arg or "").strip()
        low = arg.lower()
        if not arg:
            return ("🌐 Navegador automatizado (Playwright):\n"
                    "  /navegar <url>            abre y muestra el contenido\n"
                    "  /navegar ver <url>        con ventana visible (para logins)\n"
                    "  /navegar clic <texto>     clic en un botón/enlace\n"
                    "  /navegar escribe <campo> | <valor>\n"
                    "  /navegar tecla Enter      enviar formulario\n"
                    "  /navegar texto · captura · cerrar\n"
                    "También: «entra a <url> y dime <pregunta>»")
        try:
            if low in ("cerrar", "close"):
                return self._browser_call("close")
            if low.startswith("ver "):
                # ventana visible: cerrar la sesión headless y relanzar
                self._browser_headless = False
                try:
                    self._browser_call("close")
                except Exception:
                    pass
                return self._browser_call("goto", arg[4:].strip())
            if low.startswith(("clic ", "click ")):
                return self._browser_call("click", arg.split(None, 1)[1])
            if low.startswith(("escribe ", "fill ")):
                resto = arg.split(None, 1)[1]
                if "|" not in resto:
                    return "Uso: /navegar escribe <selector o placeholder> | <valor>"
                sel, val = (x.strip() for x in resto.split("|", 1))
                return self._browser_call("fill", sel, val)
            if low.startswith(("tecla ", "press ")):
                return self._browser_call("press", arg.split(None, 1)[1])
            if low in ("texto", "text"):
                return self._browser_tool("text")[:3500]
            if low in ("captura", "screenshot"):
                path = self._browser_call("screenshot")
                return f"📸 Captura guardada: {path}"
            # default: es una URL
            header = self._browser_call("goto", arg)
            content = self._browser_tool("text")
            return f"{header}\n\n{content[:900]}{'…' if len(content) > 900 else ''}"
        except Exception as e:
            return f"Error de navegador: {e}"
