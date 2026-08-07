"""
Web Application entry point for BiblioSync.
Initializes a FastAPI application, provides REST endpoints for settings and directory browsing,
and manages real-time tasks and logging over WebSockets.
"""

import os
import string
import platform
import asyncio
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

# Core imports
from src.config.settings import settings
from src.database.database import db_manager
from src.database.models import Book
from src.core.indexer import LibraryIndexer
from src.core.scanner import LibraryScanner
from src.core.comparer import BookComparer, NameSizeStrategy, ISBNStrategy, AuthorTitleStrategy, SHA256Strategy
from src.core.copier import FileCopier
from src.export.excel_export import generate_excel_report
from src.export.csv_export import generate_csv_report
from src.utils.helpers import format_size
from src.utils.logger import logger

# Store the global active books list found in the last analysis
global_new_books: List[Book] = []
global_new_books_lock = threading.Lock()

# Custom logging handler to stream logs over WebSockets
class WebSocketLogHandler(logging.Handler):
    def __init__(self, loop, send_coro):
        super().__init__()
        self.loop = loop
        self.send_coro = send_coro

    def emit(self, record):
        try:
            log_line = self.format(record)
            # Push message thread-safely to the async event loop
            asyncio.run_coroutine_threadsafe(self.send_coro(log_line), self.loop)
        except Exception:
            pass

def get_windows_drives() -> List[str]:
    """Lists logical drives on Windows system."""
    import ctypes
    drives = []
    bitmask = ctypes.cdll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            drives.append(f"{letter}:\\")
        bitmask >>= 1
    return drives

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB schemas
    db_manager.initialize_db()
    yield
    # Shutdown

app = FastAPI(title="BiblioSync Web App", lifespan=lifespan)

# Endpoint: Settings management
@app.get("/api/settings")
def get_settings():
    settings.load()
    return {
        "main_library_path": settings.main_library_path,
        "scan_folders": settings.scan_folders,
        "destination_folder": settings.destination_folder,
        "last_comparison_method": settings.last_comparison_method
    }

@app.post("/api/settings")
def save_settings(data: Dict[str, Any]):
    settings.main_library_path = data.get("main_library_path", "")
    settings.scan_folders = list(data.get("scan_folders", []))
    settings.destination_folder = data.get("destination_folder", "")
    settings.last_comparison_method = data.get("last_comparison_method", "Name & Size")
    settings.save()
    return {"status": "success", "message": "Configuración guardada correctamente."}

# Endpoint: Server-side Directory Explorer
@app.get("/api/browse")
def browse_directory(path: str = ""):
    is_windows = platform.system() == "Windows"
    
    # If path is empty, return drives on Windows or root on Unix
    if not path:
        if is_windows:
            drives = get_windows_drives()
            return {
                "current_path": "",
                "parent_path": "",
                "directories": [{"name": d, "path": d} for d in drives]
            }
        else:
            path = "/"
            
    p = Path(path)
    if not p.exists() or not p.is_dir():
        # Fallback to drives on Windows or root on Unix
        if is_windows:
            drives = get_windows_drives()
            return {
                "error": "El directorio no existe.",
                "current_path": "",
                "parent_path": "",
                "directories": [{"name": d, "path": d} for d in drives]
            }
        else:
            p = Path("/")

    directories = []
    try:
        for entry in os.scandir(p):
            try:
                if entry.is_dir(follow_symlinks=False):
                    if not entry.name.startswith("."):
                        directories.append({
                            "name": entry.name,
                            "path": str(Path(entry.path).resolve())
                        })
            except OSError:
                pass # Skip folders with permission issues
    except Exception as e:
        return {"error": f"No se pudo leer el directorio: {e}"}

    directories.sort(key=lambda x: x["name"].lower())
    
    # Calculate parent directory path
    parent_path = str(p.parent.resolve()) if p.parent != p else ""
    if is_windows and str(p) in get_windows_drives():
        parent_path = "" # Windows drives have no parents

    return {
        "current_path": str(p.resolve()),
        "parent_path": parent_path,
        "directories": directories
    }

# Endpoint: Sync history log
@app.get("/api/history")
def get_history():
    history = []
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, files_copied, errors_encountered, summary FROM sync_history ORDER BY id DESC LIMIT 15")
            for row in cursor.fetchall():
                history.append({
                    "timestamp": row["timestamp"],
                    "files_copied": row["files_copied"],
                    "errors_encountered": row["errors_encountered"],
                    "summary": row["summary"]
                })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer historial: {e}")
    return history

