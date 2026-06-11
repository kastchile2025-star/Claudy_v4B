"""Claudy features.watcher — Notify Me: vigilar páginas web e indicadores (C1).

"Avísame cuando baje el precio de <url>" / "vigila esta página" /
"avísame si el dólar baja de 900".

Cada vigilancia es un cron job (action="watch") del engine existente
(features/scheduler.py): el engine la dispara según interval_min y
_watch_check compara contra el baseline guardado. Si hay cambio, notifica
por burbuja + toast + Telegram (las mismas piezas del cron).

Tipos (watch_kind):
  precio    : extrae precios del HTML; avisa cuando BAJA respecto al último
              precio conocido (baseline se actualiza solo al notificar).
  texto     : una palabra/frase aparece o desaparece de la página.
  cambio    : cualquier cambio en el texto visible (hash).
  indicador : dólar/uf/utm/euro/bitcoin/ipc vía mindicador.cl, con umbral
              opcional ("baje de 900") o cualquier variación.

Se usa como mixin: ClawdPet hereda de WatcherMixin. Depende de _cron_jobs,
_save_cron_json, _cron_notify_telegram, _notify, show_pet_speech_bubble.
"""
import datetime
import hashlib
import json
import re
import threading
import time
import urllib.request
from collections import Counter

DEFAULT_INTERVAL_MIN = 60
MIN_INTERVAL_MIN = 5
MAX_FAILS = 5

INDICADORES = {
    "dolar": "dólar", "dólar": "dólar", "uf": "UF", "utm": "UTM",
    "euro": "euro", "bitcoin": "bitcoin", "ipc": "IPC",
}
_INDICADOR_API = {"dólar": "dolar", "UF": "uf", "UTM": "utm",
                  "euro": "euro", "bitcoin": "bitcoin", "IPC": "ipc"}

_WATCH_VERBS = (r"av[ií]sa(?:me)?|vigila(?:r)?|monitorea(?:r)?|notif[ií]ca(?:me)?|"
                r"al[eé]rta(?:me)?|/vigilar")
_URL_RX = re.compile(r"(https?://[^\s\"'<>]+|www\.[^\s\"'<>]+)", re.IGNORECASE)


# ──────────────────────────────────────────────────────────────
# Helpers puros (testeables sin pet)
# ──────────────────────────────────────────────────────────────
def extract_visible_text(html):
    """Texto visible de un HTML: sin scripts/estilos/tags, espacios normalizados."""
    html = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", html,
                  flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", html)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
            .replace("&lt;", "<").replace("&gt;", ">").replace("&#36;", "$"))
    return re.sub(r"\s+", " ", text).strip()


def parse_money(s):
    """'19.990' → 19990.0 (miles chilenos) · '25.99' → 25.99 · '1.234,56' → 1234.56"""
    s = s.strip().rstrip(".,")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):     # 1.234,56 → coma decimal
            s = s.replace(".", "").replace(",", ".")
        else:                               # 1,234.56 → punto decimal
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) == 2:             # 1234,56 → decimal
            s = s.replace(",", ".")
        else:                               # 19,990 → miles
            s = s.replace(",", "")
    elif "." in s:
        parts = s.split(".")
        if len(parts[-1]) == 3 and len(parts) >= 2 and parts[0].isdigit():
            s = s.replace(".", "")          # 19.990 / 1.234.567 → miles
        # 25.99 / 912.4 → decimal, queda igual
    try:
        return float(s)
    except ValueError:
        return None


def extract_prices(text):
    """Precios plausibles (>10) encontrados en el texto, en orden de aparición."""
    out = []
    for m in re.finditer(r"(?:\$|clp|usd|€|precio[:\s]+)\s*([\d][\d.,]*)",
                         text, re.IGNORECASE):
        v = parse_money(m.group(1))
        if v is not None and v > 10:
            out.append(v)
    return out


def pick_main_price(prices):
    """El precio 'principal' de una página: el más repetido (el precio del
    producto suele aparecer varias veces); empate → el menor."""
    if not prices:
        return None
    counts = Counter(prices)
    best = max(counts.values())
    return min(p for p, c in counts.items() if c == best)


def fmt_clp(v):
    """1234567.0 → '$1.234.567' (estilo chileno); decimales solo si los hay."""
    if v == int(v):
        return "$" + f"{int(v):,}".replace(",", ".")
    entero = f"{int(v):,}".replace(",", ".")
    return f"${entero},{int(round((v - int(v)) * 100)):02d}"


