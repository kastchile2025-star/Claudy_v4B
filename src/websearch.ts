/**
 * CLI Web Search — auto-detects when the user needs live info and fetches it.
 *
 * Priority:
 *   1. Claudy backend /api/search (ESPN, Open-Meteo, DuckDuckGo combined)
 *   2. Direct DuckDuckGo HTML scraping (fallback if backend is down)
 */

export interface WebSearchResult {
  title: string;
  snippet: string;
  url: string;
}

// ── Intent detection ──────────────────────────────────────────────────────────

const CURRENT_INFO_PATTERN =
  /\b(hoy|ayer|ultimo|ultima|ultimos|ultimas|último|última|últimos|últimas|reciente|actual|precio|clima|tiempo|temperatura|partido|marcador|goles|fixture|noticia|noticias|cotizacion|cotización|dolar|dólar|bitcoin|btc|agenda|calendario|resultado|resultados|cuando|cuándo|próximo|proximo|siguiente|jugará|jugara|juega)\b/i;

const EXPLICIT_SEARCH_PATTERN =
  /\b(?:busca en internet|busca por internet|buscar en internet|buscar por internet|búsqueda por internet|busqueda por internet|search the web|googlea|averigua|investiga)\b/i;

/**
 * Returns true if the message looks like something that needs live web data.
 */
export function shouldSearchWeb(message: string): boolean {
  const trimmed = message.trim();
  if (trimmed.startsWith('/')) return false;
  if (trimmed.length < 8) return false;
  return EXPLICIT_SEARCH_PATTERN.test(trimmed) || CURRENT_INFO_PATTERN.test(trimmed);
}

/**
 * Strips filler words and command prefixes to extract a clean search query.
 */
export function extractSearchQuery(message: string): string {
  return message
    .replace(/^\/search\s+/i, '')
    .replace(
      /\b(claudy|busca en internet|buscar en internet|busca por internet|buscar por internet|search the web|googlea|averigua|investiga|consulta|revisa|buscar|busca)\b/gi,
      ''
    )
    .replace(/\b(porfa|por favor|me dices|dime|sabes|quiero saber|puedes)\b/gi, '')
    .replace(/[?¿!¡]+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// ── Search execution ──────────────────────────────────────────────────────────

/**
 * Searches the web. Tries the Claudy backend first (richer results: ESPN,
 * Open-Meteo, DuckDuckGo). Falls back to direct DuckDuckGo if backend is down.
 */
export async function searchWeb(
  query: string,
  backendUrl = 'http://127.0.0.1:3001'
): Promise<WebSearchResult[]> {
  const normalized = extractSearchQuery(query);
  if (!normalized) return [];

  // Append current year if the query looks time-sensitive and doesn't already have a year
  const currentYear = new Date().getFullYear().toString();
  const hasYear = /\b20\d{2}\b/.test(normalized);
  const timeEnhanced = hasYear ? normalized : `${normalized} ${currentYear}`;

  // ── 1. Try Claudy backend API ──
  try {
    const url = new URL('/api/search', backendUrl);
    url.searchParams.set('q', timeEnhanced);
    const response = await fetch(url, {
      signal: typeof AbortSignal.timeout === 'function' ? AbortSignal.timeout(10_000) : undefined,
    });
    if (response.ok) {
      const data = (await response.json()) as { results?: WebSearchResult[] };
      if (data.results?.length) return data.results;
    }
  } catch {
    // Backend not running — fall through to direct search
  }

  // ── 2. Direct DuckDuckGo fallback ──
  return searchDuckDuckGoDirect(timeEnhanced);
}

// ── DuckDuckGo HTML scraper (standalone, no backend needed) ───────────────────

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

function extractHref(rawAnchor: string): string {
  const href = rawAnchor.match(/\shref=["']([^"']+)["']/i)?.[1] || '';
  if (!href) return '';
  try {
    const normalized = href.startsWith('//') ? `https:${href}` : href;
    const url = new URL(normalized, 'https://duckduckgo.com');
    const redirected = url.searchParams.get('uddg');
    return redirected ? decodeURIComponent(redirected) : url.toString();
  } catch {
    return href;
  }
}

async function searchDuckDuckGoDirect(query: string, limit = 5): Promise<WebSearchResult[]> {
  const response = await fetch(
    `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`,
    {
      headers: {
        'User-Agent':
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Claudy/0.1',
      },
      signal: typeof AbortSignal.timeout === 'function' ? AbortSignal.timeout(8_000) : undefined,
    }
  );

  if (!response.ok) return [];

  const html = await response.text();
  const blocks = html.split(/<div[^>]+class=["'][^"']*result[^"']*["'][^>]*>/i);
  const results: WebSearchResult[] = [];

  for (const block of blocks) {
    const anchor = block.match(
      /<a[^>]+class=["'][^"']*result__a[^"']*["'][^>]*>[\s\S]*?<\/a>/i
    )?.[0];
    if (!anchor) continue;

    const title = decodeHtml(anchor);
    const url = extractHref(anchor);
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
    if (results.length >= limit) break;
  }

  return results;
}

// ── Context formatting for LLM injection ──────────────────────────────────────

/**
 * Formats search results as a context block to inject into the LLM system prompt.
 */
export function formatSearchContext(query: string, results: WebSearchResult[]): string {
  if (results.length === 0) return '';

  const top = results.slice(0, 3);

  return [
    `=== INFORMACIÓN DE INTERNET (búsqueda: "${query}") ===`,
    'Usa estos datos para responder directamente. Da la respuesta como si la supieras, sin mencionar que buscaste:',
    '',
    ...top.map((r, i) =>
      `[${i + 1}] ${r.title}\n${r.snippet || ''}${r.url ? `\nFuente: ${r.url}` : ''}`
    ),
    '',
    '=== FIN ===',
  ].join('\n');
}
