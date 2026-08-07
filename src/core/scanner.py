"""
Scanner module for BiblioSync.
Traverses source folders and identifies ebook files matching supported formats,
filtering out irrelevant system or image files.
"""

import os
from pathlib import Path
from typing import List, Set
from src.database.models import Book
from src.utils.logger import logger

# Constants for ebook formats and files to ignore
SUPPORTED_FORMATS: Set[str] = {
    '.epub', '.pdf', '.mobi', '.azw', '.azw3', '.fb2', '.djvu', '.cbz', '.cbr'
}

IGNORED_EXTENSIONS: Set[str] = {
    '.jpg', '.jpeg', '.png', '.gif', '.opf', '.xml', '.ini', '.db'
}

IGNORED_FILENAMES: Set[str] = {
    'thumbs.db', 'desktop.ini', '.ds_store'
}

class LibraryScanner:
    """
    Scans folders recursively to locate supported ebook files.
    """
    def __init__(self, paths_to_scan: List[str]):
        self.paths_to_scan = [Path(p) for p in paths_to_scan]

    def scan(self) -> List[Book]:
        """
        Scans all registered directories for supported ebooks.
        Skips ignored extensions and filenames.
        
        Returns:
            List[Book]: List of Book instances containing basic file metadata.
        """
        found_books: List[Book] = []
        logger.info(f"Starting scanning of {len(self.paths_to_scan)} source directories...")

        for root_path in self.paths_to_scan:
            if not root_path.exists() or not root_path.is_dir():
                logger.warning(f"Scan path does not exist or is not a directory: {root_path}")
                continue

            logger.info(f"Scanning directory: {root_path}")
            books_in_path = self._scan_directory_recursive(root_path)
            found_books.extend(books_in_path)
            logger.info(f"Completed scanning {root_path}. Found {len(books_in_path)} ebook(s).")

        logger.info(f"Scanning completed. Total ebooks found: {len(found_books)}")
        return found_books

    def _scan_directory_recursive(self, directory: Path) -> List[Book]:
        """Helper to recursively scan a single directory."""
        books: List[Book] = []
        
        try:
            for entry in os.scandir(directory):
                try:
                    entry_path = Path(entry.path)
                    
                    if entry.is_dir(follow_symlinks=False):
                        # Recursive call
                        books.extend(self._scan_directory_recursive(entry_path))
                        
                    elif entry.is_file(follow_symlinks=False):
                        filename_lower = entry.name.lower()
                        
                        # 1. Skip system files
                        if filename_lower in IGNORED_FILENAMES:
                            continue
                            
                        # 2. Skip ignored extensions
                        suffix = entry_path.suffix.lower()
                        if suffix in IGNORED_EXTENSIONS:
                            continue
                            
                        # 3. Process supported formats
                        if suffix in SUPPORTED_FORMATS:
                            stat_res = entry.stat()
                            book = Book(
                                file_name=entry.name,
                                file_path=str(entry_path.resolve()),
                                file_size=stat_res.st_size,
                                format=suffix[1:],  # Remove the leading dot (e.g. 'epub')
                                mtime=stat_res.st_mtime,
                                id=None
                            )
                            books.append(book)
                except OSError as e:
                    logger.error(f"Error accessing entry '{entry.name}' in '{directory}': {e}")
                    
        except OSError as e:
            logger.error(f"Error listing directory '{directory}': {e}")

        return books
