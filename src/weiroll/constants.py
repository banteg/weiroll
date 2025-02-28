from enum import IntEnum


class CallType(IntEnum):
    """Call types for Weiroll commands."""
    DELEGATECALL = 0x00
    CALL = 0x01
    STATICCALL = 0x02
    VALUECALL = 0x03


class ArgType(IntEnum):
    """Special argument type identifiers."""
    END_OF_ARGS = 0xFF
    USE_STATE = 0xFE


# Bit masks for command flags
TUP_BIT = 0x80  # Tuple return bit
EXT_BIT = 0x40  # Extended command bit