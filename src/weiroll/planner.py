import logging
from typing import Any, Optional, Set

from ape import Contract as ApeContract
from eth_abi import encode
from eth_abi.exceptions import EncodingError

from .command import Command, CommandArg
from .constants import ArgType, CallType, CommandType
from .contract import FunctionCall, StateValue, SubplanValue
from .utils.tree_renderer import render_tree
from .utils.html_renderer import render_html

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

        # The placeholder for the current planner state
        self.state_value = StateValue(-1, is_dynamic=True)
        self.state_value.to_arg = lambda: CommandArg(index=-1, is_dynamic=True, is_state=True)

    def _add_to_state(self, value: Any, is_dynamic: bool = False) -> int:
        """
        Add a value to the state and return its index.

        Performs deduplication by checking if the value already exists in the state.
        If so, returns the existing index. Otherwise, adds the value to the state
        and returns the new index.

        Args:
            value: The value to add (int, bool, str, bytes, list, etc.)
            is_dynamic: Whether the value is a dynamic type (string, bytes, array)
                        that requires special handling during encoding

        Returns:
            int: Index of the value in the state array
        """
        # Try to deduplicate values
        for i, existing_value in enumerate(self.state):
            if existing_value == value:
                return i

        # Add value to state
        state_index = self.next_state_index
        self.state.append(value)
        self.next_state_index += 1
        return state_index

    def add(self, fn_call: FunctionCall) -> StateValue | None:
        """
        Add a function call to the plan and return a reference to its output in state.

        This method processes the function call, validates arguments, creates the appropriate
        command, and adds it to the planner's command list. If the function has outputs,
        a state slot is allocated and a StateValue reference is returned. If the function
        has no outputs, None is returned.

        Args:
            fn_call: The function call to add to the plan

        Returns:
            StateValue: A reference to the function's output in the state, or None if the
                       function has no outputs.

        Raises:
            TypeError: If fn_call is not a FunctionCall instance
            ValueError: If SubplanValue arguments are used (not allowed in regular add)

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
        # Validate input - ensure required attributes exist
        for attr in ["selector", "target", "args", "method_abi", "call_type"]:
            if not hasattr(fn_call, attr):
                raise TypeError(f"Expected a FunctionCall-like object with '{attr}' attribute")

        # Check arguments for subplans (not allowed in regular add)
        for i, arg in enumerate(fn_call.args):
            if isinstance(arg, SubplanValue):
                raise ValueError(f"Argument {i}: SubplanValue arguments can only be used with addSubplan")

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

        # Find out if this call has output
        output = None
        output_arg = None

        # Handle tuple return for raw_value() calls
        if getattr(fn_call, "is_tuple_return", False):
            # For raw_value, we always create a state value with a bytes type
            output_type = "bytes"
            # Create state value with source tracking information
            output = StateValue(
                index=self.next_state_index,
                is_dynamic=True,  # bytes is dynamic
                # Will set source_command to current command index after we add the command
                output_of=True,
            )
            output_arg = CommandArg(self.next_state_index)
            self.next_state_index += 1
        # Handle normal function outputs
        elif fn_call.method_abi.outputs and len(fn_call.method_abi.outputs) > 0:
            # Normal case - function has outputs defined in ABI
            output_type = fn_call.method_abi.outputs[0].type
            # Create state value with source tracking information
            output = StateValue(
                index=self.next_state_index,
                is_dynamic=isinstance(output_type, (bytes, str)) or output_type in ["bytes", "string"],
                # Will set source_command to current command index after we add the command
                output_of=True,
            )
            output_arg = CommandArg(self.next_state_index)
            self.next_state_index += 1

        # Create command
        command = Command(
            function_selector=fn_call.selector,
            target=fn_call.target,
            inputs=input_args,
            output=output_arg,  # This might be None
            call_type=fn_call.call_type,
            command_type=CommandType.CALL,
            is_tuple_return=getattr(fn_call, "is_tuple_return", False),  # Get is_tuple_return flag if it exists
        )

        # Add command to the list
        command_idx = len(self.commands)
        self.commands.append(command)

        # Set source command reference for tracking dependencies if there's an output
        if output and hasattr(output, "source_command"):
            output.source_command = command_idx

        return output  # This might be None

    def addSubplan(self, fn_call: FunctionCall) -> StateValue:
        """Add a function call with a subplan as an argument.

        This allows creating nested execution plans, which can be used for
        implementing control flow, flashloans, and other callback-based operations.

        Args:
            fn_call: A function call with a SubplanValue as one of its arguments

        Returns:
            StateValue: The output value of the function call

        Examples:
            ```python
            # Implement a flashloan pattern
            flashloan = Contract(flashloan_contract)

            # Create a subplan for the flashloan
            subplan = Planner()
            subplan.add(token.transfer(recipient, 1000))
            subplan.add(token.approve(dex_router, 500))
            subplan.add(dex_router.swapExactTokensForTokens(...))

            # Add subplan to the main planner
            planner.addSubplan(flashloan.execute(subplan, planner.state_value))
            ```
        """
        # Validate input - ensure required attributes exist
        for attr in ["args", "call_type", "fn"]:
            if not hasattr(fn_call, attr):
                raise TypeError(f"Expected a FunctionCall-like object with '{attr}' attribute")

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

    def plan(self) -> dict[str, list[str]]:
        """
        Prepare the execution plan with all commands and state values.

        This method:
        1. Builds the command bytecode for each command in the planner
        2. Encodes all state values to their proper hex string representation
        3. Combines everything into a format ready for VM execution

        Returns:
            dict: A dictionary with two keys:
                - "commands": A list of hex strings representing encoded commands
                - "state": A list of hex strings representing the initial state values

        Example:
            ```python
            planner = Planner()
            # ... add function calls ...

            execution_plan = planner.plan()
            # execution_plan = {
            #     "commands": ["0x123...", "0x456..."],
            #     "state": ["0xabc...", "0xdef..."]
            # }
            ```
        """
        encoded_commands = []
        encoded_state = []

        # Process commands, handling subplans as needed
        for cmd in self.commands:
            # Handle subplans first, as they may modify inputs
            if cmd.command_type == CommandType.SUBPLAN:
                if not hasattr(cmd, "subplan") or cmd.subplan is None:
                    raise ValueError("Subplan command missing subplan reference")

                # Build and encode the subplan
                encoded_subplan = self._build_subplan(cmd.subplan, set())

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

    def show_tree(self, use_color: Optional[bool] = None) -> str:
        """
        Generate a visual representation of the execution plan as a dependency tree.

        Args:
            use_color: Whether to use colors in the output. None for auto-detection,
                       True to force colors, False to disable colors.

        Returns:
            str: A formatted string showing the execution plan as a tree
        """
        if not self.commands:
            return "Empty plan (no commands)"

        # Convert commands to the format expected by the renderer
        commands_for_renderer = []
        call_types = []

        # Track state value sources for better visualization
        source_tracking = {}

        # First pass - collect StateValue objects with source_command information
        for i, value in enumerate(self.state):
            if isinstance(value, StateValue) and hasattr(value, "source_command") and value.source_command >= 0:
                source_tracking[i] = value.source_command

        for _i, cmd in enumerate(self.commands):
            target_address = "0x" + cmd.target.hex()[-40:]
            selector_hex = "0x" + cmd.function_selector.hex()

            # Check if command has function_info from decoder
            if hasattr(cmd, "function_info") and cmd.function_info:
                fn_name = cmd.function_info.get("signature") or f"function({selector_hex})"
            else:
                # Try to extract the function name from the 4byte selector (legacy approach)
                fn_name = f"function({selector_hex})"  # Default if lookup fails

                contract_name = ""
                try:
                    # Try to look up with Contract class from ape (if available)
                    contract = ApeContract(target_address)

                    # Try to get the signature from the contract's identifier_lookup
                    if hasattr(contract, "identifier_lookup") and selector_hex in contract.identifier_lookup:
                        fn_name = contract.identifier_lookup[selector_hex].signature

                    # Try to get the contract name - prioritize name() function first
                    name_found = False

                    # Try to get the name from name() function first
                    if hasattr(contract, "name") and callable(getattr(contract, "name")):
                        try:
                            # Try to call name() properly - needs to be called as a method
                            contract_name = contract.name()
                            name_found = True
                        except Exception:
                            # name() call failed, try with symbol() as fallback
                            if hasattr(contract, "symbol") and callable(getattr(contract, "symbol")):
                                try:
                                    # Try to get symbol as a fallback for name
                                    contract_name = contract.symbol()
                                    name_found = True
                                except Exception:
                                    pass

                    # If name() failed, fall back to contract_type.name
                    if not name_found and hasattr(contract, "contract_type") and contract.contract_type.name:
                        contract_name = contract.contract_type.name
                except Exception:
                    # If ape is not available or there's an error, use the default
                    pass

            # Format command for renderer with enhanced tracking info
            command_dict = {
                "to": target_address,
                "function": fn_name,
                "selector": selector_hex,
                "inputs": [arg.index for arg in cmd.inputs],
                "outputs": [cmd.output.index] if cmd.output and cmd.output.index != ArgType.USE_STATE else [],
                "command_type": cmd.command_type.name,
                "contract_name": contract_name,  # Add contract name if available
            }

            # Add source tracking info for command inputs
            input_sources = []
            for arg in cmd.inputs:
                # Check if this input has a known source
                if isinstance(arg.index, int) and arg.index in source_tracking:
                    input_sources.append(source_tracking[arg.index])
                else:
                    input_sources.append(-1)  # No known source
            command_dict["input_sources"] = input_sources

            commands_for_renderer.append(command_dict)

            # Handle both enum and int call types for backward compatibility
            if hasattr(cmd.call_type, "name"):
                call_types.append(cmd.call_type.name)
            else:
                # Convert int to enum
                call_types.append(CallType(cmd.call_type).name)

            # Track sources for output values
            if cmd.output and cmd.output.index != ArgType.USE_STATE:
                source_tracking[cmd.output.index] = _i

        # Use the common renderer with enhanced tracking info
        return render_tree(commands_for_renderer, self.state, call_types, use_color=use_color)

    def _repr_html_(self) -> str:
        """
        Generate an HTML representation of the execution plan for display in notebooks.

        This method is automatically called by notebook environments like Jupyter and Marimo
        when they need to display the object. It provides a rich HTML representation with
        proper formatting and highlighting.

        Returns:
            str: An HTML string representation of the execution plan
        """
        if not self.commands:
            return "<div class='weiroll-plan'><p><em>Empty plan (no commands)</em></p></div>"

        # Convert commands to the format expected by the renderer
        commands_for_renderer = []
        call_types = []

        # Track state value sources for better visualization
        source_tracking = {}

        # First pass - collect StateValue objects with source_command information
        for i, value in enumerate(self.state):
            if isinstance(value, StateValue) and hasattr(value, "source_command") and value.source_command >= 0:
                source_tracking[i] = value.source_command

        # Get data like in show_tree but format as HTML
        for _i, cmd in enumerate(self.commands):
            target_address = "0x" + cmd.target.hex()[-40:]
            selector_hex = "0x" + cmd.function_selector.hex()

            # Check if command has function_info from decoder
            if hasattr(cmd, "function_info") and cmd.function_info:
                fn_name = cmd.function_info.get("signature") or f"function({selector_hex})"
            else:
                # Try to extract the function name from the 4byte selector
                fn_name = f"function({selector_hex})"  # Default if lookup fails

                contract_name = ""
                try:
                    # Try to look up with Contract class from ape (if available)
                    contract = ApeContract(target_address)

                    # Try to get the signature from the contract's identifier_lookup
                    if hasattr(contract, "identifier_lookup") and selector_hex in contract.identifier_lookup:
                        fn_name = contract.identifier_lookup[selector_hex].signature

                    # Try to get contract name
                    name_found = False
                    if hasattr(contract, "name") and callable(getattr(contract, "name")):
                        try:
                            contract_name = contract.name()
                            name_found = True
                        except Exception:
                            if hasattr(contract, "symbol") and callable(getattr(contract, "symbol")):
                                try:
                                    contract_name = contract.symbol()
                                    name_found = True
                                except Exception:
                                    pass

                    if not name_found and hasattr(contract, "contract_type") and contract.contract_type.name:
                        contract_name = contract.contract_type.name
                except Exception:
                    pass

            # Format command for renderer with enhanced tracking info
            command_dict = {
                "to": target_address,
                "function": fn_name,
                "selector": selector_hex,
                "inputs": [arg.index for arg in cmd.inputs],
                "outputs": [cmd.output.index] if cmd.output and cmd.output.index != ArgType.USE_STATE else [],
                "command_type": cmd.command_type.name,
                "contract_name": contract_name,
            }

            # Add source tracking info for command inputs
            input_sources = []
            for arg in cmd.inputs:
                if isinstance(arg.index, int) and arg.index in source_tracking:
                    input_sources.append(source_tracking[arg.index])
                else:
                    input_sources.append(-1)
            command_dict["input_sources"] = input_sources

            commands_for_renderer.append(command_dict)

            # Handle both enum and int call types for backward compatibility
            if hasattr(cmd.call_type, "name"):
                call_types.append(cmd.call_type.name)
            else:
                call_types.append(CallType(cmd.call_type).name)

            # Track sources for output values
            if cmd.output and cmd.output.index != ArgType.USE_STATE:
                source_tracking[cmd.output.index] = _i

        # Build dependency maps for reference relationships
        state_sources = {}
        state_usage = {}
        for i, command in enumerate(commands_for_renderer):
            # Track outputs (sources)
            outputs = command.get("outputs", [])
            for output_idx, state_idx in enumerate(outputs):
                try:
                    numeric_state_idx = int(state_idx)
                    state_sources[numeric_state_idx] = (i, output_idx)
                except (ValueError, TypeError):
                    continue

            # Track inputs (usage)
            inputs = command.get("inputs", [])
            for input_idx, input_val in enumerate(inputs):
                try:
                    numeric_input_val = int(input_val)
                    if numeric_input_val not in state_usage:
                        state_usage[numeric_input_val] = []
                    state_usage[numeric_input_val].append((i, input_idx))
                except (ValueError, TypeError):
                    continue

        # Use the HTML renderer module
        return render_html(commands_for_renderer, self.state, call_types, state_sources, state_usage)
        for i, command in enumerate(commands_for_renderer):
            # Track outputs (sources)
            outputs = command.get("outputs", [])
            for output_idx, state_idx in enumerate(outputs):
                try:
                    numeric_state_idx = int(state_idx)
                    state_sources[numeric_state_idx] = (i, output_idx)
                except (ValueError, TypeError):
                    continue

            # Track inputs (usage)
            inputs = command.get("inputs", [])
            for input_idx, input_val in enumerate(inputs):
                try:
                    numeric_input_val = int(input_val)
                    if numeric_input_val not in state_usage:
                        state_usage[numeric_input_val] = []
                    state_usage[numeric_input_val].append((i, input_idx))
                except (ValueError, TypeError):
                    continue

        # Format each command
        for i, command in enumerate(commands_for_renderer):
            call_type = call_types[i] if i < len(call_types) else "CALL"

            # Format command header
            target = command.get("to", "0x0000000000000000000000000000000000000000")
            function = command.get("function", f"function({command.get('selector', '0x00000000')})")
            contract_name = command.get("contract_name", "")

            # Color class based on call type
            call_type_class = f"command-{call_type.lower()}"

            # Command header - combining contract, function, and call type in one block
            header_line = f"<div class='command-header'>Command {i}: "

            # Contract name and address
            if contract_name:
                header_line += (
                    f"<span class='function-name'>{contract_name}</span> @ <span class='address'>{target}</span>"
                )
            else:
                header_line += f"<span class='address'>{target}</span>"

            html.append(header_line + "</div>")

            # Function signature and call type
            function_line = f"<div class='{call_type_class}'>  <span class='function-name'>{function}</span> <span class='command-type'>["

            # Handle command type
            command_type = command.get("command_type", "CALL")
            if command_type != "CALL":
                function_line += f"{call_type}, {command_type}]"
            else:
                function_line += f"{call_type}]"

            html.append(function_line + "</span></div>")

            # Process inputs
            inputs = command.get("inputs", [])
            outputs = command.get("outputs", [])

            # Format inputs
            for j, input_val in enumerate(inputs):
                is_last_input = j == len(inputs) - 1
                has_output = bool(outputs)

                # Determine branch character
                branch_char = "└─" if is_last_input and not has_output else "├─"

                # Try to get parameter info
                param_type = ""
                param_name = ""

                if "function" in command:
                    function_sig = command.get("function", "")
                    if "(" in function_sig and ")" in function_sig:
                        params_section = function_sig.split("(")[1].split(")")[0]
                        params = params_section.split(",")
                        if j < len(params):
                            param = params[j].strip()
                            if " " in param:
                                param_parts = param.split(" ", 1)
                                param_type = param_parts[0]
                                param_name = param_parts[1] if len(param_parts) > 1 else ""
                            else:
                                param_type = param

                # Create input label
                if param_type and param_name:
                    input_label = f"{param_type} {param_name}:"
                elif param_type:
                    input_label = f"{param_type}:"
                else:
                    input_label = f"Input {j}:"

                # Get the source command
                source_cmd = -1
                if "input_sources" in command and j < len(command["input_sources"]):
                    source_cmd = command["input_sources"][j]

                if isinstance(input_val, int) or (isinstance(input_val, str) and input_val.isdigit()):
                    # Convert to int
                    try:
                        numeric_val = int(input_val)
                    except (ValueError, TypeError):
                        numeric_val = input_val

                    # Special handling for negative indices
                    if isinstance(numeric_val, int) and numeric_val < 0:
                        if "command_type" in command and command["command_type"] == "SUBPLAN":
                            if numeric_val == -1:
                                html.append(
                                    f"<div data-command-idx='{i}'>  <span class='tree-branch'>{branch_char}</span> <span class='input-label'>{input_label}</span> <span class='subplan'>&lt;Subplan&gt;</span></div>"
                                )
                            else:
                                html.append(
                                    f"<div data-command-idx='{i}'>  <span class='tree-branch'>{branch_char}</span> <span class='input-label'>{input_label}</span> <span class='subplan'>&lt;Special Value: {numeric_val}&gt;</span></div>"
                                )
                        else:
                            html.append(
                                f"<div data-command-idx='{i}'>  <span class='tree-branch'>{branch_char}</span> <span class='input-label'>{input_label}</span> <span class='state-ref'>&lt;Special Value: {numeric_val}&gt;</span></div>"
                            )

                    # Regular state reference
                    elif isinstance(numeric_val, int):
                        # Use the state-specific color class and add data attribute for interactivity
                        state_color_class = f"state-{numeric_val % 20}"
                        state_ref = f"<span class='{state_color_class}' data-state-ref='{numeric_val}'>State[{numeric_val}]</span>"

                        if source_cmd >= 0:
                            # Show source command
                            cmd_ref = f"<span class='function-name'>Command {source_cmd}</span>"
                            html.append(
                                f"<div data-command-idx='{i}' data-state-used='{numeric_val}'>  <span class='tree-branch'>{branch_char}</span> <span class='input-label'>{input_label}</span> {state_ref} (from {cmd_ref} output)</div>"
                            )
                        elif numeric_val < len(self.state):
                            # It's an initial state value
                            from .utils.formatters import format_value

                            value_formatted = format_value(self.state[numeric_val])

                            # Format value based on type
                            value_class = "value-string"
                            if isinstance(self.state[numeric_val], str):
                                if self.state[numeric_val].startswith("0x"):
                                    if len(self.state[numeric_val]) == 42:  # Ethereum address
                                        value_class = "value-address"
                                    else:
                                        value_class = "value-bytes"
                                else:
                                    value_class = "value-string"
                            elif isinstance(self.state[numeric_val], (int, float)):
                                value_class = "value-number"
                            elif isinstance(self.state[numeric_val], bool):
                                value_class = "value-bool"

                            html.append(
                                f"<div data-command-idx='{i}' data-state-used='{numeric_val}'>  <span class='tree-branch'>{branch_char}</span> <span class='input-label'>{input_label}</span> {state_ref} = <span class='{value_class}'>{value_formatted}</span></div>"
                            )
                        else:
                            # Reference to a state that will be computed
                            html.append(
                                f"<div data-command-idx='{i}' data-state-used='{numeric_val}'>  <span class='tree-branch'>{branch_char}</span> <span class='input-label'>{input_label}</span> {state_ref}</div>"
                            )
                else:
                    # Handle non-integer inputs
                    from .utils.formatters import format_value

                    value_text = format_value(input_val)
                    html.append(
                        f"<div data-command-idx='{i}'>  <span class='tree-branch'>{branch_char}</span> <span class='input-label'>{input_label}</span> <span class='value-string'>{value_text}</span></div>"
                    )

            # Format outputs
            if outputs:
                for output_val in outputs:
                    # Create a numeric value for the output
                    numeric_output_val = output_val
                    try:
                        numeric_output_val = int(numeric_output_val)
                    except (ValueError, TypeError):
                        numeric_output_val = output_val

                    # Extract output type if available
                    output_type = ""
                    if "function" in commands_for_renderer[i]:
                        function_sig = commands_for_renderer[i].get("function", "")
                        if "->" in function_sig:
                            return_part = function_sig.split("->")[1].strip()
                            if "," in return_part:
                                return_part = return_part.split(",")[0].strip()
                            output_type = return_part

                    # Format output label
                    if output_type:
                        output_label = f"{output_type} output:"
                    else:
                        output_label = "Output:"

                    # Use the state-specific color class and add data attribute for interactivity
                    color_idx = numeric_output_val % 20 if isinstance(numeric_output_val, int) else 0
                    state_ref = (
                        f"<span class='state-{color_idx}' data-state-ref='{numeric_output_val}' "
                        + f"onmouseover='highlightState({numeric_output_val})' "
                        + f"onmouseout='clearHighlight()'>State[{numeric_output_val}]</span>"
                    )

                    # Find if output is used by later commands
                    usage_details = []
                    if numeric_output_val in state_usage:
                        for cmd_idx, input_idx in state_usage[numeric_output_val]:
                            if cmd_idx > i:  # Only consider future commands
                                cmd = commands_for_renderer[cmd_idx]
                                function_name = cmd.get("function", "")
                                if "(" in function_name:
                                    function_name = function_name.split("(")[0]

                                # Try to get parameter name
                                param_name = f"param{input_idx}"
                                param_full = f"param{input_idx}"

                                function_sig = cmd.get("function", "")
                                if "(" in function_sig and ")" in function_sig:
                                    params_section = function_sig.split("(")[1].split(")")[0]
                                    params = params_section.split(",")
                                    if input_idx < len(params):
                                        param = params[input_idx].strip()
                                        param_full = param
                                        if " " in param:
                                            param_name = (
                                                param.split(" ")[1]
                                                if len(param.split(" ")) > 1
                                                else param.split(" ")[0]
                                            )

                                usage_details.append((cmd_idx, function_name, param_name, param_full))

                    # Format the output line
                    if usage_details:
                        if len(usage_details) == 1:
                            cmd_idx, fn_name, param_name, param_full = usage_details[0]

                            if fn_name and param_name:
                                cmd_ref = f"<span class='function-name'>Command {cmd_idx}</span>"
                                param_ref = f"<span class='param-name'>{fn_name} {param_full}</span>"
                                html.append(
                                    f"<div data-command-idx='{i}' data-state-source='{numeric_output_val}'>  <span class='tree-branch'>└─</span> <span class='output-label'>{output_label}</span> {state_ref} <span class='arrow'>→</span> {cmd_ref} ({param_ref})</div>"
                                )
                            else:
                                cmd_ref = f"<span class='function-name'>Command {cmd_idx}</span>"
                                html.append(
                                    f"<div data-command-idx='{i}' data-state-source='{numeric_output_val}'>  <span class='tree-branch'>└─</span> <span class='output-label'>{output_label}</span> {state_ref} <span class='arrow'>→</span> {cmd_ref}</div>"
                                )
                        else:
                            # Multiple usages
                            usage_strs = []
                            for cmd_idx, fn_name, param_name, param_full in usage_details:
                                if fn_name and param_name:
                                    cmd_ref = f"<span class='function-name'>Command {cmd_idx}</span>"
                                    param_ref = f"<span class='param-name'>{fn_name} {param_full}</span>"
                                    usage_strs.append(f"{cmd_ref} ({param_ref})")
                                else:
                                    cmd_ref = f"<span class='function-name'>Command {cmd_idx}</span>"
                                    usage_strs.append(f"{cmd_ref}")

                            html.append(
                                f"<div data-command-idx='{i}' data-state-source='{numeric_output_val}'>  <span class='tree-branch'>└─</span> <span class='output-label'>{output_label}</span> {state_ref} <span class='arrow'>→</span> "
                                + ", ".join(usage_strs)
                                + "</div>"
                            )
                    else:
                        html.append(
                            f"<div data-command-idx='{i}' data-state-source='{numeric_output_val}'>  <span class='tree-branch'>└─</span> <span class='output-label'>{output_label}</span> {state_ref} <span class='unused'>(unused in future commands)</span></div>"
                        )

            # Add spacing between commands
            if i < len(commands_for_renderer) - 1:
                html.append("<div style='height: 10px;'></div>")

        # Close container div
        html.append("</div>")

        return "\n".join(html)
