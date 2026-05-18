import { listSessions, loadSession } from './utils.js';
import { Session, Message } from './types.js';

export interface SearchResult {
  session: Session;
  matches: MatchFragment[];
  relevanceScore: number;
}

export interface MatchFragment {
  messageId: string;
  role: 'user' | 'assistant';
  text: string;
  highlightedText: string;
  timestamp: number;
}

const CONTEXT_CHARS = 80;

function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s]/g, '');
}

function extractTerms(query: string): string[] {
  return normalizeText(query)
    .split(/\s+/)
    .filter((t) => t.length >= 2);
}

function highlightText(text: string, terms: string[]): string {
  let result = text;
  for (const term of terms) {
    const regex = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    result = result.replace(regex, '>>$1<<');
  }
  return result;
}

function extractFragment(message: Message, query: string, terms: string[]): MatchFragment | null {
  const normalizedContent = normalizeText(message.content);
  const normalizedQuery = normalizeText(query);

  const matchIndex = normalizedContent.indexOf(normalizedQuery);
  if (matchIndex === -1) {
    // Try individual terms
    let bestIndex = -1;
    let bestTerm = '';
    for (const term of terms) {
      const idx = normalizedContent.indexOf(term);
      if (idx !== -1 && (bestIndex === -1 || idx < bestIndex)) {
        bestIndex = idx;
        bestTerm = term;
      }
    }
    if (bestIndex === -1) return null;

    const start = Math.max(0, bestIndex - CONTEXT_CHARS);
    const end = Math.min(message.content.length, bestIndex + bestTerm.length + CONTEXT_CHARS);
    const fragment = message.content.slice(start, end);
    const prefix = start > 0 ? '...' : '';
    const suffix = end < message.content.length ? '...' : '';

    return {
      messageId: message.id,
      role: message.role,
      text: `${prefix}${fragment}${suffix}`,
      highlightedText: `${prefix}${highlightText(fragment, terms)}${suffix}`,
      timestamp: message.timestamp,
    };
  }

  const start = Math.max(0, matchIndex - CONTEXT_CHARS);
  const end = Math.min(message.content.length, matchIndex + query.length + CONTEXT_CHARS);
  const fragment = message.content.slice(start, end);
  const prefix = start > 0 ? '...' : '';
  const suffix = end < message.content.length ? '...' : '';

  return {
    messageId: message.id,
    role: message.role,
    text: `${prefix}${fragment}${suffix}`,
    highlightedText: `${prefix}${highlightText(fragment, terms)}${suffix}`,
    timestamp: message.timestamp,
  };
}

function scoreResult(result: SearchResult, terms: string[]): number {
  let score = 0;

  // Session name match (high weight)
  const normalizedName = normalizeText(result.session.name);
  for (const term of terms) {
    if (normalizedName.includes(term)) {
      score += 10;
    }
  }

  // Match count
  score += result.matches.length * 2;

  // Recent messages weighted higher
  const now = Date.now();
  for (const match of result.matches) {
    const ageHours = (now - match.timestamp) / (1000 * 60 * 60);
    if (ageHours < 24) score += 3;
    else if (ageHours < 168) score += 2; // 1 week
    else score += 1;
  }

  return score;
}

export function searchSessions(query: string, maxResults = 10): SearchResult[] {
  const terms = extractTerms(query);
  if (terms.length === 0) return [];

  const sessions = listSessions();
  const results: SearchResult[] = [];

  for (const session of sessions) {
    const matches: MatchFragment[] = [];

    // Search in session name
    const normalizedName = normalizeText(session.name);
    const nameMatches = terms.filter((t) => normalizedName.includes(t));
    if (nameMatches.length > 0) {
      matches.push({
        messageId: 'session-name',
        role: 'user',
        text: `Nombre: ${session.name}`,
        highlightedText: `Nombre: ${highlightText(session.name, terms)}`,
        timestamp: session.createdAt,
      });
    }

    // Search in messages
    for (const message of session.messages) {
      const fragment = extractFragment(message, query, terms);
      if (fragment) {
        matches.push(fragment);
      }
    }

    if (matches.length > 0) {
      const result: SearchResult = {
        session,
        matches,
        relevanceScore: 0,
      };
      result.relevanceScore = scoreResult(result, terms);
      results.push(result);
    }
  }

  // Sort by relevance score descending
  results.sort((a, b) => b.relevanceScore - a.relevanceScore);

  return results.slice(0, maxResults);
}

export function formatSearchResults(results: SearchResult[], query: string): string {
  if (results.length === 0) {
    return `No se encontraron resultados para "${query}"`;
  }

  const lines: string[] = [];
  lines.push(`🔍 Resultados para "${query}" (${results.length} sesiones):\n`);

  for (const result of results) {
    const session = result.session;
    const date = new Date(session.updatedAt).toLocaleDateString('es-ES');
    const msgCount = session.messages.length;

    lines.push(`📂 ${session.name}`);
    lines.push(`   ID: ${session.id.substring(0, 8)}... | ${msgCount} mensajes | ${date}`);
    lines.push(`   Coincidencias: ${result.matches.length}`);
    lines.push('');

    // Show top 3 fragments
    const topFragments = result.matches.slice(0, 3);
    for (const fragment of topFragments) {
      const role = fragment.role === 'user' ? '👤' : '🤖';
      const time = new Date(fragment.timestamp).toLocaleTimeString('es-ES', {
        hour: '2-digit',
        minute: '2-digit',
      });
      lines.push(`   ${role} [${time}] ${fragment.highlightedText}`);
    }

    if (result.matches.length > 3) {
      lines.push(`   ... y ${result.matches.length - 3} coincidencias más`);
    }
    lines.push('');
  }

  return lines.join('\n');
}
