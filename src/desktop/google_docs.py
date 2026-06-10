"""
google_docs.py — Integracion de Claudy con Google Docs y Google Sheets.

Disenado para fallar suave: si faltan las librerias de Google o el archivo de
credenciales, las funciones devuelven {"connected": False, "reason": ...} en vez
de romper.

Credenciales (las pone el usuario):
  ~/.claudy/google_client_secret.json   <- cliente OAuth tipo "App de escritorio"
Token (se genera solo tras autorizar):
  ~/.claudy/google_docs_token.json

Scopes: lectura + escritura de Docs, Sheets y Drive.
"""

import os
import json

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CLAUDY_DIR = os.path.join(os.path.expanduser("~"), ".claudy")
CLIENT_SECRET_FILE = os.path.join(CLAUDY_DIR, "google_client_secret.json")
TOKEN_FILE = os.path.join(CLAUDY_DIR, "google_docs_token.json")

PIP_HINT = "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"


def _import_google():
    """Importa las libs de Google de forma perezosa. Devuelve (mods, error)."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        return {
            "Credentials": Credentials,
            "InstalledAppFlow": InstalledAppFlow,
            "Request": Request,
            "build": build,
        }, None
    except Exception:
        return None, f"Faltan librerias de Google. Instala con:\n{PIP_HINT}"


def _load_creds(mods):
    """Carga credenciales validas (refresca si expira). Devuelve (creds, error)."""
    Credentials = mods["Credentials"]
    Request = mods["Request"]
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            creds = None
    if creds and creds.valid:
        return creds, None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds, None
        except Exception as e:
            return None, f"No se pudo refrescar el token: {e}"
    return None, "no-autorizado"


def _save_token(creds):
    os.makedirs(CLAUDY_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def _service(api_name, api_version):
    """Devuelve (service, error). service=None si no se puede conectar."""
    mods, err = _import_google()
    if err:
        return None, err
    if not os.path.exists(CLIENT_SECRET_FILE):
        return None, (
            "Falta el archivo de credenciales. Crea un cliente OAuth 'App de escritorio' "
            "en Google Cloud Console y guardalo como:\n" + CLIENT_SECRET_FILE
        )
    creds, err = _load_creds(mods)
    if err == "no-autorizado":
        return None, "no-autorizado"
    if err:
        return None, err
    try:
        service = mods["build"](api_name, api_version, credentials=creds, cache_discovery=False)
        return service, None
    except Exception as e:
        return None, f"Error creando el servicio de {api_name}: {e}"


def status():
    """Estado de la conexion, sin abrir navegador."""
    mods, err = _import_google()
    if err:
        return {"connected": False, "reason": err, "needs_libs": True}
    if not os.path.exists(CLIENT_SECRET_FILE):
        return {"connected": False, "reason": "falta-credencial", "client_secret_path": CLIENT_SECRET_FILE}
    creds, err = _load_creds(mods)
    if err == "no-autorizado":
        return {"connected": False, "reason": "no-autorizado"}
    if err:
        return {"connected": False, "reason": err}
    return {"connected": True}


def connect():
    """Lanza el flujo OAuth (abre el navegador una vez) y guarda el token.
    Devuelve {"connected": True} o {"connected": False, "reason": ...}."""
    mods, err = _import_google()
    if err:
        return {"connected": False, "reason": err}
    if not os.path.exists(CLIENT_SECRET_FILE):
        return {"connected": False, "reason": "falta-credencial", "client_secret_path": CLIENT_SECRET_FILE}
    st = status()
    if st.get("connected"):
        return st
    try:
        flow = mods["InstalledAppFlow"].from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        _save_token(creds)
        return {"connected": True}
    except Exception as e:
        return {"connected": False, "reason": f"Fallo al autorizar: {e}"}


def search_docs(query, max_results=20, doc_type="all"):
    """Busca documentos en Drive.
    
    Args:
        query: Texto de busqueda
        max_results: Maximo de resultados (default 20)
        doc_type: "document", "spreadsheet", o "all" (default)
    
    Devuelve: {"connected": bool, "items": [...], "reason": ...}
    """
    service, err = _service("drive", "v3")
    if err:
        return {"connected": False, "reason": err, "items": []}
    
    try:
        q = f"name contains '{query}'"
        if doc_type == "document":
            q += " and mimeType='application/vnd.google-apps.document'"
        elif doc_type == "spreadsheet":
            q += " and mimeType='application/vnd.google-apps.spreadsheet'"
        else:
            q += " and (mimeType='application/vnd.google-apps.document' or mimeType='application/vnd.google-apps.spreadsheet')"
        
        results = service.files().list(
            q=q,
            pageSize=max_results,
            fields="files(id, name, mimeType, modifiedTime, webViewLink)",
            orderBy="modifiedTime desc"
        ).execute()
        
        items = []
        for f in results.get("files", []):
            items.append({
                "id": f.get("id"),
                "name": f.get("name"),
                "type": "document" if "document" in f.get("mimeType", "") else "spreadsheet",
                "modifiedTime": f.get("modifiedTime"),
                "link": f.get("webViewLink"),
            })
        
        return {"connected": True, "items": items}
    except Exception as e:
        return {"connected": False, "reason": f"Error buscando: {e}", "items": []}


def read_doc(document_id):
    """Lee el contenido de un Google Doc.
    
    Args:
        document_id: ID del documento (de la URL o de search_docs)
    
    Devuelve: {"connected": bool, "ok": bool, "title": ..., "content": ..., "reason": ...}
    """
    service, err = _service("docs", "v1")
    if err:
        return {"connected": False, "ok": False, "reason": err}
    
    try:
        doc = service.documents().get(documentId=document_id).execute()
        title = doc.get("title", "")
        
        content_parts = []
        body = doc.get("body", {})
        for element in body.get("content", []):
            if "paragraph" in element:
                for elem in element["paragraph"].get("elements", []):
                    if "textRun" in elem:
                        content_parts.append(elem["textRun"].get("content", ""))
        
        content = "".join(content_parts)
        return {"connected": True, "ok": True, "title": title, "content": content}
    except Exception as e:
        return {"connected": False, "ok": False, "reason": f"Error leyendo documento: {e}"}


def create_doc(title, content=""):
    """Crea un nuevo Google Doc.
    
    Args:
        title: Titulo del documento
        content: Contenido inicial (texto plano, default vacio)
    
    Devuelve: {"ok": bool, "id": ..., "link": ..., "reason": ...}
    """
    service, err = _service("docs", "v1")
    if err:
        return {"ok": False, "reason": err}
    
    try:
        doc = service.documents().create(body={"title": title}).execute()
        doc_id = doc.get("documentId")
        
        if content:
            requests = [{
                "insertText": {
                    "location": {"index": 1},
                    "text": content
                }
            }]
            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": requests}
            ).execute()
        # Mover a la carpeta Claudy automáticamente
        drive_svc, _ = _service("drive", "v3")
        if drive_svc:
            _move_to_claudy_folder(drive_svc, doc_id)
        return {
            "ok": True,
            "id": doc_id,
            "title": doc.get("title"),
            "link": f"https://docs.google.com/document/d/{doc_id}/edit",
        }
    except Exception as e:
        return {"ok": False, "reason": f"Error creando documento: {e}"}


def edit_doc(document_id, operations):
    """Edita un Google Doc con operaciones batch.
    
    Args:
        document_id: ID del documento
        operations: Lista de operaciones (ver Google Docs API batchUpdate)
                    Ejemplo: [{"insertText": {"location": {"index": 1}, "text": "Hola"}}]
    
    Devuelve: {"ok": bool, "replies": [...], "reason": ...}
    """
    service, err = _service("docs", "v1")
    if err:
        return {"ok": False, "reason": err}
    
    try:
        result = service.documents().batchUpdate(
            documentId=document_id,
            body={"requests": operations}
        ).execute()
        
        return {"ok": True, "replies": result.get("replies", [])}
    except Exception as e:
        return {"ok": False, "reason": f"Error editando documento: {e}"}


def append_to_doc(document_id, text):
    """Agrega texto al final de un Google Doc.
    
    Args:
        document_id: ID del documento
        text: Texto a agregar
    
    Devuelve: {"ok": bool, "reason": ...}
    """
    doc = read_doc(document_id)
    if not doc.get("ok"):
        return doc
    
    content = doc.get("content", "")
    end_index = len(content) + 1
    
    return edit_doc(document_id, [{
        "insertText": {
            "location": {"index": end_index},
            "text": text
        }
    }])


def read_sheet(spreadsheet_id, range_name="A1:Z1000"):
    """Lee datos de un Google Sheet.
    
    Args:
        spreadsheet_id: ID de la hoja (de la URL o de search_docs)
        range_name: Rango en formato A1 (default "A1:Z1000")
    
    Devuelve: {"connected": bool, "ok": bool, "values": [[...]], "reason": ...}
    """
    service, err = _service("sheets", "v4")
    if err:
        return {"connected": False, "ok": False, "reason": err}
    
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get("values", [])
        return {"connected": True, "ok": True, "values": values, "range": range_name}
    except Exception as e:
        return {"connected": False, "ok": False, "reason": f"Error leyendo hoja: {e}"}


def create_sheet(title, data=None, headers=None):
    """Crea un nuevo Google Sheet.
    
    Args:
        title: Titulo de la hoja
        data: Lista de listas con datos (opcional)
        headers: Lista con encabezados (opcional, se agrega antes de data)
    
    Devuelve: {"ok": bool, "id": ..., "link": ..., "reason": ...}
    """
    service, err = _service("sheets", "v4")
    if err:
        return {"ok": False, "reason": err}
    
    try:
        spreadsheet = {
            "properties": {"title": title}
        }
        
        result = service.spreadsheets().create(body=spreadsheet).execute()
        spreadsheet_id = result.get("spreadsheetId")
        
        if headers or data:
            values = []
            if headers:
                values.append(headers)
            if data:
                values.extend(data)
            
            if values:
                body = {"values": values}
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range="A1",
                    valueInputOption="RAW",
                    body=body
                ).execute()
        
        # Mover a la carpeta Claudy automáticamente
        drive_svc, _ = _service("drive", "v3")
        if drive_svc:
            _move_to_claudy_folder(drive_svc, spreadsheet_id)
        return {
            "ok": True,
            "id": spreadsheet_id,
            "title": result.get("properties", {}).get("title"),
            "link": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
        }
    except Exception as e:
        return {"ok": False, "reason": f"Error creando hoja: {e}"}


def edit_sheet(spreadsheet_id, range_name, values):
    """Edita celdas de un Google Sheet.
    
    Args:
        spreadsheet_id: ID de la hoja
        range_name: Rango en formato A1 (ej. "A1:C10" o "Sheet1!A1:C10")
        values: Lista de listas con los valores (ej. [["a", "b"], ["c", "d"]])
    
    Devuelve: {"ok": bool, "updatedCells": ..., "reason": ...}
    """
    service, err = _service("sheets", "v4")
    if err:
        return {"ok": False, "reason": err}
    
    try:
        body = {"values": values}
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        
        return {
            "ok": True,
            "updatedCells": result.get("updatedCells"),
            "updatedRows": result.get("updatedRows"),
            "updatedColumns": result.get("updatedColumns"),
        }
    except Exception as e:
        return {"ok": False, "reason": f"Error editando hoja: {e}"}


def append_to_sheet(spreadsheet_id, range_name, values):
    """Agrega filas al final de un Google Sheet.
    
    Args:
        spreadsheet_id: ID de la hoja
        range_name: Rango donde empezar (ej. "A1" o "Sheet1!A1")
        values: Lista de listas con los valores a agregar
    
    Devuelve: {"ok": bool, "updatedCells": ..., "reason": ...}
    """
    service, err = _service("sheets", "v4")
    if err:
        return {"ok": False, "reason": err}
    
    try:
        body = {"values": values}
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()

        return {
            "ok": True,
            "updatedCells": result.get("updates", {}).get("updatedCells"),
            "updatedRows": result.get("updates", {}).get("updatedRows"),
        }
    except Exception as e:
        return {"ok": False, "reason": f"Error agregando a hoja: {e}"}


# ── Carpeta raíz de Claudy en Drive ──────────────────────────────────────
CLAUDY_DRIVE_FOLDER_NAME = "claudy_files"


def get_or_create_claudy_folder():
    """Devuelve (folder_id, created) de la carpeta raíz 'Claudy' en Drive.
    La crea si no existe. Todos los archivos nuevos de Claudy van aquí."""
    service, err = _service("drive", "v3")
    if err:
        return None, False
    try:
        res = service.files().list(
            q=f"name='{CLAUDY_DRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)",
            pageSize=1,
        ).execute()
        files = res.get("files", [])
        if files:
            return files[0]["id"], False
        folder = service.files().create(
            body={"name": CLAUDY_DRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
        ).execute()
        return folder["id"], True
    except Exception:
        return None, False


def create_folder(name, parent_id=None):
    """Crea una carpeta en Drive.
    Si parent_id=None usa la carpeta raíz 'Claudy' automáticamente.
    Devuelve {"ok": bool, "id": ..., "name": ..., "link": ..., "reason": ...}"""
    service, err = _service("drive", "v3")
    if err:
        return {"ok": False, "reason": err}
    try:
        if not parent_id:
            parent_id, _ = get_or_create_claudy_folder()
        body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            body["parents"] = [parent_id]
        folder = service.files().create(body=body, fields="id, name, webViewLink").execute()
        return {
            "ok": True,
            "id": folder.get("id"),
            "name": folder.get("name"),
            "link": folder.get("webViewLink", f"https://drive.google.com/drive/folders/{folder.get('id')}"),
        }
    except Exception as e:
        return {"ok": False, "reason": f"Error creando carpeta: {e}"}


def search_in_drive(query, folder_id=None, doc_type="all", max_results=20):
    """Busca archivos en Drive (opcionalmente dentro de una carpeta específica).
    Si folder_id=None busca en todo Drive; si folder_id='claudy' usa la carpeta raíz de Claudy.
    doc_type: 'document' | 'spreadsheet' | 'folder' | 'all'
    Devuelve {"connected": bool, "items": [...], "reason": ...}"""
    service, err = _service("drive", "v3")
    if err:
        return {"connected": False, "reason": err, "items": []}
    try:
        if folder_id == "claudy":
            folder_id, _ = get_or_create_claudy_folder()
        parts = ["trashed=false"]
        if query:
            parts.append(f"name contains '{query}'")
        if folder_id:
            parts.append(f"'{folder_id}' in parents")
        if doc_type == "document":
            parts.append("mimeType='application/vnd.google-apps.document'")
        elif doc_type == "spreadsheet":
            parts.append("mimeType='application/vnd.google-apps.spreadsheet'")
        elif doc_type == "folder":
            parts.append("mimeType='application/vnd.google-apps.folder'")
        elif doc_type == "all":
            parts.append("(mimeType='application/vnd.google-apps.document' or "
                         "mimeType='application/vnd.google-apps.spreadsheet' or "
                         "mimeType='application/vnd.google-apps.folder')")
        q = " and ".join(parts)
        res = service.files().list(
            q=q, pageSize=max_results,
            fields="files(id, name, mimeType, modifiedTime, webViewLink, parents)",
            orderBy="modifiedTime desc",
        ).execute()
        items = []
        for f in res.get("files", []):
            mt = f.get("mimeType", "")
            kind = ("folder" if "folder" in mt
                    else "document" if "document" in mt
                    else "spreadsheet" if "spreadsheet" in mt else "file")
            items.append({
                "id": f.get("id"), "name": f.get("name"), "type": kind,
                "modifiedTime": f.get("modifiedTime"), "link": f.get("webViewLink"),
            })
        return {"connected": True, "items": items}
    except Exception as e:
        return {"connected": False, "reason": f"Error buscando: {e}", "items": []}


def _move_to_claudy_folder(service, file_id):
    """Mueve un archivo recién creado a la carpeta Claudy en Drive."""
    try:
        folder_id, _ = get_or_create_claudy_folder()
        if not folder_id:
            return
        f = service.files().get(fileId=file_id, fields="parents").execute()
        prev_parents = ",".join(f.get("parents", []))
        service.files().update(
            fileId=file_id,
            addParents=folder_id,
            removeParents=prev_parents,
            fields="id, parents",
        ).execute()
    except Exception:
        pass


def get_file_info(file_id):
    """Devuelve metadatos de un archivo de Drive (nombre, tipo, link).
    {"ok": bool, "name": ..., "type": ..., "link": ..., "reason": ...}"""
    service, err = _service("drive", "v3")
    if err:
        return {"ok": False, "reason": err}
    try:
        f = service.files().get(
            fileId=file_id, fields="id, name, mimeType, modifiedTime, webViewLink, trashed"
        ).execute()
        mt = f.get("mimeType", "")
        kind = "document" if "document" in mt else ("spreadsheet" if "spreadsheet" in mt else "file")
        return {
            "ok": True,
            "id": f.get("id"),
            "name": f.get("name"),
            "type": kind,
            "link": f.get("webViewLink"),
            "modifiedTime": f.get("modifiedTime"),
            "trashed": f.get("trashed", False),
        }
    except Exception as e:
        return {"ok": False, "reason": f"Error obteniendo info: {e}"}


def delete_file(file_id, to_trash=True):
    """Borra un Doc/Sheet (o cualquier archivo de Drive).

    Por defecto lo envia a la PAPELERA (recuperable desde Drive > Papelera).
    Con to_trash=False lo borra de forma PERMANENTE (irreversible).

    Devuelve: {"ok": bool, "trashed": bool, "name": ..., "reason": ...}
    """
    service, err = _service("drive", "v3")
    if err:
        return {"ok": False, "reason": err}
    try:
        # Capturar el nombre antes de borrar, para confirmar al usuario.
        name = ""
        try:
            name = service.files().get(fileId=file_id, fields="name").execute().get("name", "")
        except Exception:
            pass
        if to_trash:
            service.files().update(fileId=file_id, body={"trashed": True}).execute()
            return {"ok": True, "trashed": True, "name": name}
        service.files().delete(fileId=file_id).execute()
        return {"ok": True, "trashed": False, "name": name}
    except Exception as e:
        return {"ok": False, "reason": f"Error borrando: {e}"}
