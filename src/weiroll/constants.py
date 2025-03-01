from enum import IntEnum


class CallType(IntEnum):
    """Call types for Weiroll commands."""

    DELEGATECALL = 0x00
    CALL = 0x01
    STATICCALL = 0x02
    VALUECALL = 0x03


class CommandType(IntEnum):
    """
    Type of command to execute.
    
    CALL: Standard function call
    RAWCALL: Call that replaces planner state with return value
    SUBPLAN: Execute a nested planner
    """

    CALL = 0
    RAWCALL = 1
    SUBPLAN = 2


class ArgType(IntEnum):
    """Special argument type identifiers."""

    END_OF_ARGS = 0xFF
    USE_STATE = 0xFE


# Bit masks for command flags
TUP_BIT = 0x80  # Tuple return bit
EXT_BIT = 0x40  # Extended command bit
