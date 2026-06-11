"""Claudy features.voice_chat — Conversación por voz, estilo Claude voice mode.

El botón 🎙️ del chat web activa un loop continuo:

  escuchar (micrófono → Google STT es-CL)
    → transcripción aparece como mensaje del usuario en el chat
    → pipeline normal (_handle_web_submit: intents + LLM + streaming)
    → la respuesta se LEE en voz alta (edge-tts, voz chilena) y queda en el chat
    → volver a escuchar

Mientras Claudy habla NO se escucha (evita el eco). Se sale con el botón o
diciendo una frase de despedida ("adiós claudy", "termina la conversación").

Se usa como mixin: ClawdPet hereda de VoiceChatMixin. Depende de
_handle_web_submit, _eval_in_web y _debug_log. La respuesta final la captura
WebViewChatWrapper (add_bot/end_stream) vía _voice_capture_answer.
"""
import json
import threading
import time

EXIT_PHRASES = (
    "termina la conversacion", "termina la conversación",
    "adios claudy", "adiós claudy", "chao claudy", "chau claudy",
    "deja de escuchar", "cierra el modo voz", "termina el modo voz",
    "detén la conversación", "deten la conversacion",
)


class VoiceChatMixin:

    def _voice_chat_toggle(self):
        """Botón 🎙️: inicia o detiene el modo conversación. Devuelve el estado."""
        if getattr(self, "_voice_chat_on", False):
            return self._voice_chat_stop()
        return self._voice_chat_start()

    def _voice_chat_start(self):
        if getattr(self, "_voice_chat_on", False):
            return "on"
        try:
            import speech_recognition  # noqa: F401
        except ImportError:
            self._voice_chat_status(
                "error", "Falta el módulo de voz: pip install SpeechRecognition pyaudio")
            return "error"
        self._voice_chat_on = True
        self._voice_answer_event = threading.Event()
        self._voice_last_answer = ""
        threading.Thread(target=self._voice_chat_loop, daemon=True,
                         name="voice-chat").start()
        return "on"

    def _voice_chat_stop(self):
        self._voice_chat_on = False
        try:
            from tts import stop_speaking
            stop_speaking()
        except Exception:
            pass
        ev = getattr(self, "_voice_answer_event", None)
        if ev:
            ev.set()  # destraba el loop si estaba esperando una respuesta
        self._voice_chat_status("off")
        return "off"

    def _voice_capture_answer(self, text):
        """La llama WebViewChatWrapper cuando llega la respuesta final del bot."""
        if getattr(self, "_voice_chat_on", False):
            self._voice_last_answer = text or ""
            ev = getattr(self, "_voice_answer_event", None)
            if ev:
                ev.set()

    def _voice_chat_status(self, state, detail=""):
        """Empuja el estado al chat web: off|listening|thinking|speaking|error."""
        try:
            self._eval_in_web(
                f"try {{ setVoiceState({json.dumps(state)}, {json.dumps(detail)}); }} catch(e) {{}}")
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────
    # Dictado (botón 🎤): graba → transcribe → deja el texto en el
    # input del chat para que el usuario lo edite y lo envíe.
    # Clic para grabar, clic de nuevo para detener (máx. 60 s).
    # ──────────────────────────────────────────────────────────
    def _dictation_toggle(self):
        if getattr(self, "_dictating", False):
            self._dictating = False   # señal de stop → transcribe lo grabado
            return "stopping"
        try:
            import speech_recognition  # noqa: F401
        except ImportError:
            self._dictation_status(
                "error", "Falta el módulo de voz: pip install SpeechRecognition pyaudio")
            return "error"
        self._dictating = True
        threading.Thread(target=self._dictation_worker, daemon=True,
                         name="dictation").start()
        return "recording"

    def _dictation_status(self, state, detail=""):
        """Empuja el estado del dictado al chat: off|recording|transcribing|error."""
        try:
            self._eval_in_web(
                f"try {{ setDictationState({json.dumps(state)}, {json.dumps(detail)}); }} catch(e) {{}}")
        except Exception:
            pass

    def _dictation_worker(self):
        import speech_recognition as sr
        frames = []
        try:
            r = sr.Recognizer()
            mic = sr.Microphone()
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=0.3)
                self._dictation_status("recording")
                start = time.time()
                while getattr(self, "_dictating", False) and time.time() - start < 60:
                    try:
                        frames.append(source.stream.read(source.CHUNK))
                    except Exception:
                        time.sleep(0.005)
                sample_rate, sample_width = source.SAMPLE_RATE, source.SAMPLE_WIDTH
            if not frames:
                self._dictation_status("off")
                return
            self._dictation_status("transcribing")
            audio = sr.AudioData(b"".join(frames), sample_rate, sample_width)
            try:
                text = (r.recognize_google(audio, language="es-CL") or "").strip()
            except sr.UnknownValueError:
                self._dictation_status("error", "No entendí el audio, intenta de nuevo")
                return
            if text:
                self._eval_in_web(
                    f"try {{ insertDictation({json.dumps(text)}); }} catch(e) {{}}")
            self._dictation_status("off")
        except Exception as e:
            self._dictation_status("error", f"Micrófono: {e}")
        finally:
            self._dictating = False

    def _voice_chat_loop(self):
        import speech_recognition as sr
        r = sr.Recognizer()
        r.pause_threshold = 1.1       # tolera pausas naturales al hablar
        r.dynamic_energy_threshold = True
        try:
            mic = sr.Microphone()
        except Exception as e:
            self._voice_chat_on = False
            self._voice_chat_status("error", f"Micrófono no disponible: {e}")
            return
        try:
            from tts import speak_blocking
        except Exception:
            speak_blocking = None

        try:
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=0.6)
                while getattr(self, "_voice_chat_on", False):
                    self._voice_chat_status("listening")
                    try:
                        audio = r.listen(source, timeout=6, phrase_time_limit=25)
                    except sr.WaitTimeoutError:
                        continue
                    if not getattr(self, "_voice_chat_on", False):
                        break
                    self._voice_chat_status("thinking")
                    try:
                        text = r.recognize_google(audio, language="es-CL")
                    except sr.UnknownValueError:
                        continue  # ruido / no se entendió: seguir escuchando
                    except Exception:
                        self._voice_chat_status("error", "No pude transcribir (¿sin internet?)")
                        time.sleep(1.2)
                        continue
                    text = (text or "").strip()
                    if not text:
                        continue
                    if any(p in text.lower() for p in EXIT_PHRASES):
                        break

                    # Pipeline normal del chat web: el mensaje transcrito aparece
                    # como burbuja del usuario y la respuesta llega al chat.
                    self._voice_answer_event.clear()
                    self._voice_last_answer = ""
                    try:
                        self._handle_web_submit(text)
                    except Exception:
                        continue
                    got = self._voice_answer_event.wait(timeout=180)
                    if not getattr(self, "_voice_chat_on", False):
                        break
                    answer = (self._voice_last_answer or "").strip()
                    if got and answer and speak_blocking:
                        self._voice_chat_status("speaking")
                        try:
                            speak_blocking(answer)
                        except Exception:
                            pass
                        time.sleep(0.25)  # colita anti-eco antes de volver a escuchar
        except Exception as e:
            try:
                self._debug_log("VOICE CHAT", f"loop error: {e}")
            except Exception:
                pass
        self._voice_chat_on = False
        self._voice_chat_status("off")
