from dataclasses import dataclass

from eth_utils import to_bytes, to_hex

from .constants import EXT_BIT, TUP_BIT, ArgType, CallType, CommandType


@dataclass
class CommandArg:
    """Represents an argument to a command."""

    index: int
    is_dynamic: bool = False
    is_subplan: bool = False  # Indicates this arg is a subplan
    is_state: bool = False  # Indicates this arg is the planner state

    def encode(self) -> bytes:
        """
        Encode the argument specification as a byte.
        
        Special values:
        - For Subplans: The index will be updated during planning (initially -1)
        - For State: Use 0xFE (the special state value index)
        """
        if self.is_state:
            # State is represented as 0xFE
            return bytes([0xFE])
        
        if self.is_subplan:
            # The actual index will be filled in during planning
            # For now, we just mark it as dynamic
            var_bit = 0x80
            # The index will be provided during planning
            return bytes([var_bit | (self.index & 0x7F)])
        
        # Standard argument
        var_bit = 0x80 if self.is_dynamic else 0
        return bytes([var_bit | (self.index & 0x7F)])

    @classmethod
    def from_byte(cls, b: int) -> "CommandArg":
        """Decode an argument from a byte."""
        is_dynamic = (b & 0x80) != 0
        index = b & 0x7F
        
        # Handle special cases
        is_state = (index == 0x7E)  # 0xFE & 0x7F = 0x7E
        
        return cls(
            index=index, 
            is_dynamic=is_dynamic,
            is_state=is_state
        )


@dataclass
class Command:
    """Represents a command in the Weiroll VM."""

    function_selector: bytes
    target: bytes
    inputs: list[CommandArg]
    output: CommandArg | None = None
    call_type: CallType = CallType.DELEGATECALL
    is_tuple_return: bool = False  # For raw value capture of return values
    extended_inputs: bool = False  # For handling more than 6 arguments
    command_type: CommandType = CommandType.CALL  # Type of command (standard, rawcall, subplan)

    @property
    def flags(self) -> int:
        """Generate the flags byte for the command."""
        result = 0
        if self.is_tuple_return:
            result |= TUP_BIT
        if self.extended_inputs:
            result |= EXT_BIT
        result |= self.call_type & 0x03
        return result

    def encode(self) -> bytes:
        """Encode the command as bytes32."""
        # Ensure function selector is 4 bytes
        selector = self.function_selector[:4].ljust(4, b"\x00")

        # Flags byte
        flags = bytes([self.flags])

        # Encode inputs (up to 6 bytes)
        encoded_inputs = b""
        for i, arg in enumerate(self.inputs):
            if i >= 6:
                # If we have more than 6 inputs, set extended flag
                self.extended_inputs = True
                break
            encoded_inputs += arg.encode()

        # Pad inputs to 6 bytes
        padded_inputs = encoded_inputs.ljust(6, bytes([ArgType.END_OF_ARGS]))

        # Output byte
        output_byte = self.output.encode() if self.output else bytes([ArgType.END_OF_ARGS])

        # Target address (20 bytes)
        target = self.target[-20:].rjust(20, b"\x00")

        # Combine all parts
        return selector + flags + padded_inputs + output_byte + target

    @classmethod
    def decode(cls, data: bytes | str) -> "Command":
        """Decode a bytes32 command."""
        if isinstance(data, str):
            data = to_bytes(hexstr=data)

        # Ensure we have 32 bytes
        if len(data) != 32:
            raise ValueError(f"Command must be 32 bytes, got {len(data)}")

        selector = data[0:4]
        flags_byte = data[4]
        input_bytes = data[5:11]
        output_byte = data[11]
        target = data[12:32]

        # Parse flags
        is_tuple_return = (flags_byte & TUP_BIT) != 0
        extended_inputs = (flags_byte & EXT_BIT) != 0
        call_type = CallType(flags_byte & 0x03)

        # Parse inputs
        inputs = []
        for b in input_bytes:
            if b == ArgType.END_OF_ARGS:
                break
            inputs.append(CommandArg.from_byte(b))

        # Parse output
        output = None if output_byte == ArgType.END_OF_ARGS else CommandArg.from_byte(output_byte)

        return cls(
            function_selector=selector,
            target=target,
            inputs=inputs,
            output=output,
            call_type=call_type,
            is_tuple_return=is_tuple_return,
            extended_inputs=extended_inputs,
        )

    def __str__(self) -> str:
        return f"Command(selector={to_hex(self.function_selector)}, target={to_hex(self.target)}, call_type={self.call_type.name})"
