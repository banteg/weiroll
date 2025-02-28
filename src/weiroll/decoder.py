from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass

import eth_abi
from eth_utils import to_hex, to_bytes, to_checksum_address

from .command import Command
from .constants import CallType, ArgType


@dataclass
class DecodedCommand:
    """Represents a decoded Weiroll command with human-readable information."""
    selector: str
    target: str
    call_type: str
    inputs: List[int]
    output: Optional[int]
    is_tuple_return: bool
    is_extended: bool
    raw_command: str

    def __str__(self) -> str:
        call_types = {
            CallType.DELEGATECALL: "DELEGATECALL",
            CallType.CALL: "CALL",
            CallType.STATICCALL: "STATICCALL",
            CallType.VALUECALL: "VALUECALL"
        }
        
        return (
            f"Command: {self.selector} @ {self.target}\n"
            f"Call Type: {self.call_type}\n"
            f"Inputs: {self.inputs}\n"
            f"Output: {self.output if self.output is not None else 'None'}\n"
            f"Tuple Return: {self.is_tuple_return}\n"
            f"Extended: {self.is_extended}"
        )


@dataclass
class DecodedPlan:
    """Represents a full decoded Weiroll execution plan."""
    commands: List[DecodedCommand]
    state: List[str]
    
    def __str__(self) -> str:
        result = "--- Weiroll Plan ---\n\n"
        result += f"Commands: {len(self.commands)}\n"
        result += f"State: {len(self.state)} elements\n\n"
        
        for i, cmd in enumerate(self.commands):
            result += f"Command {i}:\n{cmd}\n\n"
        
        result += "State Values:\n"
        for i, state_value in enumerate(self.state):
            # Truncate long state values for display
            display_value = state_value
            if len(display_value) > 66:  # 0x + 64 hex chars
                display_value = display_value[:66] + "..."
            result += f"  [{i}]: {display_value}\n"
        
        return result


class Decoder:
    """Decoder for Weiroll commands and plans."""
    
    @staticmethod
    def decode_command(command_data: Union[str, bytes]) -> DecodedCommand:
        """Decode a command from bytes32 or hex string."""
        # Use the existing Command class to decode
        cmd = Command.decode(command_data)
        
        # Convert to a more human-readable format
        call_type_names = {
            CallType.DELEGATECALL: "DELEGATECALL",
            CallType.CALL: "CALL", 
            CallType.STATICCALL: "STATICCALL",
            CallType.VALUECALL: "VALUECALL"
        }
        
        input_indices = [arg.index for arg in cmd.inputs]
        output_index = cmd.output.index if cmd.output else None
        
        return DecodedCommand(
            selector=to_hex(cmd.function_selector),
            target=to_checksum_address(cmd.target),
            call_type=call_type_names[cmd.call_type],
            inputs=input_indices,
            output=output_index,
            is_tuple_return=cmd.is_tuple_return,
            is_extended=cmd.extended_inputs,
            raw_command=to_hex(command_data) if isinstance(command_data, bytes) else command_data
        )
    
    @staticmethod
    def decode_plan(commands: List[Union[str, bytes]], state: List[str]) -> DecodedPlan:
        """Decode a full Weiroll plan."""
        decoded_commands = [Decoder.decode_command(cmd) for cmd in commands]
        
        # Clean up state values for display
        clean_state = []
        for value in state:
            if isinstance(value, bytes):
                clean_state.append(to_hex(value))
            else:
                clean_state.append(value)
        
        return DecodedPlan(
            commands=decoded_commands,
            state=clean_state
        )
    
    @staticmethod
    def decode_command_with_abi(command_data: Union[str, bytes], abi: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Decode a command with ABI information for enhanced readability."""
        decoded = Decoder.decode_command(command_data)
        
        # TODO: Implement ABI-based decoding for function name and arguments
        # This would require:
        # 1. Finding the function in the ABI by selector
        # 2. Parsing the state values according to function argument types
        # 3. Returning human-readable function call information
        
        result = {
            "selector": decoded.selector,
            "target": decoded.target,
            "call_type": decoded.call_type
        }
        
        # Find the function in the ABI
        fn_selector = decoded.selector
        fn_info = None
        for item in abi:
            if item.get("type") != "function":
                continue
                
            # Calculate selector for this function
            # This is a simplification - a proper implementation would use eth_utils.function_signature_to_4byte_selector
            name = item.get("name", "")
            inputs = item.get("inputs", [])
            input_types = [inp.get("type", "") for inp in inputs]
            # Function selector calculation would go here
            
            # For now, this is a placeholder
            if name:
                fn_info = item
                break
                
        if fn_info:
            result["function"] = {
                "name": fn_info.get("name"),
                "inputs": fn_info.get("inputs"),
                "outputs": fn_info.get("outputs")
            }
            
        return result