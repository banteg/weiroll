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
    command_type: CommandType = CommandType.CALL  # Type of command (standard, rawcall, subplan)
    
    @property
    def extended_inputs(self) -> bool:
        """Dynamically determine if this command has extended inputs (> 6 args)."""
        return len(self.inputs) > 6

    @property
    def flags(self) -> int:
        """Generate the flags byte for the command."""
        result = 0
        if self.is_tuple_return:
            result |= TUP_BIT
        # Always check if we have extended inputs when generating flags
        if len(self.inputs) > 6:
            result |= EXT_BIT
        result |= self.call_type & 0x03
        return result

    def encode(self) -> bytes:
        """Encode the command as bytes32.
        
        If the command has more than 6 inputs (extended inputs), the first 6 will be
        encoded in the command itself. Use encode_extended_inputs() to get the additional
        encoding for the extended inputs.
        """
        # Ensure function selector is 4 bytes
        selector = self.function_selector[:4].ljust(4, b"\x00")

        # Flags byte - uses EXT_BIT automatically when len(inputs) > 6 via extended_inputs property
        flags = bytes([self.flags])

        # Encode inputs (only first 6 for the main command)
        encoded_inputs = b""
        main_inputs = self.inputs[:6]
        for arg in main_inputs:
            encoded_inputs += arg.encode()

        # Pad inputs to 6 bytes
        padded_inputs = encoded_inputs.ljust(6, bytes([ArgType.END_OF_ARGS]))

        # Output byte
        output_byte = self.output.encode() if self.output else bytes([ArgType.END_OF_ARGS])

        # Target address (20 bytes)
        target = self.target[-20:].rjust(20, b"\x00")

        # Combine all parts for the main command
        return selector + flags + padded_inputs + output_byte + target

    @classmethod
    def decode(cls, data: bytes | str) -> "Command":
        """Decode a bytes32 command."""
        if isinstance(data, str):
            data = to_bytes(hexstr=data)

        # Ensure we have 32 bytes
        if len(data) != 32:
            raise ValueError(f"Command must be 32 bytes, got {len(data)}")
            
        # Check if this is an extended inputs command
        if data[0:4] == b"\xFF\xFF\xFF\xFF":
            # This is an extended inputs command
            # Format:
            # - 4 bytes: Special marker (0xFFFFFFFF)
            # - 1 byte: Number of extended inputs
            # - 1-15 bytes: Extended input args (1 byte each)
            
            # Create a minimal command to represent extended inputs
            # This is not meant to be a full command, just a container
            return cls(
                function_selector=data[0:4],  # Special marker
                target=bytes(20),  # Empty target
                inputs=[CommandArg.from_byte(b) for b in data[5:] if b != 0],  # Extended inputs
            )

        # Regular command decoding
        selector = data[0:4]
        flags_byte = data[4]
        input_bytes = data[5:11]
        output_byte = data[11]
        target = data[12:32]

        # Parse flags
        is_tuple_return = (flags_byte & TUP_BIT) != 0
        has_extended_inputs = (flags_byte & EXT_BIT) != 0
        call_type = CallType(flags_byte & 0x03)

        # Parse inputs
        inputs = []
        for b in input_bytes:
            if b == ArgType.END_OF_ARGS:
                break
            inputs.append(CommandArg.from_byte(b))

        # Parse output
        output = None if output_byte == ArgType.END_OF_ARGS else CommandArg.from_byte(output_byte)

        # Handle extended inputs case - we need to create a command with enough inputs
        # to trigger the extended_inputs property to return True
        if has_extended_inputs:
            # We need more than 6 inputs to get extended_inputs=True from the property
            # Just add some dummy inputs that will be replaced later
            while len(inputs) <= 6:
                inputs.append(CommandArg(index=0))

        return cls(
            function_selector=selector,
            target=target,
            inputs=inputs,
            output=output,
            call_type=call_type,
            is_tuple_return=is_tuple_return,
        )

    def encode_extended_inputs(self) -> bytes:
        """
        Encode extended inputs (inputs beyond the first 6) as a separate bytes32.
        
        When a command has more than 6 inputs, this method creates a special command
        containing the additional inputs. This command should follow the main command
        in the final encoding.
        
        Returns:
            bytes: 32-byte encoding of the extended inputs, or empty bytes if no extended inputs
        """
        if not self.extended_inputs:
            return b""
            
        # Get extended inputs (beyond the first 6)
        extended_inputs = self.inputs[6:]
        
        # Create a special command for extended inputs
        # Format:
        # - 4 bytes: Special marker (0xFFFFFFFF)
        # - 1 byte: Number of extended inputs
        # - 1-15 bytes: Extended input args (1 byte each)
        # - Remaining bytes: Zeros
        
        # Special marker for extended inputs command
        marker = b"\xFF\xFF\xFF\xFF"
        
        # Number of extended inputs (1 byte)
        count = bytes([len(extended_inputs)])
        
        # Encode the extended inputs
        encoded_inputs = b""
        for arg in extended_inputs:
            encoded_inputs += arg.encode()
            
        # Pad to 32 bytes
        padding_size = 32 - len(marker) - len(count) - len(encoded_inputs)
        padding = b"\x00" * padding_size
        
        return marker + count + encoded_inputs + padding
    
    def __str__(self) -> str:
        return f"Command(selector={to_hex(self.function_selector)}, target={to_hex(self.target)}, call_type={self.call_type.name}, inputs={len(self.inputs)})"