# Endpoint: WebSocket for real-time task triggers, progress, and logging
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()

    # Define message sender helpers
    async def send_log_line(line: str):
        try:
            await websocket.send_json({"type": "log", "line": line})
        except Exception:
            pass

    async def send_progress_update(val: float, text: str):
        try:
            await websocket.send_json({"type": "progress", "val": val, "text": text})
        except Exception:
            pass

    # Safe callback wrapper for indexer/scanner/copier
    def progress_callback_thread(val: float, text: str):
        asyncio.run_coroutine_threadsafe(send_progress_update(val, text), loop)

    # Attach websocket log handler to the system logger
    log_handler = WebSocketLogHandler(loop, send_log_line)
    # Format log entries nicely for the client console
    log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
    logging.getLogger().addHandler(log_handler)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "analyze":
                threading.Thread(
                    target=run_analysis_task, 
                    args=(progress_callback_thread,), 
                    daemon=True
                ).start()
                
            elif action == "copy":
                threading.Thread(
                    target=run_copy_task, 
                    args=(progress_callback_thread,), 
                    daemon=True
                ).start()
                
    except WebSocketDisconnect:
        pass
    finally:
        # Detach log handler on websocket disconnect to prevent memory leak
        logging.getLogger().removeHandler(log_handler)

def run_analysis_task(progress_callback):
    global global_new_books
    try:
        progress_callback(0.05, "Iniciando análisis...")
        settings.load()
        
        # 1. Index Calibre database
        progress_callback(0.1, "Indexando biblioteca Calibre...")
        indexer = LibraryIndexer(settings.main_library_path)
        indexer.sync_index(progress_callback=progress_callback)
        
        # 2. Scan source folders
        progress_callback(0.8, "Escaneando carpetas de origen...")
        scanner = LibraryScanner(settings.scan_folders)
        scanned_books = scanner.scan()
        
        # 3. Compare and filter
        progress_callback(0.9, "Filtrando libros existentes...")
        strategy_choice = settings.last_comparison_method
        if strategy_choice == "ISBN":
            strategy = ISBNStrategy()
        elif strategy_choice == "Title & Author":
            strategy = AuthorTitleStrategy()
        elif strategy_choice == "SHA256 Hash":
            strategy = SHA256Strategy()
        else:
            strategy = NameSizeStrategy()
            
        comparer = BookComparer(strategy)
        new_books = comparer.get_new_books(scanned_books)
        
        with global_new_books_lock:
            global_new_books = new_books
            
        progress_callback(1.0, "Análisis completado.")
        logger.info(f"Análisis finalizado: se han detectado {len(new_books)} libros nuevos de {len(scanned_books)} escaneados.")
        
    except Exception as e:
        logger.error(f"Error durante el análisis: {e}")
        progress_callback(1.0, f"Error: {e}")

def run_copy_task(progress_callback):
    global global_new_books
    try:
        progress_callback(0.05, "Iniciando copia de archivos...")
        settings.load()
        
        with global_new_books_lock:
            books_to_copy = list(global_new_books)
            
        if not books_to_copy:
            logger.warning("No hay libros nuevos para copiar. Realice un análisis primero.")
            progress_callback(1.0, "No hay libros nuevos para copiar.")
            return

        dest_path = settings.destination_folder
        copier = FileCopier(dest_path)
        copied, failed = copier.copy_books(books_to_copy, progress_callback=progress_callback)
        
        # 2. Report generation
        progress_callback(0.9, "Generando informes...")
        total_bytes = sum(b.file_size for b, _ in copied)
        
        summary_data = {
            "Fecha de Sincronización": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Método de Comparación": settings.last_comparison_method,
            "Libros Analizados": len(books_to_copy),
            "Libros Copiados con Éxito": len(copied),
            "Errores de Copia": len(failed),
            "Tamaño Total Copiado": format_size(total_bytes)
        }
        
        # Generate Excel
        excel_report_path = Path(dest_path) / "informe_bibliosync.xlsx"
        generate_excel_report(excel_report_path, copied, failed, summary_data)
        
        # Generate CSV
        csv_report_dir = Path(dest_path) / "informes_csv"
        generate_csv_report(csv_report_dir, copied, failed, summary_data)
        
        # Write history record to DB
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sync_history (timestamp, files_copied, errors_encountered, summary)
                    VALUES (?, ?, ?, ?)
                """, (
                    summary_data["Fecha de Sincronización"],
                    len(copied),
                    len(failed),
                    f"Copias: {len(copied)}, Errores: {len(failed)}"
                ))
                conn.commit()
        except Exception as db_err:
            logger.error(f"Error al escribir en la base de datos de historial: {db_err}")

        progress_callback(1.0, "Copia completada con éxito.")
        logger.info("Copia de libros e informes generados correctamente.")
        logger.info(f"Informe Excel guardado en: {excel_report_path}")
        logger.info(f"Informes CSV guardados en: {csv_report_dir}")
        
        # Clear list on successful copy completion
        with global_new_books_lock:
            global_new_books = []
            
    except Exception as e:
        logger.error(f"Error durante el proceso de copia: {e}")
        progress_callback(1.0, f"Error: {e}")

# Mount static files and redirect homepage to index.html
web_dir = Path(__file__).parent / "web"
if not web_dir.exists():
    web_dir.mkdir(parents=True, exist_ok=True)

app.mount("/web", StaticFiles(directory=str(web_dir), html=True), name="web")

@app.get("/")
def read_root():
    return RedirectResponse(url="/web/index.html")

if __name__ == "__main__":
    import uvicorn
    # Start web server on port 6080 (matching compose settings)
    uvicorn.run("src.main:app", host="0.0.0.0", port=6080, reload=True)
