"""
Settings module for BiblioSync.
Manages loading, updating, and saving application configurations.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List
from src.utils.logger import logger

# Config path selection based on environment
if os.path.exists("/data"):
    SETTINGS_PATH = Path("/data/settings.json")
else:
    SETTINGS_PATH = Path("settings.json")

@dataclass
class AppSettings:
    """
    Holds and manages the user configurations.
    Automatically persists to a JSON file.
    """
    main_library_path: str = ""
    scan_folders: List[str] = field(default_factory=list)
    destination_folder: str = ""
    last_comparison_method: str = "Name & Size"
    last_metadata_db_mtime: float = 0.0
    last_metadata_db_size: int = 0

    def load(self) -> None:
        """Loads configuration from JSON file."""
        if not SETTINGS_PATH.exists():
            logger.info("Configuration file does not exist. Creating default configurations.")
            self.save()
            return
            
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.main_library_path = data.get("main_library_path", "")
                # Ensure we got a list and not something else
                scan_paths = data.get("scan_folders", [])
                self.scan_folders = list(scan_paths) if isinstance(scan_paths, list) else []
                self.destination_folder = data.get("destination_folder", "")
                self.last_comparison_method = data.get("last_comparison_method", "Name & Size")
                self.last_metadata_db_mtime = float(data.get("last_metadata_db_mtime", 0.0))
                self.last_metadata_db_size = int(data.get("last_metadata_db_size", 0))
            logger.info(f"Loaded configurations from {SETTINGS_PATH}")
        except Exception as e:
            logger.error(f"Failed to load configurations from {SETTINGS_PATH}: {e}")

    def save(self) -> None:
        """Saves current configurations to JSON file."""
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=4, ensure_ascii=False)
            logger.info(f"Saved configurations to {SETTINGS_PATH}")
        except Exception as e:
            logger.error(f"Failed to save configurations to {SETTINGS_PATH}: {e}")

# Global settings instance
settings = AppSettings()
