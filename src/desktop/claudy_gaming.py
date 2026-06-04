"""Claudy Gaming — busca ROMs en archive.org, descarga emulador y lanza el juego.

Pipeline: parse query → search archive.org → download ROM → get emulator → launch
"""
import json
import os
import re
import ssl
import subprocess
import urllib.parse
import urllib.request
import zipfile

# ─── SSL context — bypass cert errors (common on Windows without certs) ───────
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode   = ssl.CERT_NONE


# ─── Headers de browser real (evita bloqueos de archive.org) ─────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",  # No gzip so we read raw bytes
}

# ─── Emuladores portables ─────────────────────────────────────────────────────
_EMULATORS = {
    "nes": {
        "name": "FCEUX",
        "exe": "fceux.exe",
        "alt_exe": ["fceux64.exe", "fceux.exe"],
        "gh_repo": "TASEmulators/fceux",
        "gh_asset_keywords": ["win64", "win32"],
        "urls": [
            "https://github.com/TASEmulators/fceux/releases/download/2.6.6/fceux-2.6.6-win64.zip",
            "https://github.com/TASEmulators/fceux/releases/download/2.6.4/fceux-2.6.4-win32.zip",
        ],
    },
    "snes": {
        "name": "Snes9x",
        "exe": "snes9x-x64.exe",
        "alt_exe": ["snes9x-x64.exe", "snes9x.exe", "snes9x64.exe"],
        "gh_repo": "snes9xgit/snes9x",
        "gh_asset_keywords": ["win32", "win64"],
        "urls": [
            "https://github.com/snes9xgit/snes9x/releases/download/1.62.3/snes9x-1.62.3-win32.zip",
        ],
    },
    "gba": {
        "name": "mGBA",
        "exe": "mGBA.exe",
        "alt_exe": ["mGBA.exe", "mgba.exe"],
        "gh_repo": "mgba-emu/mgba",
        "gh_asset_keywords": ["win64"],
        "urls": [
            "https://github.com/mgba-emu/mgba/releases/download/0.10.3/mGBA-0.10.3-win64.zip",
        ],
    },
    "gb": {
        "name": "mGBA",
        "exe": "mGBA.exe",
        "alt_exe": ["mGBA.exe", "mgba.exe"],
        "gh_repo": "mgba-emu/mgba",
        "gh_asset_keywords": ["win64"],
        "urls": [
            "https://github.com/mgba-emu/mgba/releases/download/0.10.3/mGBA-0.10.3-win64.zip",
        ],
    },
    "genesis": {
        "name": "Gens/GS",
        "exe": "Gens.exe",
        "alt_exe": ["Gens.exe", "gens.exe"],
        "urls": [
            "https://segaretro.org/images/7/75/Gens_GS_r7.7z",
        ],
    },
}


_ROM_EXTS = {
    "nes":     [".nes"],
    "snes":    [".sfc", ".smc"],
    "gba":     [".gba"],
    "gb":      [".gb", ".gbc"],
    "genesis": [".md", ".gen"],
}

_SYS_KEYWORDS = {
    "snes":    ["snes", "super nintendo", "super nes", "super famicom"],
    "gba":     ["gba", "game boy advance", "gameboy advance"],
    "gb":      ["game boy color", "gameboy color", "game boy", "gameboy", "gbc"],
    "genesis": ["genesis", "mega drive", "megadrive", "sega genesis"],
    "nes":     ["nes", "nintendo", "famicom"],
}

_SYS_SEARCH_TERM = {
    "nes":     "NES Nintendo",
    "snes":    "SNES Super Nintendo",
    "gba":     "GBA Game Boy Advance",
    "gb":      "Game Boy",
    "genesis": "Sega Genesis Mega Drive",
}

_SERIES_SYSTEM_HINTS = {
    "super mario world": ["snes"],
    "super metroid": ["snes"],
    "link to the past": ["snes"],
    "chrono trigger": ["snes"],
    "earthbound": ["snes"],
    "mega man x": ["snes"],
    "street fighter ii": ["snes"],
    "sonic": ["genesis"],
    "streets of rage": ["genesis"],
    "golden axe": ["genesis"],
    "pokemon": ["gba", "gb"],
    "metroid fusion": ["gba"],
}

