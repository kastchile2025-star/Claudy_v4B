# 🎨 Claudy Web UI

Interfaz web moderna y funcional para Claudy AI, construida con React, Vite y Tailwind CSS.

## 📋 Características

✨ **Chat en Tiempo Real**
- Streaming de respuestas con actualizaciones en vivo
- Historial de sesiones persistente
- Auto-scroll hacia últimos mensajes

🤖 **Selector de Modelos**
- 4+ modelos disponibles (DeepSeek, Claude, Gemini, GPT-4)
- Cambio dinámico por sesión
- Información contextual del modelo

⚙️ **Configuración Avanzada**
- Control de temperatura (creatividad)
- Límite de tokens ajustable
- Instrucción del sistema personalizable
- Herramientas (read/write/exec) habilitables

🌙 **Tema Oscuro/Claro**
- Toggle fácil entre temas
- Persistencia de preferencia

💾 **Persistencia Local**
- Sesiones guardadas en localStorage
- Configuración sincronizada
- Historial ilimitado

🛠️ **Integración OpenCode**
- Conexión HTTP directa a OpenCode (puerto 4096)
- Streaming real-time
- Fallback a APIs cloud

## 🚀 Instalación

### Requisitos
- Node.js 18+
- npm / pnpm
- OpenCode corriendo en `http://localhost:4096`

### Setup

```bash
# 1. Ir al directorio
cd src/web

# 2. Instalar dependencias
npm install

# 3. Desarrollo
npm run dev
# Abre http://localhost:3000

# 4. Build producción
npm run build
```

## 📁 Estructura

```
src/web/
├── src/
│   ├── components/
│   │   ├── Sidebar.tsx          # Panel izquierdo + conversaciones
│   │   ├── ChatArea.tsx         # Área principal de chat
│   │   ├── MessageBubble.tsx    # Burbujas de mensaje (Markdown)
│   │   ├── ChatInput.tsx        # Input + botones de envío
│   │   └── SettingsPanel.tsx    # Panel configuración (drawer)
│   │
│   ├── store/
│   │   └── useStore.ts          # Zustand store (estado global)
│   │
│   ├── services/
│   │   └── opencode.ts          # Cliente HTTP OpenCode
│   │
│   ├── types/
│   │   └── index.ts             # TypeScript interfaces
│   │
│   ├── App.tsx                  # Componente raíz
│   ├── main.tsx                 # Entrada React
│   └── index.css                # Tailwind + estilos globales
│
├── index.html
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
└── package.json
```

## 🎯 Componentes Principales

### Sidebar
- Logo + estado ("En línea")
- Botón "Nueva conversación"
- Listado de sesiones anteriores
- Perfil de usuario
- Botón configuración

### ChatArea
- Header con título e iconos
- Área de mensajes (auto-scroll)
- Input + botones de acción
- Indicador de escritura

### MessageBubble
- Soporte Markdown completo
- Syntax highlighting en código
- Botón copiar
- Avatares usuario/asistente

### SettingsPanel
- Drawer lateral (animado)
- Selector de modelo
- Sliders: temperatura, tokens
- Editor de instrucción sistema
- Toggle herramientas
- Selector tema

### ChatInput
- Textarea autoajustable
- Soporte Enter/Shift+Enter
- Botones adjuntar/emoji
- Indicador loading

## 🔌 Integración OpenCode

### Conexión automática
```typescript
// services/opencode.ts
const client = axios.create({
  baseURL: 'http://localhost:4096',
  timeout: 30000
})
```

### Métodos disponibles
- `sendMessage()` - Request/response
- `sendMessageStream()` - Streaming
- `getModels()` - Listar modelos
- `health()` - Verificar servidor
- `executeTool()` - Ejecutar tools
- `webSearch()` - Búsqueda web
- `queryMemory()` - Consultar memoria

## 🎨 Theming

### Colores principales (Tailwind)
```js
colors: {
  'primary': '#6366f1',      // Indigo (botones, enlaces)
  'secondary': '#8b5cf6',    // Purple (gradientes)
  'bg-dark': '#0f172a',      // Slate 900
  'bg-darker': '#020617',    // Slate 950
  'border-dark': '#1e293b',  // Slate 800
  'text-muted': '#94a3b8',   // Slate 400
}
```

### Componentes reutilizables
```css
.btn-primary          /* Botón principal */
.btn-secondary        /* Botón secundario */
.card-dark           /* Tarjetas estilo */
.gradient-text       /* Texto gradiente */
.pulse-dot           /* Punto pulsante */
```

## 💾 State Management (Zustand)

### Store global
```typescript
const store = useStore()
```

### Acciones principales
- `initializeStore()` - Cargar config e sesiones
- `createSession()` - Nueva sesión
- `selectSession()` - Cambiar sesión
- `deleteSession()` - Eliminar
- `addMessage()` - Agregar mensaje
- `setSelectedModel()` - Cambiar modelo
- `updateConfig()` - Actualizar configuración
- `toggleTheme()` - Cambiar tema

### Persistencia
- localStorage: sesiones + config
- Sincronización automática

## 📱 Responsive

- Mobile: Sidebar colapsable con overlay
- Tablet: Layout adaptativo
- Desktop: Layout completo

## 🔄 Streaming en Tiempo Real

```typescript
await openCodeService.sendMessageStream(
  prompt,
  (chunk) => {
    // Actualizar UI con cada chunk
    addMessage({ ...msg, content: fullResponse })
  }
)
```

## ⚡ Performance

- Lazy loading de modelos
- Memoización de componentes
- Scroll virtualizado (para futuro)
- Compresión de sesiones antiguas

## 🐛 Debugging

```typescript
// Logs disponibles
console.log('Estado store:', useStore.getState())
console.log('OpenCode health:', await openCodeService.health())
```

## 🚀 Próximas Mejoras

- [ ] Carga de imágenes y vision
- [ ] Búsqueda web integrada
- [ ] Memory visualization
- [ ] Function calling
- [ ] Export a PDF/HTML
- [ ] Integración MCP
- [ ] Voice input/output
- [ ] Compartir sesiones
- [ ] Colaboración en tiempo real

## 📝 Variables de Entorno

```env
VITE_OPENCODE_URL=http://localhost:4096
VITE_TIMEOUT=30000
```

## 🤝 Contribución

Las PRs son bienvenidas. Para cambios mayores, abre un issue primero.

## 📄 Licencia

MIT - Parte del proyecto Claudy v4
