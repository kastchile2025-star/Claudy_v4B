import { create } from 'zustand'
import { Session, Message, Model, MemoryItem, Config } from '../types'

interface StoreState {
  // Sessions
  sessions: Session[]
  currentSessionId: string | null
  currentSession: Session | null

  // Messages
  messages: Message[]
  isLoading: boolean
  error: string | null

  // Models
  models: Model[]
  selectedModel: Model | null

  // Memory
  memoryItems: MemoryItem[]

  // Config
  config: Config
  theme: 'dark' | 'light'
  showSettings: boolean

  // Actions
  initializeStore: () => void
  createSession: (title: string) => void
  selectSession: (id: string) => void
  deleteSession: (id: string) => void
  addMessage: (message: Message) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setSelectedModel: (model: Model) => void
  updateConfig: (config: Partial<Config>) => void
  toggleTheme: () => void
  toggleSettings: () => void
  loadSessions: () => Promise<void>
  loadModels: () => Promise<void>
}

export const useStore = create<StoreState>((set, get) => ({
  // Initial state
  sessions: [],
  currentSessionId: null,
  currentSession: null,
  messages: [],
  isLoading: false,
  error: null,
  models: [],
  selectedModel: null,
  memoryItems: [],
  config: {
    theme: 'dark',
    model: 'deepseek/deepseek-chat',
    temperature: 0.7,
    maxTokens: 2048,
    systemPrompt: 'Eres Claudy, un asistente IA inteligente. Responde con claridad y precisión.',
    tools: {
      read: true,
      write: false,
      exec: false,
    },
  },
  theme: 'dark',
  showSettings: false,

  // Actions
  initializeStore: async () => {
    try {
      // Cargar config desde localStorage
      const savedConfig = localStorage.getItem('claudy-config')
      if (savedConfig) {
        set((state) => ({
          config: { ...state.config, ...JSON.parse(savedConfig) },
        }))
      }

      // Cargar sesiones
      await get().loadSessions()
      await get().loadModels()
    } catch (err) {
      console.error('Error initializing store:', err)
    }
  },

  createSession: () => {
    const newSession: Session = {
      id: `session-${Date.now()}`,
      title: `Sesión ${new Date().toLocaleDateString()}`,
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
      model: get().selectedModel?.id || 'deepseek/deepseek-chat',
    }

    set((state) => ({
      sessions: [newSession, ...state.sessions],
      currentSessionId: newSession.id,
      currentSession: newSession,
      messages: [],
    }))

    // Guardar en localStorage
    const sessions = get().sessions
    localStorage.setItem('claudy-sessions', JSON.stringify(sessions))
  },

  selectSession: (id: string) => {
    const session = get().sessions.find((s) => s.id === id)
    if (session) {
      set({
        currentSessionId: id,
        currentSession: session,
        messages: session.messages,
      })
    }
  },

  deleteSession: (id: string) => {
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== id),
      currentSessionId: state.currentSessionId === id ? null : state.currentSessionId,
      currentSession: state.currentSessionId === id ? null : state.currentSession,
    }))

    const sessions = get().sessions
    localStorage.setItem('claudy-sessions', JSON.stringify(sessions))
  },

  addMessage: (message: Message) => {
    set((state) => ({
      messages: [...state.messages, message],
      currentSession: state.currentSession
        ? {
            ...state.currentSession,
            messages: [...state.currentSession.messages, message],
            updatedAt: new Date(),
          }
        : null,
    }))

    // Guardar sesión actualizada
    const sessions = get().sessions.map((s) =>
      s.id === get().currentSessionId ? get().currentSession! : s
    )
    localStorage.setItem('claudy-sessions', JSON.stringify(sessions))
  },

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  setSelectedModel: (model) => set({ selectedModel: model }),

  updateConfig: (newConfig) => {
    set((state) => {
      const updated = { ...state.config, ...newConfig }
      localStorage.setItem('claudy-config', JSON.stringify(updated))
      return { config: updated }
    })
  },

  toggleTheme: () => {
    set((state) => ({
      theme: state.theme === 'dark' ? 'light' : 'dark',
    }))
  },

  toggleSettings: () => {
    set((state) => ({ showSettings: !state.showSettings }))
  },

  loadSessions: async () => {
    try {
      // Primero intentar cargar desde localStorage
      const saved = localStorage.getItem('claudy-sessions')
      if (saved) {
        const sessions = JSON.parse(saved)
        set({
          sessions,
          currentSessionId: sessions[0]?.id || null,
          currentSession: sessions[0] || null,
          messages: sessions[0]?.messages || [],
        })
      }
    } catch (err) {
      console.error('Error loading sessions:', err)
    }
  },

  loadModels: async () => {
    try {
      // Modelos por defecto (puede ser reemplazado por API)
      const defaultModels: Model[] = [
        {
          id: 'deepseek/deepseek-chat',
          name: 'DeepSeek Chat',
          provider: 'deepseek',
          description: 'Modelo DeepSeek optimizado para chat',
          contextWindow: 32768,
        },
        {
          id: 'claude-3-opus',
          name: 'Claude 3 Opus',
          provider: 'anthropic',
          description: 'Modelo más potente de Anthropic',
          contextWindow: 200000,
        },
        {
          id: 'gpt-4-turbo',
          name: 'GPT-4 Turbo',
          provider: 'openai',
          description: 'Modelo GPT-4 optimizado',
          contextWindow: 128000,
        },
        {
          id: 'gemini-2.0-pro',
          name: 'Gemini 2.0 Pro',
          provider: 'google',
          description: 'Modelo Gemini avanzado',
          contextWindow: 100000,
        },
      ]

      set({
        models: defaultModels,
        selectedModel: defaultModels[0],
      })
    } catch (err) {
      console.error('Error loading models:', err)
    }
  },
}))
