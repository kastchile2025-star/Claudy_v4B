# Claudy CLI

Interfaz de línea de comandos para Claudy. Usa **OpenCode local** como motor de IA.

## Requisitos previos

Tener OpenCode corriendo localmente:

```bash
opencode serve --port 4096 --hostname 127.0.0.1
```

## Instalación

```bash
cd claudy
npm install
npm run build
npm link    # Para usar 'claudy' globalmente
```

O ejecutar en modo desarrollo:

```bash
npm run dev -- <comando>
```

## Configuración inicial

```bash
claudy setup
```

Te pedirá:
- URL del servidor OpenCode (default: `http://127.0.0.1:4096`)
- Usuario y password (si OpenCode tiene auth, opcional)
- Modelo predeterminado (formato `provider/model`)
- System prompt
- Parámetros (temperature, max tokens)

La configuración se guarda en `~/.claudy/config.json`.
Las sesiones se guardan en `~/.claudy/sessions/`.

## Comandos

### `claudy chat`
Iniciar chat interactivo.

```bash
claudy chat                  # Continuar/elegir sesión
claudy chat --new            # Forzar sesión nueva
claudy chat -s <session-id>  # Continuar sesión específica
claudy chat -m <model>       # Usar modelo distinto
```

**Comandos dentro del chat:**
- `/exit`, `/quit` - Salir
- `/clear` - Limpiar pantalla
- `/save` - Guardar sesión
- `/model <m>` - Cambiar modelo
- `/history` - Info de sesión
- `/help` - Ayuda

### `claudy sessions`
Gestionar sesiones.

```bash
claudy sessions list                    # Listar
claudy sessions show <id>               # Ver contenido
claudy sessions delete <id>             # Eliminar
claudy sessions export <id> -o file.md  # Exportar a markdown
```

### `claudy models`
Gestionar modelos.

```bash
claudy models list                 # Listar disponibles
claudy models list -s claude       # Filtrar
claudy models list -l 50           # Aumentar límite
claudy models current              # Modelo actual
claudy models set <provider/model> # Cambiar default
```

### `claudy config`
Gestionar configuración.

```bash
claudy config get                       # Ver toda
claudy config get -k agent.temperature  # Ver una clave
claudy config set agent.temperature 0.5 # Editar
claudy config edit                      # Editor interactivo
claudy config path                      # Ruta del archivo
```

## Estructura

```
src/
├── cli.ts              # Punto de entrada
├── config.ts           # Gestión de config
├── opencode.ts         # Cliente OpenCode server
├── types.ts            # Tipos TypeScript
├── utils.ts            # Sesiones y helpers
└── commands/
    ├── setup.ts        # claudy setup
    ├── chat.ts         # claudy chat
    ├── config.ts       # claudy config
    ├── sessions.ts     # claudy sessions
    └── models.ts       # claudy models
```

## Stack

- Node.js 20+ (ESM)
- TypeScript
- commander (CLI parsing)
- chalk (colores)
- ora (spinners)
- inquirer (prompts interactivos)
- axios (HTTP)

## Próximos pasos

- [ ] Streaming de respuestas (SSE)
- [ ] Tools: web_search, exec, read, write
- [ ] Soporte multi-canal (Telegram, Discord)
- [ ] Memoria/RAG
- [ ] Plugins
