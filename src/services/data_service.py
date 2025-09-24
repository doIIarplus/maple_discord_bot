"""Data persistence service for JSON files."""

import json
import os
from typing import Any, Dict, List, Optional
import logging

from core.config import COLORS_FILE, MACROS_FILE, QUOTES_FILE, HEXA_USER_DATA_FILE


class DataService:
    """Service for handling JSON data persistence."""

    @staticmethod
    def load_json_file(file_path: str, default: Any = None) -> Any:
        """
        Load data from a JSON file.

        Args:
            file_path: Path to the JSON file
            default: Default value if file doesn't exist or is invalid

        Returns:
            Loaded data or default value
        """
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                logging.warning(f"File {file_path} does not exist, using default value")
                return default if default is not None else {}
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Error loading {file_path}: {e}")
            return default if default is not None else {}

    @staticmethod
    def save_json_file(file_path: str, data: Any) -> bool:
        """
        Save data to a JSON file.

        Args:
            file_path: Path to the JSON file
            data: Data to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except (IOError, TypeError) as e:
            logging.error(f"Error saving {file_path}: {e}")
            return False

    @classmethod
    def get_colors_for_user(cls, user_id: str) -> Dict[str, str]:
        """Get color preferences for a user."""
        colors_data = cls.load_json_file(COLORS_FILE, {})
        return colors_data.get(str(user_id), {})

    @classmethod
    def save_colors_for_user(cls, user_id: str, colors: Dict[str, str]) -> bool:
        """Save color preferences for a user."""
        colors_data = cls.load_json_file(COLORS_FILE, {})
        colors_data[str(user_id)] = colors
        return cls.save_json_file(COLORS_FILE, colors_data)

    @classmethod
    def get_quotes(cls) -> List[str]:
        """Get all quotes."""
        quotes_data = cls.load_json_file(QUOTES_FILE, [])
        return quotes_data if isinstance(quotes_data, list) else []

    @classmethod
    def add_quote(cls, quote: str) -> bool:
        """Add a new quote."""
        quotes = cls.get_quotes()
        quotes.append(quote)
        return cls.save_json_file(QUOTES_FILE, quotes)

    @classmethod
    def get_macros(cls) -> Dict[str, str]:
        """Get all macros."""
        return cls.load_json_file(MACROS_FILE, {})

    @classmethod
    def save_macros(cls, macros: Dict[str, str]) -> bool:
        """Save macros data."""
        return cls.save_json_file(MACROS_FILE, macros)

    @classmethod
    def get_hexa_user_data(cls) -> Dict[str, Any]:
        """Get hexa user data."""
        return cls.load_json_file(HEXA_USER_DATA_FILE, {})

    @classmethod
    def save_hexa_user_data(cls, data: Dict[str, Any]) -> bool:
        """Save hexa user data."""
        return cls.save_json_file(HEXA_USER_DATA_FILE, data)
