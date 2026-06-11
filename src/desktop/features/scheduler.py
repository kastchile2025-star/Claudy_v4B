"""Claudy features.scheduler — Alarmas y tareas programadas (refactor v5).

Dos subsistemas extraídos de pet.py:
  - Alarmas one-shot (~/.claudy/alarms.json): "recuérdame X a las 18:00",
    con notificación de escritorio + Telegram y badge sobre el sprite.
  - Cron engine (~/.claudy/cron.json): tareas recurrentes en lenguaje
    natural ("todos los lunes a las 9 mándame el resumen"), comandos o
    recordatorios, con notificación por Telegram.

Se usa como mixin: ClawdPet hereda de SchedulerMixin. Depende de la clase
compuesta: after, _show_notification, _alarm_badge_*, send_quick_message.
"""
import datetime
import json
import os
import re
import subprocess
import threading
import time


class SchedulerMixin:
    def _alarms_path(self):
        p = os.path.join(os.path.expanduser("~"), ".claudy", "alarms.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def _load_alarms(self):
        try:
            with open(self._alarms_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_alarms(self, alarms):
        try:
            with open(self._alarms_path(), "w", encoding="utf-8") as f:
                json.dump(alarms, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _parse_alarm_time(self, text):
        """Parse Spanish natural language time from text.
        Returns (fire_ts, label) or (None, None) on failure.
        Examples: 'en 30 minutos', 'a las 15:30', 'mañana a las 9', '2 horas'.
        """
        import re as _re
        import time as _time
        now = _time.time()
        tl = text.lower()

        # en N minutos / en N horas / en N segundos
        m = _re.search(r'en\s+(\d+)\s*(minuto|minutos|min|hora|horas|h|segundo|segundos|seg)', tl)
        if m:
            qty = int(m.group(1))
            unit = m.group(2)
            if unit.startswith("s"):
                delta = qty
            elif unit.startswith("m"):
                delta = qty * 60
            else:
                delta = qty * 3600
            label = _re.sub(r'(/alarma|alarma\s*(para|en|a\s*las)?)', '', tl, flags=_re.IGNORECASE).strip()
            return now + delta, label or text

        # a las HH:MM  o  a las H (am/pm)
        m = _re.search(r'a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', tl)
        if m:
            import datetime as _dt
            h = int(m.group(1))
            mins = int(m.group(2)) if m.group(2) else 0
            ampm = (m.group(3) or "").lower()
            if ampm == "pm" and h < 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0
            target = _dt.datetime.now().replace(hour=h, minute=mins, second=0, microsecond=0)
            if target.timestamp() <= now:
                target += _dt.timedelta(days=1)  # next day if already past
            label = _re.sub(r'(/alarma|alarma\s*(para|en|a\s*las?)?)', '', tl, flags=_re.IGNORECASE).strip()
            label = _re.sub(r'a\s+las?\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?', '', label).strip(" ,-")
            return target.timestamp(), label or f"Alarma {h:02d}:{mins:02d}"

        # mañana a las HH:MM
        m = _re.search(r'mañana\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?', tl)
        if m:
            import datetime as _dt
            h = int(m.group(1))
            mins = int(m.group(2)) if m.group(2) else 0
            target = _dt.datetime.now().replace(hour=h, minute=mins, second=0, microsecond=0)
            target += _dt.timedelta(days=1)
            label = _re.sub(r'(/alarma|alarma\s*(para|mañana)?|mañana\s+a\s+las?\s+\d+(?::\d+)?)', '', tl).strip(" ,-")
            return target.timestamp(), label or f"Alarma mañana {h:02d}:{mins:02d}"

        return None, None

    def _alarm_set(self, text):
        """Create and schedule an alarm from natural language text."""
        import time as _time
        fire_ts, label = self._parse_alarm_time(text)
        if fire_ts is None:
            return (
                "⏰ No entendí la hora, Felipe. Prueba con:\n"
                "• \"en 30 minutos\"\n"
                "• \"en 2 horas\"\n"
                "• \"a las 15:30\"\n"
                "• \"mañana a las 9\""
            )
        alarms = self._load_alarms()
        alarm_id = str(int(_time.time() * 1000))[-6:]
        label = label or "Alarma"
        alarms.append({"id": alarm_id, "fire": fire_ts, "label": label, "created": _time.time()})
        self._save_alarms(alarms)
        self._schedule_alarm(alarm_id, fire_ts, label)

        import datetime as _dt
        dt = _dt.datetime.fromtimestamp(fire_ts)
        secs = fire_ts - _time.time()
        if secs < 3600:
            when = f"en {int(secs//60)} min {int(secs%60)} seg"
        else:
            when = dt.strftime("el %d/%m a las %H:%M")
        return f"⏰ Alarma #{alarm_id} configurada — {when}\n📌 {label}"

    def _schedule_alarm(self, alarm_id, fire_ts, label):
        """Spawn a background thread that fires the alarm at fire_ts."""
        import time as _time
        import threading as _th

        def _waiter():
            delay = fire_ts - _time.time()
            if delay > 0:
                _time.sleep(delay)
            # Fire! — update alarm to done
            alarms = self._load_alarms()
            alarms = [a for a in alarms if a.get("id") != alarm_id]
            self._save_alarms(alarms)
            # Notify in UI thread
            self.after(0, lambda: self._fire_alarm_notify(label))

        t = _th.Thread(target=_waiter, daemon=True, name=f"alarm-{alarm_id}")
        t.start()

    def _fire_alarm_notify(self, label):
        """Visual + audio alarm notification."""
        msg = f"⏰ ¡ALARMA, Felipe!\n{label}"
        self.show_pet_speech_bubble(msg, duration=30000)
        chat = getattr(self, "_chat_view", None)
        if chat:
            chat.add_bot(msg)
        try:
            import winsound
            for _ in range(3):
                winsound.Beep(1000, 400)
        except Exception:
            pass
        try:
            self._notify("⏰ Claudy", label)
        except Exception:
            pass

    def _alarm_list(self):
        import time as _time
        import datetime as _dt
        alarms = self._load_alarms()
        if not alarms:
            return "No tienes alarmas pendientes, Felipe.\nUsa: /alarma en 30 minutos [etiqueta]"
        lines = ["⏰ Alarmas pendientes:"]
        for a in sorted(alarms, key=lambda x: x["fire"]):
            dt = _dt.datetime.fromtimestamp(a["fire"])
            secs = a["fire"] - _time.time()
            if secs < 0:
                remain = "(pasada)"
            elif secs < 3600:
                remain = f"en {int(secs//60)} min"
            else:
                remain = dt.strftime("%d/%m %H:%M")
            lines.append(f"  #{a['id']} — {remain} — {a.get('label','')}")
        lines.append("\nUsa /alarma del <id> para borrar.")
        return "\n".join(lines)

    def _alarm_delete(self, alarm_id):
        alarms = self._load_alarms()
        before = len(alarms)
        alarms = [a for a in alarms if a.get("id") != alarm_id]
        self._save_alarms(alarms)
        if len(alarms) < before:
            return f"✅ Alarma #{alarm_id} eliminada."
        return f"⚠️ No encontré la alarma #{alarm_id}."

    def _alarm_delete_all(self):
        """Delete ALL pending alarms."""
        alarms = self._load_alarms()
        count = len(alarms)
        if count == 0:
            return "No tienes alarmas pendientes, Felipe."
        self._save_alarms([])
        self._alarm_badge_hide()
        return f"✅ Eliminé todas las alarmas ({count} en total)."

    def _alarm_delete_by_text(self, text):
        """Delete an alarm matching a time (HH:MM) or label keyword in the text."""
        import re as _re
        import datetime as _dt
        import time as _t
        alarms = self._load_alarms()
        if not alarms:
            return "No tienes alarmas pendientes, Felipe."

        tl = text.lower()

        # Try to match HH:MM or H.MM or H:MM from the text
        m = _re.search(r'(\d{1,2})[.:h](\d{2})', tl)
        if m:
            h, mins = int(m.group(1)), int(m.group(2))
            # Find alarm whose fire time matches hour+minute
            matched = []
            for a in alarms:
                dt = _dt.datetime.fromtimestamp(a["fire"])
                if dt.hour == h and dt.minute == mins:
                    matched.append(a)
            if matched:
                ids = [a["id"] for a in matched]
                remaining = [a for a in alarms if a["id"] not in ids]
                self._save_alarms(remaining)
                labels = ", ".join(a.get("label","") or f"#{a['id']}" for a in matched)
                return f"✅ Alarma(s) de las {h:02d}:{mins:02d} eliminada(s): {labels}"

        # Try to match by label keyword (any word > 3 chars from text that matches label)
        noise = {"alarma", "borra", "elimina", "cancela", "quita", "la", "el", "de", "las",
                 "eliminar", "borrar", "cancelar", "quitar", "que", "esta", "ese", "esa"}
        words = [w for w in _re.split(r'\W+', tl) if len(w) > 3 and w not in noise]
        if words:
            matched = []
            for a in alarms:
                label_low = (a.get("label") or "").lower()
                if any(w in label_low for w in words):
                    matched.append(a)
            if matched:
                ids = [a["id"] for a in matched]
                remaining = [a for a in alarms if a["id"] not in ids]
                self._save_alarms(remaining)
                labels = ", ".join(a.get("label","") or f"#{a['id']}" for a in matched)
                return f"✅ Alarma(s) eliminada(s): {labels}"

        # Last resort: show list and ask for ID
        lines = ["⚠️ No encontré qué alarma borrar. Estas son tus alarmas pendientes:"]
        for a in sorted(alarms, key=lambda x: x["fire"]):
            dt = _dt.datetime.fromtimestamp(a["fire"])
            lines.append(f"  #{a['id']} — {dt.strftime('%H:%M')} — {a.get('label','')}")
        lines.append("\nDi: \"elimina la alarma de las HH:MM\" o \"/alarma del <id>\"")
        return "\n".join(lines)

    def _restore_pending_alarms(self):
        """Call on startup to re-schedule any persisted alarms that haven't fired yet."""
        import time as _time
        alarms = self._load_alarms()
        active = []
        for a in alarms:
            if a["fire"] > _time.time():
                self._schedule_alarm(a["id"], a["fire"], a.get("label", "Alarma"))
                active.append(a)
        if len(active) != len(alarms):
            self._save_alarms(active)  # prune past alarms

    def _load_cron_json(self):
        if not os.path.exists(self._cron_file):
            return []
        try:
            with open(self._cron_file, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_cron_json(self):
        os.makedirs(os.path.dirname(self._cron_file), exist_ok=True)
        with open(self._cron_file, "w", encoding="utf-8") as f:
            json.dump(self._cron_jobs, f, indent=2, ensure_ascii=False)

    def _start_cron_engine(self):
        self._cron_jobs = self._load_cron_json()

        def engine_loop():
            while True:
                try:
                    now = datetime.datetime.now()
                    for job in self._cron_jobs[:]:
                        if not job.get("enabled", True):
                            continue
                        last = job.get("last_fired", "")
                        fire = False
                        if job["type"] == "interval":
                            if not last:
                                fire = True
                            else:
                                try:
                                    last_dt = datetime.datetime.fromisoformat(last)
                                    elapsed = (now - last_dt).total_seconds() / 60
                                    if elapsed >= job["interval_min"]:
                                        fire = True
                                except Exception:
                                    fire = True
                        elif job["type"] == "daily":
                            if last and last[:10] == now.strftime("%Y-%m-%d"):
                                continue
                            h, m = job.get("hour", 0), job.get("minute", 0)
                            # Catch-up: dispara una vez al día si ya pasó la hora,
                            # aunque Claudy se haya abierto más tarde (no solo en el minuto exacto).
                            if now.hour > h or (now.hour == h and now.minute >= m):
                                fire = True
                        elif job["type"] == "weekly":
                            if last and last[:10] == now.strftime("%Y-%m-%d"):
                                continue
                            wd = job.get("weekday", 0)  # 0=lunes ... 6=domingo
                            h, m = job.get("hour", 0), job.get("minute", 0)
                            # Catch-up: dispara una vez si es el día objetivo y ya pasó la hora,
                            # aunque Claudy se haya abierto más tarde (no solo en el minuto exacto).
                            if now.weekday() == wd and (now.hour > h or (now.hour == h and now.minute >= m)):
                                fire = True
                        if fire:
                            job["last_fired"] = now.isoformat()
                            self._save_cron_json()
                            self.after(0, lambda j=job.copy(): self._execute_cron_job(j))
                    time.sleep(30)
                except Exception:
                    time.sleep(60)

        threading.Thread(target=engine_loop, daemon=True, name="cron-engine").start()

    def _execute_cron_job(self, job):
        # Trabajos de recordatorio: alarma de Claudy + correo, sin pasar por el LLM.
        if job.get("action") == "reminder":
            self._execute_cron_reminder(job)
            return
        # Trabajos de comando: ejecuta un programa/script externo (sin pasar por el LLM).
        if job.get("action") == "command":
            self._execute_cron_command(job)
            return
        msg = job.get("message", "")
        if not msg:
            return
        try:
            result = self.send_quick_message(msg)
            result = self._strip_markdown(result)
            notification = f"[CRON] {msg[:80]}\n\n{result}"
            # Show in desktop bubble
            self.show_chat_bubble(notification[:500])
            # F3.20 Native Windows toast
            try:
                self._notify("Claudy CRON", result[:200])
            except Exception:
                pass
            try:
                self.after(0, lambda: self._set_state_briefly("wave", 1500))
            except Exception:
                pass
            self._fire_hook("on_cron", message=msg, result=result)
            # Send to Telegram if available
            self._cron_notify_telegram(notification[:500])
        except Exception:
            pass

    def _execute_cron_command(self, job):
        """Ejecuta un comando/script externo programado.
        El job define: "command" (lista de args o string), "cwd" (opcional) y
        "label" (opcional, para la notificación). Pensado para automatizaciones
        como el correo de facturación QCORE SPA."""
        cmd = job.get("command")
        if not cmd:
            return
        label = job.get("label") or "Tarea programada"
        cwd = job.get("cwd") or None

        def _run():
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                shell = isinstance(cmd, str)
                proc = subprocess.run(
                    cmd, cwd=cwd, shell=shell, capture_output=True, text=True,
                    timeout=job.get("timeout", 180), creationflags=flags,
                )
                ok = proc.returncode == 0
                out = (proc.stdout or "").strip()[-200:]
                err = (proc.stderr or "").strip()[-200:]
                estado = "OK" if ok else f"ERROR (code {proc.returncode})"
                resumen = f"[CRON cmd] {label}: {estado}"
                if not job.get("silent"):
                    try:
                        self.after(0, lambda: self._notify("Claudy CRON", resumen[:200]))
                    except Exception:
                        pass
                # Telegram + log
                self._cron_notify_telegram(f"{resumen}\n{out or err}")
                self._fire_hook("on_cron", message=label, result=out or err)
            except Exception as e:
                try:
                    self._cron_notify_telegram(f"[CRON cmd] {label}: EXCEPTION {e}")
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True, name="cron-command").start()

    def _execute_cron_reminder(self, job):
        """Dispara un recordatorio: alarma visual/sonora de Claudy + (opcional) correo.
        Si el job trae "silent": true, NO muestra la alarma emergente y se entrega
        solo como correo (y Telegram), p.ej. para digests diarios por email."""
        msg = job.get("message") or "Recordatorio"
        silent = job.get("silent", False)
        # 1) Alarma de Claudy (burbuja + beep + toast + chat) — se omite si es silencioso.
        if not silent:
            try:
                self._fire_alarm_notify(msg)
            except Exception:
                pass
        # 2) Telegram, si está disponible
        try:
            self._cron_notify_telegram(msg)
        except Exception:
            pass
        # 3) Correo, si el job lo pide y hay SMTP configurado
        email = job.get("email")
        if email and email.get("to"):
            threading.Thread(
                target=self._send_reminder_email, args=(email,), daemon=True
            ).start()

    def _cron_notify_telegram(self, text):
        if not self._telegram_bot_app or not self._telegram_allowed_users:
            return
        import asyncio
        try:
            for uid in list(self._telegram_allowed_users)[:3]:
                async def send():
                    try:
                        await self._telegram_bot_app.bot.send_message(
                            chat_id=int(uid), text=f"[Claudy Cron]\n{text}"
                        )
                    except Exception:
                        pass
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(send())
                except Exception:
                    pass
        except Exception:
            pass

    def _parse_cron_nl(self, prompt):
        """
        Parse natural-language cron requests in Spanish.
        Returns (kind, params, message) or None.
          kind = "interval", params = minutes
          kind = "daily",    params = (hour, minute)
        """
        text = prompt.strip()
        low = text.lower()

        # Skip if not a scheduling request
        triggers = ("recuerdame", "recuérdame", "avisame", "avísame", "avisa",
                    "recordatorio", "programa", "agenda", "cada ", "todos los",
                    "todas las", "diariamente", "diario", "/cron")
        if not any(t in low for t in triggers):
            return None

        # ---- INTERVAL: "cada N min|hora|horas" ----
        m = re.search(r'cada\s+(\d+)\s*(minutos?|mins?|m\b|horas?|h\b|segundos?|s\b)', low)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            if unit.startswith("s"):
                interval_min = max(1, n // 60)
            elif unit.startswith("h"):
                interval_min = n * 60
            else:
                interval_min = n
            msg = self._cron_strip_prefix(text)
            msg = re.sub(r'cada\s+\d+\s*(minutos?|mins?|m\b|horas?|h\b|segundos?|s\b)\s*', '', msg, count=1, flags=re.IGNORECASE).strip()
            msg = re.sub(r'^[,:\-\s]+', '', msg)
            if msg:
                return ("interval", interval_min, msg)

        # ---- DAILY: "a las HH(:MM)? (am|pm)?" ----
        # "a las 9", "a las 9am", "a las 14:30", "a las 22 hrs", "a las 9 de la noche"
        dm = re.search(r'a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|hrs|h)?(?:\s+de\s+la\s+(manana|mañana|tarde|noche))?', low)
        if dm:
            h = int(dm.group(1))
            mins = int(dm.group(2) or 0)
            ampm = (dm.group(3) or "").lower()
            partofday = (dm.group(4) or "").lower()
            if ampm == "pm" and h < 12:
                h += 12
            if ampm == "am" and h == 12:
                h = 0
            if partofday in ("tarde", "noche") and h < 12:
                h += 12
            if partofday in ("manana", "mañana") and h == 12:
                h = 0
            if 0 <= h <= 23 and 0 <= mins <= 59:
                msg = self._cron_strip_prefix(text)
                msg = re.sub(r'a\s+las?\s+\d{1,2}(?::\d{2})?\s*(am|pm|hrs|h)?(\s+de\s+la\s+(manana|mañana|tarde|noche))?\s*', '', msg, count=1, flags=re.IGNORECASE).strip()
                msg = re.sub(r'\b(todos\s+los\s+d[ií]as|diariamente|diario|cada\s+d[ií]a)\b\s*', '', msg, flags=re.IGNORECASE).strip()
                msg = re.sub(r'^[,:\-\s]+', '', msg)
                if msg:
                    return ("daily", (h, mins), msg)

        return None

    def _cron_strip_prefix(self, text):
        """Remove leading trigger words like 'recuerdame', 'avisame', '/cron'."""
        t = text
        t = re.sub(r'^/cron\s+', '', t, flags=re.IGNORECASE)
        t = re.sub(r'^(recuerdame|recuérdame|avisame|avísame|avisa|agenda|programa|recordatorio[:\s]*|que)\s+', '', t, flags=re.IGNORECASE)
        return t.strip()

    def _generate_cron_expression(self, prompt):
        """Generate a standard 5-field cron expression from Spanish text."""
        text = (prompt or "").strip()
        low = text.lower()
        if not any(k in low for k in (
            "/cron expr", "/cronexp", "generar cron", "genera cron", "crear cron",
            "crea cron", "expresion cron", "expresión cron", "cron para", "cron de"
        )):
            return None

        spec = re.sub(
            r'^(/cron\s+expr|/cronexp|generar\s+cron|genera\s+cron|crear\s+cron|crea\s+cron|'
            r'expresi[oó]n\s+cron|cron\s+(?:para|de))\s*[:\-]?\s*',
            '',
            text,
            flags=re.IGNORECASE,
        ).strip()
        if not spec:
            return (
                "Dime el horario que quieres convertir a cron.\n\n"
                "Ejemplos:\n"
                "  /cron expr cada 15 minutos\n"
                "  genera cron lunes a viernes a las 9:30\n"
                "  cron para el dia 1 de cada mes a las 8"
            )

        low_spec = spec.lower()

        def parse_time(default_hour=9, default_minute=0):
            m = re.search(
                r'a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|hrs|h)?'
                r'(?:\s+de\s+la\s+(manana|mañana|tarde|noche))?',
                low_spec,
            )
            if not m:
                return default_hour, default_minute, "hora por defecto 09:00"
            h = int(m.group(1))
            minute = int(m.group(2) or 0)
            ampm = (m.group(3) or "").lower()
            partofday = (m.group(4) or "").lower()
            if ampm == "pm" and h < 12:
                h += 12
            if ampm == "am" and h == 12:
                h = 0
            if partofday in ("tarde", "noche") and h < 12:
                h += 12
            if partofday in ("manana", "mañana") and h == 12:
                h = 0
            if not (0 <= h <= 23 and 0 <= minute <= 59):
                raise ValueError("Hora invalida. Usa 0-23 para hora y 0-59 para minutos.")
            return h, minute, f"{h:02d}:{minute:02d}"

        day_names = {
            "domingo": "0", "domingos": "0",
            "lunes": "1",
            "martes": "2",
            "miercoles": "3", "miércoles": "3",
            "jueves": "4",
            "viernes": "5",
            "sabado": "6", "sábado": "6", "sabados": "6", "sábados": "6",
        }

        try:
            # Intervals.
            m = re.search(r'cada\s+(\d+)\s*(minutos?|mins?|m\b)', low_spec)
            if m:
                n = max(1, min(59, int(m.group(1))))
                expr = f"*/{n} * * * *"
                desc = f"cada {n} minuto(s)"
                return self._format_cron_expression_result(expr, desc, spec)

            m = re.search(r'cada\s+(\d+)\s*(horas?|hrs?|h\b)', low_spec)
            if m:
                n = max(1, min(23, int(m.group(1))))
                expr = f"0 */{n} * * *"
                desc = f"cada {n} hora(s)"
                return self._format_cron_expression_result(expr, desc, spec)

            if re.search(r'\bcada\s+minuto\b|\btodos\s+los\s+minutos\b', low_spec):
                return self._format_cron_expression_result("* * * * *", "cada minuto", spec)

            if re.search(r'\bcada\s+hora\b|\btodas\s+las\s+horas\b', low_spec):
                return self._format_cron_expression_result("0 * * * *", "cada hora", spec)

            # Monthly by day number.
            m = re.search(r'(?:dia|día)\s+(\d{1,2})\s+de\s+cada\s+mes|cada\s+mes\s+(?:el\s+)?(?:dia|día)\s+(\d{1,2})', low_spec)
            if m:
                day = int(m.group(1) or m.group(2))
                if not 1 <= day <= 31:
                    raise ValueError("Dia de mes invalido. Usa 1-31.")
                h, minute, time_desc = parse_time()
                expr = f"{minute} {h} {day} * *"
                return self._format_cron_expression_result(expr, f"el dia {day} de cada mes a las {time_desc}", spec)

            # Week ranges and named days.
            h, minute, time_desc = parse_time()
            if re.search(r'lunes\s+a\s+viernes|d[ií]as\s+h[aá]biles|entre\s+semana', low_spec):
                return self._format_cron_expression_result(f"{minute} {h} * * 1-5", f"lunes a viernes a las {time_desc}", spec)

            if re.search(r'fines?\s+de\s+semana|sabados?\s+y\s+domingos?|s[aá]bados?\s+y\s+domingos?', low_spec):
                return self._format_cron_expression_result(f"{minute} {h} * * 6,0", f"fines de semana a las {time_desc}", spec)

            selected_days = []
            for name, value in day_names.items():
                if re.search(rf'\b{name}\b', low_spec) and value not in selected_days:
                    selected_days.append(value)
            if selected_days:
                expr = f"{minute} {h} * * {','.join(selected_days)}"
                return self._format_cron_expression_result(expr, f"dias seleccionados a las {time_desc}", spec)

            # Daily fallback when time is present or text says daily.
            if re.search(r'todos\s+los\s+d[ií]as|diario|diariamente|cada\s+d[ií]a|a\s+las?', low_spec):
                expr = f"{minute} {h} * * *"
                return self._format_cron_expression_result(expr, f"todos los dias a las {time_desc}", spec)

        except ValueError as e:
            return f"No pude generar el cron: {e}"

        return (
            "No pude convertirlo a cron con seguridad.\n\n"
            "Prueba con algo como:\n"
            "  genera cron cada 10 minutos\n"
            "  genera cron todos los dias a las 8:30\n"
            "  genera cron lunes a viernes a las 18:00\n"
            "  genera cron dia 1 de cada mes a las 9"
        )

    def _format_cron_expression_result(self, expr, description, original):
        return (
            "Expresion cron generada:\n\n"
            f"  {expr}\n\n"
            f"Significado: {description}\n"
            f"Entrada: {original}\n\n"
            "Formato: minuto hora dia_mes mes dia_semana\n"
            "Nota: usa cron Unix de 5 campos."
        )

    def _add_cron_interval(self, interval_min, message):
        job = {
            "id": str(int(time.time())),
            "type": "interval",
            "interval_min": interval_min,
            "message": message,
            "last_fired": "",
            "enabled": True,
            "created": datetime.datetime.now().isoformat(),
        }
        self._cron_jobs.append(job)
        self._save_cron_json()
        return f"Tarea programada cada {interval_min} min: {message[:80]}"

    def _add_cron_daily(self, hour, minute, message):
        job = {
            "id": str(int(time.time())),
            "type": "daily",
            "hour": hour,
            "minute": minute,
            "message": message,
            "last_fired": "",
            "enabled": True,
            "created": datetime.datetime.now().isoformat(),
        }
        self._cron_jobs.append(job)
        self._save_cron_json()
        return f"Tarea diaria a las {hour:02d}:{minute:02d}: {message[:80]}"

    def _add_cron_weekly(self, weekday, hour, minute, message, action=None, email=None):
        job = {
            "id": str(int(time.time())),
            "type": "weekly",
            "weekday": weekday,
            "hour": hour,
            "minute": minute,
            "message": message,
            "last_fired": "",
            "enabled": True,
            "created": datetime.datetime.now().isoformat(),
        }
        if action:
            job["action"] = action
        if email:
            job["email"] = email
        self._cron_jobs.append(job)
        self._save_cron_json()
        day = self._WEEKDAY_NAMES[weekday] if 0 <= weekday < 7 else "?"
        return f"Tarea semanal los {day} a las {hour:02d}:{minute:02d}: {message[:80]}"

    def _list_cron_jobs(self):
        if not self._cron_jobs:
            return ("No hay tareas programadas.\n\n"
                    "/cron cada 30 min <mensaje>\n"
                    "/cron a las 22:00 <mensaje>\n"
                    "/cron los martes a las 9 <mensaje>\n"
                    "/cron list\n"
                    "/cron editar <num> <campo> <valor>\n"
                    "/cron off|on <num>\n"
                    "/cron delete <num>")
        lines = ["Tareas programadas:", "=" * 40]
        for i, j in enumerate(self._cron_jobs, 1):
            t = j["type"]
            if t == "interval":
                schedule = f"cada {j['interval_min']} min"
            elif t == "weekly":
                wd = j.get("weekday", 0)
                day = self._WEEKDAY_NAMES[wd] if 0 <= wd < 7 else "?"
                schedule = f"los {day} a las {j.get('hour',0):02d}:{j.get('minute',0):02d}"
            else:
                schedule = f"diario a las {j.get('hour',0):02d}:{j.get('minute',0):02d}"
            enabled = "ON" if j.get("enabled", True) else "OFF"
            desc = j.get("message") or j.get("label") or (f"[{j.get('action')}]" if j.get("action") else "")
            lines.append(f"  [{i}] [{enabled}] {schedule}: {desc[:60]}")
        lines.append("")
        lines.append("Gestionar:")
        lines.append("  /cron editar <num> hora 22:30   (o: cada 45 min / dia martes / mensaje ...)")
        lines.append("  /cron off <num>   pausar      /cron on <num>   activar")
        lines.append("  /cron delete <num>   eliminar")
        return "\n".join(lines)

    def _delete_cron_job(self, idx):
        if idx < 0 or idx >= len(self._cron_jobs):
            return f"Numero invalido. Hay {len(self._cron_jobs)} tareas."
        removed = self._cron_jobs.pop(idx)
        self._save_cron_json()
        return f"Tarea eliminada: {removed.get('message','')[:60]}"

    def _toggle_cron_job(self, idx, enabled):
        """Pausa (enabled=False) o reanuda (enabled=True) una tarea."""
        if idx < 0 or idx >= len(self._cron_jobs):
            return f"Numero invalido. Hay {len(self._cron_jobs)} tareas."
        self._cron_jobs[idx]["enabled"] = bool(enabled)
        self._save_cron_json()
        estado = "activada" if enabled else "pausada"
        return f"Tarea {idx+1} {estado}: {self._cron_jobs[idx].get('message','')[:60]}"

    def _edit_cron_job(self, idx, *, message=None, hour=None, minute=None,
                       interval_min=None, weekday=None):
        """Modifica una tarea existente. Solo cambia los campos indicados."""
        if idx < 0 or idx >= len(self._cron_jobs):
            return f"Numero invalido. Hay {len(self._cron_jobs)} tareas."
        job = self._cron_jobs[idx]
        cambios = []
        if message is not None:
            job["message"] = message
            cambios.append(f"mensaje «{message[:50]}»")
        if interval_min is not None:
            job["type"] = "interval"
            job["interval_min"] = interval_min
            cambios.append(f"cada {interval_min} min")
        if weekday is not None:
            job["type"] = "weekly"
            job["weekday"] = weekday
            day = self._WEEKDAY_NAMES[weekday] if 0 <= weekday < 7 else "?"
            cambios.append(f"día {day}")
        if hour is not None:
            job["hour"] = hour
            if minute is not None:
                job["minute"] = minute
            # Cambiar la hora implica un horario fijo (diario salvo que ya sea semanal).
            if job.get("type") not in ("daily", "weekly"):
                job["type"] = "daily"
            cambios.append(f"hora {hour:02d}:{job.get('minute', 0):02d}")
        elif minute is not None:
            job["minute"] = minute
            cambios.append(f"minuto {minute:02d}")
        if not cambios:
            return ("No indicaste qué cambiar.\n"
                    "Ej: /cron editar 1 hora 22:30  |  /cron editar 1 mensaje nuevo texto  |  "
                    "/cron editar 1 cada 45 min  |  /cron editar 1 dia martes")
        # Reinicia el disparo para que el nuevo horario aplique limpio.
        job["last_fired"] = ""
        self._save_cron_json()
        return f"Tarea {idx+1} actualizada ({', '.join(cambios)})."

    def _apply_cron_edit_spec(self, idx, rest):
        """Interpreta el 'campo valor' de una edición y aplica el cambio."""
        rest = rest.strip()
        rlow = rest.lower()
        m = re.match(r'cada\s+(\d+)\s*(minutos?|mins?|m|horas?|hrs?|h)\b', rlow)
        if m:
            n = int(m.group(1))
            interval = n * 60 if m.group(2).startswith("h") else n
            return self._edit_cron_job(idx, interval_min=max(1, interval))
        m = re.search(r'(?:hora|a\s+las?)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', rlow)
        if m:
            h = int(m.group(1))
            minute = int(m.group(2) or 0)
            ampm = (m.group(3) or "")
            if ampm == "pm" and h < 12:
                h += 12
            if ampm == "am" and h == 12:
                h = 0
            if not (0 <= h <= 23 and 0 <= minute <= 59):
                return "Hora inválida. Usa 0-23 y 0-59."
            return self._edit_cron_job(idx, hour=h, minute=minute)
        m = re.match(r'(?:dia|día)\s+(\w+)', rlow)
        if m:
            wd = self._WEEKDAY_MAP.get(m.group(1))
            if wd is None:
                return "Día no reconocido. Usa lunes..domingo."
            return self._edit_cron_job(idx, weekday=wd)
        m = re.match(r'(?:mensaje|texto|msg)\s+(.+)', rest, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return self._edit_cron_job(idx, message=m.group(1).strip())
        # Sin campo explícito: se asume que es el nuevo mensaje.
        return self._edit_cron_job(idx, message=rest)

    def _manage_cron_command(self, prompt):
        """Gestión avanzada de tareas: editar, pausar/activar y crear semanales.
        Devuelve el texto de respuesta, o None si no es un comando de gestión."""
        text = (prompt or "").strip()
        low = text.lower()

        # Pausar: /cron off|pausar|desactivar <num>
        m = re.match(r'/cron\s+(?:off|pausar|pausa|desactivar)\s+(\d+)', low)
        if m:
            return self._toggle_cron_job(int(m.group(1)) - 1, False)
        # Activar: /cron on|activar|reanudar <num>
        m = re.match(r'/cron\s+(?:on|activar|activa|reanudar)\s+(\d+)', low)
        if m:
            return self._toggle_cron_job(int(m.group(1)) - 1, True)

        # Editar: /cron editar|edit|modificar|cambiar <num> <campo> <valor>
        m = re.match(r'/cron\s+(?:editar|edit|modificar|cambiar)\s+(\d+)\s+(.+)',
                     text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return self._apply_cron_edit_spec(int(m.group(1)) - 1, m.group(2))

        # Editar en lenguaje natural: "modifica/cambia/edita la tarea N ..."
        m = re.match(r'(?:cambia|cambiar|modifica|modificar|edita|editar)\s+(?:la\s+)?'
                     r'tarea\s+(\d+)\s+(?:a\s+|para\s+|por\s+)?(.+)',
                     text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return self._apply_cron_edit_spec(int(m.group(1)) - 1, m.group(2))

        # Pausar/activar en lenguaje natural.
        m = re.match(r'(?:pausa|pausar|desactiva|desactivar|detén|deten)\s+(?:la\s+)?tarea\s+(\d+)', low)
        if m:
            return self._toggle_cron_job(int(m.group(1)) - 1, False)
        m = re.match(r'(?:activa|activar|reanuda|reanudar)\s+(?:la\s+)?tarea\s+(\d+)', low)
        if m:
            return self._toggle_cron_job(int(m.group(1)) - 1, True)

        # Crear semanal: requiere intención explícita (/cron, o una palabra de
        # agenda como los/cada/todos los/programa/agenda/recuérdame/avísame) para
        # no capturar frases normales tipo "lunes a las 10 entrego el informe".
        m = re.match(
            r'(?:/cron\s+|los?\s+|cada\s+|todos\s+los\s+|'
            r'programa\s+|agenda\s+|recu[eé]rdame\s+(?:que\s+)?|av[ií]same\s+(?:que\s+)?)'
            r'(?:los?\s+|cada\s+)?'
            r'(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)'
            r'\s+a\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+(.+)',
            text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            wd = self._WEEKDAY_MAP.get(m.group(1).lower())
            if wd is None:
                return None
            h = int(m.group(2))
            minute = int(m.group(3) or 0)
            ampm = (m.group(4) or "")
            if ampm == "pm" and h < 12:
                h += 12
            if ampm == "am" and h == 12:
                h = 0
            if not (0 <= h <= 23 and 0 <= minute <= 59):
                return "Hora inválida. Usa 0-23 y 0-59."
            return self._add_cron_weekly(wd, h, minute, m.group(5).strip())

        return None

