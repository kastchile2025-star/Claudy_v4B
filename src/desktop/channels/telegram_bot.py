"""Claudy Telegram Bot — único canal externo de Claudy (refactor v5).

Proceso independiente que conversa con la app de escritorio vía el
Gateway API (core/gateway.py, puerto 8720). Mejoras v5:
  - Formato nativo de Telegram (HTML: negrita, cursiva, código) con
    fallback automático a texto plano
  - Progreso editando UN solo mensaje de estado (antes: varios sueltos)
  - Hot-reload de config (usuarios autorizados y voz, sin reiniciar)
  - Comandos /memoria, /resumen, /estado, /atajos
"""
import asyncio
import glob
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

# El bot vive en channels/; los módulos compartidos (secure_store) en el padre.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claudy", "config.json")
GATEWAY_URL = "http://127.0.0.1:8720/api"
GATEWAY_HEALTH = "http://127.0.0.1:8720/health"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    # Los secretos (incl. botToken) se guardan encriptados con secure_store.
    try:
        import secure_store
        cfg = secure_store.decrypt_config_secrets(cfg)
    except Exception as e:
        print(f"[TelegramBot] No pude desencriptar config: {e}")
    return cfg


cfg = load_config()
TOKEN = cfg.get("telegram", {}).get("botToken", "")

# Estado mutable en runtime. allowed/tts se recargan en caliente si
# config.json cambia (el token NO: cambiar token requiere reiniciar el bot,
# cosa que hace el watchdog de pet.py al guardar uno nuevo).
STATE = {
    "tts": bool(cfg.get("telegram", {}).get("ttsReply", False)),
    "allowed": [str(u) for u in cfg.get("telegram", {}).get("allowedUsers", [])],
    "config_mtime": os.path.getmtime(CONFIG_PATH) if os.path.exists(CONFIG_PATH) else 0,
}


def maybe_reload_config():
    """Recarga usuarios autorizados y preferencia de voz si config.json cambió."""
    try:
        mt = os.path.getmtime(CONFIG_PATH)
        if mt == STATE["config_mtime"]:
            return
        STATE["config_mtime"] = mt
        fresh = load_config()
        tg = fresh.get("telegram", {})
        STATE["allowed"] = [str(u) for u in tg.get("allowedUsers", [])]
        STATE["tts"] = bool(tg.get("ttsReply", STATE["tts"]))
        print("[TelegramBot] Config recargada en caliente.")
    except Exception as e:
        print(f"[TelegramBot] Error recargando config: {e}")


def _is_allowed(uid):
    maybe_reload_config()
    return not STATE["allowed"] or str(uid) in STATE["allowed"]


