import fs from 'fs';
import path from 'path';
import { Session, Message } from './types.js';
import { getSessionsDir } from './config.js';

export function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

export function createSession(name: string, model: string): Session {
  return {
    id: generateId(),
    name,
    model,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
}

export function saveSession(session: Session): void {
  const sessionsDir = getSessionsDir();
  const filePath = path.join(sessionsDir, `${session.id}.json`);
  fs.writeFileSync(filePath, JSON.stringify(session, null, 2), 'utf-8');
}

export function loadSession(sessionId: string): Session | null {
  const sessionsDir = getSessionsDir();
  const filePath = path.join(sessionsDir, `${sessionId}.json`);

  if (!fs.existsSync(filePath)) {
    return null;
  }

  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    console.error('Error loading session:', error);
    return null;
  }
}

export function listSessions(): Session[] {
  const sessionsDir = getSessionsDir();

  if (!fs.existsSync(sessionsDir)) {
    return [];
  }

  const files = fs.readdirSync(sessionsDir);
  return files
    .filter((file) => file.endsWith('.json'))
    .map((file) => {
      try {
        const content = fs.readFileSync(
          path.join(sessionsDir, file),
          'utf-8'
        );
        return JSON.parse(content);
      } catch {
        return null;
      }
    })
    .filter((session): session is Session => session !== null)
    .sort((a, b) => b.updatedAt - a.updatedAt);
}

export function deleteSession(sessionId: string): boolean {
  const sessionsDir = getSessionsDir();
  const filePath = path.join(sessionsDir, `${sessionId}.json`);

  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
    return true;
  }
  return false;
}

export function addMessage(
  session: Session,
  role: 'user' | 'assistant',
  content: string
): Message {
  const message: Message = {
    id: generateId(),
    role,
    content,
    timestamp: Date.now(),
  };

  session.messages.push(message);
  session.updatedAt = Date.now();

  return message;
}

export function formatSessionList(sessions: Session[]): string {
  if (sessions.length === 0) {
    return 'No sessions found';
  }

  return sessions
    .map(
      (session) =>
        `${session.id.substring(0, 8)}... | ${session.name} | ${session.model}`
    )
    .join('\n');
}

export function formatDate(timestamp: number): string {
  return new Date(timestamp).toLocaleString();
}

export function truncateString(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.substring(0, maxLength - 3) + '...';
}

const SUMMARIZE_THRESHOLD = 30;
const KEEP_MESSAGES = 10;

export function needsSummarization(session: { messages: unknown[] }, threshold = SUMMARIZE_THRESHOLD): boolean {
  return session.messages.length >= threshold;
}

export function buildSummarizationPrompt(session: { messages: Message[]; summary?: string }): string {
  const messagesToSummarize = session.messages.slice(0, -KEEP_MESSAGES);
  const recentMessages = session.messages.slice(-KEEP_MESSAGES);

  const previousSummary = session.summary
    ? `Resumen anterior de la conversación:\n${session.summary}\n\n`
    : '';

  const conversationText = messagesToSummarize
    .map((m) => `${m.role === 'user' ? 'Usuario' : 'Asistente'}: ${m.content}`)
    .join('\n\n---\n\n');

  const recentText = recentMessages
    .map((m) => `${m.role === 'user' ? 'Usuario' : 'Asistente'}: ${m.content.substring(0, 200)}`)
    .join('\n\n');

  return `${previousSummary}He analizado esta conversación larga y necesito un resumen compacto que preserve:
- Decisiones clave y acuerdos
- Contexto técnico importante
- Preferencias del usuario
- Tareas pendientes o en curso

Conversación a resumir (${messagesToSummarize.length} mensajes):
${conversationText}

Últimos ${KEEP_MESSAGES} mensajes (NO resumir, mantener intactos):
${recentText}

Genera un resumen conciso en español de máximo 500 palabras. Solo devuelve el resumen, sin preámbulos.`;
}

export function compactSession(session: { messages: Message[]; summary?: string }, summary: string): void {
  const recentMessages = session.messages.slice(-KEEP_MESSAGES);
  session.summary = summary;
  session.messages = recentMessages;
}
