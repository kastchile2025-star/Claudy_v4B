import { Config, ModelInfo, OpenCodeMessageResponse, OpenCodeTextPart, Session } from './types.js';
import { saveSession } from './utils.js';

const DISABLED_TOOLS = {
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
  skill: false,
};

const STALE_SESSION_TIMEOUT_MS = 20_000;

export class OpenCodeClient {
  private baseUrl: string;
  private apiKey?: string;
  private username?: string;
  private password?: string;

  constructor(config: Config['opencode']) {
    this.baseUrl = config.baseUrl;
    this.apiKey = config.apiKey;
    this.username = config.username;
    this.password = config.password;
  }

  private getAuthHeader(): string | undefined {
    if (this.apiKey) return `Bearer ${this.apiKey}`;
    if (!this.password) return undefined;
    const user = this.username || 'opencode';
    return `Basic ${Buffer.from(`${user}:${this.password}`).toString('base64')}`;
  }

  private buildHeaders(extra?: Record<string, string>): Headers {
    const headers = new Headers(extra);
    const auth = this.getAuthHeader();
    if (auth) headers.set('Authorization', auth);
    return headers;
  }

  private resolveUrl(path: string): URL {
    return new URL(path, this.baseUrl.endsWith('/') ? this.baseUrl : `${this.baseUrl}/`);
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const url = this.resolveUrl(path);
    const headers = this.buildHeaders();
    if (init.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    let response: Response;
    try {
      response = await fetch(url, { ...init, headers });
    } catch (error) {
      throw new Error(
        `No pude conectar con OpenCode en ${this.baseUrl}. Inicia OpenCode con "opencode serve --port 4096 --hostname 127.0.0.1". Detalle: ${
          error instanceof Error ? error.message : String(error)
        }`
      );
    }

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`OpenCode error ${response.status}: ${text || response.statusText}`);
    }

    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  private parseModel(model: string): { providerID: string; modelID: string } {
    const trimmed = model.trim();
    if (trimmed.includes('/')) {
      const [providerID, ...modelParts] = trimmed.split('/');
      return { providerID, modelID: modelParts.join('/') };
    }
    return { providerID: '', modelID: trimmed };
  }

  private extractText(response: OpenCodeMessageResponse): string {
    if (response.info?.error) {
      const { name, data } = response.info.error;
      throw new Error(data?.message || name || 'OpenCode devolvio un error');
    }
    const text = response.parts
      ?.filter((p): p is OpenCodeTextPart => p.type === 'text')
      .map((p) => p.text)
      .join('\n')
      .trim();
    return text || '(OpenCode no devolvio texto.)';
  }

