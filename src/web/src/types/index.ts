// Tipos para la aplicación Claudy Web

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  model?: string
  tokenCount?: number
}

export interface Session {
  id: string
  title: string
  messages: Message[]
  createdAt: Date
  updatedAt: Date
  model: string
  systemPrompt?: string
}

export interface Model {
  id: string
  name: string
  provider: string
  description?: string
  contextWindow?: number
  costPer1kTokens?: {
    input: number
    output: number
  }
}

export interface MemoryItem {
  id: string
  content: string
  embedding: number[]
  relevance: number
  timestamp: Date
}

export interface Tool {
  id: string
  name: string
  description: string
  enabled: boolean
}

export interface Config {
  theme: 'dark' | 'light'
  model: string
  temperature: number
  maxTokens: number
  systemPrompt: string
  tools: {
    read: boolean
    write: boolean
    exec: boolean
  }
}

export interface OpenCodeResponse {
  response: string
  model: string
  tokensUsed: number
  finishReason: string
}
