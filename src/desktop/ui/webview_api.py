"""Claudy ui.webview_api — Puente JS <-> Python del chat (refactor v5).

Clases expuestas al webview (chat.html) vía pywebview:
  - WebViewApi: la API que invoca el JavaScript del chat (enviar mensaje,
    calendario, historial, adjuntos, voz, estado de Drive/Telegram...)
  - WebView*Wrapper: adaptadores que imitan la interfaz de los widgets
    tkinter legacy (status/entry/chat) para reusar la lógica de pet.py
    sin cambios cuando la UI activa es el webview.

IMPORTANTE: chat.html no se toca — este módulo es solo el lado Python.
"""
import json
import threading
import time
import uuid


class WebViewApi:
    def __init__(self, pet):
        self._pet = pet
        self._callbacks = {}

    def set_focused(self, focused):
        self._pet._webview_focused = focused
        # When the webview loses focus (e.g., user clicked another window),
        # kick off the focus check so panels and bubble auto-hide.
        if not focused and getattr(self._pet, "_webview_visible", False):
            try:
                self._pet.after(150, self._pet._check_bubble_focus)
            except Exception:
                pass

    def _register_callback(self, cid, cb):
        if cid:
            self._callbacks[cid] = cb

    def trigger_callback(self, cid, *args):
        cb = self._callbacks.get(cid)
        if cb:
            threading.Thread(target=cb, args=args, daemon=True).start()

    def send_message(self, message):
        def _run():
            self._pet._handle_web_submit(message)
        threading.Thread(target=_run, daemon=True).start()

    def new_conversation(self):
        def _run():
            self._pet._handle_web_new_conversation()
        threading.Thread(target=_run, daemon=True).start()

    def select_product(self, product_name):
        def _run():
            self._pet._handle_web_product_switch(product_name)
        threading.Thread(target=_run, daemon=True).start()

    def analyze_folder(self):
        def _run():
            self._pet._handle_web_analyze_folder()
        threading.Thread(target=_run, daemon=True).start()

    def pick_attachment(self):
        def _run():
            self._pet._handle_web_pick_attachment()
        threading.Thread(target=_run, daemon=True).start()

    def paste_image(self):
        """Ctrl+V en el chat con una imagen o archivos copiados: Python lee el
        portapapeles (PIL.ImageGrab) y analiza el contenido con visión."""
        def _run():
            self._pet._handle_web_paste_image()
        threading.Thread(target=_run, daemon=True).start()

    def open_last_location(self):
        def _run():
            self._pet._open_last_file_location()
        threading.Thread(target=_run, daemon=True).start()

    def minimize_window(self):
        self._pet.after(0, self._pet.hide_bubble)

    def toggle_voice_chat(self):
        """Botón ıılıı del chat: inicia/detiene la conversación por voz.
        Devuelve el estado resultante: on | off | error."""
        try:
            return self._pet._voice_chat_toggle()
        except Exception as e:
            return f"error:{e}"

    def toggle_dictation(self):
        """Botón 🎤 del chat: dicta al input. Clic graba, clic detiene y
        transcribe. Devuelve: recording | stopping | error."""
        try:
            return self._pet._dictation_toggle()
        except Exception as e:
            return f"error:{e}"

    def cancel_processing(self):
        """Botón de pánico (doble ESC): interrumpe lo que Claudy esté haciendo
        (informe a medias, etc.) sin reiniciar la app."""
        try:
            self._pet._request_cancel()
        except Exception:
            pass

    def show_settings(self):
        """Open the history/settings window (alarms, themes, skins, API keys)."""
        self._pet.after(0, self._pet.show_history_window)

    # ── Google Calendar bridge ────────────────────────────────────────────
    def _gcal(self):
        import google_calendar as gcal
        return gcal

    def get_calendar_status(self):
        try:
            return self._gcal().status()
        except Exception as e:
            return {"connected": False, "reason": str(e)}

    def get_calendar_events(self):
        try:
            return self._gcal().list_upcoming()
        except Exception as e:
            return {"connected": False, "reason": str(e), "events": []}

    def calendar_connect(self):
        """Lanza el flujo OAuth (abre navegador 1 vez). Bloquea hasta autorizar."""
        try:
            return self._gcal().connect()
        except Exception as e:
            return {"connected": False, "reason": str(e)}

    def create_calendar_event(self, payload):
        try:
            p = payload or {}
            attendees = p.get("attendees") or []
            if isinstance(attendees, str):
                attendees = [a.strip() for a in attendees.replace(";", ",").split(",") if a.strip()]
            return self._gcal().create_event(
                summary=p.get("summary") or "Reunión",
                start_iso=p.get("start"),
                end_iso=p.get("end"),
                description=p.get("description", ""),
                attendees=attendees,
                location=p.get("location", ""),
                add_meet=bool(p.get("addMeet")),
            )
        except Exception as e:
            return {"ok": False, "reason": str(e)}

    def set_calendar_open(self, is_open):
        """Abre/cierra el panel Calendario (derecha): ensancha/reposiciona la ventana."""
        self._pet._calendar_open = bool(is_open)
        self._pet.after(0, lambda: self._pet._resize_webview_for_panels())
        return True

    # ── Panel Historial (izquierda) ───────────────────────────────────────
    def set_history_open(self, is_open):
        """Abre/cierra el panel Historial (izquierda): ensancha/reposiciona la ventana."""
        self._pet._history_panel_open = bool(is_open)
        self._pet.after(0, lambda: self._pet._resize_webview_for_panels())
        return True

    def get_history_archive(self, limit=200):
        """Devuelve el historial eterno de conversaciones para el panel."""
        try:
            msgs = self._pet._load_memory() or []
            out = []
            for m in msgs:
                role = m.get("role")
                shown = self._pet._tidy_history_text(role, m.get("text") or "")
                if shown is None:
                    continue  # ruido interno: no mostrar
                out.append({
                    "role": "user" if role == "Usuario" else "claudy",
                    "text": shown[:2000],
                    "time": m.get("time", "") or "",
                })
            # Límite tras compactar/filtrar: así se ven los últimos N mensajes limpios.
            if limit:
                out = out[-int(limit):]
            return out
        except Exception as e:
            return []

    def open_settings_window(self):
        """Abre la ventana clásica de Ajustes (alarmas, temas, skins, API keys)."""
        self._pet.after(0, self._pet.show_history_window)
        return True

    def speak_message(self, message):
        def _run():
            self._pet._speak_text(message)
        threading.Thread(target=_run, daemon=True).start()

    def set_voice_enabled(self, enabled):
        """Toggle global TTS desde el botón de voz del chat."""
        self._pet._voice_enabled = bool(enabled)
        return self._pet._voice_enabled

    def get_voice_enabled(self):
        return bool(getattr(self._pet, "_voice_enabled", False))

    def get_drive_status(self):
        return getattr(self._pet, "_drive_connected", True)

    def open_drive_folder(self):
        """Abre la carpeta de Claudy en Google Drive y esconde el chat.

        El chat es una ventana always-on-top: si no se esconde primero, el
        Explorador se abre DETRÁS y parece que el botón no hizo nada."""
        try:
            self._pet.after(0, self._pet.hide_bubble)
        except Exception:
            pass

        def _run():
            import os
            import webbrowser
            time.sleep(0.3)  # dar tiempo a que el chat se oculte antes de abrir
            local = r"G:\Mi unidad\QCORE-ECOSYSTEM"
            try:
                if os.path.isdir(local):
                    os.startfile(local)
                elif os.path.isdir(r"G:\Mi unidad"):
                    os.startfile(r"G:\Mi unidad")
                else:
                    webbrowser.open("https://drive.google.com/drive/my-drive")
            except Exception as e:
                print(f"[drive] no se pudo abrir la carpeta: {e}")
        threading.Thread(target=_run, daemon=True).start()
        return True

    def get_telegram_status(self):
        """Estado de conexión con Telegram para el indicador del sidebar.
        Devuelve el último valor verificado al instante y, si está viejo (>30s),
        dispara una re-verificación en segundo plano (no bloquea la UI)."""
        pet = self._pet
        try:
            last = getattr(pet, "_telegram_last_check", 0)
            if time.time() - last > 30:
                pet._telegram_last_check = time.time()  # evita ráfagas de checks
                threading.Thread(target=pet._verify_telegram_connection, daemon=True).start()
        except Exception:
            pass
        return getattr(pet, "_telegram_connected", False)

    def get_history(self):
        raw_msgs = getattr(self._pet, "_current_session_msgs", []) or []
        serializable = []
        for m in raw_msgs:
            serializable.append({
                "role": m.get("role", "system"),
                "text": m.get("text", "") or "",
                "ts": m.get("ts", time.time()),
                "fileCard": m.get("fileCard", None),
                "optionsCard": m.get("optionsCard", None),
                "summaryCard": m.get("summaryCard", None),
            })
        return serializable


