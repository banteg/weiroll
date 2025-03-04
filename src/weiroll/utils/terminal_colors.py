"""
Terminal color utilities for weiroll output formatting.

This module provides ANSI color codes and utility functions for 
terminal color detection and colored text formatting.
"""
import os
import sys
from typing import Dict, List, Optional

# Import Glasbey high-visibility color map from colorcet
try:
    import colorcet as cc
    HAS_COLORCET = True
except ImportError:
    HAS_COLORCET = False

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

# Convert Glasbey high-visibility colors to ANSI escape sequences
def rgb_to_ansi_256(r: float, g: float, b: float) -> str:
    """Convert RGB color to ANSI 256-color escape sequence.
    
    Args:
        r, g, b: RGB values as floats in range 0-1 or integers in range 0-255
        
    Returns:
        ANSI 256-color escape sequence
    """
    # Convert RGB values (0-1) to 0-255 range if needed
    if isinstance(r, float) and r <= 1.0:
        r_255 = int(r * 255)
        g_255 = int(g * 255)
        b_255 = int(b * 255)
    else:
        r_255 = int(r)
        g_255 = int(g)
        b_255 = int(b)
        
    # Convert RGB values (0-255) to ANSI 256-color code (16-231)
    ansi = 16 + (36 * (r_255 // 43)) + (6 * (g_255 // 43)) + (b_255 // 43)
    return f"\033[38;5;{ansi}m"

# Generate ANSI color codes from Glasbey high-visibility colormap
def generate_glasbey_colors() -> List[str]:
    """Generate ANSI color codes from Glasbey high-visibility colormap."""
    colors = []
    
    # Only use colorcet if it's available
    if HAS_COLORCET:
        # cc.glasbey_hv is a high-visibility Glasbey palette provided as a list of RGB triplets
        # Each triplet is [r, g, b] with values in range 0-1
        for i, rgb_color in enumerate(cc.glasbey_hv):
            # Skip the first few colors which might be too light (especially white)
            if i > 3:  # Start from the 4th color
                # RGB values are provided as floats 0-1
                r, g, b = rgb_color
                # Add this color to our list
                colors.append(rgb_to_ansi_256(r, g, b))
    
    return colors

# Fallback colors in case Glasbey isn't available
FALLBACK_STATE_COLORS = [
    COLORS["BRIGHT_RED"],
    COLORS["BRIGHT_GREEN"],
    COLORS["BRIGHT_YELLOW"],
    COLORS["BRIGHT_BLUE"],
    COLORS["BRIGHT_MAGENTA"],
    COLORS["BRIGHT_CYAN"],
    COLORS["RED"],
    COLORS["GREEN"],
    COLORS["YELLOW"],
    COLORS["BLUE"],
    COLORS["MAGENTA"],
    COLORS["CYAN"],
]

# State slot colors using Glasbey high-visibility color map
STATE_SLOT_COLORS = generate_glasbey_colors()

# Ensure we have at least some colors
if not STATE_SLOT_COLORS:
    STATE_SLOT_COLORS = FALLBACK_STATE_COLORS

# Tree colors mapping by element type
TREE_COLORS = {
    "command_header": COLORS["BRIGHT_BLUE"] + COLORS["BOLD"],
    "command_header_call": COLORS["GREEN"] + COLORS["BOLD"], 
    "command_header_staticcall": COLORS["CYAN"] + COLORS["BOLD"],
    "command_header_delegatecall": COLORS["YELLOW"] + COLORS["BOLD"],

    "tree_structure": COLORS["GRAY"],
    "state_ref": COLORS["MAGENTA"],  # Default state reference color (when not using color by slot)
    "param_name": COLORS["CYAN"],
    "function_name": COLORS["BRIGHT_GREEN"],
    "address": COLORS["YELLOW"],
    "unused": COLORS["DIM"] + COLORS["GRAY"],
    "subplan": COLORS["BRIGHT_MAGENTA"],
    
    "input_label": COLORS["BRIGHT_WHITE"],
    "output_label": COLORS["BRIGHT_YELLOW"],
    
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

def colorize_state_ref(text: str, slot_index: int, use_color: Optional[bool] = None) -> str:
    """
    Apply slot-based coloring to a state reference.
    
    Args:
        text: State reference text to colorize
        slot_index: The state slot index to use for color selection
        use_color: Force color on/off, defaults to auto-detection
        
    Returns:
        Colored text string if colors are supported, otherwise the original text
    """
    # Determine if we should use color
    should_use_color = supports_color() if use_color is None else use_color
    
    if not should_use_color:
        return text
    
    # Get the color for this state slot and make it bold
    color_code = get_state_slot_color(slot_index) + COLORS["BOLD"]
    
    return f"{color_code}{text}{COLORS['RESET']}"

def get_color_mode() -> bool:
    """
    Get the current color mode based on environment and terminal detection.
    
    Returns:
        bool: True if colors should be used, False otherwise
    """
    return supports_color()

def get_state_slot_color(slot_index: int) -> str:
    """
    Get the color code for a specific state slot using Glasbey high-visibility colors.
    This allows visually tracking state values across commands with perceptually
    distinct colors that are designed to be maximally different from each other.
    
    Args:
        slot_index: The state slot index
        
    Returns:
        str: ANSI color code for this state slot
    """
    # For special values like uint256 (used when StateValue has string indices)
    if not isinstance(slot_index, int):
        return COLORS["WHITE"]
    
    # Ensure index is positive
    abs_index = abs(slot_index)
    
    # Return a color from our Glasbey palette based on slot index
    # Use modulo to handle any number of state slots
    color_index = abs_index % len(STATE_SLOT_COLORS)
    return STATE_SLOT_COLORS[color_index]