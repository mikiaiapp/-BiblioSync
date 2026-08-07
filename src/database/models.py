"""
Data models for BiblioSync.
Defines Python dataclasses mapped to the SQLite database schema.
"""

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Book:
    """
    Represents a book file indexed from Calibre or scanned from sources.
    """
    file_name: str
    file_path: str
    file_size: int
    format: str
    mtime: float
    id: Optional[int] = None
    sha256: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    isbn: Optional[str] = None

@dataclass
class SyncRecord:
    """
    Represents a log of a synchronization process.
    """
    timestamp: str
    files_copied: int
    errors_encountered: int
    summary: str
    id: Optional[int] = None
