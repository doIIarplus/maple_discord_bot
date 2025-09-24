"""Text processing utilities for the Discord bot."""
import re
from typing import List


def split_by_newlines(content: str, max_length: int = 2000) -> List[str]:
    """
    Split content into chunks by newlines to stay under Discord's message limits.
    
    Args:
        content: Text to split
        max_length: Maximum length per chunk
        
    Returns:
        List of text chunks
    """
    if len(content) <= max_length:
        return [content]
    
    chunks = []
    current_chunk = ""
    
    for line in content.split('\n'):
        if len(current_chunk) + len(line) + 1 <= max_length:
            if current_chunk:
                current_chunk += '\n' + line
            else:
                current_chunk = line
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def remove_spaces_and_adjacent_repeats(text: str) -> str:
    """
    Remove extra spaces and adjacent repeated characters.
    
    Args:
        text: Input text to clean
        
    Returns:
        Cleaned text
    """
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove adjacent repeated characters (but keep intentional repeats like "...")
    # This is a simplified version - may need adjustment based on specific requirements
    text = re.sub(r'(.)\1{3,}', r'\1\1\1', text)
    
    return text.strip()


def process_response(text: str, max_length: int = 1900) -> List[str]:
    """
    Process a response text to fit Discord's message limits.
    
    Args:
        text: Response text to process
        max_length: Maximum length per message chunk
        
    Returns:
        List of processed text chunks
    """
    # Clean the text first
    cleaned_text = remove_spaces_and_adjacent_repeats(text)
    
    # Split into chunks
    return split_by_newlines(cleaned_text, max_length)