import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import { Config } from './types.js';

const execAsync = promisify(exec);

export interface ToolResult {
  ok: boolean;
  output: string;
  error?: string;
}

function resolveSafe(targetPath: string, allowedRoot: string): string {
  const root = path.resolve(allowedRoot);
  const resolved = path.resolve(root, targetPath);
  // Normalizar con separador para evitar bypass por prefijo similar
  const rootWithSep = root.endsWith(path.sep) ? root : root + path.sep;
  if (!resolved.startsWith(rootWithSep) && resolved !== root) {
    throw new Error(
      `Path fuera del directorio permitido (${root}): ${targetPath}`
    );
  }
  return resolved;
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + `\n... [truncado, ${text.length - max} chars omitidos]`;
}

export async function toolRead(
  filePath: string,
  config: Config['tools']
): Promise<ToolResult> {
  if (!config.enabled) return { ok: false, output: '', error: 'Tools deshabilitadas' };
  if (!config.allowRead) return { ok: false, output: '', error: '/read deshabilitado' };

  try {
    const safePath = resolveSafe(filePath, config.allowedRoot);
    if (!fs.existsSync(safePath)) {
      return { ok: false, output: '', error: `Archivo no encontrado: ${filePath}` };
    }
    const stat = fs.statSync(safePath);
    if (stat.isDirectory()) {
      const entries = fs.readdirSync(safePath);
      return {
        ok: true,
        output: `Directorio ${filePath}:\n${entries.join('\n')}`,
      };
    }
    const content = fs.readFileSync(safePath, 'utf-8');
    return { ok: true, output: truncate(content, config.maxOutputChars) };
  } catch (err: any) {
    return { ok: false, output: '', error: err.message };
  }
}

export async function toolWrite(
  filePath: string,
  content: string,
  config: Config['tools']
): Promise<ToolResult> {
  if (!config.enabled) return { ok: false, output: '', error: 'Tools deshabilitadas' };
  if (!config.allowWrite) {
    return {
      ok: false,
      output: '',
      error: '/write deshabilitado. Activa con: claudy config set tools.allowWrite true',
    };
  }

  try {
    const safePath = resolveSafe(filePath, config.allowedRoot);
    fs.mkdirSync(path.dirname(safePath), { recursive: true });
    fs.writeFileSync(safePath, content, 'utf-8');
    return {
      ok: true,
      output: `Escrito ${content.length} chars en ${filePath}`,
    };
  } catch (err: any) {
    return { ok: false, output: '', error: err.message };
  }
}

export async function toolExec(
  command: string,
  config: Config['tools']
): Promise<ToolResult> {
  if (!config.enabled) return { ok: false, output: '', error: 'Tools deshabilitadas' };
  if (!config.allowExec) {
    return {
      ok: false,
      output: '',
      error: '/exec deshabilitado. Activa con: claudy config set tools.allowExec true',
    };
  }

  try {
    const { stdout, stderr } = await execAsync(command, {
      cwd: path.resolve(config.allowedRoot),
      timeout: config.commandTimeoutMs,
      maxBuffer: config.maxOutputChars * 2,
      // shell por defecto del SO (cmd en Windows, bash/sh en Unix)
    });
    const output = [stdout, stderr].filter(Boolean).join('\n').trim();
    return { ok: true, output: truncate(output || '(sin output)', config.maxOutputChars) };
  } catch (err: any) {
    const stdout = err.stdout?.toString?.() || '';
    const stderr = err.stderr?.toString?.() || '';
    const combined = [stdout, stderr, err.message].filter(Boolean).join('\n');
    return {
      ok: false,
      output: truncate(combined, config.maxOutputChars),
      error: err.killed ? `Timeout tras ${config.commandTimeoutMs}ms` : err.message,
    };
  }
}
