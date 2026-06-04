# 🤖 Claudy v4 - Asistente IA Personal Local

**Versión:** 4.0  
**Fecha de Análisis:** Mayo 2026  
**Estado:** Producción con Roadmap Activo  
**Autor/Mantenedor:** kastchile2025-star  

---

## 📋 Tabla de Contenidos

1. [¿Qué es Claudy?](#qué-es-claudy)
2. [Características Principales](#características-principales)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Tecnologías Utilizadas](#tecnologías-utilizadas)
5. [Estructura del Proyecto](#estructura-del-proyecto)
6. [Instalación y Setup](#instalación-y-setup)
7. [Comandos Principales](#comandos-principales)
8. [Sistema de Configuración](#sistema-de-configuración)
9. [Dependencias](#dependencias)
10. [Estado del Proyecto](#estado-del-proyecto)
11. [Roadmap (15 Mejoras Planificadas)](#roadmap-15-mejoras-planificadas)
12. [Uso Avanzado](#uso-avanzado)

---

## ¿Qué es Claudy?

**Claudy** es un asistente de inteligencia artificial personal que funciona localmente, diseñado para proporcionar acceso flexible a múltiples modelos de IA sin depender de interfaces web. Se presenta en tres modalidades:

### Modalidades

| Modalidad | Descripción | Tecnología |
|-----------|-------------|-----------|
| **CLI (Terminal)** | Chat interactivo en terminal con historial | Node.js + TypeScript + Commander |
| **Desktop Pet** | Mascota animada interactiva en pantalla | Python 3.13 + tkinter |
| **Web UI** | Interfaz web moderna | React + Vite + Tailwind |

### Propósito Principal

- Proporcionar acceso a **300+ modelos de IA** (DeepSeek, Claude, Gemini, Kimi, Qwen, GLM, etc.)
- Funcionar **localmente** con OpenCode (servidor IA local)
- Ofrecer herramientas integradas (`/read`, `/write`, `/exec`) para interacción con el sistema
- Mantener **sistema de skills extensibles** en Markdown
- Soportar **múltiples canales** de comunicación (CLI, Telegram, Discord, WhatsApp)
- Proporcionar **privacidad** sin enviar datos a servidores externos

---

## Características Principales

### ✨ CLI Moderna

- **Streaming en tiempo real** - Visualiza respuestas conforme se generan
- **REPL Interactivo** - Historia de comandos y auto-completado
- **Syntax Highlighting** - Con Chalk y marked-terminal
- **Spinners de progreso** - Visualización de carga con Ora
- **Comandos contextuales** - Slash commands (`/read`, `/write`, `/exec`, `/model`, etc.)

### 🤖 IA Flexible

- **Acceso a 300+ modelos** - Catálogo completo de OpenCode Go
- **Cambio dinámico de modelo** - Selecciona modelo por sesión
- **Router inteligente** - Asignación automática según contexto
- **Selector visual** - Interfaz amigable para elegir modelo
- **Soporte multi-proveedor** - DeepSeek, Claude, Kimi, Qwen, GLM, Gemini

### 🛠️ Tools Seguros

- **Sandbox controlado** - Ejecución segura de comandos
- **`/read`** - Lectura de archivos (habilitado por defecto)
- **`/write`** - Escritura de archivos (configurable)
- **`/exec`** - Ejecución de comandos (configurable)
- **Timeout ajustable** - Control de ejecución
- **Output truncado** - Prevención de desbordamientos

### 🧠 Sistema de Memoria

- **Memoria vectorial local** - Sin base de datos externa
- **Búsqueda semántica** - Aproximada basada en embeddings
- **Persistencia JSON** - Almacenamiento en `~/.claudy/memory.json`
- **Integración automática** - Contexto histórico en chats

### 📚 Skills Extensibles

- **Formato SKILL.md** - Markdown puro para definir skills
- **Instalación desde GitHub** - `claudy skills install <repo>`
- **90+ comandos slash** - Pre-configurados y extensibles
- **Sistema modular** - Cada skill es independiente

### 🎙️ Multicanal

- **CLI** - Terminal interactiva
- **Web UI** - Navegador moderno
- **Telegram Bot** - Polling automático
- **Discord Bot** - Experimental
- **WhatsApp Bot** - Experimental
- **Desktop Pet** - Interfaz visual en pantalla

### 🎨 Desktop Pet

- **Animaciones fluidas** - 6 frames por estado
- **Skinning dinámico** - Cambio de apariencia
- **Estados múltiples** - Idle, happy, thinking, etc.
- **Drag & drop** - Movilidad en pantalla (planificado)
- **Snap to edges** - Adhesión a bordes (planificado)
- **Notificaciones** - Windows toast notifications

### 📡 Integración OpenCode

- **Servidor local** - `opencode serve --port 4096`
- **Sin dependencia de API externa** - Funciona offline
- **Compatible con APIs cloud** - Fallback a proveedores
- **Gestión automática** - Verificación e inicialización automática

---

## Arquitectura del Sistema

### Diagrama General

```
┌──────────────────────────────────────────────────────────────┐
│                         USUARIOS                              │
│        CLI      |      Desktop Pet      |      Web UI        │
└───────┬──────────────────┬──────────────────────┬────────────┘
        │                  │                      │
        │         WebSocket Connection            │
        │                  │                      │
        ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│              CLAUDY CORE (Node.js + TypeScript)             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  CLI Controller | Session Manager | Config Manager  │  │
│  │  Memory System | Skills Loader | Tool Executor     │  │
│  └──────────────────────────────────────────────────────┘  │
└────────┬───────────────────┬─────────────────────┬──────────┘
         │                   │                     │
    HTTP │                   │                 File I/O
    API  │                   │                     │
         ▼                   ▼                     ▼
    ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐
    │  OpenCode   │  │   APIs       │  │   ~/.claudy/    │
    │  Server     │  │   (DeepSeek, │  │ ├─ config.json  │
    │ (4096)      │  │    Claude)   │  │ ├─ sessions/    │
    └─────────────┘  └──────────────┘  │ ├─ memory.json  │
                                        │ └─ skills/      │
                                        └─────────────────┘
```

### Flujo de Datos

```
Usuario → CLI Input → Session Creation → OpenCode Query → Memory Integration
                            ↓
                      Tool Execution (/read, /write, /exec)
                            ↓
                      Response Streaming → Storage → Display
```

---

## Tecnologías Utilizadas

### Backend CLI

| Capa | Tecnología | Versión |
|------|-----------|---------|
| **Runtime** | Node.js | 20+ |
| **Lenguaje** | TypeScript | 5.x |
| **Build** | tsup | Latest |
| **Web Framework** | Express | 4.x |
| **CLI Framework** | Commander | Latest |
| **Real-time** | WebSocket | nativo |
| **HTTP Client** | Axios | Latest |

### Frontend Web

| Componente | Tecnología |
|-----------|-----------|
| **Framework** | React 18+ |
| **Build Tool** | Vite |
| **Styling** | Tailwind CSS |
| **State** | React Hooks |

### Desktop Pet

| Aspecto | Tecnología |
|--------|-----------|
| **Runtime** | Python 3.13+ |
| **UI Framework** | tkinter |
| **Imágenes** | PIL (Pillow) |
| **Notificaciones** | winotify, win10toast |
| **System Tray** | pystray |
| **Bots** | python-telegram-bot |

### Modelos & IA

| Tipo | Proveedores |
|------|-----------|
| **LLM** | DeepSeek, Claude, Kimi, Qwen, GLM, Gemini |
| **Embeddings** | sentence-transformers |
| **Speech-to-Text** | Faster-Whisper |
| **Text-to-Speech** | Edge-TTS |
| **ML** | scikit-learn, numpy |

### Storage

| Formato | Uso |
|--------|-----|
| **JSON** | Config, sesiones, memoria |
| **Markdown** | Skills, documentación |
| **SQLite** | (Planificado para FTS) |

---

## Estructura del Proyecto

### Directorios Principales

```
Claudy_v4/
│
├── 📁 src/                          # Código fuente TypeScript
│   ├── cli.ts                       # Entrada principal (Commander)
│   ├── config.ts                    # Gestión ~/.claudy/config.json
│   ├── opencode.ts                  # Cliente HTTP a OpenCode
│   ├── types.ts                     # Interfaces TypeScript
│   ├── utils.ts                     # Utilidades y CRUD
│   ├── tools.ts                     # /read, /write, /exec (sandbox)
│   ├── memory.ts                    # Vector memory local
│   ├── skills.ts                    # Carga y búsqueda de skills
│   ├── websearch.ts                 # Búsqueda web (DuckDuckGo)
│   ├── session-search.ts            # Búsqueda de sesiones
│   ├── export.ts                    # Export multi-formato
│   ├── fileops.ts                   # Operaciones de archivos
│   ├── location.ts                  # Geolocalización
│   ├── opencode-ensure.ts           # Auto-inicialización OpenCode
│   │
│   ├── 📁 commands/                 # Comandos CLI
│   │   ├── chat.ts                  # Chat REPL interactivo
│   │   ├── setup.ts                 # Wizard configuración
│   │   ├── config.ts                # Gestión de configuración
│   │   ├── sessions.ts              # CRUD de sesiones
│   │   ├── models.ts                # Gestión de modelos
│   │   └── skills.ts                # Comandos de skills
│   │
│   └── 📁 desktop/                  # Aplicación Desktop (Python)
│       ├── pet.py                   # Mascota principal
│       ├── chat_view.py             # Interfaz de chat
│       ├── browser.py               # Navegador integrado
│       ├── tts.py                   # Text-to-Speech
│       ├── memory_providers.py      # Proveedores de memoria
│       ├── model_router.py          # Router inteligente
│       ├── mcp_client.py            # Cliente MCP
│       ├── skin_swap.py             # Cambio de apariencia
│       ├── subagent_runner.py       # Sub-agentes
│       ├── obsidian_export.py       # Export a Obsidian
│       ├── bg_telegram_bot.py       # Bot Telegram
│       ├── bg_discord_bot.py        # Bot Discord (exp)
│       ├── bg_whatsapp_bot.py       # Bot WhatsApp (exp)
│       ├── generate_moon_frames.py  # Animación luna
│       ├── generate_coffee_frames.py # Animación café
│       └── backup_original/         # Código legacy
│
├── 📁 scripts/                      # Scripts de utilidad
│   ├── backup-claudy.ps1            # Backup PowerShell
│   ├── restore-claudy.ps1           # Restore PowerShell
│   ├── backup-claudy-full.ps1       # Backup completo
│   ├── restore-claudy-full.ps1      # Restore completo
│   ├── codespace-*.sh               # Scripts GitHub Codespaces
│   ├── ingest_qcore.ts              # Ingestión de datos
│   └── gen_informe_rusa.py          # Generación reportes
│
├── 📁 skills/                       # Sistema de skills extensible
│   ├── README.md                    # Documentación skills
│   ├── find-skills/                 # Búsqueda de skills
│   ├── github-pr-workflow/          # Workflow PR GitHub
│   ├── systematic-debugging/        # Debugging sistemático
│   ├── test-driven-development/     # TDD
│   ├── web-search-answer/           # Búsqueda web
│   └── writing-plans/               # Planificación
│
├── 📁 documentos/                   # Documentación
├── 📁 power point/                  # Presentaciones
│
├── 📄 Configuración & Info
│   ├── package.json                 # Dependencies Node.js
│   ├── pyproject.toml               # Metadata Python
│   ├── requirements.txt             # Dependencies Python
│   ├── tsconfig.json                # Config TypeScript
│   ├── tsup.config.ts               # Config bundler
│   ├── .env.example                 # Variables de entorno
│   └── .gitignore
│
├── 📄 Documentación
│   ├── README.md                    # Documentación principal
│   ├── CLI.md                       # Documentación CLI
│   ├── INSTALL.md                   # Instalación
│   ├── ROADMAP.md                   # Roadmap 15 mejoras
│   ├── PROGRESO.md                  # Estado actual
│   ├── HERMES_REPLICATION_PLAN.md   # Plan replicación
│   ├── PASO_A_PASO_INICIALIZAR_CLAUDY.md # Guía paso a paso
│   └── PROYECTO_ACTUALIZADO.md      # Este archivo
│
└── 📁 Batch Scripts
    ├── iniciar_claudy.bat           # Iniciar Claudy
    ├── backup_claudy.bat            # Backup rápido
    ├── subir_a_github.bat           # Push a GitHub
    └── setup.sh                     # Setup Unix
```

---

## Instalación y Setup

### Requisitos Previos

```
✓ Windows 10/11 (con soporte WSL2 opcional)
✓ Node.js 20+ (LTS recomendado)
✓ Python 3.13+
✓ Git
✓ FFmpeg (para audio)
✓ npm / pnpm (gestor paquetes)
```

### Instalación Rápida (5-10 minutos)

#### 1. Clonar repositorio

```bash
git clone https://github.com/kastchile2025-star/Claudy_v4.git
cd Claudy_v4
```

#### 2. Instalar dependencias Node.js

```bash
npm install
```

#### 3. Instalar dependencias Python

```bash
pip install -r requirements.txt
```

#### 4. Inicializar OpenCode

```bash
# Autenticarse con OpenCode
opencode auth login

# Iniciar servidor en puerto 4096
opencode serve --port 4096
```

#### 5. Compilar y enlazar Claudy

```bash
# Build
npm run build

# Link global
npm link

# Verificar instalación
claudy --version
```

#### 6. Configuración inicial

```bash
# Wizard interactivo
claudy config

# O iniciar chat directamente
claudy chat
```

### Setup Detallado

Consultar [INSTALL.md](INSTALL.md) y [PASO_A_PASO_INICIALIZAR_CLAUDY.md](PASO_A_PASO_INICIALIZAR_CLAUDY.md) para:
- Configuración de variables de entorno
- Setup de bots (Telegram, Discord, WhatsApp)
- Integración con Obsidian
- Configuración de modelos específicos

---

## Comandos Principales

### Chat Interactivo

```bash
# Continuar última sesión o seleccionar
claudy chat

# Forzar nueva sesión
claudy chat --new

# Continuar sesión específica por ID
claudy chat -s <session-id>

# Especificar modelo
claudy chat -m <provider/model>

# Con opciones combinadas
claudy chat --new -m deepseek/deepseek-chat
```

### Gestión de Sesiones

```bash
# Listar todas las sesiones
claudy sessions list

# Ver contenido de sesión
claudy sessions show <id>

# Eliminar sesión
claudy sessions delete <id>

# Exportar a Markdown
claudy sessions export <id> -o archivo.md

# Exportar a PDF
claudy sessions export <id> -o archivo.pdf

# Exportar a HTML
claudy sessions export <id> -o archivo.html
```

### Gestión de Modelos

```bash
# Listar modelos disponibles
claudy models list

# Ver modelo actual
claudy models current

# Establecer modelo por defecto
claudy models set deepseek/deepseek-chat

# Ver detalles de modelo
claudy models info <provider/model>
```

### Configuración

```bash
# Ver configuración completa
claudy config get

# Establecer valor
claudy config set <clave> <valor>

# Ejemplos
claudy config set opencode-port 4096
claudy config set allow-exec true
claudy config set model-timeout 60

# Editor interactivo
claudy config edit

# Ruta del archivo config
claudy config path
```

### Skills

```bash
# Listar skills disponibles
claudy skills list

# Instalar skill desde GitHub
claudy skills install <owner/repo>

# Buscar skills
claudy skills search <palabra-clave>

# Ver skill específico
claudy skills show <skill-name>
```

### Dentro del Chat REPL

```
/exit, /quit       - Salir de sesión
/clear             - Limpiar pantalla
/save              - Guardar sesión manualmente
/model <modelo>    - Cambiar modelo dinámicamente
/read <ruta>       - Leer archivo
/write <ruta>      - Escribir archivo (si está habilitado)
/exec <comando>    - Ejecutar comando (si está habilitado)
/tools             - Ver permisos de tools
/history           - Información de sesión
/memory            - Ver memoria vectorial
/help              - Ayuda contextual
```

---

## Sistema de Configuración

### Ubicación

```
~/.claudy/config.json          # Configuración principal
~/.claudy/sessions/            # Historial de sesiones
~/.claudy/memory.json          # Memoria vectorial
~/.claudy/skills/              # Skills instalados
```

### Archivo config.json

```json
{
  "opencode": {
    "baseUrl": "http://localhost:4096",
    "timeout": 30000,
    "enableSandbox": true
  },
  "model": {
    "default": "deepseek/deepseek-chat",
    "providers": {
      "opencode": true,
      "anthropic": false,
      "gemini": false
    }
  },
  "tools": {
    "read": true,
    "write": false,
    "exec": false,
    "maxOutputLength": 5000,
    "allowedRoot": "/home/user"
  },
  "memory": {
    "enabled": true,
    "vectorSize": 384,
    "maxSessions": 100
  },
  "session": {
    "autoSave": true,
    "saveInterval": 300000,
    "maxSessions": 100
  },
  "ui": {
    "theme": "dark",
    "fontSize": 14,
    "language": "es"
  },
  "telegram": {
    "enabled": false,
    "token": "YOUR_BOT_TOKEN"
  }
}
```

---

## Dependencias

### Frontend/Backend (package.json)

```json
{
  "dependencies": {
    "axios": "^1.x",
    "chalk": "^5.x",
    "commander": "^11.x",
    "dotenv": "^16.x",
    "inquirer": "^8.x",
    "marked": "^9.x",
    "marked-terminal": "^6.x",
    "ora": "^7.x"
  },
  "devDependencies": {
    "typescript": "^5.x",
    "tsx": "^4.x",
    "tsup": "^8.x",
    "vitest": "^1.x",
    "@types/node": "^20.x",
    "@types/inquirer": "^8.x"
  }
}
```

### Desktop/Python (pyproject.toml)

```toml
[project]
name = "claudy-desktop"
version = "4.0"
requires-python = ">=3.13"

dependencies = [
    "winotify",
    "pillow",
    "win10toast",
    "pystray",
    "reportlab",
    "pypdf"
]
```

### Python Completo (requirements.txt)

**IA & Embeddings:**
- sentence-transformers
- scikit-learn
- numpy
- torch (opcional)

**Audio:**
- edge-tts
- faster-whisper
- PyAudio

**Bots & Comunicación:**
- python-telegram-bot
- discord.py (exp)
- whatsapp-web.py (exp)

**Web:**
- playwright
- yt-dlp
- youtube-transcript-api

**Visión & OCR:**
- pytesseract
- pypdf
- PIL

**Sistema:**
- keyboard
- mss
- psutil
- pycaw
- tkinterdnd2

**MCP:**
- mcp>=1.0

---

## Estado del Proyecto

### ✅ Características Completadas

**Core:**
- ✓ CLI completa en TypeScript
- ✓ Chat REPL interactivo con streaming
- ✓ Integración OpenCode
- ✓ Sistema de sesiones persistentes
- ✓ Almacenamiento JSON local

**Herramientas:**
- ✓ Tools sandbox (`/read`, `/write`, `/exec`)
- ✓ Autenticación flexible (Bearer, Basic)
- ✓ Búsqueda web (DuckDuckGo scraping)
- ✓ Memoria local vectorial
- ✓ Sistema de skills en Markdown

**Multicanal:**
- ✓ CLI completa
- ✓ Web UI (React + Vite)
- ✓ Telegram Bot (polling)
- ✓ Voice STT/TTS (navegador)

**Extras:**
- ✓ Export Markdown multi-sesión
- ✓ Syntax highlighting terminal
- ✓ Auto-completado modelos
- ✓ Soporte 300+ modelos OpenCode

### 🔄 En Progreso / Experimental

- 🟡 Desktop Pet (Python) - Funcional pero mejoras visuales pendientes
- 🟡 Discord Bot - Experimental
- 🟡 WhatsApp Bot - Experimental
- 🟡 Sistema de temas personalizados

---

## Roadmap (15 Mejoras Planificadas)

### 🔴 Alto Impacto (8 ítems) - 2-3 semanas

1. **Cancelación de streaming con Ctrl+C**
   - Interrumpir respuestas sin perder contexto
   - Mejora UX en respuestas largas

2. **Auto-resumen de sesiones largas**
   - Comprimir contexto histórico
   - Mantener información relevante

3. **Búsqueda semántica de memoria**
   - Búsqueda vectorial mejorada
   - Recuperación contextual

4. **Drag & drop del desktop pet**
   - Movilidad libre en pantalla
   - Posición persistente

5. **Snap to edges**
   - Adhesión automática a bordes
   - Ahorro de espacio pantalla

6. **Auto-start en Windows**
   - Iniciar con el sistema
   - Tray icon integrado

7. **System tray icon**
   - Minimizar a bandeja
   - Acceso rápido

8. **Notificaciones Windows 10/11**
   - Toast notifications
   - Recordatorios contextuales

### 🟡 Medio Impacto (4 ítems) - 3-4 semanas

1. **Cliente MCP completo**
   - Brave Search API
   - GitHub API
   - Filesystem tools

2. **Function calling nativo**
   - Llamadas a funciones del sistema
   - Ejecución de workflows

3. **Búsqueda web robusta**
   - APIs en lugar de scraping
   - Mejor precisión resultados

4. **Full-text search (FTS)**
   - Búsqueda sesiones mejorada
   - SQLite indexing

### 🟢 Bajo Impacto (3 ítems) - 2-3 semanas

1. **Soporte de imágenes (Vision)**
   - Análisis de imágenes
   - OCR integrado

2. **Model routing inteligente**
   - Selección automática por tarea
   - Optimización contexto

3. **Export multi-formato**
   - PDF con formato
   - HTML interactivo
   - PowerPoint

**Cronograma estimado:** 3 meses para completar las 15 mejoras

---

## Uso Avanzado

### Integración con Obsidian

```bash
# Exportar sesión a vault Obsidian
claudy sessions export <id> -o ~/Obsidian/Claudy/sesión-<fecha>.md

# Configurar en config.json
{
  "obsidian": {
    "enabled": true,
    "vaultPath": "~/Obsidian",
    "autoSync": true
  }
}
```

### Custom Skills

Crear archivo `SKILL.md` con estructura:

```markdown
---
name: mi-skill
version: 1.0.0
description: Descripción de mi skill
author: Tu nombre
---

## Descripción
Texto descriptivo.

## Uso
/micomando [args]

## Implementación
Detalles técnicos.
```

### Variables de Entorno

```env
# .env
OPENCODE_URL=http://localhost:4096
OPENCODE_TIMEOUT=30000

TELEGRAM_TOKEN=tu_token_aqui
TELEGRAM_ENABLED=true

ALLOW_WRITE=false
ALLOW_EXEC=false

DEFAULT_MODEL=deepseek/deepseek-chat
```

### Debugging

```bash
# Modo verbose
claudy chat --verbose

# Ver logs
tail -f ~/.claudy/logs/claudy.log

# Debug de configuración
claudy config debug

# Test de OpenCode
claudy opencode test
```

### Performance

**Optimizaciones:**
- Sesiones comprimidas después de 100 mensajes
- Memory cleaning automático
- Caché de modelos en memoria

**Benchmark típico:**
- Inicialización: ~500ms
- Primera query: ~2-3s
- Respuestas streaming: Real-time
- Memoria por sesión: ~50-100KB

---

## Contribución y Desarrollo

### Clonar para desarrollo

```bash
git clone https://github.com/kastchile2025-star/Claudy_v4.git
cd Claudy_v4
npm install
npm run dev
```

### Scripts disponibles

```bash
npm run build      # Compilar TypeScript
npm run dev        # Modo desarrollo
npm run test       # Ejecutar tests
npm run lint       # Linting
npm link           # Link global
```

### Estructura de commits

```
feat: agregar nueva funcionalidad
fix: corregir bug
docs: actualizar documentación
perf: mejora de performance
refactor: refactorización de código
test: agregar tests
```

---

## Problemas Comunes

### OpenCode no se conecta

```bash
# Verificar si está corriendo
curl http://localhost:4096/health

# Reiniciar
opencode kill
opencode serve --port 4096
```

### Sesiones no se guardan

```bash
# Verificar permisos en ~/.claudy/
ls -la ~/.claudy/
chmod -R 755 ~/.claudy/
```

### Memoria llena

```bash
# Limpiar sesiones antiguas
claudy sessions cleanup --older-than 30days

# Ver tamaño
claudy stats size
```

---

## Recursos

- **GitHub:** https://github.com/kastchile2025-star/Claudy_v4
- **Documentación:** [README.md](README.md)
- **CLI Guide:** [CLI.md](CLI.md)
- **Instalación:** [INSTALL.md](INSTALL.md)
- **Roadmap:** [ROADMAP.md](ROADMAP.md)
- **Progreso:** [PROGRESO.md](PROGRESO.md)

---

## Licencia

Desarrollado por **kastchile2025-star**  
Fork mejorado de **OpenClaw** con arquitectura moderna

---

## Contacto y Soporte

Para reportar issues, sugerencias o contribuciones:
- GitHub Issues: https://github.com/kastchile2025-star/Claudy_v4/issues
- Discussions: https://github.com/kastchile2025-star/Claudy_v4/discussions

---

**Última actualización:** Mayo 2026  
**Versión:** 4.0  
**Estado:** Activo y en desarrollo continuo
