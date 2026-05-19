"""Claudy Telegram Bot - standalone process communicating via Gateway API."""
import asyncio
import glob
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)

cfg = load_config()
TOKEN = cfg.get("telegram", {}).get("botToken", "")
ALLOWED = [str(u) for u in cfg.get("telegram", {}).get("allowedUsers", [])]
TTS_REPLY = bool(cfg.get("telegram", {}).get("ttsReply", False))
GATEWAY_URL = "http://127.0.0.1:8720/api"

if not TOKEN:
    print("[TelegramBot] No token configured. Exiting.")
    sys.exit(0)

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Locate ffmpeg (winget alias may not be on PATH for subprocesses)
def _find_ffmpeg():
    for cand in (
        os.environ.get("FFMPEG_BIN"),
        "ffmpeg",
        "ffmpeg.exe",
    ):
        if cand:
            try:
                subprocess.run([cand, "-version"], capture_output=True, timeout=5)
                return cand
            except Exception:
                pass
    pattern = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "**", "ffmpeg.exe",
    )
    found = glob.glob(pattern, recursive=True)
    return found[0] if found else None

FFMPEG = _find_ffmpeg()

# Lazy-load whisper model
_whisper_model = None
def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            print("[TelegramBot] Cargando whisper tiny...")
            _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            print("[TelegramBot] Whisper listo.")
        except Exception as e:
            print(f"[TelegramBot] Error cargando whisper: {e}")
            _whisper_model = False
    return _whisper_model if _whisper_model else None


def ogg_to_wav(ogg_path, wav_path):
    if not FFMPEG:
        return False
    try:
        subprocess.run(
            [FFMPEG, "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, timeout=60, check=True,
        )
        return os.path.exists(wav_path)
    except Exception as e:
        print(f"[TelegramBot] ffmpeg error: {e}")
        return False


def transcribe(audio_path):
    model = get_whisper()
    if not model:
        return ""
    try:
        segments, _info = model.transcribe(audio_path, language="es", beam_size=1)
        text = " ".join(seg.text.strip() for seg in segments)
        return text.strip()
    except Exception as e:
        print(f"[TelegramBot] transcribe error: {e}")
        return ""


def ask_claudy(msg):
    """Send message to Claudy Gateway and return response."""
    try:
        req = urllib.request.Request(
            GATEWAY_URL,
            data=json.dumps({"message": msg}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=180)
        return json.loads(resp.read()).get("response", "Sin respuesta")
    except Exception as e:
        return f"Error conectando con Claudy: {e}"


# Mensajes de progreso para cuando Claudy se demora
PROGRESS_MESSAGES = [
    (12, "Dame un momento, estoy buscando..."),
    (28, "Sigo trabajando, ya casi tengo algo para ti."),
    (50, "Esto tomo mas de lo esperado, no te abandone."),
    (80, "Aun aqui. Tarea larga, pero ahi vamos."),
    (120, "Sigo encima. Si esto sigue colgado, avisame."),
]


async def _ask_with_progress(update, msg):
    """Run ask_claudy in a thread and emit typing + textual progress updates."""
    chat = update.message.chat
    task = asyncio.create_task(asyncio.to_thread(ask_claudy, msg))
    start = asyncio.get_event_loop().time()
    sent_idx = 0
    try:
        while not task.done():
            try:
                await chat.send_action("typing")
            except Exception:
                pass
            # Check if we crossed a progress threshold
            elapsed = asyncio.get_event_loop().time() - start
            while sent_idx < len(PROGRESS_MESSAGES) and elapsed >= PROGRESS_MESSAGES[sent_idx][0]:
                try:
                    await update.message.reply_text(PROGRESS_MESSAGES[sent_idx][1])
                except Exception:
                    pass
                sent_idx += 1
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=4.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
        return await task
    except Exception as e:
        return f"Error: {e}"


async def start(update, context):
    uid = str(update.effective_user.id)
    uname = update.effective_user.first_name or "humano"
    if ALLOWED and uid not in ALLOWED:
        await update.message.reply_text(
            f"Hola {uname}. No estas autorizado.\nTu ID: {uid}\n"
            "Pedi al dueno que ejecute /vincular {uid} en Claudy Desktop."
        )
        return
    await update.message.reply_text(
        f"Hola {uname}! Soy Claudy.\n\n"
        "Preguntame lo que necesites - texto o audio.\n"
        "/atajos para ver comandos."
    )


def _synth_voice_mp3(text):
    """Generate mp3 via edge-tts and return path."""
    try:
        import edge_tts as _et
        out = os.path.join(tempfile.gettempdir(), f"claudy_voice_{os.getpid()}_{int(__import__('time').time())}.mp3")
        async def _go():
            await _et.Communicate(text[:1500], "es-CL-LorenzoNeural").save(out)
        asyncio.get_event_loop().run_until_complete(_go())
        return out
    except Exception as e:
        print(f"[TelegramBot] TTS error: {e}")
        return None


import re as _re
_IMAGE_MARKER = _re.compile(r"\[CLAUDY_IMAGE:([^\]]+)\]")
_FILE_MARKER = _re.compile(r"\[CLAUDY_FILE:([^\]]+)\]")


async def _maybe_send_attachments(update, result):
    """Extract [CLAUDY_IMAGE:path] and [CLAUDY_FILE:path] markers, send them as
    photos/documents, and return the cleaned text. Returns ('', True) if only
    attachments (no remaining text)."""
    sent_any = False
    for m in _IMAGE_MARKER.finditer(result):
        p = m.group(1).strip()
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    await update.message.reply_photo(photo=f)
                sent_any = True
            except Exception as e:
                await update.message.reply_text(f"No pude enviar imagen: {e}")
    for m in _FILE_MARKER.finditer(result):
        p = m.group(1).strip()
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    await update.message.reply_document(document=f, filename=os.path.basename(p))
                sent_any = True
            except Exception as e:
                await update.message.reply_text(f"No pude enviar archivo: {e}")
    cleaned = _IMAGE_MARKER.sub("", result)
    cleaned = _FILE_MARKER.sub("", cleaned).strip()
    return cleaned, sent_any


async def _reply(update, result):
    # Attachments first (image/file markers)
    try:
        cleaned, sent_any = await _maybe_send_attachments(update, result)
    except Exception:
        cleaned, sent_any = result, False
    if sent_any and not cleaned:
        return
    result = cleaned if sent_any else result
    if TTS_REPLY:
        # Try to send voice; fallback to text on error
        try:
            import edge_tts as _et
            tmp = os.path.join(tempfile.gettempdir(), f"claudy_voice_{os.getpid()}_{int(__import__('time').time())}.mp3")
            await _et.Communicate(result[:1500], "es-CL-LorenzoNeural").save(tmp)
            with open(tmp, "rb") as f:
                await update.message.reply_voice(voice=f)
            try: os.unlink(tmp)
            except Exception: pass
            return
        except Exception as e:
            print(f"[TelegramBot] voice fallback: {e}")
    if len(result) > 4000:
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i+4000])
    else:
        await update.message.reply_text(result)


