from typing import Any, Dict, List, Optional, Tuple, Union

from eth_utils import to_checksum_address

from .formatters import format_value
from .terminal_colors import colorize, colorize_state_ref, get_color_mode

# Tree drawing characters
TREE_CHARS = {
    "branch": "    ├─",  # For most items in a list
    "last": "    └─",  # For the last item in a list
    "vertical": "    │ ",  # Vertical continuation
    "empty": "      ",  # Empty space
    "contract_indent": "  ",  # Indentation for contract info line
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
        Formatted header string (possibly multiline)
    """
    # Format target address
    target = command.get("to", "0x0000000000000000000000000000000000000000")
    target_formatted = to_checksum_address(target)

    # Format function signature
    function_formatted = command.get("function", f"function({command.get('selector', '0x00000000')})")

    # Get contract name if available
    contract_name = command.get("contract_name", "")

    # Colorize based on call type
    color_key = f"command_header_{call_type.lower()}" if call_type.lower() in ["call", "staticcall", "delegatecall"] else "command_header"
    
    # Get parts to colorize separately
    command_index = f"Command {index}"
    function_part = function_formatted
    type_part = f"[{call_type}"
    
    # Handle command type
    command_type = command.get("command_type", "CALL")
    if command_type != "CALL":
        type_part += f", {command_type}]"
    else:
        type_part += "]"
        
    # Colorize each part
    colored_command_index = colorize(command_index, color_key)
    colored_function = colorize(function_part, "function_name")
    colored_type = colorize(type_part, color_key)
    
    # Format contract name and address
    contract_line = ""
    contract_indent = TREE_CHARS["contract_indent"]
    if contract_name:
        # Show both name and address
        colored_name = colorize(contract_name, "function_name")
        colored_address = colorize(target_formatted, "address")
        contract_line = f"\n{contract_indent}{colored_name} @ {colored_address}"
    else:
        # Just show address on its own line
        colored_address = colorize(target_formatted, "address")
        contract_line = f"\n{contract_indent}@ {colored_address}"
    
    # Return a multi-line header with function on first line, contract info on second
    return f"{colored_command_index}: {colored_function} {colored_type}{contract_line}"


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
    prefix_char = TREE_CHARS["last"] if is_last_input and not has_output else TREE_CHARS["branch"]
    # Colorize the tree structure
    prefix = colorize(prefix_char, "tree_structure")

    # Colorize the input label
    input_label = colorize(f"Input {input_index}", "input_label")

    # Get the source command from enhanced tracking, if available
    source_cmd = -1
    if "input_sources" in command and input_index < len(command["input_sources"]):
        source_cmd = command["input_sources"][input_index]
    
    # If we don't have it from enhanced tracking, use the original lookup
    if source_cmd < 0 and isinstance(input_val, (int, str)):
        try:
            numeric_val = int(input_val) if isinstance(input_val, str) and input_val.isdigit() else input_val
            if isinstance(numeric_val, int):
                source_cmd_tuple = state_sources.get(numeric_val, (-1, -1))
                source_cmd = source_cmd_tuple[0]
        except (ValueError, TypeError):
            pass

    # Special case - uint256 type parameter
    if input_val == 'uint256':
        # This is likely the value we want to track from the previous command
        # but we need to find which command's output is being used (usually the preceding one)
        # We'll add a special indicator for clarity
        param_text = colorize(f"uint256 (value from returned balance)", "value_number")
        return f"{prefix} {input_label}: {param_text}"

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
                    subplan_text = colorize("<Subplan>", "subplan")
                    return f"{prefix} {input_label}: {subplan_text}"
                else:
                    special_text = colorize(f"<Special Value: {numeric_val}>", "subplan")
                    return f"{prefix} {input_label}: {special_text}"
            else:
                special_text = colorize(f"<Special Value: {numeric_val}>", "state_ref")
                return f"{prefix} {input_label}: {special_text}"

        # Regular state reference
        elif isinstance(numeric_val, int):
            # Use state-based color coding
            state_ref = colorize_state_ref(f"State[{numeric_val}]", numeric_val)
            
            if source_cmd >= 0:
                # Show both source command and parameter role if available
                cmd_ref = colorize(f"Command {source_cmd}", "function_name")
                return f"{prefix} {input_label}: {state_ref} (from {cmd_ref} output)"
            elif numeric_val < len(state):
                # It's an initial state value
                value_formatted = format_value(state[numeric_val])
                # Colorize value based on type
                if isinstance(state[numeric_val], str):
                    if state[numeric_val].startswith("0x"):  # Likely address or bytes
                        if len(state[numeric_val]) == 42:  # Ethereum address
                            value_formatted = colorize(value_formatted, "value_address")
                        else:
                            value_formatted = colorize(value_formatted, "value_bytes")
                    else:
                        value_formatted = colorize(value_formatted, "value_string")
                elif isinstance(state[numeric_val], (int, float)):
                    value_formatted = colorize(value_formatted, "value_number")
                elif isinstance(state[numeric_val], bool):
                    value_formatted = colorize(value_formatted, "value_bool")
                
                return f"{prefix} {input_label}: {state_ref} = {value_formatted}"
            else:
                # Reference to a state that will be computed during execution
                return f"{prefix} {input_label}: {state_ref}"

    # Handle non-integer inputs (should be rare in the planner, more common in decoded plans)
    value_text = colorize(format_value(input_val), "value_string")
    return f"{prefix} {input_label}: {value_text}"


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
                    param_full = f"param{input_idx}"  # Full version with type info

                    # If we have a function signature, try to extract parameter names
                    function_sig = cmd.get("function", "")
                    if hasattr(cmd, "function_info") and cmd.function_info:
                        # Try to get parameter names from the function signature in function_info
                        signature = cmd.function_info.get("signature", "")
                        if signature and "(" in signature and ")" in signature:
                            # Extract parameters section from the signature
                            params_section = signature.split("(")[1].split(")")[0]
                            params = params_section.split(",")
                            if input_idx < len(params):
                                param = params[input_idx].strip()
                                param_full = param  # Keep the full param with type
                                if " " in param:
                                    # Extract the parameter name from "address receiver" -> "receiver"
                                    param_name = param.split(" ")[1] if len(param.split(" ")) > 1 else param.split(" ")[0]
                    elif "(" in function_sig and ")" in function_sig:
                        # Fallback to original function signature if function_info not available
                        params_section = function_sig.split("(")[1].split(")")[0]
                        params = params_section.split(",")
                        if input_idx < len(params):
                            param = params[input_idx].strip()
                            param_full = param  # Keep the full param with type
                            if " " in param:
                                param_name = param.split(" ")[0]

                    usage_details.append((cmd_idx, function_name, param_name, param_full))
                else:
                    usage_details.append((cmd_idx, "", f"param{input_idx}", f"param{input_idx}"))

    # Sort by command index
    usage_details.sort()

    # Colorize the tree structure
    prefix_char = TREE_CHARS["last"]
    prefix = colorize(prefix_char, "tree_structure")

    # Colorize the output label
    output_label_text = "Output"
    if output_type:
        output_label_text = f"Output ({output_type})"
    output_label = colorize(output_label_text, "output_label")
    
    # Colorize state reference with state-based coloring
    state_ref = colorize_state_ref(f"State[{numeric_output_val}]", numeric_output_val)

    # Format the output line with colorization
    if usage_details:
        if len(usage_details) == 1:
            cmd_idx, fn_name, param_name, param_full = usage_details[0]
            
            if fn_name and param_name:
                cmd_ref = colorize(f"Command {cmd_idx}", "function_name")
                # Use full parameter with type
                param_ref = colorize(f"{fn_name} {param_full}", "param_name")
                arrow = colorize("→", "tree_structure")
                return f"{prefix} {output_label}: {state_ref} {arrow} {cmd_ref} ({param_ref})"
            else:
                cmd_ref = colorize(f"Command {cmd_idx}", "function_name")
                arrow = colorize("→", "tree_structure")
                return f"{prefix} {output_label}: {state_ref} {arrow} {cmd_ref}"
        else:
            # Multiple usages
            usage_strs = []
            for cmd_idx, fn_name, param_name, param_full in usage_details:
                if fn_name and param_name:
                    cmd_ref = colorize(f"Command {cmd_idx}", "function_name")
                    # Use full parameter with type
                    param_ref = colorize(f"{fn_name} {param_full}", "param_name")
                    usage_strs.append(f"{cmd_ref} ({param_ref})")
                else:
                    cmd_ref = colorize(f"Command {cmd_idx}", "function_name")
                    usage_strs.append(f"{cmd_ref}")
                    
            arrow = colorize("→", "tree_structure")
            return f"{prefix} {output_label}: {state_ref} {arrow} " + ", ".join(usage_strs)
    else:
        unused_msg = colorize("(unused in future commands)", "unused")
        return f"{prefix} {output_label}: {state_ref} {unused_msg}"


def render_tree(
    commands: List[Dict[str, Any]], state: List[Any], call_types: List[str], contracts: Optional[Dict[str, Any]] = None,
    use_color: Optional[bool] = None
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
        use_color: Whether to use colors in the output (None for auto-detection)

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
