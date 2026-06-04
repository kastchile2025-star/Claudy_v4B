# 🏗️ Arquitectura - Claudy Web UI

## Vista General

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLAUDY WEB UI (React)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐              ┌──────────────────┐              │
│  │   Sidebar    │              │   Chat Area      │              │
│  │              │              │                  │              │
│  │ • Sessions   │ ◄──────────► │ • Messages       │              │
│  │ • New Chat   │              │ • Input          │              │
│  │ • Settings   │              │ • Streaming      │              │
│  └──────────────┘              └──────────────────┘              │
│         │                              │                          │
│         └──────────────┬───────────────┘                          │
│                        │                                          │
│         ┌──────────────▼──────────────┐                          │
│         │    Zustand Global Store    │                          │
│         │                            │                          │
│         │ • Sessions                 │                          │
│         │ • Messages                 │                          │
│         │ • Models                   │                          │
│         │ • Config                   │                          │
│         │ • Theme                    │                          │
│         └──────────────┬──────────────┘                          │
│                        │                                          │
│                        │ localStorage                            │
│                        ▼                                          │
│         ┌──────────────────────────┐                            │
│         │   Browser Storage        │                            │
│         │ • config.json            │                            │
│         │ • sessions[]             │                            │
│         └──────────────────────────┘                            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
         │
         │ HTTP
         ▼