async def handle_text(update, context):
    uid = str(update.effective_user.id)
    if ALLOWED and uid not in ALLOWED:
        await update.message.reply_text(f"No autorizado. Tu ID: {uid}")
        return
    msg = (update.message.text or "").strip()
    if not msg:
        return
    await update.message.chat.send_action("typing")
    result = await _ask_with_progress(update, msg)
    await _reply(update, result)


async def handle_voice(update, context):
    uid = str(update.effective_user.id)
    if ALLOWED and uid not in ALLOWED:
        await update.message.reply_text(f"No autorizado. Tu ID: {uid}")
        return
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    await update.message.chat.send_action("typing")
    if not FFMPEG:
        await update.message.reply_text("No tengo ffmpeg para decodificar el audio.")
        return
    tmpdir = tempfile.mkdtemp(prefix="claudy_voice_")
    ogg_path = os.path.join(tmpdir, "in.ogg")
    wav_path = os.path.join(tmpdir, "in.wav")
    try:
        f = await voice.get_file()
        await f.download_to_drive(ogg_path)
        if not ogg_to_wav(ogg_path, wav_path):
            await update.message.reply_text("No pude convertir el audio.")
            return
        text = transcribe(wav_path)
        if not text:
            await update.message.reply_text("No entendi el audio. Manda mas claro o por texto.")
            return
        await update.message.reply_text(f"🎤 \"{text}\"")
        result = await _ask_with_progress(update, text)
        await _reply(update, result)
    except Exception as e:
        await update.message.reply_text(f"Error procesando audio: {e}")
    finally:
        try:
            for fn in (ogg_path, wav_path):
                if os.path.exists(fn):
                    os.unlink(fn)
            os.rmdir(tmpdir)
        except Exception:
            pass


async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print(f"[TelegramBot] Iniciado. FFmpeg: {FFMPEG or 'NO DISPONIBLE'}")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass
    await app.updater.stop()
    await app.stop()
    await app.shutdown()


if __name__ == "__main__":
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
