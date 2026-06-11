"""Claudy core.llm — Capa de proveedores de IA (extraído de pet.py, refactor v5).

Cadena de resolución de respuestas:
  1. OpenCode local (http://127.0.0.1:4096) si baseUrl es local
  2. Proveedor remoto del modelo activo (Anthropic / OpenAI / DeepSeek / Google)
     con pool de credenciales y cadena de fallback configurable
  3. Pollinations (gratuito, terceros) SOLO si providers.allowFreeFallback=true

Incluye el registro de tools (TOOL_REGISTRY) para function-calling nativo.
Se usa como mixin: ClawdPet hereda de LLMMixin. Depende de self._save_memory,
self._build_memory_context (core.memory), self._get_superpowers, self._fire_hook,
self._debug_log y self._tts_say definidos en la clase compuesta.
"""
import base64
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from model_router import pick_model as _route_model
except Exception:
    def _route_model(_prompt, _config, fallback):
        return fallback

from core.prompts import BASE_IDENTITY


def extract_text(response):
    """Extrae el texto de una respuesta en cualquier formato conocido:
    OpenCode (parts), OpenAI (choices), Anthropic (content[]) o directo.
    Antes esta lógica estaba copiada 3 veces en send_quick_message."""
    if not isinstance(response, dict):
        return str(response or "").strip()
    parts = response.get("parts")
    if parts:
        text = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
        if text:
            return text
    choices = response.get("choices")
    if choices and isinstance(choices, list):
        text = (choices[0].get("message", {}) or {}).get("content", "")
        if isinstance(text, str) and text.strip():
            return text.strip()
    content = response.get("content", "")
    if isinstance(content, list):
        text = "\n".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
        if text:
            return text
    elif isinstance(content, str) and content.strip():
        return content.strip()
    return (response.get("text", "") or "").strip()


