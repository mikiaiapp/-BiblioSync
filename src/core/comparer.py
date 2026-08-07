"""
Comparer module for BiblioSync.
Implements the Strategy Pattern to dynamically interchange book comparison methods
(e.g., Name & Size, ISBN, Title & Author, or SHA256 hashing).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List
from src.database.models import Book
from src.database.database import db_manager
from src.core.metadata import MetadataExtractor
from src.core.hashing import calculate_sha256
from src.utils.logger import logger

class ComparisonStrategy(ABC):
    """
    Abstract Base Class for all comparison strategies.
    Determines whether scanned books already exist in the database index.
    """
    @abstractmethod
    def filter_existing(self, books: List[Book]) -> List[Book]:
        """
        Filters a list of books, returning only those that do NOT exist in the library.
        
        Args:
            books (List[Book]): List of scanned books to evaluate.
            
        Returns:
            List[Book]: Books that are new and need to be copied.
        """
        pass


class NameSizeStrategy(ComparisonStrategy):
    """
    Compares books using their Filename and File Size.
    This is the default, fast comparison method.
    """
    def filter_existing(self, books: List[Book]) -> List[Book]:
        logger.info("Comparing books using Name & Size strategy...")
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT file_name, file_size FROM books")
                existing = {(row['file_name'].lower(), row['file_size']) for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching existing books for Name & Size strategy: {e}")
            existing = set()
        
        new_books: List[Book] = []
        for book in books:
            key = (book.file_name.lower(), book.file_size)
            if key not in existing:
                new_books.append(book)
        logger.info(f"Name & Size filter: {len(books)} scanned -> {len(new_books)} new.")
        return new_books


class SHA256Strategy(ComparisonStrategy):
    """
    Compares books using the SHA256 hash of their content.
    Highly accurate but slower due to hashing scanned files on the fly.
    """
    def filter_existing(self, books: List[Book]) -> List[Book]:
        logger.info("Comparing books using SHA256 Hash strategy...")
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT sha256 FROM books WHERE sha256 IS NOT NULL")
                existing = {row['sha256'] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching existing books for SHA256 strategy: {e}")
            existing = set()
        
        new_books: List[Book] = []
        for book in books:
            try:
                # Calculate hash for scanned book on the fly
                sha = calculate_sha256(Path(book.file_path))
                book.sha256 = sha
                if sha not in existing:
                    new_books.append(book)
            except Exception as e:
                logger.warning(f"Could not calculate SHA256 for {book.file_name}: {e}. Treating as new.")
                new_books.append(book)
        logger.info(f"SHA256 Hash filter: {len(books)} scanned -> {len(new_books)} new.")
        return new_books


class ISBNStrategy(ComparisonStrategy):
    """
    Compares books using their extracted ISBN.
    Falls back to Name & Size if no ISBN is found.
    """
    def filter_existing(self, books: List[Book]) -> List[Book]:
        logger.info("Comparing books using ISBN strategy...")
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                # Fetch all existing ISBNs and normalize them
                cursor.execute("SELECT isbn FROM books WHERE isbn IS NOT NULL AND isbn != ''")
                existing_isbns = {
                    row['isbn'].replace("-", "").replace(" ", "").lower() 
                    for row in cursor.fetchall()
                }
                
                # Also fetch Name & Size map for fallback
                cursor.execute("SELECT file_name, file_size FROM books")
                existing_names = {(row['file_name'].lower(), row['file_size']) for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching existing books for ISBN strategy: {e}")
            existing_isbns = set()
            existing_names = set()
        
        new_books: List[Book] = []
        for book in books:
            try:
                meta = MetadataExtractor.extract(Path(book.file_path))
                isbn = meta.get('isbn')
                if isbn:
                    book.isbn = isbn
                    isbn_clean = isbn.replace("-", "").replace(" ", "").lower()
                    if isbn_clean not in existing_isbns:
                        new_books.append(book)
                else:
                    # Fallback to Name & Size
                    key = (book.file_name.lower(), book.file_size)
                    if key not in existing_names:
                        new_books.append(book)
            except Exception as e:
                logger.warning(f"Error extracting ISBN for {book.file_name}: {e}. Falling back to Name & Size.")
                key = (book.file_name.lower(), book.file_size)
                if key not in existing_names:
                    new_books.append(book)
                    
        logger.info(f"ISBN filter: {len(books)} scanned -> {len(new_books)} new.")
        return new_books


class AuthorTitleStrategy(ComparisonStrategy):
    """
    Compares books using Title and Author metadata.
    Falls back to Name & Size if no Title is found.
    """
    def filter_existing(self, books: List[Book]) -> List[Book]:
        logger.info("Comparing books using Title & Author strategy...")
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title, author FROM books WHERE title IS NOT NULL AND title != ''")
                existing_titles = {
                    (row['title'].strip().lower(), (row['author'] or '').strip().lower()) 
                    for row in cursor.fetchall()
                }
                
                # Fetch Name & Size map for fallback
                cursor.execute("SELECT file_name, file_size FROM books")
                existing_names = {(row['file_name'].lower(), row['file_size']) for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching existing books for Title & Author strategy: {e}")
            existing_titles = set()
            existing_names = set()
        
        new_books: List[Book] = []
        for book in books:
            try:
                meta = MetadataExtractor.extract(Path(book.file_path))
                title = meta.get('title')
                author = meta.get('author')
                if title:
                    book.title = title
                    book.author = author
                    key = (title.strip().lower(), (author or '').strip().lower())
                    if key not in existing_titles:
                        new_books.append(book)
                else:
                    # Fallback to Name & Size
                    key = (book.file_name.lower(), book.file_size)
                    if key not in existing_names:
                        new_books.append(book)
            except Exception as e:
                logger.warning(f"Error extracting metadata for {book.file_name}: {e}. Falling back to Name & Size.")
                key = (book.file_name.lower(), book.file_size)
                if key not in existing_names:
                    new_books.append(book)
                    
        logger.info(f"Title & Author filter: {len(books)} scanned -> {len(new_books)} new.")
        return new_books


class BookComparer:
    """
    Context class for executing the selected comparison strategy.
    """
    def __init__(self, strategy: ComparisonStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: ComparisonStrategy) -> None:
        """Dynamically switches the active comparison strategy."""
        self._strategy = strategy

    def get_new_books(self, source_books: List[Book]) -> List[Book]:
        """Runs the active strategy to identify new files."""
        return self._strategy.filter_existing(source_books)
