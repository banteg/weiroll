from typing import Any

from eth_utils import to_checksum_address

from .formatters import format_value


def render_tree(
    commands: list[dict[str, Any]], state: list[Any], call_types: list[str], contracts: dict[str, Any] | None = None
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
    # Create a mapping of state sources
    state_sources = {}
    state_usage = {}

    # Track state sources and usage
    for i, command in enumerate(commands):
        inputs = command.get("inputs", [])
        for input_idx, input_val in enumerate(inputs):
            # Track state usage for dependencies
            # Extract just the numeric part if input_val contains type information
            numeric_input_val = input_val.split()[0] if isinstance(input_val, str) and " " in input_val else input_val
            try:
                numeric_input_val = int(numeric_input_val)
                if numeric_input_val < len(state):
                    if input_val not in state_usage:
                        state_usage[input_val] = []
                    state_usage[input_val].append((i, input_idx))
            except (ValueError, TypeError):
                # Skip if we can't convert to int
                continue

        outputs = command.get("outputs", [])
        for output_idx, state_idx in enumerate(outputs):
            # Extract just the numeric part if state_idx contains type information
            numeric_state_idx = state_idx.split()[0] if isinstance(state_idx, str) and " " in state_idx else state_idx
            try:
                numeric_state_idx = int(numeric_state_idx)
                if numeric_state_idx < len(state) + i + 1:  # Include output indices that may exceed state array
                    state_sources[state_idx] = (i, output_idx)
            except (ValueError, TypeError):
                # Skip if we can't convert to int
                continue

    # Format each command
    lines = []
    for i, command in enumerate(commands):
        inputs = command.get("inputs", [])
        outputs = command.get("outputs", [])
        call_type = call_types[i] if i < len(call_types) else "CALL"
        command_type = command.get("command_type", "CALL")
        
        # Format target address
        target = command.get("to", "0x0000000000000000000000000000000000000000")
        target_formatted = to_checksum_address(target)
        
        # Format function signature
        function_formatted = command.get("function", f"function({command.get('selector', '0x00000000')})")
        
        # Handle command type
        if command_type != "CALL":
            command_header = f"Command {i}: {function_formatted} @ {target_formatted} [{call_type}, {command_type}]"
        else:
            command_header = f"Command {i}: {function_formatted} @ {target_formatted} [{call_type}]"
        lines.append(command_header)

        # Process inputs
        input_lines = []
        for j, input_val in enumerate(inputs):
            is_last_input = j == len(inputs) - 1
            has_output = bool(outputs)
            
            prefix = "  └─" if is_last_input and not has_output else "  ├─"
            
            # Check if this input is a reference to a previous command's output
            source_cmd = -1
            is_state_reference = False
            
            if isinstance(input_val, int):
                source_cmd, _ = state_sources.get(input_val, (-1, -1))
                is_state_reference = source_cmd >= 0
            
            # Special handling for state placeholder (254 / 0xFE)
            if isinstance(input_val, int) and input_val == 254:  # USE_STATE placeholder
                input_lines.append(f"{prefix} Input {j}: <Current VM State>")
                continue
                
            # Format state reference or direct value
            if isinstance(input_val, int):
                # Special handling for negative indices (placeholders for state or subplans)
                if input_val < 0:
                    if "command_type" in command and command["command_type"] == "SUBPLAN":
                        if input_val == -1:  # SUBPLAN_PLACEHOLDER
                            input_lines.append(f"{prefix} Input {j}: <Subplan>")
                        else:
                            input_lines.append(f"{prefix} Input {j}: <Special Value: {input_val}>")
                    else:
                        input_lines.append(f"{prefix} Input {j}: <Special Value: {input_val}>")
                        
                # Regular state reference
                elif input_val < len(state):
                    value_formatted = format_value(state[input_val])
                    if is_state_reference:
                        input_lines.append(f"{prefix} Input {j}: State[{input_val}] (from Command {source_cmd} output)")
                    else:
                        input_lines.append(f"{prefix} Input {j}: State[{input_val}] = {value_formatted}")
                else:
                    # Reference to state that is not part of initial state but computed during execution
                    if is_state_reference:
                        input_lines.append(f"{prefix} Input {j}: State[{input_val}] (from Command {source_cmd} output)")
                    else:
                        input_lines.append(f"{prefix} Input {j}: State[{input_val}]")
            else:
                # Handle non-integer inputs (should be rare in the planner, more common in decoded plans)
                input_lines.append(f"{prefix} Input {j}: {input_val}")
                
        # Add input lines
        lines.extend(input_lines)
        
        # Format outputs
        if outputs:
            for j, output_val in enumerate(outputs):
                # Find any commands that use this output
                used_in_commands = []
                for cmd_idx, cmd in enumerate(commands):
                    if cmd_idx > i:  # Only look at commands after this one
                        cmd_inputs = cmd.get("inputs", [])
                        for input_idx, inp in enumerate(cmd_inputs):
                            if isinstance(inp, int) and inp == output_val:
                                used_in_commands.append(cmd_idx)
                                break
                
                # Format the output line
                if used_in_commands:
                    next_cmd = used_in_commands[0]
                    lines.append(f"  └─ Output: State[{output_val}] (→ Command {next_cmd})")
                else:
                    lines.append(f"  └─ Output: State[{output_val}] (unused)")
        
        # Add an empty line between commands
        if i < len(commands) - 1:
            lines.append("")

    # Remove the last empty line if it exists
    if lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)