"""
QCORE Product Context — Rich context data for each QCORE product.
When user clicks a product in sidebar, this context is injected into
Claudy's system prompt so it can assist with full knowledge.
"""

# Contexto corporativo global de QCORE SPA (siempre presente en el system prompt).
# Fuente: QCORE-ECOSYSTEM (.github/qcore-master.instructions.md, README, 05-DOCS).
# NOTA: nunca incluir aquí secretos (tokens, claves).
QCORE_SPA_CONTEXT = """═══ QCORE SPA — CONTEXTO CORPORATIVO ═══
Razón social: QCORE GROUP TECHNOLOGIES SpA (Chile). Marca: QCORE SPA.

DATOS LEGALES OFICIALES (verificados en estatuto/SII; NO inventar — si no estás seguro, dilo):
- Razón social: QCORE GROUP TECHNOLOGIES SpA. Tipo: SpA de accionista único.
- RUT empresa: 78.354.502-0  (EXACTO — nunca uses otro número).
- Constituida: 10 de febrero de 2026 (Registro de Empresas y Sociedades).
- Domicilio social ACTUAL: comuna de Providencia, Región Metropolitana — dirección: Antonio Bellet 193,
  Oficina 1210, Providencia (dirección virtual/tributaria arrendada a DIVIR SPA).
  El cambio a Providencia es OFICIAL: Acuerdo de Accionista Único del 16-abr-2026 (modificó el art. 2 del estatuto).
  Dirección ANTERIOR (ya NO vigente como fiscal): Pasaje El Alfalfal #1578, Padre Hurtado.
- Accionista único / representante legal / administrador: Jorge Felipe Guillermo Arturo Castro Segura
  (C.I. 17.023.135-K), correo jorge.castro@qcorespa.com. (Es la misma persona que "Felipe", el dueño/CTO.)
- Para datos legales siempre verificar en G:\\Mi unidad\\QCORE-ECOSYSTEM\\01-CORPORATE (estatutos, facturas, contratos).

DATOS DE TRANSFERENCIA BANCARIA OFICIALES (usar EXACTOS en correos de cobro/facturación; NUNCA inventar ni usar placeholders como '123456789' o 'Banco Estado'):
- Nombre / Titular: QCORE GROUP TECHNOLOGIES SPA
- RUT: 78.354.502-0
- Banco: BCI
- Tipo de cuenta: Cuenta Corriente
- N° de cuenta: 77176032
- Correo: jorge.castro@qcorespa.com

Qué es: empresa de software que construye, opera y escala un portafolio de SaaS verticales
para rubros con baja digitalización en Chile y Latinoamérica. No es solo dev: es un ecosistema
con productos verticales, agentes con jerarquía, gobernanza y contexto acumulado.
Dueño / CTO: Felipe Castro (jorge.castro@qcorespa.com).
Sitio corporativo: QCORE Corp (repo QCORESPAWEB_v3, deploy Vercel).

Modelo de negocio: MRR por suscripción B2B (planes Free/Starter/Pro/Enterprise), pagos vía
Flow Chile (CLP), cobertura inicial Chile → expansión LatAm.

Stack unificado: Backend NestJS + TypeScript + PostgreSQL; Front React (Vite) o Next.js + Tailwind;
Mobile Expo + React Native; Deploy Vercel (front) + Render (back); AI Google Gemini vía Firebase
Genkit; Pagos Flow Chile.

Principios: 1) Vertical-first (cada producto resuelve un problema con profundidad);
2) Stack unificado; 3) Chile-first (CLP, RUT, SII, español); 4) Deploy simple (1 repo → Vercel+Render);
5) Cero vendor lock-in; 6) AI nativa (no add-on).

Portafolio de productos:
- SmartStudent — gestión académica escolar (Next.js+Firebase+Gemini). Cliente: COMBAS. smartstudent.cl.
- Roadix — SaaS talleres automotrices (React+NestJS+PostgreSQL). En producción. roadix.cl.
- Point — POS + inventario con vencimiento FEFO para comercios (Python/Flask). Cliente: Tentación a Granel.
- UnitCore — BI clínico / datos SAP (dashboard oncológico). En desarrollo.
- Luxium — belleza y barbería on-demand (monorepo NestJS + Expo). Base técnica.
- Campaign Studio — gestión de Reels/Carruseles para Meta (React + Remotion). Marketing.
- Mission Control — hub operativo central del ecosistema (React+Vite+NestJS). Coordina ventas, demos, legal, reporting.
- Claudy — asistente IA personal de escritorio (Python + tkinter/pywebview). Este asistente.
- Mi Portafolio — web personal/CV de Jorge Castro Segura (jorgecastros.xyz). Proyecto personal.
- QCORE Corp — sitio corporativo de la empresa.

Ecosistema en disco: G:\\Mi unidad\\QCORE-ECOSYSTEM (00-GROUP, 01-CORPORATE, 02-PRODUCTS,
03-SHARED, 04-OPERATIONS, 05-DOCS, 90-ARCHIVE, 99-SANDBOX, MEMORIAS, CLIENTES).
═══ FIN QCORE SPA ═══"""


