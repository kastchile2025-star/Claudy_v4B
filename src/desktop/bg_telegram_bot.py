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
        cfg = json.load(f)
    # Los secretos (incl. botToken) se guardan encriptados con secure_store.
    # Hay que desencriptarlos aquí o Telegram rechaza el token "enc:v1:...".
    try:
        import secure_store
        cfg = secure_store.decrypt_config_secrets(cfg)
    except Exception as e:
        print(f"[TelegramBot] No pude desencriptar config: {e}")
    return cfg

cfg = load_config()
TOKEN = cfg.get("telegram", {}).get("botToken", "")
ALLOWED = [str(u) for u in cfg.get("telegram", {}).get("allowedUsers", [])]
GATEWAY_URL = "http://127.0.0.1:8720/api"

# Estado de respuesta por voz, mutable en runtime (/voz on|off o lenguaje natural).
STATE = {"tts": bool(cfg.get("telegram", {}).get("ttsReply", False))}


def _persist_tts(enabled):
    """Guarda telegram.ttsReply en config.json SIN tocar los secretos encriptados
    (lee el archivo crudo, así el botToken sigue como 'enc:v1:...')."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        raw.setdefault("telegram", {})["ttsReply"] = bool(enabled)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[TelegramBot] No pude guardar ttsReply: {e}")


def _detect_voice_intent(text):
    """Detecta si el mensaje pide cambiar a/desde respuestas por voz.
    Devuelve 'on', 'off' o None. Conservador: solo si menciona audio/voz."""
    t = (text or "").lower()
    if not any(k in t for k in ("audio", "voz", "nota de voz")):
        return None
    if any(k in t for k in ("texto", "escrito", "deja de", "ya no", "sin audio",
                            "sin voz", "no me mandes", "no mas audio", "no más audio")):
        return "off"
    if any(k in t for k in ("respond", "contest", "habla", "háblame", "manda", "mánda",
                            "envia", "envía", "quiero", "prefiero", "dame", "mejor", "puedes")):
        return "on"
    return None

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
    if STATE["tts"]:
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
    # ¿El usuario pidió cambiar a/desde respuestas por voz? (lenguaje natural)
    intent = _detect_voice_intent(msg)
    if intent == "on":
        STATE["tts"] = True
        _persist_tts(True)
        await update.message.reply_text(
            "🔊 Listo, desde ahora te respondo con audios. "
            "Escribe \"respóndeme con texto\" o /voz off para volver a texto."
        )
        return
    if intent == "off":
        STATE["tts"] = False
        _persist_tts(False)
        await update.message.reply_text("📝 Ok, vuelvo a responder con texto. (/voz on para audios)")
        return
    await update.message.chat.send_action("typing")
    result = await _ask_with_progress(update, msg)
    await _reply(update, result)


async def cmd_voz(update, context):
    """/voz on|off — alterna respuestas por audio. Sin argumento muestra el estado."""
    uid = str(update.effective_user.id)
    if ALLOWED and uid not in ALLOWED:
        await update.message.reply_text(f"No autorizado. Tu ID: {uid}")
        return
    arg = (context.args[0].lower() if context.args else "")
    if arg in ("on", "si", "sí", "1", "activar", "activa", "audio", "audios"):
        STATE["tts"] = True
        _persist_tts(True)
        await update.message.reply_text("🔊 Respuestas por audio ACTIVADAS. (/voz off para volver a texto)")
    elif arg in ("off", "no", "0", "desactivar", "desactiva", "texto"):
        STATE["tts"] = False
        _persist_tts(False)
        await update.message.reply_text("📝 Respuestas por audio DESACTIVADAS. (/voz on para activarlas)")
    else:
        estado = "audios 🔊" if STATE["tts"] else "texto 📝"
        await update.message.reply_text(
            f"Ahora respondo con {estado}.\nUsa /voz on o /voz off para cambiar."
        )


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


async def handle_document(update, context):
    """Recibe un documento o imagen, lo descarga, y pide a Claudy que lo analice."""
    uid = str(update.effective_user.id)
    if ALLOWED and uid not in ALLOWED:
        await update.message.reply_text(f"No autorizado. Tu ID: {uid}")
        return

    # Resolver el archivo (documento o foto en su mayor resolución)
    file_obj = None
    suggested_name = None
    if update.message.document:
        file_obj = update.message.document
        suggested_name = file_obj.file_name or f"doc_{file_obj.file_id}"
    elif update.message.photo:
        file_obj = update.message.photo[-1]  # mayor resolución
        suggested_name = f"foto_{file_obj.file_id}.jpg"
    if not file_obj:
        return

    await update.message.chat.send_action("typing")

    # Carpeta dedicada para que Felipe pueda revisar después si quiere
    target_dir = os.path.join(os.path.expanduser("~"), ".claudy", "telegram_inbox")
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception:
        target_dir = tempfile.gettempdir()
    # Evitar colisiones de nombre
    base, ext = os.path.splitext(suggested_name)
    safe_base = "".join(c for c in base if c.isalnum() or c in " ._-")[:80] or "archivo"
    target = os.path.join(target_dir, f"{safe_base}{ext}")
    i = 1
    while os.path.exists(target):
        target = os.path.join(target_dir, f"{safe_base}_{i}{ext}")
        i += 1

    try:
        tf = await file_obj.get_file()
        await tf.download_to_drive(target)
    except Exception as e:
        await update.message.reply_text(f"No pude descargar el archivo: {e}")
        return

    # Mandar a Claudy el marcador directo de análisis
    marker = f"[CLAUDY_ANALYZE_FILE:{target}]"
    result = await _ask_with_progress(update, marker)
    await _reply(update, result)


async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("voz", cmd_voz))
    app.add_handler(CommandHandler("audio", cmd_voz))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
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