# ─── Numeros en español → dígito ─────────────────────────────────────────────
_ES_NUMBERS = {
    "uno": "1", "dos": "2", "tres": "3", "cuatro": "4", "cinco": "5",
    "seis": "6", "siete": "7", "ocho": "8", "nueve": "9", "diez": "10",
    "primero": "1", "segundo": "2", "tercero": "3",
    "primera": "1", "segunda": "2", "tercera": "3",
    "ii": "2", "iii": "3", "iv": "4", "vi": "6", "vii": "7", "viii": "8",
}

def _translate_numbers(text):
    words = text.split()
    return " ".join(_ES_NUMBERS.get(w.lower().rstrip(".,;"), w) for w in words)


def _detect_system_and_game(query):
    """Returns (system_id, clean_game_name)."""
    q = query.lower()
    system = None
    for sys_id, keywords in _SYS_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                system = sys_id
                q = q.replace(kw, " ")
                break

    noise = [
        "quiero jugar", "quisiera jugar", "jugar a", "jugar el juego",
        "quiero", "jugar", "juego", "busca el rom", "descarga el rom",
        "busca", "descarga", "instala el emulador", "instala", "instalalo",
        "emulador", "emular", "poner", "pon", "abre", "abrir", "rom",
        "quier",  # typo variant of "quiero"
    ]
    for phrase in sorted(noise, key=len, reverse=True):
        q = re.sub(r'\b' + re.escape(phrase) + r'\b', ' ', q, flags=re.IGNORECASE)

    # Remove dangling articles/connectors
    q = re.sub(r'\b(de|del|el|la|los|las|un|una|para|con|que)\b', ' ', q, flags=re.IGNORECASE)

    game = _translate_numbers(" ".join(q.split()).strip())
    game = " ".join(game.split()).strip()
    return system, game


def _normalize_match_text(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _game_variants(game_name):
    """Return search name variants including spaced compound versions."""
    variants = [game_name]
    # spaced number: "megaman3" → "megaman 3"
    spaced_num = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', game_name)
    if spaced_num != game_name:
        variants.append(spaced_num)
    # insert space in compound names: "megaman" → "mega man"
    spaced_compound = re.sub(
        r'(mega)(man|drive)|(sonic)(the)|(donkey)(kong)|(kirby)(s)|(castlevania)|(metroid)',
        lambda m: ' '.join(filter(None, m.groups())), game_name, flags=re.IGNORECASE
    )
    # Simpler: insert space between lowercase→uppercase boundary patterns
    spaced_camel = re.sub(r'([a-z])([A-Z])', r'\1 \2', game_name)
    for v in [spaced_compound, spaced_camel]:
        if v != game_name and v not in variants:
            variants.append(v)
    # no-space version for reverse case: "Mega Man" → "MegaMan"
    nospace = re.sub(r'\s+', '', game_name)
    if nospace != game_name and nospace not in variants:
        variants.append(nospace)
    return list(dict.fromkeys(variants))


def _game_search_words(game_name):
    """
    Build a set of search words from the game name.
    Splits compound words so 'megaman' matches 'mega man 3 (usa).nes'.
    Includes digits as separate tokens.
    """
    _COMPOUNDS = {
        "megaman": ["mega", "man"],
        "castlevania": ["castlevania"],
        "donkeykong": ["donkey", "kong"],
        "metroid": ["metroid"],
        "zelda": ["zelda"],
        "mario": ["mario"],
        "kirby": ["kirby"],
    }
    words = game_name.lower().split()
    result = []
    for w in words:
        if w.isdigit():
            result.append(w)
        elif w in _COMPOUNDS:
            result.extend(_COMPOUNDS[w])
            result.append(w)  # keep original too
        elif len(w) > 2:
            result.append(w)
    return list(dict.fromkeys(result))


# ─── Known archive.org identifiers (large ROM sets, not game-specific) ────────
# Only include GENERAL collections that contain many different games
_KNOWN_IDENTIFIERS = {
    "nes": [], "snes": [], "gba": [], "gb": [], "genesis": [],
}


# ─── Game-series specific identifiers (only used when name matches) ───────────
_SERIES_IDENTIFIERS = {
    "nes": {
        "mega man": ["megaman-collection"],
        "megaman":  ["megaman-collection"],
        "zelda":    ["the-legend-of-zelda-nes"],
        "mario":    ["super-mario-bros-nes"],
    },
}


def _fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
        return json.loads(r.read())


def _resolve_github_url(repo, asset_keywords):
    """
    Use GitHub API to get a real binary download URL for a release asset.
    repo: e.g. 'TASEmulators/fceux'
    asset_keywords: list of strings that must appear (any) in the asset filename
    """
    try:
        api_headers = {**_HEADERS, "Accept": "application/vnd.github.v3+json"}
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers=api_headers,
        )
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            data = json.loads(r.read())
        for asset in data.get("assets", []):
            name = asset.get("name", "").lower()
            if any(kw.lower() in name for kw in asset_keywords):
                return asset.get("browser_download_url")
    except Exception:
        pass
    return None