def build_company_context() -> str:
    """Contexto corporativo de QCORE SPA para el system prompt."""
    return QCORE_SPA_CONTEXT


PRODUCT_CONTEXTS = {
    "SmartStudent": {
        "tag": "EDU",
        "color": "#6c5ce7",
        "description": "Plataforma educativa SaaS para instituciones (Next.js + Firebase + Gemini AI)",
        "port": 9002,
        "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\SMARTSTUDENT\APP",
        "stack": "Next.js 14 (Turbopack), Firebase Auth/Firestore, Gemini AI, Tailwind CSS",
        "modules": [
            "Dashboard principal con KPIs educativos",
            "Gestión de usuarios (Admin, Profesor, Estudiante, Apoderado)",
            "Asistencia — control y reportes de asistencia escolar",
            "Calificaciones — ingreso, cálculo y reportes de notas",
            "Calendario — eventos académicos y programación",
            "Cuestionarios — generación y gestión de evaluaciones",
            "Evaluaciones — evaluaciones con IA (generate-evaluation, generate-dynamic-evaluation)",
            "Estadísticas — analytics educativos y rendimiento",
            "Resumen IA — generación automática de resúmenes con Gemini",
            "Mapa Mental — creación de mapas mentales con IA (create-mindmap, mind-map)",
            "Slides IA — generación de presentaciones automáticas (generate-slides)",
            "Libros — biblioteca digital y material de estudio",
            "Comunicaciones — mensajería interna entre roles",
            "Tareas — asignación y seguimiento de tareas",
            "Solicitudes — gestión de peticiones administrativas",
            "Gestión financiera — módulo de finanzas institucional",
            "Perfil de usuario — configuración personal",
            "OCR Vision — análisis de imágenes y documentos con IA",
            "Quiz IA — generación automática de preguntas (generate-quiz, generate-questions)",
            "Búsqueda de imágenes — proxy de imágenes educativas",
            "Notificaciones — sistema de alertas push",
        ],
        "apis": [
            "/api/auth — autenticación Firebase",
            "/api/admin — panel administrativo",
            "/api/attendance — asistencia",
            "/api/firebase — operaciones Firestore",
            "/api/gemini — integración Gemini AI",
            "/api/generate-evaluation — evaluaciones con IA",
            "/api/generate-quiz — quizzes automáticos",
            "/api/generate-slides — presentaciones IA",
            "/api/generate-summary — resúmenes IA",
            "/api/create-mindmap — mapas mentales IA",
            "/api/analyze-ocr-vision — OCR + Vision AI",
            "/api/extract-pdf-content — extracción de PDFs",
            "/api/stats — estadísticas",
            "/api/notifications — notificaciones",
            "/api/users — gestión de usuarios",
        ],
        "client": "COMBAS (cliente activo)",
        "security": "CSP headers, HSTS, 32 API routes protegidas, CSRF middleware",
    },

    "Roadix": {
        "tag": "AUTO",
        "color": "#00b894",
        "description": "SaaS de gestión integral para talleres automotrices en Chile",
        "port": 5173,
        "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\ROADIX",
        "stack": "Frontend: React + Vite + TypeScript | Backend: Node.js + Express + Supabase (PostgreSQL)",
        "modules": [
            "Dashboard — KPIs del taller (ingresos, órdenes, clientes)",
            "Órdenes de Trabajo — crear, editar, seguimiento de OT con estados",
            "Kanban — vista tablero de órdenes de trabajo",
            "Clientes — CRM de clientes del taller",
            "Vehículos — registro y historial de vehículos",
            "Mecánicos — gestión de personal técnico",
            "Inventario — control de stock de repuestos y materiales",
            "Repuestos — catálogo y gestión de repuestos",
            "Proveedores — gestión de proveedores de insumos",
            "Facturación — emisión de facturas y boletas",
            "Caja — control de caja diaria, ingresos/egresos",
            "Billing/Suscripciones — planes y pagos del SaaS",
            "Presupuestos — cotizaciones para clientes",
            "Reportes — reportes financieros y operacionales",
            "Portal Cliente — acceso externo para clientes del taller",
            "Notificaciones — alertas y recordatorios",
            "Gestión de Usuarios — roles y permisos",
            "Recordatorios — mantenciones programadas",
            "Configuración — ajustes del taller",
            "Email — notificaciones por correo",
            "PDF — generación de documentos (OT, facturas, presupuestos)",
        ],
        "backend_modules": [
            "auth", "clientes", "vehiculos", "ordenes-trabajo", "mecanicos",
            "inventario", "repuestos", "proveedores", "facturacion", "caja",
            "presupuestos", "reportes", "portal-cliente", "recordatorios",
            "suscripciones", "planes", "usuarios", "email", "pdf", "archivos", "talleres",
        ],
        "db": "Supabase (PostgreSQL) — migrado desde Render",
        "web": "https://www.roadix.cl",
        "status": "Producción — base comercial madura, 267 contactos",
    },

    "Mission Control": {
        "tag": "OPS",
        "color": "#a29bfe",
        "description": "Hub operativo central del ecosistema QCORE — coordina ventas, demos, legal y reporting",
        "port": 5200,
        "backend_port": 3100,
        "path": r"C:\Users\Felipe\Documents\QCORE-LOCAL\MISSION-CONTROL",
        "stack": "Frontend: React + Vite + TypeScript + Tailwind CSS (Port 5200) | Backend: NestJS 11 + Prisma 7 + SQLite (Port 3100)",
        "modules": [
            "Dashboard — vista ejecutiva multi-producto",
            "Products — gestión del catálogo de productos QCORE",
            "Demo Pipeline — leads desde contacto → demo → conversión → onboarding",
            "Campaigns — campañas de email masivas con SendGrid y templates multi-idioma",
            "Inbox — borradores automatizados con inferencia de nombre del lead y detección automática de idioma (ES/EN)",
            "Inbox Actions — exportador de borradores HTML renderizables al portapapeles (MIME text/html)",
            "Auth Module — login, registro y perfil de usuario protegidos con JWT y encriptación bcrypt",
            "Agents CRUD — gestión operativa de 8 agentes y sus respectivos estados y perfiles",
            "Missions System — control de tareas y objetivos con filtros por estado, producto y agente asignado",
            "Activity Feed — log histórico persistido con 12 tipos de actividades en tiempo real",
            "Metrics & Analytics — endpoints NestJS y vistas para missions-by-product, workload, timeline y dashboard unificado",
            "Coach Comercial — IA de negociación con OpenRouter, memoria por cliente",
            "Clients & Contacts — base de datos comercial e historial por producto",
            "Onboarding — flujo de incorporación con panel handoff LUNA",
            "Legal (THEMIS) — contratos SaaS, DPA, compliance por producto y pre-requisitos de facturación",
            "Billing — facturación y control financiero",
            "Reports — reportes semanales y diarios consolidados",
        ],
        "sender": "jorge.castro@qcorespa.com (SendGrid Domain ID 30446608 - CNAMEs validados en Namecheap)",
        "smtp": "Gmail SMTP (borradores inbox) + SendGrid API (autorespuesta web)",
        "status": "Producción — Backend NestJS y Base comercial operativas en Drive.",
        "notes": [
            "Para crear o sembrar borradores offline (drafts) en el Inbox de Mission Control, debes agregar/escribir un objeto JSON en el archivo: C:\\Users\\Felipe\\Documents\\QCORE-LOCAL\\MISSION-CONTROL\\logs\\seeded-drafts.json",
            "El formato del objeto JSON a agregar es: { id: 'seed-[único]', kind: 'general-reply' | 'implementation-follow-up' | 'meeting-reply' | 'receipt-confirmation' | 'website-reply', relatedMessageId: 'seed-[único]-msg', createdAt: '[ISO_string]', status: 'pending-approval', origin: 'direct-email' | 'campaign-reply' | 'website-lead', reason: '[motivo del borrador]', from: 'SmartStudent <jorge.castro@qcorespa.com>', to: ['[destinatario]'], cc: ['[copia]'], replyTo: 'jorge.castro@qcorespa.com', subject: '[Asunto]', html: '[Cuerpo en HTML]', leadId: '[opcional]', productId: 'smartstudent' | 'roadix' | 'unitcore' }",
        ],
    },

    "Luxium": {
        "tag": "CORE",
        "color": "#e17055",
        "description": "Monorepo/engine base compartido entre productos del ecosistema QCORE",
        "port": 5176,
        "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\LUXIUM\MONOREPO",
        "stack": "Monorepo TypeScript",
        "modules": [
            "Componentes compartidos entre SmartStudent, Roadix, Mission Control",
            "Design system y utilidades comunes",
            "Servicios base reutilizables",
        ],
    },

    "UnitCore": {
        "tag": "CLIN",
        "color": "#0984e3",
        "description": "Clinical Research Management — dashboard de prestaciones por estudio clínico",
        "port": 5175,
        "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\UNITCORE",
        "stack": "HTML Dashboard (single page)",
        "modules": [
            "Dashboard de estudios clínicos",
            "Visualización de prestaciones (Cobrado / Pendiente / X Castigar)",
            "Importación manual desde Excel (costos SAP + SICI + Pacientes)",
            "Narrativa comercial y branding listos",
            "Base oncológica: 195 contactos accionables, 9 centros oncológicos",
            "Legal: contratos y DPA preparados",
            "Delimitado como inteligencia operativa (NO dispositivo médico)",
        ],
        "status": "Listo para activación gradual. Campaña pausada en test-only.",
    },

    "Campaign Studio": {
        "tag": "MKT",
        "color": "#fdcb6e",
        "description": "UI web para gestionar y publicar Reels + Carruseles en Facebook e Instagram",
        "port": 5174,
        "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\CAMPAIGN-STUDIO",
        "stack": "React + Remotion (video rendering)",
        "modules": [
            "Gestión de Reels para redes sociales",
            "Gestión de Carruseles para Instagram/Facebook",
            "Publicación directa a Meta (Facebook + Instagram)",
            "Renderizado de video con Remotion",
            "Orientado a marketing de SmartStudent",
        ],
    },

    "Point": {
        "tag": "POS",
        "color": "#D81B60",
        "description": "Sistema POS con control de inventario por lotes y vencimiento (FEFO) para comercios",
        "port": 5000,
        "path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\POINT",
        "stack": "Python + Flask + SQLite + Vercel + Chart.js",
        "installer_path": r"G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\POINT\POINT_v3\tentacion_a_granel_web\installer",
        "modules": [
            "Punto de venta (POS): ventas, múltiples formas de pago, cierre de caja",
            "Inventario con control de lotes y vencimiento (FEFO)",
            "Alertas de stock y vencimiento",
            "Dashboard de ventas y exportación a Excel",
            "Multi-sucursal y branding personalizable por cliente",
            "Versión local (instalador de escritorio) y versión web",
        ],
        "notes": [
            r"RUTA CANÓNICA DE INSTALADORES (Felipe, 14-jun-2026): G:\Mi unidad\QCORE-ECOSYSTEM\02-PRODUCTS\POINT\POINT_v3\tentacion_a_granel_web\installer — ahí se alojan las últimas versiones (instaladores .exe). La carpeta de proyecto es POINT_v3; en el futuro será POINT_v4 y la ruta cambiará el tramo POINT_vN.",
            "Distinguir DOS niveles de versión: (1) carpeta de proyecto = POINT_v3; (2) instalador entregable del cliente = TentacionAGranel_Instalador_vX.Y.Z.exe. El instalador más reciente manda como 'última versión' del cliente.",
            "Hay también un instalador de servidor: TentacionAGranel_Servidor_Instalador_vX.Y.Z.exe en la misma carpeta.",
        ],
        "status": "En desarrollo / producción. Primera implementación: Tentación a Granel (Puerto Montt).",
    },

    "Mi Portafolio": {
        "tag": "WEB",
        "color": "#00cec9",
        "description": "Web personal / portafolio profesional de Jorge Castro Segura — Senior Financial Analyst & Data Analyst (Santiago, Chile, 12+ años)",
        "web": "https://www.jorgecastros.xyz",
        "path": r"C:\Users\Felipe\Documents\CV_JorgeCastro_v3.5",
        "stack": "HTML5 + CSS3 + Vanilla JS (sin build/deps) · fuentes Inter + JetBrains Mono · i18n EN/ES (data-i18n + localStorage) · tema claro/oscuro · scroll-reveal (IntersectionObserver) · responsive",
        "modules": [
            "Home (index.html) — hero, perfil, capacidades, stack y showcase de proyectos",
            "Experience — timeline de 5 cargos (FALP, LATAM Airlines, Samsung, Sigdo Koopers)",
            "Education — Ingeniero Comercial / Adm. de Empresas, UTEM (2007–2012)",
            "Certifications — 6 credenciales (Google, Microsoft, IBM ×2, LinkedIn, Anthropic)",
            "Portfolio — proyectos Python de datos/automatización (Oncology Dashboard, DataSync, SmartInvest, SAPExtractor, AutoBackup, WorkFinder, BotSlack, Adherencia)",
            "About — bio, contacto y formulario",
        ],
        "notes": [
            "FUENTE CANÓNICA (desde 2026-05-28): C:\\Users\\Felipe\\Documents\\CV_JorgeCastro_v3.5 — ahí vive la última versión del portafolio para Claudy. Backup en G:\\Mi unidad\\PERSONAL\\CV_JorgeCastro_v3.5.",
            "Persona: Jorge Castro Segura. Contacto: +56 9 4888 9506 · jorgefcs.1988@gmail.com · LinkedIn jorge-castro-segura · jorgecastros.xyz.",
            "Experiencia: Senior Financial Analyst en FALP (oncología, dic 2024–presente, KPIs+SQL+IA); Senior Analyst en LATAM Airlines (2015–2024, 9 años, SAP MM/FI, lideró 5 analistas, auditorías EY/Deloitte/PwC); Financial Manager Samsung/Alvarez y Vergara (2012–2014); también Sigdo Koopers.",
            "Educación: Ingeniero Comercial — UTEM (2007–2012). Áreas: finanzas corporativas, data analytics, ERP (SAP FI/MM), liderazgo.",
            "Certificaciones: Google Data Analytics (NEW May 2026), Microsoft Power BI (2024), IBM Data Analyst (2024), IBM Data Science (2023), LinkedIn Python & R Data Scientist (2023), Anthropic AI Fluency (2025).",
            "Herramientas clave: Power BI, SQL, Python, Tableau, Looker Studio, DAX, SAP FI/MM, Excel/VBA/Power Query.",
            "También tiene el CV en PDF (varias versiones ES/EN, incl. RoyalBlue Google Analytics 2026) dentro de la misma carpeta v3.5.",
        ],
        "status": "En línea — https://www.jorgecastros.xyz · fuente local C:\\Users\\Felipe\\Documents\\CV_JorgeCastro_v3.5",
    },
}


