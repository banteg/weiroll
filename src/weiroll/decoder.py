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
        
        # Initialize the result
        result = ["Execution Plan:", ""]
        
        # Find the highest state index
        max_state_index = 0
        for cmd in self.commands:
            if cmd.output is not None and cmd.output > max_state_index:
                max_state_index = cmd.output
            for inp in cmd.inputs:
                if inp > max_state_index:
                    max_state_index = inp
        
        # Create a map of state values to their sources (which command created them)
        state_sources = {}
        state_usage = {i: [] for i in range(max_state_index + 1)}
        
        # Track which commands use which state values
        for i, cmd in enumerate(self.commands):
            # The command produces an output state value
            if cmd.output is not None:
                state_sources[cmd.output] = i
                # Make sure the output index is in state_usage
                if cmd.output not in state_usage:
                    state_usage[cmd.output] = []
            
            # Record which state values this command uses
            for arg_index in cmd.inputs:
                # Make sure the index is in state_usage
                if arg_index not in state_usage:
                    state_usage[arg_index] = []
                state_usage[arg_index].append(i)
        
        # Create a list of formatted lines for each command
        for i, cmd in enumerate(self.commands):
            # Format the command
            target_address = cmd.target
            selector_hex = cmd.selector
            
            # Try to extract function name from selector if available
            fn_name = f"function({selector_hex})"
            
            # Get function name from extended information if available
            if hasattr(cmd, 'function') and cmd.function is not None and 'signature' in cmd.function:
                fn_name = cmd.function['signature']
            
            # Format the command with its index
            line = [f"Command {i}: {fn_name} @ {target_address} [{cmd.call_type}]"]
            
            # Add input arguments
            if cmd.inputs:
                input_lines = []
                for j, arg_index in enumerate(cmd.inputs):
                    source_str = ""
                    if arg_index in state_sources and state_sources[arg_index] != i:
                        # This input comes from another command's output
                        source_cmd = state_sources[arg_index]
                        source_str = f" (from Command {source_cmd} output)"
                    
                    # Add the value if it's a literal
                    value_str = ""
                    if arg_index < len(self.state) and arg_index not in state_sources:
                        state_value = self.state[arg_index]
                        # Format nicely based on value
                        if state_value.startswith("0x"):
                            # Ethereum address or hex value
                            if len(state_value) > 20:
                                value_str = f" = {state_value[:10]}...{state_value[-8:]}"
                            else:
                                value_str = f" = {state_value}"
                        elif state_value == "":
                            value_str = " = None"
                        else:
                            value_str = f" = {state_value}"
                    
                    # Format based on the function signature if known
                    arg_name = ""
                    if "(" in fn_name and ")" in fn_name:
                        try:
                            # Try to extract parameter names from the signature
                            parts = fn_name.split("(", 1)
                            if len(parts) > 1:
                                params_str = parts[1].split(")", 1)[0]
                                params = params_str.split(",")
                                # If this is a value call with a value argument at index 0,
                                # adjust the parameter index
                                param_index = j
                                if cmd.call_type == "VALUECALL" and j > 0:
                                    param_index = j - 1  # Skip the value parameter
                                
                                if param_index < len(params):
                                    param_type = params[param_index]
                                    if param_type == "address":
                                        arg_name = " (address)"
                                    elif param_type.startswith("uint"):
                                        arg_name = f" ({param_type})"
                        except (IndexError, ValueError):
                            # Ignore formatting errors with function signatures
                            pass
                    
                    # If this is the first argument of a VALUECALL, it's the ETH value
                    if cmd.call_type == "VALUECALL" and j == 0:
                        input_lines.append(f"  ├─ Value: {value_str if value_str else 'State[' + str(arg_index) + ']'}{source_str}")
                    else:
                        prefix = "  ├─" if j < len(cmd.inputs) - 1 or cmd.output is not None else "  └─"
                        input_lines.append(f"{prefix} Input {j}{arg_name}: State[{arg_index}]{source_str}{value_str}")
                
                line.extend(input_lines)
            
            # Add output state if any
            if cmd.output is not None:
                uses = state_usage.get(cmd.output, [])
                # Filter out this command itself
                uses = [u for u in uses if u != i]
                
                if uses:
                    target_commands = ", ".join(f"Command {u}" for u in uses)
                    usage_str = f" (→ {target_commands})"
                else:
                    usage_str = " (unused)"
                
                line.append(f"  └─ Output: State[{cmd.output}]{usage_str}")
            
            # Add the command to the result
            result.extend(line)
            result.append("")  # Empty line between commands
            
        return "\n".join(result)


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
        try:
            from ape import Contract as ApeContract
            try:
                contract = ApeContract(target_address)
                # Try to get the signature from the contract's identifier_lookup
                if hasattr(contract, 'identifier_lookup') and selector in contract.identifier_lookup:
                    identifier = contract.identifier_lookup[selector]
                    function_info = {
                        'name': identifier.name,
                        'signature': identifier.signature,
                        'selector': identifier.selector
                    }
            except Exception as e:
                logger.debug(f"Error looking up function by identifier: {e}")
        except ImportError:
            # Ape not available, skip this lookup
            pass
        
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
                try:
                    from ape import Contract as ApeContract
                    contract = ApeContract(target)
                    
                    # For each command targeting this contract
                    for cmd in cmds:
                        # Only process if function info not already set
                        if not cmd.function:
                            # Try to get the signature from the contract's identifier_lookup
                            if hasattr(contract, 'identifier_lookup') and cmd.selector in contract.identifier_lookup:
                                identifier = contract.identifier_lookup[cmd.selector]
                                cmd.function = {
                                    'name': identifier.name,
                                    'signature': identifier.signature,
                                    'selector': identifier.selector
                                }
                except (ImportError, Exception) as e:
                    # Either ape not available or contract lookup failed
                    logger.debug(f"Error enhancing commands for {target}: {e}")
        
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
            try:
                from ape import Contract as ApeContract
                if contract_address:
                    try:
                        contract = ApeContract(contract_address)
                        if hasattr(contract, 'identifier_lookup') and fn_selector in contract.identifier_lookup:
                            identifier = contract.identifier_lookup[fn_selector]
                            function_signature = identifier.signature
                            function_selector = identifier.selector
                            decoded.function = {
                                "name": identifier.name,
                                "signature": function_signature,
                                "selector": function_selector
                            }
                    except Exception as e:
                        logger.debug(f"Error looking up function by identifier: {e}")
            except ImportError:
                pass  # Ape not available
            
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