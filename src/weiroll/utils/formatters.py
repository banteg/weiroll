"""
Value formatting utilities for Weiroll.

This module provides formatting helpers for common Ethereum data types,
particularly useful for displaying values in decoded plans.
"""
from decimal import Decimal
from typing import Optional, Dict, Any, Union
from eth_utils import is_address, to_checksum_address, encode_hex


def format_value(
    hex_value: Union[str, int, bytes], param_type: Optional[str] = None
) -> str:
    """
    Format a hex value based on its inferred type.

    Args:
        hex_value: The value to format (can be hex string, integer, or bytes)
        param_type: Optional parameter type (e.g., 'uint256', 'address')

    Returns:
        str: A formatted string representation
    """
    match hex_value:
        case int() as val:
            if val >= 10**18:
                return f'{Decimal(val) / 10**18} x 10^18'
            else:
                return f"{val:,}"

        case bytes() as val:
            return encode_hex(val)

        case str() as val if is_address(val):
            return to_checksum_address(val)

        case _:
            return hex_value
