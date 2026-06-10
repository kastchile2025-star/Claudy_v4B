"""Claudy core.gateway — Gateway HTTP local (extraído de pet.py, refactor v5).

Servidor HTTP en 127.0.0.1:8720 (configurable en config.gateway). Es el
contrato estable entre la app de escritorio y los canales externos:
  POST /api            {"message": "..."}  -> {"response": "..."}
  GET  /health         estado del gateway
  GET  /               mini chat web (WEBCHAT_HTML)
Autenticación opcional por Bearer token (gateway.authToken).

El bot de Telegram (channels/) consume este API como proceso independiente.
Se usa como mixin: ClawdPet hereda de GatewayMixin.
"""
import http.server
import json
import re
import threading
import time


WEBCHAT_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claudy WebChat</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Segoe UI,sans-serif;background:#0d0d1a;color:#e8e8f0;display:flex;height:100vh}
#chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:12px 16px;border-radius:12px;line-height:1.5;white-space:pre-wrap;word-break:break-word}
.user{align-self:flex-end;background:#7c6bff;color:#fff;border-bottom-right-radius:4px}
.bot{align-self:flex-start;background:#161622;border:1px solid #2a2a40;border-bottom-left-radius:4px}
#input-area{display:flex;padding:12px;gap:8px;background:#0f0f1a;border-top:1px solid #2a2a40}
#msg{flex:1;padding:10px 14px;border-radius:8px;border:1px solid #2a2a40;background:#0f0f1a;color:#e8e8f0;font-size:14px;outline:none}
#msg:focus{border-color:#7c6bff}
#send{background:#7c6bff;color:#fff;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-weight:600}
#send:hover{background:#5e4be0}
.loading{color:#8a8aa3;font-style:italic;padding:8px}
</style>
</head>
<body>
<div style="display:flex;flex-direction:column;flex:1;max-width:700px;margin:0 auto">
<header style="padding:16px;text-align:center;border-bottom:1px solid #2a2a40">
  <h1 style="color:#7c6bff;font-size:20px">Claudy WebChat</h1>
</header>
<div id="chat"></div>
<div id="input-area">
  <input id="msg" placeholder="Escribe aqui..." onkeydown="if(event.key==='Enter')send()">
  <button id="send" onclick="send()">Enviar</button>
</div>
</div>
<script>
async function send(){
  const inp=document.getElementById('msg');
  const msg=inp.value.trim();
  if(!msg)return;
  inp.value='';
  addMsg(msg,'user');
  const ld=addMsg('...','loading');
  try{
    const r=await fetch('http://127.0.0.1:8720/api',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg})
    });
    const d=await r.json();
    ld.remove();
    addMsg(d.response,'bot');
  }catch(e){
    ld.remove();
    addMsg('Error: no se pudo conectar con Claudy. Asegurate de que la app este abierta.','bot');
  }
}
function addMsg(text,cls){
  const d=document.createElement('div');
  d.className='msg '+cls;
  d.textContent=text;
  document.getElementById('chat').appendChild(d);
  d.scrollIntoView({behavior:'smooth'});
  return d;
}
</script>
</body>
</html>"""


class GatewayMixin:
    def _start_gateway(self):
        """Start HTTP API server. Configurable bind and auth."""
        if self._gateway_server:
            return
        # Read gateway config
        try:
            config = self.load_claudy_config()
            gw = config.get("gateway", {})
            if gw.get("public", False):
                self._gateway_bind_ip = "0.0.0.0"
            self._gateway_auth_token = gw.get("authToken", None)
            port = gw.get("port", 8720)
            if port:
                self._gateway_port = port
        except Exception:
            pass
        import http.server

        pet = self

        class GatewayHandler(http.server.BaseHTTPRequestHandler):
            def _check_gateway_auth(_self):
                """Check auth token if configured. Returns True if authorized."""
                if not pet._gateway_auth_token:
                    return True
                auth = _self.headers.get("Authorization", "")
                return auth == f"Bearer {pet._gateway_auth_token}"

            def do_POST(_self):
                if not _self._check_gateway_auth():
                    _self.send_response(401)
                    _self.end_headers()
                    _self.wfile.write(json.dumps({"error": "Unauthorized"}).encode("utf-8"))
                    return
                try:
                    length = int(_self.headers.get("Content-Length", 0))
                    body = _self.rfile.read(length).decode("utf-8")
                    data = json.loads(body)
                    # OpenAI-compatible endpoint
                    if _self.path == "/v1/chat/completions":
                        msgs = data.get("messages", [])
                        user_msgs = [m for m in msgs if m.get("role") == "user"]
                        if not user_msgs:
                            raise ValueError("No user message in messages[]")
                        last_user = user_msgs[-1].get("content", "")
                        if isinstance(last_user, list):
                            last_user = " ".join(p.get("text", "") for p in last_user if isinstance(p, dict))
                        handled, result = pet._try_handle_skill_action(last_user)
                        if not handled:
                            result = pet.send_quick_message(last_user)
                        result = pet._process_embedded_commands(result)
                        result = pet._strip_markdown(result)
                        model_name = data.get("model", "claudy")
                        cmpl_id = f"chatcmpl-{int(time.time())}"
                        created = int(time.time())

                        # Streaming SSE (lo que Open WebUI / LobeChat esperan con stream:true)
                        if data.get("stream"):
                            _self.send_response(200)
                            _self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                            _self.send_header("Cache-Control", "no-cache")
                            _self.send_header("Connection", "keep-alive")
                            _self.send_header("Access-Control-Allow-Origin", "*")
                            _self.end_headers()

                            def _sse(payload):
                                _self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
                                _self.wfile.flush()

                            def _chunk(delta, finish=None):
                                return {
                                    "id": cmpl_id, "object": "chat.completion.chunk",
                                    "created": created, "model": model_name,
                                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                                }
                            try:
                                _sse(_chunk({"role": "assistant"}))
                                # trocea por palabras para un streaming fluido y fiable
                                tokens = re.findall(r"\S+\s*", result) or ([result] if result else [])
                                for tk in tokens:
                                    _sse(_chunk({"content": tk}))
                                _sse(_chunk({}, finish="stop"))
                                _self.wfile.write(b"data: [DONE]\n\n")
                                _self.wfile.flush()
                            except (BrokenPipeError, ConnectionResetError):
                                pass
                            return

                        resp = {
                            "id": cmpl_id,
                            "object": "chat.completion",
                            "created": created,
                            "model": model_name,
                            "choices": [{
                                "index": 0,
                                "message": {"role": "assistant", "content": result},
                                "finish_reason": "stop",
                            }],
                            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        }
                        _self.send_response(200)
                        _self.send_header("Content-Type", "application/json")
                        _self.send_header("Access-Control-Allow-Origin", "*")
                        _self.end_headers()
                        _self.wfile.write(json.dumps(resp).encode("utf-8"))
                        return
                    # Native Claudy endpoint
                    msg = data.get("message", "")
                    channel = data.get("channel", "")
                    # El canal activo adapta el system prompt (p.ej. Telegram
                    # permite negritas/código; el escritorio usa texto plano).
                    pet._current_channel = channel or "gateway"
                    try:
                        handled, result = pet._try_handle_skill_action(msg)
                        if not handled:
                            result = pet.send_quick_message(msg)
                        result = pet._process_embedded_commands(result)
                    finally:
                        pet._current_channel = ""
                    if channel != "telegram":
                        # Telegram renderiza su propio formato (HTML); para el
                        # resto se mantiene el texto plano de siempre.
                        result = pet._strip_markdown(result)
                    _self.send_response(200)
                    _self.send_header("Content-Type", "application/json")
                    _self.send_header("Access-Control-Allow-Origin", "*")
                    _self.end_headers()
                    _self.wfile.write(json.dumps({"response": result}).encode("utf-8"))
                except Exception as e:
                    _self.send_response(500)
                    _self.send_header("Access-Control-Allow-Origin", "*")
                    _self.end_headers()
                    _self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

            def do_OPTIONS(_self):
                _self.send_response(200)
                _self.send_header("Access-Control-Allow-Origin", "*")
                _self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
                _self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                _self.end_headers()

            def do_GET(_self):
                if _self.path == "/v1/models":
                    _self.send_response(200)
                    _self.send_header("Content-Type", "application/json")
                    _self.send_header("Access-Control-Allow-Origin", "*")
                    _self.end_headers()
                    _self.wfile.write(json.dumps({
                        "object": "list",
                        "data": [{"id": "claudy", "object": "model", "created": int(time.time()), "owned_by": "claudy"}],
                    }).encode("utf-8"))
                    return
                if _self.path == "/api/health":
                    _self.send_response(200)
                    _self.send_header("Content-Type", "application/json")
                    _self.send_header("Access-Control-Allow-Origin", "*")
                    _self.end_headers()
                    _self.wfile.write(json.dumps({"status": "ok", "gateway": "Claudy", "version": "3.0"}).encode("utf-8"))
                    return
                if _self.path == "/" or _self.path == "":
                    _self.send_response(200)
                    _self.send_header("Content-Type", "text/html; charset=utf-8")
                    _self.end_headers()
                    _self.wfile.write(WEBCHAT_HTML.encode("utf-8"))
                else:
                    _self.send_response(200)
                    _self.send_header("Content-Type", "application/json")
                    _self.send_header("Access-Control-Allow-Origin", "*")
                    _self.end_headers()
                    _self.wfile.write(json.dumps({"status": "ok", "endpoint": "/api"}).encode("utf-8"))

            def log_message(_self, *args):
                pass

        def run():
            try:
                bind_ip = pet._gateway_bind_ip
                port = pet._gateway_port
                server = http.server.HTTPServer((bind_ip, port), GatewayHandler)
                pet._gateway_server = server
                print(f"[Gateway] Listening on {bind_ip}:{port}")
                server.serve_forever()
            except Exception as e:
                print(f"[Gateway] Error: {e}")

        threading.Thread(target=run, daemon=True, name="gateway-server").start()

