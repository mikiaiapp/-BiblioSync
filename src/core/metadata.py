"""
Metadata extraction module for BiblioSync.
Extracts title, author, and ISBN information from ebook files (EPUB, PDF, etc.).
"""

import warnings
from pathlib import Path
from typing import Dict, Optional

# Suppress ebooklib / BeautifulSoup warnings about HTML parsing
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

from src.utils.logger import logger

# Import ebooklib and pypdf inside try blocks to handle import issues gracefully
try:
    from ebooklib import epub
except ImportError:
    epub = None
    logger.warning("ebooklib is not installed, EPUB metadata extraction will be disabled.")

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None
    logger.warning("pypdf is not installed, PDF metadata extraction will be disabled.")


class MetadataExtractor:
    """
    Service class to extract ebook metadata based on file extension.
    """
    @staticmethod
    def extract(file_path: Path) -> Dict[str, Optional[str]]:
        """
        Dispatches metadata extraction based on the file format.
        
        Returns:
            Dict containing 'title', 'author', and 'isbn'.
        """
        suffix = file_path.suffix.lower()
        result = {'title': None, 'author': None, 'isbn': None}
        
        if not file_path.exists():
            return result
            
        try:
            if suffix == '.epub' and epub:
                return MetadataExtractor._extract_epub(file_path)
            elif suffix == '.pdf' and PdfReader:
                return MetadataExtractor._extract_pdf(file_path)
        except Exception as e:
            logger.debug(f"Failed to extract metadata for {file_path.name}: {e}")
            
        return result

    @staticmethod
    def _extract_epub(file_path: Path) -> Dict[str, Optional[str]]:
        """Extracts metadata from EPUB using ebooklib."""
        result = {'title': None, 'author': None, 'isbn': None}
        try:
            # read_epub can raise standard exceptions on corrupt files
            book = epub.read_epub(str(file_path), read_geometry=False)
            
            # Title
            titles = book.get_metadata('DC', 'title')
            if titles:
                title_val = titles[0][0]
                if isinstance(title_val, bytes):
                    title_val = title_val.decode('utf-8', errors='ignore')
                result['title'] = str(title_val).strip()

            # Author (Creator)
            creators = book.get_metadata('DC', 'creator')
            if creators:
                author_val = creators[0][0]
                if isinstance(author_val, bytes):
                    author_val = author_val.decode('utf-8', errors='ignore')
                result['author'] = str(author_val).strip()

            # ISBN (from DC identifier)
            identifiers = book.get_metadata('DC', 'identifier')
            for ident in identifiers:
                val = ident[0]
                if isinstance(val, bytes):
                    val = val.decode('utf-8', errors='ignore')
                val_clean = str(val).replace("-", "").replace(" ", "").lower()
                
                # Check for standard ISBN shapes: 10/13 digits, or starts with 978, or explicitly includes 'isbn'
                if "isbn" in val_clean or val_clean.startswith("978") or (val_clean.isdigit() and len(val_clean) in (10, 13)):
                    # Clean the ISBN label part if it's like 'isbn:1234567890'
                    if ":" in val:
                        val = val.split(":", 1)[1]
                    result['isbn'] = str(val).strip()
                    break
        except Exception as e:
            logger.debug(f"Epub extractor error on {file_path.name}: {e}")
            
        return result

    @staticmethod
    def _extract_pdf(file_path: Path) -> Dict[str, Optional[str]]:
        """Extracts metadata from PDF using pypdf."""
        result = {'title': None, 'author': None, 'isbn': None}
        try:
            reader = PdfReader(str(file_path))
            meta = reader.metadata
            if meta:
                if meta.title:
                    result['title'] = str(meta.title).strip()
                if meta.author:
                    result['author'] = str(meta.author).strip()
        except Exception as e:
            logger.debug(f"PDF extractor error on {file_path.name}: {e}")
            
        return result