def scan_product_versions(path: str, max_items: int = 12):
    """Escanea la carpeta de un producto y devuelve sus versiones/subcarpetas.

    Para que Claudy responda "¿cuál es la última versión?" con el dato REAL del
    disco (POINT_v3 vive en G:\\...\\02-PRODUCTS\\POINT) en vez de irse a
    internet. Devuelve (lista_ordenada, ultima) donde cada item es
    (nombre, mtime, version_num|None). 'ultima' prioriza el mayor número de
    versión; si no hay números, la subcarpeta más reciente por mtime.
    """
    import os
    import re
    if not path or not os.path.isdir(path):
        return [], None
    ver_rx = re.compile(r"(?:^|[_\- ])v(?:er(?:sion)?)?[_\- ]?(\d+)", re.IGNORECASE)
    items = []
    try:
        for name in os.listdir(path):
            full = os.path.join(path, name)
            if not os.path.isdir(full):
                continue
            if name.startswith((".", "$", "__")):
                continue
            try:
                mtime = os.path.getmtime(full)
            except Exception:
                mtime = 0
            m = ver_rx.search(name)
            vnum = int(m.group(1)) if m else None
            items.append((name, mtime, vnum))
    except Exception:
        return [], None
    if not items:
        return [], None
    # Última: por número de versión si hay; si no, por fecha de modificación.
    versioned = [it for it in items if it[2] is not None]
    if versioned:
        ultima = max(versioned, key=lambda it: (it[2], it[1]))
    else:
        ultima = max(items, key=lambda it: it[1])
    # Orden de presentación: versionadas por num desc, luego el resto por mtime desc.
    items.sort(key=lambda it: (it[2] if it[2] is not None else -1, it[1]), reverse=True)
    return items[:max_items], ultima


