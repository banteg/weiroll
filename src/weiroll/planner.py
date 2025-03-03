import logging
from typing import Any, Dict, Literal, Set

from ape import Contract as ApeContract
from eth_abi import encode
from eth_abi.exceptions import EncodingError

from .command import Command, CommandArg
from .constants import ArgType, CallType, CommandType
from .contract import FunctionCall, StateValue, SubplanValue
from .utils.tree_renderer import render_tree

# Set up logging
logger = logging.getLogger(__name__)


class Planner:
    """
    Plans a series of commands for the Weiroll VM.

    This class allows building a sequence of contract calls to be executed
    by the Weiroll VM on-chain.

    Attributes:
        commands: List of commands to execute
        state: List of state values used by commands
        next_state_index: Next available index in the state array
        state_value: Represents the current planner state for use with addSubplan
    """

    def __init__(self):
        self.commands: list[Command] = []
        self.state: list[Any] = []
        self.next_state_index: int = 0

        # Visibility tracking for optimization
        self._command_visibility: Dict[Command, Command] = {}  # Map command to last command that uses its output
        self._literal_visibility: Dict[Any, Command] = {}  # Map literal value to last command that uses it

        # The placeholder for the current planner state
        self.state_value = StateValue(-1, is_dynamic=True)
        self.state_value.to_arg = lambda: CommandArg(index=-1, is_dynamic=True, is_state=True)

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
            token = Contract(token_contract)
            recipient = "0x1234..."
            amount = 1000

            # Add the transfer call to the plan
            result = planner.add(token.transfer(recipient, amount))

            # Use result in another call
            planner.add(another_contract.process_token_transfer(result))
            ```
        """
        # Check arguments for subplans (not allowed in regular add)
        for arg in fn_call.args:
            if isinstance(arg, SubplanValue):
                raise ValueError("SubplanValue arguments can only be used with addSubplan")

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
            call_type=fn_call.call_type,
            command_type=CommandType.CALL,
        )

        self.commands.append(command)
        return output

    def addSubplan(self, fn_call: FunctionCall) -> None:
        """
        Add a call to a subplan. This executes a nested instance of the Weiroll VM.

        Subplans are commonly used for:
        - Flashloans
        - Control flow
        - Callback-based operations

        A function call passed to addSubplan must:
        - Take a SubplanValue (created from a Planner) as one argument
        - Take the planner.state_value as another argument
        - Return either nothing or a bytes[] that will replace the parent planner state

        Args:
            fn_call: The function call containing the subplan

        Example:
            ```python
            # Create main planner
            planner = Planner()

            # Create subplan
            subplan = Planner()
            subplan.add(token.transfer(recipient, amount))

            # Add subplan to the main planner
            planner.addSubplan(flashloan.execute(subplan, planner.state_value))
            ```
        """
        # Check for subplan and state arguments
        has_subplan = False
        has_state = False
        subplan_index = -1

        # Process arguments
        input_args: list[CommandArg] = []

        # Handle value for value calls
        if fn_call.call_type == CallType.VALUECALL and fn_call.fn.value > 0:
            # Add value as first argument
            value_index = self._add_to_state(fn_call.fn.value)
            input_args.append(CommandArg(index=value_index))

        # Process function arguments and check for subplan/state
        for i, arg in enumerate(fn_call.args):
            if isinstance(arg, SubplanValue):
                if has_subplan:
                    raise ValueError("Subplans can only take one planner argument")
                has_subplan = True
                subplan_index = i

                # Create a placeholder for now - we'll replace it during planning
                input_args.append(CommandArg(index=-1, is_dynamic=True, is_subplan=True))
            elif isinstance(arg, StateValue) and arg.to_arg().is_state:
                if has_state:
                    raise ValueError("Subplans can only take one state argument")
                has_state = True

                # Add the state placeholder
                input_args.append(CommandArg(index=-1, is_dynamic=True, is_state=True))
            elif isinstance(arg, StateValue):
                # Use existing state value
                input_args.append(arg.to_arg())
            else:
                # Add literal value to state
                is_dynamic = isinstance(arg, (bytes, str, list, tuple))
                state_index = self._add_to_state(arg, is_dynamic)
                input_args.append(CommandArg(index=state_index, is_dynamic=is_dynamic))

        if not has_subplan or not has_state:
            raise ValueError("Subplans must take planner and state arguments")

        # Verify return type is bytes[] or void
        if fn_call.method_abi.outputs and len(fn_call.method_abi.outputs) > 0:
            output_type = fn_call.method_abi.outputs[0].canonical_type
            if output_type != "bytes[]":
                raise ValueError("Subplans must return a bytes[] replacement state or nothing")

        # Create command
        command = Command(
            function_selector=fn_call.selector,
            target=fn_call.target,
            inputs=input_args,
            output=CommandArg(index=ArgType.USE_STATE),
            call_type=fn_call.call_type,
            command_type=CommandType.SUBPLAN,
        )

        # Store the subplan for later processing
        # We'll encode it during the planning phase
        command.subplan = fn_call.args[subplan_index].planner if has_subplan else None

        self.commands.append(command)

    def replaceState(self, fn_call: FunctionCall) -> None:
        """
        Execute a function call that replaces the planner state with its return value.

        This can be used for functions that make arbitrary changes to the planner state.

        Args:
            fn_call: The function call to execute. Must return bytes[].

        Example:
            ```python
            planner = Planner()
            # Add some initial commands

            # Replace the state with a function call result
            planner.replaceState(processor.processState(planner.state_value))
            ```
        """
        # Verify return type is bytes[]
        if not fn_call.method_abi.outputs or len(fn_call.method_abi.outputs) == 0:
            raise ValueError("Function replacing state must return a value")

        output_type = fn_call.method_abi.outputs[0].canonical_type
        if output_type != "bytes[]":
            raise ValueError("Function replacing state must return a bytes[]")

        # Process arguments
        input_args: list[CommandArg] = []

        # Handle value for value calls
        if fn_call.call_type == CallType.VALUECALL and fn_call.fn.value > 0:
            # Add value as first argument
            value_index = self._add_to_state(fn_call.fn.value)
            input_args.append(CommandArg(index=value_index))

        # Process function arguments
        for arg in fn_call.args:
            if isinstance(arg, StateValue) and arg.to_arg().is_state:
                # Add the state placeholder
                input_args.append(CommandArg(index=-1, is_dynamic=True, is_state=True))
            elif isinstance(arg, StateValue):
                # Use existing state value
                input_args.append(arg.to_arg())
            elif isinstance(arg, SubplanValue):
                raise ValueError("SubplanValue cannot be used with replaceState")
            else:
                # Add literal value to state
                is_dynamic = isinstance(arg, (bytes, str, list, tuple))
                state_index = self._add_to_state(arg, is_dynamic)
                input_args.append(CommandArg(index=state_index, is_dynamic=is_dynamic))

        # Create command
        command = Command(
            function_selector=fn_call.selector,
            target=fn_call.target,
            inputs=input_args,
            output=CommandArg(index=ArgType.USE_STATE),
            call_type=fn_call.call_type,
            command_type=CommandType.RAWCALL,
        )

        self.commands.append(command)

    def _prepare_planning(self) -> None:
        """
        Prepare for planning by building visibility maps.
        This tracks which values are used by which commands.
        """
        # Reset tracking maps
        self._command_visibility = {}
        self._literal_visibility = {}

    def _build_subplan(self, planner: "Planner", seen: Set["Planner"]) -> str:
        """
        Build the subplan commands as a bytes32[] string.

        Args:
            planner: The subplanner to build
            seen: Set of planners already seen (to detect circular references)

        Returns:
            str: The hex-encoded commands as a bytes32[]
        """
        if planner in seen:
            raise ValueError("A planner cannot contain itself")

        # Create a new set with this planner to detect circular references
        new_seen = seen.copy()
        new_seen.add(planner)

        # Build the subplan using the updated seen set to track circular references
        # This is where we'd detect circular references between planners
        try:
            subplan = planner.plan()
            subcommands = subplan["commands"]
        except RecursionError:
            raise ValueError("A planner cannot contain itself (circular reference detected)")

        # Encode the commands as bytes32[]
        try:
            # Convert hex strings to bytes
            bytes_commands = [bytes.fromhex(cmd[2:]) for cmd in subcommands]
            encoded = "0x" + encode(["bytes32[]"], [bytes_commands]).hex()
            # Skip the first 32 bytes which is the offset to the array
            return encoded[66:]
        except Exception as e:
            raise ValueError(f"Failed to encode subplan: {e}")

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
        # First, prepare for planning (build visibility maps)
        self._prepare_planning()

        # Track planners we've seen to detect circular references
        seen_planners = set()

        encoded_commands = []
        encoded_state = []

        # Process commands, handling subplans as needed
        for cmd in self.commands:
            # Handle subplans first, as they may modify inputs
            if cmd.command_type == CommandType.SUBPLAN:
                if not hasattr(cmd, "subplan") or cmd.subplan is None:
                    raise ValueError("Subplan command missing subplan reference")

                # Build and encode the subplan
                encoded_subplan = self._build_subplan(cmd.subplan, seen_planners)

                # Add the encoded subplan to state
                subplan_index = self._add_to_state(bytes.fromhex(encoded_subplan[2:]))

                # Update the subplan argument index
                for i, arg in enumerate(cmd.inputs):
                    if arg.is_subplan:
                        cmd.inputs[i] = CommandArg(index=subplan_index, is_dynamic=True)

            # All inputs should be resolved at this point
            # Encode the command
            encoded_bytes = cmd.encode()
            encoded_commands.append("0x" + encoded_bytes.hex())

        # Encode state values
        for i, value in enumerate(self.state):
            try:
                # Handle each type directly
                if value is None:
                    encoded_state.append("0x")
                elif isinstance(value, (int, bool)):
                    # Encode integers and booleans as uint256
                    if isinstance(value, bool):
                        value = int(value)
                    encoded_state.append("0x" + encode(["uint256"], [value]).hex())
                elif isinstance(value, str):
                    if value.startswith("0x"):
                        # Ethereum address or hex value, pass through as is
                        encoded_state.append(value)
                    else:
                        # Regular string
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
            except EncodingError as e:
                # Re-raise with better error message
                raise ValueError(f"Failed to encode state at index {i}: {e}")
            except Exception as e:
                # Catch other exceptions for better debugging
                logger.debug(
                    f"Exception while encoding value at index {i}: {value!r}, error: {type(e).__name__}: {e!s}"
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
                    "outputs": [cmd.output.index] if cmd.output and cmd.output.index != ArgType.USE_STATE else [],
                    "command_type": cmd.command_type.name,
                }
            )
            # Handle both enum and int call types for backward compatibility
            if hasattr(cmd.call_type, "name"):
                call_types.append(cmd.call_type.name)
            else:
                # Convert int to enum
                call_types.append(CallType(cmd.call_type).name)

        # Use the common renderer
        return render_tree(commands_for_renderer, self.state, call_types)
