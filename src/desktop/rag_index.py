"""Local RAG index for Claudy.

Indexes the user's own folders/documents and answers queries by retrieving the
most relevant chunks. Designed to be self-contained and degrade gracefully:

  - Embeddings use ``sentence-transformers`` (all-MiniLM-L6-v2) when available.
  - If that model can't load (offline / not installed), it falls back to a
    dependency-free hashed bag-of-words vector so search still works (degraded).

Everything is persisted under ``~/.claudy/rag/`` so the index survives restarts.

Public API
----------
    index_folder(path, recursive=True, max_files=2000) -> dict   # build/update
    search(query, k=4) -> list[dict]                             # retrieve
    status() -> dict                                             # what's indexed
    clear() -> None                                             # wipe the index

Each search hit is ``{"path": str, "chunk": str, "score": float}``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time

RAG_DIR = os.path.join(os.path.expanduser("~"), ".claudy", "rag")
VECS_PATH = os.path.join(RAG_DIR, "vectors.jsonl")
META_PATH = os.path.join(RAG_DIR, "meta.json")

# File types we can read as plain text directly.
TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".json", ".csv", ".tsv", ".html", ".htm", ".css", ".xml", ".yaml",
    ".yml", ".ini", ".cfg", ".log", ".sql", ".java", ".c", ".cpp", ".h",
    ".go", ".rs", ".rb", ".php", ".sh", ".ps1", ".bat",
}
# File types that need an optional extractor (handled best-effort).
DOC_EXTS = {".pdf", ".docx", ".pptx", ".xlsx"}

CHUNK_CHARS = 900
CHUNK_OVERLAP = 150
HASH_DIM = 384  # matches MiniLM dim so both paths are interchangeable

_model = None
_model_tried = False


# ----------------------------------------------------------------------------
# Embeddings
# ----------------------------------------------------------------------------
def _get_model():
    """Lazy-load the sentence-transformers model once; None if unavailable."""
    global _model, _model_tried
    if _model_tried:
        return _model
    _model_tried = True
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        _model = None
    return _model


# Function words add noise to the bag-of-words fallback (they match everything),
# so we drop them before hashing. Only used by the dependency-free path.
_STOPWORDS = {
    # Spanish
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "en", "y", "o", "u", "a", "que", "como", "con", "por", "para", "su", "sus",
    "lo", "le", "les", "se", "es", "son", "mi", "tu", "te", "me", "ya", "muy",
    "mas", "pero", "si", "no", "este", "esta", "esto", "ese", "esa", "eso",
    "hago", "hace", "hacer", "donde", "cuando", "cual", "quien", "the",
    # English
    "an", "of", "in", "on", "to", "is", "are", "and", "or", "for", "with",
    "this", "that", "it", "as", "be", "at", "by", "how", "do", "i",
}


def _hash_embed(text: str, dim: int = HASH_DIM):
    """Dependency-free fallback embedding: hashed bag-of-words, L2-normalized.
    Stopwords are dropped so common function words don't dominate similarity."""
    vec = [0.0] * dim
    for tok in re.findall(r"[a-záéíóúñü0-9]{2,}", text.lower()):
        if tok in _STOPWORDS:
            continue
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(texts):
    """Return a list of vectors (lists of floats) for the given texts."""
    model = _get_model()
    if model is not None:
        try:
            arr = model.encode(texts, normalize_embeddings=True)
            return [list(map(float, row)) for row in arr]
        except Exception:
            pass
    return [_hash_embed(t) for t in texts]


def _cosine(a, b):
    # Vectors are L2-normalized on both paths, so dot product == cosine.
    n = min(len(a), len(b))
    return sum(a[i] * b[i] for i in range(n))


# ----------------------------------------------------------------------------
# Text extraction + chunking
# ----------------------------------------------------------------------------
def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def _read_doc_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        if ext == ".docx":
            import docx  # python-docx
            d = docx.Document(path)
            return "\n".join(p.text for p in d.paragraphs)
        if ext == ".pptx":
            from pptx import Presentation
            prs = Presentation(path)
            out = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        out.append(shape.text)
            return "\n".join(out)
        if ext == ".xlsx":
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True, data_only=True)
            out = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    out.append("\t".join("" if c is None else str(c) for c in row))
            return "\n".join(out)
    except Exception:
        return ""
    return ""


