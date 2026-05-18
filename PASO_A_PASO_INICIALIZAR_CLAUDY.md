# Paso a paso para inicializar Claudy

Esta guia esta pensada para este repo local:

```powershell
C:\Users\felip\Downloads\Claudy-main
```

Claudy funciona como una CLI de Node.js que se conecta a un servidor local de OpenCode.

## 1. Abrir una terminal en la raiz del proyecto

En PowerShell:

```powershell
cd C:\Users\felip\Downloads\Claudy-main
```

## 2. Verificar requisitos

Necesitas Node.js 20 o superior:

```powershell
node --version
npm --version
```

Tambien necesitas OpenCode CLI disponible:

```powershell
opencode --version
```

Si `opencode` no existe, instalalo primero siguiendo la documentacion oficial de OpenCode.

## 3. Instalar dependencias de Claudy

Desde la raiz del proyecto:

```powershell
npm install
```

## 4. Iniciar sesion en OpenCode

Si usaras OpenCode Go u otro proveedor configurado en OpenCode:

```powershell
opencode auth login
```

Sigue el flujo interactivo y deja OpenCode autenticado antes de arrancar Claudy.

## 5. Levantar el servidor local de OpenCode

Abre otra terminal y ejecuta:

```powershell
opencode serve --port 4096 --hostname 127.0.0.1
```

Deja esa terminal abierta. Claudy se conectara a:

```text
http://127.0.0.1:4096
```

Nota: Claudy tambien intenta iniciar OpenCode automaticamente si no responde, pero para la primera configuracion es mejor levantarlo manualmente para ver errores.

## 6. Ejecutar el setup inicial de Claudy

En la terminal ubicada en la raiz del proyecto:

```powershell
npm run dev -- setup
```

Respuestas recomendadas para una configuracion local:

```text
Tipo de autenticacion: Sin autenticacion (servidor local)
URL del servidor: http://127.0.0.1:4096
Modelo predeterminado: Qwen3.6 Plus (recomendado)
System prompt: Enter para usar el default
Temperatura: 0.7
Maximo de tokens: 4096
```

La configuracion queda guardada en:

```text
~/.claudy/config.json
```

En Windows normalmente equivale a:

```text
C:\Users\<tu_usuario>\.claudy\config.json
```

## 7. Probar la configuracion

Puedes revisar la configuracion actual con:

```powershell
npm run dev -- config get
```

Tambien puedes listar modelos si OpenCode esta respondiendo:

```powershell
npm run dev -- models list
```

## 8. Iniciar el chat

Para abrir Claudy en modo chat:

```powershell
npm run dev -- chat
```

Comandos utiles dentro del chat:

```text
/help
/model <provider/model>
/history
/save
/exit
```

## 9. Opcional: instalar el comando global `claudy`

Si quieres usar `claudy` sin `npm run dev --`, compila y enlaza el paquete:

```powershell
npm run build
npm link
```

Despues podras usar:

```powershell
claudy setup
claudy chat
claudy config get
claudy models list
claudy sessions list
```

## 10. Opcional: configurar permisos de tools

Por seguridad, lectura suele estar activa, pero escritura y ejecucion vienen apagadas por defecto.

Para activar escritura:

```powershell
npm run dev -- config set tools.allowWrite true
```

Para activar ejecucion de comandos:

```powershell
npm run dev -- config set tools.allowExec true
```

Para limitar el directorio permitido:

```powershell
npm run dev -- config set tools.allowedRoot "C:\Users\felip\Downloads\Claudy-main"
```

## 11. Si algo falla

Si Claudy no conecta:

```powershell
opencode serve --port 4096 --hostname 127.0.0.1
```

Luego vuelve a probar:

```powershell
npm run dev -- setup
```

Si el comando `claudy` global no existe, usa modo desarrollo:

```powershell
npm run dev -- chat
```

Si hay errores de dependencias:

```powershell
npm install
npm run build
```

## Flujo corto recomendado

```powershell
cd C:\Users\felip\Downloads\Claudy-main
npm install
opencode auth login
opencode serve --port 4096 --hostname 127.0.0.1
npm run dev -- setup
npm run dev -- chat
```