def _download_file(url, dest_path, label="", progress_cb=None):
    """Download any file (ROM or emulator) using SSL context. Returns (True,'') or (False,err)."""
    if progress_cb and label:
        progress_cb(f"⬇️ Descargando {label}...")
    try:
        req = urllib.request.Request(url, headers={**_HEADERS, "Referer": "https://github.com/", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=180, context=_SSL_CTX) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total > 0:
                        pct = int(downloaded * 100 / total)
                        progress_cb(f"⬇️ {label}: {pct}%")
        return True, ""
    except Exception as e:
        return False, str(e)


def _download_rom_direct(url, dest_path, progress_cb=None):
    """Thin wrapper kept for backward compat."""
    return _download_file(url, dest_path, "ROM", progress_cb)


def _find_rom_in_files(files, target_exts, game_words):
    """
    Scan archive.org file list for a matching ROM.
    Returns (local_filename, archive_path) or (None, None).
      local_filename = flat basename safe for local disk (no subdirs)
      archive_path   = original path in archive (used in download URL)
    """
    digit_words = [w for w in game_words if w.isdigit()]
    name_words  = [w for w in game_words if not w.isdigit()]

    def _ok_strict(flo):
        # Digit must appear (e.g. "3" for Mega Man 3)
        if digit_words and not all(d in flo for d in digit_words):
            return False
        return bool(name_words) and any(w in flo for w in name_words)

    def _ok_loose(flo):
        return bool(name_words) and any(w in flo for w in name_words)

    def _to_local(arch_path):
        return os.path.basename(arch_path.replace("/", os.sep))

    # Pass 1: strict — name AND digit match
    for f in files:
        ap = f.get("name", "")
        if any(ap.lower().endswith(ext) for ext in target_exts):
            if _ok_strict(ap.lower()):
                return _to_local(ap), ap

    # Pass 2: loose — just name word match (no wrong game)
    for f in files:
        ap = f.get("name", "")
        if any(ap.lower().endswith(ext) for ext in target_exts):
            if _ok_loose(ap.lower()):
                return _to_local(ap), ap

    # Never return an unrelated ROM — caller will try next identifier
    return None, None



def search_rom(game_name, system, progress_cb=None):
    """
    Search archive.org for a ROM. Returns (download_url, local_filename) or (None, None).
    Strategies: series identifiers → text search.
    """
    target_exts = _ROM_EXTS.get(system, [".nes"]) + [".zip"]
    sys_term    = _SYS_SEARCH_TERM.get(system, "NES Nintendo")
    variants    = _game_variants(game_name)
    game_words  = _game_search_words(game_name)
    seen_idents = set()

    def _scan(ident):
        if ident in seen_idents:
            return None, None
        seen_idents.add(ident)
        try:
            files = _fetch_json(
                f"https://archive.org/metadata/{ident}/files", timeout=15
            ).get("result", [])
        except Exception:
            return None, None
        return _find_rom_in_files(files, target_exts, game_words)

    # ── Strategy 0: Series-specific identifiers ─────────────────────────
    game_lower = game_name.lower()
    for keyword, series_idents in _SERIES_IDENTIFIERS.get(system, {}).items():
        if keyword in game_lower:
            for ident in series_idents:
                if progress_cb:
                    progress_cb(f"🔍 Buscando en {ident}...")
                local, arch = _scan(ident)
                if local:
                    return (
                        f"https://archive.org/download/{ident}/{urllib.parse.quote(arch, safe='')}",
                        local,
                    )

    # ── Strategy 1: Text search with expanded queries ────────────────────
    for variant in variants:
        queries = [
            f"{variant} {sys_term} ROM",
            f"{variant} {system.upper()} ROM",
            f'"{variant}" {system.upper()}',
            f"{variant} ROM",
            variant,
        ]
        for q in queries:
            if progress_cb:
                progress_cb(f"🔍 Buscando '{variant}'...")
            search_url = (
                "https://archive.org/advancedsearch.php?"
                f"q={urllib.parse.quote(q)}&mediatype=software"
                "&fl[]=identifier,title&rows=15&output=json&sort[]=downloads+desc"
            )
            try:
                docs = _fetch_json(search_url, timeout=20).get("response", {}).get("docs", [])
            except Exception:
                continue
            for doc in docs:
                ident = doc.get("identifier", "")
                if not ident:
                    continue
                local, arch = _scan(ident)
                if local:
                    return (
                        f"https://archive.org/download/{ident}/{urllib.parse.quote(arch, safe='')}",
                        local,
                    )

    return None, None





def _guess_identifiers(game_name, system):
    """Generate many likely archive.org identifier patterns for a game."""
    words  = game_name.strip().split()
    cap    = "_".join(w.capitalize() for w in words)
    lo     = "-".join(w.lower() for w in words)
    plain  = "".join(w.capitalize() for w in words)
    lo_u   = "_".join(w.lower() for w in words)
    sys_lo = system.lower()
    candidates = [
        f"{cap}_USA", f"{cap}_(USA)", f"{cap}_-_(USA)",
        f"{cap}_USA_{system.upper()}", f"{cap}_{system.upper()}_USA",
        f"{lo}-{sys_lo}", f"{lo}-{sys_lo}-rom",
        f"{lo}-usa", f"{lo}-usa-{sys_lo}", f"{lo}-{sys_lo}-usa",
        f"{cap}", f"{lo}", f"{plain}", f"{lo_u}",
        f"{cap}_ROM", f"{lo}-rom", f"{plain}USA",
    ]
    seen, result = set(), []
    for c in candidates:
        if c and c not in seen:
            seen.add(c); result.append(c)
    return result


def search_rom_web(game_name, system, progress_cb=None):
    """DuckDuckGo web search fallback: find archive.org ROM via HTML scraping."""
    if progress_cb:
        progress_cb("🌐 Buscando en la web (DuckDuckGo)...")

    target_exts = _ROM_EXTS.get(system, [".nes"]) + [".zip"]
    game_words  = [w.lower() for w in game_name.split() if len(w) > 2 or w.isdigit()]
    sys_term    = _SYS_SEARCH_TERM.get(system, "NES")
    seen        = set()

    # ── Strategy A: DuckDuckGo HTML scraping ─────────────────────────
    queries = [
        f'site:archive.org "{game_name}" {sys_term} ROM',
        f'site:archive.org {game_name} {system.upper()} download rom',
    ]
    for q in queries:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", errors="replace")
        except Exception:
            continue

        idents = re.findall(
            r'archive\.org/(?:download|details)/([A-Za-z0-9._%-]+)', html
        )
        for ident in idents:
            ident = urllib.parse.unquote(ident).rstrip(".")
            if ident in seen or len(ident) < 3:
                continue
            seen.add(ident)
            if progress_cb:
                progress_cb(f"🔍 Revisando {ident}...")
            try:
                data  = _fetch_json(f"https://archive.org/metadata/{ident}/files", timeout=12)
                files = data.get("result", [])
                local_fname, arch_path = _find_rom_in_files(files, target_exts, game_words)
                if local_fname:
                    dl = f"https://archive.org/download/{ident}/{urllib.parse.quote(arch_path, safe='')}"
                    return dl, local_fname
            except Exception:
                continue

    # ── Strategy B: Guessed identifiers ──────────────────────────────
    if progress_cb:
        progress_cb("🔍 Probando identificadores directos...")
    for ident in _guess_identifiers(game_name, system):
        if ident in seen:
            continue
        seen.add(ident)
        try:
            data  = _fetch_json(f"https://archive.org/metadata/{ident}/files", timeout=10)
            files = data.get("result", [])
            if files:
                local_fname, arch_path = _find_rom_in_files(files, target_exts, game_words)
                if local_fname:
                    dl = f"https://archive.org/download/{ident}/{urllib.parse.quote(arch_path, safe='')}"
                    return dl, local_fname
        except Exception:
            continue

    return None, None


# Override the ROM matching helpers with less biased variants and better scoring.
def _game_variants(game_name):
    variants = [game_name]
    spaced_num = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', game_name)
    if spaced_num != game_name:
        variants.append(spaced_num)

    replacements = {
        "megaman": "mega man",
        "megadrive": "mega drive",
        "donkeykong": "donkey kong",
        "doubledragon": "double dragon",
        "finalfantasy": "final fantasy",
        "mariokart": "mario kart",
        "mortalkombat": "mortal kombat",
        "paperboy": "paper boy",
        "robocop": "robo cop",
        "rockman": "rock man",
        "sonicthehedgehog": "sonic the hedgehog",
        "streetfighter": "street fighter",
        "supermario": "super mario",
        "supermarioworld": "super mario world",
        "teenagemutantninjaturtles": "teenage mutant ninja turtles",
    }
    lower_game = game_name.lower()
    for compact, spaced in replacements.items():
        if compact in lower_game:
            variants.append(re.sub(compact, spaced, game_name, flags=re.IGNORECASE))

    spaced_camel = re.sub(r'([a-z])([A-Z])', r'\1 \2', game_name)
    if spaced_camel != game_name:
        variants.append(spaced_camel)

    nospace = re.sub(r'\s+', '', game_name)
    if nospace != game_name:
        variants.append(nospace)
    return list(dict.fromkeys(variants))


def _game_search_words(game_name):
    words = []
    for variant in _game_variants(game_name):
        words.extend(_normalize_match_text(variant).split())
    result = []
    for word in words:
        if word.isdigit() or len(word) > 2:
            result.append(word)
    return list(dict.fromkeys(result))


def _find_rom_in_files(files, target_exts, game_words):
    digit_words = [w for w in game_words if w.isdigit()]
    name_words = [w for w in game_words if not w.isdigit()]

    def _to_local(arch_path):
        return os.path.basename(arch_path.replace("/", os.sep))

    best = None
    best_score = -1

    for file_info in files:
        archive_path = file_info.get("name", "")
        archive_lower = archive_path.lower()
        if not any(archive_lower.endswith(ext) for ext in target_exts):
            continue

        normalized = _normalize_match_text(os.path.basename(archive_lower))
        if not normalized:
            continue

        matched_words = [w for w in name_words if w in normalized]
        if not matched_words:
            continue
        if digit_words and not all(d in normalized for d in digit_words):
            continue

        score = len(matched_words) * 14
        if digit_words:
            score += len(digit_words) * 12
        if normalized.startswith(" ".join(matched_words[:2])):
            score += 8
        if re.search(r"\b(usa|world|europe)\b", normalized):
            score += 3
        if re.search(r"\b(beta|proto|prototype|sample|demo|hack)\b", normalized):
            score -= 30
        if archive_lower.endswith(".zip"):
            score -= 1

        if score > best_score:
            best = (_to_local(archive_path), archive_path)
            best_score = score

    return best if best_score >= 14 else (None, None)


def _guess_identifiers(game_name, system):
    candidates = []
    sys_lo = system.lower()
    for variant in _game_variants(game_name):
        words = variant.strip().split()
        cap = "_".join(w.capitalize() for w in words)
        lo = "-".join(w.lower() for w in words)
        plain = "".join(w.capitalize() for w in words)
        lo_u = "_".join(w.lower() for w in words)
        candidates.extend([
            f"{cap}_USA", f"{cap}_(USA)", f"{cap}_-_(USA)",
            f"{cap}_USA_{system.upper()}", f"{cap}_{system.upper()}_USA",
            f"{lo}-{sys_lo}", f"{lo}-{sys_lo}-rom",
            f"{lo}-usa", f"{lo}-usa-{sys_lo}", f"{lo}-{sys_lo}-usa",
            f"{cap}", f"{lo}", f"{plain}", f"{lo_u}",
            f"{cap}_ROM", f"{lo}-rom", f"{plain}USA",
        ])
    seen, result = set(), []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
    return result


def search_rom(game_name, system, progress_cb=None):
    target_exts = _ROM_EXTS.get(system, [".nes"]) + [".zip"]
    sys_term = _SYS_SEARCH_TERM.get(system, "NES Nintendo")
    variants = _game_variants(game_name)
    game_words = _game_search_words(game_name)
    seen_idents = set()

    def _scan(ident):
        if ident in seen_idents:
            return None, None
        seen_idents.add(ident)
        try:
            files = _fetch_json(f"https://archive.org/metadata/{ident}/files", timeout=15).get("result", [])
        except Exception:
            return None, None
        return _find_rom_in_files(files, target_exts, game_words)

    game_lower = game_name.lower()
    for keyword, series_idents in _SERIES_IDENTIFIERS.get(system, {}).items():
        if keyword in game_lower:
            for ident in series_idents:
                if progress_cb:
                    progress_cb(f"Buscando en {ident}...")
                local, arch = _scan(ident)
                if local:
                    return f"https://archive.org/download/{ident}/{urllib.parse.quote(arch, safe='')}", local

    for variant in variants:
        queries = [
            f"{variant} {sys_term} ROM",
            f"{variant} {system.upper()} ROM",
            f'"{variant}" {system.upper()}',
            f"{variant} ROM",
            variant,
        ]
        for query in queries:
            if progress_cb:
                progress_cb(f"Buscando '{variant}'...")
            search_url = (
                "https://archive.org/advancedsearch.php?"
                f"q={urllib.parse.quote(query)}&mediatype=software"
                "&fl[]=identifier,title&rows=15&output=json&sort[]=downloads+desc"
            )
            try:
                docs = _fetch_json(search_url, timeout=20).get("response", {}).get("docs", [])
            except Exception:
                continue
            for doc in docs:
                ident = doc.get("identifier", "")
                if not ident:
                    continue
                local, arch = _scan(ident)
                if local:
                    return f"https://archive.org/download/{ident}/{urllib.parse.quote(arch, safe='')}", local

    return None, None


def search_rom_web(game_name, system, progress_cb=None):
    if progress_cb:
        progress_cb("Buscando en la web...")

    target_exts = _ROM_EXTS.get(system, [".nes"]) + [".zip"]
    game_words = _game_search_words(game_name)
    sys_term = _SYS_SEARCH_TERM.get(system, "NES")
    seen = set()

    queries = []
    for variant in _game_variants(game_name):
        queries.extend([
            f'site:archive.org "{variant}" {sys_term} ROM',
            f'site:archive.org {variant} {system.upper()} download rom',
        ])

    for query in dict.fromkeys(queries):
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=20) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception:
            continue

        idents = re.findall(r'archive\.org/(?:download|details)/([A-Za-z0-9._%-]+)', html)
        for ident in idents:
            ident = urllib.parse.unquote(ident).rstrip(".")
            if ident in seen or len(ident) < 3:
                continue
            seen.add(ident)
            if progress_cb:
                progress_cb(f"Revisando {ident}...")
            try:
                data = _fetch_json(f"https://archive.org/metadata/{ident}/files", timeout=12)
                files = data.get("result", [])
                local_fname, arch_path = _find_rom_in_files(files, target_exts, game_words)
                if local_fname:
                    dl = f"https://archive.org/download/{ident}/{urllib.parse.quote(arch_path, safe='')}"
                    return dl, local_fname
            except Exception:
                continue

    if progress_cb:
        progress_cb("Probando identificadores directos...")
    for ident in _guess_identifiers(game_name, system):
        if ident in seen:
            continue
        seen.add(ident)
        try:
            data = _fetch_json(f"https://archive.org/metadata/{ident}/files", timeout=10)
            files = data.get("result", [])
            if files:
                local_fname, arch_path = _find_rom_in_files(files, target_exts, game_words)
                if local_fname:
                    dl = f"https://archive.org/download/{ident}/{urllib.parse.quote(arch_path, safe='')}"
                    return dl, local_fname
        except Exception:
            continue

    return None, None


