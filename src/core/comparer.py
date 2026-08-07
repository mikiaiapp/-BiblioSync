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
import unicodedata

def normalize_title(title: str) -> str:
    """Normalizes book title for comparison: lowercase, alphanumeric characters only."""
    if not title:
        return ""
    title_normalized = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('utf-8')
    words = "".join(c if c.isalnum() else " " for c in title_normalized.lower()).split()
    return " ".join(words)

def normalize_author(author: str) -> str:
    """Normalizes author name for comparison: lowercase, sorted words, alphanumeric characters only."""
    if not author:
        return ""
    author_normalized = unicodedata.normalize('NFKD', author).encode('ASCII', 'ignore').decode('utf-8')
    words = "".join(c if c.isalnum() else " " for c in author_normalized.lower()).split()
    # Sort alphabetically to treat "Lastname, Firstname" and "Firstname Lastname" as identical
    words.sort()
    return " ".join(words)

def parse_filename_meta(filename: str) -> tuple[str, str]:
    """Tries to extract title and author from filename using common separators (e.g. Title - Author)."""
    # Strip extension
    name_without_ext = Path(filename).stem
    # Separators typically used: " - ", " – " (en dash), " — " (em dash), " -", "- "
    for sep in [" - ", " – ", " — ", " -", "- "]:
        if sep in name_without_ext:
            parts = name_without_ext.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return name_without_ext.strip(), ""


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


class NameOnlyStrategy(ComparisonStrategy):
    """
    Compares books using only their Filename (case-insensitive).
    Ignores file size, which might change when Calibre updates internal metadata.
    """
    def filter_existing(self, books: List[Book]) -> List[Book]:
        logger.info("Comparing books using Name Only strategy...")
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT file_name FROM books")
                existing = {row['file_name'].lower() for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching existing books for Name Only strategy: {e}")
            existing = set()
        
        new_books: List[Book] = []
        for book in books:
            key = book.file_name.lower()
            if key not in existing:
                new_books.append(book)
        logger.info(f"Name Only filter: {len(books)} scanned -> {len(new_books)} new.")
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
    Falls back to Name Only if no Title metadata is found.
    """
    def filter_existing(self, books: List[Book]) -> List[Book]:
        logger.info("Comparing books using Title & Author strategy...")
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title, author FROM books WHERE title IS NOT NULL AND title != ''")
                existing_titles = {
                    (normalize_title(row['title']), normalize_author(row['author'])) 
                    for row in cursor.fetchall()
                }
                
                # Fetch Name Only set for fallback
                cursor.execute("SELECT file_name FROM books")
                existing_names = {row['file_name'].lower() for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching existing books for Title & Author strategy: {e}")
            existing_titles = set()
            existing_names = set()
        
        new_books: List[Book] = []
        for book in books:
            try:
                # 1. Fast path: try parsing title & author from filename
                part1, part2 = parse_filename_meta(book.file_name)
                if part2:  # If we successfully parsed an author part
                    t_norm1 = normalize_title(part1)
                    a_norm1 = normalize_author(part2)
                    t_norm2 = normalize_title(part2)
                    a_norm2 = normalize_author(part1)
                    
                    if (t_norm1, a_norm1) in existing_titles or (t_norm2, a_norm2) in existing_titles:
                        continue  # Match found! Skip.
                
                # 2. Slow path: extract metadata from the physical file
                meta = MetadataExtractor.extract(Path(book.file_path))
                title = meta.get('title')
                author = meta.get('author')
                if title:
                    book.title = title
                    book.author = author
                    t_norm = normalize_title(title)
                    a_norm = normalize_author(author)
                    if (t_norm, a_norm) in existing_titles:
                        continue
                    else:
                        new_books.append(book)
                else:
                    # 3. Fallback path: Name Only (case-insensitive filename comparison)
                    if book.file_name.lower() not in existing_names:
                        new_books.append(book)
            except Exception as e:
                logger.warning(f"Error extracting metadata for {book.file_name}: {e}. Falling back to Name Only.")
                if book.file_name.lower() not in existing_names:
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
