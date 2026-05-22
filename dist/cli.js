#!/usr/bin/env node
import {
  __require
} from "./chunk-3RG5ZIWI.js";

// src/cli.ts
import { Command as Command7 } from "commander";

// src/commands/setup.ts
import { Command } from "commander";
import inquirer from "inquirer";
import chalk from "chalk";
import ora from "ora";

// src/config.ts
import fs from "fs";
import path from "path";
import os from "os";
var CONFIG_DIR = path.join(os.homedir(), ".claudy");
var CONFIG_FILE = path.join(CONFIG_DIR, "config.json");
var DEFAULT_CONFIG = {
  opencode: {
    baseUrl: "http://127.0.0.1:4096",
    defaultModel: "opencode-go/qwen3.6-plus",
    apiKey: "",
    username: "opencode",
    password: ""
  },
  agent: {
    systemPrompt: [
      "IDENTIDAD: Eres Claudy, asistente personal de Felipe. Hablas espa\xF1ol natural, directo, sin formalidad \u2014 como un amigo t\xE9cnico que sabe.",
      "",
      "PROTOCOLO DE RESPUESTA (clasifica antes de responder):",
      "1. Saludo / definici\xF3n estable \u2192 1-3 l\xEDneas, sin buscar.",
      "2. Dato actual (precios, clima, noticias) \u2192 busca primero, da dato + fuente.",
      "3. C\xF3digo / t\xE9cnico \u2192 c\xF3digo o pasos exactos, sin teor\xEDa innecesaria.",
      "4. Tarea multi-paso \u2192 anuncia plan en 1 l\xEDnea, ejecuta cada paso, reporta brevemente.",
      "5. Opini\xF3n \u2192 TU recomendaci\xF3n primero, 1 l\xEDnea de por qu\xE9.",
      "",
      "REGLAS:",
      '- PROHIBIDO: "como modelo de IA", "no tengo acceso a", pre\xE1mbulos ("\xA1claro!", "por supuesto").',
      '- PROHIBIDO: derivar a otros sitios ("te recomiendo buscar..."). RESUELVE.',
      "- PROHIBIDO: markdown (**, *, `, ###, ```). Solo texto plano.",
      '- Si no sabes, di "No s\xE9" directo.',
      "- Cada respuesta debe ACERCAR al objetivo, no solo informar.",
      "- Si la pregunta es ambigua, asume la interpretaci\xF3n m\xE1s \xFAtil y procede."
    ].join("\n"),
    maxTokens: 4096,
    temperature: 0.7
  },
  tools: {
    enabled: true,
    allowRead: true,
    allowWrite: false,
    allowExec: false,
    allowedRoot: process.cwd(),
    commandTimeoutMs: 1e4,
    maxOutputChars: 2e4
  },
  server: {
    port: 3001,
    host: "127.0.0.1"
  }
};
function ensureConfigDir() {
  if (!fs.existsSync(CONFIG_DIR)) {
    fs.mkdirSync(CONFIG_DIR, { recursive: true });
  }
}
function loadConfig() {
  ensureConfigDir();
  if (!fs.existsSync(CONFIG_FILE)) {
    saveConfig(DEFAULT_CONFIG);
    return DEFAULT_CONFIG;
  }
  try {
    const content = fs.readFileSync(CONFIG_FILE, "utf-8");
    const parsed = JSON.parse(content);
    return {
      ...DEFAULT_CONFIG,
      ...parsed,
      opencode: { ...DEFAULT_CONFIG.opencode, ...parsed.opencode || {} },
      agent: { ...DEFAULT_CONFIG.agent, ...parsed.agent || {} },
      tools: { ...DEFAULT_CONFIG.tools, ...parsed.tools || {} },
      server: { ...DEFAULT_CONFIG.server, ...parsed.server || {} }
    };
  } catch (error) {
    console.error("Error loading config:", error);
    return DEFAULT_CONFIG;
  }
}
function saveConfig(config) {
  ensureConfigDir();
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), "utf-8");
}
function getConfigPath() {
  return CONFIG_FILE;
}
function getSessionsDir() {
  const dir = path.join(CONFIG_DIR, "sessions");
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  return dir;
}

// src/utils.ts
import fs2 from "fs";
import path2 from "path";
function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}
function createSession(name, model) {
  return {
    id: generateId(),
    name,
    model,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: []
  };
}
function saveSession(session) {
  const sessionsDir = getSessionsDir();
  const filePath = path2.join(sessionsDir, `${session.id}.json`);
  fs2.writeFileSync(filePath, JSON.stringify(session, null, 2), "utf-8");
}
function loadSession(sessionId) {
  const sessionsDir = getSessionsDir();
  const filePath = path2.join(sessionsDir, `${sessionId}.json`);
  if (!fs2.existsSync(filePath)) {
    return null;
  }
  try {
    const content = fs2.readFileSync(filePath, "utf-8");
    return JSON.parse(content);
  } catch (error) {
    console.error("Error loading session:", error);
    return null;
  }
}
function listSessions() {
  const sessionsDir = getSessionsDir();
  if (!fs2.existsSync(sessionsDir)) {
    return [];
  }
  const files = fs2.readdirSync(sessionsDir);
  return files.filter((file) => file.endsWith(".json")).map((file) => {
    try {
      const content = fs2.readFileSync(
        path2.join(sessionsDir, file),
        "utf-8"
      );
      return JSON.parse(content);
    } catch {
      return null;
    }
  }).filter((session) => session !== null).sort((a, b) => b.updatedAt - a.updatedAt);
}
function deleteSession(sessionId) {
  const sessionsDir = getSessionsDir();
  const filePath = path2.join(sessionsDir, `${sessionId}.json`);
  if (fs2.existsSync(filePath)) {
    fs2.unlinkSync(filePath);
    return true;
  }
  return false;
}
function addMessage(session, role, content) {
  const message = {
    id: generateId(),
    role,
    content,
    timestamp: Date.now()
  };
  session.messages.push(message);
  session.updatedAt = Date.now();
  return message;
}
function formatDate(timestamp) {
  return new Date(timestamp).toLocaleString();
}
var SUMMARIZE_THRESHOLD = 30;
var KEEP_MESSAGES = 10;
function needsSummarization(session, threshold = SUMMARIZE_THRESHOLD) {
  return session.messages.length >= threshold;
}
function buildSummarizationPrompt(session) {
  const messagesToSummarize = session.messages.slice(0, -KEEP_MESSAGES);
  const recentMessages = session.messages.slice(-KEEP_MESSAGES);
  const previousSummary = session.summary ? `Resumen anterior de la conversaci\xF3n:
${session.summary}

` : "";
  const conversationText = messagesToSummarize.map((m) => `${m.role === "user" ? "Usuario" : "Asistente"}: ${m.content}`).join("\n\n---\n\n");
  const recentText = recentMessages.map((m) => `${m.role === "user" ? "Usuario" : "Asistente"}: ${m.content.substring(0, 200)}`).join("\n\n");
  return `${previousSummary}He analizado esta conversaci\xF3n larga y necesito un resumen compacto que preserve:
- Decisiones clave y acuerdos
- Contexto t\xE9cnico importante
- Preferencias del usuario
- Tareas pendientes o en curso

Conversaci\xF3n a resumir (${messagesToSummarize.length} mensajes):
${conversationText}

\xDAltimos ${KEEP_MESSAGES} mensajes (NO resumir, mantener intactos):
${recentText}

Genera un resumen conciso en espa\xF1ol de m\xE1ximo 500 palabras. Solo devuelve el resumen, sin pre\xE1mbulos.`;
}
function compactSession(session, summary) {
  const recentMessages = session.messages.slice(-KEEP_MESSAGES);
  session.summary = summary;
  session.messages = recentMessages;
}

// src/opencode.ts
var DISABLED_TOOLS = {
  bash: false,
  read: false,
  edit: false,
  glob: false,
  grep: false,
  webfetch: false,
  task: false,
  todowrite: false,
  websearch: false,
  codesearch: false,
  lsp: false,
  skill: false
};
var STALE_SESSION_TIMEOUT_MS = 2e4;
var OpenCodeClient = class {
  constructor(config) {
    this.baseUrl = config.baseUrl;
    this.apiKey = config.apiKey;
    this.username = config.username;
    this.password = config.password;
  }
  getAuthHeader() {
    if (this.apiKey) return `Bearer ${this.apiKey}`;
    if (!this.password) return void 0;
    const user = this.username || "opencode";
    return `Basic ${Buffer.from(`${user}:${this.password}`).toString("base64")}`;
  }
  buildHeaders(extra) {
    const headers = new Headers(extra);
    const auth = this.getAuthHeader();
    if (auth) headers.set("Authorization", auth);
    return headers;
  }
  resolveUrl(path8) {
    return new URL(path8, this.baseUrl.endsWith("/") ? this.baseUrl : `${this.baseUrl}/`);
  }
  async request(path8, init = {}) {
    const url = this.resolveUrl(path8);
    const headers = this.buildHeaders();
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    let response;
    try {
      response = await fetch(url, { ...init, headers });
    } catch (error) {
      throw new Error(
        `No pude conectar con OpenCode en ${this.baseUrl}. Inicia OpenCode con "opencode serve --port 4096 --hostname 127.0.0.1". Detalle: ${error instanceof Error ? error.message : String(error)}`
      );
    }
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`OpenCode error ${response.status}: ${text || response.statusText}`);
    }
    if (response.status === 204) return void 0;
    return await response.json();
  }
  parseModel(model) {
    const trimmed = model.trim();
    if (trimmed.includes("/")) {
      const [providerID, ...modelParts] = trimmed.split("/");
      return { providerID, modelID: modelParts.join("/") };
    }
    return { providerID: "", modelID: trimmed };
  }
  extractText(response) {
    if (response.info?.error) {
      const { name, data } = response.info.error;
      throw new Error(data?.message || name || "OpenCode devolvio un error");
    }
    const text = response.parts?.filter((p) => p.type === "text").map((p) => p.text).join("\n").trim();
    return text || "(OpenCode no devolvio texto.)";
  }
  async ensureSession(session) {
    if (session.opencodeSessionId) return session.opencodeSessionId;
    const created = await this.request("/session", {
      method: "POST",
      body: JSON.stringify({ title: session.name })
    });
    session.opencodeSessionId = created.id;
    saveSession(session);
    return created.id;
  }
  /**
   * Envía un mensaje con streaming real via SSE.
   * onToken se llama por cada fragmento de texto recibido.
   * Devuelve el texto completo acumulado.
   */
  async sendMessageStreaming(session, userMessage, model, systemPrompt, onToken, abortSignal) {
    const parsedModel = this.parseModel(model);
    const sessionId = await this.ensureSession(session);
    const url = this.resolveUrl(`/session/${encodeURIComponent(sessionId)}/message`);
    const headers = this.buildHeaders({
      "Content-Type": "application/json",
      Accept: "text/event-stream"
    });
    const body = JSON.stringify({
      model: parsedModel,
      system: systemPrompt,
      tools: DISABLED_TOOLS,
      parts: [{ type: "text", text: userMessage }]
    });
    let response;
    try {
      response = await fetch(url, { method: "POST", headers, body, signal: abortSignal });
    } catch (error) {
      throw new Error(
        `No pude conectar con OpenCode en ${this.baseUrl}. Detalle: ${error instanceof Error ? error.message : String(error)}`
      );
    }
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("text/event-stream")) {
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`OpenCode error ${response.status}: ${text || response.statusText}`);
      }
      const json = await response.json();
      const fullText = this.extractText(json);
      await typewriterEffect(fullText, onToken);
      return fullText;
    }
    if (!response.body) throw new Error("No se recibio cuerpo de respuesta SSE.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let accumulated = "";
    const STREAM_TIMEOUT_MS = 9e4;
    while (true) {
      const timeoutPromise = new Promise(
        (_, reject) => setTimeout(() => reject(new Error("Timeout: el modelo no respondi\xF3 en 90 segundos. Intenta con un mensaje m\xE1s corto o cambia de modelo con /model.")), STREAM_TIMEOUT_MS)
      );
      let result;
      try {
        result = await Promise.race([reader.read(), timeoutPromise]);
      } catch (err) {
        reader.cancel();
        throw err;
      }
      const { done, value } = result;
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith(":")) continue;
        if (trimmed.startsWith("data:")) {
          const data = trimmed.slice(5).trim();
          if (data === "[DONE]") break;
          try {
            const parsed = JSON.parse(data);
            const token = extractSseToken(parsed);
            if (token) {
              accumulated += token;
              onToken(token);
            }
          } catch {
            if (data && data !== "[DONE]") {
              accumulated += data;
              onToken(data);
            }
          }
        }
      }
    }
    if (!accumulated.trim()) {
      const full = await this.sendMessage(session, userMessage, model, systemPrompt);
      await typewriterEffect(full, onToken);
      return full;
    }
    return accumulated;
  }
  async sendMessage(session, userMessage, model, systemPrompt) {
    const parsedModel = this.parseModel(model);
    const send = async (timeoutMs) => {
      const sessionId = await this.ensureSession(session);
      const signal = timeoutMs && typeof AbortSignal.timeout === "function" ? AbortSignal.timeout(timeoutMs) : void 0;
      return this.request(
        `/session/${encodeURIComponent(sessionId)}/message`,
        {
          method: "POST",
          signal,
          body: JSON.stringify({
            model: parsedModel,
            system: systemPrompt,
            tools: DISABLED_TOOLS,
            parts: [{ type: "text", text: userMessage }]
          })
        }
      );
    };
    const hadSession = Boolean(session.opencodeSessionId);
    let response;
    try {
      response = await send(hadSession ? STALE_SESSION_TIMEOUT_MS : void 0);
    } catch (error) {
      if (!hadSession) throw error;
      session.opencodeSessionId = void 0;
      saveSession(session);
      response = await send();
    }
    return this.extractText(response);
  }
  async listModels() {
    const response = await this.request("/provider");
    const providers = response.all || response.providers || [];
    const connected = response.connected?.length ? new Set(response.connected) : void 0;
    return providers.flatMap((provider) => {
      const providerID = provider.id;
      if (!providerID || !provider.models) return [];
      if (connected && !connected.has(providerID)) return [];
      return Object.entries(provider.models).map(([modelID, model]) => ({
        id: `${providerID}/${model.id || modelID}`,
        name: `${provider.name || providerID}: ${model.name || model.id || modelID}`,
        description: model.description,
        context_length: model.limit?.context
      }));
    });
  }
  async testConnection() {
    try {
      await this.request("/provider");
      return true;
    } catch {
      return false;
    }
  }
};
function extractSseToken(data) {
  const choices = data["choices"];
  if (Array.isArray(choices) && choices.length > 0) {
    const delta2 = choices[0]["delta"];
    if (delta2 && typeof delta2["content"] === "string") return delta2["content"];
  }
  const delta = data["delta"];
  if (delta && typeof delta["text"] === "string") return delta["text"];
  const parts = data["parts"];
  if (Array.isArray(parts)) {
    return parts.filter((p) => p["type"] === "text" && typeof p["text"] === "string").map((p) => p["text"]).join("");
  }
  if (typeof data["content"] === "string") return data["content"];
  if (typeof data["text"] === "string") return data["text"];
  return "";
}
async function typewriterEffect(text, onToken) {
  const CHUNK = 4;
  const DELAY = 12;
  for (let i = 0; i < text.length; i += CHUNK) {
    onToken(text.slice(i, i + CHUNK));
    if (i + CHUNK < text.length) {
      await new Promise((resolve) => setTimeout(resolve, DELAY));
    }
  }
}

