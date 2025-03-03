from typing import Any, Dict, List, Optional, Tuple

from eth_utils import to_checksum_address

from .formatters import format_value

# Tree drawing characters
TREE_CHARS = {
    "branch": "  ├─",  # For most items in a list
    "last": "  └─",  # For the last item in a list
    "vertical": "  │ ",  # Vertical continuation
    "empty": "    ",  # Empty space
}


def build_state_dependency_maps(
    commands: List[Dict[str, Any]], state: List[Any]
) -> Tuple[Dict[int, Tuple[int, int]], Dict[int, List[Tuple[int, int]]]]:
    """
    Build maps of state dependencies between commands.

    Args:
        commands: List of command dictionaries
        state: List of state values

    Returns:
        Tuple containing:
        - state_sources: Maps state index to the command that produced it
        - state_usage: Maps state index to commands that use it as input
    """
    state_sources = {}  # Maps state index to the command that produced it
    state_usage = {}  # Maps state index to commands that use it as input

    # First pass: track all command outputs (sources)
    for i, command in enumerate(commands):
        outputs = command.get("outputs", [])
        for output_idx, state_idx in enumerate(outputs):
            # Extract just the numeric part if state_idx contains type information
            numeric_state_idx = state_idx
            if isinstance(state_idx, str) and " " in state_idx:
                numeric_state_idx = state_idx.split()[0]

            try:
                numeric_state_idx = int(numeric_state_idx)
                # Use the numeric index for the source mapping
                if numeric_state_idx < len(state) + len(commands):  # Allow for state indices that will be created
                    state_sources[numeric_state_idx] = (i, output_idx)
            except (ValueError, TypeError):
                # Skip if we can't convert to int
                continue

    # Second pass: track all command inputs (usage)
    for i, command in enumerate(commands):
        inputs = command.get("inputs", [])
        for input_idx, input_val in enumerate(inputs):
            # Track state usage for dependencies
            # Extract just the numeric part if input_val contains type information
            numeric_input_val = input_val
            if isinstance(input_val, str) and " " in input_val:
                numeric_input_val = input_val.split()[0]

            try:
                numeric_input_val = int(numeric_input_val)
                if numeric_input_val < len(state) + len(commands):  # Allow for references to future state
                    # Store the input value exactly as it appears in the command
                    if numeric_input_val not in state_usage:
                        state_usage[numeric_input_val] = []
                    state_usage[numeric_input_val].append((i, input_idx))
            except (ValueError, TypeError):
                # Skip if we can't convert to int
                continue

    return state_sources, state_usage


def format_command_header(command: Dict[str, Any], index: int, call_type: str) -> str:
    """
    Format the command header line.

    Args:
        command: The command dictionary
        index: Command index
        call_type: The call type (e.g., "CALL", "DELEGATECALL")

    Returns:
        Formatted header string
    """
    # Format target address
    target = command.get("to", "0x0000000000000000000000000000000000000000")
    target_formatted = to_checksum_address(target)

    # Format function signature
    function_formatted = command.get("function", f"function({command.get('selector', '0x00000000')})")

    # Handle command type
    command_type = command.get("command_type", "CALL")
    if command_type != "CALL":
        return f"Command {index}: {function_formatted} @ {target_formatted} [{call_type}, {command_type}]"
    else:
        return f"Command {index}: {function_formatted} @ {target_formatted} [{call_type}]"


def format_input_line(
    input_val: Any,
    input_index: int,
    is_last_input: bool,
    has_output: bool,
    command: Dict[str, Any],
    state_sources: Dict[int, Tuple[int, int]],
    state: List[Any],
) -> str:
    """
    Format a single input line for the command.

    Args:
        input_val: The input value
        input_index: Index of this input in the command's inputs
        is_last_input: Whether this is the last input in the list
        has_output: Whether the command has outputs
        command: The command dictionary
        state_sources: Maps state index to the command that produced it
        state: List of state values

    Returns:
        Formatted input line
    """
    # Determine the tree character to use
    prefix = TREE_CHARS["last"] if is_last_input and not has_output else TREE_CHARS["branch"]

    # Check if this input is a reference to a previous command's output
    source_cmd = -1

    if isinstance(input_val, int) or (isinstance(input_val, str) and input_val.isdigit()):
        # Convert to int for consistency
        try:
            numeric_val = int(input_val)
        except (ValueError, TypeError):
            numeric_val = input_val

        # Special handling for negative indices (placeholders for state or subplans)
        if isinstance(numeric_val, int) and numeric_val < 0:
            if "command_type" in command and command["command_type"] == "SUBPLAN":
                if numeric_val == -1:  # SUBPLAN_PLACEHOLDER
                    return f"{prefix} Input {input_index}: <Subplan>"
                else:
                    return f"{prefix} Input {input_index}: <Special Value: {numeric_val}>"
            else:
                return f"{prefix} Input {input_index}: <Special Value: {numeric_val}>"

        # Regular state reference
        elif isinstance(numeric_val, int):
            # First check if this value comes from a command output
            source_cmd, _ = state_sources.get(numeric_val, (-1, -1))
            if source_cmd >= 0:
                return f"{prefix} Input {input_index}: State[{numeric_val}] (from Command {source_cmd} output)"
            elif numeric_val < len(state):
                # It's an initial state value
                value_formatted = format_value(state[numeric_val])
                return f"{prefix} Input {input_index}: State[{numeric_val}] = {value_formatted}"
            else:
                # Reference to a state that will be computed during execution
                return f"{prefix} Input {input_index}: State[{numeric_val}]"

    # Handle non-integer inputs (should be rare in the planner, more common in decoded plans)
    return f"{prefix} Input {input_index}: {format_value(input_val)}"