def scan_installers(path: str, max_items: int = 10):
    """Escanea instaladores .exe en una carpeta y devuelve (lista, ultimo).

    Ordena por versión semántica vX.Y.Z embebida en el nombre (cae a mtime si no
    hay). Responde "¿cuál es el último instalador entregable?" — el que recibe el
    cliente, distinto de la carpeta de proyecto (POINT_v3)."""
    import os
    import re
    if not path or not os.path.isdir(path):
        return [], None
    semver_rx = re.compile(r"v(\d+)\.(\d+)\.(\d+)", re.IGNORECASE)
    items = []
    try:
        for name in os.listdir(path):
            full = os.path.join(path, name)
            if not os.path.isfile(full) or not name.lower().endswith(".exe"):
                continue
            try:
                mtime = os.path.getmtime(full)
            except Exception:
                mtime = 0
            m = semver_rx.search(name)
            sem = tuple(int(x) for x in m.groups()) if m else None
            items.append((name, mtime, sem))
    except Exception:
        return [], None
    if not items:
        return [], None
    semmed = [it for it in items if it[2] is not None]
    if semmed:
        ultimo = max(semmed, key=lambda it: (it[2], it[1]))
    else:
        ultimo = max(items, key=lambda it: it[1])
    items.sort(key=lambda it: (it[2] or (-1,), it[1]), reverse=True)
    return items[:max_items], ultimo


