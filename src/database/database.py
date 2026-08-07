"""
Database management module for BiblioSync.
Initializes SQLite database schemas, manages connections, and indexes.
"""

import sqlite3
import os
from pathlib import Path
from src.utils.logger import logger

# Path configuration based on environment
if os.path.exists("/data"):
    DB_PATH = Path("/data/bibliosync.db")
else:
    DB_PATH = Path("bibliosync.db")

class DatabaseManager:
    """
    Manages connections and lifecycle operations for the SQLite database.
    """
    def __init__(self):
        self.db_path = DB_PATH

    import contextlib

    @contextlib.contextmanager
    def get_connection(self):
        """
        Creates and yields a connection to the SQLite database.
        Ensures that the database connection is closed when exiting the context.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def initialize_db(self) -> None:
        """
        Executes table creations and indexes to prepare the database schema.
        Executed once during application startup.
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Books Index Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS books (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_name TEXT NOT NULL,
                        file_path TEXT UNIQUE NOT NULL,
                        file_size INTEGER NOT NULL,
                        format TEXT NOT NULL,
                        mtime REAL NOT NULL,
                        sha256 TEXT,
                        title TEXT,
                        author TEXT,
                        isbn TEXT
                    )
                """)
                
                # Synchronization History Log Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sync_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        files_copied INTEGER NOT NULL,
                        errors_encountered INTEGER NOT NULL,
                        summary TEXT NOT NULL
                    )
                """)
                
                # Indexes to accelerate scan query comparisons
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_name_size ON books(file_name, file_size)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_path ON books(file_path)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_hash ON books(sha256)")
                
                conn.commit()
            logger.info(f"Database schema initialized successfully at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise e

# Database manager instance
db_manager = DatabaseManager()
