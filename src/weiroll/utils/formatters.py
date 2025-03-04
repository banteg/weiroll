"""
Utility functions for formatting values in weiroll.
"""
from typing import Any


def format_value(value: Any) -> str:
    """
    Format a value for display, applying special formatting for common types.
    
    Args:
        value: The value to format
        
    Returns:
        str: Formatted string representation
    """
    if value is None:
        return "None"
    
    if isinstance(value, str):
        # Handle common representations
        if value.startswith("0x"):
            # Likely an address or bytes
            return value
        return f'"{value}"'
    
    # Handle bytes type directly
    if isinstance(value, bytes):
        # Try to decode as utf-8 if possible
        try:
            clean_bytes = value.rstrip(b'\x00')
            decoded = clean_bytes.decode('utf-8')
            return f'"{decoded}"' if decoded else '""'
        except UnicodeDecodeError:
            # Fall back to hex representation
            return f"0x{value.hex()}"
    
    # Just use normal string representation for most types
    return str(value)


def format_contract_name(name: Any) -> str:
    """
    Format a contract name, with special handling for byte strings.
    
    Args:
        name: The contract name to format, which could be a string, bytes, or other type
        
    Returns:
        str: Properly formatted contract name
    """
    if name is None:
        return ""
    
    # Handle bytes-like objects (common for some contracts like Maker)
    if isinstance(name, bytes):
        # Try to decode the bytes as a string, stripping null bytes
        try:
            # Remove null bytes and decode as utf-8
            clean_bytes = name.rstrip(b'\x00')
            return clean_bytes.decode('utf-8')
        except UnicodeDecodeError:
            # If decoding fails, return a hex representation
            return f"0x{name.hex()}"
    
    # Handle strings
    if isinstance(name, str):
        # Handle binary data that's already been stringified with null characters
        if '\\x00' in name or '\x00' in name:
            return name.rstrip('\x00')
        return name
    
    # For other types, just use string representation
    return str(name)
