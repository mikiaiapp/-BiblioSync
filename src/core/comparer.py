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


def load_all_existing_books() -> List[Book]:
    """Queries all books from the local SQLite database."""
    books = []
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_name, file_path, file_size, format, mtime, sha256, title, author, isbn FROM books")
            for row in cursor.fetchall():
                books.append(Book(
                    file_name=row['file_name'],
                    file_path=row['file_path'],
                    file_size=row['file_size'],
                    format=row['format'],
                    mtime=row['mtime'],
                    sha256=row['sha256'],
                    title=row['title'],
                    author=row['author'],
                    isbn=row['isbn']
                ))
    except Exception as e:
        logger.error(f"Error loading existing books for comparison: {e}")
    return books


def is_exact_match(scanned: Book, existing: Book) -> bool:
    """
    Compares two Book objects on key data fields to determine if they match exactly.
    """
    # 1. Compare sizes
    if scanned.file_size != existing.file_size:
        return False
    # 2. Compare formats
    if scanned.format.lower() != existing.format.lower():
        return False
    # 3. Compare ISBNs
    scanned_isbn = (scanned.isbn or "").replace("-", "").replace(" ", "").lower()
    existing_isbn = (existing.isbn or "").replace("-", "").replace(" ", "").lower()
    if scanned_isbn != existing_isbn:
        return False
    # 4. Compare Title and Author
    s_title = normalize_title(scanned.title or parse_filename_meta(scanned.file_name)[0])
    e_title = normalize_title(existing.title or parse_filename_meta(existing.file_name)[0])
    if s_title != e_title:
        return False
        
    s_author = normalize_author(scanned.author or parse_filename_meta(scanned.file_name)[1])
    e_author = normalize_author(existing.author or parse_filename_meta(existing.file_name)[1])
    if s_author != e_author:
        return False
        
    return True


class ComparisonStrategy(ABC):
    """
    Abstract Base Class for all comparison strategies.
    Determines whether scanned books already exist in the database index.
    """
    def filter_existing(self, books: List[Book]) -> List[Book]:
        """
        Filters a list of books, returning only those that do NOT exist in the library.
        
        Args:
            books (List[Book]): List of scanned books to evaluate.
            
        Returns:
            List[Book]: Books that are new and need to be copied.
        """
        new_books, _ = self.compare_books(books)
        return new_books

    @abstractmethod
    def compare_books(self, books: List[Book]) -> tuple[List[Book], List[tuple[Book, Book]]]:
        """
        Compares books against the library database.
        
        Returns:
            Tuple[List[Book], List[Tuple[Book, Book]]]:
                - List of new books to be copied.
                - List of tuples (scanned_book, matching_existing_book) representing duplicates.
        """
        pass


class NameSizeStrategy(ComparisonStrategy):
    """
    Compares books using their Filename and File Size.
    This is the default, fast comparison method.
    """
    def compare_books(self, books: List[Book]) -> tuple[List[Book], List[tuple[Book, Book]]]:
        logger.info("Comparing books using Name & Size strategy...")
        db_books = load_all_existing_books()
        existing_map = {(b.file_name.lower(), b.file_size): b for b in db_books}
        
        new_books: List[Book] = []
        duplicates: List[tuple[Book, Book]] = []
        
        for book in books:
            key = (book.file_name.lower(), book.file_size)
            if key in existing_map:
                duplicates.append((book, existing_map[key]))
            else:
                new_books.append(book)
        logger.info(f"Name & Size filter: {len(books)} scanned -> {len(new_books)} new, {len(duplicates)} duplicates.")
        return new_books, duplicates


class NameOnlyStrategy(ComparisonStrategy):
    """
    Compares books using only their Filename (case-insensitive).
    Ignores file size, which might change when Calibre updates internal metadata.
    """
    def compare_books(self, books: List[Book]) -> tuple[List[Book], List[tuple[Book, Book]]]:
        logger.info("Comparing books using Name Only strategy...")
        db_books = load_all_existing_books()
        existing_map = {b.file_name.lower(): b for b in db_books}
        
        new_books: List[Book] = []
        duplicates: List[tuple[Book, Book]] = []
        
        for book in books:
            key = book.file_name.lower()
            if key in existing_map:
                duplicates.append((book, existing_map[key]))
            else:
                new_books.append(book)
        logger.info(f"Name Only filter: {len(books)} scanned -> {len(new_books)} new, {len(duplicates)} duplicates.")
        return new_books, duplicates


class SHA256Strategy(ComparisonStrategy):
    """
    Compares books using the SHA256 hash of their content.
    Highly accurate but slower due to hashing scanned files on the fly.
    """
    def compare_books(self, books: List[Book]) -> tuple[List[Book], List[tuple[Book, Book]]]:
        logger.info("Comparing books using SHA256 Hash strategy...")
        db_books = load_all_existing_books()
        existing_map = {b.sha256: b for b in db_books if b.sha256}
        
        new_books: List[Book] = []
        duplicates: List[tuple[Book, Book]] = []
        
        for book in books:
            try:
                # Calculate hash for scanned book on the fly
                sha = calculate_sha256(Path(book.file_path))
                book.sha256 = sha
                if sha in existing_map:
                    duplicates.append((book, existing_map[sha]))
                else:
                    new_books.append(book)
            except Exception as e:
                logger.warning(f"Could not calculate SHA256 for {book.file_name}: {e}. Treating as new.")
                new_books.append(book)
        logger.info(f"SHA256 Hash filter: {len(books)} scanned -> {len(new_books)} new, {len(duplicates)} duplicates.")
        return new_books, duplicates


