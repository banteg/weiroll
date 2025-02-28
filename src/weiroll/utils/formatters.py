"""
Value formatting utilities for Weiroll.

This module provides formatting helpers for common Ethereum data types,
particularly useful for displaying values in decoded plans.
"""

from typing import Optional, Dict, Any, Union


def format_eth_value(wei_value: int) -> str:
    """
    Format an ETH value in wei to a readable string with appropriate units.
    
    Args:
        wei_value: The value in wei (10^-18 ETH)
        
    Returns:
        str: A formatted string representation with appropriate units
    """
    if wei_value == 0:
        return "0 ETH"
        
    # Format large values using scientific notation
    if wei_value >= 10**18:
        eth = wei_value / 10**18
        # Check if it's a whole number
        if wei_value % 10**18 == 0:
            return f"{int(eth)} ETH"
        else:
            # Display with up to 4 decimal places for fractional ETH
            return f"{eth:.4f} ETH"
    elif wei_value >= 10**9:
        # Format as gwei for medium values
        gwei = wei_value / 10**9
        return f"{gwei:.2f} gwei"
    else:
        # Format as wei for small values (with commas for readability)
        return f"{wei_value:,} wei"


def format_hex_value(hex_value: str, param_type: Optional[str] = None) -> str:
    """
    Format a hex value based on its inferred type.
    
    Args:
        hex_value: The hex string to format
        param_type: Optional parameter type (e.g., 'uint256', 'address')
        
    Returns:
        str: A formatted string representation
    """
    # Return empty values as is
    if not hex_value or hex_value == '0x':
        return "None"
        
    # Strip 0x prefix for processing
    clean_hex = hex_value[2:] if hex_value.startswith('0x') else hex_value
    
    # Handle known Ethereum types
    if param_type:
        param_type = param_type.strip()
        
        # Handle addresses
        if param_type == 'address':
            # For addresses, just return the original value
            return hex_value
            
        # Handle integers - only add formatting for large numbers
        elif param_type.startswith('uint'):
            try:
                int_val = int(clean_hex, 16)
                # Only do special formatting for very large numbers that are likely token amounts
                if int_val >= 10**18:
                    # Format large integers in terms of 10^18 units
                    return f"{int_val // 10**18} × 10^18"
                elif int_val > 10**6:
                    # Format with commas for readability
                    return f"{int_val:,}"
                else:
                    return str(int_val)
            except ValueError:
                pass
    
    # Default formatting based on value appearance - very minimal
    
    # For addresses or short hex values, return as is
    if len(clean_hex) <= 42:
        return hex_value
    
    # Try to interpret as a number for large hex strings
    try:
        int_val = int(clean_hex, 16)
        if int_val >= 10**18:
            # Format large integers in terms of 10^18 units
            return f"{int_val // 10**18} × 10^18"
        return str(int_val)
    except (ValueError, OverflowError):
        # If it's not a valid number, truncate for display
        return f"{hex_value[:10]}...{hex_value[-8:]}"