"""Integration modules for external services."""
from .db import MapleDatabase, get_database
from .culvert_reader import send_request, parse_results
from .latex_utils import split_text_and_latex

# Backward compatibility aliases
Database = MapleDatabase
Sheet = MapleDatabase  # For smooth transition

__all__ = [
    'MapleDatabase',
    'Database', 
    'Sheet',  # Backward compatibility
    'get_database',
    'send_request',
    'parse_results', 
    'split_text_and_latex'
]