def _persist_tts(enabled):
    """Guarda telegram.ttsReply en config.json SIN tocar los secretos encriptados
    (lee el archivo crudo, así el botToken sigue como 'enc:v1:...')."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        raw.setdefault("telegram", {})["ttsReply"] = bool(enabled)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)
        STATE["config_mtime"] = os.path.getmtime(CONFIG_PATH)
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


# ------------------------------------------------------------------
# Markdown → HTML de Telegram (negrita, cursiva, código) con escape
# ------------------------------------------------------------------
def md_to_telegram_html(text):
    """Convierte markdown ligero a HTML soportado por Telegram.
    Si algo sale mal, el caller debe caer a texto plano."""
    placeholders = {}

    def _stash(content, tag):
        key = f"\x00{len(placeholders)}\x00"
        placeholders[key] = f"<{tag}>{html.escape(content)}</{tag}>"
        return key

    # Bloques de código primero (no deben recibir más formato)
    text = re.sub(r"```[a-zA-Z0-9_+-]*\n?(.*?)```",
                  lambda m: _stash(m.group(1).rstrip(), "pre"), text, flags=re.S)
    text = re.sub(r"`([^`\n]+)`", lambda m: _stash(m.group(1), "code"), text)
    # Escapar el resto
    text = html.escape(text)
    # Links [texto](url)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                  r'<a href="\2">\1</a>', text)
    # Negrita y cursiva
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", text)
    # Títulos markdown → negrita
    text = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", text, flags=re.M)
    # Restaurar bloques de código
    for key, val in placeholders.items():
        text = text.replace(key, val)
    return text


# Locate ffmpeg (winget alias may not be on PATH for subprocesses)
def _find_ffmpeg():
    for cand in (os.environ.get("FFMPEG_BIN"), "ffmpeg", "ffmpeg.exe"):
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
            data=json.dumps({"message": msg, "channel": "telegram"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=180)
        return json.loads(resp.read()).get("response", "Sin respuesta")
    except Exception as e:
        return f"Error conectando con Claudy: {e}"


def gateway_health():
    """True si el gateway de la app de escritorio responde."""
    try:
        with urllib.request.urlopen(GATEWAY_HEALTH, timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


# Hitos de progreso: se EDITA un único mensaje de estado en vez de
# mandar varios mensajes sueltos.
PROGRESS_MESSAGES = [
    (12, "⏳ Dame un momento, estoy trabajando en eso..."),
    (28, "⏳ Sigo en ello, ya casi tengo algo para ti."),
    (50, "⏳ Esto tomó más de lo esperado, no te abandoné."),
    (80, "⏳ Aún aquí. Tarea larga, pero ahí vamos."),
    (120, "⏳ Sigo encima. Si esto sigue colgado, avísame."),
]


async def _ask_with_progress(update, msg):
    """Ejecuta ask_claudy en un hilo, mostrando typing + UN mensaje de
    progreso que se va editando con cada hito."""
    chat = update.message.chat
    task = asyncio.create_task(asyncio.to_thread(ask_claudy, msg))
    start = asyncio.get_event_loop().time()
    sent_idx = 0
    status_msg = None
    try:
        while not task.done():
            try:
                await chat.send_action("typing")
            except Exception:
                pass
            elapsed = asyncio.get_event_loop().time() - start
            while sent_idx < len(PROGRESS_MESSAGES) and elapsed >= PROGRESS_MESSAGES[sent_idx][0]:
                txt = PROGRESS_MESSAGES[sent_idx][1]
                try:
                    if status_msg is None:
                        status_msg = await update.message.reply_text(txt)
                    else:
                        await status_msg.edit_text(txt)
                except Exception:
                    pass
                sent_idx += 1
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=4.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
        result = await task
    except Exception as e:
        result = f"Error: {e}"
    if status_msg is not None:
        try:
            await status_msg.delete()
        except Exception:
            pass
    return result


async def start(update, context):
    uid = str(update.effective_user.id)
    uname = update.effective_user.first_name or "humano"
    if not _is_allowed(uid):
        await update.message.reply_text(
            f"Hola {uname}. No estás autorizado.\nTu ID: {uid}\n"
            "Pide al dueño que ejecute /vincular {uid} en Claudy Desktop."
        )
        return
    await update.message.reply_text(
        f"Hola {uname}! Soy Claudy.\n\n"
        "Pregúntame lo que necesites — texto o audio.\n"
        "/atajos para ver comandos."
    )


_IMAGE_MARKER = re.compile(r"\[CLAUDY_IMAGE:([^\]]+)\]")
_FILE_MARKER = re.compile(r"\[CLAUDY_FILE:([^\]]+)\]")


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


async def _send_formatted(update, text):
    """Envía texto con formato HTML de Telegram; fallback a texto plano.
    Trocea respetando el límite de 4096 de Telegram."""
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or [""]
    for chunk in chunks:
        try:
            await update.message.reply_text(
                md_to_telegram_html(chunk), parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:
            await update.message.reply_text(chunk)


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
            tmp = os.path.join(tempfile.gettempdir(), f"claudy_voice_{os.getpid()}_{int(time.time())}.mp3")
            plain = re.sub(r"[*_`#]+", "", result)
            await _et.Communicate(plain[:1500], "es-CL-LorenzoNeural").save(tmp)
            with open(tmp, "rb") as f:
                await update.message.reply_voice(voice=f)
            try:
                os.unlink(tmp)
            except Exception:
                pass
            return
        except Exception as e:
            print(f"[TelegramBot] voice fallback: {e}")
    await _send_formatted(update, result)


async def handle_text(update, context):
    uid = str(update.effective_user.id)
    if not _is_allowed(uid):
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
    if not _is_allowed(uid):
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


async def cmd_memoria(update, context):
    """/memoria <consulta> — busca en TODA la historia de Claudy (FTS5)."""
    uid = str(update.effective_user.id)
    if not _is_allowed(uid):
        await update.message.reply_text(f"No autorizado. Tu ID: {uid}")
        return
    query = " ".join(context.args or []).strip()
    if not query:
        await update.message.reply_text("¿Qué busco en mi memoria? Ej: /memoria factura combas")
        return
    await update.message.chat.send_action("typing")
    result = await _ask_with_progress(update, f"/memoria {query}")
    await _reply(update, result)


async def cmd_resumen(update, context):
    """/resumen — resumen de lo conversado/hecho hoy."""
    uid = str(update.effective_user.id)
    if not _is_allowed(uid):
        await update.message.reply_text(f"No autorizado. Tu ID: {uid}")
        return
    await update.message.chat.send_action("typing")
    prompt = ("Resume en máximo 10 líneas lo que conversamos e hicimos hoy "
              "(usa tu memoria del día). Cierra con los pendientes si los hay. "
              "Si no hubo nada hoy, dilo en una línea.")
    result = await _ask_with_progress(update, prompt)
    await _reply(update, result)


async def cmd_estado(update, context):
    """/estado — salud del bot, gateway y servicios de voz."""
    uid = str(update.effective_user.id)
    if not _is_allowed(uid):
        await update.message.reply_text(f"No autorizado. Tu ID: {uid}")
        return
    gw = await asyncio.to_thread(gateway_health)
    lines = [
        "<b>Estado de Claudy</b>",
        f"• Gateway escritorio: {'🟢 conectado' if gw else '🔴 sin conexión (¿está abierta la app?)'}",
        f"• Voz (respuestas): {'🔊 audio' if STATE['tts'] else '📝 texto'}",
        f"• Transcripción (ffmpeg): {'🟢' if FFMPEG else '🔴 no encontrado'}",
        f"• Usuarios autorizados: {len(STATE['allowed']) or 'todos (sin restricción)'}",
    ]
    try:
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception:
        await update.message.reply_text(re.sub(r"</?b>", "", "\n".join(lines)))


async def cmd_atajos(update, context):
    """/atajos — lista de comandos del bot."""
    uid = str(update.effective_user.id)
    if not _is_allowed(uid):
        await update.message.reply_text(f"No autorizado. Tu ID: {uid}")
        return
    txt = (
        "<b>Comandos de Claudy</b>\n"
        "/memoria &lt;consulta&gt; — busco en toda mi memoria\n"
        "/resumen — resumen de lo de hoy\n"
        "/estado — salud de la conexión y servicios\n"
        "/voz on|off — respuestas por audio o texto\n\n"
        "También puedes mandarme <i>notas de voz</i>, <i>fotos</i> y "
        "<i>documentos</i> y los proceso."
    )
    try:
        await update.message.reply_text(txt, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(re.sub(r"<[^>]+>", "", txt))


async def handle_voice(update, context):
    uid = str(update.effective_user.id)
    if not _is_allowed(uid):
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
            await update.message.reply_text("No entendí el audio. Manda más claro o por texto.")
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
    if not _is_allowed(uid):
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
    app.add_handler(CommandHandler("memoria", cmd_memoria))
    app.add_handler(CommandHandler("resumen", cmd_resumen))
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("atajos", cmd_atajos))
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