def parse_watch_request(prompt):
    """Interpreta una petición de vigilancia en lenguaje natural o slash.

    Devuelve un dict con los campos del watch, o None si el mensaje no es
    una petición de vigilancia (no hay verbo de aviso + url/indicador).
    """
    lower = prompt.lower().strip()
    is_slash = lower.startswith("/vigilar")
    if not is_slash and not re.search(_WATCH_VERBS, lower):
        return None

    # Intervalo: "cada 30 min", "cada 2 horas", "cada hora"
    interval = DEFAULT_INTERVAL_MIN
    m = re.search(r"cada\s+(\d+)\s*(min(?:utos?)?|h(?:oras?)?\b)", lower)
    if m:
        interval = int(m.group(1)) * (60 if m.group(2).startswith("h") else 1)
    elif re.search(r"cada\s+hora", lower):
        interval = 60
    elif re.search(r"cada\s+d[ií]a|diariamente|una\s+vez\s+al\s+d[ií]a", lower):
        interval = 24 * 60
    interval = max(interval, MIN_INTERVAL_MIN)

    m_url = _URL_RX.search(prompt)
    if m_url:
        url = m_url.group(1).rstrip(").,;!?")
        if url.lower().startswith("www."):
            url = "https://" + url
        # tipo
        if re.search(r"\bprecio|\bbaje\b|\bbarat|\boferta|\bdescuento|\brebaj", lower):
            kind = "precio"
            label = f"precio en {re.sub(r'^https?://(www[.])?', '', url).split('/')[0]}"
            return {"kind": kind, "url": url, "keyword": None,
                    "interval_min": interval, "label": label}
        # palabra: comillas, o tras "la palabra / diga / aparezca / mencione / contenga"
        kw = None
        m_q = re.search(r"[\"'«]([^\"'»]{2,80})[\"'»]", prompt)
        if m_q:
            kw = m_q.group(1).strip()
        else:
            m_kw = re.search(
                r"(?:la\s+palabra|diga|aparezca|mencione|contenga)\s+(.+?)(?:\s+en\s+http|\s*$)",
                lower)
            if m_kw:
                kw = m_kw.group(1).strip().strip(".!?,")
                kw = re.sub(r"\s+(?:cada\s+.*|en\s+la\s+p[aá]gina.*)$", "", kw).strip()
        if kw:
            return {"kind": "texto", "url": url, "keyword": kw,
                    "interval_min": interval,
                    "label": f"«{kw}» en {re.sub(r'^https?://(www[.])?', '', url).split('/')[0]}"}
        return {"kind": "cambio", "url": url, "keyword": None,
                "interval_min": interval,
                "label": f"cambios en {re.sub(r'^https?://(www[.])?', '', url).split('/')[0]}"}

    # Sin URL: ¿indicador económico? ("avísame si el dólar baja de 900")
    m_ind = re.search(r"\b(d[oó]lar|uf|utm|euro|bitcoin|ipc)\b", lower)
    if m_ind:
        nombre = INDICADORES[m_ind.group(1)]
        umbral, direction = None, "cambio"
        m_b = re.search(r"baj[ea](?:\s+de|\s+los?|\s+bajo)?\s+\$?\s*([\d.,]+)", lower)
        m_s = re.search(r"(?:sub[ea]|super[ea]|pas[ea])(?:\s+de|\s+los?|\s+sobre)?\s+\$?\s*([\d.,]+)", lower)
        if m_b:
            umbral, direction = parse_money(m_b.group(1)), "baja"
        elif m_s:
            umbral, direction = parse_money(m_s.group(1)), "sube"
        cond = (f" {'bajo' if direction == 'baja' else 'sobre'} {fmt_clp(umbral)}"
                if umbral else "")
        return {"kind": "indicador", "indicador": nombre, "umbral": umbral,
                "direction": direction, "interval_min": interval,
                "label": f"{nombre}{cond}"}
    return None