class LLMMixin:
    def build_auth_headers(self, config):
        headers = {"Content-Type": "application/json"}
        opencode = config["opencode"]
        if opencode.get("apiKey"):
            headers["Authorization"] = f'Bearer {opencode["apiKey"]}'
        elif opencode.get("password"):
            user = opencode.get("username") or "opencode"
            token = base64.b64encode(f'{user}:{opencode["password"]}'.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        return headers

    def request_json(self, url, payload, config, timeout=60):
        body = json.dumps(payload).encode("utf-8")
        headers = self.build_auth_headers(config)
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as error:
            raise RuntimeError("no pude conectar con el cerebro remoto") from error
        self._debug_log("RAW RESPONSE", raw)
        return json.loads(raw) if raw else {}

    def ping_opencode(self, base_url, config, timeout=1.5):
        headers = self.build_auth_headers(config)
        request = urllib.request.Request(f"{base_url}/provider", headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout):
                return True
        except Exception:
            return False

    def ensure_opencode_server(self, base_url, config):
        if self.ping_opencode(base_url, config):
            return
        opencode_path = self.find_opencode_command()
        if not opencode_path:
            raise RuntimeError("no encuentro al oráculo en este equipo")
        parsed = urllib.parse.urlparse(base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 4096
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.opencode_process = subprocess.Popen(
            [opencode_path, "serve", "--port", str(port), "--hostname", host],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags,
        )
        for _ in range(50):
            if self.ping_opencode(base_url, config):
                return
            time.sleep(0.2)
        raise RuntimeError("el cerebro remoto no despertó a tiempo")

    def find_opencode_command(self):
        return (
            shutil.which("opencode.exe")
            or shutil.which("opencode.cmd")
            or shutil.which("opencode.bat")
            or shutil.which("opencode")
        )

    # ── Router de modelos (/router): ver, encender/apagar, asignar modelos ──
    def _router_cmd(self, arg):
        from model_router import classify, CATEGORIES
        arg = (arg or "").strip()
        config_path = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception:
            data = {}
        router = data.setdefault("router", {})

        def _save():
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        low = arg.lower()
        if not arg:
            estado = "ON" if router.get("enabled") else "OFF"
            default = data.get("opencode", {}).get("defaultModel", "?")
            lines = [f"🔀 Router de modelos: {estado}", ""]
            for cat in ("simple", "code", "complex"):
                lines.append(f"  {cat:<8} → {router.get(cat) or f'(default: {default})'}")
            lines.append(f"  default  → {default}")
            lines += ["", "Comandos:",
                      "  /router on | off",
                      "  /router simple|code|complex <modelo>",
                      "  /router probar <frase>"]
            return "\n".join(lines)
        if low in ("on", "off"):
            router["enabled"] = (low == "on")
            _save()
            return f"🔀 Router de modelos: {'ON' if router['enabled'] else 'OFF'}"
        if low.startswith(("probar ", "test ")):
            frase = arg.split(None, 1)[1]
            cat = classify(frase)
            default = data.get("opencode", {}).get("defaultModel", "?")
            modelo = (router.get(cat) or default) if router.get("enabled") else default
            return (f"Categoría: {cat}\nModelo que usaría: {modelo}"
                    + ("" if router.get("enabled") else "\n(router OFF: usa el default)"))
        parts = arg.split(None, 1)
        if parts[0].lower() in CATEGORIES and len(parts) == 2:
            router[parts[0].lower()] = parts[1].strip()
            _save()
            return f"🔀 {parts[0].lower()} → {parts[1].strip()}"
        return ("Uso: /router | /router on|off | /router simple|code|complex <modelo> "
                "| /router probar <frase>")

    TOOL_REGISTRY = {}  # name -> {"handler": fn, "description": str, "schema": dict}

    @classmethod
    def register_tool(cls, name, handler, description, parameters=None):
        cls.TOOL_REGISTRY[name] = {
            "handler": handler,
            "description": description,
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters or {"type": "object", "properties": {}},
                },
            },
        }

    def send_quick_message(self, prompt, _skip_skill_action=False, timeout=90, on_delta=None, max_tokens=None, tier=None):
        # Check for local skill commands first
        if not _skip_skill_action:
            handled, result = self._try_handle_skill_action(prompt)
            if handled:
                self._save_memory("Usuario", prompt)
                self._save_memory("Claudy", result)
                self._fire_hook("on_response", user=prompt, response=result, source="skill")
                try:
                    self.after(0, lambda: self._set_state_briefly("happy", 800))
                except Exception:
                    pass
                if self._voice_enabled:
                    self._tts_say(result)
                return result

        self._save_memory("Usuario", prompt)
        self._fire_hook("on_message", user=prompt)
        config = self.load_claudy_config()
        # Permitir subir el límite de tokens para respuestas largas (p.ej. informes
        # extensos de 4000+ palabras que con el default de 4096 se cortaban a la mitad).
        if max_tokens:
            try:
                config = dict(config)
                config["agent"] = dict(config.get("agent", {}))
                config["agent"]["maxTokens"] = int(max_tokens)
            except Exception:
                pass
        opencode = config["opencode"]
        base_url = opencode.get("baseUrl", "http://127.0.0.1:4096").rstrip("/")
        model = self._current_model or opencode.get("defaultModel", "deepseek-chat")
        # P3-2: Model router por complejidad (estilo AFM 3 de Apple):
        #  - tier="fast": llamada interna de máquina (resúmenes, evaluaciones,
        #    extracción de entidades) → modelo barato/rápido del router.
        #  - Chat del usuario (sin _skip_skill_action): clasificar y rutear
        #    (simple/code → barato, complejo → modelo de razonamiento).
        #  - Llamadas internas largas (secciones de informes, etc.) NO se
        #    rutean: conservan el modelo default para no romper sus timeouts.
        _router_cfg = config.get("router") or {}
        _default_model = model
        if tier == "fast" and _router_cfg.get("enabled") and _router_cfg.get("simple"):
            model = _router_cfg["simple"]
        elif not _skip_skill_action:
            model = _route_model(prompt, config, model)
        if model != _default_model:
            # Los modelos de razonamiento tardan más: dar margen extra de timeout.
            timeout = max(timeout, 150)
            self._debug_log("MODEL ROUTER", f"{_default_model} -> {model} (tier={tier})")

        is_local = any(h in base_url for h in ("127.0.0.1", "localhost", "0.0.0.0"))
        context = self._build_memory_context(prompt)
        superpowers = self._get_superpowers()
        # Prompt único: la identidad base vive en core/prompts.py (antes había
        # una copia divergente hardcodeada aquí).
        base_sys = config["agent"].get("systemPrompt") or BASE_IDENTITY
        local_skills = self._load_installed_skills()
        try:
            from qcore_products import build_company_context
            company_ctx = build_company_context() + "\n\n"
        except Exception:
            company_ctx = ""
        enhanced_sys = superpowers + local_skills + company_ctx + base_sys
        # Auto-detect product mention — robust matching with variations
        _detected_product = None
        try:
            from qcore_products import build_context_prompt, PRODUCT_CONTEXTS
            plow = prompt.lower().replace("-", " ").replace("_", " ")
            # Map of aliases → canonical product name
            _product_aliases = {
                "smartstudent": "SmartStudent",
                "smart student": "SmartStudent",
                "roadix": "Roadix",
                "luxium": "Luxium",
                "unitcore": "UnitCore",
                "unit core": "UnitCore",
                "campaign studio": "Campaign Studio",
                "campaignstudio": "Campaign Studio",
                "mission control": "Mission Control",
                "missioncontrol": "Mission Control",
                "point": "Point",
                "mi portafolio": "Mi Portafolio",
                "portafolio": "Mi Portafolio",
                "portfolio": "Mi Portafolio",
            }
            for alias, canonical in _product_aliases.items():
                if alias in plow:
                    _detected_product = canonical
                    self._active_product = canonical
                    self._product_context = build_context_prompt(canonical)
                    break
        except Exception:
            pass
        # Inject active QCORE product context (detailed) into system prompt
        product_ctx = getattr(self, "_product_context", "")
        if product_ctx:
            enhanced_sys += "\n\n" + product_ctx
        # Also inject into user prompt so the AI MUST use this info
        if _detected_product and product_ctx:
            prompt = f"[IMPORTANTE: Responde usando SOLO la información del producto {_detected_product} de QCORE SPA que tienes en tu contexto. NO busques información externa ni confundas con otros productos de otras empresas.]\n\n{prompt}"

        if is_local:
            try:
                self.ensure_opencode_server(base_url, config)
                if not self.quick_session_id:
                    created = self.request_json(
                        f"{base_url}/session", {"title": "Claudy Desktop"}, config, timeout=12,
                    )
                    self.quick_session_id = created.get("id")
                    if not self.quick_session_id:
                        raise RuntimeError("el oraculo no abrio la puerta")

                provider_id, _, model_id = model.partition("/")
                full_prompt = context + f"Usuario: {prompt}\nClaudy:" if context else prompt
                payload = {
                    "model": {"providerID": provider_id, "modelID": model_id or provider_id},
                    "system": enhanced_sys,
                    "tools": {
                        "bash": True, "read": True, "glob": True, "grep": True, "webfetch": True,
                        "edit": False, "task": False, "todowrite": False,
                        "websearch": True, "codesearch": True, "lsp": False, "skill": False,
                    },
                    "parts": [{"type": "text", "text": full_prompt}],
                }
                endpoint = f"{base_url}/session/{self.quick_session_id}/message"
                response = self.request_json(endpoint, payload, config, timeout=timeout)
                if response.get("info", {}).get("error"):
                    error = response["info"]["error"]
                    raise RuntimeError(error.get("data", {}).get("message") or error.get("name") or "el oraculo se quedo dormido")
            except Exception as local_err:
                self._debug_log("LOCAL OPENCODE FAILED, FALLING BACK TO REMOTE", str(local_err))
                # Auto-fallback to remote credentials if local server times out/fails
                response = self._call_remote_provider(model, enhanced_sys, context, prompt, config, on_delta=on_delta, timeout=timeout)
        else:
            # Multi-provider remote path
            response = self._call_remote_provider(model, enhanced_sys, context, prompt, config, on_delta=on_delta, timeout=timeout)

        text = extract_text(response)

        # Dynamic fallback: If local server returned empty response, call remote provider
        if not text and is_local:
            self._debug_log("LOCAL OPENCODE RETURNED EMPTY TEXT, FALLING BACK TO REMOTE")
            try:
                response = self._call_remote_provider(model, enhanced_sys, context, prompt, config, timeout=timeout)
                text = extract_text(response)
            except Exception as remote_err:
                text = ""
                self._debug_log("REMOTE FALLBACK ALSO FAILED", str(remote_err))

        # Último fallback: Pollinations (API gratuita de TERCEROS — manda el
        # prompt fuera de tus proveedores). Por privacidad es OPT-IN:
        # config.providers.allowFreeFallback = true para activarlo.
        allow_free = bool(config.get("providers", {}).get("allowFreeFallback", False))
        if (not text or text.startswith("Error ")) and allow_free:
            try:
                poll_payload = {
                    "model": "openai",
                    "messages": [
                        {"role": "system", "content": enhanced_sys[:3000]},
                        {"role": "user", "content": (context + prompt)[:12000] if context else prompt[:12000]},
                    ],
                    "max_tokens": 2000,
                }
                req = urllib.request.Request(
                    "https://text.pollinations.ai/openai",
                    data=json.dumps(poll_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "Claudy/1.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    poll_data = json.loads(resp.read().decode("utf-8"))
                choices = poll_data.get("choices") or []
                if choices:
                    msg = choices[0].get("message") or {}
                    poll_text = msg.get("content", "").strip()
                    if poll_text:
                        text = poll_text
                if not text:
                    text = poll_data.get("response", "").strip()
            except Exception as poll_err:
                self._debug_log("POLLINATIONS FALLBACK ALSO FAILED", str(poll_err))

        answer = text or "El oraculo me dejo en visto..."
        self._save_memory("Claudy", answer)
        self._fire_hook("on_response", user=prompt, response=answer, source="llm")
        # Bucle de auto-mejora: registra qué skills fueron relevantes y, al cruzar
        # el umbral, dispara un refinamiento solo (en background, sin bloquear).
        if not self._refining_skill:
            try:
                threading.Thread(
                    target=self._record_skill_usage, args=(prompt,), daemon=True,
                    name="skill-usage").start()
            except Exception:
                pass
        # Animacion: feliz brevemente, luego talking si hay voz, sino idle
        try:
            if self._voice_enabled:
                self.after(0, lambda: self._set_state_briefly("happy", 600))
                self.after(700, lambda: self._set_state_briefly("talking", max(1500, min(8000, len(answer) * 60))))
            else:
                self.after(0, lambda: self._set_state_briefly("happy", 1200))
        except Exception:
            pass
        if self._voice_enabled:
            self._tts_say(answer)
        return answer

    def _detect_provider(self, model):
        """Detect provider and return (provider_key, api_url, is_anthropic, is_openai_compat)."""
        m = model.lower()
        if "claude" in m or "anthropic" in m:
            return ("anthropic", "https://api.anthropic.com/v1/messages", True, False)
        if "deepseek" in m:
            return ("deepseek", "https://api.deepseek.com/v1/chat/completions", False, True)
        if "gemini" in m or "google" in m:
            return ("google", "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent", False, False)
        # Default: OpenAI or OpenAI-compatible
        return ("openai", "https://api.openai.com/v1/chat/completions", False, True)

    def _get_provider_keys(self, config, provider):
        """Get API keys for a provider with credential pooling support."""
        provider_cfg = config.get("providers", {}).get(provider, {})
        keys = provider_cfg.get("keys", [])
        if not keys:
            single = provider_cfg.get("key", "") or config.get(provider, {}).get("apiKey", "")
            if single:
                keys = [single]
        if not keys:
            # Fallback to opencode.apiKey (covers DeepSeek, etc.)
            opencode_key = config.get("opencode", {}).get("apiKey", "")
            if opencode_key:
                keys = [opencode_key]
        if not keys:
            env_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "google": "GOOGLE_API_KEY",
            }
            env_key = os.environ.get(env_map.get(provider, ""), "")
            if env_key:
                keys = [env_key]
        return keys

    def _call_remote_provider(self, model, system_prompt, context, user_prompt, config, on_delta=None, max_tokens_override=None, timeout=90):
        """Call remote AI provider with credential pooling, retry, and inter-provider fallback."""
        last_error = None

        # Build provider chain: primary model first, then fallback list from config.
        primary = (model, *self._detect_provider(model))
        chain = [primary]
        fallbacks = config.get("providers", {}).get("fallback", [])
        if isinstance(fallbacks, list):
            for fb_model in fallbacks:
                if not fb_model or fb_model == model:
                    continue
                chain.append((fb_model, *self._detect_provider(fb_model)))

        for fb_model, provider, api_url, is_anthropic, is_openai_compat in chain:
            keys = self._get_provider_keys(config, provider)
            if not keys:
                last_error = RuntimeError(f"No API key configured for {provider}")
                continue
            # Strip provider prefix for the actual API call
            actual_model = fb_model.partition("/")[2] if "/" in fb_model else fb_model
            for key in keys:
                try:
                    return self._call_provider_api(provider, api_url, is_anthropic, is_openai_compat, actual_model, system_prompt, context, user_prompt, key, config, on_delta=on_delta, timeout=timeout)
                except Exception as e:
                    last_error = e
                    continue

        raise RuntimeError(f"All providers/keys exhausted. Last error: {last_error}")

    def _call_provider_api(self, provider, api_url, is_anthropic, is_openai_compat, model, system_prompt, context, user_prompt, key, config, on_delta=None, timeout=90):
        """Make a single API call to a provider."""
        if is_anthropic:
            return self._call_anthropic(api_url, model, system_prompt, context, user_prompt, key, config, timeout=timeout)
        elif is_openai_compat:
            return self._call_openai_compat(api_url, model, system_prompt, context, user_prompt, key, config, on_delta=on_delta, timeout=timeout)
        else:
            return self._call_generic(api_url, model, system_prompt, context, user_prompt, key, provider, timeout=timeout)

    def _anthropic_tool_schemas(self):
        """Convert OpenAI-style registry to Anthropic tool format."""
        out = []
        for name, info in self.TOOL_REGISTRY.items():
            fn = info["schema"]["function"]
            out.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return out

    def _execute_tool_calls_and_followup(self, tool_calls, base_payload, headers, endpoint, is_anthropic):
        """Run each tool call and POST a follow-up with the tool results.
        Returns the final response JSON."""
        import urllib.request as r
        if is_anthropic:
            tool_result_blocks = []
            assistant_blocks = []
            for tc in tool_calls:
                tid = tc.get("id")
                name = tc.get("name")
                inp = tc.get("input", {}) or {}
                info = self.TOOL_REGISTRY.get(name)
                try:
                    result = info["handler"](self, **inp) if info else f"Tool '{name}' not found."
                except Exception as e:
                    result = f"Error: {e}"
                assistant_blocks.append({"type": "tool_use", "id": tid, "name": name, "input": inp})
                tool_result_blocks.append({"type": "tool_result", "tool_use_id": tid, "content": str(result)[:4000]})
            messages = list(base_payload.get("messages", []))
            messages.append({"role": "assistant", "content": assistant_blocks})
            messages.append({"role": "user", "content": tool_result_blocks})
            payload = dict(base_payload)
            payload["messages"] = messages
            req = r.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with r.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())
        else:
            messages = list(base_payload.get("messages", []))
            messages.append({"role": "assistant", "tool_calls": tool_calls, "content": None})
            for tc in tool_calls:
                tid = tc.get("id")
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments", "{}") or "{}")
                except Exception:
                    args = {}
                info = self.TOOL_REGISTRY.get(name)
                try:
                    result = info["handler"](self, **args) if info else f"Tool '{name}' not found."
                except Exception as e:
                    result = f"Error: {e}"
                messages.append({"role": "tool", "tool_call_id": tid, "content": str(result)[:4000]})
            payload = dict(base_payload)
            payload["messages"] = messages
            payload.pop("tools", None)  # avoid recursive tool use
            req = r.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with r.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())

    def _call_openai_compat(self, api_url, model, system_prompt, context, user_prompt, key, config=None, on_delta=None, timeout=90):
        """Call OpenAI-compatible API."""
        endpoint = api_url
        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": user_prompt})
        max_tokens = (config or {}).get("agent", {}).get("maxTokens", 4096)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }
        # P2-2: native function calling
        tools_enabled = bool((config or {}).get("tools", {}).get("enableFunctionCalling", False))
        if tools_enabled and self.TOOL_REGISTRY:
            payload["tools"] = self._get_tool_schemas()
            payload["tool_choice"] = "auto"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }
        # Streaming path: only when a delta callback is provided and tools are off.
        if on_delta is not None and not (tools_enabled and self.TOOL_REGISTRY):
            try:
                return self._stream_openai_compat(endpoint, payload, headers, on_delta)
            except Exception:
                pass  # fall back to a normal blocking request on any streaming error
        import urllib.request as r
        req = r.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with r.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        if tools_enabled:
            choices = data.get("choices") or []
            if choices:
                msg = choices[0].get("message", {})
                tcs = msg.get("tool_calls") or []
                if tcs:
                    return self._execute_tool_calls_and_followup(tcs, payload, headers, endpoint, is_anthropic=False)
        return data

    def _call_anthropic(self, api_url, model, system_prompt, context, user_prompt, key, config=None, timeout=90):
        """Call Anthropic Messages API with prompt caching."""
        cache_control = {"type": "ephemeral"}
        max_tokens = (config or {}).get("agent", {}).get("maxTokens", 4096)
        payload = {
            "model": model,
            "system": [
                {"type": "text", "text": system_prompt, "cache_control": cache_control},
            ],
            "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
            "max_tokens": max_tokens,
        }
        if context:
            payload["system"].append({"type": "text", "text": context, "cache_control": cache_control})
        tools_enabled = bool((config or {}).get("tools", {}).get("enableFunctionCalling", False))
        if tools_enabled and self.TOOL_REGISTRY:
            payload["tools"] = self._anthropic_tool_schemas()
        headers = {
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "prompt-caching-2024-07-31",
        }
        import urllib.request as r
        req = r.Request(api_url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with r.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        if tools_enabled and data.get("stop_reason") == "tool_use":
            tool_uses = [b for b in data.get("content", []) if b.get("type") == "tool_use"]
            if tool_uses:
                return self._execute_tool_calls_and_followup(tool_uses, payload, headers, api_url, is_anthropic=True)
        return data

    def _call_generic(self, api_url, model, system_prompt, context, user_prompt, key, provider, timeout=90):
        """Generic API call for providers like Google."""
        raise RuntimeError(f"Provider {provider} not fully implemented yet. Use OpenAI-compatible providers like DeepSeek or Anthropic.")

