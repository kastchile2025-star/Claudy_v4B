"""Claudy WhatsApp Bot - standalone process via Meta Cloud API (stub)."""
import asyncio
import json
import os
import urllib.request
import sys

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)

cfg = load_config()
WHATSAPP_TOKEN = cfg.get("whatsapp", {}).get("accessToken", "")
WHATSAPP_PHONE_ID = cfg.get("whatsapp", {}).get("phoneNumberId", "")
WHATSAPP_VERIFY_TOKEN = cfg.get("whatsapp", {}).get("verifyToken", "claudy_webhook")
GATEWAY_URL = "http://127.0.0.1:8720/api"

if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
    print("[WhatsAppBot] No configurado. Necesitas accessToken y phoneNumberId en config.")
    sys.exit(0)

print("[WhatsAppBot] Config detectada. Para usar WhatsApp necesitas:")
print("  1. Una cuenta de Meta Business (business.facebook.com)")
print("  2. Configurar Webhook en Meta Developer Dashboard")
print("  3. URL del webhook: https://TU_IP:8720/whatsapp/webhook")
print(f"  4. Verify token: {WHATSAPP_VERIFY_TOKEN}")
print()
print("[WhatsAppBot] El bot completo requiere un servidor HTTPS publico.")
print("[WhatsAppBot] Usa ngrok o similar para exponer el puerto 8720.")

# Stub: the full implementation would:
# 1. Run an HTTP server to receive webhooks from Meta
# 2. Verify webhook with the verify token
# 3. For each incoming message, call ask_claudy() and reply via Cloud API

def ask_claudy(msg):
    try:
        req = urllib.request.Request(
            GATEWAY_URL,
            data=json.dumps({"message": msg}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=90)
        return json.loads(resp.read()).get("response", "Sin respuesta")
    except Exception as e:
        return f"Error: {e}"

def send_whatsapp(to_number, text):
    """Send a WhatsApp message via Cloud API."""
    url = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text[:4000]},
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers,
    )
    urllib.request.urlopen(req, timeout=30)

async def main():
    print("[WhatsAppBot] Modo stub - esperando integracion completa.")
    print(f"[WhatsAppBot] Token config: {WHATSAPP_PHONE_ID}")
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
