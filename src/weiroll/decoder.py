from typing import Dict, List, Any, Optional, Tuple, Union, Literal
from dataclasses import dataclass
import logging
from functools import lru_cache

import eth_abi
from eth_utils import to_hex, to_bytes, to_checksum_address, function_signature_to_4byte_selector

from .command import Command
from .constants import CallType, ArgType

# Set up logger
logger = logging.getLogger("weiroll.decoder")


@dataclass
class DecodedCommand:
    """
    Represents a decoded Weiroll command with human-readable information.
    
    Attributes:
        selector: The 4-byte function selector as a hex string
        target: The target contract address (checksummed)
        call_type: Human-readable call type (CALL, DELEGATECALL, etc.)
        inputs: List of state indices used as inputs
        output: State index for the output value or None
        is_tuple_return: Whether this call returns multiple values
        is_extended: Whether this call has extended inputs
        raw_command: The original command data
    """
    selector: str
    target: str
    call_type: str
    inputs: List[int]
    output: Optional[int]
    is_tuple_return: bool
    is_extended: bool
    raw_command: str

    def __str__(self) -> str:
        """Format the command for human-readable output."""
        return (
            f"Command: {self.selector} @ {self.target}\n"
            f"Call Type: {self.call_type}\n"
            f"Inputs: {self.inputs}\n"
            f"Output: {self.output if self.output is not None else 'None'}\n"
            f"Tuple Return: {self.is_tuple_return}\n"
            f"Extended: {self.is_extended}"
        )
        
    def __repr__(self) -> str:
        """Provide a concise representation for debugging."""
        return f"DecodedCommand(selector={self.selector}, target={self.target}, call_type={self.call_type})"


@dataclass
class DecodedPlan:
    """
    Represents a full decoded Weiroll execution plan.
    
    Attributes:
        commands: List of decoded commands
        state: List of state values as hex strings
    """
    commands: List[DecodedCommand]
    state: List[str]
    
    def __str__(self) -> str:
        """Format the plan for human-readable output."""
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
        
    def __repr__(self) -> str:
        """Provide a concise representation for debugging."""
        return f"DecodedPlan(commands={len(self.commands)}, state_size={len(self.state)})"


class Decoder:
    """
    Decoder for Weiroll commands and plans.
    
    This class provides utilities to decode Weiroll commands and plans
    into human-readable formats.
    """
    
    @staticmethod
    def decode_command(command_data: Union[str, bytes]) -> DecodedCommand:
        """
        Decode a command from bytes32 or hex string.
        
        Args:
            command_data: The command data to decode (bytes32 or hex string)
            
        Returns:
            DecodedCommand: A decoded command with human-readable information
            
        Raises:
            ValueError: If the command data is invalid
        """
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
    def decode_plan(
        commands: List[Union[str, bytes]], 
        state: List[str]
    ) -> DecodedPlan:
        """
        Decode a full Weiroll plan.
        
        Args:
            commands: List of command data (bytes32 or hex strings)
            state: List of state values
            
        Returns:
            DecodedPlan: A decoded plan with human-readable information
        """
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
    @lru_cache(maxsize=128)
    def _get_selector_for_function(name: str, input_types: List[str]) -> str:
        """
        Calculate a function selector from name and input types.
        
        Args:
            name: Function name
            input_types: List of input type strings
            
        Returns:
            str: The 4-byte function selector as a hex string
        """
        signature = f"{name}({','.join(input_types)})"
        return to_hex(function_signature_to_4byte_selector(signature))
    
    @staticmethod
    def decode_command_with_abi(
        command_data: Union[str, bytes], 
        abi: List[Dict[str, Any]] = None,
        contract_address: str = None
    ) -> Dict[str, Any]:
        """
        Decode a command with ABI information for enhanced readability.
        
        Args:
            command_data: The command data to decode (bytes32 or hex string)
            abi: The ABI for the target contract (optional if contract_address is provided)
            contract_address: The contract address to look up (optional if abi is provided)
            
        Returns:
            dict: A dictionary with decoded command information
        """
        decoded = Decoder.decode_command(command_data)
        
        result = {
            "selector": decoded.selector,
            "target": decoded.target,
            "call_type": decoded.call_type,
            "inputs": decoded.inputs,
            "output": decoded.output
        }
        
        # Use contract address from decoded command if not provided
        if not contract_address:
            contract_address = decoded.target
        
        # Find the function in the ABI using one of several approaches
        fn_selector = decoded.selector
        fn_info = None
        function_signature = None
        
        # 1. Try to get the function signature from the contract's identifier_lookup
        try:
            from ape import Contract as ApeContract
            if contract_address:
                try:
                    contract = ApeContract(contract_address)
                    if hasattr(contract, 'identifier_lookup') and fn_selector in contract.identifier_lookup:
                        identifier = contract.identifier_lookup[fn_selector]
                        function_signature = identifier.signature
                        function_selector = identifier.selector
                        result["function"] = {
                            "name": identifier.name,
                            "signature": function_signature,
                            "selector": function_selector
                        }
                        # If successful, we're done
                        return result
                except Exception as e:
                    logger.debug(f"Error looking up function by identifier: {e}")
        except ImportError:
            pass  # Ape not available
        
        # 2. Try to find the function in the provided ABI
        if abi:
            # Try to match the function by selector
            for item in abi:
                if item.get("type") != "function":
                    continue
                    
                name = item.get("name", "")
                inputs = item.get("inputs", [])
                
                # Skip if no name or no inputs section
                if not name or inputs is None:
                    continue
                    
                # Extract input types
                input_types = []
                for inp in inputs:
                    if isinstance(inp, dict) and "type" in inp:
                        input_types.append(inp["type"])
                    else:
                        # If input doesn't have a type, skip this function
                        logger.warning(f"Skipping function {name} due to missing input type")
                        break
                else:
                    # Calculate selector for this function
                    calculated_selector = Decoder._get_selector_for_function(name, input_types)
                    
                    # If selectors match, we found the function
                    if calculated_selector == fn_selector:
                        fn_info = item
                        function_signature = f"{name}({','.join(input_types)})"
                        break
        
        # 3. Try to use 4byte.directory API or other signature sources
        # We'll only implement this placeholder for now - future enhancement
        if not function_signature:
            # Placeholder for possible future enhancement:
            # - Query 4byte.directory API
            # - Use local signature database
            # - Check etherscan API
            pass
        
        # Add the function info to the result if found in ABI
        if fn_info:
            result["function"] = {
                "name": fn_info.get("name"),
                "signature": function_signature or f"{fn_info.get('name')}({','.join(inp.get('type', '') for inp in fn_info.get('inputs', []))})",
                "inputs": fn_info.get("inputs"),
                "outputs": fn_info.get("outputs")
            }
        # Add minimal function info if only signature is available
        elif function_signature:
            name = function_signature.split("(")[0]
            result["function"] = {
                "name": name,
                "signature": function_signature
            }
            
        return result