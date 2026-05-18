export interface Config {
  opencode: {
    baseUrl: string;
    defaultModel: string;
    apiKey?: string;
    username?: string;
    password?: string;
  };
  agent: {
    systemPrompt: string;
    maxTokens: number;
    temperature: number;
  };
  tools: {
    enabled: boolean;
    allowRead: boolean;
    allowWrite: boolean;
    allowExec: boolean;
    allowedRoot: string;
    commandTimeoutMs: number;
    maxOutputChars: number;
  };
  server: {
    port: number;
    host: string;
  };
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface Session {
  id: string;
  name: string;
  model: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
  opencodeSessionId?: string;
  summary?: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  description?: string;
  context_length?: number;
}

export interface OpenCodeTextPart {
  type: 'text';
  text: string;
}

export interface OpenCodeMessageResponse {
  info?: {
    error?: {
      name?: string;
      data?: { message?: string };
    };
  };
  parts?: Array<OpenCodeTextPart | { type: string; [key: string]: unknown }>;
}
