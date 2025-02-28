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
        
    @singledispatchmethod
    def _encode_state_value(self, value: Any, index: int) -> str:
        """
        Encode a state value for VM execution.
        
        Args:
            value: The value to encode
            index: Index of the value in the state array
            
        Raises:
            ValueError: If the value type is not supported
        """
        raise ValueError(f"Unsupported state value type at index {index}: {type(value)}")
    
    @_encode_state_value.register
    def _(self, value: type(None), index: int) -> str:
        """Encode None values as empty."""
        return '0x'
        
    @_encode_state_value.register(int)
    @_encode_state_value.register(bool)
    def _(self, value: Union[int, bool], index: int) -> str:
        """Encode integers and booleans as uint256."""
        if isinstance(value, bool):
            value = int(value)
        return '0x' + encode(['uint256'], [value]).hex()
        
    @_encode_state_value.register(str)
    def _(self, value: str, index: int) -> str:
        """Encode strings."""
        if value.startswith('0x'):
            return value
        return '0x' + encode(['string'], [value]).hex()
        
    @_encode_state_value.register(bytes)
    def _(self, value: bytes, index: int) -> str:
        """Encode raw bytes."""
        return '0x' + value.hex()
        
    @_encode_state_value.register(list)
    def _(self, value: list, index: int) -> str:
        """Encode lists/arrays."""
        if all(isinstance(x, int) for x in value):
            # Array of integers
            return '0x' + encode(['uint256[]'], [value]).hex()
        elif all(isinstance(x, str) and x.startswith('0x') for x in value):
            # Array of addresses (0x-prefixed strings)
            return '0x' + encode(['address[]'], [value]).hex()
        else:
            raise ValueError(f"Unsupported array type at index {index} - arrays must contain only integers or Ethereum addresses")
    
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
        
        # Encode commands
        for cmd in self.commands:
            encoded_commands.append('0x' + cmd.encode().hex())
        
        # Encode state
        for i, value in enumerate(self.state):
            try:
                encoded_state.append(self._encode_state_value(value, i))
            except ValueError as e:
                # Re-raise with better error message
                raise ValueError(f"Failed to encode state at index {i}: {e}")
        
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