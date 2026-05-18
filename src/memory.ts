import fs from 'fs';
import path from 'path';
import os from 'os';
import { loadConfig } from './config.js';

const MEMORY_DIR = path.join(os.homedir(), '.claudy', 'memory');
const MEMORY_INDEX = path.join(MEMORY_DIR, 'index.jsonl');
const MEMORY_ARCHIVE = path.join(MEMORY_DIR, 'archive.jsonl');

interface MemoryEntry {
  id: string;
  content: string;
  timestamp: number;
  tags?: string[];
  session?: string;
}

function ensureMemoryDir(): void {
  if (!fs.existsSync(MEMORY_DIR)) {
    fs.mkdirSync(MEMORY_DIR, { recursive: true });
  }
}

/**
 * Añade una entrada a la memoria vectorial.
 */
export function addMemory(content: string, tags?: string[], session?: string): MemoryEntry {
  ensureMemoryDir();
  const entry: MemoryEntry = {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    content,
    timestamp: Date.now(),
    tags,
    session,
  };

  fs.appendFileSync(MEMORY_INDEX, JSON.stringify(entry) + '\n', 'utf-8');
  return entry;
}

/**
 * Busca memorias por contenido o tags.
 */
export function searchMemories(query: string, limit = 10): MemoryEntry[] {
  ensureMemoryDir();
  if (!fs.existsSync(MEMORY_INDEX)) return [];

  const lines = fs.readFileSync(MEMORY_INDEX, 'utf-8').split('\n').filter(Boolean);
  const entries: MemoryEntry[] = lines.map((l) => JSON.parse(l));

  // Búsqueda simple por palabras clave (sin embeddings por ahora)
  const queryLower = query.toLowerCase();
  const scored = entries
    .map((e) => ({
      entry: e,
      score: scoreRelevance(e.content, e.tags, queryLower),
    }))
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);

  return scored.map((s) => s.entry);
}

/**
 * Lista todas las memorias recientes.
 */
export function listMemories(limit = 20): MemoryEntry[] {
  ensureMemoryDir();
  if (!fs.existsSync(MEMORY_INDEX)) return [];

  const lines = fs.readFileSync(MEMORY_INDEX, 'utf-8').split('\n').filter(Boolean);
  const entries: MemoryEntry[] = lines.map((l) => JSON.parse(l));

  return entries
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, limit);
}

/**
 * Elimina una memoria por ID.
 */
export function deleteMemory(id: string): boolean {
  ensureMemoryDir();
  if (!fs.existsSync(MEMORY_INDEX)) return false;

  const lines = fs.readFileSync(MEMORY_INDEX, 'utf-8').split('\n').filter(Boolean);
  const filtered = lines.filter((l) => {
    const entry: MemoryEntry = JSON.parse(l);
    return entry.id !== id;
  });

  fs.writeFileSync(MEMORY_INDEX, filtered.join('\n') + '\n', 'utf-8');
  return filtered.length < lines.length;
}

/**
 * Archiva memorias antiguas para reducir el índice activo.
 */
export function archiveOldMemories(maxAgeDays = 7): number {
  ensureMemoryDir();
  if (!fs.existsSync(MEMORY_INDEX)) return 0;

  const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000;
  const lines = fs.readFileSync(MEMORY_INDEX, 'utf-8').split('\n').filter(Boolean);
  const active: string[] = [];
  const archived: string[] = [];

  for (const line of lines) {
    const entry: MemoryEntry = JSON.parse(line);
    if (entry.timestamp < cutoff) {
      archived.push(line);
    } else {
      active.push(line);
    }
  }

  if (archived.length > 0) {
    fs.appendFileSync(MEMORY_ARCHIVE, archived.join('\n') + '\n', 'utf-8');
    fs.writeFileSync(MEMORY_INDEX, active.join('\n') + '\n', 'utf-8');
  }

  return archived.length;
}

/**
 * Puntúa la relevancia de una memoria para una consulta.
 */
function scoreRelevance(content: string, tags: string[] | undefined, query: string): number {
  const contentLower = content.toLowerCase();
  let score = 0;

  // Coincidencia exacta de frase
  if (contentLower.includes(query)) {
    score += 10;
  }

  // Coincidencia de palabras individuales
  const words = query.split(/\s+/);
  for (const word of words) {
    if (contentLower.includes(word)) {
      score += 2;
    }
  }

  // Coincidencia de tags
  if (tags) {
    for (const tag of tags) {
      if (tag.toLowerCase().includes(query) || query.includes(tag.toLowerCase())) {
        score += 5;
      }
    }
  }

  return score;
}