// src/commands/setup.ts
var setupCommand = new Command("setup").description("Configurar Claudy por primera vez").action(async () => {
  console.log(chalk.cyan.bold("\n\u{1F916} Bienvenido a Claudy Setup\n"));
  console.log(chalk.gray("Configura tu asistente de IA personal en pocos pasos.\n"));
  const config = loadConfig();
  const answers = await inquirer.prompt([
    {
      type: "list",
      name: "authType",
      message: "Tipo de autenticaci\xF3n:",
      default: config.opencode.apiKey ? "apikey" : "basic",
      choices: [
        { name: "API Key (Bearer token)", value: "apikey" },
        { name: "Usuario + Password (Basic auth)", value: "basic" },
        { name: "Sin autenticaci\xF3n (servidor local)", value: "none" }
      ]
    },
    {
      type: "input",
      name: "baseUrl",
      message: "URL del servidor:",
      default: (a) => a.authType === "apikey" ? config.opencode.baseUrl !== "http://127.0.0.1:4096" ? config.opencode.baseUrl : "https://api.opencode.ai" : config.opencode.baseUrl || "http://127.0.0.1:4096"
    },
    {
      type: "password",
      name: "apiKey",
      message: "API Key:",
      mask: "*",
      when: (a) => a.authType === "apikey",
      default: config.opencode.apiKey || void 0,
      validate: (input) => input && input.length > 5 ? true : "API key requerida"
    },
    {
      type: "input",
      name: "username",
      message: "Usuario:",
      when: (a) => a.authType === "basic",
      default: config.opencode.username || "opencode"
    },
    {
      type: "password",
      name: "password",
      message: "Password:",
      mask: "*",
      when: (a) => a.authType === "basic",
      default: config.opencode.password || ""
    },
    {
      type: "list",
      name: "defaultModel",
      message: "Modelo predeterminado (OpenCode Go):",
      default: config.opencode.defaultModel,
      choices: [
        { name: "GLM-5", value: "opencode-go/glm-5" },
        { name: "GLM-5.1", value: "opencode-go/glm-5.1" },
        { name: "Kimi K2.5", value: "opencode-go/kimi-k2.5" },
        { name: "Kimi K2.6", value: "opencode-go/kimi-k2.6" },
        { name: "MiMo-V2-Pro", value: "opencode-go/mimo-v2-pro" },
        { name: "MiMo-V2-Omni", value: "opencode-go/mimo-v2-omni" },
        { name: "MiMo-V2.5-Pro", value: "opencode-go/mimo-v2.5-pro" },
        { name: "MiMo-V2.5", value: "opencode-go/mimo-v2.5" },
        { name: "MiniMax M2.5", value: "opencode-go/minimax-m2.5" },
        { name: "Qwen3.5 Plus", value: "opencode-go/qwen3.5-plus" },
        { name: "Qwen3.6 Plus (recomendado)", value: "opencode-go/qwen3.6-plus" },
        { name: "MiniMax M2.7", value: "opencode-go/minimax-m2.7" },
        { name: "DeepSeek V4 Pro", value: "opencode-go/deepseek-v4-pro" },
        { name: "DeepSeek V4 Flash", value: "opencode-go/deepseek-v4-flash" },
        new inquirer.Separator(),
        { name: "Otro (especificar manualmente)", value: "custom" }
      ]
    },
    {
      type: "input",
      name: "customModel",
      message: "Modelo (formato: provider/model):",
      when: (a) => a.defaultModel === "custom",
      validate: (input) => input && input.trim().length > 0 ? true : "Modelo requerido"
    },
    {
      type: "input",
      name: "systemPrompt",
      message: "System prompt (Enter para usar default):",
      default: config.agent.systemPrompt
    },
    {
      type: "number",
      name: "temperature",
      message: "Temperatura (0.0 - 1.0):",
      default: config.agent.temperature,
      validate: (input) => {
        if (input < 0 || input > 2) return "Debe ser entre 0 y 2";
        return true;
      }
    },
    {
      type: "number",
      name: "maxTokens",
      message: "M\xE1ximo de tokens por respuesta:",
      default: config.agent.maxTokens
    }
  ]);
  const newConfig = {
    ...config,
    opencode: {
      baseUrl: answers.baseUrl,
      defaultModel: (answers.defaultModel === "custom" ? answers.customModel : answers.defaultModel).trim(),
      apiKey: answers.apiKey || "",
      username: answers.username || "opencode",
      password: answers.password || ""
    },
    agent: {
      systemPrompt: answers.systemPrompt,
      temperature: answers.temperature,
      maxTokens: answers.maxTokens
    }
  };
  const spinner = ora("Probando conexi\xF3n...").start();
  const client = new OpenCodeClient(newConfig.opencode);
  const ok = await client.testConnection();
  if (!ok) {
    spinner.warn(
      chalk.yellow(
        `No se pudo conectar a ${newConfig.opencode.baseUrl}.
  Si usas servidor local: opencode serve --port 4096 --hostname 127.0.0.1
  Si usas remoto: verifica URL y API key.`
      )
    );
  } else {
    spinner.succeed(chalk.green("Conexi\xF3n exitosa"));
  }
  saveConfig(newConfig);
  console.log(chalk.green.bold("\n\u2713 Configuraci\xF3n guardada\n"));
  console.log(chalk.gray("Comandos disponibles:"));
  console.log(chalk.cyan("  claudy chat       ") + chalk.gray("- Iniciar chat"));
  console.log(chalk.cyan("  claudy models     ") + chalk.gray("- Ver modelos"));
  console.log(chalk.cyan("  claudy sessions   ") + chalk.gray("- Ver sesiones"));
  console.log(chalk.cyan("  claudy config     ") + chalk.gray("- Editar config"));
  console.log("");
});

// src/commands/chat.ts
import { Command as Command2 } from "commander";
import inquirer2 from "inquirer";
import chalk3 from "chalk";
import * as readline from "readline/promises";
import { marked } from "marked";
import TerminalRenderer from "marked-terminal";

// src/opencode-ensure.ts
import { spawn } from "child_process";
import chalk2 from "chalk";
async function ensureOpencodeRunning(config) {
  const client = new OpenCodeClient(config);
  if (await client.testConnection()) {
    return true;
  }
  console.log(chalk2.yellow("\u26A0 OpenCode no est\xE1 respondiendo. Intentando iniciar autom\xE1ticamente..."));
  try {
    const port = new URL(config.baseUrl).port || "4096";
    const hostname = new URL(config.baseUrl).hostname || "127.0.0.1";
    const child = spawn("opencode", ["serve", "--port", port, "--hostname", hostname], {
      stdio: "ignore",
      detached: true
    });
    child.unref();
    console.log(chalk2.cyan("\u{1F504} Iniciando opencode serve en segundo plano..."));
    const maxWait = 15e3;
    const pollInterval = 500;
    const start = Date.now();
    while (Date.now() - start < maxWait) {
      await new Promise((r) => setTimeout(r, pollInterval));
      if (await client.testConnection()) {
        console.log(chalk2.green("\u2713 OpenCode iniciado correctamente."));
        return true;
      }
    }
    console.log(chalk2.red("\u2717 No se pudo iniciar OpenCode autom\xE1ticamente."));
    console.log(chalk2.gray("  Inicia manualmente: opencode serve --port 4096 --hostname 127.0.0.1"));
    return false;
  } catch (error) {
    console.log(chalk2.red("\u2717 Error al iniciar OpenCode:"));
    console.log(chalk2.gray(`  ${error instanceof Error ? error.message : String(error)}`));
    console.log(chalk2.gray("  Inicia manualmente: opencode serve --port 4096 --hostname 127.0.0.1"));
    return false;
  }
}

// src/tools.ts
import fs3 from "fs";
import path3 from "path";
import { exec } from "child_process";
import { promisify } from "util";
var execAsync = promisify(exec);
function resolveSafe(targetPath, allowedRoot) {
  const root = path3.resolve(allowedRoot);
  const resolved = path3.resolve(root, targetPath);
  const rootWithSep = root.endsWith(path3.sep) ? root : root + path3.sep;
  if (!resolved.startsWith(rootWithSep) && resolved !== root) {
    throw new Error(
      `Path fuera del directorio permitido (${root}): ${targetPath}`
    );
  }
  return resolved;
}
function truncate(text, max) {
  if (text.length <= max) return text;
  return text.slice(0, max) + `
... [truncado, ${text.length - max} chars omitidos]`;
}
async function toolRead(filePath, config) {
  if (!config.enabled) return { ok: false, output: "", error: "Tools deshabilitadas" };
  if (!config.allowRead) return { ok: false, output: "", error: "/read deshabilitado" };
  try {
    const safePath = resolveSafe(filePath, config.allowedRoot);
    if (!fs3.existsSync(safePath)) {
      return { ok: false, output: "", error: `Archivo no encontrado: ${filePath}` };
    }
    const stat = fs3.statSync(safePath);
    if (stat.isDirectory()) {
      const entries = fs3.readdirSync(safePath);
      return {
        ok: true,
        output: `Directorio ${filePath}:
${entries.join("\n")}`
      };
    }
    const content = fs3.readFileSync(safePath, "utf-8");
    return { ok: true, output: truncate(content, config.maxOutputChars) };
  } catch (err) {
    return { ok: false, output: "", error: err.message };
  }
}
async function toolWrite(filePath, content, config) {
  if (!config.enabled) return { ok: false, output: "", error: "Tools deshabilitadas" };
  if (!config.allowWrite) {
    return {
      ok: false,
      output: "",
      error: "/write deshabilitado. Activa con: claudy config set tools.allowWrite true"
    };
  }
  try {
    const safePath = resolveSafe(filePath, config.allowedRoot);
    fs3.mkdirSync(path3.dirname(safePath), { recursive: true });
    fs3.writeFileSync(safePath, content, "utf-8");
    return {
      ok: true,
      output: `Escrito ${content.length} chars en ${filePath}`
    };
  } catch (err) {
    return { ok: false, output: "", error: err.message };
  }
}
async function toolExec(command, config) {
  if (!config.enabled) return { ok: false, output: "", error: "Tools deshabilitadas" };
  if (!config.allowExec) {
    return {
      ok: false,
      output: "",
      error: "/exec deshabilitado. Activa con: claudy config set tools.allowExec true"
    };
  }
  try {
    const { stdout, stderr } = await execAsync(command, {
      cwd: path3.resolve(config.allowedRoot),
      timeout: config.commandTimeoutMs,
      maxBuffer: config.maxOutputChars * 2
      // shell por defecto del SO (cmd en Windows, bash/sh en Unix)
    });
    const output = [stdout, stderr].filter(Boolean).join("\n").trim();
    return { ok: true, output: truncate(output || "(sin output)", config.maxOutputChars) };
  } catch (err) {
    const stdout = err.stdout?.toString?.() || "";
    const stderr = err.stderr?.toString?.() || "";
    const combined = [stdout, stderr, err.message].filter(Boolean).join("\n");
    return {
      ok: false,
      output: truncate(combined, config.maxOutputChars),
      error: err.killed ? `Timeout tras ${config.commandTimeoutMs}ms` : err.message
    };
  }
}