def _product_versions_block(product_name: str, path: str, installer_path: str = "") -> str:
    """Bloque de texto con las versiones reales en disco, para el system prompt."""
    import datetime
    items, ultima = scan_product_versions(path)
    if not items and not installer_path:
        return ""
    def _fecha(mtime):
        try:
            return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        except Exception:
            return "?"

    lines = [f"\n[VERSIONES REALES EN DISCO de {product_name} — fuente: {path}]"]
    if ultima:
        lines.append(f"⭐ ÚLTIMA CARPETA DE PROYECTO: {ultima[0]}")
    if items:
        lines.append("Carpetas/versiones encontradas (más reciente primero):")
        for name, mtime, vnum in items:
            marca = "  ← última" if ultima and name == ultima[0] else ""
            lines.append(f"  • {name}  (modificada {_fecha(mtime)}){marca}")

    # Instaladores entregables (.exe) — el último que recibe el cliente.
    if installer_path:
        insts, ultimo = scan_installers(installer_path)
        if insts:
            lines.append(f"\nInstaladores en: {installer_path}")
            if ultimo:
                lines.append(f"⭐ ÚLTIMO INSTALADOR ENTREGABLE: {ultimo[0]}  "
                             f"(modificado {_fecha(ultimo[1])}) — esta es la "
                             f"«última versión» que usa el cliente.")
            lines.append("Instaladores (más reciente primero):")
            for name, mtime, sem in insts:
                marca = "  ← último" if ultimo and name == ultimo[0] else ""
                lines.append(f"  • {name}  (modificado {_fecha(mtime)}){marca}")

    lines.append("Usa ESTOS datos del disco para responder sobre versiones; "
                 "NO busques en internet para esto.")
    return "\n".join(lines)


