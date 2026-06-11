"""Claudy features.email — Correos Mission Control (refactor v5).

Flujo guiado para redactar y sembrar borradores de correo en el Inbox de
Mission Control con las marcas de QCORE (SmartStudent, Point, QCORE SPA):
detección de destinatario/marca, redacción estructurada con el LLM y
plantillas HTML por marca.

Se usa como mixin: ClawdPet hereda de EmailMixin. Depende de helpers de la
clase compuesta: _llm_structured, _extract_json, _set_response_text,
_ui_colors (tema activo), send_quick_message, after.
"""
import os
import threading


class EmailMixin:
    _MC_KNOWN_CONTACTS = {
        "combas": {
            "name": "Conservatorio COMBAS",
            "aliases": ["combas", "conservatorio"],
            "to": ["secretaria@combas.cl"],
            "cc": ["jeanpaul.harb@combas.cl"],
            "brand": "smartstudent",
        },
        "tentacion": {
            "name": "Tentación a Granel",
            "aliases": ["tentacion", "tentación", "granel", "marco", "gonzalez", "gonzález"],
            "to": ["agraneltentacion@gmail.com"],
            "cc": [],
            "brand": "point",
        },
    }

    _MC_BRANDS = {
        "smartstudent": {
            "label": "SmartStudent (educativo)",
            "template": "smartstudent",
            "from": "SmartStudent <smartstudentweb@gmail.com>",
            "replyTo": "jorge.castro@qcorespa.com",
            "productId": "smartstudent",
            "primary": "#2563eb",
            "signature": "Equipo SmartStudent · www.smartstudent.cl",
            "guidance": "Marca SmartStudent (plataforma educativa SaaS). Tono cercano, claro y profesional, en español de Chile.",
        },
        "point": {
            "label": "Point (POS / comercio)",
            "template": "point",
            "from": "QCORE SPA <jorge.castro@qcorespa.com>",
            "replyTo": "jorge.castro@qcorespa.com",
            "productId": "",
            "primary": "#D81B60",
            "signature": "Equipo Point · QCORE SPA",
            "guidance": "Marca Point (sistema POS con control de inventario FEFO para comercios). Tono cercano, claro y práctico, orientado al dueño del negocio, en español de Chile.",
        },
        "qcore": {
            "label": "QCORE SPA (corporativo)",
            "from": "QCORE SPA <jorge.castro@qcorespa.com>",
            "replyTo": "jorge.castro@qcorespa.com",
            "productId": "",
            "primary": "#6c5ce7",
            "signature": "QCORE SPA · jorge.castro@qcorespa.com",
            "guidance": "Marca QCORE SPA (consultora tecnológica). Tono profesional corporativo, en español de Chile.",
        },
    }

    def _try_seed_mc_draft(self, prompt, plow, status, entry=None):
        """Detecta pedidos de 'crear correo borrador' y lanza el flujo guiado que
        pregunta destinatario, ubicación en Mission Control y estilo antes de
        sembrarlo en el Inbox (logs/seeded-drafts.json). Devuelve True si tomó el pedido."""
        create_verbs = (
            "crea", "créa", "crear", "haz", "hazme", "redacta", "redáctame",
            "prepara", "prepárame", "genera", "escribe", "escríbeme", "arma", "ármame",
            "quiero", "necesito", "dame",
        )
        has_create = any(v in plow for v in create_verbs)
        mentions_draft = "borrador" in plow
        mentions_mail = any(w in plow for w in ("correo", "email", "e-mail", "mail"))
        mentions_mc = any(w in plow for w in ("mission control", "inbox", "casilla", "bandeja"))

        # Un borrador de correo SIEMPRE es para Mission Control. Señal fuerte:
        # "borrador" junto a correo/MC dispara aunque no haya verbo de creación.
        strong = mentions_draft and (mentions_mail or mentions_mc)
        if not (strong or (has_create and (mentions_mail or mentions_draft))):
            return False

        self._start_guided_email_flow(prompt, plow, status, entry)
        return True

    def _detect_email_style(self, plow):
        """Detecta la marca/estilo mencionada en el texto. Devuelve la clave o None."""
        if "smart" in plow:
            return "smartstudent"
        if "point" in plow or " pos" in plow:
            return "point"
        if "qcore" in plow or "corporativo" in plow:
            return "qcore"
        return None

    def _extract_email_topic(self, prompt, plow):
        """Quita el 'andamiaje' (verbos, 'correo/borrador', destinatario, estilo, MC) y
        devuelve el tema restante. Sirve para decidir si hay contenido suficiente."""
        import re as _re
        t = " " + (prompt or "") + " "
        t = _re.sub(r'\b(crea|créa|crear|haz|hazme|redacta|redáctame|prepara|prepárame|genera|escribe|escríbeme|arma|ármame|quiero|necesito|dame)\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\b(un|una|el|la|los|las|de|del)\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\b(correo|email|e-mail|mail|borrador|mensaje)\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\bestilo\s+\w+\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\b(smartstudent|point|qcore|pos|corporativo)\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\b(mission\s+control|misi[oó]n\s+control|inbox|casilla|bandeja)\b', ' ', t, flags=_re.I)
        for c in self._MC_KNOWN_CONTACTS.values():
            for a in c.get("aliases", []):
                t = _re.sub(r'\b' + _re.escape(a) + r'\b', ' ', t, flags=_re.I)
        t = _re.sub(r'\b(a\s+granel)\b', ' ', t, flags=_re.I)
        t = _re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', ' ', t)  # emails
        # conectores colgantes al inicio
        t = _re.sub(r'^\s*(para|a|que\s+sea|y\s+que\s+sea|y\s+que|que|sobre|avisando\s+que|avisando|diciendo\s+que|informando\s+que|informando|enviando)\s+', ' ', t, flags=_re.I)
        t = _re.sub(r'\s+', ' ', t).strip(" ,.;:-")
        return t

    def _start_guided_email_flow(self, prompt, plow, status, entry):
        # Detectar contacto conocido para ofrecerlo primero (sin auto-seleccionarlo).
        detected_key = None
        for key, c in self._MC_KNOWN_CONTACTS.items():
            if any(a in plow for a in c.get("aliases", [key])):
                detected_key = key
                break

        # ── ONE-SHOT: si ya hay destinatario + tema claro, saltamos las preguntas ──
        topic = self._extract_email_topic(prompt, plow)
        detected_style = self._detect_email_style(plow)
        if detected_key and topic and len(topic.split()) >= 3:
            c = self._MC_KNOWN_CONTACTS[detected_key]
            brand_key = detected_style or c.get("brand", "qcore")
            self._guided_email_active = False
            self._guided_email_step = 0
            self._guided_email_data = {
                "prompt": prompt,
                "content": prompt,  # el LLM se enfoca en el pedido real
                "recipient_name": c["name"],
                "contact_key": detected_key,
                "to_list": list(c.get("to", [])),
                "cc_list": list(c.get("cc", [])),
                "kind": "general-reply",
                "origin": "direct-email",
                "brand_key": brand_key,
            }
            chat = getattr(self, "_chat_view", None)
            if chat is not None:
                try:
                    last = chat._messages[-1] if getattr(chat, "_messages", None) else None
                    if not (last and last.get("role") == "user" and last.get("text") == prompt):
                        chat.add_user(prompt)
                except Exception:
                    pass
            self._finalize_and_seed_email(self._guided_email_data, status)
            return

        self._guided_email_active = True
        self._guided_email_step = 1
        self._guided_email_data = {
            "prompt": prompt,
            "content": None,
            "recipient_name": None,
            "contact_key": None,
            "to_list": [],
            "cc_list": [],
            "kind": "general-reply",
            "origin": "direct-email",
            "brand_key": "qcore",
            "style_label": None,
        }
        self._bubble_status = status
        self._bubble_entry = entry

        chat = getattr(self, "_chat_view", None)
        if chat is not None:
            try:
                last = chat._messages[-1] if getattr(chat, "_messages", None) else None
                if not (last and last.get("role") == "user" and last.get("text") == prompt):
                    chat.add_user(prompt)
            except Exception:
                pass
            chat.add_bot(
                "Vamos a preparar el borrador para el **Inbox de Mission Control**.\n\n"
                "**Pregunta 1/3: ¿A quién va dirigido el correo?**"
            )
            options = []
            for key, c in self._MC_KNOWN_CONTACTS.items():
                dest = ", ".join(c.get("to", [])) or "sin destinatario"
                label = f"{c['name']}" + (" ⭐" if key == detected_key else "")
                options.append((f"contact:{key}", label, dest))
            options.append(("otro", "Otro cliente / destinatario", "Escribe el correo del nuevo cliente o destinatario a continuación"))
            chat.add_options(options, self._handle_email_option_select)

        try:
            status.configure(text="Correo · Paso 1: Destinatario", fg=self._ui_colors()["accent"])
        except Exception:
            pass
        if entry is not None:
            try:
                entry.configure(state="normal")
                entry.focus_set()
            except Exception:
                pass

    def _handle_email_option_select(self, option_value):
        status = getattr(self, "_bubble_status", None)
        entry = getattr(self, "_bubble_entry", None)
        self._handle_guided_email_step(option_value, status, entry)

    def _ask_email_content(self, chat, status):
        self._guided_email_step = 15
        chat.add_bot("**Pregunta 2/3: ¿De qué se trata el correo?** (escríbelo con tus palabras)")
        try:
            status.configure(text="Correo · Paso 2: Contenido", fg=self._ui_colors()["accent"])
        except Exception:
            pass

    def _ask_email_style(self, chat, status):
        self._guided_email_step = 4
        chat.add_bot("**Pregunta 3/3: ¿Qué estilo / marca usamos para redactar?**")
        descs = {
            "smartstudent": "Plataforma educativa. Tono cercano y profesional (plantilla SmartStudent, azul)",
            "point": "POS / comercio. Tono cercano y práctico para el dueño del negocio (rosado Point)",
            "qcore": "Consultora tecnológica. Tono profesional corporativo (morado QCORE)",
        }
        suggested = self._guided_email_data.get("brand_key", "qcore")
        order = [suggested] + [k for k in ("smartstudent", "point", "qcore") if k != suggested]
        options = []
        for k in order:
            b = self._MC_BRANDS.get(k)
            if not b:
                continue
            label = b.get("label", k)
            if k == suggested:
                label += " ⭐"
            options.append((k, label, descs.get(k, "")))
        chat.add_options(options, self._handle_email_option_select)
        try:
            status.configure(text="Correo · Paso 3: Estilo", fg=self._ui_colors()["accent"])
        except Exception:
            pass

    def _handle_guided_email_step(self, prompt, status, entry):
        chat = getattr(self, "_chat_view", None)
        if chat is None:
            return
        data = self._guided_email_data
        step = self._guided_email_step
        plow = (prompt or "").lower().strip()

        if step == 1:
            # Elegir destinatario.
            if prompt.startswith("contact:"):
                key = prompt.split(":", 1)[1]
                c = self._MC_KNOWN_CONTACTS.get(key)
                if c:
                    data["recipient_name"] = c["name"]
                    data["contact_key"] = key
                    data["to_list"] = list(c.get("to", []))
                    data["cc_list"] = list(c.get("cc", []))
                    data["brand_key"] = c.get("brand", "qcore")
                    chat.add_user(c["name"])
                    self._ask_email_content(chat, status)
                    return
            if prompt == "otro" or plow == "otro":
                self._guided_email_step = 2
                chat.add_bot("Escribe el **correo (o nombre)** del destinatario:")
                try:
                    status.configure(text="Correo · Destinatario personalizado", fg=self._ui_colors()["accent"])
                except Exception:
                    pass
                return
            # Si escribió algo libre, intentar resolver contacto conocido o usarlo como destinatario.
            matched = None
            for key, c in self._MC_KNOWN_CONTACTS.items():
                if any(a in plow for a in c.get("aliases", [key])):
                    matched = (key, c)
                    break
            if matched:
                key, c = matched
                data["recipient_name"] = c["name"]
                data["contact_key"] = key
                data["to_list"] = list(c.get("to", []))
                data["cc_list"] = list(c.get("cc", []))
                data["brand_key"] = c.get("brand", "qcore")
                chat.add_user(c["name"])
            else:
                self._set_custom_recipient(data, prompt)
                chat.add_user(prompt)
            self._ask_email_content(chat, status)
            return

        if step == 2:
            # Destinatario personalizado escrito por el usuario.
            self._set_custom_recipient(data, prompt)
            chat.add_user(prompt)
            self._ask_email_content(chat, status)
            return

        if step == 15:
            # Contenido / tema del correo.
            content = (prompt or "").strip()
            data["content"] = content
            chat.add_user(content if len(content) <= 120 else content[:117] + "…")
            self._ask_email_style(chat, status)
            return

        if step == 4:
            # Estilo / marca.
            if prompt in self._MC_BRANDS:
                brand_key = prompt
            elif "smart" in plow:
                brand_key = "smartstudent"
            elif "point" in plow or "pos" in plow:
                brand_key = "point"
            elif "qcore" in plow or "corporativo" in plow:
                brand_key = "qcore"
            else:
                brand_key = data.get("brand_key", "qcore")
            data["brand_key"] = brand_key
            data["style_label"] = self._MC_BRANDS.get(brand_key, self._MC_BRANDS["qcore"]).get("label", brand_key)
            chat.add_user(data["style_label"])
            self._finalize_and_seed_email(data, status)
            return

    def _finalize_and_seed_email(self, data, status):
        """Cierra el flujo y dispara la redacción/siembra del borrador en el Inbox de MC.
        Los borradores SIEMPRE quedan en el Inbox (kind general-reply / origin direct-email)."""
        chat = getattr(self, "_chat_view", None)
        self._guided_email_active = False
        self._guided_email_step = 0
        brand_key = data.get("brand_key", "qcore")
        brand = self._MC_BRANDS.get(brand_key, self._MC_BRANDS["qcore"])
        data["style_label"] = brand.get("label", brand_key)
        dest = ", ".join(data.get("to_list") or []) or "(sin destinatario — complétalo en el Inbox)"
        if chat:
            chat.add_bot(
                "Listo, tengo todo. Redactando el borrador para el **Inbox de Mission Control**…\n\n"
                f"**Para:** {dest}\n"
                f"**Estilo:** {data.get('style_label')}"
            )
            chat.show_typing()
        try:
            status.configure(text="Redactando borrador para Mission Control...", fg="#58c7ff")
        except Exception:
            pass
        brief = data.get("content") or data.get("prompt") or ""
        threading.Thread(
            target=self._seed_mc_draft_worker,
            args=(brief, data.get("recipient_name") or "destinatario",
                  data.get("contact_key") or "contacto", brand,
                  list(data.get("to_list") or []), list(data.get("cc_list") or []), status,
                  data.get("kind", "general-reply"), data.get("origin", "direct-email"),
                  data.get("custom_reference")),
            daemon=True,
        ).start()

    def _set_custom_recipient(self, data, text):
        import re as _re
        emails = _re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text or "")
        if emails:
            data["to_list"] = emails
            data["recipient_name"] = emails[0].split("@")[0]
        else:
            data["to_list"] = []
            data["recipient_name"] = (text or "").strip() or "destinatario"
        data["cc_list"] = []
        data["contact_key"] = _re.sub(r"[^a-z0-9]+", "-", (data["recipient_name"] or "contacto").lower()).strip("-") or "contacto"

    def _structured_email_llm_prompt(self, role_desc, recipient_name, prompt, eyebrow_hint, tail_hint):
        """Prompt común para plantillas con contenido estructurado (SmartStudent / Point)."""
        return (
            f"{role_desc}\n"
            f"Destinatario: {recipient_name}.\n\n"
            "=== PEDIDO DEL USUARIO (este es el TEMA del correo, respétalo al pie de la letra) ===\n"
            f"{prompt}\n"
            "=== FIN DEL PEDIDO ===\n\n"
            "Redacta el correo SOBRE EXACTAMENTE ese pedido. El asunto, la intro y los items deben "
            "tratar ese tema concreto y nada más. Si el pedido es puntual (p. ej. avisar que el contrato "
            "quedó firmado por ambas partes), NO inventes un listado de features ni un pitch de producto: "
            "escribe solo lo que corresponde a ese mensaje.\n\n"
            "Devuelve UNICAMENTE un objeto JSON válido (sin texto antes ni después, sin fences) "
            "con esta forma exacta:\n"
            '{\n'
            '  "subject": "asunto breve y claro, sobre el tema del pedido",\n'
            '  "eyebrow": "ETIQUETA EN MAYÚSCULAS que resuma el tema del pedido",\n'
            '  "greeting_name": "nombre de pila del destinatario o \"\" si se desconoce",\n'
            '  "greeting_tail": "remate corto del saludo acorde al tema",\n'
            '  "intro": "párrafo introductorio de 1-2 frases sobre el tema",\n'
            '  "items": [ {"title": "título del punto", "body": "descripción (puede usar <strong> y <code>)", "featured": false} ],\n'
            '  "recommendation": "texto de recomendación final o \"\" si no aplica",\n'
            '  "closing": "frase de cierre breve"\n'
            '}\n'
            f"(Solo como referencia de FORMATO, no de tema: un eyebrow se ve así \"{eyebrow_hint}\" y un "
            f"remate así \"{tail_hint}\" — pero adáptalos al pedido real.)\n"
            "Reglas: 'items' es una lista de 1 a 6 puntos; si el pedido no amerita varios puntos, usa 1. "
            "Marca featured=true solo en un punto si hay uno destacado. No incluyas saludos ni firma dentro "
            "de los textos: eso lo arma la plantilla. No incluyas HTML completo, solo los campos pedidos. Solo el JSON."
        )

    def _build_point_email_html(self, data, recipient_name, prompt):
        """Arma el HTML del correo con la plantilla institucional Point
        (header magenta, eyebrow rosado, tarjetas numeradas con badge rosado,
        punto destacado en variante morada, callout morado, firma Jorge Castro · QCORE)."""
        import html as _html

        def esc(v):
            return _html.escape((v or "").strip())

        eyebrow = esc(data.get("eyebrow")) or "POINT · COMERCIO"
        greeting_name = esc(data.get("greeting_name"))
        greeting_tail = esc(data.get("greeting_tail")) or "acá va tu sistema"
        intro = esc(data.get("intro")) or "Te escribo con la información de tu sistema Point."
        closing = esc(data.get("closing")) or "Cualquier duda me escribes y te acompaño. ¡Saludos!"
        recommendation = (data.get("recommendation") or "").strip()

        items = data.get("items")
        if not isinstance(items, list) or not items:
            items = [{"title": "Detalle", "body": esc(prompt) or "Te comparto la información solicitada."}]

        if greeting_name:
            title = f"Hola {greeting_name} \U0001F44B — {greeting_tail}"
        else:
            title = f"\U0001F44B {greeting_tail}"

        cards = []
        for i, it in enumerate(items, start=1):
            it = it if isinstance(it, dict) else {}
            t = esc(it.get("title")) or f"Paso {i}"
            body = (it.get("body") or "").strip()  # permite <strong>/<code> del LLM
            featured = bool(it.get("featured"))
            box_bg = "#f5f3ff" if featured else "#fdf2f8"
            box_border = "#ddd6fe" if featured else "#fbcfe8"
            badge_bg = "#8E24AA" if featured else "#D81B60"
            cards.append(
                f'''          <tr>
            <td style="padding:0 40px 12px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="background:{box_bg};border:1px solid {box_border};border-radius:12px;">
                <tr>
                  <td style="padding:18px 20px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="width:40px;vertical-align:top;">
                          <div style="width:32px;height:32px;border-radius:8px;background:{badge_bg};color:#ffffff;font-size:15px;font-weight:800;text-align:center;line-height:32px;">{i}</div>
                        </td>
                        <td>
                          <div style="font-size:15px;font-weight:700;color:#0f172a;">{t}</div>
                          <div style="font-size:13px;color:#475569;margin-top:6px;line-height:1.6;">{body}</div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>'''
            )

        rec_html = ""
        if recommendation:
            rec_html = f'''          <tr>
            <td style="padding:0 40px 24px;">
              <div style="border-left:3px solid #8E24AA;background:#f8fafc;padding:14px 18px;border-radius:0 8px 8px 0;">
                <div style="font-size:12px;font-weight:700;color:#8E24AA;text-transform:uppercase;letter-spacing:1px;">Recomendación</div>
                <div style="font-size:13px;color:#475569;margin-top:4px;line-height:1.6;">{recommendation}</div>
              </div>
            </td>
          </tr>'''

        return f'''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(15,23,42,0.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#1a0a14 0%,#3d0f2e 50%,#5b1248 100%);padding:0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr><td style="height:4px;background:linear-gradient(90deg,#D81B60,#8E24AA,#D81B60);"></td></tr>
                <tr>
                  <td style="padding:32px 40px 24px;">
                    <div style="font-size:28px;font-weight:900;color:#ffffff;letter-spacing:1px;">Point<span style="color:#D81B60;"> POS</span></div>
                    <div style="font-size:12px;color:#e9b8d4;margin-top:4px;letter-spacing:2px;text-transform:uppercase;">Punto de venta + inventario · by QCORE</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:32px 40px 12px;">
              <div style="font-size:12px;color:#D81B60;font-weight:700;letter-spacing:2px;text-transform:uppercase;">{eyebrow}</div>
              <h1 style="margin:8px 0 0;font-size:22px;font-weight:800;color:#0f172a;line-height:1.3;">{title}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 40px 20px;">
              <p style="margin:0;font-size:14px;color:#475569;line-height:1.6;">{intro}</p>
            </td>
          </tr>
{chr(10).join(cards)}
{rec_html}
          <tr>
            <td style="padding:0 40px 32px;">
              <p style="margin:0 0 6px;font-size:14px;color:#475569;line-height:1.6;">{closing}</p>
              <table cellpadding="0" cellspacing="0" style="margin-top:24px;border-top:1px solid #e2e8f0;padding-top:20px;width:100%;">
                <tr>
                  <td style="padding-right:16px;vertical-align:middle;width:72px;">
                    {self._qcore_logo_badge_html(64, 34)}
                  </td>
                  <td style="vertical-align:middle;border-left:2px solid #e2e8f0;padding-left:16px;">
                    <div style="font-size:14px;font-weight:700;color:#1e293b;">Jorge Castro</div>
                    <div style="font-size:12px;color:#475569;margin-top:2px;">Account Director · QCORE</div>
                    <div style="font-size:12px;color:#64748b;margin-top:2px;">Santiago, Chile</div>
                    <div style="margin-top:4px;line-height:1.4;">
                      <a href="mailto:jorge.castro@qcorespa.com" style="color:#D81B60;text-decoration:none;font-size:12px;font-weight:500;">jorge.castro@qcorespa.com</a>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background:#f8fafc;padding:20px 40px;text-align:center;">
              <div style="font-size:10px;color:#94a3b8;line-height:1.6;">Point POS · Enviado por QCORE GROUP TECHNOLOGIES SPA · Santiago, Chile</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''

    def _qcore_logo_badge_html(self, size=64, font=34):
        """Badge institucional QCORE (cuadro morado redondeado con la 'Q' blanca).
        Se usa como logo en las firmas hasta que exista una imagen hospedada."""
        radius = round(size / 4)
        return (
            f'<table cellpadding="0" cellspacing="0" role="presentation" '
            f'style="width:{size}px;height:{size}px;border-radius:{radius}px;'
            f'background-color:#4f46e5;background:linear-gradient(135deg,#7b6ef0,#4f46e5);">'
            f'<tr><td align="center" valign="middle" style="font-size:{font}px;font-weight:800;'
            f'color:#ffffff;font-family:\'Segoe UI\',Arial,sans-serif;line-height:{size}px;">Q</td></tr>'
            f'</table>'
        )

    def _build_qcore_email_html(self, data, recipient_name, prompt):
        """Envuelve el cuerpo redactado en una tarjeta corporativa QCORE con la
        firma institucional fija (badge "Q", Jorge Castro · Account Director ·
        Santiago, Chile · www.qcorespa.com)."""
        import html as _html

        body_html = (data.get("body_html") or "").strip()
        if not body_html:
            safe = _html.escape((prompt or "").strip())
            body_html = (
                f'<p style="margin:0 0 12px;font-size:14px;color:#1e293b;line-height:1.6;">Estimado/a {_html.escape(recipient_name)},</p>'
                f'<p style="margin:0;font-size:14px;color:#475569;line-height:1.6;">{safe}</p>'
            )

        return f'''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(15,23,42,0.08);">
          <tr><td style="height:4px;background:linear-gradient(90deg,#6c5ce7,#4f46e5,#a29bfe);"></td></tr>
          <tr>
            <td style="padding:32px 40px 8px;font-size:14px;color:#1e293b;line-height:1.6;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:24px 40px 32px;">
              <p style="margin:0 0 18px;font-size:14px;color:#475569;line-height:1.6;">Saludos Cordiales,</p>
              <table cellpadding="0" cellspacing="0" style="width:100%;">
                <tr>
                  <td style="padding-right:16px;vertical-align:middle;width:72px;">
                    {self._qcore_logo_badge_html(64, 34)}
                  </td>
                  <td style="vertical-align:middle;border-left:2px solid #e2e8f0;padding-left:16px;">
                    <div style="font-size:16px;font-weight:700;color:#1e293b;">Jorge Castro</div>
                    <div style="font-size:13px;color:#64748b;margin-top:2px;">Account Director</div>
                    <div style="font-size:13px;color:#64748b;margin-top:2px;">Santiago, Chile</div>
                    <div style="margin-top:4px;line-height:1.2;">
                      <a href="https://www.qcorespa.com" style="color:#4f46e5;text-decoration:none;font-size:13px;font-weight:500;">www.qcorespa.com</a>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background:#f8fafc;padding:20px 40px;text-align:center;">
              <div style="font-size:10px;color:#94a3b8;line-height:1.6;">Este correo fue enviado por QCORE SPA · Santiago, Chile</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''

    def _build_smartstudent_email_html(self, data, recipient_name, prompt):
        """Arma el HTML del correo con la plantilla institucional SmartStudent
        (header navy, eyebrow azul, tarjetas numeradas con ✓, callout de
        recomendación, firma de Jorge Castro y footer QCORE)."""
        import html as _html

        def esc(v):
            return _html.escape((v or "").strip())

        eyebrow = esc(data.get("eyebrow")) or "ACTUALIZACIÓN PLATAFORMA"
        greeting_name = esc(data.get("greeting_name"))
        greeting_tail = esc(data.get("greeting_tail")) or "tu plataforma quedó al día"
        intro = esc(data.get("intro")) or (
            "Quería confirmarte que aplicamos las configuraciones que conversamos."
        )
        closing = esc(data.get("closing")) or "Cualquier ajuste me avisas. ¡Saludos!"
        recommendation = (data.get("recommendation") or "").strip()

        items = data.get("items")
        if not isinstance(items, list) or not items:
            items = [{"title": "Detalle", "body": esc(prompt) or "Te comparto la actualización solicitada."}]

        if greeting_name:
            title = f"Hola {greeting_name} \U0001F44B — {greeting_tail}"
        else:
            title = f"\U0001F44B {greeting_tail}"

        cards = []
        for i, it in enumerate(items, start=1):
            it = it if isinstance(it, dict) else {}
            t = esc(it.get("title")) or f"Punto {i}"
            body = (it.get("body") or "").strip()  # permite <strong>/<code> del LLM
            featured = bool(it.get("featured"))
            box_bg = "#eff6ff" if featured else "#f8fafc"
            box_border = "#bfdbfe" if featured else "#e2e8f0"
            badge_bg = "#2563eb" if featured else "#dcfce7"
            badge_fg = "#ffffff" if featured else "#16a34a"
            badge_char = "★" if featured else "✓"
            title_html = (
                f'<div style="font-size:15px;font-weight:700;color:#0f172a;">{i} · '
                f'<span style="color:#2563eb;">{t}</span></div>' if featured
                else f'<div style="font-size:15px;font-weight:700;color:#0f172a;">{i} · {t}</div>'
            )
            cards.append(
                f'''          <tr>
            <td style="padding:0 40px 16px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="background:{box_bg};border:1px solid {box_border};border-radius:12px;">
                <tr>
                  <td style="padding:18px 20px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="width:36px;vertical-align:top;">
                          <div style="width:32px;height:32px;border-radius:8px;background:{badge_bg};color:{badge_fg};font-size:16px;font-weight:800;text-align:center;line-height:32px;">{badge_char}</div>
                        </td>
                        <td>
                          {title_html}
                          <div style="font-size:13px;color:#475569;margin-top:4px;line-height:1.5;">{body}</div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>'''
            )

        rec_html = ""
        if recommendation:
            rec_html = f'''          <tr>
            <td style="padding:0 40px 24px;">
              <div style="border-left:3px solid #2563eb;background:#f8fafc;padding:14px 18px;border-radius:0 8px 8px 0;">
                <div style="font-size:12px;font-weight:700;color:#2563eb;text-transform:uppercase;letter-spacing:1px;">Recomendación</div>
                <div style="font-size:13px;color:#475569;margin-top:4px;line-height:1.6;">{recommendation}</div>
              </div>
            </td>
          </tr>'''

        logo = self._SMARTSTUDENT_LOGO_URL
        return f'''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(15,23,42,0.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#060d1a 0%,#0d1b2e 50%,#112240 100%);padding:0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr><td style="height:4px;background:linear-gradient(90deg,#2563eb,#3B82F6,#4ADE80);"></td></tr>
                <tr>
                  <td style="padding:32px 40px 24px;">
                    <table cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <td style="vertical-align:middle;width:88px;padding-right:10px;">
                          <img src="{logo}" alt="SmartStudent" style="width:80px;height:80px;border-radius:16px;object-fit:contain;display:block;" />
                        </td>
                        <td>
                          <div style="font-size:28px;font-weight:900;color:#ffffff;letter-spacing:1px;">Smart<span style="color:#2563eb;">Student</span></div>
                          <div style="font-size:12px;color:#94a3b8;margin-top:4px;letter-spacing:2px;text-transform:uppercase;">Gestión Escolar con Inteligencia Artificial</div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:32px 40px 12px;">
              <div style="font-size:12px;color:#2563eb;font-weight:700;letter-spacing:2px;text-transform:uppercase;">{eyebrow}</div>
              <h1 style="margin:8px 0 0;font-size:22px;font-weight:800;color:#0f172a;line-height:1.3;">{title}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 40px 20px;">
              <p style="margin:0;font-size:14px;color:#475569;line-height:1.6;">{intro}</p>
            </td>
          </tr>
{chr(10).join(cards)}
{rec_html}
          <tr>
            <td style="padding:0 40px 32px;">
              <p style="margin:0 0 6px;font-size:14px;color:#475569;line-height:1.6;">{closing}</p>
              <table cellpadding="0" cellspacing="0" style="margin-top:24px;border-top:1px solid #e2e8f0;padding-top:20px;width:100%;">
                <tr>
                  <td style="padding-right:14px;vertical-align:top;width:90px;">
                    <img src="{logo}" alt="SmartStudent" style="width:80px;height:80px;border-radius:20px;object-fit:contain;display:block;" />
                  </td>
                  <td style="vertical-align:top;">
                    <div style="font-size:14px;font-weight:700;color:#1e293b;">Jorge Castro</div>
                    <div style="font-size:12px;color:#475569;margin-top:2px;">Account Director · SmartStudent</div>
                    <div style="font-size:12px;color:#64748b;margin-top:2px;">Santiago, Chile</div>
                    <div style="margin-top:4px;line-height:1.2;">
                      <a href="https://www.smartstudent.cl" style="color:#2563eb;text-decoration:none;font-size:12px;font-weight:500;">www.smartstudent.cl</a>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background:#f8fafc;padding:20px 40px;text-align:center;">
              <div style="font-size:10px;color:#94a3b8;line-height:1.6;">Este correo fue enviado por QCORE SPA · Santiago, Chile</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''

    def _seed_mc_draft_worker(self, prompt, recipient_name, contact_key, brand, to_list, cc_list, status,
                              kind="general-reply", origin="direct-email", custom_reference=None):
        import datetime as _dt
        import json as _json
        template = brand.get("template")
        try:
            if template == "smartstudent":
                llm_prompt = self._structured_email_llm_prompt(
                    "Eres redactor de correos de SmartStudent (plataforma educativa SaaS). "
                    "Tono cercano, claro y profesional, en español de Chile.",
                    recipient_name, prompt,
                    "ACTUALIZACIÓN PLATAFORMA · COMBAS", "tu plataforma quedó al día",
                )
                raw = self._llm_structured(llm_prompt, expect_json=True)
                data = self._extract_json(raw) or {}
                subject = (data.get("subject") or "").strip() or f"Actualización SmartStudent · {recipient_name}"
                html = self._build_smartstudent_email_html(data, recipient_name, prompt)
            elif template == "point":
                llm_prompt = self._structured_email_llm_prompt(
                    "Eres redactor de correos de Point (sistema POS con control de inventario FEFO para comercios). "
                    "Tono cercano, claro y práctico, orientado al dueño del negocio, en español de Chile.",
                    recipient_name, prompt,
                    "ENTREGA DE SOFTWARE · TENTACIÓN A GRANEL", "acá va tu sistema listo",
                )
                raw = self._llm_structured(llm_prompt, expect_json=True)
                data = self._extract_json(raw) or {}
                subject = (data.get("subject") or "").strip() or f"Point · {recipient_name}"
                html = self._build_point_email_html(data, recipient_name, prompt)
            else:
                llm_prompt = (
                    f"Eres redactor de correos profesionales. {brand['guidance']}\n"
                    f"Destinatario: {recipient_name}.\n"
                    f"Pedido del usuario: \"{prompt}\".\n\n"
                    "Redacta SOLO el cuerpo del correo en español (saludo inicial + párrafos). "
                    "NO incluyas despedida, ni firma, ni datos de contacto: eso se añade automáticamente. "
                    "Devuelve UNICAMENTE un objeto JSON válido, sin texto antes ni después y sin fences, "
                    "con esta forma exacta:\n"
                    '{"subject": "asunto breve", "body_html": "<p>saludo</p><p>párrafos del cuerpo en HTML</p>"}\n'
                    "El body_html debe usar etiquetas <p> con estilos inline simples y profesionales. "
                    "No incluyas comentarios ni explicaciones, solo el JSON."
                )
                raw = self._llm_structured(llm_prompt, expect_json=True)
                data = self._extract_json(raw) or {}
                subject = (data.get("subject") or "").strip() or f"Mensaje para {recipient_name}"
                html = self._build_qcore_email_html(data, recipient_name, prompt)

            now = _dt.datetime.now(_dt.timezone.utc)
            stamp = now.strftime("%Y%m%d%H%M%S")
            iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            seed_id = f"seed-claudy-{contact_key}-{stamp}"
            draft = {
                "id": seed_id,
                "kind": kind,
                "relatedMessageId": f"{seed_id}-msg",
                "createdAt": iso,
                "status": "pending-approval",
                "origin": origin,
                "reason": (custom_reference.strip()[:200] if custom_reference and custom_reference.strip()
                           else f"Borrador creado por Claudy a partir de: {prompt.strip()[:200]}"),
                "from": brand["from"],
                "to": to_list,
                "cc": cc_list,
                "replyTo": brand["replyTo"],
                "subject": subject,
                "html": html,
            }
            if brand.get("productId"):
                draft["productId"] = brand["productId"]

            path = self._MC_SEEDED_DRAFTS_PATH
            existing = []
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        loaded = _json.load(f)
                        if isinstance(loaded, list):
                            existing = loaded
            except Exception:
                existing = []
            existing.append(draft)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                _json.dump(existing, f, ensure_ascii=False, indent=2)

            dest = ", ".join(to_list) if to_list else "(sin destinatario — complétalo en el Inbox)"
            def _ok():
                ch = getattr(self, "_chat_view", None)
                if ch:
                    ch.hide_typing()
                    ch.add_system(
                        f"✅ Borrador creado en el **Inbox de Mission Control**.\n\n"
                        f"**Para:** {dest}\n**Asunto:** {subject}\n\n"
                        f"Aparecerá en *Borradores pendientes* en ~1 segundo si Mission Control está abierto."
                    )
                try:
                    status.configure(text="Borrador sembrado en Mission Control", fg="#00ff99")
                except Exception:
                    pass
            self.after(0, _ok)
        except Exception as e:
            def _err(ex=e):
                ch = getattr(self, "_chat_view", None)
                if ch:
                    ch.hide_typing()
                    ch.add_system(f"❌ No pude crear el borrador en Mission Control: {ex}")
                try:
                    status.configure(text=f"Error: {ex}", fg="#ff5555")
                except Exception:
                    pass
            self.after(0, _err)

