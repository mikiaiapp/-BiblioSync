"""
Hashing module for BiblioSync.
Calculates file hashes (SHA256) for unique content comparison.
"""

from pathlib import Path
import hashlib
from src.utils.logger import logger

def calculate_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """
    Computes the SHA256 hash of a file in a memory-efficient way by reading
    it in chunks.
    
    Args:
        file_path (Path): Path to the file.
        chunk_size (int): Size of chunks to read into memory. Defaults to 64KB.
        
    Returns:
        str: Hexadecimal string representing the hash.
    """
    logger.debug(f"Calculating SHA256 for {file_path.name}")
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate SHA256 hash for {file_path}: {e}")
        raise e
