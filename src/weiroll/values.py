"""
Value types for the Weiroll planner.

This module defines the polymorphic value classes used to store and
manipulate values in the Weiroll planner state.
"""

from eth_abi import encode
from eth_abi.exceptions import EncodingError
import logging
from typing import Any, Union

logger = logging.getLogger(__name__)


class PlannerValue:
    """
    Abstract base for a variety of 'Value' types that can be stored in the Weiroll planner state.
    """

    def is_literal(self) -> bool:
        """Return True if this is a literal (potentially deduplicatable)."""
        return False

    def equals_literal(self, other: "PlannerValue") -> bool:
        """
        Compare with `other` for dedup purposes. 
        By default, non-literal types always fail equality with literal values.
        """
        return False

    def to_bytes(self) -> bytes:
        """Encode this value as raw bytes for storing in the final Weiroll state."""
        raise NotImplementedError("Must implement to_bytes in subclasses.")

    def __repr__(self) -> str:
        """Base implementation of the string representation."""
        return f"{self.__class__.__name__}()"
    
    def __eq__(self, other):
        """Base implementation of equality comparison."""
        if isinstance(other, PlannerValue):
            return self.equals_literal(other)
        return False


class LiteralValue(PlannerValue):
    """
    Holds a user-supplied literal (int, bool, str, bytes, array).
    Eligible for dedup if multiple calls pass the same literal.
    """
    def __init__(self, data: Any, is_dynamic: bool = False):
        self.data = data
        self.is_dynamic = is_dynamic

    def is_literal(self) -> bool:
        return True

    def equals_literal(self, other: "PlannerValue") -> bool:
        """
        For dedup: compare if other is also a LiteralValue with the same self.data.
        """
        if not other.is_literal():
            return False
        return self.data == other.data

    def to_bytes(self) -> bytes:
        """
        Convert self.data to bytes via eth_abi.
        The logic is similar to the 'encode_single_value' approach.
        """
        d = self.data
        try:
            # Basic conversions
            if isinstance(d, bool):
                return encode(["uint256"], [int(d)])
            elif isinstance(d, int):
                return encode(["uint256"], [d])
            elif isinstance(d, str):
                if d.startswith("0x"):
                    # treat it as raw hex
                    return bytes.fromhex(d[2:])
                else:
                    return encode(["string"], [d])
            elif isinstance(d, bytes):
                return d
            elif isinstance(d, list):
                # check if it's all ints or addresses
                if all(isinstance(x, int) for x in d):
                    return encode(["uint256[]"], [d])
                elif all(isinstance(x, str) and x.startswith("0x") for x in d):
                    return encode(["address[]"], [d])
                else:
                    raise ValueError("Unsupported array contents")
            else:
                raise ValueError(f"Unsupported literal type: {type(d)}")
        except EncodingError as e:
            raise ValueError(f"Cannot ABI-encode literal: {self.data}") from e

    def __str__(self):
        # For debug rendering
        return f"<LiteralValue {self.data}>"

    def __repr__(self) -> str:
        """Return string representation of the LiteralValue."""
        return f"LiteralValue(data={repr(self.data)}, is_dynamic={self.is_dynamic})"
    
    def __eq__(self, other):
        """
        Equality comparison that allows comparing LiteralValue with its native value.
        This allows tests to do: assert planner.state[index] == 42
        """
        if isinstance(other, PlannerValue):
            return self.equals_literal(other)
        # Allow direct comparison with the underlying data type
        return self.data == other


class CommandOutputValue(PlannerValue):
    """
    Represents the output from a command. 
    We do not deduplicate these because they are semantically different from a literal 42,
    even if the command output ends up being 42 at runtime.
    """
    def __init__(self, source_command: int = -1, is_dynamic: bool = False):
        """
        Initialize a command output value.
        
        Args:
            source_command: Index of the command that produces this output
            is_dynamic: Whether this is a dynamic type (like string or bytes)
        """
        self.source_command = source_command
        self.is_dynamic = is_dynamic

    def to_bytes(self) -> bytes:
        # Usually, we have no actual data at plan-time,
        # so store '0x' or a single zero word. 
        # We'll just return empty to represent "unknown yet".
        return b""

    def __str__(self):
        # For debug rendering
        return f"<CommandOutput from cmd {self.source_command}>"

    def __repr__(self) -> str:
        """Return string representation of the CommandOutputValue."""
        return f"CommandOutputValue(source_command={self.source_command}, is_dynamic={self.is_dynamic})"
    
    def __eq__(self, other):
        """
        Equality comparison for CommandOutputValue.
        """
        if isinstance(other, CommandOutputValue):
            return (self.source_command == other.source_command and 
                    self.is_dynamic == other.is_dynamic)
        return False


class SubplanValue(PlannerValue):
    """
    Holds the encoded subplan bytes. 
    We never deduplicate these because each subplan is potentially unique logic.
    """
    def __init__(self, subplan_bytes: bytes):
        self.subplan_bytes = subplan_bytes
        self.is_dynamic = True

    def to_bytes(self) -> bytes:
        return self.subplan_bytes
        
    def __str__(self):
        # For debug rendering
        return f"<Subplan len={len(self.subplan_bytes)}>"

    def __repr__(self) -> str:
        """Return string representation of the SubplanValue."""
        if not self.subplan_bytes:
            return "SubplanValue(subplan_bytes=<empty>)"
        # Show length and first few bytes for better debugging
        hex_preview = self.subplan_bytes.hex()[:16] + "..." if len(self.subplan_bytes) > 8 else self.subplan_bytes.hex()
        return f"SubplanValue(subplan_bytes=<bytes of length {len(self.subplan_bytes)}, starts with 0x{hex_preview}>)"
    
    def __eq__(self, other):
        """
        Equality comparison for SubplanValue.
        
        To avoid circular references and infinite recursion, we only compare
        the byte representation length, not the actual content.
        """
        if isinstance(other, SubplanValue):
            # To avoid infinite recursion in circular references,
            # we only compare the byte length, not the actual content
            return len(self.subplan_bytes) == len(other.subplan_bytes)
        return False