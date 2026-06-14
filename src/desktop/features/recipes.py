"""Claudy features.recipes — B3: Catálogo de recetas QCORE.

Biblioteca local CURADA de automatizaciones listas para instalar como skills,
al estilo ClawHub pero propia del ecosistema QCORE (facturación, informes,
scraping, agentes). Complementa /skill buscar (registros remotos) y find-skills:
estas recetas viven en el repo, vienen pre-vetadas y se instalan sin red.

Cada receta es un SKILL.md completo (mismo formato canónico que skill_loop).
Instalar una receta = copiarla a ~/.claudy/skills/<slug>/SKILL.md con
origin="recipe" en su _meta.json. Se reusan los helpers existentes del pet
(_skill_dir, _save_skill_meta, _installed_skill_slugs).

Comandos (cableados en pet.py):
  /recetas                  → lista el catálogo por categoría
  /recetas <texto>          → filtra el catálogo
  /receta instalar <slug>   → instala una receta (o "todas" para el set base)
"""
import os
import re


# ── Catálogo curado. Cada entrada: slug, categoría, título, descripción y el
#    cuerpo SKILL.md completo. Mantener el frontmatter name = slug. ──────────
RECIPES = [
    {
        "slug": "factura-mensual-combas",
        "category": "Facturación",
        "title": "Factura mensual COMBAS",
        "description": "Arma y registra la factura mensual de COMBAS a partir de los adjuntos del mes.",
        "body": """---
name: factura-mensual-combas
description: Arma y registra la factura mensual de COMBAS a partir de los adjuntos del mes.
---

# Factura mensual de COMBAS

## Cuándo usarla
Cuando Felipe pida "arma la factura de COMBAS de este mes" o llegue fin de mes
y haya adjuntos de tareas/horas pendientes de facturar para COMBAS.

## Pasos
1. Reúne los adjuntos del mes desde la carpeta de COMBAS en Drive
   (QCORE-ECOSYSTEM/01-CORPORATE/FACTURACION-CLIENTES/COMBAS y los adjuntos de tareas).
2. Suma horas/ítems facturables y calcula el total; aplica el IVA vigente.
3. Genera el documento de factura (xlsx o docx) con número correlativo siguiente
   al de la última factura emitida.
4. Guarda una copia en Facturas-Emitidas/COMBAS y registra el monto.
5. Resume a Felipe: número, periodo, total y dónde quedó el archivo.

## Reglas
- Nunca reutilices un número de factura ya emitido: revisa el último correlativo.
- Si falta algún adjunto o dato (horas, tarifa), pregúntalo antes de cerrar el total.
- Montos en CLP, con separador de miles.

## Ejemplo
"Claudy, arma la factura de COMBAS de mayo" → reúne adjuntos de mayo, total
$X + IVA, factura #N guardada en Facturas-Emitidas/COMBAS.""",
    },
    {
        "slug": "resumen-semanal-facturas",
        "category": "Facturación",
        "title": "Resumen semanal de facturas",
        "description": "Cada viernes, consolida las facturas emitidas de la semana en un resumen.",
        "body": """---
name: resumen-semanal-facturas
description: Cada viernes, consolida las facturas emitidas de la semana en un resumen claro.
---

# Resumen semanal de facturas

## Cuándo usarla
Los viernes, o cuando Felipe pida "resumen de facturas de la semana". Ideal para
agendarla con un cron (`recuérdame cada viernes a las 18 ejecutar la skill
resumen-semanal-facturas`).

## Pasos
1. Lista las facturas emitidas en los últimos 7 días desde Facturas-Emitidas.
2. Agrupa por cliente (COMBAS, Tentación a Granel, etc.) y suma totales.
3. Marca las que siguen pendientes de pago.
4. Entrega una tabla compacta: cliente · nº factura · monto · estado.
5. Ofrece exportar el resumen a un archivo si Felipe lo quiere.

## Reglas
- Solo cuenta facturas de la semana en curso (lunes a viernes).
- Si no hubo facturas, dilo explícitamente en vez de inventar filas.

## Ejemplo
"Claudy, ¿cómo vamos con las facturas esta semana?" → tabla con 3 clientes,
total $X, 1 pendiente de pago.""",
    },
    {
        "slug": "informe-cliente-mensual",
        "category": "Informes",
        "title": "Informe mensual de cliente",
        "description": "Genera un informe de avance mensual para un cliente QCORE con secciones estándar.",
        "body": """---
name: informe-cliente-mensual
description: Genera un informe de avance mensual para un cliente QCORE con secciones estándar.
---

# Informe mensual de cliente

## Cuándo usarla
Cuando Felipe pida "hazme el informe mensual de <cliente>" o cierre de mes de un
proyecto (SmartStudent, Roadix, Tentación a Granel...).

## Pasos
1. Pregunta el cliente y el periodo si no están claros.
2. Reúne el contexto del mes: hitos, tareas cerradas, métricas y pendientes
   (memoria QCORE + notas del vault del producto).
3. Redacta el informe con secciones: Resumen ejecutivo · Avances · Métricas ·
   Riesgos/bloqueos · Próximos pasos.
4. Guárdalo como documento (docx/markdown) y muéstralo en el Canvas.
5. Ofrece enviarlo por correo si corresponde.

## Reglas
- Tono profesional y conciso; nada de relleno.
- Cifras siempre con su fuente; si un dato no existe, márcalo como "sin datos".

## Ejemplo
"Claudy, informe mensual de SmartStudent" → documento con las 5 secciones,
guardado y abierto en el Canvas.""",
    },
    {
        "slug": "vigilar-precio-web",
        "category": "Scraping",
        "title": "Vigilar precio/stock de una web",
        "description": "Monitorea una página y avisa por Telegram cuando cambie precio, stock o un texto.",
        "body": """---
name: vigilar-precio-web
description: Monitorea una página y avisa por Telegram cuando cambie precio, stock o un texto.
---

# Vigilar precio o stock de una web

## Cuándo usarla
Cuando Felipe diga "avísame cuando baje el precio de X" o "vigila si vuelve el
stock de Y". Se apoya en el watcher existente (/vigilar).

## Pasos
1. Identifica la URL y QUÉ se vigila (precio, "agotado" → "disponible", un texto).
2. Registra la vigilancia con /vigilar (o features/watcher) con un intervalo
   razonable (cada 1-6 h según urgencia).
3. Al detectar el cambio, avisa por Telegram con el valor viejo y el nuevo.
4. Pregunta si se mantiene la vigilancia o se cierra tras el primer aviso.

## Reglas
- No vigiles con intervalos agresivos (< 30 min) salvo que Felipe lo pida: respeta el sitio.
- Guarda el último valor visto para comparar y no avisar dos veces por lo mismo.

## Ejemplo
"Claudy, avísame si esta notebook baja de $500.000" → vigilancia cada 3 h,
aviso por Telegram al cruzar el umbral.""",
    },
    {
        "slug": "extraer-datos-pdf-factura",
        "category": "Scraping",
        "title": "Extraer datos de un PDF de factura",
        "description": "Lee un PDF de factura y extrae emisor, número, fecha, neto, IVA y total.",
        "body": """---
name: extraer-datos-pdf-factura
description: Lee un PDF de factura y extrae emisor, número, fecha, neto, IVA y total en datos limpios.
---

# Extraer datos de un PDF de factura

## Cuándo usarla
Cuando Felipe arrastre o pegue un PDF/imagen de factura y pida "sácame los datos"
o "regístrala". También al procesar lotes de facturas recibidas.

## Pasos
1. Extrae el texto del PDF (o usa visión si es una imagen/escaneo).
2. Identifica: emisor, RUT, nº de documento, fecha, neto, IVA y total.
3. Devuelve los datos como tabla o JSON limpio, validando que neto+IVA = total.
4. Si Felipe lo pide, registra la factura en la planilla/registro correspondiente.

## Reglas
- Si un campo no aparece, déjalo vacío y avísalo; no lo inventes.
- Verifica la aritmética (neto + IVA = total) y señala discrepancias.

## Ejemplo
Pega una factura PDF → tabla con emisor, nº, fecha, neto, IVA, total y el aviso
"neto+IVA cuadra con el total".""",
    },
    {
        "slug": "backup-vault-qcore",
        "category": "Procesos",
        "title": "Respaldo del vault QCORE",
        "description": "Verifica y resume el estado del respaldo del vault de memorias QCORE.",
        "body": """---
name: backup-vault-qcore
description: Verifica y resume el estado del respaldo del vault de memorias QCORE.
---

# Respaldo del vault QCORE

## Cuándo usarla
Cuando Felipe pida "revisa el backup" o periódicamente (agéndalo semanal) para
asegurar que la memoria del ecosistema esté respaldada.

## Pasos
1. Localiza el vault QCORE (G:/Mi unidad/QCORE-ECOSYSTEM/MEMORIAS/VAULT).
2. Cuenta notas .md y revisa la fecha de la nota más reciente.
3. Confirma que Drive está sincronizado (no hay conflictos ni archivos a medias).
4. Resume: nº de notas, última modificación, estado de sincronización.

## Reglas
- Nunca borres ni muevas notas del vault en este proceso: es solo verificación.
- Si detectas algo raro (0 notas, carpeta ausente), alértalo de inmediato.

## Ejemplo
"Claudy, ¿está respaldada la memoria?" → "1.240 notas, última de hoy 14:30,
Drive sincronizado ✓".""",
    },
]


