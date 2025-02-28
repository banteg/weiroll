from typing import Any, Dict, List, Optional, Tuple, Union, cast, Literal, TypeVar
from functools import singledispatchmethod
from dataclasses import dataclass

from eth_abi import encode
from eth_utils import to_bytes, to_hex

from .command import Command, CommandArg
from .constants import CallType, ArgType
from .contract import FunctionCall, StateValue


class Planner:
    """
    Plans a series of commands for the Weiroll VM.
    
    This class allows building a sequence of contract calls to be executed
    by the Weiroll VM on-chain.
    
    Attributes:
        commands: List of commands to execute
        state: List of state values used by commands
        next_state_index: Next available index in the state array
    """
    
    def __init__(self):
        self.commands: List[Command] = []
        self.state: List[Any] = []
        self.next_state_index: int = 0
    
    def _add_to_state(self, value: Any, is_dynamic: bool = False) -> int:
        """
        Add a value to the state and return its index.
        
        Args:
            value: The value to add to the state
            is_dynamic: Whether the value is a dynamic type (string, bytes, array)
            
        Returns:
            int: The index of the value in the state array
        """
        # Check if the value already exists in the state
        # This implements literal deduplication
        for i, existing_value in enumerate(self.state):
            if existing_value == value:
                return i
                
        state_index = self.next_state_index
        self.state.append(value)
        self.next_state_index += 1
        return state_index
    
    def add(self, fn_call: FunctionCall) -> StateValue:
        """
        Add a function call to the plan and return a reference to its output in state.
        
        Args:
            fn_call: The function call to add
            
        Returns:
            StateValue: A reference to the function's output in the state
            
        Example:
            ```python
            planner = Planner()
            token = Contract.create_contract(token_contract)
            recipient = "0x1234..."
            amount = 1000
            
            # Add the transfer call to the plan
            result = planner.add(token.transfer(recipient, amount))
            
            # Use result in another call
            planner.add(another_contract.process_token_transfer(result))
            ```
        """
        # Process arguments
        input_args: List[CommandArg] = []
        
        # Handle value for value calls
        if fn_call.call_type == CallType.VALUECALL and fn_call.fn.value > 0:
            # Add value as first argument
            value_index = self._add_to_state(fn_call.fn.value)
            input_args.append(CommandArg(index=value_index))
        
        # Process function arguments
        for arg in fn_call.args:
            if isinstance(arg, StateValue):
                # Use existing state value
                input_args.append(arg.to_arg())
            else:
                # Add literal value to state
                is_dynamic = isinstance(arg, (bytes, str, list, tuple))
                state_index = self._add_to_state(arg, is_dynamic)
                input_args.append(CommandArg(index=state_index, is_dynamic=is_dynamic))
        
        # Create output state value
        output_index = self.next_state_index
        output = StateValue(output_index)
        self.next_state_index += 1
        
        # Create command
        command = Command(
            function_selector=fn_call.selector,
            target=fn_call.target,
            inputs=input_args,
            output=CommandArg(index=output_index),
            call_type=fn_call.call_type
        )
        
        self.commands.append(command)
        return output
        
    # We're now using direct type checking in the plan() method instead of singledispatchmethod
    
    def plan(self) -> Dict[Literal["commands", "state"], List[str]]:
        """
        Generate the commands and state for VM execution.
        
        Returns:
            dict: A dictionary with "commands" and "state" keys
            
        Example:
            ```python
            planner = Planner()
            # Add function calls
            plan = planner.plan()
            
            # Access the encoded commands and state
            commands = plan["commands"]
            state = plan["state"]
            ```
        """
        encoded_commands = []
        encoded_state = []
        
        # Debug: print the entire state array
        print(f"DEBUG - State array contents:")
        for i, value in enumerate(self.state):
            print(f"DEBUG - State[{i}]: {repr(value)}, type: {type(value).__name__}")
        
        # Encode commands
        for cmd in self.commands:
            encoded_commands.append('0x' + cmd.encode().hex())
        
        # Encode state
        for i, value in enumerate(self.state):
            try:
                # Handle each type directly instead of using singledispatchmethod
                if value is None:
                    encoded_state.append('0x')
                elif isinstance(value, (int, bool)):
                    # Encode integers and booleans as uint256
                    if isinstance(value, bool):
                        value = int(value)
                    encoded_state.append('0x' + encode(['uint256'], [value]).hex())
                elif isinstance(value, str):
                    if value.startswith('0x'):
                        # Ethereum address or hex value, pass through as is
                        print(f"DEBUG - String value at index {i} starts with 0x, passing through: {value}")
                        encoded_state.append(value)
                    else:
                        # Regular string
                        print(f"DEBUG - Encoding string at index {i} as ABI string: {value}")
                        encoded_state.append('0x' + encode(['string'], [value]).hex())
                elif isinstance(value, bytes):
                    # Raw bytes
                    encoded_state.append('0x' + value.hex())
                elif isinstance(value, list):
                    # Handle arrays
                    if all(isinstance(x, int) for x in value):
                        # Array of integers
                        encoded_state.append('0x' + encode(['uint256[]'], [value]).hex())
                    elif all(isinstance(x, str) and x.startswith('0x') for x in value):
                        # Array of addresses
                        encoded_state.append('0x' + encode(['address[]'], [value]).hex())
                    else:
                        raise ValueError(f"Unsupported array type at index {i} - arrays must contain only integers or Ethereum addresses")
                else:
                    raise ValueError(f"Unsupported state value type at index {i}: {type(value)}")
            except ValueError as e:
                # Re-raise with better error message
                raise ValueError(f"Failed to encode state at index {i}: {e}")
            except Exception as e:
                # Catch other exceptions for better debugging
                print(f"DEBUG - Exception while encoding value at index {i}: {repr(value)}, error: {type(e).__name__}: {str(e)}")
                raise ValueError(f"Error encoding value at index {i}: {e}")
        
        # Pad state array to match next_state_index
        while len(encoded_state) < self.next_state_index:
            encoded_state.append('0x')
        
        return {
            "commands": encoded_commands,
            "state": encoded_state
        }
        
    def __enter__(self) -> 'Planner':
        """Support context manager protocol."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        pass
        
    def __repr__(self) -> str:
        """Return a string representation of the planner."""
        return f"Planner(commands={len(self.commands)}, state_size={len(self.state)})"
        
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
        max_state_index = self.next_state_index - 1
        if self.state:
            max_state_index = max(max_state_index, len(self.state) - 1)
        
        # Create a map of state values to their sources (which command created them)
        state_sources = {}
        state_usage = {i: [] for i in range(max_state_index + 1)}
        
        # Track which commands use which state values
        for i, cmd in enumerate(self.commands):
            # The command produces an output state value
            if cmd.output:
                state_sources[cmd.output.index] = i
                # Make sure the output index is in state_usage
                if cmd.output.index not in state_usage:
                    state_usage[cmd.output.index] = []
            
            # Record which state values this command uses
            for arg in cmd.inputs:
                # Make sure the index is in state_usage
                if arg.index not in state_usage:
                    state_usage[arg.index] = []
                state_usage[arg.index].append(i)
        
        # Create a list of formatted lines for each command
        for i, cmd in enumerate(self.commands):
            # Format the command
            target_address = "0x" + cmd.target.hex()[-40:]
            selector_hex = "0x" + cmd.function_selector.hex()
            
            # Try to extract the function name from the 4byte selector
            # First, check if there's a contract available
            try:
                # Try to look up with Contract class from ape (if available)
                from ape import Contract as ApeContract
                contract = ApeContract(target_address)
                
                # Try to get the signature from the contract's identifier_lookup
                if hasattr(contract, 'identifier_lookup') and selector_hex in contract.identifier_lookup:
                    fn_name = contract.identifier_lookup[selector_hex].signature
                else:
                    # Common Ethereum function signatures
                    common_signatures = {
                        "0x095ea7b3": "approve(address,uint256)",
                        "0xa9059cbb": "transfer(address,uint256)",
                        "0x23b872dd": "transferFrom(address,address,uint256)",
                        "0x70a08231": "balanceOf(address)",
                        "0xdd62ed3e": "allowance(address,address)",
                        "0x313ce567": "decimals()",
                        "0x06fdde03": "name()",
                        "0x95d89b41": "symbol()",
                        "0x18160ddd": "totalSupply()",
                        "0x6b62f89f": "deposit(uint256)",
                        "0x2e1a7d4d": "withdraw(uint256)",
                        "0xa694fc3a": "stake(uint256)",
                        "0xadc9772e": "withdraw(address,uint256)",
                        "0xd0e30db0": "deposit()",
                        "0x9dc29fac": "burn(address,uint256)",
                        "0xbd6d894d": "mint(address,uint256)",
                        "0x9b4e4634": "stake(bytes,bytes,bytes32)",
                    }
                    fn_name = common_signatures.get(selector_hex, f"function({selector_hex})")
            except (ImportError, Exception):
                # If ape is not available or there's an error, fall back to hardcoded signatures
                common_signatures = {
                    "0x095ea7b3": "approve(address,uint256)",
                    "0xa9059cbb": "transfer(address,uint256)",
                    "0x23b872dd": "transferFrom(address,address,uint256)",
                    "0x70a08231": "balanceOf(address)",
                    "0xdd62ed3e": "allowance(address,address)",
                    "0x313ce567": "decimals()",
                    "0x06fdde03": "name()",
                    "0x95d89b41": "symbol()",
                    "0x18160ddd": "totalSupply()",
                    "0x6b62f89f": "deposit(uint256)",
                    "0x2e1a7d4d": "withdraw(uint256)",
                    "0xa694fc3a": "stake(uint256)",
                    "0xadc9772e": "withdraw(address,uint256)",
                    "0xd0e30db0": "deposit()",
                    "0x9dc29fac": "burn(address,uint256)",
                    "0xbd6d894d": "mint(address,uint256)",
                    "0x9b4e4634": "stake(bytes,bytes,bytes32)",
                }
                fn_name = common_signatures.get(selector_hex, f"function({selector_hex})")
            
            # Format the command with its index
            line = [f"Command {i}: {fn_name} @ {target_address} [{cmd.call_type.name}]"]
            
            # Add input arguments
            if cmd.inputs:
                input_lines = []
                for j, arg in enumerate(cmd.inputs):
                    source_str = ""
                    if arg.index in state_sources and state_sources[arg.index] != i:
                        # This input comes from another command's output
                        source_cmd = state_sources[arg.index]
                        source_str = f" (from Command {source_cmd} output)"
                    
                    # Add the value if it's a literal
                    value_str = ""
                    if arg.index < len(self.state) and arg.index not in state_sources:
                        try:
                            # Try to format the value nicely
                            value = self.state[arg.index]
                            if value is None:
                                value_str = " = None"
                            elif isinstance(value, str) and value.startswith("0x"):
                                # Format addresses nicely
                                value_str = f" = {value[:10]}...{value[-8:]}" if len(value) > 20 else f" = {value}"
                            elif isinstance(value, int):
                                # Format large integers with commas and check for units
                                if value > 10**18 and value % 10**18 == 0:
                                    value_str = f" = {value // 10**18} tokens (10^18 units)"
                                elif value > 10**9 and value % 10**9 == 0:
                                    value_str = f" = {value // 10**9} Gwei (10^9 units)"
                                else:
                                    value_str = f" = {value:,}"
                            elif isinstance(value, (list, tuple)):
                                if len(value) <= 3:
                                    items = ", ".join(str(x)[:20] for x in value)
                                    value_str = f" = [{items}]"
                                else:
                                    value_str = f" = [{len(value)} items]"
                            else:
                                value_str = f" = {value}"
                        except Exception as e:
                            # Add a debug message but continue
                            print(f"DEBUG - Error formatting value at index {arg.index}: {e}")
                            pass
                    
                    # Format based on the function signature if known
                    arg_name = ""
                    if "(" in fn_name and ")" in fn_name:
                        # Try to extract parameter names from the signature
                        params_str = fn_name.split("(")[1].split(")")[0]
                        params = params_str.split(",")
                        # If this is a value call with a value argument at index 0,
                        # adjust the parameter index
                        param_index = j
                        if cmd.call_type.name == "VALUECALL" and j > 0:
                            param_index = j - 1  # Skip the value parameter
                        
                        if param_index < len(params):
                            param_type = params[param_index]
                            if param_type == "address":
                                arg_name = " (address)"
                            elif param_type.startswith("uint"):
                                arg_name = f" ({param_type})"
                    
                    # If this is the first argument of a VALUECALL, it's the ETH value
                    if cmd.call_type.name == "VALUECALL" and j == 0:
                        input_lines.append(f"  ├─ Value: {value_str if value_str else 'State[' + str(arg.index) + ']'}{source_str}")
                    else:
                        prefix = "  ├─" if j < len(cmd.inputs) - 1 or cmd.output else "  └─"
                        input_lines.append(f"{prefix} Input {j}{arg_name}: State[{arg.index}]{source_str}{value_str}")
                
                line.extend(input_lines)
            
            # Add output state if any
            if cmd.output:
                uses = state_usage.get(cmd.output.index, [])
                # Filter out this command itself
                uses = [u for u in uses if u != i]
                
                if uses:
                    target_commands = ", ".join(f"Command {u}" for u in uses)
                    usage_str = f" (→ {target_commands})"
                else:
                    usage_str = " (unused)"
                
                line.append(f"  └─ Output: State[{cmd.output.index}]{usage_str}")
            
            # Add the command to the result
            result.extend(line)
            result.append("")  # Empty line between commands
            
        return "\n".join(result)