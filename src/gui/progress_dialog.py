"""
Progress dialog module for BiblioSync.
Displays dynamic progress bars and status text during scanning and copying actions.
"""

import customtkinter as ctk
from src.utils.logger import logger

class ProgressDialog(ctk.CTkToplevel):
    """
    Dialog displaying real-time feedback for long-running operations.
    """
    def __init__(self, parent, title: str = "Procesando..."):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x180")
        self.resizable(False, False)
        
        # Make the window modal
        self.transient(parent)
        self.grab_set()
        
        # Configure layout
        self.grid_columnconfigure(0, weight=1)
        
        # Label
        self.status_label = ctk.CTkLabel(
            self, 
            text="Iniciando tarea...", 
            font=ctk.CTkFont(size=14)
        )
        self.status_label.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.progress_bar.set(0.0)
        
        logger.debug("Progress dialog opened.")
        
    def update_progress(self, val: float, status_text: str) -> None:
        """
        Updates the progress bar value and status text.
        
        Args:
            val (float): Progress value between 0.0 and 1.0.
            status_text (str): Display message explaining the current action.
        """
        self.progress_bar.set(val)
        self.status_label.configure(text=status_text)
        self.update_idletasks()