def _extract(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTS:
        return _read_text_file(path)
    if ext in DOC_EXTS:
        return _read_doc_file(path)
    return ""


def _chunk(text: str):
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        chunk = text[i:i + CHUNK_CHARS].strip()
        if chunk:
            chunks.append(chunk)
        if i + CHUNK_CHARS >= n:
            break
        i += CHUNK_CHARS - CHUNK_OVERLAP
    return chunks


# ----------------------------------------------------------------------------
# Persistence
# ----------------------------------------------------------------------------
def _load_records():
    records = []
    if not os.path.exists(VECS_PATH):
        return records
    try:
        with open(VECS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except Exception:
        return []
    return records


def _write_records(records):
    os.makedirs(RAG_DIR, exist_ok=True)
    tmp = VECS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, VECS_PATH)


def _save_meta(meta):
    os.makedirs(RAG_DIR, exist_ok=True)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _load_meta():
    if not os.path.exists(META_PATH):
        return {"folders": [], "files": 0, "chunks": 0, "updated": 0, "backend": ""}
    try:
        with open(META_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"folders": [], "files": 0, "chunks": 0, "updated": 0, "backend": ""}


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------
def index_folder(path: str, recursive: bool = True, max_files: int = 2000) -> dict:
    """Index every supported file under ``path``. Re-indexing replaces prior
    chunks for the same files (idempotent per file)."""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return {"ok": False, "error": f"No es una carpeta: {path}"}

    valid_exts = TEXT_EXTS | DOC_EXTS
    targets = []
    if recursive:
        for root, _dirs, files in os.walk(path):
            # Skip noise directories.
            if any(part in root for part in (os.sep + "node_modules", os.sep + ".git",
                                             os.sep + "__pycache__", os.sep + ".venv")):
                continue
            for name in files:
                if os.path.splitext(name)[1].lower() in valid_exts:
                    targets.append(os.path.join(root, name))
    else:
        for name in os.listdir(path):
            fp = os.path.join(path, name)
            if os.path.isfile(fp) and os.path.splitext(name)[1].lower() in valid_exts:
                targets.append(fp)

    targets = targets[:max_files]
    if not targets:
        return {"ok": False, "error": "No encontré archivos indexables en esa carpeta."}

    records = _load_records()
    indexed_paths = {os.path.abspath(p) for p in targets}
    # Drop old chunks for files we're about to re-index.
    records = [r for r in records if r.get("path") not in indexed_paths]

    new_chunks = []
    chunk_texts = []
    files_done = 0
    for fp in targets:
        text = _extract(fp)
        if not text.strip():
            continue
        chunks = _chunk(text)
        if not chunks:
            continue
        files_done += 1
        for ci, ch in enumerate(chunks):
            chunk_texts.append(ch)
            new_chunks.append({"path": os.path.abspath(fp), "i": ci, "chunk": ch})

    # Embed in batches to keep memory reasonable.
    BATCH = 64
    for start in range(0, len(chunk_texts), BATCH):
        batch = chunk_texts[start:start + BATCH]
        vecs = embed(batch)
        for j, v in enumerate(vecs):
            new_chunks[start + j]["vec"] = v

    records.extend(new_chunks)
    _write_records(records)

    meta = _load_meta()
    folders = set(meta.get("folders", []))
    folders.add(path)
    backend = "sentence-transformers" if _get_model() is not None else "hash-fallback"
    meta = {
        "folders": sorted(folders),
        "files": len({r["path"] for r in records}),
        "chunks": len(records),
        "updated": int(time.time()),
        "backend": backend,
    }
    _save_meta(meta)
    return {
        "ok": True,
        "folder": path,
        "files_indexed": files_done,
        "chunks_added": len(new_chunks),
        "total_chunks": len(records),
        "backend": backend,
    }


def search(query: str, k: int = 4):
    """Return the top-k most relevant chunks for the query."""
    records = _load_records()
    if not records:
        return []
    qv = embed([query])[0]
    scored = []
    for r in records:
        v = r.get("vec")
        if not v:
            continue
        scored.append((_cosine(qv, v), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, r in scored[:k]:
        out.append({"path": r["path"], "chunk": r["chunk"], "score": round(float(score), 4)})
    return out


def status() -> dict:
    meta = _load_meta()
    meta["exists"] = os.path.exists(VECS_PATH)
    return meta


def clear() -> None:
    for p in (VECS_PATH, META_PATH):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
