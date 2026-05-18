import fs from 'fs';
import path from 'path';
import os from 'os';
import { Config } from './types.js';

const CONFIG_DIR = path.join(os.homedir(), '.claudy');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

const DEFAULT_CONFIG: Config = {
  opencode: {
    baseUrl: 'http://127.0.0.1:4096',
    defaultModel: 'opencode-go/qwen3.6-plus',
    apiKey: '',
    username: 'opencode',
    password: '',
  },
  agent: {
    systemPrompt: [
      'IDENTIDAD: Eres Claudy, asistente personal de Felipe. Hablas español natural, directo, sin formalidad — como un amigo técnico que sabe.',
      '',
      'PROTOCOLO DE RESPUESTA (clasifica antes de responder):',
      '1. Saludo / definición estable → 1-3 líneas, sin buscar.',
      '2. Dato actual (precios, clima, noticias) → busca primero, da dato + fuente.',
      '3. Código / técnico → código o pasos exactos, sin teoría innecesaria.',
      '4. Tarea multi-paso → anuncia plan en 1 línea, ejecuta cada paso, reporta brevemente.',
      '5. Opinión → TU recomendación primero, 1 línea de por qué.',
      '',
      'REGLAS:',
      '- PROHIBIDO: "como modelo de IA", "no tengo acceso a", preámbulos ("¡claro!", "por supuesto").',
      '- PROHIBIDO: derivar a otros sitios ("te recomiendo buscar..."). RESUELVE.',
      '- PROHIBIDO: markdown (**, *, `, ###, ```). Solo texto plano.',
      '- Si no sabes, di "No sé" directo.',
      '- Cada respuesta debe ACERCAR al objetivo, no solo informar.',
      '- Si la pregunta es ambigua, asume la interpretación más útil y procede.',
    ].join('\n'),
    maxTokens: 4096,
    temperature: 0.7,
  },
  tools: {
    enabled: true,
    allowRead: true,
    allowWrite: false,
    allowExec: false,
    allowedRoot: process.cwd(),
    commandTimeoutMs: 10_000,
    maxOutputChars: 20_000,
  },
  server: {
    port: 3001,
    host: '127.0.0.1',
  },
};

export function ensureConfigDir(): void {
  if (!fs.existsSync(CONFIG_DIR)) {
    fs.mkdirSync(CONFIG_DIR, { recursive: true });
  }
}

export function loadConfig(): Config {
  ensureConfigDir();

  if (!fs.existsSync(CONFIG_FILE)) {
    saveConfig(DEFAULT_CONFIG);
    return DEFAULT_CONFIG;
  }

  try {
    const content = fs.readFileSync(CONFIG_FILE, 'utf-8');
    const parsed = JSON.parse(content);
    return {
      ...DEFAULT_CONFIG,
      ...parsed,
      opencode: { ...DEFAULT_CONFIG.opencode, ...(parsed.opencode || {}) },
      agent: { ...DEFAULT_CONFIG.agent, ...(parsed.agent || {}) },
      tools: { ...DEFAULT_CONFIG.tools, ...(parsed.tools || {}) },
      server: { ...DEFAULT_CONFIG.server, ...(parsed.server || {}) },
    };
  } catch (error) {
    console.error('Error loading config:', error);
    return DEFAULT_CONFIG;
  }
}

export function saveConfig(config: Config): void {
  ensureConfigDir();
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), 'utf-8');
}

export function updateConfig(updates: Partial<Config>): void {
  const config = loadConfig();
  const merged = {
    ...config,
    ...updates,
    opencode: { ...config.opencode, ...updates.opencode },
    agent: { ...config.agent, ...updates.agent },
    tools: { ...config.tools, ...updates.tools },
    server: { ...config.server, ...updates.server },
  };
  saveConfig(merged);
}

export function getConfigPath(): string {
  return CONFIG_FILE;
}

export function getSessionsDir(): string {
  const dir = path.join(CONFIG_DIR, 'sessions');
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  return dir;
}
