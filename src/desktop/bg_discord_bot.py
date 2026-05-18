"""Claudy Discord Bot - standalone process communicating via Gateway API."""
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
TOKEN = cfg.get("discord", {}).get("botToken", "")
ALLOWED = [str(u) for u in cfg.get("discord", {}).get("allowedUsers", [])]
ALLOWED_DM = cfg.get("discord", {}).get("allowDM", True)
GATEWAY_URL = "http://127.0.0.1:8720/api"

if not TOKEN:
    print("[DiscordBot] No token configured. Exiting.")
    sys.exit(0)

import discord

class ClaudyDiscord(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f"[DiscordBot] Conectado como {self.user}")

    def ask_claudy(self, msg):
        try:
            req = urllib.request.Request(
                GATEWAY_URL,
                data=json.dumps({"message": msg}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=90)
            return json.loads(resp.read()).get("response", "Sin respuesta")
        except Exception as e:
            return f"Error conectando con Claudy: {e}"

    async def on_message(self, message):
        if message.author == self.user:
            return

        uid = str(message.author.id)
        uname = message.author.name

        # Only respond to DMs unless allowed in guild channels
        if message.guild is not None and not ALLOWED_DM:
            if uid not in ALLOWED:
                return

        if ALLOWED and uid not in ALLOWED:
            await message.channel.send(
                f"Hola {uname}. No estas autorizado.\nTu ID: {uid}\n"
                "Pedi al dueno que ejecute /vincular_discord {uid} en Claudy Desktop."
            )
            return

        msg = message.content.strip()
        if not msg:
            return

        # Help commands
        if msg.lower() in ("/atajos", "/help", "/ayuda", "!atajos", "!help"):
            await message.channel.send(
                "Claudy Discord Bot\n\n"
                "Comandos:\n"
                "/disco - Espacio en disco\n"
                "/cmd <comando> - Ejecutar comando shell\n"
                "/buscar <tema> - Buscar en internet\n"
                "/checkpoint - Guardar estado\n"
                "/rollback - Deshacer\n\n"
                "O simplemente preguntame lo que necesites!"
            )
            return

        async with message.channel.typing():
            result = self.ask_claudy(msg)

        if len(result) > 1900:
            for i in range(0, len(result), 1900):
                await message.channel.send(result[i:i+1900])
        else:
            await message.channel.send(result)


async def main():
    bot = ClaudyDiscord()
    try:
        await bot.start(TOKEN)
    except discord.LoginFailure:
        print("[DiscordBot] Token invalido. Verifica ~/.claudy/config.json")
    except KeyboardInterrupt:
        await bot.close()
    except Exception as e:
        print(f"[DiscordBot] Error: {e}")
        await bot.close()

if __name__ == "__main__":
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
