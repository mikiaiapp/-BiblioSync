"""
Settings window for BiblioSync.
Enables configuring advanced options and behavior preferences.
"""

import customtkinter as ctk
from src.utils.logger import logger

class SettingsWindow(ctk.CTkToplevel):
    """
    Toplevel window for user configurations.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.title("BiblioSync - Configuración")
        self.geometry("450x300")
        self.resizable(False, False)
        
        # Make the window modal
        self.transient(parent)
        self.grab_set()
        
        # Configure layout grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Setup widgets container
        self.label = ctk.CTkLabel(
            self, 
            text="Ajustes de BiblioSync", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.label.grid(row=0, column=0, padx=20, pady=20, sticky="n")
        
        self.close_btn = ctk.CTkButton(self, text="Cerrar", command=self.destroy)
        self.close_btn.grid(row=1, column=0, padx=20, pady=20, sticky="s")
        
        logger.debug("Settings window created.")