class ISBNStrategy(ComparisonStrategy):
    """
    Compares books using their extracted ISBN.
    Falls back to Name & Size if no ISBN is found.
    """
    def compare_books(self, books: List[Book]) -> tuple[List[Book], List[tuple[Book, Book]]]:
        logger.info("Comparing books using ISBN strategy...")
        db_books = load_all_existing_books()
        
        isbn_map = {}
        for b in db_books:
            if b.isbn:
                clean = b.isbn.replace("-", "").replace(" ", "").lower()
                if clean:
                    isbn_map[clean] = b
                    
        name_size_map = {(b.file_name.lower(), b.file_size): b for b in db_books}
        
        new_books: List[Book] = []
        duplicates: List[tuple[Book, Book]] = []
        
        for book in books:
            try:
                meta = MetadataExtractor.extract(Path(book.file_path))
                isbn = meta.get('isbn')
                matched = None
                
                if isbn:
                    book.isbn = isbn
                    isbn_clean = isbn.replace("-", "").replace(" ", "").lower()
                    if isbn_clean in isbn_map:
                        matched = isbn_map[isbn_clean]
                
                if not matched:
                    # Fallback to Name & Size
                    key = (book.file_name.lower(), book.file_size)
                    if key in name_size_map:
                        matched = name_size_map[key]
                        
                if matched:
                    duplicates.append((book, matched))
                else:
                    new_books.append(book)
            except Exception as e:
                logger.warning(f"Error extracting ISBN for {book.file_name}: {e}. Falling back to Name & Size.")
                key = (book.file_name.lower(), book.file_size)
                if key in name_size_map:
                    duplicates.append((book, name_size_map[key]))
                else:
                    new_books.append(book)
                    
        logger.info(f"ISBN filter: {len(books)} scanned -> {len(new_books)} new, {len(duplicates)} duplicates.")
        return new_books, duplicates


class AuthorTitleStrategy(ComparisonStrategy):
    """
    Compares books using Title and Author metadata.
    Falls back to Name Only if no Title metadata is found.
    """
    def compare_books(self, books: List[Book]) -> tuple[List[Book], List[tuple[Book, Book]]]:
        logger.info("Comparing books using Title & Author strategy...")
        db_books = load_all_existing_books()
        
        title_author_map = {}
        for b in db_books:
            if b.title:
                key = (normalize_title(b.title), normalize_author(b.author))
                title_author_map[key] = b
                
        name_only_map = {b.file_name.lower(): b for b in db_books}
        
        new_books: List[Book] = []
        duplicates: List[tuple[Book, Book]] = []
        
        for book in books:
            matched = None
            try:
                # 1. Fast path: try parsing title & author from filename
                part1, part2 = parse_filename_meta(book.file_name)
                
                # Extract potential author name from parent directory name
                author_from_path = ""
                file_path = Path(book.file_path)
                if file_path.parent and file_path.parent.name not in ("", ".", ".."):
                    parent_name = file_path.parent.name
                    generic_names = {
                        "descargas", "downloads", "documentos", "documents", "desktop", 
                        "libros a analizar", "libros", "importar", "source_folders", 
                        "destination", "calibreweb", "biblioteca", "tmp", "temp", "books"
                    }
                    if parent_name.lower() not in generic_names:
                        author_from_path = parent_name
                
                if part2:  # If we successfully parsed an author part
                    t_norm1 = normalize_title(part1)
                    a_norm1 = normalize_author(part2)
                    t_norm2 = normalize_title(part2)
                    a_norm2 = normalize_author(part1)
                    
                    if (t_norm1, a_norm1) in title_author_map:
                        matched = title_author_map[(t_norm1, a_norm1)]
                        book.title = part1
                        book.author = part2
                    elif (t_norm2, a_norm2) in title_author_map:
                        matched = title_author_map[(t_norm2, a_norm2)]
                        book.title = part2
                        book.author = part1
                
                if not matched:
                    # 2. Slow path: extract metadata from the physical file
                    meta = MetadataExtractor.extract(file_path)
                    title = meta.get('title')
                    author = meta.get('author')
                    
                    # Fallback to filename as title if metadata title is empty
                    if not title:
                        title = part1
                    
                    if title:
                        book.title = title
                        t_norm = normalize_title(title)
                        
                        # Try matching with metadata author
                        if author:
                            book.author = author
                            a_norm = normalize_author(author)
                            if (t_norm, a_norm) in title_author_map:
                                matched = title_author_map[(t_norm, a_norm)]
                        
                        # Try matching with author from parent folder if not matched yet
                        if not matched and author_from_path:
                            a_norm_path = normalize_author(author_from_path)
                            if (t_norm, a_norm_path) in title_author_map:
                                matched = title_author_map[(t_norm, a_norm_path)]
                                # Update book author if it was empty/unknown
                                if not book.author or book.author.lower() in ("unknown", "desconocido"):
                                    book.author = author_from_path
                            
                if not matched:
                    # 3. Fallback path: Name Only (case-insensitive filename comparison)
                    key = book.file_name.lower()
                    if key in name_only_map:
                        matched = name_only_map[key]
                        
                if matched:
                    duplicates.append((book, matched))
                else:
                    new_books.append(book)
            except Exception as e:
                logger.warning(f"Error extracting metadata for {book.file_name}: {e}. Falling back to Name Only.")
                key = book.file_name.lower()
                if key in name_only_map:
                    duplicates.append((book, name_only_map[key]))
                else:
                    new_books.append(book)
                    
        logger.info(f"Title & Author filter: {len(books)} scanned -> {len(new_books)} new, {len(duplicates)} duplicates.")
        return new_books, duplicates


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

    def compare_books(self, source_books: List[Book]) -> tuple[List[Book], List[tuple[Book, Book]]]:
        """Runs the active strategy returning both new books and duplicates."""
        return self._strategy.compare_books(source_books)