def _candidate_systems(system, game_name):
    if system:
        return [system]

    game_lower = game_name.lower()
    hinted = []
    for title_hint, systems in _SERIES_SYSTEM_HINTS.items():
        if title_hint in game_lower:
            hinted.extend(systems)
    for sys_id in ("nes", "snes", "gba", "gb", "genesis"):
        if sys_id not in hinted:
            hinted.append(sys_id)
    return hinted


def _get_emulator(system, progress_cb=None):
    """Download emulator if needed. Uses GitHub API for URL resolution. Returns exe path or None."""
    config = _EMULATORS.get(system)
    if not config:
        return None

    emu_dir = os.path.join(os.path.expanduser("~"), "Documents", "Claudy", "Emuladores", system)
    os.makedirs(emu_dir, exist_ok=True)

    exe_names = list(dict.fromkeys(
        [config["exe"].lower()] + [e.lower() for e in config.get("alt_exe", [])]
    ))

    def _find_exe():
        for root, _, files in os.walk(emu_dir):
            for f in files:
                if f.lower() in exe_names:
                    return os.path.join(root, f)
        # Last resort: any .exe that's not an installer
        for root, _, files in os.walk(emu_dir):
            for f in files:
                fl = f.lower()
                if fl.endswith(".exe") and "install" not in fl and "unins" not in fl:
                    return os.path.join(root, f)
        return None

    # Already installed?
    found = _find_exe()
    if found:
        return found

    # Build URL list — try GitHub API first, then fallback URLs
    urls = []
    gh_repo = config.get("gh_repo")
    if gh_repo:
        if progress_cb:
            progress_cb(f"🔗 Obteniendo URL de {config['name']} desde GitHub...")
        resolved = _resolve_github_url(gh_repo, config.get("gh_asset_keywords", ["win64", "win32"]))
        if resolved:
            urls.append(resolved)
    urls.extend(config.get("urls", []))

    last_err = "no URLs configured"
    for url in urls:
        if not url:
            continue
        pkg = os.path.join(emu_dir, "emulator.zip")
        if progress_cb:
            progress_cb(f"⬇️ Descargando {config['name']}...")
        ok, err = _download_file(url, pkg, config["name"], progress_cb)
        if not ok:
            last_err = err
            if progress_cb:
                progress_cb(f"⚠️ Fallo: {err[:80]}")
            if os.path.exists(pkg):
                os.remove(pkg)
            continue

        # Extract
        try:
            with zipfile.ZipFile(pkg, "r") as zf:
                zf.extractall(emu_dir)
            os.remove(pkg)
        except Exception as ex:
            last_err = f"extracción: {ex}"
            if os.path.exists(pkg):
                os.remove(pkg)
            continue

        found = _find_exe()
        if found:
            return found

    if progress_cb:
        progress_cb(f"❌ No se pudo obtener {config['name']}: {last_err}")
    return None





