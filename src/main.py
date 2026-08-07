"""
Main entry point for the BiblioSync application.
Initializes logging, configuration, databases, and launches the main GUI event loop.
"""

import sys
from src.utils.logger import logger, setup_logger
from src.config.settings import settings
from src.database.database import db_manager
from src.gui.main_window import MainWindow

def main():
    """Initializes and runs the BiblioSync application."""
    # 1. Initialize logging
    setup_logger()
    logger.info("Initializing BiblioSync...")

    # 2. Initialize database
    try:
        db_manager.initialize_db()
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
        sys.exit(1)

    # 3. Start GUI
    logger.info("Launching graphical interface...")
    try:
        app = MainWindow()
        app.mainloop()
    except Exception as e:
        logger.critical(f"Application crash during GUI execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
