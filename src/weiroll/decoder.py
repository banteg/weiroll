from typing import Dict, List, Any, Optional, Tuple, Union, Literal
from dataclasses import dataclass

from functools import lru_cache
import logging

import eth_abi
from eth_utils import to_hex, to_bytes, to_checksum_address, function_signature_to_4byte_selector
from ape import Contract as ApeContract

from .command import Command
from .constants import CallType, ArgType
from .utils.formatters import format_value
from .utils.tree_renderer import render_tree

# Set up logger
logger = logging.getLogger("weiroll.decoder")
# Set to debug level
logger.setLevel(logging.DEBUG)
# Add console handler if not already present
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)


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
        function: Optional dictionary with function information (name, signature, etc.)
    """
    selector: str
    target: str
    call_type: str
    inputs: List[int]
    output: Optional[int]
    is_tuple_return: bool
    is_extended: bool
    raw_command: str
    function: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        """Format the command for human-readable output."""
        fn_signature = self.function.get('signature') if self.function else None
        fn_display = fn_signature if fn_signature else self.selector
        
        return (
            f"Command: {fn_display} @ {self.target}\n"
            f"Call Type: {self.call_type}\n"
            f"Inputs: {self.inputs}\n"
            f"Output: {self.output if self.output is not None else 'None'}\n"
            f"Tuple Return: {self.is_tuple_return}\n"
            f"Extended: {self.is_extended}"
        )
        
    def __repr__(self) -> str:
        """Provide a concise representation for debugging."""
        fn_name = self.function.get('name') if self.function else None
        fn_display = fn_name if fn_name else self.selector
        return f"DecodedCommand({fn_display} @ {self.target}, call_type={self.call_type})"


@dataclass
class DecodedPlan:
    """
    Represents a full decoded Weiroll execution plan.
    
    The DecodedPlan provides a human-readable representation of a Weiroll plan,
    with the ability to visualize it in the same tree format as Planner.show_tree().
    It can also be converted back to a Planner object for further operations.
    
    Attributes:
        commands: List of decoded commands
        state: List of state values as hex strings
        
    Example:
        ```python
        # Decode a plan
        plan = planner.plan()
        decoded = Decoder.decode_plan(plan["commands"], plan["state"])
        
        # View it in tree format
        print(decoded.show_tree())
        
        # Convert back to a Planner if needed
        new_planner = Decoder.to_planner(decoded)
        ```
    """
    commands: List[DecodedCommand]
    state: List[str]
    
    def __str__(self) -> str:
        """Format the plan for human-readable output."""
        # Now we just use the tree format by default
        return self.show_tree()
        
    def __repr__(self) -> str:
        """Provide a concise representation for debugging."""
        return f"DecodedPlan(commands={len(self.commands)}, state_size={len(self.state)})"
        
    def show_tree(self) -> str:
        """
        Display the execution plan as a tree, showing data dependencies.
        
        Returns:
            str: A formatted string representation of the execution tree
        """
        if not self.commands:
            return "Empty plan (no commands)"
            
        # Convert decoded commands to the format expected by the renderer
        commands_for_renderer = []
        call_types = []
        
        for cmd in self.commands:
            commands_for_renderer.append({
                "to": cmd.target,
                "function": cmd.function.get('signature') if cmd.function else None,
                "selector": cmd.selector,
                "inputs": cmd.inputs,
                "outputs": [cmd.output] if cmd.output is not None else []
            })
            call_types.append(cmd.call_type)
            
        # Use the common renderer
        return render_tree(commands_for_renderer, self.state, call_types)


class Decoder:
    """
    Decoder for Weiroll commands and plans.
    
    This class provides utilities to decode Weiroll commands and plans
    into human-readable formats. The decoded plan's `show_tree()` method
    provides the same tree visualization as the Planner.show_tree() method.
    
    Example:
        ```python
        # Generate a plan
        planner = Planner()
        # ... add operations ...
        plan = planner.plan()
        
        # Decode the plan for visualization
        decoded_plan = Decoder.decode_plan(plan["commands"], plan["state"])
        
        # View as a tree (same format as planner.show_tree())
        print(decoded_plan)  # __str__ now uses show_tree() format
        
        # You can also convert back to a Planner if needed
        new_planner = Decoder.to_planner(decoded_plan)
        ```
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
        
        # Target address for possible function lookup
        target_address = to_checksum_address(cmd.target)
        selector = to_hex(cmd.function_selector)
        
        # Try to get function info
        function_info = None
        
        # Try to look up with ape if available
        contract = ApeContract(target_address)
        # Try to get the signature from the contract's identifier_lookup
        # Try to use decode_input to get the correct function signature
        try:
            # Log the selector for debugging
            logger.debug(f"Processing selector: {selector}")
            
            # Try to get the function info from identifier_lookup
            if hasattr(contract, 'identifier_lookup') and selector in contract.identifier_lookup:
                identifier = contract.identifier_lookup[selector]
                function_signature = identifier.signature
                function_name = identifier.name
                logger.debug(f"Matched function via identifier_lookup: {function_signature}")
            else:
                # Use decode_input with enough data for the function to be identified
                try:
                    selector_bytes = bytes.fromhex(selector[2:] if selector.startswith('0x') else selector)
                    # Add more placeholders to handle functions with multiple args
                    min_calldata = selector_bytes + b'\x00' * 128  # 4 parameters x 32 bytes
                    
                    # Try to get the function signature from decode_input
                    decoded_input = contract.decode_input(min_calldata)
                    if decoded_input and len(decoded_input) > 0:
                        # First element is the function signature string
                        function_signature = decoded_input[0]
                        function_name = function_signature.split('(')[0]
                        logger.debug(f"Matched function via decode_input: {function_signature}")
                    else:
                        # If no signature found, use a generic one
                        function_name = f"function"
                        function_signature = f"function({selector})"
                        logger.debug(f"Using generic function signature for selector: {selector}")
                except Exception as e:
                    logger.debug(f"Error in decode_input: {e}")
                    # Fall back to a simpler selector-based name
                    function_name = f"function"
                    function_signature = f"function({selector})"
            
            function_info = {
                'name': function_name,
                'signature': function_signature,
                'selector': selector  # Keep the original selector
                }
        except Exception as e:
            logger.debug(f"Error looking up function by identifier: {e}")
        
        return DecodedCommand(
            selector=selector,
            target=target_address,
            call_type=call_type_names[cmd.call_type],
            inputs=input_indices,
            output=output_index,
            is_tuple_return=cmd.is_tuple_return,
            is_extended=cmd.extended_inputs,
            raw_command=to_hex(command_data) if isinstance(command_data, bytes) else command_data,
            function=function_info
        )
    
    @staticmethod
    def decode_plan(
        commands: List[Union[str, bytes]], 
        state: List[str],
        lookup_function_info: bool = True
    ) -> DecodedPlan:
        """
        Decode a full Weiroll plan.
        
        Args:
            commands: List of command data (bytes32 or hex strings)
            state: List of state values
            lookup_function_info: Whether to try to lookup additional function info
            
        Returns:
            DecodedPlan: A decoded plan with human-readable information
        """
        # First decode commands with basic information
        decoded_commands = [Decoder.decode_command(cmd) for cmd in commands]
        
        # Clean up state values for display
        clean_state = []
        for value in state:
            if isinstance(value, bytes):
                clean_state.append(to_hex(value))
            else:
                clean_state.append(value)
                
        # If lookup_function_info is True, try to enhance command info
        if lookup_function_info:
            # Create a dictionary of target addresses
            target_addresses = {}
            for cmd in decoded_commands:
                if cmd.target not in target_addresses:
                    target_addresses[cmd.target] = []
                target_addresses[cmd.target].append(cmd)
                
            # For each target address, try to get ABI and function info in bulk
            for target, cmds in target_addresses.items():
                # Try with ape if available
                contract = ApeContract(target)
                    
                # For each command targeting this contract
                for cmd in cmds:
                    # Only process if function info not already set
                    if not cmd.function:
                        # Try to get the signature from the contract's identifier_lookup
                        # Try to use decode_input to get the correct function signature for this selector
                        try:
                            # Check identifier_lookup first (most reliable)
                            selector = cmd.selector
                            logger.debug(f"Processing selector in decode_plan: {selector}")
                            
                            # Use identifier lookup when available
                            if hasattr(contract, 'identifier_lookup') and selector in contract.identifier_lookup:
                                # Get function details from identifier lookup
                                identifier = contract.identifier_lookup[selector]
                                function_signature = identifier.signature
                                function_name = identifier.name
                                logger.debug(f"Matched function via identifier_lookup: {function_signature}")
                            else:
                                # Try to get a better signature from decode_input
                                try:
                                    selector_bytes = bytes.fromhex(selector[2:] if selector.startswith('0x') else selector)
                                    # Use more zeros to handle functions with multiple parameters
                                    min_calldata = selector_bytes + b'\x00' * 128  # Support up to 4 parameters
                                    
                                    # Use decode_input to get the function signature
                                    decoded_input = contract.decode_input(min_calldata)
                                    if decoded_input and len(decoded_input) > 0:
                                        # First element is the function signature string
                                        function_signature = decoded_input[0]
                                        function_name = function_signature.split('(')[0]
                                        logger.debug(f"Matched via decode_input: {function_signature}")
                                    else:
                                        # Default fallback if no signature found
                                        function_signature = f"function({selector})"
                                        function_name = "function"
                                except Exception as e:
                                    logger.debug(f"Error using decode_input: {e}")
                                    # Fall back to a basic name
                                    function_signature = f"function({selector})"
                                    function_name = "function"
                            
                            cmd.function = {
                                'name': function_name,
                                'signature': function_signature,
                                'selector': selector  # Keep the original selector
                                }
                        except Exception as e:
                            logger.debug(f"Error using decode_input for cmd: {e}")
                            if hasattr(contract, 'identifier_lookup') and cmd.selector in contract.identifier_lookup:
                                identifier = contract.identifier_lookup[cmd.selector]
                                cmd.function = {
                                    'name': identifier.name,
                                    'signature': identifier.signature,
                                    'selector': cmd.selector  # Use the actual selector from the command
                                    }
        
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
    ) -> DecodedCommand:
        """
        Decode a command with ABI information for enhanced readability.
        
        Args:
            command_data: The command data to decode (bytes32 or hex string)
            abi: The ABI for the target contract (optional if contract_address is provided)
            contract_address: The contract address to look up (optional if abi is provided)
            
        Returns:
            DecodedCommand: A decoded command with human-readable information
        """
        # First get a basic decoded command
        decoded = Decoder.decode_command(command_data)
        
        # Use contract address from decoded command if not provided
        if not contract_address:
            contract_address = decoded.target
        
        # Find the function in the ABI using one of several approaches
        fn_selector = decoded.selector
        fn_info = None
        function_signature = None
        
        # Only attempt to look up if not already found
        if not decoded.function:
            # 1. Try to get the function signature from the contract's identifier_lookup
            contract = ApeContract(contract_address)
            # Try to use decode_input to get the correct function signature for this selector
            try:
                # For the deposit selector specifically, handle different versions
                logger.debug(f"Processing selector in decode_command_with_abi: {fn_selector}")
                
                if fn_selector.lower() == "0xb6b55f25":  # deposit(uint256)
                    function_signature = "deposit(uint256)"
                    function_name = "deposit"
                    logger.debug(f"Matched deposit(uint256) selector in decode_command_with_abi: {fn_selector}")
                elif fn_selector.lower() == "0x6e553f65":  # deposit(uint256,address)
                    function_signature = "deposit(uint256,address)"
                    function_name = "deposit"
                    logger.debug(f"Matched deposit(uint256,address) selector in decode_command_with_abi: {fn_selector}")
                else:
                    # For other selectors, use decode_input
                    selector_bytes = bytes.fromhex(fn_selector[2:] if fn_selector.startswith('0x') else fn_selector)
                    min_calldata = selector_bytes + b'\x00' * 32  # Add one parameter of zeros
                    
                    # Use decode_input to get the function signature
                    decoded_input = contract.decode_input(min_calldata)
                    if decoded_input and len(decoded_input) > 0:
                        # First element is the function signature string
                        function_signature = decoded_input[0]
                        function_name = function_signature.split('(')[0]
                    
                    decoded.function = {
                        "name": function_name,
                        "signature": function_signature,
                        "selector": fn_selector  # Keep the original selector
                        }
            except Exception as e:
                # Fall back to identifier_lookup if decode_input fails
                logger.debug(f"Error using decode_input in decode_command_with_abi: {e}")
                if hasattr(contract, 'identifier_lookup') and fn_selector in contract.identifier_lookup:
                    identifier = contract.identifier_lookup[fn_selector]
                    function_signature = identifier.signature
                    # Use the actual selector from the command to ensure we get the correct function
                    decoded.function = {
                        "name": identifier.name,
                        "signature": function_signature,
                        "selector": fn_selector
                    }
        
        # 2. Try to find the function in the provided ABI
        if not decoded.function and abi:
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
                        
                        # Set function info on the decoded command
                        decoded.function = {
                            "name": name,
                            "signature": function_signature,
                            "inputs": inputs,
                            "outputs": item.get("outputs")
                        }
                        break
            
            # 3. Try to use 4byte.directory API or other signature sources
            # We'll only implement this placeholder for now - future enhancement
            if not decoded.function and not function_signature:
                # Placeholder for possible future enhancement:
                # - Query 4byte.directory API
                # - Use local signature database
                # - Check etherscan API
                pass
            
            # Add minimal function info if only signature is available
            if not decoded.function and function_signature:
                name = function_signature.split("(")[0]
                decoded.function = {
                    "name": name,
                    "signature": function_signature
                }
        
        return decoded
        
    @staticmethod
    def to_planner(decoded_plan: DecodedPlan) -> 'Planner':
        """
        Convert a DecodedPlan back to a Planner object.
        
        This allows reconstructing a Planner from a previously decoded plan,
        enabling further operations on the plan.
        
        Note: This is a best-effort reconstruction. Some information might not
        be perfectly preserved, especially for complex state values.
        
        Args:
            decoded_plan: The decoded plan to convert
            
        Returns:
            Planner: A reconstructed Planner object
            
        Example:
            ```python
            # Decode a plan
            plan = planner.plan()
            decoded = Decoder.decode_plan(plan["commands"], plan["state"])
            
            # Display it
            print(decoded.show_tree())
            
            # Convert back to a Planner for additional operations
            new_planner = Decoder.to_planner(decoded)
            ```
        """
        # Import here to avoid circular import
        from .planner import Planner
        from .command import Command, CommandArg
        from .constants import CallType
        
        planner = Planner()
        
        # Reconstruct the state array
        for state_value in decoded_plan.state:
            planner.state.append(state_value)
        
        # Find the highest state index to set next_state_index
        max_state_index = 0
        for cmd in decoded_plan.commands:
            if cmd.output is not None and cmd.output > max_state_index:
                max_state_index = cmd.output
            for inp in cmd.inputs:
                if inp > max_state_index:
                    max_state_index = inp
                    
        planner.next_state_index = max_state_index + 1
        
        # Reconstruct the commands
        for decoded_cmd in decoded_plan.commands:
            # Map string call type back to enum
            call_type_map = {
                "DELEGATECALL": CallType.DELEGATECALL,
                "CALL": CallType.CALL, 
                "STATICCALL": CallType.STATICCALL,
                "VALUECALL": CallType.VALUECALL
            }
            call_type = call_type_map.get(decoded_cmd.call_type, CallType.CALL)
            
            # Convert selector and target from hex strings to bytes
            selector_bytes = bytes.fromhex(decoded_cmd.selector[2:] if decoded_cmd.selector.startswith('0x') else decoded_cmd.selector)
            
            # Extract the last 20 bytes of the target address (in case it's not properly formatted)
            target_hex = decoded_cmd.target[2:] if decoded_cmd.target.startswith('0x') else decoded_cmd.target
            if len(target_hex) > 40:  # More than 20 bytes
                target_hex = target_hex[-40:]  # Take last 20 bytes
            target_bytes = bytes.fromhex(target_hex.zfill(40))  # Ensure it's 20 bytes
            
            # Reconstruct input arguments
            input_args = []
            for arg_index in decoded_cmd.inputs:
                # We have to guess if it's dynamic (best effort)
                state_val = planner.state[arg_index] if arg_index < len(planner.state) else None
                is_dynamic = isinstance(state_val, str) and not state_val.startswith('0x')
                input_args.append(CommandArg(index=arg_index, is_dynamic=is_dynamic))
            
            # Reconstruct output argument
            output_arg = None
            if decoded_cmd.output is not None:
                output_arg = CommandArg(index=decoded_cmd.output)
            
            # Create the command
            cmd = Command(
                function_selector=selector_bytes,
                target=target_bytes,
                inputs=input_args,
                output=output_arg,
                call_type=call_type,
                is_tuple_return=decoded_cmd.is_tuple_return,
                extended_inputs=decoded_cmd.is_extended
            )
            
            planner.commands.append(cmd)
            
        return planner