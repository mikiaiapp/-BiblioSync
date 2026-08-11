"""
Main window GUI component for BiblioSync.
Designs a modern dashboard utilizing CustomTkinter to handle user interaction,
input validation, scan settings, progress updates, and logger telemetry.
"""

import customtkinter as ctk
from tkinter import filedialog, END
from pathlib import Path
import threading
import datetime
from src.config.settings import settings
from src.utils.logger import logger, gui_handler
from src.gui.settings_window import SettingsWindow
from src.gui.progress_dialog import ProgressDialog

# Core imports
from src.core.indexer import LibraryIndexer
from src.core.scanner import LibraryScanner
from src.core.comparer import BookComparer, NameSizeStrategy, NameOnlyStrategy, ISBNStrategy, AuthorTitleStrategy, SHA256Strategy
from src.core.copier import FileCopier
from src.export.excel_export import generate_excel_report
from src.export.csv_export import generate_csv_report
from src.database.database import db_manager
from src.utils.helpers import format_size

# Set initial appearance and theme
ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

class MainWindow(ctk.CTk):
    """
    Main dashboard for BiblioSync.
    Contains panels to select paths, view files to scan, configure options,
    trigger index/scan/sync tasks, and view live application logs.
    """
    def __init__(self):
        super().__init__()

        # Window settings
        self.title("BiblioSync - Sincronizador de Libros")
        self.geometry("900x650")
        self.minimum_size(800, 600)

        # Configure Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # Make log text box expand

        # Load configurations
        settings.load()
        
        # Instance state
        self.new_books = []

        # Build UI Elements
        self._create_paths_panel()
        self._create_scan_folders_panel()
        self._create_actions_panel()
        self._create_logs_panel()

        # Connect logger handler to GUI
        gui_handler.set_callback(self.write_log_line)
        logger.info("BiblioSync Dashboard iniciado.")

    def _create_paths_panel(self):
        """Creates widgets to select main library path and destination path."""
        # Container frame
        paths_frame = ctk.CTkFrame(self)
        paths_frame.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="ew")
        paths_frame.grid_columnconfigure(1, weight=1)

        # Title/Header
        lbl_section = ctk.CTkLabel(
            paths_frame, 
            text="Rutas de Sincronización", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_section.grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="w")

        # 1. Main Calibre Library Path
        lbl_lib = ctk.CTkLabel(paths_frame, text="Biblioteca Calibre:")
        lbl_lib.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        
        self.entry_lib_path = ctk.CTkEntry(paths_frame)
        self.entry_lib_path.insert(0, settings.main_library_path)
        self.entry_lib_path.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.entry_lib_path.bind("<FocusOut>", self._save_library_path)

        self.btn_browse_lib = ctk.CTkButton(
            paths_frame, 
            text="Examinar...", 
            width=100, 
            command=self._browse_library_path
        )
        self.btn_browse_lib.grid(row=1, column=2, padx=10, pady=5)

        # 2. Destination Folder Path
        lbl_dest = ctk.CTkLabel(paths_frame, text="Carpeta Destino:")
        lbl_dest.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        self.entry_dest_path = ctk.CTkEntry(paths_frame)
        self.entry_dest_path.insert(0, settings.destination_folder)
        self.entry_dest_path.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.entry_dest_path.bind("<FocusOut>", self._save_destination_path)

        self.btn_browse_dest = ctk.CTkButton(
            paths_frame, 
            text="Examinar...", 
            width=100, 
            command=self._browse_destination_path
        )
        self.btn_browse_dest.grid(row=2, column=2, padx=10, pady=5)

    def _create_scan_folders_panel(self):
        """Creates widgets to add, list, and remove folders to scan."""
        # Container frame
        scan_frame = ctk.CTkFrame(self)
        scan_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        scan_frame.grid_columnconfigure(0, weight=1)

        # Header and Buttons layout
        header_frame = ctk.CTkFrame(scan_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        lbl_section = ctk.CTkLabel(
            header_frame, 
            text="Carpetas de Origen a Analizar", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_section.grid(row=0, column=0, sticky="w")

        self.btn_add_folder = ctk.CTkButton(
            header_frame, 
            text="Añadir Carpeta", 
            width=120, 
            command=self._add_scan_folder
        )
        self.btn_add_folder.grid(row=0, column=1, padx=5)

        # Scrollable list area
        self.scrollable_folders = ctk.CTkScrollableFrame(scan_frame, height=120)
        self.scrollable_folders.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.scrollable_folders.grid_columnconfigure(0, weight=1)

        self._refresh_scan_folders_ui()

    def _create_actions_panel(self):
        """Creates widgets for trigger buttons, progress, and strategy."""
        actions_frame = ctk.CTkFrame(self)
        actions_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        actions_frame.grid_columnconfigure(1, weight=1)

        # Strategy dropdown
        lbl_strategy = ctk.CTkLabel(actions_frame, text="Método de Comparación:")
        lbl_strategy.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.strategy_menu = ctk.CTkOptionMenu(
            actions_frame, 
            values=["Name & Size", "Name Only", "ISBN", "Title & Author", "SHA256 Hash"],
            command=self._save_comparison_strategy
        )
        self.strategy_menu.set(settings.last_comparison_method)
        self.strategy_menu.grid(row=0, column=1, padx=5, pady=10, sticky="w")

        # Action trigger buttons
        buttons_frame = ctk.CTkFrame(actions_frame, fg_color="transparent")
        buttons_frame.grid(row=0, column=2, padx=10, pady=10, sticky="e")

        self.btn_analyze = ctk.CTkButton(
            buttons_frame, 
            text="Analizar", 
            fg_color="#1f538d", 
            hover_color="#14375e",
            command=self._trigger_analysis
        )
        self.btn_analyze.grid(row=0, column=0, padx=5)

        self.btn_copy = ctk.CTkButton(
            buttons_frame, 
            text="Copiar Libros", 
            fg_color="#2c823f", 
            hover_color="#1b5227",
            command=self._trigger_copy
        )
        self.btn_copy.grid(row=0, column=1, padx=5)

        # Progress indicator
        self.progress_bar = ctk.CTkProgressBar(actions_frame)
        self.progress_bar.grid(row=1, column=0, columnspan=3, padx=10, pady=(5, 10), sticky="ew")
        self.progress_bar.set(0.0)

    def _create_logs_panel(self):
        """Creates a bottom terminal logging console area."""
        logs_frame = ctk.CTkFrame(self)
        logs_frame.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="nsew")
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_rowconfigure(1, weight=1)

        lbl_section = ctk.CTkLabel(
            logs_frame, 
            text="Registro de Actividad (Log)", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_section.grid(row=0, column=0, padx=10, pady=(5, 2), sticky="w")

        self.txt_logs = ctk.CTkTextbox(
            logs_frame, 
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.txt_logs.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.txt_logs.configure(state="disabled")

    # Log writer helper
    def write_log_line(self, line: str) -> None:
        """Pipes log lines safely into the bottom GUI console."""
        self.after(0, self._append_to_textbox, line)

    def _append_to_textbox(self, line: str) -> None:
        self.txt_logs.configure(state="normal")
        self.txt_logs.insert(END, line)
        self.txt_logs.see(END)
        self.txt_logs.configure(state="disabled")

    # Folder list management
    def _refresh_scan_folders_ui(self):
        """Cleans and redraws the scan folders scrollable frame list."""
        for widget in self.scrollable_folders.winfo_children():
            widget.destroy()

        if not settings.scan_folders:
            empty_lbl = ctk.CTkLabel(
                self.scrollable_folders, 
                text="No hay carpetas configuradas. Haz clic en 'Añadir Carpeta'.", 
                text_color="gray"
            )
            empty_lbl.grid(row=0, column=0, padx=10, pady=10, sticky="w")
            return

        for index, path in enumerate(settings.scan_folders):
            row_frame = ctk.CTkFrame(self.scrollable_folders, fg_color="transparent")
            row_frame.grid(row=index, column=0, padx=5, pady=2, sticky="ew")
            row_frame.grid_columnconfigure(0, weight=1)

            lbl_path = ctk.CTkLabel(row_frame, text=path, anchor="w")
            lbl_path.grid(row=0, column=0, padx=5, pady=2, sticky="ew")

            btn_del = ctk.CTkButton(
                row_frame, 
                text="Eliminar", 
                width=70, 
                fg_color="#a83232", 
                hover_color="#702121",
                command=lambda p=path: self._remove_scan_folder(p)
            )
            btn_del.grid(row=0, column=1, padx=5, pady=2)

    # Event handlers and bindings
    def _browse_library_path(self):
        selected = filedialog.askdirectory(title="Seleccionar Biblioteca de Calibre")
        if selected:
            self.entry_lib_path.delete(0, END)
            self.entry_lib_path.insert(0, selected)
            self._save_library_path()

    def _browse_destination_path(self):
        selected = filedialog.askdirectory(title="Seleccionar Carpeta Destino")
        if selected:
            self.entry_dest_path.delete(0, END)
            self.entry_dest_path.insert(0, selected)
            self._save_destination_path()

    def _save_library_path(self, event=None):
        path = self.entry_lib_path.get().strip()
        settings.main_library_path = path
        settings.save()

    def _save_destination_path(self, event=None):
        path = self.entry_dest_path.get().strip()
        settings.destination_folder = path
        settings.save()

    def _save_comparison_strategy(self, choice: str):
        settings.last_comparison_method = choice
        settings.save()
        logger.info(f"Estrategia de comparación cambiada a: {choice}")

    def _add_scan_folder(self):
        selected = filedialog.askdirectory(title="Seleccionar Carpeta para Analizar")
        if selected and selected not in settings.scan_folders:
            settings.scan_folders.append(selected)
            settings.save()
            self._refresh_scan_folders_ui()
            logger.info(f"Carpeta añadida a la lista: {selected}")

    def _remove_scan_folder(self, path: str):
        if path in settings.scan_folders:
            settings.scan_folders.remove(path)
            settings.save()
            self._refresh_scan_folders_ui()
            logger.info(f"Carpeta eliminada de la lista: {path}")

    def _set_controls_state(self, state: str) -> None:
        """Enables or disables UI action widgets to prevent race conditions."""
        self.btn_analyze.configure(state=state)
        self.btn_copy.configure(state=state)
        self.entry_lib_path.configure(state=state)
        self.entry_dest_path.configure(state=state)
        self.strategy_menu.configure(state=state)
        self.btn_add_folder.configure(state=state)
        self.btn_browse_lib.configure(state=state)
        self.btn_browse_dest.configure(state=state)

    def _update_gui_progress(self, dialog: ProgressDialog, val: float, text: str) -> None:
        """Updates the progress dialog and main progress bar in a thread-safe way."""
        if dialog and dialog.winfo_exists():
            dialog.update_progress(val, text)
        self.progress_bar.set(val)

    # Core actions triggering with Background Worker Threads

    def _trigger_analysis(self):
        lib_path = self.entry_lib_path.get().strip()
        if not lib_path or not Path(lib_path).exists() or not Path(lib_path).is_dir():
            logger.error("La ruta de la biblioteca Calibre principal no es válida o no existe.")
            return

        if not settings.scan_folders:
            logger.error("Debe configurar al menos una carpeta de origen a analizar.")
            return

        logger.info("Iniciando análisis de bibliotecas...")
        self._set_controls_state("disabled")
        
        # Open modal progress dialog
        dialog = ProgressDialog(self, title="Analizando Biblioteca...")
        
        # Thread-safe progress updating helper
        def safe_update(val, text):
            self.after(0, lambda: self._update_gui_progress(dialog, val, text))

        def run_analysis_thread():
            try:
                # 1. Sync Calibre DB local index
                safe_update(0.1, "Indexando biblioteca de Calibre...")
                indexer = LibraryIndexer(lib_path)
                indexer.sync_index(progress_callback=safe_update)
                
                # 2. Scan source folders
                safe_update(0.8, "Escaneando carpetas de origen...")
                scanner = LibraryScanner(settings.scan_folders)
                scanned_books = scanner.scan()
                
                # 3. Filter using strategy
                safe_update(0.9, "Identificando libros duplicados...")
                strategy_choice = self.strategy_menu.get()
                
                if strategy_choice == "ISBN":
                    strategy = ISBNStrategy()
                elif strategy_choice == "Title & Author":
                    strategy = AuthorTitleStrategy()
                elif strategy_choice == "SHA256 Hash":
                    strategy = SHA256Strategy()
                elif strategy_choice == "Name Only":
                    strategy = NameOnlyStrategy()
                else:
                    strategy = NameSizeStrategy()
                
                comparer = BookComparer(strategy)
                new_books, duplicates = comparer.compare_books(scanned_books)
                
                # Categorize duplicates
                from src.core.comparer import is_exact_match
                confirmed = []
                doubtful = []
                for scanned, existing in duplicates:
                    if is_exact_match(scanned, existing):
                        confirmed.append((scanned, existing))
                    else:
                        doubtful.append((scanned, existing))
                
                self.new_books = new_books
                self.confirmed_dups = confirmed
                self.doubtful_dups = doubtful
                
                safe_update(1.0, "Análisis completado.")
                logger.info(f"Análisis finalizado: se han detectado {len(new_books)} libros nuevos y {len(duplicates)} duplicados ({len(confirmed)} confirmados, {len(doubtful)} dudosos) de {len(scanned_books)} escaneados.")
            except Exception as e:
                logger.error(f"Error durante el análisis: {e}")
                self.new_books = []
                self.confirmed_dups = []
                self.doubtful_dups = []
            finally:
                self.after(0, lambda: self._cleanup_after_analysis(dialog))

        # Start thread
        threading.Thread(target=run_analysis_thread, daemon=True).start()

    def _cleanup_after_analysis(self, dialog: ProgressDialog):
        if dialog and dialog.winfo_exists():
            dialog.grab_release()
            dialog.destroy()
        self._set_controls_state("normal")
        self.progress_bar.set(0.0)

    def _trigger_copy(self):
        dest_path = self.entry_dest_path.get().strip()
        if not dest_path:
            logger.error("Debe configurar la ruta de la carpeta de destino.")
            return

        new_books = getattr(self, "new_books", [])
        confirmed_dups = getattr(self, "confirmed_dups", [])
        doubtful_dups = getattr(self, "doubtful_dups", [])
        if not new_books and not confirmed_dups and not doubtful_dups:
            logger.warning("No hay libros nuevos detectados para copiar ni duplicados. Ejecute un análisis primero.")
            return

        logger.info("Iniciando copia de nuevos libros...")
        self._set_controls_state("disabled")
        
        # Open modal progress dialog
        dialog = ProgressDialog(self, title="Copiando libros...")
        
        # Thread-safe progress updating helper
        def safe_update(val, text):
            self.after(0, lambda: self._update_gui_progress(dialog, val, text))

        def run_copy_thread():
            try:
                safe_update(0.0, "Preparando copia...")
                copied_new = []
                failed_new = []
                if self.new_books:
                    copier = FileCopier(str(Path(dest_path) / "libros_a_importar"))
                    copied_new, failed_new = copier.copy_books(self.new_books, progress_callback=safe_update)
                
                confirmed_dups = getattr(self, "confirmed_dups", [])
                doubtful_dups = getattr(self, "doubtful_dups", [])
                
                copied_doubtful = []
                failed_doubtful = []
                if doubtful_dups:
                    logger.info(f"Copiando {len(doubtful_dups)} libros dudosos a la subcarpeta 'libros_dudosos'...")
                    doubtful_books = [scanned for scanned, _ in doubtful_dups]
                    
                    def safe_update_doubtful(val, text):
                        safe_update(0.5 + 0.3 * val, f"[Dudosos] {text}")
                        
                    copier_doubtful = FileCopier(str(Path(dest_path) / "libros_dudosos"))
                    copied_doubtful, failed_doubtful = copier_doubtful.copy_books(
                        doubtful_books, 
                        progress_callback=safe_update_doubtful
                    )
                
                copied = copied_new + copied_doubtful
                failed = failed_new + failed_doubtful
                
                # Report generation
                safe_update(0.9, "Generando informes de copia...")
                total_bytes = sum(b.file_size for b, _ in copied)
                strategy_choice = self.strategy_menu.get()
                
                confirmed_dups = getattr(self, "confirmed_dups", [])
                doubtful_dups = getattr(self, "doubtful_dups", [])
                
                summary_data = {
                    "Fecha de Sincronización": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Método de Comparación": strategy_choice,
                    "Libros Analizados": len(self.new_books) + len(confirmed_dups) + len(doubtful_dups),
                    "Libros Nuevos Copiados con Éxito": len(copied_new),
                    "Libros Dudosos Copiados con Éxito": len(copied_doubtful),
                    "Duplicados Confirmados": len(confirmed_dups),
                    "Errores de Copia (Nuevos)": len(failed_new),
                    "Errores de Copia (Dudosos)": len(failed_doubtful),
                    "Tamaño Total Copiado": format_size(total_bytes)
                }
                
                # Generate Excel
                excel_report_path = Path(dest_path) / "informe_bibliosync.xlsx"
                generate_excel_report(excel_report_path, copied, failed, confirmed_dups, doubtful_dups, summary_data)
                
                # Generate CSV
                csv_report_dir = Path(dest_path) / "informes_csv"
                generate_csv_report(csv_report_dir, copied, failed, confirmed_dups, doubtful_dups, summary_data)
                
                # Store history record
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
                            f"Nuevos: {len(copied_new)}, Dudosos: {len(copied_doubtful)}, Duplicados: {len(confirmed_dups)}"
                        ))
                        conn.commit()
                except Exception as db_err:
                    logger.error(f"Error al escribir registro de sincronización en BD: {db_err}")
                
                safe_update(1.0, "Copia completada con éxito.")
                logger.info("Copia de libros y exportación de informes completadas.")
                logger.info(f"Informe Excel guardado en: {excel_report_path}")
                logger.info(f"Informes CSV generados en: {csv_report_dir}")
                
                # Reset books list
                self.new_books = []
            except Exception as e:
                logger.error(f"Error durante el proceso de copia: {e}")
            finally:
                self.after(0, lambda: self._cleanup_after_copy(dialog))

        # Start thread
        threading.Thread(target=run_copy_thread, daemon=True).start()

    def _cleanup_after_copy(self, dialog: ProgressDialog):
        if dialog and dialog.winfo_exists():
            dialog.grab_release()
            dialog.destroy()
        self._set_controls_state("normal")
        self.progress_bar.set(0.0)