// src/skills.ts
import fs4 from "fs";
import path4 from "path";
import os2 from "os";
var SKILLS_DIR = path4.join(os2.homedir(), ".claudy", "skills");
var SKILLS_README = path4.join(SKILLS_DIR, "README.md");
var SKILLS_SEARCH_ENDPOINT = "https://skills.sh/api/search";
var MAX_SKILL_ASSET_BYTES = 15e5;
function getSkillsDir() {
  if (!fs4.existsSync(SKILLS_DIR)) {
    fs4.mkdirSync(SKILLS_DIR, { recursive: true });
  }
  return SKILLS_DIR;
}
function sanitizeSkillName(name) {
  return name.toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80);
}
function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) return { meta: {}, body: content };
  const meta = {};
  for (const line of match[1].split("\n")) {
    const idx = line.indexOf(":");
    if (idx > 0) {
      const key = line.slice(0, idx).trim();
      const value = line.slice(idx + 1).trim().replace(/^["']|["']$/g, "");
      meta[key] = value;
    }
  }
  return { meta, body: match[2] };
}
function listSkills() {
  const dir = getSkillsDir();
  const skills = [];
  for (const entry of fs4.readdirSync(dir)) {
    const skillDir = path4.join(dir, entry);
    if (!fs4.statSync(skillDir).isDirectory()) continue;
    const skillFile = path4.join(skillDir, "SKILL.md");
    if (!fs4.existsSync(skillFile)) continue;
    try {
      const content = fs4.readFileSync(skillFile, "utf-8");
      const { meta, body } = parseFrontmatter(content);
      skills.push({
        name: meta.name || entry,
        description: meta.description || body.split("\n")[0].slice(0, 100),
        path: skillFile,
        content: body
      });
    } catch {
    }
  }
  return skills;
}
function escapeTable(value) {
  return (value || "").replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
}
function readSourceMetadata(skillFile) {
  const sourcePath = path4.join(path4.dirname(skillFile), "source.json");
  if (!fs4.existsSync(sourcePath)) return {};
  try {
    return JSON.parse(fs4.readFileSync(sourcePath, "utf-8"));
  } catch {
    return {};
  }
}
function updateSkillsReadme() {
  const skills = listSkills();
  const rows = skills.map((skill) => {
    const source = readSourceMetadata(skill.path);
    const sourceLabel = source.url || source.skillsUrl || source.id || "local";
    return `| ${escapeTable(skill.name)} | ${escapeTable(skill.description)} | ${escapeTable(sourceLabel)} | ${escapeTable(skill.path)} |`;
  });
  const content = [
    "# Skills instalados en Claudy",
    "",
    "Este archivo se actualiza automaticamente cuando Claudy instala skills desde internet o desde una URL.",
    "",
    `Actualizado: ${(/* @__PURE__ */ new Date()).toISOString()}`,
    "",
    "| Skill | Descripcion | Fuente | Ruta local |",
    "| --- | --- | --- | --- |",
    rows.length ? rows.join("\n") : "| _Sin skills instalados_ |  |  |  |",
    "",
    "Nota: los skills son instrucciones Markdown. Instala solo fuentes confiables.",
    ""
  ].join("\n");
  fs4.writeFileSync(SKILLS_README, content, "utf-8");
  return SKILLS_README;
}
function cleanSkillQuery(message) {
  const normalized = message.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[¿?!.:,;]/g, " ").replace(/\s+/g, " ").trim();
  const afterPara = normalized.match(/\b(?:para|sobre|de)\s+(.+)$/)?.[1] || normalized;
  return afterPara.replace(
    /\b(instala|instalar|instales|instale|instalarme|instalarla|agrega|agregar|anade|anadir|busca|buscar|busques|busque|encuentra|encontrar|skill|skills|habilidad|habilidades|una|un|el|la|los|las|que|yo|quiero|necesito|pueda|puedas|poder|utilizar|utilizarla|usar|hacer|leer|lectura|abrir|procesar|analizar)\b/g,
    " "
  ).replace(/\s+/g, " ").trim();
}
function parseSkillIntent(message) {
  const normalized = message.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const mentionsSkill = /\b(skill|skills|habilidad|habilidades)\b/.test(normalized);
  if (!mentionsSkill) return null;
  const looksLikeQuestion = /[¿?]/.test(message) && /\b(puedo|podemos|como|que|cual|cuanto)\b/.test(normalized);
  if (looksLikeQuestion) return null;
  const wantsInstall = /\b(instala|instalar|instales|instale|instalarme|instalarla|agrega|agregar|anade|anadir|install|add)\b/.test(
    normalized
  );
  const wantsSearch = /\b(busca|buscar|busques|busque|encuentra|encontrar|find|search)\b/.test(
    normalized
  );
  if (!wantsInstall && !wantsSearch) return null;
  const query = cleanSkillQuery(message);
  if (!query || query.length < 2) return null;
  return { action: wantsInstall ? "install" : "search", query };
}
function githubBlobToRaw(url) {
  return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/");
}
async function installSkillFromUrl(url, customName) {
  const rawUrl = githubBlobToRaw(url);
  const res = await fetch(rawUrl);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }
  const content = await res.text();
  const { meta } = parseFrontmatter(content);
  let name = customName || meta.name;
  if (!name) {
    const parts = rawUrl.split("/").filter(Boolean);
    const skillIdx = parts.findIndex((p) => p.toLowerCase() === "skills");
    if (skillIdx >= 0 && parts[skillIdx + 1]) {
      name = parts[skillIdx + 1];
    } else {
      name = "skill-" + Date.now().toString(36);
    }
  }
  name = sanitizeSkillName(name);
  const filePath = saveSkillFromContent(name, content);
  const assetFiles = await downloadGithubSkillAssets(rawUrl, path4.dirname(filePath));
  fs4.writeFileSync(
    path4.join(path4.dirname(filePath), "source.json"),
    JSON.stringify(
      { url: rawUrl, files: ["SKILL.md", ...assetFiles], installedAt: (/* @__PURE__ */ new Date()).toISOString() },
      null,
      2
    ),
    "utf-8"
  );
  updateSkillsReadme();
  return { name, path: filePath };
}
function findSkillUrls(text) {
  const re = /https?:\/\/(?:raw\.githubusercontent\.com|github\.com)\/[\w.-]+\/[\w.-]+\/(?:blob\/)?[\w.-/]+SKILL\.md/gi;
  const matches = text.match(re) || [];
  return [...new Set(matches)];
}
function saveSkillFromContent(name, content) {
  const dir = getSkillsDir();
  const skillDir = path4.join(dir, sanitizeSkillName(name));
  fs4.mkdirSync(skillDir, { recursive: true });
  const filePath = path4.join(skillDir, "SKILL.md");
  fs4.writeFileSync(filePath, content, "utf-8");
  return filePath;
}
function remoteSkillRawUrlCandidates(skill) {
  if (!skill.source.includes("/")) return [];
  const skillId = sanitizeSkillName(skill.skillId || skill.name);
  const branches = ["main", "master"];
  const paths = [
    `skills/${skillId}/SKILL.md`,
    `${skillId}/SKILL.md`,
    `.claude/skills/${skillId}/SKILL.md`,
    `.github/copilot/skills/${skillId}/SKILL.md`,
    `.github/skills/${skillId}/SKILL.md`
  ];
  return branches.flatMap(
    (branch) => paths.map((p) => `https://raw.githubusercontent.com/${skill.source}/${branch}/${p}`)
  );
}
async function fetchRemoteSkillContent(skill) {
  for (const url of remoteSkillRawUrlCandidates(skill)) {
    try {
      const res = await fetch(url, { headers: { "User-Agent": "Claudy/0.1" } });
      if (!res.ok) continue;
      const content = await res.text();
      if (!content.trim()) continue;
      return { content, sourceUrl: url };
    } catch {
    }
  }
  throw new Error(`No pude encontrar SKILL.md para ${skill.id}.`);
}
function parseGithubRawUrl(rawUrl) {
  const url = new URL(rawUrl);
  if (url.hostname !== "raw.githubusercontent.com") return null;
  const [owner, repo, branch, ...pathParts] = url.pathname.split("/").filter(Boolean);
  if (!owner || !repo || !branch || pathParts.length === 0) return null;
  if (pathParts[pathParts.length - 1].toLowerCase() !== "skill.md") return null;
  return {
    owner,
    repo,
    branch,
    filePath: pathParts.join("/"),
    dirPath: pathParts.slice(0, -1).join("/")
  };
}
function encodeGithubPath(githubPath) {
  return githubPath.split("/").map(encodeURIComponent).join("/");
}
function safeGithubRelativePath(baseDir, itemPath) {
  const relative = path4.posix.relative(baseDir, itemPath);
  if (!relative || relative.startsWith("..") || path4.posix.isAbsolute(relative)) return null;
  const parts = relative.split("/");
  if (parts.some((part) => !part || part === "." || part === "..")) return null;
  return parts.join("/");
}
async function listGithubDirectory(info, dirPath, depth = 0) {
  if (depth > 4) return [];
  const url = new URL(
    `https://api.github.com/repos/${info.owner}/${info.repo}/contents/${encodeGithubPath(dirPath)}`
  );
  url.searchParams.set("ref", info.branch);
  const response = await fetch(url, {
    headers: {
      Accept: "application/vnd.github+json",
      "User-Agent": "Claudy/0.1"
    }
  });
  if (!response.ok) return [];
  const payload = await response.json();
  const items = Array.isArray(payload) ? payload : [payload];
  const files = [];
  for (const item of items) {
    if (item.type === "file") {
      files.push(item);
    } else if (item.type === "dir") {
      files.push(...await listGithubDirectory(info, item.path, depth + 1));
    }
  }
  return files;
}
async function downloadGithubSkillAssets(sourceUrl, destinationDir) {
  const info = parseGithubRawUrl(sourceUrl);
  if (!info) return [];
  const files = await listGithubDirectory(info, info.dirPath);
  const written = [];
  let totalBytes = 0;
  for (const file of files) {
    const relativePath = safeGithubRelativePath(info.dirPath, file.path);
    if (!relativePath || relativePath.toLowerCase() === "skill.md") continue;
    const downloadUrl = file.download_url || `https://raw.githubusercontent.com/${info.owner}/${info.repo}/${info.branch}/${file.path}`;
    const response = await fetch(downloadUrl, { headers: { "User-Agent": "Claudy/0.1" } });
    if (!response.ok) continue;
    const bytes = Buffer.from(await response.arrayBuffer());
    totalBytes += bytes.length;
    if (totalBytes > MAX_SKILL_ASSET_BYTES) {
      throw new Error("Los archivos auxiliares del skill exceden el limite permitido.");
    }
    const target = path4.join(destinationDir, ...relativePath.split("/"));
    fs4.mkdirSync(path4.dirname(target), { recursive: true });
    fs4.writeFileSync(target, bytes);
    written.push(relativePath);
  }
  return written;
}
async function removeSkill(name) {
  const dir = getSkillsDir();
  const skillDir = path4.join(dir, name);
  if (!fs4.existsSync(skillDir)) return false;
  fs4.rmSync(skillDir, { recursive: true, force: true });
  return true;
}
var STOP_WORDS = /* @__PURE__ */ new Set([
  "de",
  "la",
  "el",
  "en",
  "y",
  "a",
  "los",
  "del",
  "las",
  "un",
  "por",
  "con",
  "una",
  "su",
  "para",
  "es",
  "al",
  "lo",
  "como",
  "si",
  "se",
  "su",
  "yo",
  "no",
  "sin",
  "son",
  "the",
  "a",
  "an",
  "is",
  "in",
  "of",
  "to",
  "it",
  "and",
  "or",
  "be",
  "as",
  "at",
  "by",
  "we",
  "for",
  "on",
  "with",
  "not",
  "but",
  "have",
  "from",
  "what",
  "you",
  "can"
]);
function tokenizeLocal(text) {
  return text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").split(/[^a-z0-9]+/).filter((t) => t.length > 2 && !STOP_WORDS.has(t));
}
function tfidfScore(queryTokens, skill) {
  const nameTokens = tokenizeLocal(skill.name);
  const descTokens = tokenizeLocal(skill.description);
  const bodyTokens = tokenizeLocal(skill.content.slice(0, 5e3));
  let score = 0;
  for (const qt of queryTokens) {
    if (nameTokens.includes(qt)) score += 10;
    if (descTokens.includes(qt)) score += 5;
    if (bodyTokens.includes(qt)) score += 1;
  }
  return score;
}
function findRelevantSkills(query, max = 3) {
  const skills = listSkills();
  const queryTokens = tokenizeLocal(query);
  if (queryTokens.length === 0) return [];
  return skills.map((skill) => ({ skill, score: tfidfScore(queryTokens, skill) })).filter((s) => s.score > 0).sort((a, b) => b.score - a.score).slice(0, max).map((s) => s.skill);
}
function buildSkillsContext(skills) {
  if (skills.length === 0) return "";
  return "\n\n=== SKILLS RELEVANTES ===\n" + skills.map((s) => `[Skill: ${s.name}]
${s.content.slice(0, 4e3)}`).join("\n\n---\n\n") + "\n=== FIN SKILLS ===";
}
async function tryBackendProxy(url, options) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(3e3), ...options });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
function backendBase() {
  return process.env.CLAUDY_BACKEND_URL || "http://127.0.0.1:3001";
}
async function searchRemoteSkills(query, limit = 8) {
  const backendUrl = `${backendBase()}/api/skills/remote-search?q=${encodeURIComponent(query)}`;
  const backendResult = await tryBackendProxy(backendUrl);
  if (backendResult && Array.isArray(backendResult)) {
    return backendResult.slice(0, limit);
  }
  const url = new URL(SKILLS_SEARCH_ENDPOINT);
  url.searchParams.set("q", query);
  const res = await fetch(url, { headers: { "User-Agent": "Claudy/0.1" } });
  if (!res.ok) throw new Error(`No pude buscar en skills.sh (${res.status}).`);
  const data = await res.json();
  const skills = data.skills || data.data || [];
  const seen = /* @__PURE__ */ new Set();
  return skills.filter((skill) => skill.id && skill.skillId && skill.source && !seen.has(skill.id)).filter((skill) => {
    seen.add(skill.id);
    return true;
  }).sort((a, b) => (b.installs || 0) - (a.installs || 0)).slice(0, limit);
}
async function installRemoteSkill(skill) {
  const { content, sourceUrl } = await fetchRemoteSkillContent(skill);
  const { meta } = parseFrontmatter(content);
  const name = sanitizeSkillName(meta.name || skill.skillId || skill.name);
  const filePath = saveSkillFromContent(name, content);
  const assetFiles = await downloadGithubSkillAssets(sourceUrl, path4.dirname(filePath));
  fs4.writeFileSync(
    path4.join(path4.dirname(filePath), "source.json"),
    JSON.stringify(
      {
        id: skill.id,
        source: skill.source,
        skillId: skill.skillId,
        installs: skill.installs || 0,
        skillsUrl: skill.url || `https://skills.sh/${skill.id}`,
        url: sourceUrl,
        files: ["SKILL.md", ...assetFiles],
        installedAt: (/* @__PURE__ */ new Date()).toISOString()
      },
      null,
      2
    ),
    "utf-8"
  );
  return {
    name,
    path: filePath,
    sourceUrl,
    readmePath: updateSkillsReadme()
  };
}
async function installBestSkillForQuery(query) {
  const backendUrl = `${backendBase()}/api/skills/install-best`;
  const backendResult = await tryBackendProxy(backendUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query })
  });
  if (backendResult && backendResult.skill?.name) {
    const candidates2 = await searchRemoteSkills(query, 8).catch(() => []);
    const remote = candidates2[0] || { id: query, skillId: query, name: query, source: "unknown" };
    return {
      installed: {
        name: backendResult.skill.name,
        path: backendResult.skill.path,
        sourceUrl: backendResult.sourceUrl || "",
        readmePath: backendResult.readmePath || ""
      },
      remote,
      candidates: candidates2
    };
  }
  const candidates = await searchRemoteSkills(query, 8);
  if (candidates.length === 0) throw new Error(`No encontre skills para "${query}".`);
  const errors = [];
  for (const candidate of candidates) {
    try {
      const installed = await installRemoteSkill(candidate);
      return { installed, remote: candidate, candidates };
    } catch (err) {
      errors.push(`${candidate.id}: ${err.message || String(err)}`);
    }
  }
  throw new Error(`Encontre candidatos, pero no pude instalar ninguno:
${errors.join("\n")}`);
}

