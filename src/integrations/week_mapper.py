"""Week mapping utilities for converting between column numbers and week dates."""

from datetime import datetime, timedelta
from typing import Dict, Optional


class WeekMapper:
    """Maps between column numbers and week date strings."""
    
    def __init__(self):
        self._column_to_week: Dict[int, str] = {}
        self._week_to_column: Dict[str, int] = {}
        self._next_column = 4  # Start at column 4 (after username, discord_username, discord_id)
    
    def get_column_for_week(self, week_date: str) -> Optional[int]:
        """Get the column number for a given week date."""
        if week_date not in self._week_to_column:
            return None
        return self._week_to_column[week_date]
    
    def get_week_for_column(self, column: int) -> Optional[str]:
        """Get the week date for a given column number."""
        if column not in self._column_to_week:
            return None
        return self._column_to_week[column]
    
    def add_week(self, week_date: str) -> int:
        """Add a new week and return its column number."""
        if week_date in self._week_to_column:
            return self._week_to_column[week_date]
        
        column = self._next_column
        self._column_to_week[column] = week_date
        self._week_to_column[week_date] = column
        self._next_column += 1
        return column
    
    def get_all_weeks(self) -> Dict[str, int]:
        """Get all week mappings."""
        return self._week_to_column.copy()


# Global week mapper instance
_week_mapper = WeekMapper()


def get_week_mapper() -> WeekMapper:
    """Get the global week mapper instance."""
    return _week_mapper


def column_to_week_date(column: int) -> str:
    """Convert column number to week date string (simplified)."""
    week_mapper = get_week_mapper()
    week = week_mapper.get_week_for_column(column)
    if week:
        return week
    
    # Fallback: generate week date based on column offset
    # This is a simplified approach - in practice you'd want better logic
    base_date = datetime(2024, 1, 1)  # Start of year
    week_offset = column - 4
    week_start = base_date + timedelta(weeks=week_offset)
    return week_start.strftime("%m/%d/%Y")


def week_date_to_column(week_date: str) -> int:
    """Convert week date string to column number."""
    week_mapper = get_week_mapper()
    column = week_mapper.get_column_for_week(week_date)
    if column:
        return column
    
    # If not found, add it
    return week_mapper.add_week(week_date)