def format_output_line(
    output_val: Any, command_index: int, state_usage: Dict[int, List[Tuple[int, int]]], commands: List[Dict[str, Any]]
) -> str:
    """
    Format the output line for the command.

    Args:
        output_val: The output value
        command_index: Index of this command
        state_usage: Maps state index to commands that use it as input
        commands: List of all commands in the plan

    Returns:
        Formatted output line
    """
    # Create a normalized numeric value for the output
    numeric_output_val = output_val
    if isinstance(output_val, str) and " " in output_val:
        numeric_output_val = output_val.split()[0]

    try:
        numeric_output_val = int(numeric_output_val)
    except (ValueError, TypeError):
        numeric_output_val = output_val

    # Extract output type if available
    output_type = ""
    if isinstance(output_val, str) and " " in output_val:
        parts = output_val.split(" ", 1)
        if len(parts) > 1:
            output_type = parts[1].strip()

    # Find if this output is used by commands in the state_usage map
    usage_details = []
    if numeric_output_val in state_usage:
        for cmd_idx, input_idx in state_usage[numeric_output_val]:
            # Only consider future commands (after this one)
            if cmd_idx > command_index:
                # Get the function name and parameter name if possible
                if cmd_idx < len(commands):
                    cmd = commands[cmd_idx]
                    function_name = cmd.get("function", "")
                    # Extract the base function name
                    if "(" in function_name:
                        function_name = function_name.split("(")[0]

                    # Try to get parameter name - this is a simplification and could be improved
                    param_name = f"param{input_idx}"

                    # If we have a function signature, try to extract parameter names
                    function_sig = cmd.get("function", "")
                    if "(" in function_sig and ")" in function_sig:
                        # Extract parameters section from the signature
                        params_section = function_sig.split("(")[1].split(")")[0]
                        params = params_section.split(",")
                        if input_idx < len(params):
                            # Check if parameter has a name
                            param = params[input_idx].strip()
                            if " " in param:
                                param_name = param.split(" ")[0]

                    usage_details.append((cmd_idx, function_name, param_name))
                else:
                    usage_details.append((cmd_idx, "", f"param{input_idx}"))

    # Sort by command index
    usage_details.sort()

    # Format the output line
    output_prefix = f"{TREE_CHARS['last']} Output: "
    if output_type:
        output_prefix = f"{TREE_CHARS['last']} Output ({output_type}): "

    if usage_details:
        if len(usage_details) == 1:
            cmd_idx, fn_name, param_name = usage_details[0]
            if fn_name and param_name:
                return f"{output_prefix}State[{numeric_output_val}] → Command {cmd_idx} ({fn_name}.{param_name})"
            else:
                return f"{output_prefix}State[{numeric_output_val}] → Command {cmd_idx}"
        else:
            # Multiple usages
            usage_strs = []
            for cmd_idx, fn_name, param_name in usage_details:
                if fn_name and param_name:
                    usage_strs.append(f"Command {cmd_idx} ({fn_name}.{param_name})")
                else:
                    usage_strs.append(f"Command {cmd_idx}")
            return f"{output_prefix}State[{numeric_output_val}] → " + ", ".join(usage_strs)
    else:
        return f"{output_prefix}State[{numeric_output_val}] (unused in future commands)"


def render_tree(
    commands: List[Dict[str, Any]], state: List[Any], call_types: List[str], contracts: Optional[Dict[str, Any]] = None
) -> str:
    """
    Renders a plan execution tree.

    This is a shared implementation used by both Planner.show_tree and DecodedPlan.__str__
    to ensure consistent output format between both implementations.

    Args:
        commands: List of command dictionaries
        state: List of state values
        call_types: List of call types (e.g. "STATICCALL", "CALL")
        contracts: Optional dictionary of contract objects to decode function selectors

    Returns:
        Formatted string representation of the execution tree
    """
    # Build dependency maps
    state_sources, state_usage = build_state_dependency_maps(commands, state)

    # Format each command
    lines = []
    for i, command in enumerate(commands):
        # Add command header
        call_type = call_types[i] if i < len(call_types) else "CALL"
        lines.append(format_command_header(command, i, call_type))

        # Process inputs
        inputs = command.get("inputs", [])
        outputs = command.get("outputs", [])

        input_lines = []
        for j, input_val in enumerate(inputs):
            is_last_input = j == len(inputs) - 1
            has_output = bool(outputs)
            input_lines.append(
                format_input_line(input_val, j, is_last_input, has_output, command, state_sources, state)
            )

        # Add input lines
        lines.extend(input_lines)

        # Format outputs
        if outputs:
            for output_val in outputs:
                lines.append(format_output_line(output_val, i, state_usage, commands))

        # Add an empty line between commands
        if i < len(commands) - 1:
            lines.append("")

    # Remove the last empty line if it exists
    if lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)