// src/websearch.ts
var CURRENT_INFO_PATTERN = /\b(hoy|ayer|ultimo|ultima|ultimos|ultimas|último|última|últimos|últimas|reciente|actual|precio|clima|tiempo|temperatura|partido|marcador|goles|fixture|noticia|noticias|cotizacion|cotización|dolar|dólar|bitcoin|btc|agenda|calendario|resultado|resultados|cuando|cuándo|próximo|proximo|siguiente|jugará|jugara|juega)\b/i;
var EXPLICIT_SEARCH_PATTERN = /\b(?:busca en internet|busca por internet|buscar en internet|buscar por internet|búsqueda por internet|busqueda por internet|search the web|googlea|averigua|investiga)\b/i;
function shouldSearchWeb(message) {
  const trimmed = message.trim();
  if (trimmed.startsWith("/")) return false;
  if (trimmed.length < 8) return false;
  return EXPLICIT_SEARCH_PATTERN.test(trimmed) || CURRENT_INFO_PATTERN.test(trimmed);
}
function extractSearchQuery(message) {
  return message.replace(/^\/search\s+/i, "").replace(
    /\b(claudy|busca en internet|buscar en internet|busca por internet|buscar por internet|search the web|googlea|averigua|investiga|consulta|revisa|buscar|busca)\b/gi,
    ""
  ).replace(/\b(porfa|por favor|me dices|dime|sabes|quiero saber|puedes)\b/gi, "").replace(/[?¿!¡]+/g, "").replace(/\s+/g, " ").trim();
}
async function searchWeb(query, backendUrl = "http://127.0.0.1:3001") {
  const normalized = extractSearchQuery(query);
  if (!normalized) return [];
  const currentYear = (/* @__PURE__ */ new Date()).getFullYear().toString();
  const hasYear = /\b20\d{2}\b/.test(normalized);
  const timeEnhanced = hasYear ? normalized : `${normalized} ${currentYear}`;
  try {
    const url = new URL("/api/search", backendUrl);
    url.searchParams.set("q", timeEnhanced);
    const response = await fetch(url, {
      signal: typeof AbortSignal.timeout === "function" ? AbortSignal.timeout(1e4) : void 0
    });
    if (response.ok) {
      const data = await response.json();
      if (data.results?.length) return data.results;
    }
  } catch {
  }
  return searchDuckDuckGoDirect(timeEnhanced);
}
function decodeHtml(input) {
  return input.replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/\s+/g, " ").trim();
}
function extractHref(rawAnchor) {
  const href = rawAnchor.match(/\shref=["']([^"']+)["']/i)?.[1] || "";
  if (!href) return "";
  try {
    const normalized = href.startsWith("//") ? `https:${href}` : href;
    const url = new URL(normalized, "https://duckduckgo.com");
    const redirected = url.searchParams.get("uddg");
    return redirected ? decodeURIComponent(redirected) : url.toString();
  } catch {
    return href;
  }
}
async function searchDuckDuckGoDirect(query, limit = 5) {
  const response = await fetch(
    `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`,
    {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Claudy/0.1"
      },
      signal: typeof AbortSignal.timeout === "function" ? AbortSignal.timeout(8e3) : void 0
    }
  );
  if (!response.ok) return [];
  const html = await response.text();
  const blocks = html.split(/<div[^>]+class=["'][^"']*result[^"']*["'][^>]*>/i);
  const results = [];
  for (const block of blocks) {
    const anchor = block.match(
      /<a[^>]+class=["'][^"']*result__a[^"']*["'][^>]*>[\s\S]*?<\/a>/i
    )?.[0];
    if (!anchor) continue;
    const title = decodeHtml(anchor);
    const url = extractHref(anchor);
    const snippetRaw = block.match(
      /<a[^>]+class=["'][^"']*result__snippet[^"']*["'][^>]*>[\s\S]*?<\/a>/i
    )?.[0] || block.match(
      /<div[^>]+class=["'][^"']*result__snippet[^"']*["'][^>]*>[\s\S]*?<\/div>/i
    )?.[0] || "";
    const snippet = decodeHtml(snippetRaw);
    if (title && url && !results.some((r) => r.url === url)) {
      results.push({ title, snippet, url });
    }
    if (results.length >= limit) break;
  }
  return results;
}
function formatSearchContext(query, results) {
  if (results.length === 0) return "";
  const top = results.slice(0, 3);
  return [
    `=== INFORMACI\xD3N DE INTERNET (b\xFAsqueda: "${query}") ===`,
    "Usa estos datos para responder directamente. Da la respuesta como si la supieras, sin mencionar que buscaste:",
    "",
    ...top.map(
      (r, i) => `[${i + 1}] ${r.title}
${r.snippet || ""}${r.url ? `
Fuente: ${r.url}` : ""}`
    ),
    "",
    "=== FIN ==="
  ].join("\n");
}

// src/memory.ts
import fs5 from "fs";
import path5 from "path";
import os3 from "os";
var MEMORY_DIR = path5.join(os3.homedir(), ".claudy", "memory");
var MEMORY_INDEX = path5.join(MEMORY_DIR, "index.jsonl");
var MEMORY_ARCHIVE = path5.join(MEMORY_DIR, "archive.jsonl");
function ensureMemoryDir() {
  if (!fs5.existsSync(MEMORY_DIR)) {
    fs5.mkdirSync(MEMORY_DIR, { recursive: true });
  }
}
function addMemory(content, tags, session) {
  ensureMemoryDir();
  const entry = {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    content,
    timestamp: Date.now(),
    tags,
    session
  };
  fs5.appendFileSync(MEMORY_INDEX, JSON.stringify(entry) + "\n", "utf-8");
  return entry;
}
function searchMemories(query, limit = 10) {
  ensureMemoryDir();
  if (!fs5.existsSync(MEMORY_INDEX)) return [];
  const lines = fs5.readFileSync(MEMORY_INDEX, "utf-8").split("\n").filter(Boolean);
  const entries = lines.map((l) => JSON.parse(l));
  const queryLower = query.toLowerCase();
  const scored = entries.map((e) => ({
    entry: e,
    score: scoreRelevance(e.content, e.tags, queryLower)
  })).filter((s) => s.score > 0).sort((a, b) => b.score - a.score).slice(0, limit);
  return scored.map((s) => s.entry);
}
function listMemories(limit = 20) {
  ensureMemoryDir();
  if (!fs5.existsSync(MEMORY_INDEX)) return [];
  const lines = fs5.readFileSync(MEMORY_INDEX, "utf-8").split("\n").filter(Boolean);
  const entries = lines.map((l) => JSON.parse(l));
  return entries.sort((a, b) => b.timestamp - a.timestamp).slice(0, limit);
}
function deleteMemory(id) {
  ensureMemoryDir();
  if (!fs5.existsSync(MEMORY_INDEX)) return false;
  const lines = fs5.readFileSync(MEMORY_INDEX, "utf-8").split("\n").filter(Boolean);
  const filtered = lines.filter((l) => {
    const entry = JSON.parse(l);
    return entry.id !== id;
  });
  fs5.writeFileSync(MEMORY_INDEX, filtered.join("\n") + "\n", "utf-8");
  return filtered.length < lines.length;
}
function archiveOldMemories(maxAgeDays = 7) {
  ensureMemoryDir();
  if (!fs5.existsSync(MEMORY_INDEX)) return 0;
  const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1e3;
  const lines = fs5.readFileSync(MEMORY_INDEX, "utf-8").split("\n").filter(Boolean);
  const active = [];
  const archived = [];
  for (const line of lines) {
    const entry = JSON.parse(line);
    if (entry.timestamp < cutoff) {
      archived.push(line);
    } else {
      active.push(line);
    }
  }
  if (archived.length > 0) {
    fs5.appendFileSync(MEMORY_ARCHIVE, archived.join("\n") + "\n", "utf-8");
    fs5.writeFileSync(MEMORY_INDEX, active.join("\n") + "\n", "utf-8");
  }
  return archived.length;
}
function scoreRelevance(content, tags, query) {
  const contentLower = content.toLowerCase();
  let score = 0;
  if (contentLower.includes(query)) {
    score += 10;
  }
  const words = query.split(/\s+/);
  for (const word of words) {
    if (contentLower.includes(word)) {
      score += 2;
    }
  }
  if (tags) {
    for (const tag of tags) {
      if (tag.toLowerCase().includes(query) || query.includes(tag.toLowerCase())) {
        score += 5;
      }
    }
  }
  return score;
}

// src/fileops.ts
import fs6 from "fs";
import os4 from "os";
import path6 from "path";
import { exec as exec2, execFile } from "child_process";
import { promisify as promisify2 } from "util";
var execFileAsync = promisify2(execFile);
function sanitizeFilename(name) {
  const safe = [...name].filter((c) => /[a-zA-Z0-9._\- ]/.test(c)).join("");
  return safe || "archivo_descargado";
}
async function extractFilename(url) {
  try {
    const parsed = new URL(url);
    const basename = path6.basename(parsed.pathname);
    if (basename && basename.includes(".")) return basename;
  } catch {
  }
  try {
    const resp = await fetch(url, {
      method: "HEAD",
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Claudy/0.1" },
      signal: AbortSignal.timeout(8e3)
    });
    const cd = resp.headers.get("Content-Disposition") || "";
    if (cd.includes("filename=")) {
      if (cd.includes("filename*=")) {
        const raw = cd.split("filename*=")[1]?.split("''")[1];
        if (raw) return decodeURIComponent(raw);
      }
      const match = cd.match(/filename=["']?([^"';]+)["']?/);
      if (match) return match[1];
    }
    const ct = resp.headers.get("Content-Type") || "";
    const extMap = {
      "application/pdf": ".pdf",
      "application/zip": ".zip",
      "application/x-rar-compressed": ".rar",
      "application/x-7z-compressed": ".7z",
      "application/x-msdownload": ".exe",
      "application/x-msi": ".msi",
      "image/png": ".png",
      "image/jpeg": ".jpg",
      "image/gif": ".gif",
      "image/webp": ".webp",
      "video/mp4": ".mp4",
      "audio/mpeg": ".mp3",
      "text/html": ".html",
      "text/plain": ".txt"
    };
    for (const [mime, ext] of Object.entries(extMap)) {
      if (ct.includes(mime)) return `descarga_claudy${ext}`;
    }
  } catch {
  }
  return "descarga_claudy";
}
async function downloadFile(url, destDir) {
  url = url.trim().replace(/^["']|["']$/g, "");
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    return { ok: false, message: "URL inv\xE1lida. Debe empezar con http:// o https://" };
  }
  const dir = destDir || path6.join(os4.homedir(), "Downloads", "Claudy");
  fs6.mkdirSync(dir, { recursive: true });
  try {
    const filename = await extractFilename(url);
    const safeName = sanitizeFilename(filename);
    let destPath = path6.join(dir, safeName);
    let counter = 1;
    const base = path6.basename(safeName, path6.extname(safeName));
    const ext = path6.extname(safeName);
    while (fs6.existsSync(destPath)) {
      destPath = path6.join(dir, `${base}_${counter}${ext}`);
      counter++;
    }
    const resp = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Claudy/0.1" },
      signal: AbortSignal.timeout(12e4)
    });
    if (!resp.ok) {
      return { ok: false, message: `Error HTTP ${resp.status}: ${resp.statusText}` };
    }
    const buffer = Buffer.from(await resp.arrayBuffer());
    fs6.writeFileSync(destPath, buffer);
    const sizeStr = buffer.length < 1024 * 1024 ? `${(buffer.length / 1024).toFixed(1)} KB` : `${(buffer.length / (1024 * 1024)).toFixed(1)} MB`;
    return {
      ok: true,
      message: `Archivo descargado:
${destPath}
Tama\xF1o: ${sizeStr}`,
      path: destPath,
      size: sizeStr
    };
  } catch (err) {
    if (err.name === "TimeoutError" || err.name === "AbortError") {
      return { ok: false, message: "Timeout: la descarga tard\xF3 m\xE1s de 120s." };
    }
    return { ok: false, message: `Error descargando: ${err.message}` };
  }
}
var FILE_EXTENSIONS = [
  ".pdf",
  ".zip",
  ".rar",
  ".7z",
  ".exe",
  ".msi",
  ".mp4",
  ".mp3",
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".docx",
  ".xlsx",
  ".pptx",
  ".txt",
  ".csv",
  ".json",
  ".xml",
  ".iso",
  ".torrent",
  ".apk"
];
function decodeHtml2(input) {
  return input.replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/\s+/g, " ").trim();
}
async function searchFilesOnline(query) {
  const q = query.trim();
  if (!q || q.length < 2) {
    return { ok: false, message: 'Escribe qu\xE9 archivo buscas. Ej: /buscar "python 3.12 installer"' };
  }
  const fileQuery = `${q} filetype:pdf OR filetype:zip OR filetype:exe OR download`;
  try {
    const resp = await fetch(
      `https://html.duckduckgo.com/html/?q=${encodeURIComponent(fileQuery)}`,
      {
        headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Claudy/0.1" },
        signal: AbortSignal.timeout(1e4)
      }
    );
    if (!resp.ok) return { ok: false, message: "B\xFAsqueda fall\xF3. Intenta de nuevo." };
    const html = await resp.text();
    const blocks = html.split(/<div[^>]+class=["'][^"']*result[^"']*["'][^>]*>/i);
    const results = [];
    for (const block of blocks) {
      const anchor = block.match(
        /<a[^>]+class=["'][^"']*result__a[^"']*["'][^>]*>[\s\S]*?<\/a>/i
      )?.[0];
      if (!anchor) continue;
      const title = decodeHtml2(anchor);
      const hrefMatch = anchor.match(/\shref=["']([^"']+)["']/i);
      let url = hrefMatch?.[1] || "";
      if (url.startsWith("//")) url = `https:${url}`;
      try {
        const parsed = new URL(url, "https://duckduckgo.com");
        const redirected = parsed.searchParams.get("uddg");
        if (redirected) url = decodeURIComponent(redirected);
      } catch {
      }
      const snippetRaw = block.match(
        /<a[^>]+class=["'][^"']*result__snippet[^"']*["'][^>]*>[\s\S]*?<\/a>/i
      )?.[0] || block.match(
        /<div[^>]+class=["'][^"']*result__snippet[^"']*["'][^>]*>[\s\S]*?<\/div>/i
      )?.[0] || "";
      const snippet = decodeHtml2(snippetRaw);
      if (title && url && !results.some((r) => r.url === url)) {
        results.push({ title, snippet, url });
      }
      if (results.length >= 8) break;
    }
    if (results.length === 0) {
      return { ok: false, message: `No encontr\xE9 resultados para "${q}". Prueba con otras palabras.` };
    }
    const scored = results.map((r) => {
      let score = 0;
      const lower = r.url.toLowerCase();
      for (const ext of FILE_EXTENSIONS) {
        if (lower.includes(ext)) score += 10;
      }
      if (lower.includes("download")) score += 5;
      if (lower.includes("github")) score += 3;
      return { ...r, _score: score };
    });
    scored.sort((a, b) => b._score - a._score);
    return {
      ok: true,
      message: `Resultados para "${q}":`,
      results: scored.slice(0, 8).map(({ _score, ...r }) => r)
    };
  } catch {
    return { ok: false, message: "Error conectando al buscador. Revisa tu internet." };
  }
}
async function executeFile(filePath) {
  filePath = filePath.trim().replace(/^["']|["']$/g, "");
  let resolved = filePath;
  if (resolved.startsWith("~")) {
    resolved = path6.join(os4.homedir(), resolved.slice(1));
  }
  if (!path6.isAbsolute(resolved)) {
    resolved = path6.resolve(resolved);
  }
  if (!fs6.existsSync(resolved)) {
    const bases = [os4.homedir(), path6.join(os4.homedir(), "Downloads"), path6.join(os4.homedir(), "Desktop")];
    for (const base of bases) {
      const candidate = path6.join(base, filePath);
      if (fs6.existsSync(candidate)) {
        resolved = candidate;
        break;
      }
    }
    if (!fs6.existsSync(resolved)) {
      return { ok: false, message: `No encuentro el archivo: ${filePath}` };
    }
  }
  const ext = path6.extname(resolved).toLowerCase();
  const isExecutable = [".exe", ".bat", ".cmd", ".ps1", ".msi", ".vbs", ".js"].includes(ext);
  try {
    if (process.platform === "win32") {
      await new Promise((resolve, reject) => {
        exec2(`start "" "${resolved}"`, { windowsHide: true }, (err) => {
          if (err) reject(err);
          else resolve();
        });
      });
    } else {
      const cmd = process.platform === "darwin" ? "open" : "xdg-open";
      await new Promise((resolve, reject) => {
        exec2(`"${cmd}" "${resolved}"`, (err) => {
          if (err) reject(err);
          else resolve();
        });
      });
    }
    const warn = isExecutable ? "\n\u26A0\uFE0F  Es un ejecutable \u2014 aseg\xFArate de confiar en la fuente." : "";
    return {
      ok: true,
      message: `Abierto: ${resolved}${warn}`,
      path: resolved
    };
  } catch (err) {
    return { ok: false, message: `Error ejecutando: ${err.message}` };
  }
}
var TRUSTED_DOMAINS = [
  "github.com",
  "sourceforge.net",
  "fosshub.com",
  "ninite.com",
  "chocolatey.org",
  "winget.run",
  "microsoft.com",
  "apps.microsoft.com",
  "apple.com",
  "adobe.com",
  "oracle.com",
  "java.com",
  "win-rar.com",
  "rarlab.com",
  "videolan.org",
  "notepad-plus-plus.org",
  "7-zip.org",
  "code.visualstudio.com"
];
var CLEANUP_WORDS = [
  "download",
  "descargar",
  "descarga",
  "bajar",
  "instalar",
  "instala",
  "instalador",
  "install",
  "installer",
  "gratis",
  "free",
  "latest",
  "ultima",
  "\xFAltima",
  "version",
  "versi\xF3n"
];
function scoreDownloadUrl(url, query) {
  let score = 0;
  const lower = url.toLowerCase();
  const qLower = query.toLowerCase();
  if (/\.(exe|msi|dmg|pkg|apk|deb|rpm|appimage)$/i.test(lower)) score += 30;
  if (/\.(zip|7z|rar|tar\.gz|tar\.xz)$/i.test(lower)) score += 15;
  for (const domain of TRUSTED_DOMAINS) {
    if (lower.includes(domain)) {
      score += 25;
      break;
    }
  }
  const appWords = qLower.split(/\s+/).filter((w) => w.length > 2);
  for (const word of appWords) {
    if (lower.includes(word)) score += 5;
  }
  if (lower.includes("download")) score += 5;
  if (lower.includes("release")) score += 3;
  if (lower.startsWith("https://")) score += 2;
  return score;
}
function cleanupAppName(input) {
  let clean = input.trim().replace(/^["']|["']$/g, "").replace(/[.!?¿¡]+$/g, "").replace(/\b(por favor|please)\b/gi, "").trim();
  for (const word of CLEANUP_WORDS) {
    clean = clean.replace(new RegExp(`\\b${word}\\b`, "gi"), " ");
  }
  return clean.replace(/\s+/g, " ").trim() || input.trim();
}
function splitWingetRow(line) {
  return line.trim().split(/\s{2,}/).map((part) => part.trim()).filter(Boolean);
}
function parseWingetSearch(stdout, query) {
  const rows = stdout.split(/\r?\n/).map((line) => line.trimEnd()).filter((line) => line.trim() && !/^[-\s]+$/.test(line) && !/^Name\s+Id\s+/i.test(line));
  const queryWords = query.toLowerCase().split(/\s+/).filter((word) => word.length > 1);
  const candidates = rows.map((line) => {
    const parts = splitWingetRow(line);
    if (parts.length < 2) return null;
    if (parts[1].toLowerCase() === "id") return null;
    return {
      name: parts[0],
      id: parts[1],
      version: parts[2] || ""
    };
  }).filter((pkg) => Boolean(pkg));
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
async function installWithWinget(query) {
  if (process.platform !== "win32") {
    return { ok: false, message: "winget solo aplica en Windows." };
  }
  try {
    await execFileAsync("winget", ["--version"], { timeout: 1e4, windowsHide: true });
  } catch {
    return { ok: false, message: "winget no esta disponible en este equipo." };
  }
  const search = await execFileAsync(
    "winget",
    ["search", "--source", "winget", "--accept-source-agreements", query],
    { timeout: 45e3, windowsHide: true, maxBuffer: 1024 * 1024 }
  );
  const pkg = parseWingetSearch(search.stdout, query);
  if (!pkg) {
    return { ok: false, message: `winget no encontro un paquete claro para "${query}".` };
  }
  const install = await execFileAsync(
    "winget",
    [
      "install",
      "--id",
      pkg.id,
      "--exact",
      "--source",
      "winget",
      "--accept-package-agreements",
      "--accept-source-agreements"
    ],
    { timeout: 15 * 6e4, windowsHide: false, maxBuffer: 1024 * 1024 }
  );
  const output = [install.stdout, install.stderr].filter(Boolean).join("\n").trim();
  try {
    exec2(`start "" "${pkg.name}"`, { windowsHide: true });
  } catch {
  }
  return {
    ok: true,
    message: [
      `Instalado con winget: ${pkg.name}`,
      `Paquete: ${pkg.id}`,
      output ? `Salida:
${output.slice(-2e3)}` : "",
      `Intento de apertura enviado para: ${pkg.name}`
    ].filter(Boolean).join("\n")
  };
}
function isLikelyInstallerPath(filePath) {
  return /\.(exe|msi|dmg|pkg|apk|deb|rpm|appimage)$/i.test(filePath);
}
async function installApp(appName) {
  const query = cleanupAppName(appName);
  if (!query || query.length < 2) {
    return { ok: false, message: "Dime qu\xE9 aplicaci\xF3n quieres instalar. Ej: /instalar winrar" };
  }
  const steps = [];
  steps.push(`Buscando instalador confiable para "${query}"...`);
  if (process.platform === "win32") {
    try {
      const winget = await installWithWinget(query);
      if (winget.ok) {
        return {
          ok: true,
          message: [
            ...steps,
            "Use winget como fuente principal para evitar instaladores falsos.",
            winget.message
          ].join("\n")
        };
      }
      steps.push(`winget no resolvio la instalacion: ${winget.message}`);
    } catch (err) {
      steps.push(`winget fallo: ${err.message || String(err)}`);
    }
  }
  steps.push(`\u{1F50D} Buscando "${query}" en internet...`);
  const installQuery = `${query} official download windows installer`;
  const sr = await searchFilesOnline(installQuery);
  if (!sr.ok || !sr.results || sr.results.length === 0) {
    return { ok: false, message: `No encontr\xE9 resultados para "${query}".` };
  }
  const scored = sr.results.map((r) => ({
    ...r,
    _score: scoreDownloadUrl(r.url, query)
  }));
  scored.sort((a, b) => b._score - a._score);
  const best = scored[0];
  steps.push(`\u2713 Encontrado: ${best.title}`);
  steps.push(`  URL: ${best.url}`);
  steps.push(`\u2B07 Descargando...`);
  const dl = await downloadFile(best.url);
  if (!dl.ok || !dl.path) {
    steps.push(`\u2717 Error: ${dl.message}`);
    return { ok: false, message: steps.join("\n") };
  }
  steps.push(`\u2713 ${dl.message}`);
  if (!isLikelyInstallerPath(dl.path)) {
    steps.push("La descarga no parece ser un instalador ejecutable. No la ejecutare automaticamente.");
    return { ok: false, message: steps.join("\n"), path: dl.path };
  }
  steps.push(`  Guardado en: ${dl.path}`);
  steps.push(`\u25B6 Ejecutando...`);
  const ext = path6.extname(dl.path).toLowerCase();
  if ([".exe", ".msi", ".bat", ".cmd"].includes(ext)) {
    steps.push("  \u26A0\uFE0F  Se abrir\xE1 el instalador \u2014 sigue los pasos en pantalla.");
  }
  const exec4 = await executeFile(dl.path);
  if (!exec4.ok) {
    steps.push(`\u2717 Error ejecutando: ${exec4.message}`);
    return { ok: false, message: steps.join("\n") };
  }
  steps.push(`\u2713 ${exec4.message}`);
  return { ok: true, message: steps.join("\n"), path: dl.path };
}
var URL_PATTERN = /https?:\/\/[^\s<>"]+/i;
var DOWNLOAD_KWS = [
  "descargar",
  "descarga",
  "desc\xE1rgame",
  "descargame",
  "bajar",
  "bajame",
  "b\xE1jame",
  "download",
  "trae este archivo",
  "consigue este archivo",
  "baja este archivo",
  "descarga este archivo",
  "quiero descargar",
  "necesito descargar"
];
var SEARCH_DOWNLOAD_KWS = [
  "busca para descargar",
  "buscar para descargar",
  "encuentra para descargar",
  "b\xFAscame",
  "buscame",
  "busca el archivo",
  "buscar el archivo",
  "busca un",
  "buscar un",
  "busca una",
  "buscar una",
  "busca el instalador",
  "buscar el instalador",
  "donde descargar",
  "d\xF3nde descargar",
  "donde puedo descargar",
  "donde encontrar",
  "d\xF3nde encontrar"
];
var EXECUTE_KWS = [
  "ejecutar",
  "ejecuta",
  "abrir archivo",
  "abre el archivo",
  "abre este archivo",
  "correr",
  "corre el archivo",
  "run file",
  "lanza",
  "abrir con"
];
var INSTALL_KWS = [
  "instalar",
  "instala",
  "instalame",
  "inst\xE1lame",
  "baja e instala",
  "descarga e instala",
  "bajar e instalar",
  "descargar e instalar",
  "busca e instala",
  "buscar e instalar",
  "quiero instalar",
  "necesito instalar",
  "puedes instalar",
  "podrias instalar",
  "podr\xEDas instalar",
  "me puedes instalar",
  "me instalas",
  "consigueme e instala",
  "cons\xEDgueme e instala",
  "bajame e instala",
  "b\xE1jame e instala"
];
function parseFileIntent(input) {
  const lower = input.toLowerCase().trim();
  if (!lower) return null;
  const urls = lower.match(URL_PATTERN);
  if (urls && DOWNLOAD_KWS.some((kw) => lower.includes(kw))) {
    return { action: "download", target: urls[0] };
  }
  if (!urls) {
    for (const kw of SEARCH_DOWNLOAD_KWS) {
      if (lower.includes(kw)) {
        const idx = lower.indexOf(kw) + kw.length;
        let target = input.slice(idx).trim();
        target = target.replace(/^(de|del|la|el|los|las|un|una)\s+/i, "").trim();
        if (target.length >= 2) {
          return { action: "search-download", target };
        }
      }
    }
  }
  for (const kw of EXECUTE_KWS) {
    if (lower.includes(kw)) {
      const idx = lower.indexOf(kw) + kw.length;
      let target = input.slice(idx).trim();
      target = target.replace(/[.!?¿¡]+$/, "").trim();
      if (target.length >= 2) {
        return { action: "execute", target };
      }
    }
  }
  for (const kw of INSTALL_KWS) {
    if (lower.includes(kw)) {
      const idx = lower.indexOf(kw) + kw.length;
      let target = input.slice(idx).trim();
      target = target.replace(/[.!?¿¡]+$/, "").trim();
      target = target.replace(/^(de|del|la|el|los|las|un|una)\s+/i, "").trim();
      if (target.length >= 2) {
        return { action: "auto-install", target };
      }
    }
  }
  return null;
}

// src/export.ts
import { writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";
function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
function formatMarkdown(messages, sessionName) {
  const lines = [];
  lines.push(`# ${sessionName}`);
  lines.push("");
  lines.push(`Exported: ${(/* @__PURE__ */ new Date()).toLocaleString("es-ES")}`);
  lines.push("");
  lines.push("---");
  lines.push("");
  for (const msg of messages) {
    const role = msg.role === "user" ? "\u{1F464} Usuario" : "\u{1F916} Asistente";
    lines.push(`### ${role}`);
    lines.push("");
    lines.push(msg.content);
    lines.push("");
    lines.push("---");
    lines.push("");
  }
  return lines.join("\n");
}
function formatHTML(messages, sessionName) {
  const body = messages.map((msg) => {
    const role = msg.role === "user" ? "Usuario" : "Asistente";
    const cls = msg.role === "user" ? "message-user" : "message-assistant";
    return `  <div class="${cls}">
    <h3>${role}</h3>
    <pre>${escapeHtml(msg.content)}</pre>
  </div>`;
  }).join("\n\n");
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
  <p class="meta">Exportado: ${(/* @__PURE__ */ new Date()).toLocaleString("es-ES")}</p>
${body}
</body>
</html>`;
}
function formatTXT(messages, sessionName) {
  const lines = [];
  lines.push(`${sessionName}`);
  lines.push("=".repeat(sessionName.length));
  lines.push("");
  lines.push(`Exportado: ${(/* @__PURE__ */ new Date()).toLocaleString("es-ES")}`);
  lines.push("");
  for (const msg of messages) {
    const role = msg.role === "user" ? "Usuario" : "Asistente";
    lines.push(`[${role}]`);
    lines.push(msg.content);
    lines.push("");
    lines.push("-".repeat(40));
    lines.push("");
  }
  return lines.join("\n");
}
function formatPDF(messages, sessionName) {
  const lines = [];
  lines.push(`%PDF-1.4`);
  lines.push(`1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj`);
  lines.push(`2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj`);
  const content = messages.map((msg) => {
    const role = msg.role === "user" ? "Usuario" : "Asistente";
    return `${role}: ${msg.content.replace(/\n/g, " ")}`;
  }).join("\n");
  const streamContent = `BT /F1 10 Tf 50 750 Td (${escapePdf(sessionName)}) Tj ET
${content.split("\n").slice(0, 50).map((line, i) => `BT /F1 8 Tf 50 ${730 - i * 14} Td (${escapePdf(line)}) Tj ET`).join("\n")}`;
  lines.push(
    `3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj`
  );
  lines.push(`4 0 obj << /Length ${streamContent.length} >> stream
${streamContent}
endstream endobj`);
  lines.push(`5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj`);
  lines.push(`xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000${String(streamContent.length + 100).padStart(10, "0")} 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
${streamContent.length + 300}
%%EOF`);
  return lines.join("\n");
}
function escapePdf(str) {
  return str.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}
function exportChat(messages, sessionName, format, outputDir) {
  let content;
  let extension;
  switch (format) {
    case "md":
      content = formatMarkdown(messages, sessionName);
      extension = "md";
      break;
    case "html":
      content = formatHTML(messages, sessionName);
      extension = "html";
      break;
    case "txt":
      content = formatTXT(messages, sessionName);
      extension = "txt";
      break;
    case "pdf":
      content = formatPDF(messages, sessionName);
      extension = "pdf";
      break;
    default:
      throw new Error(`Formato no soportado: ${format}`);
  }
  const dir = outputDir || process.cwd();
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
  const safeName = sessionName.replace(/[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]/g, "").replace(/\s+/g, "_");
  const timestamp = (/* @__PURE__ */ new Date()).toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const filename = join(dir, `${safeName}_${timestamp}.${extension}`);
  writeFileSync(filename, content, "utf-8");
  return filename;
}
function getSupportedFormats() {
  return "Formatos soportados: md (Markdown), html (HTML), txt (Texto plano), pdf (PDF b\xE1sico)";
}

// src/session-search.ts
var CONTEXT_CHARS = 80;
function normalizeText(text) {
  return text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9\s]/g, "");
}
function extractTerms(query) {
  return normalizeText(query).split(/\s+/).filter((t) => t.length >= 2);
}
function highlightText(text, terms) {
  let result = text;
  for (const term of terms) {
    const regex = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
    result = result.replace(regex, ">>$1<<");
  }
  return result;
}
function extractFragment(message, query, terms) {
  const normalizedContent = normalizeText(message.content);
  const normalizedQuery = normalizeText(query);
  const matchIndex = normalizedContent.indexOf(normalizedQuery);
  if (matchIndex === -1) {
    let bestIndex = -1;
    let bestTerm = "";
    for (const term of terms) {
      const idx = normalizedContent.indexOf(term);
      if (idx !== -1 && (bestIndex === -1 || idx < bestIndex)) {
        bestIndex = idx;
        bestTerm = term;
      }
    }
    if (bestIndex === -1) return null;
    const start2 = Math.max(0, bestIndex - CONTEXT_CHARS);
    const end2 = Math.min(message.content.length, bestIndex + bestTerm.length + CONTEXT_CHARS);
    const fragment2 = message.content.slice(start2, end2);
    const prefix2 = start2 > 0 ? "..." : "";
    const suffix2 = end2 < message.content.length ? "..." : "";
    return {
      messageId: message.id,
      role: message.role,
      text: `${prefix2}${fragment2}${suffix2}`,
      highlightedText: `${prefix2}${highlightText(fragment2, terms)}${suffix2}`,
      timestamp: message.timestamp
    };
  }
  const start = Math.max(0, matchIndex - CONTEXT_CHARS);
  const end = Math.min(message.content.length, matchIndex + query.length + CONTEXT_CHARS);
  const fragment = message.content.slice(start, end);
  const prefix = start > 0 ? "..." : "";
  const suffix = end < message.content.length ? "..." : "";
  return {
    messageId: message.id,
    role: message.role,
    text: `${prefix}${fragment}${suffix}`,
    highlightedText: `${prefix}${highlightText(fragment, terms)}${suffix}`,
    timestamp: message.timestamp
  };
}
function scoreResult(result, terms) {
  let score = 0;
  const normalizedName = normalizeText(result.session.name);
  for (const term of terms) {
    if (normalizedName.includes(term)) {
      score += 10;
    }
  }
  score += result.matches.length * 2;
  const now = Date.now();
  for (const match of result.matches) {
    const ageHours = (now - match.timestamp) / (1e3 * 60 * 60);
    if (ageHours < 24) score += 3;
    else if (ageHours < 168) score += 2;
    else score += 1;
  }
  return score;
}
function searchSessions(query, maxResults = 10) {
  const terms = extractTerms(query);
  if (terms.length === 0) return [];
  const sessions = listSessions();
  const results = [];
  for (const session of sessions) {
    const matches = [];
    const normalizedName = normalizeText(session.name);
    const nameMatches = terms.filter((t) => normalizedName.includes(t));
    if (nameMatches.length > 0) {
      matches.push({
        messageId: "session-name",
        role: "user",
        text: `Nombre: ${session.name}`,
        highlightedText: `Nombre: ${highlightText(session.name, terms)}`,
        timestamp: session.createdAt
      });
    }
    for (const message of session.messages) {
      const fragment = extractFragment(message, query, terms);
      if (fragment) {
        matches.push(fragment);
      }
    }
    if (matches.length > 0) {
      const result = {
        session,
        matches,
        relevanceScore: 0
      };
      result.relevanceScore = scoreResult(result, terms);
      results.push(result);
    }
  }
  results.sort((a, b) => b.relevanceScore - a.relevanceScore);
  return results.slice(0, maxResults);
}
function formatSearchResults(results, query) {
  if (results.length === 0) {
    return `No se encontraron resultados para "${query}"`;
  }
  const lines = [];
  lines.push(`\u{1F50D} Resultados para "${query}" (${results.length} sesiones):
`);
  for (const result of results) {
    const session = result.session;
    const date = new Date(session.updatedAt).toLocaleDateString("es-ES");
    const msgCount = session.messages.length;
    lines.push(`\u{1F4C2} ${session.name}`);
    lines.push(`   ID: ${session.id.substring(0, 8)}... | ${msgCount} mensajes | ${date}`);
    lines.push(`   Coincidencias: ${result.matches.length}`);
    lines.push("");
    const topFragments = result.matches.slice(0, 3);
    for (const fragment of topFragments) {
      const role = fragment.role === "user" ? "\u{1F464}" : "\u{1F916}";
      const time = new Date(fragment.timestamp).toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit"
      });
      lines.push(`   ${role} [${time}] ${fragment.highlightedText}`);
    }
    if (result.matches.length > 3) {
      lines.push(`   ... y ${result.matches.length - 3} coincidencias m\xE1s`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

// src/commands/chat.ts
var chatCommand = new Command2("chat").description("Iniciar sesi\xF3n de chat interactivo").option("-s, --session <id>", "Continuar una sesi\xF3n existente").option("-m, --model <model>", "Modelo a utilizar").option("-n, --new", "Crear nueva sesi\xF3n sin preguntar").action(async (options) => {
  const config = loadConfig();
  const opencodeReady = await ensureOpencodeRunning(config.opencode);
  if (!opencodeReady) {
    console.log(chalk3.red("\u2717 No se pudo conectar a OpenCode. Saliendo."));
    process.exit(1);
  }
  let session;
  if (options.session) {
    const loaded = loadSession(options.session);
    if (!loaded) {
      console.log(chalk3.red(`\u2717 Sesi\xF3n "${options.session}" no encontrada.`));
      process.exit(1);
    }
    session = loaded;
    console.log(chalk3.cyan(`
\u{1F4C2} Continuando sesi\xF3n: ${session.name}`));
  } else if (!options.new) {
    const existing = listSessions();
    if (existing.length > 0) {
      const { action } = await inquirer2.prompt([
        {
          type: "list",
          name: "action",
          message: "\xBFQu\xE9 deseas hacer?",
          choices: [
            { name: "Nueva sesi\xF3n", value: "new" },
            ...existing.slice(0, 10).map((s) => ({
              name: `Continuar: ${s.name} (${s.messages.length} mensajes)`,
              value: s.id
            }))
          ]
        }
      ]);
      if (action === "new") {
        session = await createNewSession(options.model || config.opencode.defaultModel);
      } else {
        session = loadSession(action);
        console.log(chalk3.cyan(`
\u{1F4C2} Continuando sesi\xF3n: ${session.name}`));
      }
    } else {
      session = await createNewSession(options.model || config.opencode.defaultModel);
    }
  } else {
    session = await createNewSession(options.model || config.opencode.defaultModel);
  }
  const client = new OpenCodeClient(config.opencode);
  console.log(chalk3.gray("\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"));
  console.log(chalk3.gray(`Modelo: ${session.model}`));
  console.log(chalk3.gray(`Sesi\xF3n: ${session.id.substring(0, 8)}...`));
  console.log(chalk3.gray(`OpenCode: ${config.opencode.baseUrl}`));
  console.log(
    chalk3.gray(
      `Tools: read=${config.tools.allowRead ? "\u2713" : "\u2717"} write=${config.tools.allowWrite ? "\u2713" : "\u2717"} exec=${config.tools.allowExec ? "\u2713" : "\u2717"}`
    )
  );
  const installedSkills = listSkills();
  if (installedSkills.length > 0) {
    console.log(
      chalk3.gray(
        `Skills: ${installedSkills.map((s) => s.name).join(", ")}`
      )
    );
  }
  console.log(
    chalk3.gray(
      "Comandos: /exit /clear /save /model /read /write /exec /skills /find-skill /install-skill /search /export /help"
    )
  );
  console.log(chalk3.gray("\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"));
  if (session.messages.length > 0) {
    session.messages.forEach((msg) => {
      if (msg.role === "user") {
        console.log(chalk3.green("You: ") + msg.content);
      } else {
        console.log(chalk3.blue("Claudy: ") + msg.content + "\n");
      }
    });
  }
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });
  let isStreaming = false;
  let streamController = null;
  rl.on("SIGINT", () => {
    if (isStreaming && streamController) {
      streamController.abort();
      isStreaming = false;
      process.stdout.write("\n");
      console.log(chalk3.yellow("\u26A0 Respuesta interrumpida por el usuario"));
    } else {
      saveSession(session);
      console.log(chalk3.gray("\n\u{1F44B} Sesi\xF3n guardada. \xA1Hasta luego!\n"));
      rl.close();
      process.exit(0);
    }
  });
  while (true) {
    let userInput;
    try {
      userInput = (await rl.question(chalk3.green("You: "))).trim();
    } catch {
      break;
    }
    if (!userInput) continue;
    if (userInput.startsWith("/")) {
      if (userInput.startsWith("/find-skill ")) {
        const query = userInput.slice("/find-skill ".length).trim();
        await handleFindSkill(query, session);
        continue;
      }
      if (userInput.startsWith("/install-skill ")) {
        const query = userInput.slice("/install-skill ".length).trim();
        await handleInstallSkill(query, session);
        continue;
      }
      const result = await handleCommand(userInput, session, config);
      if (result === "exit") break;
      continue;
    }
    const skillIntent = parseSkillIntent(userInput);
    if (skillIntent) {
      addMessage(session, "user", userInput);
      if (skillIntent.action === "install") {
        await handleInstallSkill(skillIntent.query, session);
      } else {
        await handleFindSkill(skillIntent.query, session);
      }
      continue;
    }
    const fileIntent = parseFileIntent(userInput);
    if (fileIntent) {
      addMessage(session, "user", userInput);
      if (fileIntent.action === "download") {
        console.log(chalk3.cyan(`\u2B07 Descargando: ${fileIntent.target}`));
        const dlResult = await downloadFile(fileIntent.target);
        if (dlResult.ok) {
          console.log(chalk3.green(`
${dlResult.message}`));
          if (dlResult.path) {
            console.log(chalk3.gray(`
Para ejecutar: /ejecutar ${dlResult.path}`));
          }
          console.log("");
        } else {
          console.log(chalk3.red(`
\u2717 ${dlResult.message}
`));
        }
      } else if (fileIntent.action === "search-download") {
        console.log(chalk3.cyan(`\u{1F50D} Buscando: "${fileIntent.target}"`));
        const sr = await searchFilesOnline(fileIntent.target);
        if (sr.ok && sr.results) {
          console.log(chalk3.cyan(`
${sr.message}`));
          sr.results.forEach((r, i) => {
            console.log(chalk3.white(`  ${i + 1}. ${r.title}`));
            console.log(chalk3.gray(`     ${r.url}`));
            if (r.snippet) console.log(chalk3.gray(`     ${r.snippet.substring(0, 120)}`));
          });
          console.log(chalk3.gray("\nPara descargar: /download <url>\n"));
        } else {
          console.log(chalk3.yellow(`
${sr.message}
`));
        }
      } else if (fileIntent.action === "execute") {
        const execResult = await executeFile(fileIntent.target);
        if (execResult.ok) {
          console.log(chalk3.green(`
${execResult.message}
`));
        } else {
          console.log(chalk3.red(`
\u2717 ${execResult.message}
`));
        }
      } else if (fileIntent.action === "auto-install") {
        console.log(chalk3.cyan(`\u{1F680} Pipeline: buscar \u2192 descargar \u2192 ejecutar "${fileIntent.target}"
`));
        const installResult = await installApp(fileIntent.target);
        if (installResult.ok) {
          console.log(chalk3.green(installResult.message));
          console.log("");
        } else {
          console.log(chalk3.red(installResult.message));
          console.log("");
        }
      }
      saveSession(session);
      continue;
    }
    addMessage(session, "user", userInput);
    let webContext = "";
    if (shouldSearchWeb(userInput)) {
      const query = extractSearchQuery(userInput);
      if (query.length >= 3) {
        process.stdout.write(chalk3.yellow("\u{1F50D} Buscando en internet..."));
        try {
          const backendUrl = config.claudyBackendUrl || "http://127.0.0.1:3001";
          const results = await searchWeb(query, backendUrl);
          if (results.length > 0) {
            webContext = formatSearchContext(query, results);
            process.stdout.write(
              `\r${chalk3.green("\u2713")} ${chalk3.dim(`${results.length} resultados encontrados`)}` + " ".repeat(20) + "\n"
            );
          } else {
            process.stdout.write(
              `\r${chalk3.yellow("\u26A0")} ${chalk3.dim("Sin resultados web")}` + " ".repeat(20) + "\n"
            );
          }
        } catch {
          process.stdout.write(
            `\r${chalk3.yellow("\u26A0")} ${chalk3.dim("B\xFAsqueda web no disponible")}` + " ".repeat(20) + "\n"
          );
        }
      }
    }
    let receivedTokens = false;
    let charCount = 0;
    const spinnerChars = ["\u280B", "\u2819", "\u2839", "\u2838", "\u283C", "\u2834", "\u2826", "\u2827", "\u2807", "\u280F"];
    let spinnerIdx = 0;
    let startTime = Date.now();
    const spinnerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1e3);
      const label = receivedTokens ? `Generando respuesta... (${charCount} chars)` : `Pensando... (${elapsed}s)`;
      process.stdout.write(`\r${chalk3.cyan(spinnerChars[spinnerIdx++ % spinnerChars.length])} ${label}  `);
    }, 80);
    try {
      const skillsCtx = webContext ? "" : buildSkillsContext(findRelevantSkills(userInput, 2));
      const locationCtx = await (async () => {
        try {
          const { buildLocationContext } = await import("./location-AYOEQ43I.js");
          return await buildLocationContext();
        } catch {
          return "";
        }
      })();
      const sessionSummaryCtx = session.summary ? `Resumen de mensajes anteriores de esta sesi\xF3n (los mensajes originales fueron compactados):
${session.summary}` : "";
      const systemPrompt = [
        config.agent.systemPrompt,
        locationCtx,
        sessionSummaryCtx,
        skillsCtx,
        webContext
      ].filter(Boolean).join("\n\n");
      let reply = "";
      startTime = Date.now();
      streamController = new AbortController();
      const hardTimeout = setTimeout(() => streamController.abort(), 12e4);
      isStreaming = true;
      try {
        let firstToken = true;
        await client.sendMessageStreaming(
          session,
          userInput,
          session.model,
          systemPrompt,
          (token) => {
            if (!receivedTokens) {
              receivedTokens = true;
              clearInterval(spinnerInterval);
              process.stdout.write("\r" + " ".repeat(60) + "\r");
              process.stdout.write(chalk3.blue("Claudy: "));
            }
            reply += token;
            charCount = reply.length;
            process.stdout.write(token);
          },
          streamController.signal
        );
        if (receivedTokens) {
          process.stdout.write("\n");
        }
      } finally {
        clearTimeout(hardTimeout);
        isStreaming = false;
        streamController = null;
      }
      if (!receivedTokens) {
        clearInterval(spinnerInterval);
        process.stdout.write("\r" + " ".repeat(60) + "\r");
      }
      addMessage(session, "assistant", reply);
      saveSession(session);
      if (needsSummarization(session)) {
        console.log(chalk3.dim("\n\u{1F4DD} Sesi\xF3n larga detectada \u2014 generando resumen compacto..."));
        try {
          const summaryPrompt = buildSummarizationPrompt(session);
          let summaryText = "";
          const summaryCtrl = new AbortController();
          const summaryTimeout = setTimeout(() => summaryCtrl.abort(), 6e4);
          await client.sendMessageStreaming(
            session,
            summaryPrompt,
            session.model,
            "Responde solo con el resumen solicitado. No a\xF1adas comentarios.",
            (token) => {
              summaryText += token;
            },
            summaryCtrl.signal
          );
          clearTimeout(summaryTimeout);
          if (summaryText.trim().length > 0) {
            compactSession(session, summaryText.trim());
            saveSession(session);
            console.log(chalk3.dim(`\u2713 Sesi\xF3n compactada: ${session.messages.length} mensajes activos + resumen guardado`));
          }
        } catch (err) {
          console.log(chalk3.dim(`\u26A0 No se pudo generar resumen: ${err.message}`));
        }
      }
      const urls = findSkillUrls(reply);
      for (const url of urls) {
        const { confirm } = await inquirer2.prompt([
          {
            type: "confirm",
            name: "confirm",
            message: `\u{1F50C} Detect\xE9 un skill: ${url}
  \xBFInstalar?`,
            default: true
          }
        ]);
        if (confirm) {
          try {
            const installed = await installSkillFromUrl(url);
            console.log(
              chalk3.green(`\u2713 Skill "${installed.name}" instalado en ${installed.path}
`)
            );
          } catch (err) {
            console.log(chalk3.red(`\u2717 Error instalando: ${err.message}
`));
          }
        }
      }
    } catch (error) {
      clearInterval(spinnerInterval);
      process.stdout.write("\r" + " ".repeat(60) + "\r");
      isStreaming = false;
      streamController = null;
      if (error.name === "AbortError" && !receivedTokens) {
        console.log(chalk3.yellow("\u26A0 Respuesta cancelada") + "\n");
        continue;
      }
      const msg = error.name === "AbortError" ? "Timeout: el modelo tard\xF3 m\xE1s de 120s. Prueba un mensaje m\xE1s corto o cambia de modelo con /model." : error.message;
      console.log(chalk3.red("\u2717 " + msg) + "\n");
    }
  }
  saveSession(session);
  rl.close();
  console.log(chalk3.gray("\n\u{1F44B} Sesi\xF3n guardada. \xA1Hasta luego!\n"));
});
async function createNewSession(model) {
  const { name } = await inquirer2.prompt([
    {
      type: "input",
      name: "name",
      message: "Nombre de la sesi\xF3n (Enter para auto):",
      default: `Chat ${(/* @__PURE__ */ new Date()).toLocaleString()}`
    }
  ]);
  return createSession(name, model);
}
async function handleCommand(command, session, config) {
  const [cmd, ...args] = command.split(" ");
  const rest = args.join(" ");
  switch (cmd) {
    case "/exit":
    case "/quit":
      return "exit";
    case "/clear":
      console.clear();
      return "handled";
    case "/save":
      saveSession(session);
      console.log(chalk3.green("\u2713 Sesi\xF3n guardada"));
      return "handled";
    case "/model":
      if (args.length > 0) {
        session.model = args.join(" ");
        session.opencodeSessionId = void 0;
        saveSession(session);
        console.log(chalk3.green(`\u2713 Modelo cambiado a: ${session.model}`));
      } else {
        console.log(chalk3.gray(`Modelo actual: ${session.model}`));
      }
      return "handled";
    case "/read": {
      if (!rest) {
        console.log(chalk3.yellow("Uso: /read <ruta>"));
        return "handled";
      }
      const result = await toolRead(rest, config.tools);
      if (result.ok) {
        console.log(chalk3.cyan(`
\u{1F4C4} ${rest}:`));
        console.log(chalk3.gray(result.output));
        console.log("");
        addMessage(
          session,
          "user",
          `[Tool /read ${rest}]
\`\`\`
${result.output}
\`\`\``
        );
        saveSession(session);
      } else {
        console.log(chalk3.red(`\u2717 ${result.error}`));
      }
      return "handled";
    }
    case "/write": {
      const newlineIdx = rest.indexOf("\n");
      const filePath = newlineIdx >= 0 ? rest.slice(0, newlineIdx).trim() : rest.trim();
      const content = newlineIdx >= 0 ? rest.slice(newlineIdx + 1) : "";
      if (!filePath) {
        console.log(chalk3.yellow("Uso: /write <ruta>\\n<contenido>"));
        return "handled";
      }
      if (!content) {
        console.log(chalk3.yellow("Sin contenido. Pasa el contenido tras un salto de l\xEDnea."));
        return "handled";
      }
      const result = await toolWrite(filePath, content, config.tools);
      if (result.ok) {
        console.log(chalk3.green(`\u2713 ${result.output}`));
        addMessage(session, "user", `[Tool /write ${filePath}] ${result.output}`);
        saveSession(session);
      } else {
        console.log(chalk3.red(`\u2717 ${result.error}`));
      }
      return "handled";
    }
    case "/exec": {
      if (!rest) {
        console.log(chalk3.yellow("Uso: /exec <comando>"));
        return "handled";
      }
      const result = await toolExec(rest, config.tools);
      if (result.ok) {
        console.log(chalk3.cyan(`
\u25B6 ${rest}`));
        console.log(chalk3.gray(result.output));
        console.log("");
        addMessage(
          session,
          "user",
          `[Tool /exec ${rest}]
\`\`\`
${result.output}
\`\`\``
        );
        saveSession(session);
      } else {
        console.log(chalk3.red(`\u2717 ${result.error}`));
        if (result.output) console.log(chalk3.gray(result.output));
      }
      return "handled";
    }
    case "/skills": {
      const skills = listSkills();
      if (skills.length === 0) {
        console.log(chalk3.gray("\nNo hay skills instalados."));
        console.log(chalk3.gray("Instala con: claudy skills install <url>\n"));
      } else {
        console.log(chalk3.cyan(`
\u{1F4DA} Skills (${skills.length}):`));
        skills.forEach((s) => console.log(chalk3.gray(`  \u2022 ${s.name} \u2014 ${s.description}`)));
        console.log("");
      }
      return "handled";
    }
    case "/tools":
      console.log(chalk3.cyan("\nEstado de tools:"));
      console.log(`  enabled:    ${tick(config.tools.enabled)}`);
      console.log(`  read:       ${tick(config.tools.allowRead)}`);
      console.log(`  write:      ${tick(config.tools.allowWrite)}`);
      console.log(`  exec:       ${tick(config.tools.allowExec)}`);
      console.log(`  root:       ${chalk3.gray(config.tools.allowedRoot)}`);
      console.log(`  timeout:    ${chalk3.gray(config.tools.commandTimeoutMs + "ms")}`);
      console.log(chalk3.gray("\nCambia con: claudy config set tools.allowWrite true\n"));
      return "handled";
    case "/history":
      console.log(chalk3.gray(`
Mensajes: ${session.messages.length}`));
      console.log(chalk3.gray(`OpenCode session: ${session.opencodeSessionId || "(no creada)"}
`));
      return "handled";
    case "/download":
    case "/descargar": {
      if (!rest) {
        console.log(chalk3.yellow("Uso: /download <url>  o  /descargar <url>"));
        return "handled";
      }
      console.log(chalk3.cyan(`\u2B07 Descargando: ${rest}`));
      const dlResult = await downloadFile(rest);
      if (dlResult.ok) {
        console.log(chalk3.green(`
${dlResult.message}`));
        if (dlResult.path) {
          console.log(chalk3.gray(`
Para ejecutar: /ejecutar ${dlResult.path}`));
        }
        console.log("");
      } else {
        console.log(chalk3.red(`
\u2717 ${dlResult.message}
`));
      }
      return "handled";
    }
    case "/buscar": {
      if (!rest) {
        console.log(chalk3.yellow("Uso: /buscar <qu\xE9 archivo buscas>"));
        return "handled";
      }
      console.log(chalk3.cyan(`\u{1F50D} Buscando archivos: "${rest}"`));
      const sr = await searchFilesOnline(rest);
      if (sr.ok && sr.results) {
        console.log(chalk3.cyan(`
${sr.message}`));
        sr.results.forEach((r, i) => {
          console.log(chalk3.white(`  ${i + 1}. ${r.title}`));
          console.log(chalk3.gray(`     ${r.url}`));
          if (r.snippet) console.log(chalk3.gray(`     ${r.snippet.substring(0, 120)}`));
        });
        console.log(chalk3.gray("\nPara descargar: /download <url>\n"));
      } else {
        console.log(chalk3.yellow(`
${sr.message}
`));
      }
      return "handled";
    }
    case "/ejecutar": {
      if (!rest) {
        console.log(chalk3.yellow("Uso: /ejecutar <ruta del archivo>"));
        return "handled";
      }
      const execResult = await executeFile(rest);
      if (execResult.ok) {
        console.log(chalk3.green(`
${execResult.message}
`));
      } else {
        console.log(chalk3.red(`
\u2717 ${execResult.message}
`));
      }
      return "handled";
    }
    case "/instalar":
    case "/install": {
      if (!rest) {
        console.log(chalk3.yellow("Uso: /instalar <nombre de la app>\nEj: /instalar winrar"));
        return "handled";
      }
      console.log(chalk3.cyan(`\u{1F680} Pipeline autom\xE1tico: buscar \u2192 descargar \u2192 ejecutar
`));
      const installResult = await installApp(rest);
      if (installResult.ok) {
        console.log(chalk3.green(installResult.message));
        console.log("");
      } else {
        console.log(chalk3.red(installResult.message));
        console.log("");
      }
      return "handled";
    }
    case "/search":
    case "/buscar-sesion": {
      if (!rest) {
        console.log(chalk3.yellow("Uso: /search <texto>  o  /buscar-sesion <texto>"));
        console.log(chalk3.gray("Busca en todas las sesiones por nombre y contenido de mensajes."));
        return "handled";
      }
      const results = searchSessions(rest);
      console.log(formatSearchResults(results, rest));
      return "handled";
    }
    case "/export": {
      if (!rest) {
        console.log(chalk3.yellow(`Uso: /export <formato> [ruta]`));
        console.log(chalk3.gray(getSupportedFormats()));
        console.log(chalk3.gray("Ej: /export md, /export html, /export txt, /export pdf"));
        return "handled";
      }
      const [format, ...pathParts] = rest.split(" ");
      const validFormats = ["md", "html", "txt", "pdf"];
      if (!validFormats.includes(format)) {
        console.log(chalk3.red(`\u2717 Formato "${format}" no v\xE1lido.`));
        console.log(chalk3.gray(getSupportedFormats()));
        return "handled";
      }
      const outputDir = pathParts.join(" ") || void 0;
      try {
        const filename = exportChat(session.messages, session.name, format, outputDir);
        console.log(chalk3.green(`\u2713 Chat exportado a: ${filename}`));
        addMessage(session, "user", `[Tool /export ${format}] Exportado a ${filename}`);
        saveSession(session);
      } catch (err) {
        console.log(chalk3.red(`\u2717 Error exportando: ${err.message}`));
      }
      return "handled";
    }
    case "/memory": {
      const subCmd = args[0];
      const restArgs = args.slice(1).join(" ");
      if (!subCmd || subCmd === "help") {
        console.log(chalk3.cyan("\nComandos de memoria:"));
        console.log(chalk3.gray("  /memory save <texto>        - Guardar nota en memoria"));
        console.log(chalk3.gray("  /memory search <query>      - Buscar en memoria"));
        console.log(chalk3.gray("  /memory list [n]            - Listar \xFAltimas n memorias (default 20)"));
        console.log(chalk3.gray("  /memory delete <id>         - Eliminar memoria por ID"));
        console.log(chalk3.gray("  /memory archive [dias]      - Archivar memorias antiguas (default 7 d\xEDas)"));
        console.log(chalk3.gray("  /memory help                - Esta ayuda\n"));
        return "handled";
      }
      if (subCmd === "save") {
        if (!restArgs) {
          console.log(chalk3.yellow("Uso: /memory save <texto a recordar>"));
          return "handled";
        }
        const entry = addMemory(restArgs, [], session.id);
        console.log(chalk3.green(`\u2713 Memoria guardada (ID: ${entry.id.substring(0, 12)}...)`));
        addMessage(session, "user", `[Memory saved] ${restArgs}`);
        saveSession(session);
        return "handled";
      }
      if (subCmd === "search") {
        if (!restArgs) {
          console.log(chalk3.yellow("Uso: /memory search <query>"));
          return "handled";
        }
        const results = searchMemories(restArgs, 10);
        if (results.length === 0) {
          console.log(chalk3.gray("\nNo se encontraron memorias."));
        } else {
          console.log(chalk3.cyan(`
\u{1F9E0} Memorias (${results.length}):`));
          results.forEach((m) => {
            console.log(chalk3.gray(`  [${m.id.substring(0, 12)}] ${m.content.substring(0, 100)}${m.content.length > 100 ? "..." : ""}`));
            console.log(chalk3.gray(`    ${new Date(m.timestamp).toLocaleString()}`));
          });
          console.log("");
        }
        return "handled";
      }
      if (subCmd === "list") {
        const limit = parseInt(restArgs) || 20;
        const results = listMemories(limit);
        if (results.length === 0) {
          console.log(chalk3.gray("\nNo hay memorias guardadas."));
        } else {
          console.log(chalk3.cyan(`
\u{1F4DA} Memorias recientes (${results.length}):`));
          results.forEach((m) => {
            console.log(chalk3.gray(`  [${m.id.substring(0, 12)}] ${m.content.substring(0, 100)}${m.content.length > 100 ? "..." : ""}`));
            console.log(chalk3.gray(`    ${new Date(m.timestamp).toLocaleString()}`));
          });
          console.log("");
        }
        return "handled";
      }
      if (subCmd === "delete") {
        if (!restArgs) {
          console.log(chalk3.yellow("Uso: /memory delete <id>"));
          return "handled";
        }
        const deleted = deleteMemory(restArgs);
        if (deleted) {
          console.log(chalk3.green("\u2713 Memoria eliminada."));
        } else {
          console.log(chalk3.yellow("\u26A0 No se encontr\xF3 esa memoria."));
        }
        return "handled";
      }
      if (subCmd === "archive") {
        const days = parseInt(restArgs) || 7;
        const archived = archiveOldMemories(days);
        console.log(chalk3.green(`\u2713 ${archived} memorias archivadas (> ${days} d\xEDas).`));
        return "handled";
      }
      console.log(chalk3.yellow(`Subcomando desconocido: ${subCmd}. Usa /memory help`));
      return "handled";
    }
    case "/help":
      console.log(chalk3.cyan("\nComandos disponibles:"));
      console.log(chalk3.gray("  /exit                       - Salir"));
      console.log(chalk3.gray("  /clear                      - Limpiar pantalla"));
      console.log(chalk3.gray("  /save                       - Guardar sesi\xF3n"));
      console.log(chalk3.gray("  /model <m>                  - Cambiar modelo"));
      console.log(chalk3.gray("  /read <ruta>                - Leer archivo (lo a\xF1ade al contexto)"));
      console.log(chalk3.gray("  /write <ruta>\\n<contenido>  - Escribir archivo"));
      console.log(chalk3.gray("  /exec <comando>             - Ejecutar shell command"));
      console.log(chalk3.gray("  /download <url>             - Descargar archivo de internet"));
      console.log(chalk3.gray("  /buscar <tema>              - Buscar archivos para descargar"));
      console.log(chalk3.gray("  /ejecutar <ruta>            - Abrir/ejecutar un archivo"));
      console.log(chalk3.gray("  /instalar <app>             - Pipeline: buscar\u2192descargar\u2192ejecutar"));
      console.log(chalk3.gray("  /find-skill <tema>          - Buscar skills en internet"));
      console.log(chalk3.gray("  /install-skill <tema>       - Instalar el mejor skill encontrado"));
      console.log(chalk3.gray("  /tools                      - Ver estado de tools"));
      console.log(chalk3.gray("  /history                    - Info de sesi\xF3n"));
      console.log(chalk3.gray("  /search <texto>             - Buscar en sesiones pasadas"));
      console.log(chalk3.gray("  /export <formato>           - Exportar chat (md, html, txt, pdf)"));
      console.log(chalk3.gray("  /memory                     - Gestionar memoria vectorial"));
      console.log(chalk3.gray("  /help                       - Esta ayuda\n"));
      return "handled";
    default:
      console.log(chalk3.yellow(`Comando desconocido: ${cmd}. Usa /help`));
      return "handled";
  }
}
function tick(value) {
  return value ? chalk3.green("\u2713") : chalk3.red("\u2717");
}
async function handleFindSkill(query, session) {
  if (!query.trim()) {
    return;
  }
  process.stdout.write(chalk3.cyan("Buscando skills..."));
  try {
    const skills = await searchRemoteSkills(query, 5);
    process.stdout.write("\r" + " ".repeat(24) + "\r");
    if (skills.length === 0) {
      const message2 = `No encontre skills en internet para "${query}".`;
      console.log(chalk3.blue("Claudy: ") + message2 + "\n");
      addMessage(session, "assistant", message2);
      saveSession(session);
      return;
    }
    const message = [
      `Encontre estos skills en internet para "${query}":`,
      ...skills.map(
        (skill, index) => `${index + 1}. ${skill.name} (${skill.source}/${skill.skillId}) - ${skill.installs || 0} installs`
      ),
      "",
      `Para instalar el mejor resultado: /install-skill ${query}`
    ].join("\n");
    console.log(chalk3.blue("Claudy: ") + message + "\n");
    addMessage(session, "assistant", message);
    saveSession(session);
  } catch (error) {
    process.stdout.write("\r" + " ".repeat(24) + "\r");
    const message = `No pude buscar skills: ${error.message || String(error)}`;
    console.log(chalk3.red("Error: ") + message + "\n");
    addMessage(session, "assistant", message);
    saveSession(session);
  }
}
async function handleInstallSkill(query, session) {
  if (!query.trim()) {
    return;
  }
  process.stdout.write(chalk3.cyan("Buscando e instalando skill..."));
  try {
    const result = await installBestSkillForQuery(query);
    process.stdout.write("\r" + " ".repeat(36) + "\r");
    const alternatives = result.candidates.filter((candidate) => candidate.id !== result.remote.id).slice(0, 3).map(
      (candidate) => `- ${candidate.name} (${candidate.source}/${candidate.skillId}, ${candidate.installs || 0} installs)`
    );
    const message = [
      `Skill instalado: ${result.installed.name}`,
      `Fuente: ${result.remote.source}/${result.remote.skillId}`,
      `Installs reportados: ${result.remote.installs || 0}`,
      `Archivo: ${result.installed.path}`,
      `README actualizado: ${result.installed.readmePath}`,
      "",
      "Ya queda disponible para futuras respuestas de Claudy cuando el mensaje sea relevante.",
      alternatives.length ? "\nOtros candidatos considerados:\n" + alternatives.join("\n") : ""
    ].filter(Boolean).join("\n");
    console.log(chalk3.blue("Claudy: ") + message + "\n");
    addMessage(session, "assistant", message);
    saveSession(session);
  } catch (error) {
    process.stdout.write("\r" + " ".repeat(36) + "\r");
    const message = `No pude instalar la skill: ${error.message || String(error)}`;
    console.log(chalk3.red("Error: ") + message + "\n");
    addMessage(session, "assistant", message);
    saveSession(session);
  }
}

// src/commands/config.ts
import { Command as Command3 } from "commander";
import chalk4 from "chalk";
import inquirer3 from "inquirer";
var configCommand = new Command3("config").description("Gestionar configuraci\xF3n");
configCommand.command("get").description("Ver configuraci\xF3n actual").option("-k, --key <key>", "Obtener un valor espec\xEDfico").action((options) => {
  const config = loadConfig();
  if (options.key) {
    const keys = options.key.split(".");
    let value = config;
    for (const k of keys) {
      value = value?.[k];
    }
    console.log(value ?? chalk4.red("No encontrado"));
    return;
  }
  console.log(chalk4.cyan.bold("\n\u2699\uFE0F  Configuraci\xF3n actual:\n"));
  console.log(chalk4.gray("Archivo: ") + getConfigPath());
  console.log("");
  console.log(chalk4.cyan("OpenCode:"));
  console.log(`  baseUrl: ${chalk4.yellow(config.opencode.baseUrl)}`);
  console.log(`  defaultModel: ${chalk4.yellow(config.opencode.defaultModel)}`);
  console.log(`  apiKey: ${config.opencode.apiKey ? chalk4.green("***configurada***") : chalk4.gray("(none)")}`);
  console.log(`  username: ${chalk4.gray(config.opencode.username || "(none)")}`);
  console.log(`  password: ${config.opencode.password ? chalk4.green("***configurada***") : chalk4.gray("(no auth)")}`);
  console.log("");
  console.log(chalk4.cyan("Agent:"));
  console.log(`  systemPrompt: ${chalk4.gray(config.agent.systemPrompt.substring(0, 60))}...`);
  console.log(`  maxTokens: ${chalk4.yellow(config.agent.maxTokens)}`);
  console.log(`  temperature: ${chalk4.yellow(config.agent.temperature)}`);
  console.log("");
  console.log(chalk4.cyan("Tools:"));
  console.log(`  enabled:    ${config.tools.enabled ? chalk4.green("\u2713") : chalk4.red("\u2717")}`);
  console.log(`  allowRead:  ${config.tools.allowRead ? chalk4.green("\u2713") : chalk4.red("\u2717")}`);
  console.log(`  allowWrite: ${config.tools.allowWrite ? chalk4.green("\u2713") : chalk4.red("\u2717")}`);
  console.log(`  allowExec:  ${config.tools.allowExec ? chalk4.green("\u2713") : chalk4.red("\u2717")}`);
  console.log(`  allowedRoot: ${chalk4.gray(config.tools.allowedRoot)}`);
  console.log(`  timeout:    ${chalk4.yellow(config.tools.commandTimeoutMs + "ms")}`);
  console.log("");
});
configCommand.command("set").description("Establecer un valor de configuraci\xF3n").argument("<key>", "Clave (ej: agent.temperature, opencode.baseUrl)").argument("<value>", "Valor").action((key, value) => {
  const config = loadConfig();
  const keys = key.split(".");
  let parsedValue = value;
  if (value === "true") parsedValue = true;
  else if (value === "false") parsedValue = false;
  else if (!isNaN(Number(value))) parsedValue = Number(value);
  let current = config;
  for (let i = 0; i < keys.length - 1; i++) {
    if (!current[keys[i]]) current[keys[i]] = {};
    current = current[keys[i]];
  }
  current[keys[keys.length - 1]] = parsedValue;
  saveConfig(config);
  console.log(chalk4.green(`\u2713 ${key} = ${parsedValue}`));
});
configCommand.command("edit").description("Editar configuraci\xF3n interactivamente").action(async () => {
  const config = loadConfig();
  const answers = await inquirer3.prompt([
    {
      type: "input",
      name: "baseUrl",
      message: "OpenCode URL:",
      default: config.opencode.baseUrl
    },
    {
      type: "input",
      name: "defaultModel",
      message: "Modelo predeterminado:",
      default: config.opencode.defaultModel
    },
    {
      type: "input",
      name: "systemPrompt",
      message: "System prompt:",
      default: config.agent.systemPrompt
    },
    {
      type: "number",
      name: "temperature",
      message: "Temperatura:",
      default: config.agent.temperature
    },
    {
      type: "number",
      name: "maxTokens",
      message: "M\xE1ximo de tokens:",
      default: config.agent.maxTokens
    }
  ]);
  config.opencode.baseUrl = answers.baseUrl;
  config.opencode.defaultModel = answers.defaultModel;
  config.agent.systemPrompt = answers.systemPrompt;
  config.agent.temperature = answers.temperature;
  config.agent.maxTokens = answers.maxTokens;
  saveConfig(config);
  console.log(chalk4.green("\n\u2713 Configuraci\xF3n actualizada\n"));
});
configCommand.command("path").description("Mostrar ruta del archivo de configuraci\xF3n").action(() => {
  console.log(getConfigPath());
});

// src/commands/sessions.ts
import { Command as Command4 } from "commander";
import chalk5 from "chalk";
import inquirer4 from "inquirer";
var sessionsCommand = new Command4("sessions").description("Gestionar sesiones de chat");
sessionsCommand.command("list").alias("ls").description("Listar todas las sesiones").action(() => {
  const sessions = listSessions();
  if (sessions.length === 0) {
    console.log(chalk5.gray("\nNo tienes sesiones guardadas.\n"));
    console.log(chalk5.cyan("Crea una con: ") + chalk5.yellow("claudy chat\n"));
    return;
  }
  console.log(chalk5.cyan.bold(`
\u{1F4CB} Sesiones (${sessions.length}):
`));
  sessions.forEach((session) => {
    console.log(chalk5.yellow(`\u25B8 ${session.id.substring(0, 8)}`));
    console.log(`  ${chalk5.bold(session.name)}`);
    console.log(chalk5.gray(`  Modelo: ${session.model}`));
    console.log(chalk5.gray(`  Mensajes: ${session.messages.length}`));
    console.log(chalk5.gray(`  Actualizada: ${formatDate(session.updatedAt)}`));
    console.log("");
  });
});
sessionsCommand.command("show <id>").description("Mostrar contenido de una sesi\xF3n").action((id) => {
  const sessions = listSessions();
  const session = sessions.find((s) => s.id.startsWith(id)) || loadSession(id);
  if (!session) {
    console.log(chalk5.red(`\u2717 Sesi\xF3n "${id}" no encontrada.`));
    process.exit(1);
  }
  console.log(chalk5.cyan.bold(`
\u{1F4AC} ${session.name}
`));
  console.log(chalk5.gray(`ID: ${session.id}`));
  console.log(chalk5.gray(`Modelo: ${session.model}`));
  console.log(chalk5.gray(`Creada: ${formatDate(session.createdAt)}`));
  console.log(chalk5.gray(`Mensajes: ${session.messages.length}
`));
  console.log(chalk5.gray("\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"));
  session.messages.forEach((msg) => {
    const prefix = msg.role === "user" ? chalk5.green("You:") : chalk5.blue("Claudy:");
    console.log(`${prefix} ${msg.content}
`);
  });
});
sessionsCommand.command("delete <id>").alias("rm").description("Eliminar una sesi\xF3n").option("-f, --force", "No pedir confirmaci\xF3n").action(async (id, options) => {
  const sessions = listSessions();
  const session = sessions.find((s) => s.id.startsWith(id));
  if (!session) {
    console.log(chalk5.red(`\u2717 Sesi\xF3n "${id}" no encontrada.`));
    process.exit(1);
  }
  if (!options.force) {
    const { confirm } = await inquirer4.prompt([
      {
        type: "confirm",
        name: "confirm",
        message: `\xBFEliminar sesi\xF3n "${session.name}"?`,
        default: false
      }
    ]);
    if (!confirm) {
      console.log(chalk5.gray("Cancelado."));
      return;
    }
  }
  if (deleteSession(session.id)) {
    console.log(chalk5.green(`\u2713 Sesi\xF3n "${session.name}" eliminada.`));
  } else {
    console.log(chalk5.red("\u2717 No se pudo eliminar."));
  }
});
sessionsCommand.command("export <id>").description("Exportar sesi\xF3n a markdown").option("-o, --output <file>", "Archivo de salida").action((id, options) => {
  const sessions = listSessions();
  const session = sessions.find((s) => s.id.startsWith(id)) || loadSession(id);
  if (!session) {
    console.log(chalk5.red(`\u2717 Sesi\xF3n "${id}" no encontrada.`));
    process.exit(1);
  }
  let markdown = `# ${session.name}

`;
  markdown += `- **ID**: ${session.id}
`;
  markdown += `- **Modelo**: ${session.model}
`;
  markdown += `- **Creada**: ${formatDate(session.createdAt)}
`;
  markdown += `- **Mensajes**: ${session.messages.length}

`;
  markdown += "---\n\n";
  session.messages.forEach((msg) => {
    const role = msg.role === "user" ? "**You**" : "**Claudy**";
    markdown += `### ${role}

${msg.content}

`;
  });
  if (options.output) {
    const fs8 = __require("fs");
    fs8.writeFileSync(options.output, markdown, "utf-8");
    console.log(chalk5.green(`\u2713 Exportado a: ${options.output}`));
  } else {
    console.log(markdown);
  }
});

// src/commands/models.ts
import { Command as Command5 } from "commander";
import chalk6 from "chalk";
import ora2 from "ora";
var modelsCommand = new Command5("models").description("Gestionar modelos LLM");
modelsCommand.command("list").alias("ls").description("Listar modelos disponibles en OpenCode").option("-s, --search <query>", "Filtrar por texto").option("-l, --limit <n>", "Limitar resultados", "50").action(async (options) => {
  const config = loadConfig();
  const spinner = ora2("Obteniendo modelos desde OpenCode...").start();
  try {
    const client = new OpenCodeClient(config.opencode);
    let models = await client.listModels();
    if (options.search) {
      const query = options.search.toLowerCase();
      models = models.filter(
        (m) => m.id.toLowerCase().includes(query) || m.name.toLowerCase().includes(query)
      );
    }
    const limit = parseInt(options.limit);
    const limited = models.slice(0, limit);
    spinner.succeed(chalk6.green(`${models.length} modelos encontrados`));
    if (models.length === 0) {
      console.log(chalk6.yellow("\nNo hay modelos. Aseg\xFArate de:"));
      console.log(chalk6.gray("  1. Tener OpenCode corriendo"));
      console.log(chalk6.gray("  2. Haber configurado al menos un provider"));
      return;
    }
    console.log("");
    limited.forEach((model) => {
      const isDefault = model.id === config.opencode.defaultModel;
      const marker = isDefault ? chalk6.green(" \u2605") : "";
      console.log(chalk6.yellow(`\u25B8 ${model.id}${marker}`));
      console.log(chalk6.gray(`  ${model.name}`));
      if (model.description) {
        const desc = model.description.substring(0, 100);
        console.log(chalk6.gray(`  ${desc}${model.description.length > 100 ? "..." : ""}`));
      }
      if (model.context_length) {
        console.log(chalk6.gray(`  Context: ${model.context_length.toLocaleString()} tokens`));
      }
      console.log("");
    });
    if (models.length > limit) {
      console.log(chalk6.gray(`... y ${models.length - limit} m\xE1s. Usa --limit.
`));
    }
  } catch (error) {
    spinner.fail(chalk6.red("Error: " + error.message));
    process.exit(1);
  }
});
modelsCommand.command("current").description("Mostrar modelo actual").action(() => {
  const config = loadConfig();
  console.log(chalk6.cyan("Modelo actual: ") + chalk6.yellow(config.opencode.defaultModel));
  console.log(chalk6.cyan("OpenCode URL:  ") + chalk6.yellow(config.opencode.baseUrl));
});
modelsCommand.command("set <model>").description("Establecer modelo predeterminado").action((model) => {
  const config = loadConfig();
  if (!model.includes("/")) {
    console.log(chalk6.red("\u2717 Formato inv\xE1lido. Usa: provider/model"));
    process.exit(1);
  }
  config.opencode.defaultModel = model;
  saveConfig(config);
  console.log(chalk6.green(`\u2713 Modelo predeterminado: ${model}`));
});

// src/commands/skills.ts
import { Command as Command6 } from "commander";
import chalk7 from "chalk";
import inquirer5 from "inquirer";
import { exec as exec3 } from "child_process";
import { promisify as promisify3 } from "util";
import path7 from "path";
import fs7 from "fs";
var execAsync2 = promisify3(exec3);
var skillsCommand = new Command6("skills").description("Gestionar skills");
function githubBlobToRaw2(url) {
  return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/");
}
skillsCommand.command("list").alias("ls").description("Listar skills instalados").action(() => {
  const skills = listSkills();
  if (skills.length === 0) {
    console.log(chalk7.gray("\nNo tienes skills instalados.\n"));
    console.log(chalk7.cyan("Instala uno con:"));
    console.log(chalk7.gray("  claudy skills install <url-a-SKILL.md>"));
    console.log(chalk7.gray("  claudy skills install-uipro    # UI/UX Pro Max\n"));
    return;
  }
  console.log(chalk7.cyan.bold(`
\u{1F4DA} Skills instalados (${skills.length}):
`));
  skills.forEach((s) => {
    console.log(chalk7.yellow(`\u25B8 ${s.name}`));
    console.log(chalk7.gray(`  ${s.description}`));
    console.log(chalk7.gray(`  ${s.path}
`));
  });
});
skillsCommand.command("install <url>").description("Instalar skill desde URL de SKILL.md (raw o blob)").option("-n, --name <name>", "Nombre del skill (default: derivado de URL)").action(async (url, options) => {
  const rawUrl = githubBlobToRaw2(url);
  console.log(chalk7.cyan(`Descargando ${rawUrl}...`));
  try {
    const res = await fetch(rawUrl);
    if (!res.ok) {
      console.log(chalk7.red(`\u2717 Error ${res.status}: ${res.statusText}`));
      process.exit(1);
    }
    const content = await res.text();
    const name = options.name || path7.basename(rawUrl, ".md").replace(/SKILL/i, "").replace(/^[-_]+|[-_]+$/g, "") || "skill-" + Date.now().toString(36);
    const filePath = saveSkillFromContent(name, content);
    console.log(chalk7.green(`\u2713 Skill "${name}" instalado en:`));
    console.log(chalk7.gray(`  ${filePath}
`));
  } catch (err) {
    console.log(chalk7.red("\u2717 Error: " + err.message));
    process.exit(1);
  }
});
skillsCommand.command("install-uipro").description("Instalar UI/UX Pro Max skill (v\xEDa npx uipro-cli)").action(async () => {
  const skillsDir = getSkillsDir();
  const tmpDir = path7.join(skillsDir, "_uipro_tmp");
  fs7.mkdirSync(tmpDir, { recursive: true });
  console.log(chalk7.cyan("\u{1F3A8} Instalando UI/UX Pro Max via uipro-cli..."));
  console.log(chalk7.gray("   Ejecutando: npx uipro-cli init --ai opencode\n"));
  try {
    const { stdout, stderr } = await execAsync2(
      "npx -y uipro-cli init --ai opencode",
      { cwd: tmpDir, timeout: 12e4 }
    );
    console.log(chalk7.gray(stdout));
    if (stderr) console.log(chalk7.gray(stderr));
    const generatedPath = path7.join(
      tmpDir,
      ".opencode",
      "skills",
      "ui-ux-pro-max",
      "SKILL.md"
    );
    if (!fs7.existsSync(generatedPath)) {
      console.log(
        chalk7.yellow(
          `\u26A0 No se encontr\xF3 SKILL.md generado en ${generatedPath}.
  Puede que el comando haya cambiado de path.`
        )
      );
      return;
    }
    const content = fs7.readFileSync(generatedPath, "utf-8");
    const filePath = saveSkillFromContent("ui-ux-pro-max", content);
    const sourceDir = path7.dirname(generatedPath);
    const targetDir = path7.dirname(filePath);
    for (const sub of ["scripts", "data"]) {
      const src = path7.join(sourceDir, sub);
      const dst = path7.join(targetDir, sub);
      if (fs7.existsSync(src)) {
        fs7.cpSync(src, dst, { recursive: true });
      }
    }
    fs7.rmSync(tmpDir, { recursive: true, force: true });
    console.log(chalk7.green(`
\u2713 Skill "ui-ux-pro-max" instalado`));
    console.log(chalk7.gray(`  ${filePath}`));
    console.log(chalk7.cyan("\n\xDAsalo en chat:"));
    console.log(chalk7.gray("  claudy chat"));
    console.log(
      chalk7.gray("  > dise\xF1a una landing con UI moderna estilo glassmorphism\n")
    );
  } catch (err) {
    console.log(chalk7.red("\u2717 Error: " + err.message));
    console.log(
      chalk7.yellow(
        "\nAseg\xFArate de tener Node.js + npm. Si falla npx, intenta:\n  npm install -g uipro-cli\n  uipro-cli init --ai opencode"
      )
    );
  }
});
skillsCommand.command("remove <name>").alias("rm").description("Eliminar un skill").option("-f, --force", "Sin confirmaci\xF3n").action(async (name, options) => {
  if (!options.force) {
    const { confirm } = await inquirer5.prompt([
      {
        type: "confirm",
        name: "confirm",
        message: `\xBFEliminar skill "${name}"?`,
        default: false
      }
    ]);
    if (!confirm) {
      console.log(chalk7.gray("Cancelado."));
      return;
    }
  }
  const removed = await removeSkill(name);
  if (removed) {
    console.log(chalk7.green(`\u2713 Skill "${name}" eliminado`));
  } else {
    console.log(chalk7.red(`\u2717 Skill "${name}" no encontrado`));
  }
});
skillsCommand.command("show <name>").description("Ver el contenido de un skill").action((name) => {
  const skill = listSkills().find((s) => s.name === name);
  if (!skill) {
    console.log(chalk7.red(`\u2717 Skill "${name}" no encontrado`));
    process.exit(1);
  }
  console.log(chalk7.cyan.bold(`
\u{1F4DA} ${skill.name}
`));
  console.log(chalk7.gray(skill.description));
  console.log(chalk7.gray("\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"));
  console.log(skill.content);
});

// src/cli.ts
var program = new Command7();
program.name("claudy").description("Personal AI Assistant CLI").version("0.1.0");
program.addCommand(setupCommand);
program.addCommand(chatCommand);
program.addCommand(configCommand);
program.addCommand(sessionsCommand);
program.addCommand(modelsCommand);
program.addCommand(skillsCommand);
program.on("--help", () => {
  console.log("");
  console.log("Ejemplos:");
  console.log("  $ claudy setup           # Configurar Claudy por primera vez");
  console.log("  $ claudy chat            # Iniciar sesi\xF3n de chat interactivo");
  console.log("  $ claudy config get      # Ver configuraci\xF3n actual");
  console.log("  $ claudy models list     # Listar modelos disponibles");
  console.log("");
});
program.parse(process.argv);
if (!process.argv.slice(2).length) {
  program.outputHelp();
}
