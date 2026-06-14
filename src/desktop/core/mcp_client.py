"""Claudy core.mcp_client — Cliente MCP por stdio (plan Hermes 2.3).

Conecta Claudy a servidores MCP (Model Context Protocol) externos —
GitHub, Postgres, filesystem, Slack… — y registra sus tools dinámicamente
en el TOOL_REGISTRY para que el LLM las use por function-calling, sin
escribir tools nativas.

Transporte: stdio con JSON-RPC 2.0 delimitado por saltos de línea (el
estándar MCP). Un hilo lector por servidor empareja respuestas por id;
el handshake es initialize → notifications/initialized → tools/list.

Config (~/.claudy/config.json):
  "mcp": {
    "servers": {
      "github": {"command": ["npx", "-y", "@modelcontextprotocol/server-github"],
                  "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "..."}}
    }
  }

Uso por chat: /mcp · /mcp conectar <nombre> · /mcp tools · /mcp llamar
<servidor> <tool> {json} · /mcp desconectar <nombre>.
"""
import json
import os
import subprocess
import threading

PROTOCOL_VERSION = "2024-11-05"


class MCPServer:
    """Un servidor MCP corriendo como subproceso stdio."""

    def __init__(self, name, command, env=None):
        self.name = name
        self.command = command
        self.env = env or {}
        self.proc = None
        self.tools = []
        self._id = 0
        self._lock = threading.Lock()
        self._pending = {}  # id -> (Event, box)

    # ── transporte ──
    def start(self, timeout=30):
        full_env = dict(os.environ)
        full_env.update({k: str(v) for k, v in self.env.items()})
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            self.command, shell=isinstance(self.command, str),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=full_env,
            text=True, encoding="utf-8", bufsize=1, creationflags=flags)
        threading.Thread(target=self._reader, daemon=True,
                         name=f"mcp-{self.name}").start()
        result = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "claudy", "version": "4.0"},
        }, timeout=timeout)
        self._notify("notifications/initialized")
        self.tools = (self._request("tools/list", {}, timeout=timeout)
                      .get("tools", []))
        return result.get("serverInfo", {})

    def _reader(self):
        try:
            for line in self.proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                mid = msg.get("id")
                if mid is None:
                    continue  # notificación del servidor: se ignora en v1
                with self._lock:
                    pending = self._pending.pop(mid, None)
                if pending:
                    ev, box = pending
                    box["msg"] = msg
                    ev.set()
        except Exception:
            pass

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        self._send(msg)

    def _request(self, method, params, timeout=30):
        with self._lock:
            self._id += 1
            mid = self._id
            ev, box = threading.Event(), {}
            self._pending[mid] = (ev, box)
        self._send({"jsonrpc": "2.0", "id": mid, "method": method,
                    "params": params or {}})
        if not ev.wait(timeout):
            with self._lock:
                self._pending.pop(mid, None)
            raise RuntimeError(f"{self.name}: sin respuesta a {method} en {timeout}s")
        msg = box["msg"]
        if "error" in msg:
            err = msg["error"]
            raise RuntimeError(f"{self.name}: {err.get('message', err)}")
        return msg.get("result", {})

    # ── API ──
    def call_tool(self, tool_name, arguments, timeout=60):
        """Llama una tool y devuelve el texto concatenado del resultado."""
        result = self._request("tools/call",
                               {"name": tool_name, "arguments": arguments or {}},
                               timeout=timeout)
        parts = []
        for block in result.get("content", []):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        if result.get("isError"):
            return "Error de la tool MCP: " + ("\n".join(parts) or "?")
        return "\n".join(parts) or json.dumps(result, ensure_ascii=False)[:1500]

    def close(self):
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except Exception:
                    self.proc.kill()
        except Exception:
            pass
        # Cerrar los pipes stdin/stdout para no dejar fds abiertos (ResourceWarning).
        if self.proc:
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                try:
                    if stream:
                        stream.close()
                except Exception:
                    pass
        self.proc = None

    @property
    def alive(self):
        return bool(self.proc and self.proc.poll() is None)


