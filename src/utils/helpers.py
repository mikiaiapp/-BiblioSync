"""
Helper utilities for BiblioSync.
Includes path manipulation, formatting, and file resolution helpers.
"""

from pathlib import Path

def get_unique_path(directory: Path, filename: str) -> Path:
    """
    Appends a counter suffix (e.g., ' (1)', ' (2)') to a filename if a file
    with the same name already exists in the destination directory.
    
    Example:
        get_unique_path('/dest', 'Libro.epub') 
        -> returns '/dest/Libro.epub' if it doesn't exist
        -> returns '/dest/Libro (1).epub' if '/dest/Libro.epub' already exists
    """
    path = Path(directory) / filename
    if not path.exists():
        return path
        
    stem = path.stem
    suffix = path.suffix
    counter = 1
    
    while True:
        new_filename = f"{stem} ({counter}){suffix}"
        new_path = Path(directory) / new_filename
        if not new_path.exists():
            return new_path
        counter += 1

def format_size(bytes_size: int) -> str:
    """Formats an integer size in bytes into a human-readable string (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"
