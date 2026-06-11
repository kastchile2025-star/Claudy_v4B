import asyncio
import os
import re
import tempfile
import threading

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

DEFAULT_VOICE = "es-CL-LorenzoNeural"
_LOCK = threading.Lock()
_CURRENT_PROCESS = None


def _strip_for_tts(text):
    if not text:
        return ""
    t = re.sub(r"```[\s\S]*?```", " bloque de codigo ", text)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"[*_#>]+", "", t)
    t = re.sub(r"https?://\S+", "enlace", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 800:
        t = t[:800].rsplit(" ", 1)[0] + "..."
    return t


async def _synth(text, voice, out_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def _play_windows(path):
    global _CURRENT_PROCESS
    import subprocess
    ps = (
        f'Add-Type -AssemblyName presentationCore; '
        f'$p = New-Object System.Windows.Media.MediaPlayer; '
        f'$p.Open([uri]"{path}"); '
        f'$p.Play(); '
        f'Start-Sleep -Seconds 1; '
        f'while ($p.NaturalDuration.HasTimeSpan -eq $false) {{ Start-Sleep -Milliseconds 100 }}; '
        f'$dur = $p.NaturalDuration.TimeSpan.TotalSeconds + 1; '
        f'Start-Sleep -Seconds $dur'
    )
    _CURRENT_PROCESS = subprocess.Popen(
        ["powershell", "-NoProfile", "-Command", ps],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    _CURRENT_PROCESS.wait()


def stop_speaking():
    global _CURRENT_PROCESS
    if _CURRENT_PROCESS and _CURRENT_PROCESS.poll() is None:
        try:
            _CURRENT_PROCESS.terminate()
        except Exception:
            pass


def speak(text, voice=DEFAULT_VOICE):
    if not EDGE_TTS_AVAILABLE:
        return
    clean = _strip_for_tts(text)
    if not clean:
        return

    def _run():
        with _LOCK:
            stop_speaking()
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            try:
                asyncio.run(_synth(clean, voice, tmp.name))
                _play_windows(tmp.name)
            except Exception:
                pass
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

    threading.Thread(target=_run, daemon=True).start()


def speak_blocking(text, voice=DEFAULT_VOICE, max_chars=900):
    """Sintetiza y reproduce BLOQUEANDO hasta terminar.

    Para el modo conversación por voz: el loop no debe volver a escuchar
    mientras Claudy habla (oiría su propio eco)."""
    if not EDGE_TTS_AVAILABLE:
        return
    clean = _strip_for_tts(text)
    if not clean:
        return
    if len(clean) > max_chars:
        clean = clean[:max_chars].rsplit(" ", 1)[0] + ". El detalle completo está en el chat."
    with _LOCK:
        stop_speaking()
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        try:
            asyncio.run(_synth(clean, voice, tmp.name))
            _play_windows(tmp.name)
        except Exception:
            pass
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
