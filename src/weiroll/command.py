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
        Encode this argument as a byte.
        
        The format is:
        - MSB (bit 7): 1 if dynamic, 0 if static
        - bits 0-6: the index of the state value
        
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
            # Handle both integer and string index types
            idx = 0 if isinstance(self.index, str) else (self.index & 0x7F)
            return bytes([var_bit | idx])

        # Standard argument
        var_bit = 0x80 if self.is_dynamic else 0
        # Handle both integer and string index types
        idx = 0 if isinstance(self.index, str) else (self.index & 0x7F)
        return bytes([var_bit | idx])

    @classmethod
    def from_byte(cls, b: int) -> "CommandArg":
        """Decode an argument from a byte."""
        is_dynamic = (b & 0x80) != 0
        index = b & 0x7F

        # Handle special cases
        is_state = index == 0x7E  # 0xFE & 0x7F = 0x7E

        return cls(index=index, is_dynamic=is_dynamic, is_state=is_state)


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
        """True if this command has more inputs than can fit in a single command."""
        return len(self.inputs) > 6

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
        """Encode the command into bytes.
        
        For standard commands (≤6 inputs), returns a single 32-byte word:
        - 4 bytes: function selector
        - 1 byte: flags
        - 6 bytes: encoded input arguments (each 1 byte), padded with END_OF_ARGS (0xFF)
        - 1 byte: output specifier (or END_OF_ARGS if none)
        - 20 bytes: target address
        
        For extended commands (>6 inputs), returns two concatenated 32-byte words (64 bytes):
        - First word:
            - 4 bytes: function selector
            - 1 byte: flags (with EXT_BIT set)
            - 6 bytes: reserved (zeros)
            - 1 byte: output specifier (or END_OF_ARGS if none)
            - 20 bytes: target address
        - Second word:
            - All input arguments (each 1 byte) padded with END_OF_ARGS (0xFF)
        
        Returns:
            bytes: 32 bytes for standard commands, 64 bytes for extended commands
        """
        # Ensure function selector is 4 bytes
        selector = self.function_selector[:4].ljust(4, b"\x00")

        # Flags byte - uses EXT_BIT automatically when len(inputs) > 6 via extended_inputs property
        flags = bytes([self.flags])

        # Output byte
        output_byte = self.output.encode() if self.output else bytes([ArgType.END_OF_ARGS])

        # Target address (20 bytes)
        target = self.target[-20:].rjust(20, b"\x00")
        
        # Check if we need to use extended encoding (more than 6 inputs)
        if self.extended_inputs:
            # First 32-byte word: selector + flags + reserved zeros + output + target
            reserved_zeros = b"\x00" * 6  # 6 bytes of zeros in place of inputs
            main_command = selector + flags + reserved_zeros + output_byte + target
            
            # Second 32-byte word: all inputs
            all_inputs_encoded = b""
            for arg in self.inputs:
                all_inputs_encoded += arg.encode()
                
            # Pad to 32 bytes
            padded_inputs = all_inputs_encoded.ljust(32, bytes([ArgType.END_OF_ARGS]))
            
            # Return both words concatenated (64 bytes total)
            return main_command + padded_inputs
        else:
            # Standard command: encode the inputs (up to 6)
            encoded_inputs = b""
            for arg in self.inputs:
                encoded_inputs += arg.encode()
                
            # Pad inputs to 6 bytes
            padded_inputs = encoded_inputs.ljust(6, bytes([ArgType.END_OF_ARGS]))
            
            # Combine all parts for the standard command (32 bytes total)
            return selector + flags + padded_inputs + output_byte + target
    
    def __str__(self) -> str:
        return f"Command(selector={to_hex(self.function_selector)}, target={to_hex(self.target)}, call_type={self.call_type.name}, inputs={len(self.inputs)})"

    @classmethod
    def decode(cls, data: bytes | str) -> "Command":
        """Decode a command from bytes.
        
        Args:
            data: Can be:
                - bytes: Either a 32-byte standard command or a 64-byte extended command
                - str: A hex string representing a command
                
        Returns:
            Command: The decoded command.
        """
        # Convert hex string to bytes if needed
        if isinstance(data, str):
            data = to_bytes(hexstr=data)
            
        # Validate data length
        if len(data) not in (32, 64):
            raise ValueError(f"Command must be either 32 or 64 bytes, got {len(data)}")
        
        # Extract common fields from the first 32 bytes
        selector = data[0:4]
        flags_byte = data[4]
        call_type = CallType(flags_byte & 0x03)
        is_tuple_return = (flags_byte & TUP_BIT) != 0
        has_extended_inputs = (flags_byte & EXT_BIT) != 0
        
        # For both standard and extended commands, output and target are in the same positions
        output_byte = data[11]
        target = data[12:32]
        
        # Parse inputs based on command type
        inputs = []
        
        if has_extended_inputs:
            # Extended command should be 64 bytes
            if len(data) != 64:
                raise ValueError(f"Extended command flag is set but data is only {len(data)} bytes, expected 64")
                
            # For extended commands, all inputs are in the second word
            ext_data = data[32:]
            
            # Parse inputs until we hit END_OF_ARGS
            for b in ext_data:
                if b == ArgType.END_OF_ARGS:
                    break
                inputs.append(CommandArg.from_byte(b))
        else:
            # Standard command - inputs are in bytes 5-10
            input_bytes = data[5:11]
            
            # Parse inputs until we hit END_OF_ARGS
            for b in input_bytes:
                if b == ArgType.END_OF_ARGS:
                    break
                inputs.append(CommandArg.from_byte(b))
        
        # Parse output (same for both types)
        output = None if output_byte == ArgType.END_OF_ARGS else CommandArg.from_byte(output_byte)
        
        # Create the command object
        return cls(
            function_selector=selector,
            target=target,
            inputs=inputs,
            output=output,
            call_type=call_type,
            is_tuple_return=is_tuple_return,
        )
