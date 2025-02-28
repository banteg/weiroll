from typing import Any, Literal

from ape import Contract as ApeContract
from eth_abi import encode

from .command import Command, CommandArg
from .constants import CallType
from .contract import FunctionCall, StateValue
from .utils.tree_renderer import render_tree


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
        self.commands: list[Command] = []
        self.state: list[Any] = []
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
        input_args: list[CommandArg] = []

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
                is_dynamic = isinstance(arg, bytes | str | list | tuple)
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
            call_type=fn_call.call_type,
        )

        self.commands.append(command)
        return output

    # We're now using direct type checking in the plan() method instead of singledispatchmethod

    def plan(self) -> dict[Literal["commands", "state"], list[str]]:
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
        print("DEBUG - State array contents:")
        for i, value in enumerate(self.state):
            print(f"DEBUG - State[{i}]: {value!r}, type: {type(value).__name__}")

        # Encode commands
        for cmd in self.commands:
            encoded_commands.append("0x" + cmd.encode().hex())

        # Encode state
        for i, value in enumerate(self.state):
            try:
                # Handle each type directly instead of using singledispatchmethod
                if value is None:
                    encoded_state.append("0x")
                elif isinstance(value, int | bool):
                    # Encode integers and booleans as uint256
                    if isinstance(value, bool):
                        value = int(value)
                    encoded_state.append("0x" + encode(["uint256"], [value]).hex())
                elif isinstance(value, str):
                    if value.startswith("0x"):
                        # Ethereum address or hex value, pass through as is
                        print(f"DEBUG - String value at index {i} starts with 0x, passing through: {value}")
                        encoded_state.append(value)
                    else:
                        # Regular string
                        print(f"DEBUG - Encoding string at index {i} as ABI string: {value}")
                        encoded_state.append("0x" + encode(["string"], [value]).hex())
                elif isinstance(value, bytes):
                    # Raw bytes
                    encoded_state.append("0x" + value.hex())
                elif isinstance(value, list):
                    # Handle arrays
                    if all(isinstance(x, int) for x in value):
                        # Array of integers
                        encoded_state.append("0x" + encode(["uint256[]"], [value]).hex())
                    elif all(isinstance(x, str) and x.startswith("0x") for x in value):
                        # Array of addresses
                        encoded_state.append("0x" + encode(["address[]"], [value]).hex())
                    else:
                        raise ValueError(
                            f"Unsupported array type at index {i} - arrays must contain only integers or Ethereum addresses"
                        )
                else:
                    raise ValueError(f"Unsupported state value type at index {i}: {type(value)}")
            except ValueError as e:
                # Re-raise with better error message
                raise ValueError(f"Failed to encode state at index {i}: {e}")
            except Exception as e:
                # Catch other exceptions for better debugging
                print(
                    f"DEBUG - Exception while encoding value at index {i}: {value!r}, error: {type(e).__name__}: {e!s}"
                )
                raise ValueError(f"Error encoding value at index {i}: {e}")

        # Pad state array to match next_state_index
        while len(encoded_state) < self.next_state_index:
            encoded_state.append("0x")

        return {"commands": encoded_commands, "state": encoded_state}

    def __enter__(self) -> "Planner":
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

        # Convert commands to the format expected by the renderer
        commands_for_renderer = []
        call_types = []

        for _i, cmd in enumerate(self.commands):
            target_address = "0x" + cmd.target.hex()[-40:]
            selector_hex = "0x" + cmd.function_selector.hex()

            # Try to extract the function name from the 4byte selector
            fn_name = f"function({selector_hex})"  # Default if lookup fails

            try:
                # Try to look up with Contract class from ape (if available)
                contract = ApeContract(target_address)

                # Try to get the signature from the contract's identifier_lookup
                if hasattr(contract, "identifier_lookup") and selector_hex in contract.identifier_lookup:
                    fn_name = contract.identifier_lookup[selector_hex].signature
            except Exception:
                # If ape is not available or there's an error, use the default
                pass

            # Format command for renderer
            commands_for_renderer.append(
                {
                    "to": target_address,
                    "function": fn_name,
                    "selector": selector_hex,
                    "inputs": [arg.index for arg in cmd.inputs],
                    "outputs": [cmd.output.index] if cmd.output else [],
                }
            )
            call_types.append(cmd.call_type.name)

        # Use the common renderer
        return render_tree(commands_for_renderer, self.state, call_types)
