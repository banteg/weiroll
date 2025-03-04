import logging
from typing import Any, Optional, Set, List

from ape import Contract as ApeContract
from eth_abi import encode
from eth_abi.exceptions import EncodingError

from .command import Command, CommandArg
from .constants import ArgType, CallType, CommandType
from .contract import FunctionCall, StateValue as ContractStateValue
from .contract import SubplanValue as ContractSubplanValue
from .utils.tree_renderer import render_tree
from .utils.html_renderer import render_html
from .values import PlannerValue, LiteralValue, CommandOutputValue, SubplanValue

logger = logging.getLogger(__name__)


class Planner:
    """
    Plans a series of commands for the Weiroll VM.

    This class allows building a sequence of contract calls to be executed
    by the Weiroll VM on-chain.

    Attributes:
        commands: List of commands to execute
        state: List of (value, kind) tuples (the "kind" is a string describing how to treat the value)
        next_state_index: Next available index in the state array
        state_value: Represents the current planner state for use with addSubplan
    """

    def __init__(self):
        # Use polymorphic PlannerValue objects instead of (value, kind) tuples
        self.state: List[PlannerValue] = []
        self.commands: List[Command] = []
        self.next_state_index: int = 0

        # The placeholder for the current planner state
        self.state_value = ContractStateValue(-1, is_dynamic=True)
        self.state_value.to_arg = lambda: CommandArg(index=-1, is_dynamic=True, is_state=True)

    def _add_to_state(
        self, value: PlannerValue, deduplicate: bool = True
    ) -> int:
        """
        Add a PlannerValue to the planner's state and return the state index.

        We only deduplicate if:
          1) deduplicate == True
          2) The new value is a LiteralValue (value.is_literal() == True)
          3) There's an existing LiteralValue with equal data

        Otherwise, we always add a new entry to the end of `self.state`.
        """
        # If deduplicate is enabled and this is a literal, try to find a match
        if deduplicate and value.is_literal():
            for i, existing_value in enumerate(self.state):
                if existing_value.is_literal() and existing_value.equals_literal(value):
                    # Found an identical literal entry -> reuse its index
                    return i

        # No deduplication or no match found, add new
        index = self.next_state_index
        self.state.append(value)
        self.next_state_index += 1
        return index
        
    def _add_literal_to_state(
        self, value: Any, is_dynamic: bool = False, deduplicate: bool = True
    ) -> int:
        """
        Helper method to add a Python literal value to the state.
        Wraps it in a LiteralValue and calls _add_to_state.
        """
        planner_value = LiteralValue(value, is_dynamic)
        return self._add_to_state(planner_value, deduplicate)

    def add(self, fn_call: FunctionCall) -> ContractStateValue | None:
        """
        Add a function call to the plan and return a reference to its output in state (if any).

        The function call is a standard (non-subplan) call. We handle deduplication for literal args,
        but any command output or subplan reference is *not* deduplicated.
        """
        # Validate input - ensure required attributes exist
        for attr in ("selector", "target", "args", "method_abi", "call_type"):
            if not hasattr(fn_call, attr):
                raise TypeError(f"Expected a FunctionCall-like object with '{attr}' attribute")

        # Subplans are not allowed in a regular add()
        for i, arg in enumerate(fn_call.args):
            if isinstance(arg, ContractSubplanValue):
                raise ValueError(f"Argument {i}: SubplanValue can only be used with addSubplan")

        # Build the command inputs
        input_args: list[CommandArg] = []

        # If this is a value-call, the value is the first argument
        if fn_call.call_type == CallType.VALUECALL and fn_call.fn.value > 0:
            # Value calls can safely use deduplication since they're not part of dependency tracking
            val_index = self._add_literal_to_state(fn_call.fn.value, is_dynamic=False, deduplicate=True)
            input_args.append(CommandArg(index=val_index))

        # Process each function argument
        for arg in fn_call.args:
            if isinstance(arg, ContractStateValue):
                # Already a reference to some state index
                input_args.append(arg.to_arg())
            else:
                # For a raw literal argument, create a LiteralValue
                # Always disable deduplication for function arguments to ensure proper dependency tracking
                is_dyn = isinstance(arg, (bytes, str, list, tuple))
                state_index = self._add_literal_to_state(
                    value=arg,
                    is_dynamic=is_dyn,
                    deduplicate=False,  # Disable deduplication for function arguments
                )
                input_args.append(CommandArg(index=state_index, is_dynamic=is_dyn))

        # Figure out if there's an output
        has_tuple_return = getattr(fn_call, "is_tuple_return", False)
        output_arg = None
        output_state = None

        if has_tuple_return:
            # This is the .rawValue() scenario => always "bytes" output
            idx = self.next_state_index
            output_arg = CommandArg(index=idx)
            output_state = ContractStateValue(index=idx, is_dynamic=True)
            output_state.source_command = len(self.commands)
            
            # Create a CommandOutputValue for tuple return
            cmd_output = CommandOutputValue(source_command=len(self.commands), is_dynamic=True)
            self._add_to_state(cmd_output, deduplicate=False)
        
        elif fn_call.method_abi.outputs and len(fn_call.method_abi.outputs) > 0:
            # Normal function with a single output
            outtype = fn_call.method_abi.outputs[0].type
            is_dyn = (outtype in ["string", "bytes"]) or outtype.endswith("[]")

            idx = self.next_state_index
            output_arg = CommandArg(index=idx, is_dynamic=is_dyn)
            output_state = ContractStateValue(index=idx, is_dynamic=is_dyn)
            output_state.source_command = len(self.commands)
            
            # Create a CommandOutputValue with the source command index
            cmd_output = CommandOutputValue(source_command=len(self.commands), is_dynamic=is_dyn)
            self._add_to_state(cmd_output, deduplicate=False)

        # Create the Command
        command = Command(
            function_selector=fn_call.selector,
            target=fn_call.target,
            inputs=input_args,
            output=output_arg,
            call_type=fn_call.call_type,
            command_type=CommandType.CALL,
            is_tuple_return=has_tuple_return,
        )
        cmd_index = len(self.commands)
        self.commands.append(command)

        return output_state  # Might be None if no output

    def addSubplan(self, fn_call: FunctionCall) -> None:
        """
        Add a function call referencing a subplan. The subplan is embedded in the parent's plan
        as a nested commands array, to be executed in a callback-like way.
        """
        # Validate input
        for attr in ("args", "call_type", "fn"):
            if not hasattr(fn_call, attr):
                raise TypeError(f"Expected a FunctionCall-like object with '{attr}' attribute")

        # We expect exactly one subplan argument and one "state" argument
        has_subplan = False
        has_state = False
        subplan_index = -1

        input_args: list[CommandArg] = []

        # If this is a valuecall
        if fn_call.call_type == CallType.VALUECALL and fn_call.fn.value > 0:
            val_index = self._add_literal_to_state(fn_call.fn.value, is_dynamic=False, deduplicate=True)
            input_args.append(CommandArg(index=val_index))

        for i, arg in enumerate(fn_call.args):
            if isinstance(arg, ContractSubplanValue):
                if has_subplan:
                    raise ValueError("Subplans can only take one planner argument")
                has_subplan = True
                subplan_index = i
                # This placeholder is replaced during plan() with encoded subplan bytes
                input_args.append(CommandArg(index=-1, is_dynamic=True, is_subplan=True))

            elif isinstance(arg, ContractStateValue) and arg.to_arg().is_state:
                if has_state:
                    raise ValueError("Subplans can only take one state argument")
                has_state = True
                # State placeholder
                input_args.append(CommandArg(index=-1, is_dynamic=True, is_state=True))

            elif isinstance(arg, ContractStateValue):
                # Regular state usage
                input_args.append(arg.to_arg())

            else:
                # A literal argument to the subplan call
                # Always disable deduplication for function arguments to ensure proper dependency tracking
                is_dyn = isinstance(arg, (bytes, str, list, tuple))
                idx = self._add_literal_to_state(
                    value=arg, 
                    is_dynamic=is_dyn, 
                    deduplicate=False  # Disable deduplication for function arguments
                )
                input_args.append(CommandArg(index=idx, is_dynamic=is_dyn))

        if not has_subplan or not has_state:
            raise ValueError("Subplans must take planner and state arguments")

        # Verify return type is bytes[] or none
        if fn_call.method_abi.outputs and len(fn_call.method_abi.outputs) > 0:
            outtype = fn_call.method_abi.outputs[0].canonical_type
            if outtype != "bytes[]":
                raise ValueError("Subplans must return a bytes[] replacement state or nothing")

        # Create the subplan command
        command = Command(
            function_selector=fn_call.selector,
            target=fn_call.target,
            inputs=input_args,
            output=CommandArg(index=ArgType.USE_STATE),
            call_type=fn_call.call_type,
            command_type=CommandType.SUBPLAN,
        )

        # Attach the subplanner object for usage in plan()
        command.subplan = fn_call.args[subplan_index].planner if has_subplan else None
        self.commands.append(command)

    def replaceState(self, fn_call: FunctionCall) -> None:
        """
        Executes a function that returns bytes[], which we treat as a full replacement for the state.
        """
        # Must return exactly bytes[]
        if not fn_call.method_abi.outputs or len(fn_call.method_abi.outputs) < 1:
            raise ValueError("Function replacing state must return a value")
        outtype = fn_call.method_abi.outputs[0].canonical_type
        if outtype != "bytes[]":
            raise ValueError("Function replacing state must return a bytes[]")

        input_args: list[CommandArg] = []

        # Possibly a valuecall
        if fn_call.call_type == CallType.VALUECALL and fn_call.fn.value > 0:
            val_index = self._add_literal_to_state(fn_call.fn.value, is_dynamic=False, deduplicate=True)
            input_args.append(CommandArg(index=val_index))

        # Process the rest
        for arg in fn_call.args:
            if isinstance(arg, ContractStateValue) and arg.to_arg().is_state:
                input_args.append(CommandArg(index=-1, is_dynamic=True, is_state=True))

            elif isinstance(arg, ContractStateValue):
                input_args.append(arg.to_arg())

            elif isinstance(arg, ContractSubplanValue):
                raise ValueError("SubplanValue cannot be used with replaceState")

            else:
                is_dyn = isinstance(arg, (bytes, str, list, tuple))
                # Always disable deduplication for function arguments
                idx = self._add_literal_to_state(
                    value=arg, 
                    is_dynamic=is_dyn, 
                    deduplicate=False  # Disable deduplication for function arguments
                )
                input_args.append(CommandArg(index=idx, is_dynamic=is_dyn))

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
        Builds the subplan as hex-encoded bytes32[] to embed in the parent plan.
        Detects planner self-reference or cycles by using the 'seen' set.
        """
        if planner in seen:
            raise ValueError("A planner cannot contain itself")

        new_seen = set(seen)
        new_seen.add(planner)

        subplan_data = planner.plan()
        subcommands = subplan_data["commands"]  # Already hex strings like "0xabcd..."

        # Encode as bytes32[] with eth_abi
        try:
            bytes_commands = [bytes.fromhex(cmd[2:]) for cmd in subcommands]
            encoded = "0x" + encode(["bytes32[]"], [bytes_commands]).hex()
            # Skip the first 32 bytes offset
            return encoded[66:]
        except Exception as e:
            raise ValueError(f"Failed to encode subplan: {e}")

    def plan(self) -> dict[str, list[str]]:
        """
        Finalize this planner into a dict with "commands" and "state" suitable for Weiroll VM execution.
        """
        encoded_commands = []

        # First pass: build commands & handle subplans
        for cmd in self.commands:
            if cmd.command_type == CommandType.SUBPLAN:
                if not hasattr(cmd, "subplan") or cmd.subplan is None:
                    raise ValueError("Subplan command missing subplan reference")

                encoded_subplan = self._build_subplan(cmd.subplan, set())
                # Create a SubplanValue with the encoded bytes
                subplan_value = SubplanValue(bytes.fromhex(encoded_subplan[2:]))
                subplan_index = self._add_to_state(subplan_value, deduplicate=False)
                
                # Patch the argument that is_subplan=True
                for arg in cmd.inputs:
                    if arg.is_subplan:
                        arg.index = subplan_index

            # Now encode the command itself
            cmd_bytes = cmd.encode()
            encoded_commands.append("0x" + cmd_bytes.hex())

        # Encode state as hex
        encoded_state = []
        # Each PlannerValue knows how to encode itself
        for i, value in enumerate(self.state):
            try:
                raw_bytes = value.to_bytes()
                encoded_state.append("0x" + raw_bytes.hex() if raw_bytes else "0x")
            except Exception as e:
                logger.error(f"Failed to encode state at index {i}: {e}")
                encoded_state.append("0x")  # Empty as fallback

        # Pad state array if needed
        while len(encoded_state) < self.next_state_index:
            encoded_state.append("0x")

        return {"commands": encoded_commands, "state": encoded_state}

    # The _encode_single_value method is removed since each PlannerValue subclass 
    # now has its own to_bytes() method for encoding

    def __enter__(self) -> "Planner":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __repr__(self) -> str:
        return f"Planner(commands={len(self.commands)}, state_size={len(self.state)})"

    def show_tree(self, use_color: Optional[bool] = None) -> str:
        """
        Generate a visual ASCII-based tree representation of the plan, showing how
        command inputs and outputs depend on each other or on literal state.
        """
        if not self.commands:
            return "Empty plan (no commands)"

        commands_for_renderer = []
        call_types = []
        source_tracking = {}

        # Record which state indices come from which command
        for i, val in enumerate(self.state):
            if isinstance(val, CommandOutputValue):
                source_tracking[i] = val.source_command

        for idx, cmd in enumerate(self.commands):
            target_address = "0x" + cmd.target.hex()[-40:]
            selector_hex = "0x" + cmd.function_selector.hex()

            # Attempt function name from `function_info`
            contract_name = ""
            fn_name = f"function({selector_hex})"
            if hasattr(cmd, "function_info") and cmd.function_info:
                fn_name = cmd.function_info.get("signature") or fn_name
                contract_name = cmd.function_info.get("contract_name", "")

            command_dict = {
                "to": target_address,
                "function": fn_name,
                "selector": selector_hex,
                "inputs": [arg.index for arg in cmd.inputs],
                "outputs": [],
                "command_type": cmd.command_type.name,
                "contract_name": contract_name,
            }

            if cmd.output and cmd.output.index != ArgType.USE_STATE:
                command_dict["outputs"].append(cmd.output.index)

            commands_for_renderer.append(command_dict)

            ctype = cmd.call_type.name if hasattr(cmd.call_type, "name") else CallType(cmd.call_type).name
            call_types.append(ctype)

        # Convert PlannerValue objects to plain values for compatibility with renderer
        state_for_renderer = []
        for val in self.state:
            if isinstance(val, LiteralValue):
                state_for_renderer.append(val.data)
            else:
                # For non-literal values, pass None as a placeholder
                state_for_renderer.append(None)

        return render_tree(commands_for_renderer, state_for_renderer, call_types, use_color=use_color)

    def _repr_html_(self) -> str:
        """
        Return an HTML rendering (for Jupyter/IPython notebooks) of the planned calls.
        """
        if not self.commands:
            return "<div class='weiroll-plan'><p><em>Empty plan (no commands)</em></p></div>"

        commands_for_renderer = []
        call_types = []
        for idx, cmd in enumerate(self.commands):
            target_address = "0x" + cmd.target.hex()[-40:]
            selector_hex = "0x" + cmd.function_selector.hex()

            contract_name = ""
            fn_name = f"function({selector_hex})"
            if hasattr(cmd, "function_info") and cmd.function_info:
                fn_name = cmd.function_info.get("signature") or fn_name
                contract_name = cmd.function_info.get("contract_name", "")

            command_dict = {
                "to": target_address,
                "function": fn_name,
                "selector": selector_hex,
                "inputs": [arg.index for arg in cmd.inputs],
                "outputs": [],
                "command_type": cmd.command_type.name,
                "contract_name": contract_name,
                "input_sources": [],  # Track sources for each input
            }

            # For each input, if it's a state index from a command output, add the source
            for arg in cmd.inputs:
                if arg.index >= 0 and arg.index < len(self.state):
                    state_val = self.state[arg.index]
                    if isinstance(state_val, CommandOutputValue):
                        command_dict["input_sources"].append(state_val.source_command)
                    else:
                        command_dict["input_sources"].append(-1)

            if cmd.output and cmd.output.index != ArgType.USE_STATE:
                command_dict["outputs"].append(cmd.output.index)

            commands_for_renderer.append(command_dict)

            ctype = cmd.call_type.name if hasattr(cmd.call_type, "name") else CallType(cmd.call_type).name
            call_types.append(ctype)

        # Build simple state mapping
        state_sources = {}
        state_usage = {}

        for i, command in enumerate(commands_for_renderer):
            for outidx, state_idx in enumerate(command.get("outputs", [])):
                try:
                    si = int(state_idx)
                    state_sources[si] = (i, outidx)
                except (ValueError, TypeError):
                    pass
            for inidx, state_idx in enumerate(command.get("inputs", [])):
                try:
                    si = int(state_idx)
                    if si not in state_usage:
                        state_usage[si] = []
                    state_usage[si].append((i, inidx))
                except (ValueError, TypeError):
                    pass

        # Convert PlannerValue objects to plain values for compatibility with renderer
        state_for_renderer = []
        for val in self.state:
            if isinstance(val, LiteralValue):
                state_for_renderer.append(val.data)
            else:
                # For non-literal values, pass None as a placeholder
                state_for_renderer.append(None)

        return render_html(commands_for_renderer, state_for_renderer, call_types, state_sources, state_usage)