def _extract_if_zip(zip_path, system, dest_dir):
    """Unzip ROM and return path to inner ROM file."""
    exts = _ROM_EXTS.get(system, [".nes"])
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if any(name.lower().endswith(ext) for ext in exts):
                    zf.extract(name, dest_dir)
                    os.remove(zip_path)
                    extracted = os.path.join(dest_dir, name)
                    # Flatten: if extracted into subfolder, move up
                    if not os.path.isfile(extracted):
                        for root, _, fs in os.walk(dest_dir):
                            for ff in fs:
                                if ff == os.path.basename(name):
                                    extracted = os.path.join(root, ff)
                    return extracted
    except Exception:
        pass
    return zip_path


def _legacy_play_retro_game(query, progress_cb=None):
    """Main entry point: parse → search → download → emulate → launch."""
    system, game_name = _detect_system_and_game(query)
    if not game_name:
        return (
            "🎮 No entendí qué juego quieres, Felipe.\n"
            "Prueba: \"quiero jugar Mega Man 2 de NES\""
        )

    sys_name = _EMULATORS.get(system, {}).get("name", system.upper())
    games_dir = os.path.join(os.path.expanduser("~"), "Documents", "Claudy", "Juegos", system)
    os.makedirs(games_dir, exist_ok=True)

    if progress_cb:
        progress_cb(f"🎮 Buscando: {game_name} [{system.upper()}]")

    # ── 1. Search ROM — archive.org advancedsearch ───────────────────
    dl_url, fname = search_rom(game_name, system, progress_cb)

    # ── 1b. Fallback — DuckDuckGo + identifier guessing ──────────────
    if not dl_url:
        dl_url, fname = search_rom_web(game_name, system, progress_cb)

    if not dl_url:
        return (
            f"❌ No encontré el ROM de '{game_name}' ({system.upper()}).\n"
            "Escríbelo exactamente en inglés, por ejemplo:\n"
            "  \"quiero jugar Super Mario World SNES\"\n"
            "  \"jugar Mega Man 2 NES\""
        )


    # ── 2. Download ROM ──────────────────────────────────────────────
    rom_dest = os.path.join(games_dir, fname)

    if not os.path.isfile(rom_dest):
        ok, err = _download_rom_direct(dl_url, rom_dest, progress_cb)
        if not ok:
            # Retry with a slightly different URL encoding
            clean_url = dl_url.replace("%28", "(").replace("%29", ")")
            ok, err = _download_rom_direct(clean_url, rom_dest, progress_cb)
        if not ok:
            return (
                f"❌ No pude descargar el ROM de '{game_name}'.\n"
                f"Error: {err}\n"
                f"URL: {dl_url}"
            )

    # Extract if zip
    if rom_dest.lower().endswith(".zip"):
        if progress_cb:
            progress_cb("📦 Extrayendo ROM...")
        rom_dest = _extract_if_zip(rom_dest, system, games_dir)

    # ── 3. Get emulator ──────────────────────────────────────────────
    emu_path = _get_emulator(system, progress_cb)
    if not emu_path:
        return (
            f"❌ No pude obtener el emulador {sys_name}.\n"
            f"ROM guardado en: {rom_dest}"
        )

    # ── 4. Launch ────────────────────────────────────────────────────
    if progress_cb:
        progress_cb(f"🚀 Lanzando {game_name}...")
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([emu_path, rom_dest], creationflags=flags)
        return (
            f"🎮 ¡A jugar, Felipe!\n\n"
            f"🎯 {os.path.basename(rom_dest)}\n"
            f"🕹️ {sys_name}\n"
            f"📁 {games_dir}"
        )
    except Exception as e:
        return f"❌ Error al lanzar: {e}\nROM: {rom_dest}\nEmulador: {emu_path}"


