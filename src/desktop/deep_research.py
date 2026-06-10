import re
import urllib.request
import urllib.parse
import ssl
import threading
import os
import json
import time
from html.parser import HTMLParser

class WebScrapingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.ignore_tags = {"script", "style", "nav", "header", "footer", "form", "head", "noscript", "aside", "iframe"}
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        self.tag_stack.append(tag.lower())

    def handle_endtag(self, tag):
        if self.tag_stack:
            self.tag_stack.pop()

    def handle_data(self, data):
        if any(t in self.ignore_tags for t in self.tag_stack):
            return
        clean_text = data.strip()
        if clean_text:
            self.text_parts.append(clean_text)

    def get_text(self):
        return "\n".join(self.text_parts)


def scrape_url(url, timeout=12):
    # Bypass SSL verification errors
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            html = response.read().decode("utf-8", errors="ignore")
            parser = WebScrapingParser()
            parser.feed(html)
            text = parser.get_text()
            
            # Simple spacing cleanup
            text = re.sub(r'\n+', '\n', text)
            text = re.sub(r' +', ' ', text)
            return text.strip()
    except Exception as e:
        return f"Error al extraer {url}: {e}"


def run_deep_research(pet, topic):
    chat_v = getattr(pet, "_chat_view", None)
    
    def log_system(msg):
        if chat_v:
            pet.after(0, lambda: chat_v.add_system(msg))
        print(f"[Deep Research] {msg}")

    def log_bot(msg):
        if chat_v:
            pet.after(0, lambda: chat_v.add_bot(msg))
        print(f"[Deep Research Bot] {msg}")

    try:
        if hasattr(pet, "_reset_cancel"):
            pet._reset_cancel()  # limpiar cancelación previa al iniciar
        log_system(f"🔍 Iniciando investigación profunda sobre: '{topic}'")

        # Step 1: Formulate 3 initial queries
        log_system("🧠 Formulando 3 consultas de búsqueda iniciales...")
        q_prompt = (
            f"Eres un planificador de investigación profunda. Felipe te ha pedido investigar sobre: '{topic}'.\n"
            f"Formula 3 consultas de búsqueda de internet distintas, específicas e independientes para recopilar información completa sobre este tema.\n"
            f"Responde estrictamente con la lista de 3 consultas, una por línea, sin numeración, viñetas ni comentarios adicionales."
        )
        q_resp = pet.send_quick_message(q_prompt, _skip_skill_action=True)
        queries = [q.strip() for q in q_resp.strip().split("\n") if q.strip()]
        if not queries:
            queries = [topic]
        else:
            queries = queries[:3]
            
        log_system(f"📋 Consultas formuladas:\n" + "\n".join(f"  • {q}" for q in queries))

        visited_urls = set()
        collected_summaries = []
        
        max_iterations = 2
        for iteration in range(1, max_iterations + 1):
            # Botón de pánico (doble ESC): el usuario interrumpió.
            if hasattr(pet, "_is_cancelled") and pet._is_cancelled():
                log_system("⛔ Investigación interrumpida por ti (doble ESC).")
                return
            log_system(f"🚀 [Iteración {iteration}/{max_iterations}] Buscando y analizando información...")

            new_results = []
            for query in queries:
                log_system(f"🔍 Buscando: '{query}'")
                try:
                    items = pet._search_files_online(query, max_results=4)
                except Exception as e:
                    log_system(f"⚠️ Error buscando '{query}': {e}")
                    items = []
                
                # Fetch content of best links (limit to 2 per query)
                links_to_fetch = []
                for item in items:
                    url = item.get("url")
                    if url and url not in visited_urls and "duckduckgo.com" not in url:
                        links_to_fetch.append(url)
                        visited_urls.add(url)
                        if len(links_to_fetch) >= 2:
                            break
                            
                for url in links_to_fetch:
                    log_system(f"📄 Extrayendo contenido de: {url}")
                    text = scrape_url(url)
                    truncated_text = text[:6000] # Safeguard context window
                    new_results.append({
                        "url": url,
                        "content": truncated_text
                    })
                    
            if not new_results:
                log_system("⚠️ No se pudo extraer información nueva de los enlaces encontrados.")
                
            # Compile context
            for res in new_results:
                collected_summaries.append(f"FUENTE: {res['url']}\nCONTENIDO:\n{res['content']}\n---\n")
                
            context_str = "\n".join(collected_summaries)
            
            # Step 4: Evaluate progress
            log_system("🤔 Evaluando información recopilada...")
            
            eval_prompt = (
                f"Has realizado una investigación profunda sobre el tema: '{topic}'.\n"
                f"Aquí está el contenido recolectado de varias páginas web (Iteración {iteration}):\n\n"
                f"{context_str[:25000]}\n\n"
                f"INSTRUCCIONES:\n"
                f"1. Evalúa si necesitas profundizar en aspectos específicos adicionales (en cuyo caso responde con la palabra 'SEGUIR' seguida de 2 nuevas consultas de búsqueda específicas en líneas separadas) o si ya tienes suficiente información para redactar el reporte definitivo (en cuyo caso responde con la palabra 'LISTO' seguida del reporte final detallado y estructurado en Markdown).\n"
                f"2. Si es la iteración número {max_iterations}, debes responder obligatoriamente con 'LISTO' y el reporte final.\n"
                f"3. Tu respuesta debe comenzar estrictamente con 'SEGUIR' o 'LISTO'."
            )
            
            eval_resp = pet.send_quick_message(eval_prompt, _skip_skill_action=True)
            
            if eval_resp.strip().startswith("SEGUIR") and iteration < max_iterations:
                lines = eval_resp.strip().split("\n")[1:]
                queries = [line.strip() for line in lines if line.strip()][:2]
                if not queries:
                    break
                log_system(f"🔄 La IA decidió profundizar con nuevas consultas:\n" + "\n".join(f"  • {q}" for q in queries))
            else:
                report = eval_resp.strip()
                if report.startswith("LISTO"):
                    report = report[5:].strip()
                elif report.startswith("SEGUIR"):
                    report = report[6:].strip()
                
                log_system("✍️ Generando reporte final estructurado...")
                
                # Create filename based on topic
                sanitized_topic = re.sub(r'[^a-zA-Z0-9_\-]', '_', topic)
                filename = f"investigacion_{sanitized_topic}_{int(time.time())}.md"
                
                doc_dir = r"c:\Users\Felipe\Documents\Claudy_v4-main\documentos"
                if not os.path.exists(doc_dir):
                    os.makedirs(doc_dir, exist_ok=True)
                
                report_path = os.path.join(doc_dir, filename)
                
                final_content = (
                    f"# Reporte de Investigación Profunda: {topic}\n\n"
                    f"**Fecha:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"**Fuentes analizadas:**\n"
                )
                for url in visited_urls:
                    final_content += f"- [{url}]({url})\n"
                final_content += f"\n---\n\n{report}"
                
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(final_content)
                
                log_system(f"💾 Reporte guardado en: {report_path}")

                # Persistir los hechos en la memoria de largo plazo (web_facts),
                # para que Claudy recuerde lo investigado en futuras conversaciones
                # sin depender de la ventana deslizante del chat.
                try:
                    if hasattr(pet, "_save_web_fact"):
                        pet._save_web_fact(topic, report, list(visited_urls)[:6])
                        log_system("🧠 Hechos clave guardados en la memoria de largo plazo.")
                except Exception as e:
                    log_system(f"⚠️ No se pudieron guardar los hechos en memoria: {e}")
                
                # Open in Canvas safely from UI thread
                log_system("🎨 Abriendo el reporte en el panel de Canvas/Artifacts...")
                pet.after(0, lambda: pet.open_canvas_in_ui(report_path, final_content))
                
                log_bot(
                    f"### 🔬 Investigación Finalizada sobre: *{topic}*\n\n"
                    f"He recopilado información de {len(visited_urls)} fuentes web y he generado un reporte estructurado.\n\n"
                    f"📂 **Archivo guardado:** `{report_path}`\n\n"
                    f"🎨 He abierto el panel **Canvas** a tu derecha para que puedas leer y editar el reporte cómodamente."
                )
                break
                
    except Exception as e:
        log_system(f"❌ Error en bucle de investigación profunda: {e}")


def handle_research_prompt(pet, prompt):
    lower = prompt.lower().strip()
    
    m_research = re.match(r"^(?:/research\s+|/investigar\s+|investiga\s+profundamente\s+sobre\s+|investigacion\s+profunda\s+sobre\s+)(.+)$", lower)
    
    if m_research or lower == "/research" or lower == "/investigar":
        topic = m_research.group(1).strip() if m_research else ""
        if not topic:
            return True, "Uso: `/research <tema>` o `/investigar <tema>` para iniciar un bucle de investigación profunda en segundo plano."
            
        t = threading.Thread(target=run_deep_research, args=(pet, topic), daemon=True)
        t.start()
        
        return True, f"🚀 He iniciado un agente de investigación profunda en segundo plano para estudiar **\"{topic}\"**.\nTe notificaré por el chat a medida que avance y abriré el reporte resultante en el Canvas."

    return False, ""
