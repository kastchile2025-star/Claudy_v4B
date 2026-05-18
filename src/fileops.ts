/**
 * File operations for the CLI — download, search-download, and execute files.
 *
 * Storage: ~/Downloads/Claudy/
 * Search: DuckDuckGo HTML (free, no API key)
 * Execute: Windows shell (os.startfile equivalent via cmd /c start)
 */

import fs from 'fs';
import os from 'os';
import path from 'path';
import { exec, execFile } from 'child_process';
import chalk from 'chalk';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

export interface FileOpResult {
  ok: boolean;
  message: string;
  path?: string;
  size?: string;
  results?: { title: string; url: string; snippet: string }[];
}

export interface FileIntent {
  action: 'download' | 'search-download' | 'execute' | 'auto-install';
  target: string; // URL, search query, or file path
}

// ── Download ─────────────────────────────────────────────────────────────────

function sanitizeFilename(name: string): string {
  const safe = [...name].filter((c) => /[a-zA-Z0-9._\- ]/.test(c)).join('');
  return safe || 'archivo_descargado';
}

async function extractFilename(url: string): Promise<string> {
  try {
    const parsed = new URL(url);
    const basename = path.basename(parsed.pathname);
    if (basename && basename.includes('.')) return basename;
  } catch { /* fall through */ }

  // Try HEAD request for Content-Disposition
  try {
    const resp = await fetch(url, {
      method: 'HEAD',
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Claudy/0.1' },
      signal: AbortSignal.timeout(8_000),
    });
    const cd = resp.headers.get('Content-Disposition') || '';
    if (cd.includes('filename=')) {
      if (cd.includes('filename*=')) {
        const raw = cd.split('filename*=')[1]?.split("''")[1];
        if (raw) return decodeURIComponent(raw);
      }
      const match = cd.match(/filename=["']?([^"';]+)["']?/);
      if (match) return match[1];
    }
    // Try Content-Type to guess extension
    const ct = resp.headers.get('Content-Type') || '';
    const extMap: Record<string, string> = {
      'application/pdf': '.pdf',
      'application/zip': '.zip',
      'application/x-rar-compressed': '.rar',
      'application/x-7z-compressed': '.7z',
      'application/x-msdownload': '.exe',
      'application/x-msi': '.msi',
      'image/png': '.png',
      'image/jpeg': '.jpg',
      'image/gif': '.gif',
      'image/webp': '.webp',
      'video/mp4': '.mp4',
      'audio/mpeg': '.mp3',
      'text/html': '.html',
      'text/plain': '.txt',
    };
    for (const [mime, ext] of Object.entries(extMap)) {
      if (ct.includes(mime)) return `descarga_claudy${ext}`;
    }
  } catch { /* HEAD failed, use fallback */ }

  return 'descarga_claudy';
}

export async function downloadFile(
  url: string,
  destDir?: string
): Promise<FileOpResult> {
  url = url.trim().replace(/^["']|["']$/g, '');
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    return { ok: false, message: 'URL inválida. Debe empezar con http:// o https://' };
  }

  const dir = destDir || path.join(os.homedir(), 'Downloads', 'Claudy');
  fs.mkdirSync(dir, { recursive: true });

  try {
    const filename = await extractFilename(url);
    const safeName = sanitizeFilename(filename);
    let destPath = path.join(dir, safeName);

    // Handle duplicates
    let counter = 1;
    const base = path.basename(safeName, path.extname(safeName));
    const ext = path.extname(safeName);
    while (fs.existsSync(destPath)) {
      destPath = path.join(dir, `${base}_${counter}${ext}`);
      counter++;
    }

    const resp = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Claudy/0.1' },
      signal: AbortSignal.timeout(120_000),
    });

    if (!resp.ok) {
      return { ok: false, message: `Error HTTP ${resp.status}: ${resp.statusText}` };
    }

    const buffer = Buffer.from(await resp.arrayBuffer());
    fs.writeFileSync(destPath, buffer);

    const sizeStr =
      buffer.length < 1024 * 1024
        ? `${(buffer.length / 1024).toFixed(1)} KB`
        : `${(buffer.length / (1024 * 1024)).toFixed(1)} MB`;

    return {
      ok: true,
      message: `Archivo descargado:\n${destPath}\nTamaño: ${sizeStr}`,
      path: destPath,
      size: sizeStr,
    };
  } catch (err: any) {
    if (err.name === 'TimeoutError' || err.name === 'AbortError') {
      return { ok: false, message: 'Timeout: la descarga tardó más de 120s.' };
    }
    return { ok: false, message: `Error descargando: ${err.message}` };
  }
}