class MCPMixin:

    def _mcp_config(self):
        try:
            with open(os.path.join(os.path.expanduser("~"), ".claudy", "config.json"),
                      encoding="utf-8-sig") as f:
                return (json.load(f).get("mcp") or {}).get("servers") or {}
        except Exception:
            return {}

    def _mcp_connect(self, name):
        servers = self._mcp_config()
        spec = servers.get(name)
        if not spec:
            disponibles = ", ".join(servers) or "(ninguno configurado)"
            return (f"No hay un servidor MCP '{name}' en config.json.\n"
                    f"Configurados: {disponibles}")
        registry = getattr(self, "_mcp_servers", None)
        if registry is None:
            registry = self._mcp_servers = {}
        old = registry.get(name)
        if old and old.alive:
            return f"'{name}' ya está conectado ({len(old.tools)} tools)."
        srv = MCPServer(name, spec.get("command"), spec.get("env"))
        try:
            info = srv.start()
        except Exception as e:
            srv.close()
            return f"No pude conectar '{name}': {e}"
        registry[name] = srv
        # Registrar cada tool del servidor en el TOOL_REGISTRY del LLM
        for t in srv.tools:
            tool_id = f"mcp_{name}_{t['name']}"

            def _handler(_self, __srv=srv, __tool=t["name"], **kwargs):
                try:
                    return __srv.call_tool(__tool, kwargs)
                except Exception as e:
                    return f"Error MCP: {e}"

            self.register_tool(
                tool_id, _handler,
                f"[MCP {name}] {t.get('description', t['name'])[:200]}",
                t.get("inputSchema") or {"type": "object", "properties": {}})
        nombres = ", ".join(t["name"] for t in srv.tools[:12])
        return (f"🔌 Conectado a '{name}' "
                f"({info.get('name', '?')} v{info.get('version', '?')}): "
                f"{len(srv.tools)} tools registradas.\n{nombres}")

    def _mcp_disconnect(self, name):
        registry = getattr(self, "_mcp_servers", {}) or {}
        srv = registry.pop(name, None)
        if not srv:
            return f"'{name}' no estaba conectado."
        for t in srv.tools:
            self.TOOL_REGISTRY.pop(f"mcp_{name}_{t['name']}", None)
        srv.close()
        return f"Desconectado '{name}' (sus tools fueron des-registradas)."

    def _mcp_cmd(self, arg):
        arg = (arg or "").strip()
        servers = self._mcp_config()
        registry = getattr(self, "_mcp_servers", {}) or {}
        if not arg:
            if not servers:
                return ("🔌 MCP: sin servidores configurados.\n"
                        "Agrega en ~/.claudy/config.json:\n"
                        '  "mcp": {"servers": {"github": {"command": '
                        '["npx", "-y", "@modelcontextprotocol/server-github"], '
                        '"env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "..."}}}}\n'
                        "y conecta con: /mcp conectar github")
            lines = ["🔌 Servidores MCP:"]
            for name in servers:
                srv = registry.get(name)
                estado = (f"conectado, {len(srv.tools)} tools"
                          if srv and srv.alive else "desconectado")
                lines.append(f"  - {name}: {estado}")
            lines.append("\n/mcp conectar <nombre> · /mcp tools · "
                         "/mcp llamar <srv> <tool> {json} · /mcp desconectar <nombre>")
            return "\n".join(lines)
        parts = arg.split(None, 1)
        sub = parts[0].lower()
        resto = parts[1].strip() if len(parts) > 1 else ""
        if sub in ("conectar", "connect"):
            return self._mcp_connect(resto) if resto else "Uso: /mcp conectar <nombre>"
        if sub in ("desconectar", "disconnect"):
            return self._mcp_disconnect(resto) if resto else "Uso: /mcp desconectar <nombre>"
        if sub == "tools":
            lines = []
            for name, srv in registry.items():
                if resto and name != resto:
                    continue
                for t in srv.tools:
                    lines.append(f"  mcp_{name}_{t['name']} — {t.get('description', '')[:80]}")
            return ("🧰 Tools MCP registradas:\n" + "\n".join(lines)) if lines else \
                "No hay tools MCP registradas. Conecta un servidor: /mcp conectar <nombre>"
        if sub in ("llamar", "call"):
            bits = resto.split(None, 2)
            if len(bits) < 2:
                return "Uso: /mcp llamar <servidor> <tool> {json de argumentos}"
            srv = registry.get(bits[0])
            if not srv or not srv.alive:
                return f"'{bits[0]}' no está conectado (/mcp conectar {bits[0]})."
            try:
                args = json.loads(bits[2]) if len(bits) > 2 else {}
            except Exception:
                return "Los argumentos deben ser JSON válido. Ej: {\"query\": \"claudy\"}"
            try:
                return srv.call_tool(bits[1], args)[:3500]
            except Exception as e:
                return f"Error: {e}"
        return "Subcomando desconocido. Usa /mcp para ver la ayuda."