# ──────────────────────────────────────────────────────────────
# Mixin
# ──────────────────────────────────────────────────────────────
class WatcherMixin:

    # ── creación ──
    def _watch_add(self, prompt):
        """Crea una vigilancia desde lenguaje natural. Toma el baseline ahora."""
        req = parse_watch_request(prompt)
        if not req:
            return ("Para vigilar algo dime, por ejemplo:\n"
                    "• avísame cuando baje el precio de https://...\n"
                    "• vigila https://... cada 2 horas\n"
                    "• avísame si la página https://... menciona \"agotado\"\n"
                    "• avísame si el dólar baja de 900")
        job = {
            "id": str(int(time.time() * 1000)),
            "type": "interval",
            "interval_min": req["interval_min"],
            "action": "watch",
            "watch_kind": req["kind"],
            "label": req["label"],
            "enabled": True,
            "fail_count": 0,
            "last_fired": datetime.datetime.now().isoformat(),
            "created": datetime.datetime.now().isoformat(),
        }
        for k in ("url", "keyword", "indicador", "umbral", "direction"):
            if req.get(k) is not None:
                job[k] = req[k]

        # Baseline inmediato: así el primer chequeo del cron compara contra HOY.
        detalle = ""
        try:
            if req["kind"] == "indicador":
                valor = self._watch_fetch_indicador(job["indicador"])
                job["baseline"] = {"valor": valor}
                detalle = f"\nValor actual: {fmt_clp(valor)}"
            else:
                text = self._watch_fetch_text(job["url"])
                if req["kind"] == "precio":
                    price = pick_main_price(extract_prices(text))
                    if price is None:
                        return (f"No encontré precios en {job['url']} — "
                                "¿es la página correcta del producto?")
                    job["baseline"] = {"price": price}
                    detalle = f"\nPrecio actual: {fmt_clp(price)} — te aviso si baja."
                elif req["kind"] == "texto":
                    present = req["keyword"].lower() in text.lower()
                    job["baseline"] = {"present": present}
                    detalle = (f"\nAhora mismo «{req['keyword']}» "
                               f"{'SÍ aparece' if present else 'NO aparece'} — "
                               "te aviso cuando eso cambie.")
                else:
                    job["baseline"] = {"hash": self._watch_hash(text), "len": len(text)}
                    detalle = "\nGuardé una foto de la página — te aviso ante cualquier cambio."
        except Exception as e:
            return f"No pude leer eso ahora ({e}). Revisa la URL e intenta de nuevo."

        self._cron_jobs.append(job)
        self._save_cron_json()
        horas = job["interval_min"] / 60
        cad = (f"cada {job['interval_min']} min" if job["interval_min"] < 60
               else f"cada {horas:g} hora{'s' if horas != 1 else ''}")
        return f"👁️ Vigilando: {job['label']} ({cad}).{detalle}"

    # ── listado / borrado ──
    def _watch_list(self):
        watches = [j for j in self._cron_jobs if j.get("action") == "watch"]
        if not watches:
            return ("No estoy vigilando nada.\n"
                    "Prueba: «avísame cuando baje el precio de <url>» o /vigilar <url>")
        lines = ["👁️ Vigilancias activas:"]
        for i, j in enumerate(watches, 1):
            estado = "ON" if j.get("enabled", True) else "OFF"
            extra = ""
            b = j.get("baseline") or {}
            if "price" in b:
                extra = f" (último precio: {fmt_clp(b['price'])})"
            elif "valor" in b:
                extra = f" (último valor: {fmt_clp(b['valor'])})"
            lines.append(f"  [{i}] [{estado}] {j.get('label','?')} — "
                         f"cada {j.get('interval_min', 60)} min{extra}")
        lines.append("\nQuitar: /vigilar quitar <num>")
        return "\n".join(lines)

    def _watch_remove(self, num):
        watches = [j for j in self._cron_jobs if j.get("action") == "watch"]
        try:
            idx = int(num) - 1
            target = watches[idx]
        except (ValueError, IndexError):
            return f"Número inválido. Hay {len(watches)} vigilancias (/vigilando)."
        self._cron_jobs.remove(target)
        self._save_cron_json()
        return f"✅ Ya no vigilo: {target.get('label', '?')}"

    # ── chequeo (lo llama el cron engine vía _execute_cron_job) ──
    def _watch_check(self, job):
        """El engine entrega una COPIA del job y corre en el hilo de UI:
        el trabajo real va en un thread y los cambios se persisten por id."""
        threading.Thread(target=self._watch_check_worker, args=(job,),
                         daemon=True, name="watch-check").start()

    def _watch_check_worker(self, job):
        try:
            if job.get("watch_kind") == "indicador":
                self._watch_check_indicador(job)
            else:
                self._watch_check_url(job)
            self._watch_update_job(job["id"], fail_count=0)
        except Exception as e:
            fails = int(job.get("fail_count", 0)) + 1
            if fails >= MAX_FAILS:
                self._watch_update_job(job["id"], fail_count=fails, enabled=False)
                self._watch_notify(job.get("label", "vigilancia"),
                                   f"La pausé tras {fails} fallos seguidos ({e}). "
                                   "Reactívala desde /cron on.")
            else:
                self._watch_update_job(job["id"], fail_count=fails)

    def _watch_check_url(self, job):
        text = self._watch_fetch_text(job["url"])
        kind = job.get("watch_kind")
        base = job.get("baseline") or {}
        if kind == "precio":
            price = pick_main_price(extract_prices(text))
            old = base.get("price")
            if price is None or old is None:
                return
            if price < old:
                self._watch_update_job(job["id"], baseline={"price": price})
                self._watch_notify(job.get("label", "precio"),
                                   f"💸 ¡Bajó el precio! {fmt_clp(old)} → {fmt_clp(price)}\n"
                                   f"{job['url']}")
        elif kind == "texto":
            present = (job.get("keyword") or "").lower() in text.lower()
            if present != base.get("present"):
                self._watch_update_job(job["id"], baseline={"present": present})
                estado = "apareció" if present else "desapareció"
                self._watch_notify(job.get("label", "texto"),
                                   f"La palabra «{job.get('keyword')}» {estado} en la página.\n"
                                   f"{job['url']}")
        else:  # cambio
            h = self._watch_hash(text)
            if h != base.get("hash"):
                delta = abs(len(text) - int(base.get("len", 0)))
                self._watch_update_job(job["id"],
                                       baseline={"hash": h, "len": len(text)})
                self._watch_notify(job.get("label", "página"),
                                   f"La página cambió (~{delta} caracteres de diferencia).\n"
                                   f"{job['url']}")

    def _watch_check_indicador(self, job):
        valor = self._watch_fetch_indicador(job["indicador"])
        base = job.get("baseline") or {}
        old = base.get("valor")
        umbral = job.get("umbral")
        direction = job.get("direction", "cambio")
        if umbral:
            cruzo = (valor <= umbral) if direction == "baja" else (valor >= umbral)
            ya_avisado = base.get("avisado", False)
            if cruzo and not ya_avisado:
                self._watch_update_job(job["id"],
                                       baseline={"valor": valor, "avisado": True})
                verbo = "bajó de" if direction == "baja" else "superó"
                self._watch_notify(job.get("label", job["indicador"]),
                                   f"💱 El {job['indicador']} {verbo} {fmt_clp(umbral)}: "
                                   f"ahora vale {fmt_clp(valor)}.")
            elif not cruzo and ya_avisado:
                # volvió a cruzar de vuelta: re-armar el aviso sin notificar
                self._watch_update_job(job["id"],
                                       baseline={"valor": valor, "avisado": False})
            else:
                self._watch_update_job(job["id"],
                                       baseline={"valor": valor,
                                                 "avisado": ya_avisado})
        else:
            if old is not None and valor != old:
                self._watch_update_job(job["id"], baseline={"valor": valor})
                flecha = "📉 bajó" if valor < old else "📈 subió"
                self._watch_notify(job.get("label", job["indicador"]),
                                   f"💱 El {job['indicador']} {flecha}: "
                                   f"{fmt_clp(old)} → {fmt_clp(valor)}.")
            elif old is None:
                self._watch_update_job(job["id"], baseline={"valor": valor})

    # ── infraestructura ──
    def _watch_hash(self, text):
        return hashlib.md5(text.encode("utf-8", "ignore")).hexdigest()

    def _watch_fetch_text(self, url):
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/126.0 Safari/537.36"),
            "Accept-Language": "es-CL,es;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read(2_000_000).decode("utf-8", "ignore")
        return extract_visible_text(html)

    def _watch_fetch_indicador(self, nombre):
        key = _INDICADOR_API.get(nombre, nombre)
        req = urllib.request.Request(f"https://mindicador.cl/api/{key}",
                                     headers={"User-Agent": "Claudy/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        serie = data.get("serie") or []
        if not serie:
            raise RuntimeError(f"mindicador sin datos para {nombre}")
        return float(serie[0]["valor"])

    def _watch_update_job(self, job_id, **fields):
        """Persiste cambios sobre el job REAL (el engine reparte copias)."""
        for j in self._cron_jobs:
            if j.get("id") == job_id:
                j.update(fields)
                self._save_cron_json()
                return

    def _watch_notify(self, label, msg):
        text = f"👁️ Vigía — {label}\n{msg}"
        try:
            self.after(0, lambda: self.show_pet_speech_bubble(text, duration=20000))
        except Exception:
            pass
        try:
            chat = getattr(self, "_chat_view", None)
            if chat:
                self.after(0, lambda: chat.add_bot(text))
        except Exception:
            pass
        try:
            self._notify("Claudy Vigía", msg[:200])
        except Exception:
            pass
        try:
            self._cron_notify_telegram(text[:500])
        except Exception:
            pass