class WebViewStatusWrapper:
    def __init__(self, pet):
        self.pet = pet

    def configure(self, text=None, fg=None, **kwargs):
        if text is not None:
            self.pet._eval_in_web(f"updateStatusText({json.dumps(text)})")
            # Show speech bubble when chat is hidden and a background task is running
            if not getattr(self.pet, '_webview_visible', False) and text.strip():
                try:
                    self.pet.show_pet_speech_bubble(text, duration=5000)
                except Exception:
                    pass


class WebViewEntryWrapper:
    def __init__(self, pet):
        self.pet = pet
        self._val = ""

    def get(self, *args):
        return self._val

    def delete(self, first, last=None):
        self._val = ""
        self.pet._eval_in_web("try { clearInputField(); } catch(e) {}")

    def insert(self, index, text):
        self._val = text
        self.pet._eval_in_web(f"try {{ insertInputText({json.dumps(text)}); }} catch(e) {{}}")

    def focus_set(self):
        self.pet._eval_in_web("try { focusInputField(); } catch(e) {}")

    def config(self, **kwargs):
        pass


class WebViewChatWrapper:
    def __init__(self, pet):
        self.pet = pet
        self._messages = list(getattr(pet, "_current_session_msgs", []) or [])

    def add_user(self, text, ts=None):
        ts = ts or time.time()
        self._messages.append({"role": "user", "text": text, "ts": ts})
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addUserMessage({json.dumps(text)}, {ts}); }} catch(e) {{}}")

    def add_bot(self, text, ts=None):
        ts = ts or time.time()
        self._messages.append({"role": "bot", "text": text, "ts": ts})
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addBotMessage({json.dumps(text)}, {ts}); }} catch(e) {{}}")
        self._notify_voice(text)

    def begin_stream(self, ts=None):
        ts = ts or time.time()
        self.pet._eval_in_web(f"try {{ beginBotStream({ts}); }} catch(e) {{}}")

    def update_stream(self, text):
        self.pet._eval_in_web(f"try {{ updateBotStream({json.dumps(text)}); }} catch(e) {{}}")

    def end_stream(self, text, ts=None):
        ts = ts or time.time()
        self._messages.append({"role": "bot", "text": text, "ts": ts})
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ endBotStream({json.dumps(text)}, {ts}); }} catch(e) {{}}")
        self._notify_voice(text)

    def _notify_voice(self, text):
        """Modo conversación por voz: entrega la respuesta final al loop de voz
        (features/voice_chat.py) para que la lea en alta voz."""
        try:
            self.pet._voice_capture_answer(text)
        except Exception:
            pass

    def add_system(self, text):
        self._messages.append({"role": "system", "text": text, "ts": time.time()})
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addSystemMessage({json.dumps(text)}); }} catch(e) {{}}")

    def show_typing(self):
        self.pet._eval_in_web("try { showTypingIndicator(); } catch(e) {}")

    def hide_typing(self):
        self.pet._eval_in_web("try { hideTypingIndicator(); } catch(e) {}")

    def clear(self):
        self._messages.clear()
        self.pet._current_session_msgs = []
        self.pet._eval_in_web("try { clearChat(); } catch(e) {}")

    def add_options(self, options, on_select):
        callback_id = f"opt_cb_{uuid.uuid4().hex}"
        self.pet.js_api._register_callback(callback_id, on_select)
        self._messages.append({
            "role": "bot",
            "ts": time.time(),
            "optionsCard": {"options": options, "callbackId": callback_id, "active": True}
        })
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addOptionsCard({json.dumps(options)}, {json.dumps(callback_id)}); }} catch(e) {{}}")

    def add_summary_card(self, topic, depth, images, references, style, language, research=None):
        self._messages.append({
            "role": "bot",
            "ts": time.time(),
            "summaryCard": {"topic": topic, "depth": depth, "images": images, "references": references, "style": style, "language": language, "research": research}
        })
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addSummaryCard({json.dumps(topic)}, {json.dumps(depth)}, {json.dumps(images)}, {json.dumps(references)}, {json.dumps(style)}, {json.dumps(language)}, {json.dumps(research)}); }} catch(e) {{}}")

    def add_file_card(self, filename, on_open_file=None, on_open_folder=None, message="Listo. Archivo generado"):
        open_file_id = f"file_cb_{uuid.uuid4().hex}" if on_open_file else None
        open_folder_id = f"folder_cb_{uuid.uuid4().hex}" if on_open_folder else None
        
        if on_open_file:
            self.pet.js_api._register_callback(open_file_id, on_open_file)
        if on_open_folder:
            self.pet.js_api._register_callback(open_folder_id, on_open_folder)

        self._messages.append({
            "role": "bot",
            "ts": time.time(),
            "fileCard": {"filename": filename, "message": message, "openFileId": open_file_id, "openFolderId": open_folder_id}
        })
        self.pet._current_session_msgs = list(self._messages)
        self.pet._eval_in_web(f"try {{ addFileCard({json.dumps(filename)}, {json.dumps(message)}, {json.dumps(open_file_id)}, {json.dumps(open_folder_id)}); }} catch(e) {{}}")

    def load_history(self, messages):
        self.clear()
        for m in messages:
            role = m.get("role", "")
            text = m.get("text", "")
            ts = m.get("ts", time.time())
            fileCard = m.get("fileCard", None)
            optionsCard = m.get("optionsCard", None)
            summaryCard = m.get("summaryCard", None)
            
            if fileCard:
                self.add_file_card(fileCard["filename"], None, None, fileCard["message"])
            elif optionsCard:
                self.add_options(optionsCard["options"], lambda x: None)
            elif summaryCard:
                self.add_summary_card(summaryCard["topic"], summaryCard["depth"], summaryCard["images"], summaryCard["references"], summaryCard["style"], summaryCard["language"], summaryCard.get("research"))
            elif role in ("user", "Usuario") or role == "user":
                self.add_user(text, ts)
            elif role in ("bot", "Claudy") or role == "bot":
                self.add_bot(text, ts)
            else:
                self.add_system(text)