def build_context_prompt(product_name: str) -> str:
    """Build a rich context string for Claudy's system prompt."""
    info = PRODUCT_CONTEXTS.get(product_name)
    if not info:
        return f"Producto activo: {product_name}"

    lines = [
        f"[CONTEXTO DE PRODUCTO ACTIVO: {product_name}]",
        f"Descripción: {info['description']}",
        f"Stack: {info.get('stack', 'N/A')}",
        f"Puerto: {info.get('port', 'N/A')}",
        f"Ruta: {info.get('path', 'N/A')}",
    ]

    if info.get("web"):
        lines.append(f"Web: {info['web']}")
    if info.get("status"):
        lines.append(f"Estado: {info['status']}")
    if info.get("client"):
        lines.append(f"Cliente activo: {info['client']}")
    if info.get("db"):
        lines.append(f"Base de datos: {info['db']}")
    if info.get("sender"):
        lines.append(f"Sender: {info['sender']}")
    if info.get("security"):
        lines.append(f"Seguridad: {info['security']}")

    if info.get("modules"):
        lines.append(f"\nFuncionalidades ({len(info['modules'])} módulos):")
        for m in info["modules"]:
            lines.append(f"  • {m}")

    if info.get("apis"):
        lines.append(f"\nAPIs ({len(info['apis'])}):")
        for a in info["apis"]:
            lines.append(f"  • {a}")

    if info.get("backend_modules"):
        lines.append(f"\nBackend modules: {', '.join(info['backend_modules'])}")

    if info.get("notes"):
        lines.append(f"\nNotas importantes de desarrollo:")
        for n in info["notes"]:
            lines.append(f"  • {n}")

    # Versiones reales en disco (responde "¿cuál es la última versión?" sin internet).
    vblock = _product_versions_block(product_name, info.get("path", ""),
                                     info.get("installer_path", ""))
    if vblock:
        lines.append(vblock)

    lines.append(f"\n[FIN CONTEXTO {product_name}]")
    return "\n".join(lines)
