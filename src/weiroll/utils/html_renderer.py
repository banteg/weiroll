"""
HTML rendering utilities for Weiroll plans.

Provides functions to render a plan as HTML for display in environments like Jupyter notebooks and Marimo.
This module now uses the rich_renderer for consistent output.
"""

from typing import Any, Dict, List, Optional, Tuple

from .rich_renderer import render_rich_html


def render_html(
    commands: List[Dict[str, Any]],
    state: List[Any],
    call_types: List[str],
    state_sources: Dict[int, tuple],
    state_usage: Dict[int, list],
) -> str:
    """
    Render a plan as HTML for display in notebook environments like Jupyter and Marimo.
    This function now delegates to the rich_renderer for consistent output.

    Args:
        commands: List of command dictionaries
        state: List of state values
        call_types: List of call types (e.g. "CALL", "STATICCALL")
        state_sources: Maps state index to the command that produced it
        state_usage: Maps state index to commands that use it as input

    Returns:
        str: HTML representation of the plan
    """
    # Convert state_sources and state_usage to the format expected by rich_renderer
    # The rich_renderer expects state_sources to be Dict[int, Tuple[int, int]]
    # and state_usage to be Dict[int, List[Tuple[int, int]]]
    converted_state_sources = {}
    for k, v in state_sources.items():
        if isinstance(v, tuple):
            converted_state_sources[k] = v
        else:
            # If it's not already a tuple, convert it to one
            converted_state_sources[k] = (v, 0)

    converted_state_usage = {}
    for k, v in state_usage.items():
        if isinstance(v, list):
            # Ensure each item in the list is a tuple
            converted_state_usage[k] = [item if isinstance(item, tuple) else (item, 0) for item in v]
        else:
            # If it's not a list, convert it to a list with one tuple
            converted_state_usage[k] = [(v, 0)]

    # Delegate to rich_renderer
    return render_rich_html(commands, state, call_types, converted_state_sources, converted_state_usage)
