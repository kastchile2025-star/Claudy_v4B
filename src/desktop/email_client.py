import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import re
import os

class EmailClient:
    def __init__(self, config):
        self.config = config or {}
        self.imap_host = self.config.get("imap_host", "imap.gmail.com")
        self.imap_port = int(self.config.get("imap_port", 993))
        self.imap_user = self.config.get("imap_user", "")
        self.imap_pass = self.config.get("imap_pass", "")
        
        self.smtp_host = self.config.get("smtp_host", "smtp.gmail.com")
        self.smtp_port = int(self.config.get("smtp_port", 465))
        self.smtp_user = self.config.get("smtp_user", "")
        self.smtp_pass = self.config.get("smtp_pass", "")
        self.mail_from = self.config.get("from", self.imap_user)

    def is_configured(self):
        return bool(self.imap_user and self.imap_pass)

    def _decode_mime_words(self, s):
        if not s:
            return ""
        parts = []
        try:
            for word, encoding in decode_header(s):
                if isinstance(word, bytes):
                    parts.append(word.decode(encoding or "utf-8", errors="replace"))
                else:
                    parts.append(str(word))
            return "".join(parts)
        except Exception:
            return str(s)

    def _extract_body(self, msg):
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                        break
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
            except Exception:
                pass
        return body.strip()

    def list_unread(self, limit=3):
        if not self.is_configured():
            raise ValueError("Credenciales de correo no configuradas.")
            
        emails = []
        try:
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.imap_user, self.imap_pass)
            mail.select("inbox")
            
            status, response = mail.search(None, "UNSEEN")
            if status != "OK":
                return []
                
            mail_ids = response[0].split()
            mail_ids = mail_ids[::-1][:limit]
            
            for m_id in mail_ids:
                status, data = mail.fetch(m_id, "(RFC822)")
                if status != "OK":
                    continue
                
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                uid = m_id.decode("utf-8", errors="ignore")
                subject = self._decode_mime_words(msg.get("Subject"))
                sender = self._decode_mime_words(msg.get("From"))
                date_str = msg.get("Date")
                body = self._extract_body(msg)
                
                body_truncated = body[:1500] + ("..." if len(body) > 1500 else "")
                
                emails.append({
                    "uid": uid,
                    "subject": subject,
                    "sender": sender,
                    "date": date_str,
                    "body": body_truncated
                })
                
            mail.close()
            mail.logout()
        except Exception as e:
            print(f"[EmailClient] Error listing unread: {e}")
            raise e
            
        return emails

    def triage_email_with_ai(self, email_data, pet_instance):
        prompt = f"""Analiza el siguiente correo electrónico y clasifícalo para el triage de la bandeja de entrada de Felipe.

REMITENTE: {email_data['sender']}
ASUNTO: {email_data['subject']}
FECHA: {email_data['date']}
CUERPO:
{email_data['body']}

Responde estrictamente en formato JSON válido sin bloques markdown adicionales, con los siguientes campos:
{{
  "urgency": "Alta" | "Media" | "Baja",
  "summary": "Resumen muy breve de una sola frase en español",
  "is_spam": true | false,
  "suggested_reply": "Un borrador de respuesta sugerido y formal de parte de Felipe en español chileno natural si corresponde, o una cadena vacía si no requiere respuesta."
}}"""
        try:
            raw_response = pet_instance.send_quick_message(prompt, _skip_skill_action=True, timeout=30)
            clean_resp = raw_response.strip()
            if clean_resp.startswith("```"):
                lines = clean_resp.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_resp = "\n".join(lines).strip()
                
            parsed = json.loads(clean_resp)
            return {
                "urgency": parsed.get("urgency", "Media"),
                "summary": parsed.get("summary", "Sin resumen."),
                "is_spam": bool(parsed.get("is_spam", False)),
                "suggested_reply": parsed.get("suggested_reply", "")
            }
        except Exception as e:
            print(f"[EmailClient] Error: {e}")
            return {
                "urgency": "Media",
                "summary": "No se pudo clasificar por error de red.",
                "is_spam": False,
                "suggested_reply": ""
            }

    def send_email(self, to, subject, body):
        if not self.smtp_host or not self.smtp_user or not self.smtp_pass:
            raise ValueError("Credenciales SMTP no configuradas.")
            
        try:
            msg = MIMEMultipart()
            msg["From"] = self.mail_from
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))
            
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.mail_from, [to], msg.as_string())
            server.quit()
            return f"Correo enviado correctamente a {to}"
        except Exception as e:
            print(f"[EmailClient] Error: {e}")
            raise e