// ── Search files online ──────────────────────────────────────────────────────

const FILE_EXTENSIONS = [
  '.pdf', '.zip', '.rar', '.7z', '.exe', '.msi', '.mp4', '.mp3',
  '.png', '.jpg', '.jpeg', '.gif', '.docx', '.xlsx', '.pptx', '.txt',
  '.csv', '.json', '.xml', '.iso', '.torrent', '.apk',
];

function decodeHtml(input: string): string {
  return input
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim();
}

export async function searchFilesOnline(query: string): Promise<FileOpResult> {
  const q = query.trim();
  if (!q || q.length < 2) {
    return { ok: false, message: 'Escribe qué archivo buscas. Ej: /buscar "python 3.12 installer"' };
  }

  // Boost file-related results by appending filetype keywords
  const fileQuery = `${q} filetype:pdf OR filetype:zip OR filetype:exe OR download`;

  try {
    const resp = await fetch(
      `https://html.duckduckgo.com/html/?q=${encodeURIComponent(fileQuery)}`,
      {
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Claudy/0.1' },
        signal: AbortSignal.timeout(10_000),
      }
    );

    if (!resp.ok) return { ok: false, message: 'Búsqueda falló. Intenta de nuevo.' };

    const html = await resp.text();
    const blocks = html.split(/<div[^>]+class=["'][^"']*result[^"']*["'][^>]*>/i);
    const results: { title: string; url: string; snippet: string }[] = [];

    for (const block of blocks) {
      const anchor = block.match(
        /<a[^>]+class=["'][^"']*result__a[^"']*["'][^>]*>[\s\S]*?<\/a>/i
      )?.[0];
      if (!anchor) continue;

      const title = decodeHtml(anchor);
      const hrefMatch = anchor.match(/\shref=["']([^"']+)["']/i);
      let url = hrefMatch?.[1] || '';

      // Resolve DuckDuckGo redirect
      if (url.startsWith('//')) url = `https:${url}`;
      try {
        const parsed = new URL(url, 'https://duckduckgo.com');
        const redirected = parsed.searchParams.get('uddg');
        if (redirected) url = decodeURIComponent(redirected);
      } catch { /* keep raw */ }

      const snippetRaw =
        block.match(
          /<a[^>]+class=["'][^"']*result__snippet[^"']*["'][^>]*>[\s\S]*?<\/a>/i
        )?.[0] ||
        block.match(
          /<div[^>]+class=["'][^"']*result__snippet[^"']*["'][^>]*>[\s\S]*?<\/div>/i
        )?.[0] ||
        '';
      const snippet = decodeHtml(snippetRaw);

      if (title && url && !results.some((r) => r.url === url)) {
        results.push({ title, snippet, url });
      }
      if (results.length >= 8) break;
    }

    if (results.length === 0) {
      return { ok: false, message: `No encontré resultados para "${q}". Prueba con otras palabras.` };
    }

    // Score results: prefer those with file extensions in URL
    const scored = results.map((r) => {
      let score = 0;
      const lower = r.url.toLowerCase();
      for (const ext of FILE_EXTENSIONS) {
        if (lower.includes(ext)) score += 10;
      }
      if (lower.includes('download')) score += 5;
      if (lower.includes('github')) score += 3;
      return { ...r, _score: score };
    });
    scored.sort((a, b) => b._score - a._score);

    return {
      ok: true,
      message: `Resultados para "${q}":`,
      results: scored.slice(0, 8).map(({ _score, ...r }) => r),
    };
  } catch {
    return { ok: false, message: 'Error conectando al buscador. Revisa tu internet.' };
  }
}

// ── Execute file ─────────────────────────────────────────────────────────────

export async function executeFile(filePath: string): Promise<FileOpResult> {
  filePath = filePath.trim().replace(/^["']|["']$/g, '');

  // Expand ~ and resolve
  let resolved = filePath;
  if (resolved.startsWith('~')) {
    resolved = path.join(os.homedir(), resolved.slice(1));
  }
  if (!path.isAbsolute(resolved)) {
    resolved = path.resolve(resolved);
  }

  if (!fs.existsSync(resolved)) {
    // Try common locations
    const bases = [os.homedir(), path.join(os.homedir(), 'Downloads'), path.join(os.homedir(), 'Desktop')];
    for (const base of bases) {
      const candidate = path.join(base, filePath);
      if (fs.existsSync(candidate)) {
        resolved = candidate;
        break;
      }
    }
    if (!fs.existsSync(resolved)) {
      return { ok: false, message: `No encuentro el archivo: ${filePath}` };
    }
  }

  const ext = path.extname(resolved).toLowerCase();
  const isExecutable = ['.exe', '.bat', '.cmd', '.ps1', '.msi', '.vbs', '.js'].includes(ext);

  try {
    if (process.platform === 'win32') {
      await new Promise<void>((resolve, reject) => {
        exec(`start "" "${resolved}"`, { windowsHide: true }, (err) => {
          if (err) reject(err);
          else resolve();
        });
      });
    } else {
      // macOS / Linux: xdg-open or open
      const cmd = process.platform === 'darwin' ? 'open' : 'xdg-open';
      await new Promise<void>((resolve, reject) => {
        exec(`"${cmd}" "${resolved}"`, (err) => {
          if (err) reject(err);
          else resolve();
        });
      });
    }

    const warn = isExecutable
      ? '\n⚠️  Es un ejecutable — asegúrate de confiar en la fuente.'
      : '';
    return {
      ok: true,
      message: `Abierto: ${resolved}${warn}`,
      path: resolved,
    };
  } catch (err: any) {
    return { ok: false, message: `Error ejecutando: ${err.message}` };
  }
}

// ── Full pipeline: search → download → execute ───────────────────────────────

const TRUSTED_DOMAINS = [
  'github.com', 'sourceforge.net', 'fosshub.com', 'ninite.com',
  'chocolatey.org', 'winget.run', 'microsoft.com', 'apps.microsoft.com',
  'apple.com', 'adobe.com', 'oracle.com', 'java.com', 'win-rar.com',
  'rarlab.com', 'videolan.org', 'notepad-plus-plus.org', '7-zip.org',
  'code.visualstudio.com',
];

const CLEANUP_WORDS = [
  'download', 'descargar', 'descarga', 'bajar', 'instalar', 'instala',
  'instalador', 'install', 'installer', 'gratis', 'free', 'latest',
  'ultima', 'última', 'version', 'versión',
];

function scoreDownloadUrl(url: string, query: string): number {
  let score = 0;
  const lower = url.toLowerCase();
  const qLower = query.toLowerCase();

  // File extensions that are installers
  if (/\.(exe|msi|dmg|pkg|apk|deb|rpm|appimage)$/i.test(lower)) score += 30;
  if (/\.(zip|7z|rar|tar\.gz|tar\.xz)$/i.test(lower)) score += 15;

  // Trusted domains
  for (const domain of TRUSTED_DOMAINS) {
    if (lower.includes(domain)) { score += 25; break; }
  }

  // URL contains app name keywords
  const appWords = qLower.split(/\s+/).filter(w => w.length > 2);
  for (const word of appWords) {
    if (lower.includes(word)) score += 5;
  }

  // Has "download" in URL
  if (lower.includes('download')) score += 5;
  // Has "release" in URL
  if (lower.includes('release')) score += 3;
  // HTTPS bonus
  if (lower.startsWith('https://')) score += 2;

  return score;
}

function cleanupAppName(input: string): string {
  let clean = input
    .trim()
    .replace(/^["']|["']$/g, '')
    .replace(/[.!?¿¡]+$/g, '')
    .replace(/\b(por favor|please)\b/gi, '')
    .trim();

  for (const word of CLEANUP_WORDS) {
    clean = clean.replace(new RegExp(`\\b${word}\\b`, 'gi'), ' ');
  }

  return clean.replace(/\s+/g, ' ').trim() || input.trim();
}

interface WingetPackage {
  name: string;
  id: string;
  version: string;
}

function splitWingetRow(line: string): string[] {
  return line.trim().split(/\s{2,}/).map((part) => part.trim()).filter(Boolean);
}

function parseWingetSearch(stdout: string, query: string): WingetPackage | null {
  const rows = stdout
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.trim() && !/^[-\s]+$/.test(line) && !/^Name\s+Id\s+/i.test(line));

  const queryWords = query.toLowerCase().split(/\s+/).filter((word) => word.length > 1);
  const candidates = rows
    .map((line) => {
      const parts = splitWingetRow(line);
      if (parts.length < 2) return null;
      if (parts[1].toLowerCase() === 'id') return null;
      return {
        name: parts[0],
        id: parts[1],
        version: parts[2] || '',
      };
    })
    .filter((pkg): pkg is WingetPackage => Boolean(pkg));

  if (candidates.length === 0) return null;

  const scored = candidates.map((pkg) => {
    const haystack = `${pkg.name} ${pkg.id}`.toLowerCase();
    let score = 0;
    if (pkg.name.toLowerCase() === query.toLowerCase()) score += 50;
    if (pkg.id.toLowerCase() === query.toLowerCase()) score += 50;
    for (const word of queryWords) {
      if (haystack.includes(word)) score += 10;
    }
    if (/^(rar|winrar)$/i.test(query) && /winrar/i.test(haystack)) score += 30;
    return { ...pkg, score };
  });

  scored.sort((a, b) => b.score - a.score);
  return scored[0];
}

async function installWithWinget(query: string): Promise<FileOpResult> {
  if (process.platform !== 'win32') {
    return { ok: false, message: 'winget solo aplica en Windows.' };
  }

  try {
    await execFileAsync('winget', ['--version'], { timeout: 10_000, windowsHide: true });
  } catch {
    return { ok: false, message: 'winget no esta disponible en este equipo.' };
  }

  const search = await execFileAsync(
    'winget',
    ['search', '--source', 'winget', '--accept-source-agreements', query],
    { timeout: 45_000, windowsHide: true, maxBuffer: 1024 * 1024 }
  );

  const pkg = parseWingetSearch(search.stdout, query);
  if (!pkg) {
    return { ok: false, message: `winget no encontro un paquete claro para "${query}".` };
  }

  const install = await execFileAsync(
    'winget',
    [
      'install',
      '--id', pkg.id,
      '--exact',
      '--source', 'winget',
      '--accept-package-agreements',
      '--accept-source-agreements',
    ],
    { timeout: 15 * 60_000, windowsHide: false, maxBuffer: 1024 * 1024 }
  );

  const output = [install.stdout, install.stderr].filter(Boolean).join('\n').trim();

  try {
    exec(`start "" "${pkg.name}"`, { windowsHide: true });
  } catch {
    // Some apps do not register a shell alias. Installation still succeeded.
  }

  return {
    ok: true,
    message: [
      `Instalado con winget: ${pkg.name}`,
      `Paquete: ${pkg.id}`,
      output ? `Salida:\n${output.slice(-2000)}` : '',
      `Intento de apertura enviado para: ${pkg.name}`,
    ].filter(Boolean).join('\n'),
  };
}

function isLikelyInstallerPath(filePath: string): boolean {
  return /\.(exe|msi|dmg|pkg|apk|deb|rpm|appimage)$/i.test(filePath);
}

export async function installApp(appName: string): Promise<FileOpResult> {
  const query = cleanupAppName(appName);
  if (!query || query.length < 2) {
    return { ok: false, message: 'Dime qué aplicación quieres instalar. Ej: /instalar winrar' };
  }

  const steps: string[] = [];

  steps.push(`Buscando instalador confiable para "${query}"...`);
  if (process.platform === 'win32') {
    try {
      const winget = await installWithWinget(query);
      if (winget.ok) {
        return {
          ok: true,
          message: [
            ...steps,
            'Use winget como fuente principal para evitar instaladores falsos.',
            winget.message,
          ].join('\n'),
        };
      }
      steps.push(`winget no resolvio la instalacion: ${winget.message}`);
    } catch (err: any) {
      steps.push(`winget fallo: ${err.message || String(err)}`);
    }
  }

  // Step 1: Search
  steps.push(`🔍 Buscando "${query}" en internet...`);
  const installQuery = `${query} official download windows installer`;
  const sr = await searchFilesOnline(installQuery);

  if (!sr.ok || !sr.results || sr.results.length === 0) {
    return { ok: false, message: `No encontré resultados para "${query}".` };
  }

  // Step 2: Score and pick best URL
  const scored = sr.results.map(r => ({
    ...r,
    _score: scoreDownloadUrl(r.url, query),
  }));
  scored.sort((a, b) => b._score - a._score);
  const best = scored[0];

  steps.push(`✓ Encontrado: ${best.title}`);
  steps.push(`  URL: ${best.url}`);

  // Step 3: Download
  steps.push(`⬇ Descargando...`);
  const dl = await downloadFile(best.url);
  if (!dl.ok || !dl.path) {
    steps.push(`✗ Error: ${dl.message}`);
    return { ok: false, message: steps.join('\n') };
  }

  steps.push(`✓ ${dl.message}`);
  if (!isLikelyInstallerPath(dl.path)) {
    steps.push('La descarga no parece ser un instalador ejecutable. No la ejecutare automaticamente.');
    return { ok: false, message: steps.join('\n'), path: dl.path };
  }

  steps.push(`  Guardado en: ${dl.path}`);

  // Step 4: Execute
  steps.push(`▶ Ejecutando...`);
  const ext = path.extname(dl.path).toLowerCase();
  if (['.exe', '.msi', '.bat', '.cmd'].includes(ext)) {
    steps.push('  ⚠️  Se abrirá el instalador — sigue los pasos en pantalla.');
  }

  const exec = await executeFile(dl.path);
  if (!exec.ok) {
    steps.push(`✗ Error ejecutando: ${exec.message}`);
    return { ok: false, message: steps.join('\n') };
  }

  steps.push(`✓ ${exec.message}`);
  return { ok: true, message: steps.join('\n'), path: dl.path };
}

// ── Natural language intent detection ────────────────────────────────────────

const URL_PATTERN = /https?:\/\/[^\s<>"]+/i;

const DOWNLOAD_KWS = [
  'descargar', 'descarga', 'descárgame', 'descargame', 'bajar', 'bajame', 'bájame',
  'download', 'trae este archivo', 'consigue este archivo', 'baja este archivo',
  'descarga este archivo', 'quiero descargar', 'necesito descargar',
];

const SEARCH_DOWNLOAD_KWS = [
  'busca para descargar', 'buscar para descargar', 'encuentra para descargar',
  'búscame', 'buscame', 'busca el archivo', 'buscar el archivo',
  'busca un', 'buscar un', 'busca una', 'buscar una',
  'busca el instalador', 'buscar el instalador',
  'donde descargar', 'dónde descargar', 'donde puedo descargar',
  'donde encontrar', 'dónde encontrar',
];

const EXECUTE_KWS = [
  'ejecutar', 'ejecuta', 'abrir archivo', 'abre el archivo', 'abre este archivo',
  'correr', 'corre el archivo', 'run file', 'lanza', 'abrir con',
];

const INSTALL_KWS = [
  'instalar', 'instala', 'instalame', 'instálame', 'baja e instala',
  'descarga e instala', 'bajar e instalar', 'descargar e instalar',
  'busca e instala', 'buscar e instalar', 'quiero instalar',
  'necesito instalar', 'puedes instalar', 'podrias instalar',
  'podrías instalar', 'me puedes instalar', 'me instalas',
  'consigueme e instala', 'consígueme e instala',
  'bajame e instala', 'bájame e instala',
];

export function parseFileIntent(input: string): FileIntent | null {
  const lower = input.toLowerCase().trim();
  if (!lower) return null;

  // ── Download: explicit URL + download intent ──
  const urls = lower.match(URL_PATTERN);
  if (urls && DOWNLOAD_KWS.some((kw) => lower.includes(kw))) {
    return { action: 'download', target: urls[0] };
  }

  // ── Search + download: no URL, but keywords like "busca X para descargar" ──
  if (!urls) {
    for (const kw of SEARCH_DOWNLOAD_KWS) {
      if (lower.includes(kw)) {
        const idx = lower.indexOf(kw) + kw.length;
        let target = input.slice(idx).trim();
        // Strip leading filler words
        target = target.replace(/^(de|del|la|el|los|las|un|una)\s+/i, '').trim();
        if (target.length >= 2) {
          return { action: 'search-download', target };
        }
      }
    }
  }

  // ── Execute: keywords + file path ──
  for (const kw of EXECUTE_KWS) {
    if (lower.includes(kw)) {
      const idx = lower.indexOf(kw) + kw.length;
      let target = input.slice(idx).trim();
      // Strip trailing punctuation
      target = target.replace(/[.!?¿¡]+$/, '').trim();
      if (target.length >= 2) {
        return { action: 'execute', target };
      }
    }
  }

  // ── Auto-install: "instala X", "baja e instala X" ──
  for (const kw of INSTALL_KWS) {
    if (lower.includes(kw)) {
      const idx = lower.indexOf(kw) + kw.length;
      let target = input.slice(idx).trim();
      target = target.replace(/[.!?¿¡]+$/, '').trim();
      // Strip leading filler words
      target = target.replace(/^(de|del|la|el|los|las|un|una)\s+/i, '').trim();
      if (target.length >= 2) {
        return { action: 'auto-install', target };
      }
    }
  }

  return null;
}