def play_retro_game(query, progress_cb=None):
    """Improved entry point: parse, search across sane system candidates, download, emulate, launch."""
    system, game_name = _detect_system_and_game(query)
    if not game_name:
        return (
            "No entendi que juego quieres.\n"
            'Prueba: "quiero jugar Mega Man 2 de NES"'
        )

    searched_systems = []
    dl_url = None
    fname = None

    for candidate_system in _candidate_systems(system, game_name):
        searched_systems.append(candidate_system.upper())
        if progress_cb:
            progress_cb(f"Buscando: {game_name} [{candidate_system.upper()}]")
        dl_url, fname = search_rom(game_name, candidate_system, progress_cb)
        if not dl_url:
            dl_url, fname = search_rom_web(game_name, candidate_system, progress_cb)
        if dl_url:
            system = candidate_system
            break

    if not dl_url or not system:
        return (
            f"No encontre el ROM de '{game_name}'.\n"
            f"Sistemas probados: {', '.join(searched_systems) or 'ninguno'}.\n"
            "Prueba con el nombre en ingles y, si puedes, indica la consola.\n"
            'Ejemplos: "quiero jugar RoboCop de NES" o "quiero jugar Super Mario World de SNES".'
        )

    sys_name = _EMULATORS.get(system, {}).get("name", system.upper())
    games_dir = os.path.join(os.path.expanduser("~"), "Documents", "Claudy", "Juegos", system)
    os.makedirs(games_dir, exist_ok=True)
    rom_dest = os.path.join(games_dir, fname)

    if not os.path.isfile(rom_dest):
        ok, err = _download_rom_direct(dl_url, rom_dest, progress_cb)
        if not ok:
            clean_url = dl_url.replace("%28", "(").replace("%29", ")")
            ok, err = _download_rom_direct(clean_url, rom_dest, progress_cb)
        if not ok:
            return (
                f"No pude descargar el ROM de '{game_name}'.\n"
                f"Error: {err}\n"
                f"URL: {dl_url}"
            )

    if rom_dest.lower().endswith(".zip"):
        if progress_cb:
            progress_cb("Extrayendo ROM...")
        rom_dest = _extract_if_zip(rom_dest, system, games_dir)

    emu_path = _get_emulator(system, progress_cb)
    if not emu_path:
        return f"No pude obtener el emulador {sys_name}.\nROM guardado en: {rom_dest}"

    if progress_cb:
        progress_cb(f"Lanzando {game_name}...")
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([emu_path, rom_dest], creationflags=flags)
        return (
            "A jugar.\n\n"
            f"Juego: {os.path.basename(rom_dest)}\n"
            f"Emulador: {sys_name}\n"
            f"Carpeta: {games_dir}"
        )
    except Exception as exc:
        return f"Error al lanzar: {exc}\nROM: {rom_dest}\nEmulador: {emu_path}"
