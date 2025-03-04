"""
Terminal color utilities for weiroll output formatting.

This module provides both standard ANSI color codes and true color (24-bit)
support for modern terminals. It detects terminal capabilities and automatically
selects the appropriate color mode.

Features:
- True color (24-bit RGB) support for terminals that support it
- Automatic fallback to 256-color mode for older terminals
- Glasbey high-visibility color palette optimized for both light and dark backgrounds
- Maximum perceptual distinctness between adjacent colors
- Color detection to disable colors when not supported
- Environment variable overrides for color preferences

Environment variables:
- WEIROLL_FORCE_COLOR: Force color output even if terminal doesn't support it
- WEIROLL_NO_COLOR: Disable color output
- WEIROLL_FORCE_TRUECOLOR: Force true color (24-bit) mode
- NO_COLOR: Standard variable to disable color output across applications
- FORCE_COLOR: Standard variable to force color output
- COLORTERM=truecolor: Indicates terminal supports true color

The module automatically selects the best color mode based on the terminal
capabilities and environment variables.
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

# Define Fallback colors here
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

# ===== Core Terminal Color Detection =====

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
    
    # Force color support for Weiroll testing/debugging
    if "WEIROLL_FORCE_TRUECOLOR" in os.environ:
        return True
    
    # Check if output is a terminal
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

def supports_truecolor() -> bool:
    """
    Check if the current terminal supports true color (24-bit color).
    
    Returns:
        bool: True if the terminal supports true color, False otherwise
    """
    # Force truecolor via env var
    if "WEIROLL_FORCE_TRUECOLOR" in os.environ:
        return True
    
    # Check if we support any colors first
    if not supports_color():
        return False
    
    # Check COLORTERM for explicit truecolor support
    colorterm = os.environ.get("COLORTERM", "").lower()
    if "truecolor" in colorterm or "24bit" in colorterm:
        return True
    
    # Check if running in a terminal that likely supports truecolor
    term = os.environ.get("TERM", "").lower()
    if "xterm" in term or "256color" in term:
        return True
    
    # Check for specific terminals
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    return term_program in ["iterm", "apple_terminal", "vscode", "hyper"]

# ===== Color Generation Functions =====

# Generate ANSI color codes from Glasbey high-visibility colormap
def generate_glasbey_colors() -> List[str]:
    """Generate ANSI true color codes from Glasbey high-visibility colormap.
    
    Uses the Glasbey high-visibility color map optimized for both light and dark backgrounds.
    """
    colors = []
    
    # Only use colorcet if it's available
    if HAS_COLORCET:
        # cc.glasbey_hv contains RGB triplets as floats 0-1
        for i, rgb_color in enumerate(cc.glasbey_hv):
            # Skip the first few colors which might be too light
            if i > 3:  # Start from the 4th color
                # RGB values are provided as floats 0-1
                r, g, b = rgb_color
                # Convert to integers 0-255
                r_int, g_int, b_int = int(r * 255), int(g * 255), int(b * 255)
                # Generate ANSI color code
                if supports_truecolor():
                    colors.append(f"\033[38;2;{r_int};{g_int};{b_int}m")
                else:
                    # Fall back to 256-color ANSI escape sequence
                    ansi = 16 + (36 * (r_int // 43)) + (6 * (g_int // 43)) + (b_int // 43)
                    colors.append(f"\033[38;5;{ansi}m")
    
    return colors

# State slot colors using Glasbey high-visibility color map
STATE_SLOT_COLORS = generate_glasbey_colors()

# Ensure we have at least some colors
if not STATE_SLOT_COLORS:
    STATE_SLOT_COLORS = FALLBACK_STATE_COLORS

# ===== Color Application Functions =====

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
    
    try:
        # Get the color for this state slot and make it bold
        color_code = get_state_slot_color(slot_index)
        if color_code:
            return f"{color_code}{COLORS['BOLD']}{text}{COLORS['RESET']}"
        else:
            # Fallback to default bold
            return f"{COLORS['BOLD']}{text}{COLORS['RESET']}"
    except Exception:
        # If any error occurs, return uncolored text
        return text

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
    
    # Safety check for empty color list
    if not STATE_SLOT_COLORS:
        return COLORS["WHITE"]
    
    # Return a color from our Glasbey palette based on slot index
    # Use modulo to handle any number of state slots
    color_index = abs_index % len(STATE_SLOT_COLORS)
    
    # Safety check for index out of range (shouldn't happen with modulo but just in case)
    if color_index >= len(STATE_SLOT_COLORS) or not STATE_SLOT_COLORS[color_index]:
        return COLORS["WHITE"]
        
    return STATE_SLOT_COLORS[color_index]
