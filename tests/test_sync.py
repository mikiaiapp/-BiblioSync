"""
Automated unit tests for BiblioSync core functionalities.
Verifies library indexing, scanning, comparison strategies, copying, collision renaming, and reporting.
"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, Any

from src.database.database import db_manager
from src.database.models import Book
from src.core.indexer import LibraryIndexer
from src.core.scanner import LibraryScanner
from src.core.comparer import BookComparer, NameSizeStrategy, SHA256Strategy, ISBNStrategy, AuthorTitleStrategy
from src.core.copier import FileCopier
from src.export.excel_export import generate_excel_report
from src.export.csv_export import generate_csv_report

class TestBiblioSync(unittest.TestCase):
    def setUp(self):
        # Create temp directory for test files
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Paths for mock components
        self.calibre_dir = self.test_dir / "calibre_library"
        self.source_dir = self.test_dir / "source_folders"
        self.dest_dir = self.test_dir / "destination"
        
        self.calibre_dir.mkdir()
        self.source_dir.mkdir()
        self.dest_dir.mkdir()
        
        # Override database path to use a test database
        self.test_db_path = self.test_dir / "test_bibliosync.db"
        db_manager.db_path = self.test_db_path
        db_manager.initialize_db()
        
        # Create mock ebook files in Calibre Library
        self._create_dummy_file(self.calibre_dir / "Author, A" / "Book 1 (100).epub", "Content of book 1")
        self._create_dummy_file(self.calibre_dir / "Author, B" / "Book 2 (101).pdf", "Content of book 2")
        
    def tearDown(self):
        # Remove all temp directories and database
        shutil.rmtree(self.test_dir, ignore_errors=True)
        # Reset database manager path
        db_manager.db_path = Path("bibliosync.db")

    def _create_dummy_file(self, file_path: Path, content: str):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_indexing(self):
        indexer = LibraryIndexer(str(self.calibre_dir))
        
        # Initial sync
        added, modified, deleted = indexer.sync_index()
        self.assertEqual(added, 2)
        self.assertEqual(modified, 0)
        self.assertEqual(deleted, 0)
        
        # Verify db entries
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM books")
            self.assertEqual(cursor.fetchone()[0], 2)
            
            # Check properties
            cursor.execute("SELECT file_name, format FROM books ORDER BY file_name")
            rows = cursor.fetchall()
            self.assertEqual(rows[0]['file_name'], "Book 1 (100).epub")
            self.assertEqual(rows[0]['format'], "epub")
            self.assertEqual(rows[1]['file_name'], "Book 2 (101).pdf")
            self.assertEqual(rows[1]['format'], "pdf")

        # Create a modified file
        self._create_dummy_file(self.calibre_dir / "Author, A" / "Book 1 (100).epub", "Content of book 1 - changed")
        # Touch modification time
        os.utime(self.calibre_dir / "Author, A" / "Book 1 (100).epub", (100000, 200000))
        
        # Second sync
        added, modified, deleted = indexer.sync_index()
        self.assertEqual(added, 0)
        self.assertEqual(modified, 1)
        self.assertEqual(deleted, 0)

        # Delete a file on disk
        os.remove(self.calibre_dir / "Author, B" / "Book 2 (101).pdf")
        
        # Third sync
        added, modified, deleted = indexer.sync_index()
        self.assertEqual(added, 0)
        self.assertEqual(modified, 0)
        self.assertEqual(deleted, 1)

    def test_scanner_and_name_size_comparison(self):
        # 1. Index calibre
        indexer = LibraryIndexer(str(self.calibre_dir))
        indexer.sync_index()
        
        # 2. Add books to source folders (one duplicate, one new)
        self._create_dummy_file(self.source_dir / "Folder A" / "Book 1 (100).epub", "Content of book 1") # duplicate (name and size match)
        self._create_dummy_file(self.source_dir / "Folder B" / "New Book (200).epub", "Content of new book") # new book
        self._create_dummy_file(self.source_dir / "Folder B" / "ignored.txt", "Ignored txt file") # ignored format
        
        # 3. Scan source folders
        scanner = LibraryScanner([str(self.source_dir)])
        scanned_books = scanner.scan()
        
        # We expect only .epub files (no txt)
        self.assertEqual(len(scanned_books), 2)
        scanned_names = {b.file_name for b in scanned_books}
        self.assertIn("Book 1 (100).epub", scanned_names)
        self.assertIn("New Book (200).epub", scanned_names)
        
        # 4. Compare using Name & Size strategy
        comparer = BookComparer(NameSizeStrategy())
        new_books = comparer.get_new_books(scanned_books)
        
        # "Book 1 (100).epub" exists in calibre DB with same size, so only "New Book (200).epub" is new
        self.assertEqual(len(new_books), 1)
        self.assertEqual(new_books[0].file_name, "New Book (200).epub")

    def test_copier_and_renaming_collision(self):
        # Create books to copy
        book1 = Book(
            file_name="Book 1.epub",
            file_path=str(self.source_dir / "Book 1.epub"),
            file_size=100,
            format="epub",
            mtime=12345.0
        )
        self._create_dummy_file(Path(book1.file_path), "Ebook Content")
        
        # Pre-create a file with the same name in destination
        self._create_dummy_file(self.dest_dir / "Book 1.epub", "Existing file")
        
        # Copy
        copier = FileCopier(str(self.dest_dir))
        copied, failed = copier.copy_books([book1])
        
        self.assertEqual(len(copied), 1)
        self.assertEqual(len(failed), 0)
        
        # It should rename the file using collision renaming
        copied_book_obj, copied_path_str = copied[0]
        copied_path = Path(copied_path_str)
        self.assertEqual(copied_path.name, "Book 1 (1).epub")
        self.assertTrue(copied_path.exists())

    def test_exporters(self):
        # Create mock data
        book = Book(
            file_name="Test Book.epub",
            file_path=str(self.source_dir / "Test Book.epub"),
            file_size=1024,
            format="epub",
            mtime=54321.0
        )
        copied = [(book, str(self.dest_dir / "Test Book.epub"))]
        failed = [(book, "Mock Error Message")]
        summary = {
            "Fecha": "2026-08-07 10:00:00",
            "Metodo": "Name & Size",
            "Copied": 1,
            "Errors": 1,
            "Total Size": "1.00 KB"
        }
        
        # Excel
        excel_path = self.dest_dir / "report.xlsx"
        generate_excel_report(excel_path, copied, failed, summary)
        self.assertTrue(excel_path.exists())
        
        # CSV
        csv_dir = self.dest_dir / "csv_reports"
        generate_csv_report(csv_dir, copied, failed, summary)
        self.assertTrue((csv_dir / "copied_books.csv").exists())
        self.assertTrue((csv_dir / "errors.csv").exists())
        self.assertTrue((csv_dir / "summary.csv").exists())

if __name__ == "__main__":
    unittest.main()
