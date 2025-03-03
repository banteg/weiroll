"""
Terminal color utilities for weiroll output formatting.

This module provides ANSI color codes and utility functions for 
terminal color detection and colored text formatting.
"""
import os
import sys
from typing import Dict, Optional

# ANSI color codes
COLORS = {
    # Text colors
    "BLACK": "\033[30m",
    "RED": "\033[31m",
    "GREEN": "\033[32m",
    "YELLOW": "\033[33m",
    "BLUE": "\033[34m",
    "MAGENTA": "\033[35m",
    "CYAN": "\033[36m",
    "WHITE": "\033[37m",
    "GRAY": "\033[90m",
    
    # Bright text colors
    "BRIGHT_RED": "\033[91m",
    "BRIGHT_GREEN": "\033[92m",
    "BRIGHT_YELLOW": "\033[93m",
    "BRIGHT_BLUE": "\033[94m",
    "BRIGHT_MAGENTA": "\033[95m", 
    "BRIGHT_CYAN": "\033[96m",
    "BRIGHT_WHITE": "\033[97m",
    
    # Text styles
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
    "ITALIC": "\033[3m",
    "DIM": "\033[2m",
    
    # Reset
    "RESET": "\033[0m",
}

# Tree colors mapping by element type
TREE_COLORS = {
    "command_header": COLORS["BRIGHT_BLUE"] + COLORS["BOLD"],
    "command_header_call": COLORS["GREEN"] + COLORS["BOLD"], 
    "command_header_staticcall": COLORS["CYAN"] + COLORS["BOLD"],
    "command_header_delegatecall": COLORS["YELLOW"] + COLORS["BOLD"],

    "tree_structure": COLORS["GRAY"],
    "state_ref": COLORS["MAGENTA"],
    "param_name": COLORS["CYAN"],
    "function_name": COLORS["BRIGHT_GREEN"],
    "address": COLORS["YELLOW"],
    "unused": COLORS["DIM"] + COLORS["GRAY"],
    "subplan": COLORS["BRIGHT_MAGENTA"],
    
    "input_label": COLORS["BRIGHT_WHITE"],
    "output_label": COLORS["BRIGHT_WHITE"],
    
    "value_string": COLORS["GREEN"],
    "value_number": COLORS["BRIGHT_YELLOW"],
    "value_bool": COLORS["BRIGHT_CYAN"],
    "value_address": COLORS["YELLOW"],
    "value_bytes": COLORS["MAGENTA"],
}

def supports_color() -> bool:
    """
    Check if the current terminal supports colors.
    
    Returns:
        bool: True if the terminal supports colors, False otherwise
    """
    # Check environment variables for color forcing/disabling
    if "WEIROLL_NO_COLOR" in os.environ:
        return False
    if "WEIROLL_FORCE_COLOR" in os.environ:
        return True
    
    # Check if NO_COLOR is set (standard for disabling color)
    if "NO_COLOR" in os.environ:
        return False
    
    # Check if FORCE_COLOR is set
    if "FORCE_COLOR" in os.environ:
        return True
    
    # Check if output is a terminal
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

def colorize(text: str, color_key: str, use_color: Optional[bool] = None) -> str:
    """
    Apply color to the given text if colors are supported.
    
    Args:
        text: Text to colorize
        color_key: Key in TREE_COLORS dictionary
        use_color: Force color on/off, defaults to auto-detection
        
    Returns:
        Colored text string if colors are supported, otherwise the original text
    """
    # Determine if we should use color
    should_use_color = supports_color() if use_color is None else use_color
    
    if not should_use_color:
        return text
    
    color_code = TREE_COLORS.get(color_key, "")
    if not color_code:
        return text
    
    return f"{color_code}{text}{COLORS['RESET']}"

def get_color_mode() -> bool:
    """
    Get the current color mode based on environment and terminal detection.
    
    Returns:
        bool: True if colors should be used, False otherwise
    """
    return supports_color()