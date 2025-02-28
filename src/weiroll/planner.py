from typing import Any, Dict, List, Optional, Tuple, Union, cast

from eth_abi import encode
from eth_utils import to_bytes, to_hex

from .command import Command, CommandArg
from .constants import CallType, ArgType
from .contract import FunctionCall, StateValue


class Planner:
    """Plans a series of commands for the Weiroll VM."""
    
    def __init__(self):
        self.commands: List[Command] = []
        self.state: List[Any] = []
        self.next_state_index: int = 0
    
    def _add_to_state(self, value: Any, is_dynamic: bool = False) -> int:
        """Add a value to the state and return its index."""
        state_index = self.next_state_index
        self.state.append(value)
        self.next_state_index += 1
        return state_index
    
    def add(self, fn_call: FunctionCall) -> StateValue:
        """Add a function call to the plan and return a reference to its output in state."""
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
    
    def plan(self) -> Dict[str, Any]:
        """Generate the commands and state for VM execution."""
        encoded_commands = []
        encoded_state = []
        
        # Encode commands
        for cmd in self.commands:
            encoded_commands.append('0x' + cmd.encode().hex())
        
        # Encode state
        for i, value in enumerate(self.state):
            if value is None:
                # Empty placeholder for output values
                encoded_state.append('0x')
                continue
                
            if isinstance(value, (int, bool)):
                # Encode integers and booleans as uint256
                encoded_state.append('0x' + encode(['uint256'], [value]).hex())
            elif isinstance(value, str) and value.startswith('0x'):
                # Handle hex strings
                encoded_state.append(value)
            elif isinstance(value, bytes):
                # Handle raw bytes
                encoded_state.append('0x' + value.hex())
            elif isinstance(value, str):
                # Handle strings
                encoded_state.append('0x' + encode(['string'], [value]).hex())
            elif isinstance(value, list):
                # Handle arrays (simplified - assumes homogeneous types)
                if all(isinstance(x, int) for x in value):
                    encoded_state.append('0x' + encode(['uint256[]'], [value]).hex())
                else:
                    raise ValueError(f"Unsupported array type at index {i}")
            else:
                raise ValueError(f"Unsupported state value type at index {i}: {type(value)}")
        
        # Pad state array to match next_state_index
        while len(encoded_state) < self.next_state_index:
            encoded_state.append('0x')
        
        return {
            "commands": encoded_commands,
            "state": encoded_state
        }