def handle_email_prompt(pet, prompt):
    """
    Routs email-related prompt.
    Returns (handled: bool, result: str)
    """
    lower = prompt.lower().strip()
    config = pet.load_claudy_config().get("email", {})
    
    # 1. LIST EMAILS / TRIAGE
    if any(k in lower for k in ("lista mis correos", "tengo correos nuevos", "triage de correos", "inbox", "correos sin leer")):
        client = EmailClient(config)
        if not client.is_configured():
            return True, "Credenciales de correo no configuradas. Por favor agrega la sección 'email' en ~/.claudy/config.json."
            
        try:
            # Show status on Tk if active
            pet.after(0, lambda: pet._set_state_briefly("thinking", 2000))
            emails = client.list_unread(limit=3)
            
            if not emails:
                return True, "No tienes correos nuevos sin leer en tu bandeja de entrada."
                
            markdown_parts = ["### 📬 Bandeja de Entrada (Triage de IA)\n"]
            for idx, e in enumerate(emails, 1):
                triage = client.triage_email_with_ai(e, pet)
                urgency_color = "🔴" if triage["urgency"] == "Alta" else ("🟡" if triage["urgency"] == "Media" else "🟢")
                
                markdown_parts.append(
                    f"{idx}. **[{triage['urgency']} {urgency_color}] De:** {e['sender']}\n"
                    f"   **Asunto:** {e['subject']}\n"
                    f"   **Resumen:** {triage['summary']}\n"
                )
                if triage["suggested_reply"]:
                    markdown_parts.append(
                        f"   *Borrador de respuesta sugerido:*\n"
                        f"   > \"{triage['suggested_reply']}\"\n"
                    )
                markdown_parts.append(f"   *[Usa `/correo leer {e['uid']}` para ver el cuerpo completo]*\n")
            return True, "\n".join(markdown_parts)
            
        except Exception as e:
            return True, f"Error al acceder a tu bandeja de correo: {e}"

    # 2. READ SPECIFIC EMAIL
    m_read = re.match(r"^(?:/correo\s+leer\s+|lee\s+el\s+correo\s+|ver\s+el\s+correo\s+|mostrar\s+el\s+correo\s+|leer\s+correo\s+)(\d+)\s*$", lower)
    if m_read:
        uid = m_read.group(1)
        client = EmailClient(config)
        if not client.is_configured():
            return True, "Credenciales de correo no configuradas."
        try:
            mail = imaplib.IMAP4_SSL(client.imap_host, client.imap_port)
            mail.login(client.imap_user, client.imap_pass)
            mail.select("inbox")
            
            status, data = mail.fetch(uid, "(RFC822)")
            if status != "OK":
                mail.close()
                mail.logout()
                return True, f"No se pudo leer el correo con UID {uid}."
                
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            subject = client._decode_mime_words(msg.get("Subject"))
            sender = client._decode_mime_words(msg.get("From"))
            date_str = msg.get("Date")
            body = client._extract_body(msg)
            
            mail.close()
            mail.logout()
            
            return True, (
                f"### 📧 Detalle del Correo (UID: {uid})\n\n"
                f"**De:** {sender}\n"
                f"**Asunto:** {subject}\n"
                f"**Fecha:** {date_str}\n\n"
                f"---\n\n"
                f"{body}"
            )
        except Exception as e:
            return True, f"Error leyendo correo: {e}"

    # 3. SEND EMAIL
    m_send = re.match(r"^(?:/correo\s+enviar\s+|envia\s+un\s+correo\s+a\s+|enviar\s+correo\s+a\s+)(\S+)\s+(?:con\s+asunto\s+)(.+?)\s+(?:y\s+cuerpo\s+)(.+)$", lower)
    if m_send:
        to = m_send.group(1).strip()
        subject = m_send.group(2).strip()
        body = m_send.group(3).strip()
        
        client = EmailClient(config)
        if not client.is_configured():
            return True, "Credenciales SMTP no configuradas."
        try:
            res = client.send_email(to, subject, body)
            return True, res
        except Exception as e:
            return True, f"Error al enviar correo: {e}"
            
    return False, ""
