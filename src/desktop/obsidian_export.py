"""Export/sync Claudy memory to an Obsidian-compatible vault.

Structure:
  <vault>/
    Claudy/
      README.md           index del vault
      Daily/
        2026-05-18.md     conversaciones del dia
      Topics/
        <topic>.md        menciones por tema
      Sessions/
        <id>.md           sesion completa
"""
import datetime
import json
import os
import re
import sqlite3


STOPWORDS = {
    "a", "ante", "bajo", "con", "de", "del", "desde", "el", "la", "los", "las",
    "en", "entre", "es", "ese", "esa", "esos", "esas", "esto", "eso", "esta",
    "este", "estos", "estas", "hacia", "hasta", "lo", "no", "o", "para", "pero",
    "por", "que", "se", "sin", "sobre", "tras", "un", "una", "unos", "unas", "y",
    "soy", "eres", "es", "somos", "son", "fue", "ser", "estar", "estoy", "estas",
    "esta", "estamos", "estan", "claudy", "felipe", "usuario",
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
    "le", "te", "me", "nos", "les", "su", "sus", "mi", "mis", "tu", "tus",
    "como", "donde", "cuando", "porque", "para", "muy", "mas", "menos", "tan",
    "aqui", "ahi", "alli", "asi", "tambien", "solo", "todo", "todos", "todas",
    "puede", "puedes", "puedo", "podria", "podrias", "voy", "vamos",
    "ok", "hola", "gracias", "bien", "buena", "buen", "buenas", "buenos",
    "si", "no", "haz", "haga", "hacer", "hace", "tengo", "tienes", "tiene",
    "necesito", "necesitas", "quiero", "quieres", "ver", "ya", "aun",
    "yo", "tu", "el", "ella", "nosotros", "vosotros", "ellos", "ellas",
    "uno", "dos", "tres", "cuatro", "cinco", "muchas", "muchos", "varios",
}


def _vault_root(vault):
    """Return base directory inside the vault for Claudy notes."""
    root = os.path.join(vault, "Claudy")
    return root


def _ensure_dirs(vault):
    """Create the Claudy/* structure inside the vault."""
    root = _vault_root(vault)
    for sub in ("", "Daily", "Topics", "Sessions"):
        os.makedirs(os.path.join(root, sub) if sub else root, exist_ok=True)
    return root


def _slugify(text, max_len=40):
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text)
    text = text.strip("-")[:max_len] or "sin-titulo"
    return text


def _extract_topics(text, max_topics=5):
    """Heuristic: find capitalized words (>3 chars) or common nouns."""
    if not text:
        return []
    # Words starting with uppercase (proper nouns, etc.)
    candidates = re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,15}\b", text)
    # Also pick words quoted or after #
    candidates += re.findall(r"#(\w{3,20})", text)
    # Filter
    out = []
    seen = set()
    for c in candidates:
        low = c.lower()
        if low in STOPWORDS:
            continue
        if low in seen:
            continue
        seen.add(low)
        out.append(c)
        if len(out) >= max_topics:
            break
    return out


def _front(meta):
    """Build YAML frontmatter."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---\n")
    return "\n".join(lines)


def _append_section(file_path, header, body):
    """Append a markdown section, creating frontmatter if file is new."""
    existed = os.path.exists(file_path)
    if not existed:
        meta = {"created": datetime.datetime.now().isoformat(timespec="seconds"), "tags": ["claudy"]}
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(_front(meta))
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"\n## {header}\n\n{body}\n")


def append_today(vault, role, text):
    """Append a message to today's daily note + relevant Topics."""
    if not vault:
        return
    try:
        root = _ensure_dirs(vault)
    except Exception as e:
        print(f"[obsidian] no se puede escribir en vault: {e}")
        return
    today = datetime.date.today().isoformat()
    daily = os.path.join(root, "Daily", f"{today}.md")
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    # Detect topics and embed as [[wiki-links]]
    topics = _extract_topics(text, max_topics=3)
    text_with_links = text
    for t in topics:
        # Wrap first occurrence as wiki-link
        text_with_links = re.sub(
            rf"\b{re.escape(t)}\b",
            f"[[Topics/{_slugify(t)}|{t}]]",
            text_with_links,
            count=1,
        )
    label = "**Felipe**" if role.lower() in ("usuario", "user", "felipe") else "**Claudy**"
    body = f"[{ts}] {label}: {text_with_links}"

    # Append to daily as plain log line
    if not os.path.exists(daily):
        with open(daily, "w", encoding="utf-8") as f:
            f.write(_front({"date": today, "tags": ["claudy", "daily"]}))
            f.write(f"# {today}\n\n")
    with open(daily, "a", encoding="utf-8") as f:
        f.write(body + "\n\n")

    # Append to each topic
    for t in topics:
        slug = _slugify(t)
        topic_file = os.path.join(root, "Topics", f"{slug}.md")
        first_time = not os.path.exists(topic_file)
        if first_time:
            with open(topic_file, "w", encoding="utf-8") as f:
                f.write(_front({"name": t, "tags": ["claudy", "topic"]}))
                f.write(f"# {t}\n\nMenciones:\n\n")
        with open(topic_file, "a", encoding="utf-8") as f:
            f.write(f"- {today} {ts} {label}: {text[:200]}{'...' if len(text) > 200 else ''} → [[Daily/{today}]]\n")


