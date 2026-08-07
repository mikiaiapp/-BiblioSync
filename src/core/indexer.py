"""
Indexer module for BiblioSync.
Scans and registers files from the Calibre main library into the SQLite database.
Performs differential updates by checking file modification times and sizes.
"""

import os
from pathlib import Path
from typing import Dict, Set, Tuple, List
from src.database.database import db_manager
from src.database.models import Book
from src.core.scanner import SUPPORTED_FORMATS, IGNORED_FILENAMES, IGNORED_EXTENSIONS
from src.core.metadata import MetadataExtractor
from src.core.hashing import calculate_sha256
from src.utils.logger import logger

class LibraryIndexer:
    """
    Indexes the main library directory and maintains the SQLite local book index.
    """
    def __init__(self, main_library_path: str):
        self.main_library_path = Path(main_library_path)

    def is_indexed(self) -> bool:
        """Checks if the database contains any records."""
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM books")
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.error(f"Error checking if database is indexed: {e}")
            return False

    def sync_index(self, progress_callback=None) -> Tuple[int, int, int]:
        """
        Main entry point for differential indexing.
        Scans disk and compares against SQLite index to compute:
          - Additions
          - Modifications
          - Deletions
        Applies changes inside a transaction.
        
        Args:
            progress_callback: A callback function taking (float progress, str status_text)
            
        Returns:
            Tuple[int, int, int]: (added_count, modified_count, deleted_count)
        """
        if not self.main_library_path.exists() or not self.main_library_path.is_dir():
            logger.error(f"Library path not found or invalid: {self.main_library_path}")
            return 0, 0, 0

        logger.info("Retrieving indexed books from database...")
        if progress_callback:
            progress_callback(0.1, "Recuperando índice actual...")
            
        db_books = self._get_indexed_books()
        logger.info(f"Retrieved {len(db_books)} books from database index.")

        logger.info("Scanning main library on disk...")
        if progress_callback:
            progress_callback(0.2, "Escaneando biblioteca en disco...")
            
        disk_files = self._scan_disk_library()
        logger.info(f"Found {len(disk_files)} ebooks on disk.")
        if len(disk_files) == 0:
            logger.warning("No se encontraron libros en la biblioteca de Calibre. Verifique que la ruta de la biblioteca sea correcta y que contenga libros en formatos soportados (epub, pdf, mobi, etc.).")

        # Compute differences
        disk_paths = set(disk_files.keys())
        db_paths = set(db_books.keys())

        new_paths = disk_paths - db_paths
        deleted_paths = db_paths - disk_paths
        
        modified_paths = set()
        for path in disk_paths & db_paths:
            disk_mtime, disk_size = disk_files[path]
            db_mtime, db_size = db_books[path]
            # Consider modified if mtime changed by more than 1 second or size changed
            if abs(disk_mtime - db_mtime) > 1.0 or disk_size != db_size:
                modified_paths.add(path)

        added_count = len(new_paths)
        modified_count = len(modified_paths)
        deleted_count = len(deleted_paths)

        logger.info(f"Index differences: {added_count} new, {modified_count} modified, {deleted_count} deleted.")

        # Process additions and modifications
        to_upsert: List[Book] = []
        total_upsert = added_count + modified_count
        processed = 0

        # Mappings
        upsert_paths = list(new_paths) + list(modified_paths)
        
        for path_str in upsert_paths:
            path = Path(path_str)
            disk_mtime, disk_size = disk_files[path_str]
            
            # Extract metadata and hash
            if progress_callback:
                processed += 1
                prog_val = 0.2 + (0.7 * (processed / max(total_upsert, 1)))
                progress_callback(prog_val, f"Indexando ({processed}/{total_upsert}): {path.name}")
            
            meta = MetadataExtractor.extract(path)
            
            sha256_val = None
            try:
                sha256_val = calculate_sha256(path)
            except Exception:
                pass # Already logged in calculate_sha256
                
            book = Book(
                file_name=path.name,
                file_path=str(path.resolve()),
                file_size=disk_size,
                format=path.suffix[1:].lower(),
                mtime=disk_mtime,
                sha256=sha256_val,
                title=meta.get('title'),
                author=meta.get('author'),
                isbn=meta.get('isbn')
            )
            to_upsert.append(book)

        # Write to Database in one transaction
        if progress_callback:
            progress_callback(0.95, "Guardando índice en base de datos...")
            
        self._apply_changes(to_upsert, list(deleted_paths))

        if progress_callback:
            progress_callback(1.0, "Indexación finalizada.")
            
        logger.info("Database index synchronization completed.")
        return added_count, modified_count, deleted_count

    def _get_indexed_books(self) -> Dict[str, Tuple[float, int]]:
        """
        Queries the database for existing book metadata.
        Returns a dict: {file_path: (mtime, file_size)}
        """
        books_map: Dict[str, Tuple[float, int]] = {}
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT file_path, mtime, file_size FROM books")
                for row in cursor.fetchall():
                    books_map[row['file_path']] = (row['mtime'], row['file_size'])
        except Exception as e:
            logger.error(f"Error fetching indexed books: {e}")
        return books_map

    def _scan_disk_library(self) -> Dict[str, Tuple[float, int]]:
        """
        Performs a fast file scan of the main library.
        Returns a dict: {file_path: (mtime, file_size)}
        """
        disk_map: Dict[str, Tuple[float, int]] = {}
        self._scan_dir(self.main_library_path, disk_map)
        return disk_map

    def _scan_dir(self, directory: Path, disk_map: Dict[str, Tuple[float, int]]):
        """Recursive directory walker populating disk_map."""
        try:
            for entry in os.scandir(directory):
                try:
                    entry_path = Path(entry.path)
                    if entry.is_dir(follow_symlinks=True):
                        self._scan_dir(entry_path, disk_map)
                    elif entry.is_file(follow_symlinks=True):
                        filename_lower = entry.name.lower()
                        if filename_lower in IGNORED_FILENAMES:
                            continue
                        suffix = entry_path.suffix.lower()
                        if suffix in IGNORED_EXTENSIONS:
                            continue
                        if suffix in SUPPORTED_FORMATS:
                            stat_res = entry.stat()
                            disk_map[str(entry_path.resolve())] = (stat_res.st_mtime, stat_res.st_size)
                except OSError as e:
                    logger.error(f"Error reading file entry {entry.name}: {e}")
        except OSError as e:
            logger.error(f"Error reading directory {directory}: {e}")

    def _apply_changes(self, to_upsert: List[Book], to_delete: List[str]):
        """Executes database updates in a single atomic transaction."""
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Delete old files
                if to_delete:
                    # Split into chunks of 900 to avoid SQLite parameter limit
                    chunk_size = 900
                    for i in range(0, len(to_delete), chunk_size):
                        chunk = to_delete[i:i+chunk_size]
                        placeholders = ",".join(["?"] * len(chunk))
                        cursor.execute(f"DELETE FROM books WHERE file_path IN ({placeholders})", chunk)

                # Upsert new/modified files
                for book in to_upsert:
                    cursor.execute("""
                        INSERT INTO books (file_name, file_path, file_size, format, mtime, sha256, title, author, isbn)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(file_path) DO UPDATE SET
                            file_name=excluded.file_name,
                            file_size=excluded.file_size,
                            format=excluded.format,
                            mtime=excluded.mtime,
                            sha256=excluded.sha256,
                            title=excluded.title,
                            author=excluded.author,
                            isbn=excluded.isbn
                    """, (
                        book.file_name,
                        book.file_path,
                        book.file_size,
                        book.format,
                        book.mtime,
                        book.sha256,
                        book.title,
                        book.author,
                        book.isbn
                    ))
                conn.commit()
            logger.info("Database changes committed successfully.")
        except Exception as e:
            logger.error(f"Error applying index changes to database: {e}")
            raise e
