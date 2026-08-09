"""
Copier module for BiblioSync.
Handles copying files to a flat destination directory, managing name collisions,
and recording status for report generation.
"""

from pathlib import Path
from typing import List, Tuple
import shutil
from src.database.models import Book
from src.utils.helpers import get_unique_path
from src.utils.logger import logger

class FileCopier:
    """
    Copies ebook files from source folders to a flat target folder.
    Tracks successful operations and failures.
    """
    def __init__(self, destination_dir: str):
        self.destination_dir = Path(destination_dir)

    def copy_books(self, books: List[Book], progress_callback=None) -> Tuple[List[Tuple[Book, str]], List[Tuple[Book, str]]]:
        """
        Copies books to the destination directory.
        If a file exists, it renames it using get_unique_path.
        
        Args:
            books: List of Book instances to copy.
            progress_callback: Optional callable for reporting progress (progress_float, status_str).
            
        Returns:
            Tuple[List[Tuple[Book, str]], List[Tuple[Book, str]]]: 
                - List of (Book, copied_path) for successful copies.
                - List of (Book, error_message) for failed copies.
        """
        copied_books: List[Tuple[Book, str]] = []
        failed_books: List[Tuple[Book, str]] = []
        
        logger.info(f"Starting copy of {len(books)} books to {self.destination_dir}...")
        
        # Ensure destination directory exists
        try:
            self.destination_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            msg = f"Failed to create destination directory: {e}"
            logger.error(msg)
            return [], [(b, msg) for b in books]

        total_books = len(books)
        for index, book in enumerate(books):
            if progress_callback:
                progress_val = index / max(total_books, 1)
                progress_callback(progress_val, f"Copiando ({index + 1}/{total_books}): {book.file_name}")
                
            src_path = Path(book.file_path)
            if not src_path.exists():
                err_msg = "El archivo de origen no existe."
                logger.error(f"Error al copiar {book.file_name}: {err_msg}")
                failed_books.append((book, err_msg))
                continue
                
            try:
                # Resolve author subfolder (sanitize name for paths)
                author = book.author.strip() if book.author else "Autor Desconocido"
                # Remove characters that are invalid in directory names (Windows / POSIX compatible)
                for c in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
                    author = author.replace(c, '_')
                
                # Make sure the author directory is created
                author_dir = self.destination_dir / author
                author_dir.mkdir(parents=True, exist_ok=True)
                
                dest_path = get_unique_path(author_dir, book.file_name)
                shutil.copy2(src_path, dest_path)
                copied_path_str = str(dest_path.resolve())
                copied_books.append((book, copied_path_str))
                logger.info(f"Copiado con éxito: {book.file_name} -> {author}/{dest_path.name}")
            except Exception as e:
                err_msg = str(e)
                logger.error(f"Error al copiar {book.file_name}: {err_msg}")
                failed_books.append((book, err_msg))
                
        if progress_callback:
            progress_callback(1.0, "Copia de archivos finalizada.")
            
        logger.info(f"Copy process completed: {len(copied_books)} successful, {len(failed_books)} failed.")
        return copied_books, failed_books