┌─────────────────────────────────────────────────────────────────┐
│           OpenCode Server (http://localhost:4096)               │
│                                                                   │
│  • Chat Completions API                                         │
│  • Models Listing                                               │
│  • Tools Execution                                              │
│  • Memory Queries                                               │
│  • Web Search                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Stack Tecnológico

| Capa | Tecnología | Versión |
|------|-----------|---------|
| **Runtime** | React | 18+ |
| **Build** | Vite | 5+ |
| **Styling** | Tailwind CSS | 3.3+ |
| **State** | Zustand | 4.4+ |
| **HTTP** | Axios | 1.6+ |
| **Markdown** | react-markdown | 8.0+ |
| **Icons** | lucide-react | 0.296+ |
| **Syntax** | react-syntax-highlighter | 15.5+ |
| **Date** | date-fns | 2.30+ |
| **Language** | TypeScript | 5.3+ |

## Flujo de Datos

### 1. Usuario envía mensaje
```
User Input → ChatInput.tsx → handleSendMessage()
    ↓
addMessage(userMessage) → Store (Zustand)
    ↓
localStorage actualizado
    ↓
UI re-render
```

### 2. Obtener respuesta de OpenCode
```
handleSendMessage() → openCodeService.sendMessageStream()
    ↓
HTTP POST → http://localhost:4096/chat/completions
    ↓
Streaming chunks recibidos
    ↓
onChunk(chunk) → fullResponse += chunk
    ↓
addMessage(assistantMessage) actualizado
    ↓
UI actualizado en tiempo real (animado)
```

### 3. Cambiar sesión
```
selectSession(id) → Store
    ↓
currentSession = sessions.find(id)
currentSession.messages → messages
    ↓
UI re-render con nuevos mensajes
    ↓
Auto-scroll al final
```

### 4. Configuración
```
updateConfig(newConfig)
    ↓
Store merge + localStorage.setItem()
    ↓
Próximos mensajes usan nueva config
    ↓
Settings Panel se actualiza
```

## Estructura de Carpetas

```
src/web/src/
├── components/              # Componentes React
│   ├── Sidebar.tsx         # Panel conversaciones
│   ├── ChatArea.tsx        # Área principal chat
│   ├── MessageBubble.tsx   # Burbuja de mensaje
│   ├── ChatInput.tsx       # Input de mensaje
│   ├── SettingsPanel.tsx   # Panel configuración
│   └── index.ts            # Exports
│
├── store/                  # State management
│   └── useStore.ts         # Zustand store
│
├── services/               # Servicios HTTP
│   └── opencode.ts         # Cliente OpenCode
│
├── hooks/                  # Custom React hooks
│   └── useOpenCode.ts      # Hook para OpenCode
│
├── types/                  # TypeScript definitions
│   └── index.ts            # Interfaces
│
├── utils/                  # Utilidades
│   └── index.ts            # Helpers
│
├── App.tsx                 # Root component
├── main.tsx                # React entry
├── index.css               # Tailwind + estilos
└── vite-env.d.ts          # Vite env types
```

## Componentes Principales

### Sidebar.tsx
**Responsabilidades:**
- Mostrar logo + estado
- Listar sesiones
- Crear nueva sesión
- Eliminar sesiones
- Navegar a configuración

**Props:** Ninguno (consume del store)

**State interno:**
- `isOpen` - Sidebar visible (mobile)

### ChatArea.tsx
**Responsabilidades:**
- Mostrar header con título
- Renderizar mensajes
- Manejar streaming
- Auto-scroll
- Integrar ChatInput

**Props:** Ninguno

**State interno:**
- `isStreaming` - Indicador escribiendo
- `messagesEndRef` - Ref para scroll

### MessageBubble.tsx
**Responsabilidades:**
- Renderizar burbujas (usuario/asistente)
- Markdown a HTML
- Syntax highlighting
- Botón copiar

**Props:**
- `message: Message`

### ChatInput.tsx
**Responsabilidades:**
- Input textarea
- Manejo Enter/Shift+Enter
- Botones de acción
- Indicador loading

**Props:**
- `onSendMessage: (msg: string) => void`
- `isLoading: boolean`

### SettingsPanel.tsx
**Responsabilidades:**
- Panel configuración (drawer)
- Selector modelo
- Sliders (temp, tokens)
- Toggle tools
- Selector tema

**Props:** Ninguno (consume del store)

## Store (Zustand)

### Estado
```typescript
{
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

  // Config
  config: Config
  theme: 'dark' | 'light'
  showSettings: boolean
}
```

### Acciones principales
```typescript
// Session management
createSession()
selectSession(id)
deleteSession(id)

// Message handling
addMessage(message)
setLoading(bool)
setError(string)

// Config
updateConfig(partial)
toggleTheme()
toggleSettings()

// Initialization
initializeStore()
loadSessions()
loadModels()
```

### Persistencia
```
Store → localStorage
  ├── claudy-sessions (JSON array)
  ├── claudy-config (JSON object)
  └── Theme preference
```

## Servicios

### opencode.ts
**Métodos:**
- `sendMessage()` - Request/response
- `sendMessageStream()` - Streaming
- `getModels()` - Listar modelos
- `health()` - Verificar disponibilidad
- `executeTool()` - Ejecutar tools
- `webSearch()` - Búsqueda web
- `queryMemory()` - Query memoria

**Configuración:**
```typescript
axios.create({
  baseURL: 'http://localhost:4096',
  timeout: 30000
})
```

## Hooks Personalizados

### useOpenCode
**Responsabilidades:**
- Simplificar llamadas a OpenCode
- Manejar loading/error
- Callbacks para chunks
- Cleanup automático

**Uso:**
```typescript
const { sendMessageStream, isLoading, error } = useOpenCode({
  onChunk: (chunk) => { /* ... */ },
  onError: (err) => { /* ... */ },
  onComplete: (full) => { /* ... */ }
})
```

## Tipos (TypeScript)

```typescript
Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  model?: string
  tokenCount?: number
}

Session {
  id: string
  title: string
  messages: Message[]
  createdAt: Date
  updatedAt: Date
  model: string
  systemPrompt?: string
}

Model {
  id: string
  name: string
  provider: string
  description?: string
  contextWindow?: number
}

Config {
  theme: 'dark' | 'light'
  model: string
  temperature: number
  maxTokens: number
  systemPrompt: string
  tools: { read, write, exec }
}
```

## Flujo de Compilación

```
src/
  ├── TypeScript → tsc check ✓
  ├── JSX → Babel transform
  ├── CSS → Tailwind processing
  └── Assets → Copy
      ↓
      vite build (optimización)
      ↓
  dist/
    ├── index.html (entry)
    ├── assets/
    │   ├── main.*.js (minified)
    │   ├── style.*.css (minified)
    │   └── *.woff2 (fonts)
```

## Performance Considerations

### Optimizaciones
1. **Lazy imports** de componentes pesados
2. **Memoización** con React.memo()
3. **useCallback** para event handlers
4. **Virtual scrolling** (futuro)
5. **Bundle splitting** automático

### Métricas típicas
- Tamaño bundle inicial: ~180KB (minified)
- Time to interactive: ~1s en red 3G
- Streaming de respuesta: Real-time

## Flujo de Desarrollo

```
npm run dev
  ↓
Vite dev server (localhost:3000)
  ↓
Hot Module Replacement (HMR)
  ↓
  Cambios automáticos sin reload
```

## Build para Producción

```
npm run build
  ↓
TypeScript compile check
  ↓
Vite minify + optimize
  ↓
dist/ lista para deploy
  ↓
npm run preview (test local)
```

## Error Handling

### Niveles
1. **HTTP Errors** → OpenCodeService
2. **Store Errors** → setError(message)
3. **Component Errors** → Try/catch local
4. **User Feedback** → Error toast/message

### Ejemplo
```typescript
try {
  await openCodeService.sendMessage(...)
} catch (err) {
  const errorMsg = err instanceof Error ? err.message : 'Error desconocido'
  setError(errorMsg)
  // UI muestra error al usuario
}
```

---

**Diagrama actualizado en Mayo 2026 para Claudy v4.0**