  async ensureSession(session: Session): Promise<string> {
    if (session.opencodeSessionId) return session.opencodeSessionId;

    const created = await this.request<{ id: string }>('/session', {
      method: 'POST',
      body: JSON.stringify({ title: session.name }),
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
  async sendMessageStreaming(
    session: Session,
    userMessage: string,
    model: string,
    systemPrompt: string,
    onToken: (token: string) => void,
    abortSignal?: AbortSignal
  ): Promise<string> {
    const parsedModel = this.parseModel(model);
    const sessionId = await this.ensureSession(session);

    const url = this.resolveUrl(`/session/${encodeURIComponent(sessionId)}/message`);
    const headers = this.buildHeaders({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    });

    const body = JSON.stringify({
      model: parsedModel,
      system: systemPrompt,
      tools: DISABLED_TOOLS,
      parts: [{ type: 'text', text: userMessage }],
    });

    let response: Response;
    try {
      response = await fetch(url, { method: 'POST', headers, body, signal: abortSignal });
    } catch (error) {
      throw new Error(
        `No pude conectar con OpenCode en ${this.baseUrl}. Detalle: ${
          error instanceof Error ? error.message : String(error)
        }`
      );
    }

    // Si el servidor no soporta SSE, caer en la respuesta JSON normal
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('text/event-stream')) {
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`OpenCode error ${response.status}: ${text || response.statusText}`);
      }
      const json = (await response.json()) as OpenCodeMessageResponse;
      const fullText = this.extractText(json);
      // Efecto typewriter: emitir el texto carácter a carácter
      await typewriterEffect(fullText, onToken);
      return fullText;
    }

    // Procesar SSE con timeout de 90 segundos por inactividad
    if (!response.body) throw new Error('No se recibio cuerpo de respuesta SSE.');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let accumulated = '';
    const STREAM_TIMEOUT_MS = 90_000;

    while (true) {
      // Race: read vs timeout
      const timeoutPromise = new Promise<{ done: true; value: undefined }>((_, reject) =>
        setTimeout(() => reject(new Error('Timeout: el modelo no respondió en 90 segundos. Intenta con un mensaje más corto o cambia de modelo con /model.')), STREAM_TIMEOUT_MS)
      );

      let result: ReadableStreamReadResult<Uint8Array>;
      try {
        result = await Promise.race([reader.read(), timeoutPromise]);
      } catch (err) {
        reader.cancel();
        throw err;
      }

      const { done, value } = result;
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith(':')) continue; // comentarios SSE

        if (trimmed.startsWith('data:')) {
          const data = trimmed.slice(5).trim();
          if (data === '[DONE]') break;

          try {
            const parsed = JSON.parse(data) as Record<string, unknown>;
            // Manejar distintos formatos de evento SSE de OpenCode
            const token = extractSseToken(parsed);
            if (token) {
              accumulated += token;
              onToken(token);
            }
          } catch {
            // Si no es JSON, puede ser texto plano
            if (data && data !== '[DONE]') {
              accumulated += data;
              onToken(data);
            }
          }
        }
      }
    }

    // Si el streaming no produjo nada, hacer fallback a solicitud normal
    if (!accumulated.trim()) {
      const full = await this.sendMessage(session, userMessage, model, systemPrompt);
      await typewriterEffect(full, onToken);
      return full;
    }

    return accumulated;
  }

  async sendMessage(
    session: Session,
    userMessage: string,
    model: string,
    systemPrompt: string
  ): Promise<string> {
    const parsedModel = this.parseModel(model);

    const send = async (timeoutMs?: number) => {
      const sessionId = await this.ensureSession(session);
      const signal =
        timeoutMs && typeof AbortSignal.timeout === 'function'
          ? AbortSignal.timeout(timeoutMs)
          : undefined;
      return this.request<OpenCodeMessageResponse>(
        `/session/${encodeURIComponent(sessionId)}/message`,
        {
          method: 'POST',
          signal,
          body: JSON.stringify({
            model: parsedModel,
            system: systemPrompt,
            tools: DISABLED_TOOLS,
            parts: [{ type: 'text', text: userMessage }],
          }),
        }
      );
    };

    const hadSession = Boolean(session.opencodeSessionId);
    let response: OpenCodeMessageResponse;
    try {
      response = await send(hadSession ? STALE_SESSION_TIMEOUT_MS : undefined);
    } catch (error) {
      if (!hadSession) throw error;
      session.opencodeSessionId = undefined;
      saveSession(session);
      response = await send();
    }

    return this.extractText(response);
  }

  async listModels(): Promise<ModelInfo[]> {
    interface ProviderModel {
      id?: string;
      name?: string;
      description?: string;
      limit?: { context?: number };
    }
    interface Provider {
      id?: string;
      name?: string;
      models?: Record<string, ProviderModel>;
    }
    interface Resp {
      all?: Provider[];
      providers?: Provider[];
      connected?: string[];
    }

    const response = await this.request<Resp>('/provider');
    const providers = response.all || response.providers || [];
    const connected = response.connected?.length
      ? new Set(response.connected)
      : undefined;

    return providers.flatMap((provider) => {
      const providerID = provider.id;
      if (!providerID || !provider.models) return [];
      if (connected && !connected.has(providerID)) return [];
      return Object.entries(provider.models).map(([modelID, model]) => ({
        id: `${providerID}/${model.id || modelID}`,
        name: `${provider.name || providerID}: ${model.name || model.id || modelID}`,
        description: model.description,
        context_length: model.limit?.context,
      }));
    });
  }

  async testConnection(): Promise<boolean> {
    try {
      await this.request('/provider');
      return true;
    } catch {
      return false;
    }
  }
}

/** Extrae el token de texto de un evento SSE con distintos formatos */
function extractSseToken(data: Record<string, unknown>): string {
  // Formato OpenAI-compatible: choices[0].delta.content
  const choices = data['choices'] as Array<Record<string, unknown>> | undefined;
  if (Array.isArray(choices) && choices.length > 0) {
    const delta = choices[0]['delta'] as Record<string, unknown> | undefined;
    if (delta && typeof delta['content'] === 'string') return delta['content'];
  }

  // Formato Anthropic-compatible: delta.text
  const delta = data['delta'] as Record<string, unknown> | undefined;
  if (delta && typeof delta['text'] === 'string') return delta['text'];

  // Formato OpenCode: parts[].text
  const parts = data['parts'] as Array<Record<string, unknown>> | undefined;
  if (Array.isArray(parts)) {
    return parts
      .filter((p) => p['type'] === 'text' && typeof p['text'] === 'string')
      .map((p) => p['text'] as string)
      .join('');
  }

  // Formato simple: { content: string } o { text: string }
  if (typeof data['content'] === 'string') return data['content'];
  if (typeof data['text'] === 'string') return data['text'];

  return '';
}

/** Simula efecto typewriter para cuando el servidor no soporta SSE */
async function typewriterEffect(text: string, onToken: (t: string) => void): Promise<void> {
  const CHUNK = 4; // caracteres por tick
  const DELAY = 12; // ms entre ticks (~83 chunks/s)

  for (let i = 0; i < text.length; i += CHUNK) {
    onToken(text.slice(i, i + CHUNK));
    if (i + CHUNK < text.length) {
      await new Promise<void>((resolve) => setTimeout(resolve, DELAY));
    }
  }
}
