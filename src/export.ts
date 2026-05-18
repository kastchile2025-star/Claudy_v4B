import { Message } from './types';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';

export type ExportFormat = 'md' | 'html' | 'txt' | 'pdf';

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatMarkdown(messages: Message[], sessionName: string): string {
  const lines: string[] = [];
  lines.push(`# ${sessionName}`);
  lines.push('');
  lines.push(`Exported: ${new Date().toLocaleString('es-ES')}`);
  lines.push('');
  lines.push('---');
  lines.push('');

  for (const msg of messages) {
    const role = msg.role === 'user' ? '👤 Usuario' : '🤖 Asistente';
    lines.push(`### ${role}`);
    lines.push('');
    lines.push(msg.content);
    lines.push('');
    lines.push('---');
    lines.push('');
  }

  return lines.join('\n');
}

function formatHTML(messages: Message[], sessionName: string): string {
  const body = messages
    .map((msg) => {
      const role = msg.role === 'user' ? 'Usuario' : 'Asistente';
      const cls = msg.role === 'user' ? 'message-user' : 'message-assistant';
      return `  <div class="${cls}">
    <h3>${role}</h3>
    <pre>${escapeHtml(msg.content)}</pre>
  </div>`;
    })
    .join('\n\n');

  return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(sessionName)}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; background: #f5f5f5; }
    h1 { text-align: center; color: #333; }
    .message-user, .message-assistant { background: #fff; border-radius: 8px; padding: 1rem; margin: 1rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .message-user { border-left: 4px solid #4a90d9; }
    .message-assistant { border-left: 4px solid #50b86c; }
    h3 { margin: 0 0 0.5rem; font-size: 0.9rem; color: #666; }
    pre { white-space: pre-wrap; word-wrap: break-word; margin: 0; font-family: inherit; font-size: 0.95rem; }
    .meta { text-align: center; color: #999; font-size: 0.8rem; margin-bottom: 2rem; }
  </style>
</head>
<body>
  <h1>${escapeHtml(sessionName)}</h1>
  <p class="meta">Exportado: ${new Date().toLocaleString('es-ES')}</p>
${body}
</body>
</html>`;
}

function formatTXT(messages: Message[], sessionName: string): string {
  const lines: string[] = [];
  lines.push(`${sessionName}`);
  lines.push('='.repeat(sessionName.length));
  lines.push('');
  lines.push(`Exportado: ${new Date().toLocaleString('es-ES')}`);
  lines.push('');

  for (const msg of messages) {
    const role = msg.role === 'user' ? 'Usuario' : 'Asistente';
    lines.push(`[${role}]`);
    lines.push(msg.content);
    lines.push('');
    lines.push('-'.repeat(40));
    lines.push('');
  }

  return lines.join('\n');
}

function formatPDF(messages: Message[], sessionName: string): string {
  // Generates a minimal PDF with chat content
  const lines: string[] = [];
  lines.push(`%PDF-1.4`);
  lines.push(`1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj`);
  lines.push(`2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj`);

  const content = messages
    .map((msg) => {
      const role = msg.role === 'user' ? 'Usuario' : 'Asistente';
      return `${role}: ${msg.content.replace(/\n/g, ' ')}`;
    })
    .join('\n');

  const streamContent = `BT /F1 10 Tf 50 750 Td (${escapePdf(sessionName)}) Tj ET\n${content
    .split('\n')
    .slice(0, 50)
    .map((line, i) => `BT /F1 8 Tf 50 ${730 - i * 14} Td (${escapePdf(line)}) Tj ET`)
    .join('\n')}`;

  lines.push(
    `3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj`
  );
  lines.push(`4 0 obj << /Length ${streamContent.length} >> stream\n${streamContent}\nendstream endobj`);
  lines.push(`5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj`);
  lines.push(`xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000266 00000 n \n0000000${String(streamContent.length + 100).padStart(10, '0')} 00000 n \ntrailer << /Size 6 /Root 1 0 R >>\nstartxref\n${streamContent.length + 300}\n%%EOF`);

  return lines.join('\n');
}

function escapePdf(str: string): string {
  return str.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)');
}

export function exportChat(
  messages: Message[],
  sessionName: string,
  format: ExportFormat,
  outputDir?: string
): string {
  let content: string;
  let extension: string;

  switch (format) {
    case 'md':
      content = formatMarkdown(messages, sessionName);
      extension = 'md';
      break;
    case 'html':
      content = formatHTML(messages, sessionName);
      extension = 'html';
      break;
    case 'txt':
      content = formatTXT(messages, sessionName);
      extension = 'txt';
      break;
    case 'pdf':
      content = formatPDF(messages, sessionName);
      extension = 'pdf';
      break;
    default:
      throw new Error(`Formato no soportado: ${format}`);
  }

  const dir = outputDir || process.cwd();
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }

  const safeName = sessionName.replace(/[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]/g, '').replace(/\s+/g, '_');
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const filename = join(dir, `${safeName}_${timestamp}.${extension}`);

  writeFileSync(filename, content, 'utf-8');
  return filename;
}

export function getSupportedFormats(): string {
  return 'Formatos soportados: md (Markdown), html (HTML), txt (Texto plano), pdf (PDF básico)';
}