def full_sync(vault, memory_db, since=None):
    """Sync entire memory.db to the vault. Returns counts."""
    root = _ensure_dirs(vault)
    if not os.path.exists(memory_db):
        return {"error": f"No existe memory.db: {memory_db}"}
    conn = sqlite3.connect(memory_db)
    rows = conn.execute("SELECT id, role, text, created_at FROM memory ORDER BY id ASC").fetchall()
    conn.close()
    if not rows:
        return {"messages": 0}
    # Group by day
    by_day = {}
    for _id, role, text, created_at in rows:
        try:
            if isinstance(created_at, str) and "T" in created_at:
                d = created_at[:10]
            elif isinstance(created_at, (int, float)):
                d = datetime.date.fromtimestamp(created_at).isoformat()
            else:
                d = datetime.date.today().isoformat()
        except Exception:
            d = datetime.date.today().isoformat()
        by_day.setdefault(d, []).append((role, text or "", created_at))

    total_topics = set()
    for day, items in by_day.items():
        daily = os.path.join(root, "Daily", f"{day}.md")
        with open(daily, "w", encoding="utf-8") as f:
            f.write(_front({"date": day, "tags": ["claudy", "daily"]}))
            f.write(f"# {day}\n\n")
            for role, text, created_at in items:
                topics = _extract_topics(text, max_topics=3)
                total_topics.update(_slugify(t) for t in topics)
                text_with_links = text
                for t in topics:
                    text_with_links = re.sub(
                        rf"\b{re.escape(t)}\b",
                        f"[[Topics/{_slugify(t)}|{t}]]",
                        text_with_links, count=1,
                    )
                label = "**Felipe**" if role.lower() in ("usuario", "user", "felipe") else "**Claudy**"
                ts = ""
                try:
                    if isinstance(created_at, str) and "T" in created_at:
                        ts = created_at[11:19]
                except Exception:
                    pass
                f.write(f"[{ts}] {label}: {text_with_links}\n\n")

    # Build topic pages aggregating across all days
    topic_index = {}
    for day, items in by_day.items():
        for role, text, created_at in items:
            for t in _extract_topics(text, max_topics=3):
                slug = _slugify(t)
                topic_index.setdefault(slug, {"name": t, "mentions": []})
                topic_index[slug]["mentions"].append((day, role, text[:200]))

    for slug, info in topic_index.items():
        topic_file = os.path.join(root, "Topics", f"{slug}.md")
        with open(topic_file, "w", encoding="utf-8") as f:
            f.write(_front({"name": info["name"], "tags": ["claudy", "topic"]}))
            f.write(f"# {info['name']}\n\n## Menciones\n\n")
            for day, role, snippet in info["mentions"][-50:]:
                label = "Felipe" if role.lower() in ("usuario", "user", "felipe") else "Claudy"
                f.write(f"- [[Daily/{day}]] {label}: {snippet}\n")

    # README index
    readme = os.path.join(root, "README.md")
    with open(readme, "w", encoding="utf-8") as f:
        f.write(_front({"tags": ["claudy", "index"]}))
        f.write("# Claudy Vault\n\nMemoria sincronizada desde Claudy.\n\n")
        f.write("## Recientes\n\n")
        for day in sorted(by_day.keys(), reverse=True)[:10]:
            f.write(f"- [[Daily/{day}]]\n")
        f.write("\n## Top temas\n\n")
        sorted_topics = sorted(topic_index.items(), key=lambda x: -len(x[1]["mentions"]))[:20]
        for slug, info in sorted_topics:
            f.write(f"- [[Topics/{slug}|{info['name']}]] ({len(info['mentions'])} menciones)\n")

    return {
        "messages": len(rows),
        "days": len(by_day),
        "topics": len(topic_index),
        "vault": root,
    }
