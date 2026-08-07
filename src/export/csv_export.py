"""
CSV report generation module for BiblioSync.
Generates structured CSV files for easy ingestion of synchronization results.
"""

from pathlib import Path
from typing import List, Tuple, Dict, Any
import csv
from src.database.models import Book
from src.utils.logger import logger

def generate_csv_report(
    output_dir: Path,
    copied_books: List[Tuple[Book, str]],
    failed_books: List[Tuple[Book, str]],
    summary_data: Dict[str, Any]
) -> None:
    """
    Creates multiple CSV files in the target directory mapping to the reports:
    - copied_books.csv
    - errors.csv
    - summary.csv
    
    Args:
        output_dir (Path): Folder where CSV files will be stored.
        copied_books: List of tuples (Book, destination_path)
        failed_books: List of tuples (Book, error_message)
        summary_data: Dict containing execution summary metrics.
    """
    logger.info(f"Generating CSV reports in {output_dir}...")
    
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Copied books CSV
        copied_path = output_dir / "copied_books.csv"
        with open(copied_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Nombre Original", "Carpeta de Origen", "Carpeta de Destino", "Nombre Final", "Tamaño"])
            for book, dest_path_str in copied_books:
                dest_path = Path(dest_path_str)
                writer.writerow([
                    book.file_name,
                    str(Path(book.file_path).parent),
                    str(dest_path.parent),
                    dest_path.name,
                    book.file_size
                ])
            
        # 2. Errors CSV
        errors_path = output_dir / "errors.csv"
        with open(errors_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Nombre del Archivo", "Carpeta de Origen", "Mensaje de Error"])
            for book, err_msg in failed_books:
                writer.writerow([
                    book.file_name,
                    str(Path(book.file_path).parent),
                    err_msg
                ])
            
        # 3. Summary CSV
        summary_path = output_dir / "summary.csv"
        with open(summary_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Métrica", "Valor"])
            for key, val in summary_data.items():
                writer.writerow([key, val])
                
        logger.info("CSV reports saved successfully.")
    except Exception as e:
        logger.error(f"Failed to generate CSV reports: {e}")
        raise e