def _frontmatter_name(body):
    m = re.search(r"^name:\s*(.+)$", body[:300], re.M)
    return m.group(1).strip() if m else ""


class RecipesMixin:
    """Comandos del catálogo de recetas QCORE. Mixin de ClawdPet: usa
    _skill_dir, _save_skill_meta, _load_skill_meta, _installed_skill_slugs."""

    def _recipe_by_slug(self, slug):
        slug = (slug or "").strip().lower()
        for r in RECIPES:
            if r["slug"] == slug:
                return r
        return None

    def _recipes_catalog(self, query=""):
        """Lista el catálogo, opcionalmente filtrado por texto. Marca instaladas."""
        query = (query or "").strip().lower()
        installed = set(self._installed_skill_slugs())
        items = RECIPES
        if query:
            def _hit(r):
                hay = f"{r['slug']} {r['title']} {r['description']} {r['category']}".lower()
                return all(tok in hay for tok in query.split())
            items = [r for r in RECIPES if _hit(r)]
        if not items:
            return (f"No hay recetas QCORE que coincidan con «{query}».\n"
                    "Mira el catálogo completo con /recetas.")
        by_cat = {}
        for r in items:
            by_cat.setdefault(r["category"], []).append(r)
        lines = ["📚 Catálogo de recetas QCORE"]
        if query:
            lines[0] += f" — filtro «{query}»"
        for cat in sorted(by_cat):
            lines.append(f"\n— {cat} —")
            for r in by_cat[cat]:
                mark = " ✓ instalada" if r["slug"] in installed else ""
                lines.append(f"  • {r['slug']}: {r['title']}{mark}")
                lines.append(f"      {r['description']}")
        lines.append("\nInstala con: /receta instalar <slug>  (o «todas» para el set base)")
        return "\n".join(lines)

    def _install_recipe(self, slug):
        """Instala una receta del catálogo como skill local. 'todas' instala el set."""
        slug = (slug or "").strip().lower()
        if not slug:
            return "Uso: /receta instalar <slug>  (mira /recetas para ver los slugs)"
        if slug in ("todas", "todo", "all", "base"):
            done, skipped = [], []
            for r in RECIPES:
                ok, _ = self._write_recipe(r)
                (done if ok else skipped).append(r["slug"])
            msg = f"Instaladas {len(done)} recetas QCORE: {', '.join(done)}."
            if skipped:
                msg += f"\nYa estaban: {', '.join(skipped)}."
            return msg
        r = self._recipe_by_slug(slug)
        if not r:
            return (f"No encuentro la receta «{slug}» en el catálogo.\n"
                    "Mira los slugs disponibles con /recetas.")
        ok, where = self._write_recipe(r)
        if not ok:
            return f"La receta «{slug}» ya estaba instalada en {where}."
        return (f"✓ Receta instalada: {r['title']} ({slug})\n"
                f"Guardada en: {where}\nSe cargará automáticamente en cada conversación.")

    def _write_recipe(self, recipe):
        """Escribe el SKILL.md de la receta. Devuelve (instalada_ahora, ruta)."""
        slug = recipe["slug"]
        folder = self._skill_dir(slug)
        path = os.path.join(folder, "SKILL.md")
        if os.path.isfile(path):
            return False, path
        os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(recipe["body"])
        try:
            meta = self._load_skill_meta(slug)
            meta["origin"] = "recipe"
            meta["category"] = recipe["category"]
            self._save_skill_meta(slug, meta)
        except Exception:
            pass
        return True, path
