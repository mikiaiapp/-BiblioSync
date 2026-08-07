"""
Logging module for BiblioSync.
Handles logging to stdout, a log file, and a custom Tkinter GUI console handler.
"""

import logging
from pathlib import Path
import os
import sys

# If running in a container, logs are stored in /data, otherwise in the local directory
if os.path.exists("/data"):
    LOG_PATH = Path("/data/bibliosync.log")
else:
    LOG_PATH = Path("bibliosync.log")

class GUIConsoleHandler(logging.Handler):
    """
    Custom logging handler that directs log records to a callback.
    Typically used to insert logs into a Tkinter text widget.
    """
    def __init__(self):
        super().__init__()
        self._callback = None

    def set_callback(self, callback):
        """Register the GUI callback to receive log messages."""
        self._callback = callback

    def emit(self, record):
        try:
            log_entry = self.format(record) + "\n"
            if self._callback:
                self._callback(log_entry)
        except Exception:
            self.handleError(record)

# Singleton-style instances for easy import
logger = logging.getLogger("BiblioSync")
gui_handler = GUIConsoleHandler()

def setup_logger():
    """
    Configures the application logger.
    - FILE: logs everything at DEBUG level
    - STDOUT: logs at INFO level (useful for Docker logs)
    - GUI: logs at INFO level
    """
    # Prevent duplicate handlers if setup_logger is called multiple times
    if logger.handlers:
        return
        
    logger.setLevel(logging.DEBUG)
    
    # Formatter for all handlers
    formatter = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 1. Console (Stdout) Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    # 2. File Handler
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_PATH, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to initialize file logger at {LOG_PATH}: {e}", file=sys.stderr)
        
    # 3. GUI Handler
    gui_handler.setFormatter(formatter)
    gui_handler.setLevel(logging.INFO)
    logger.addHandler(gui_handler)
    
    logger.info("Logger system initialized.")

# Initialize logging system automatically on module import
setup_logger()

