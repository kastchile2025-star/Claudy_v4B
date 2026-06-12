"""Claudy features.canvas — Live Canvas agéntico (B1, estilo OpenClaw).

Claudy abre visualizaciones por INICIATIVA PROPIA: cuando una respuesta
amerita tabla comparativa o gráfico (rankings, series, comparaciones), el
modelo llama a la tool show_canvas y se abre una página HTML pulida en el
navegador — tema oscuro Claudy, tablas estilizadas y Chart.js si hay datos.

Piezas:
  - markdown_to_html(): mini-renderer (títulos, negritas, listas, TABLAS).
  - build_canvas_html(): documento completo, Chart.js solo si hay gráfico.
  - CanvasMixin._canvas_show(): escribe ~/.claudy/canvas/<ts>.html y lo abre.
  - Tool LLM `show_canvas(title, markdown, chart)` registrada en pet.py —
    ahí vive la parte "agéntica": el modelo decide cuándo usarla.
  - /canvas <markdown> para abrirlo a mano.

El HTML es local y estático: sin servidores, sin dependencias nuevas
(Chart.js va por CDN y la página funciona igual sin internet, solo que
sin el gráfico).
"""
import datetime
import html as _html
import json
import os
import re

CHART_TYPES = ("bar", "line", "pie", "doughnut", "radar", "scatter")


def markdown_to_html(md):
    """Mini-markdown → HTML: #/##/### títulos, **negrita**, `code`,
    listas con -, y tablas | a | b |. Suficiente para informes de Claudy."""
    out, table, in_list = [], [], False

    def flush_table():
        nonlocal table
        if not table:
            return
        rows = [r for r in table if not re.match(r"^[\s|:\-]+$", r)]
        html_rows = []
        for i, row in enumerate(rows):
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            tag = "th" if i == 0 else "td"
            html_rows.append(
                "<tr>" + "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells) + "</tr>")
        out.append("<table>" + "".join(html_rows) + "</table>")
        table = []

    def _inline(s):
        s = _html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        return s

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for line in (md or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            close_list()
            table.append(stripped)
            continue
        flush_table()
        m = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if m:
            close_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue
        if stripped.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
            continue
        close_list()
        if stripped:
            out.append(f"<p>{_inline(stripped)}</p>")
    flush_table()
    close_list()
    return "\n".join(out)


def normalize_chart(chart):
    """Valida/normaliza el spec del gráfico. Acepta dict o JSON string con
    {type, labels, datasets|data, title?}. None si no es usable."""
    if isinstance(chart, str):
        try:
            chart = json.loads(chart)
        except Exception:
            return None
    if not isinstance(chart, dict):
        return None
    ctype = str(chart.get("type", "bar")).lower()
    if ctype not in CHART_TYPES:
        ctype = "bar"
    labels = chart.get("labels") or []
    datasets = chart.get("datasets")
    if not datasets and chart.get("data"):
        datasets = [{"label": chart.get("title", "Datos"), "data": chart["data"]}]
    if not labels or not datasets:
        return None
    return {"type": ctype, "labels": labels, "datasets": datasets,
            "title": chart.get("title", "")}


def build_canvas_html(title, markdown="", chart=None):
    """Documento HTML completo, tema oscuro Claudy. Chart.js solo si hay chart."""
    body = markdown_to_html(markdown)
    chart = normalize_chart(chart)
    chart_block = ""
    if chart:
        cfg = {
            "type": chart["type"],
            "data": {"labels": chart["labels"], "datasets": chart["datasets"]},
            "options": {"responsive": True,
                        "plugins": {"legend": {"labels": {"color": "#cbd5e1"}},
                                    "title": {"display": bool(chart["title"]),
                                              "text": chart["title"], "color": "#e2e8f0"}},
                        "scales": {"x": {"ticks": {"color": "#94a3b8"}, "grid": {"color": "#1e293b"}},
                                   "y": {"ticks": {"color": "#94a3b8"}, "grid": {"color": "#1e293b"}}}},
        }
        chart_block = (
            '<div class="chart"><canvas id="c"></canvas></div>\n'
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>\n'
            f"<script>new Chart(document.getElementById('c'), {json.dumps(cfg, ensure_ascii=False)});</script>"
        )
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>{_html.escape(title or 'Claudy Canvas')}</title>
<style>
  body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',sans-serif;
         max-width:960px; margin:2rem auto; padding:0 1.5rem; line-height:1.6; }}
  h1 {{ color:#22d3ee; border-bottom:2px solid #164e63; padding-bottom:.4rem; }}
  h2 {{ color:#67e8f9; }} h3 {{ color:#a5f3fc; }}
  table {{ border-collapse:collapse; width:100%; margin:1rem 0; }}
  th {{ background:#164e63; color:#cffafe; text-align:left; }}
  th,td {{ border:1px solid #1e293b; padding:.5rem .8rem; }}
  tr:nth-child(even) td {{ background:#13203a; }}
  code {{ background:#1e293b; padding:.1rem .35rem; border-radius:4px; color:#7dd3fc; }}
  .chart {{ background:#111c33; border:1px solid #1e293b; border-radius:10px;
            padding:1rem; margin:1.5rem 0; }}
  .foot {{ color:#475569; font-size:.8rem; margin-top:2.5rem; }}
</style></head><body>
<h1>{_html.escape(title or 'Claudy Canvas')}</h1>
{chart_block}
{body}
<div class="foot">Generado por Claudy · {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}</div>
</body></html>"""


class CanvasMixin:

    def _canvas_dir(self):
        d = os.path.join(os.path.expanduser("~"), ".claudy", "canvas")
        os.makedirs(d, exist_ok=True)
        return d

    def _canvas_open(self, path):
        os.startfile(path)  # navegador por defecto

    def _canvas_show(self, title, markdown="", chart=None):
        """Construye el HTML, lo guarda y lo abre. Devuelve un mensaje corto."""
        title = (title or "Canvas").strip()
        if not (markdown or "").strip() and not normalize_chart(chart):
            return "Canvas: no hay contenido que mostrar (ni texto ni datos de gráfico)."
        doc = build_canvas_html(title, markdown, chart)
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:40].strip("-") or "canvas"
        path = os.path.join(
            self._canvas_dir(),
            f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{slug}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        try:
            self._canvas_open(path)
        except Exception as e:
            return f"Canvas guardado en {path} pero no pude abrirlo: {e}"
        return f"🎨 Abrí el canvas «{title}» en tu navegador.\n({path})"

    def _canvas_cmd(self, arg):
        """Slash /canvas: con argumento renderiza ese contenido; sin argumento
        renderiza la última respuesta del chat."""
        arg = (arg or "").strip()
        if not arg:
            msgs = getattr(self, "_current_session_msgs", []) or []
            last_bot = next((m.get("text", "") for m in reversed(msgs)
                             if m.get("role") in ("bot", "Claudy")), "")
            if not last_bot.strip():
                return ("Uso: /canvas <texto o markdown con tablas>\n"
                        "Sin argumento renderiza mi última respuesta del chat.")
            return self._canvas_show("Última respuesta de Claudy", last_bot)
        return self._canvas_show(arg.splitlines()[0][:60], arg)
