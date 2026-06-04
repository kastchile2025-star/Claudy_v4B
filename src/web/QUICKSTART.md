# 🚀 Guía Rápida - Claudy Web UI

## ⚡ 5 Minutos de Setup

### 1. Requisitos
```bash
✓ Node.js 18+
✓ OpenCode corriendo en http://localhost:4096
```

### 2. Instalación
```bash
cd src/web
npm install
npm run dev
```

Abre **http://localhost:3000** en tu navegador.

### 3. Variables de Entorno (opcional)
```bash
cp .env.example .env.local
# Edita .env.local si necesitas cambiar la URL de OpenCode
```

## 🎯 Primer Uso

1. **Nueva Conversación** - Click en "Nueva conversación"
2. **Escribe tu pregunta** en el input
3. **Envía con Enter** o click en el botón
4. Verás la respuesta en streaming ✨

## ⚙️ Configuración

Click en **⚙️ Configuración** para:
- Cambiar modelo
- Ajustar temperatura (creatividad)
- Limitar tokens (longitud respuesta)
- Personalizar instrucción del sistema
- Habilitar/deshabilitar tools
- Cambiar tema

## 💾 Persistencia

Las sesiones se guardan automáticamente en **localStorage**:
- Historial de conversaciones
- Configuración personal
- Preferencia de tema

## 🔌 Conexión con OpenCode

La interfaz se conecta automáticamente a:
```
http://localhost:4096
```

Si OpenCode no está disponible, verás un error. Asegúrate de tenerlo corriendo:
```bash
opencode serve --port 4096
```

## 🎨 Temas

- **Oscuro (default)** - Mejor para trabajar de noche
- **Claro** - Mayor contraste, mejor para impresión

## 📱 Responsive

- **Mobile**: Sidebar colapsable
- **Tablet**: Layout adaptativo
- **Desktop**: Interfaz completa

## 🐛 Troubleshooting

### "No se conecta a OpenCode"
```bash
# Verifica que OpenCode esté corriendo
curl http://localhost:4096/health

# Si no: inicia OpenCode
opencode serve --port 4096
```

### "Sesiones no se guardan"
```bash
# Verifica localStorage en DevTools
F12 → Application → Local Storage
```

### "Build fallido"
```bash
# Limpia node_modules e instala nuevamente
rm -rf node_modules package-lock.json
npm install
```

## 🚀 Build Producción

```bash
npm run build
# Genera dist/ para deploy
```

## 📚 Documentación Completa

- [README.md](README.md) - Documentación técnica
- [Arquitectura](#arquitectura) - Estructura del código
- [API de componentes](#componentes) - Referencia de componentes

## 🆘 Soporte

- Issues: Abre un issue en GitHub
- Discussions: Participa en las conversaciones
- Documentación: Lee el README.md completo

---

**Happy chatting with Claudy AI! 🤖✨**
