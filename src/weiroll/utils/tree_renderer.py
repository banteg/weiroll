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
            if isinstance(input_val, int) and input_val < len(state) + i:
                if input_val not in state_usage:
                    state_usage[input_val] = []
                state_usage[input_val].append((i, input_idx))

        outputs = command.get("outputs", [])
        for output_idx, state_idx in enumerate(outputs):
            if state_idx < len(state) + i + 1:  # Include output indices that may exceed state array
                state_sources[state_idx] = (i, output_idx)

    # Format each command
    lines = []

    for i, command in enumerate(commands):
        to_address = command.get("to", "0x")
        if isinstance(to_address, str) and to_address.startswith("0x"):
            to_address = to_checksum_address(to_address)

        # Get function signature
        function_signature = command.get("function", "")
        call_type = call_types[i]

        # Format the command line header
        cmd_line = f"Command {i}: {function_signature} @ {to_address} [{call_type}]"

        # Format inputs
        inputs = command.get("inputs", [])
        input_lines = []

        for j, input_val in enumerate(inputs):
            # Determine the prefix based on position
            is_last_input = j == len(inputs) - 1
            has_output = bool(command.get("outputs", []))

            prefix = "  └─" if is_last_input and not has_output else "  ├─"

            # Check if this input is a reference to a previous command's output
            source_cmd = -1
            is_state_reference = False

            if isinstance(input_val, int):
                source_cmd, _ = state_sources.get(input_val, (-1, -1))
                is_state_reference = source_cmd >= 0

            # Format state reference or direct value
            if isinstance(input_val, int):
                if is_state_reference:
                    # Reference to previous command's output
                    if input_val < len(state):
                        # If we have the state value, show both the reference and the value
                        state_val = state[input_val] if input_val < len(state) else None
                        formatted_val = format_value(state_val)
                        if formatted_val != "0x" and formatted_val != "":  # Only show value if non-empty
                            input_lines.append(f"{prefix} Input {j}: State[{input_val}] = {formatted_val} (from Command {source_cmd} output)")
                        else:
                            input_lines.append(f"{prefix} Input {j}: State[{input_val}] (from Command {source_cmd} output)")
                    else:
                        # Just show the reference if we don't have the value
                        input_lines.append(f"{prefix} Input {j}: State[{input_val}] (from Command {source_cmd} output)")
                elif input_val < len(state):
                    # Regular state reference (from initial state)
                    state_val = state[input_val] if input_val < len(state) else None
                    formatted_val = format_value(state_val)
                    input_lines.append(f"{prefix} Input {j}: State[{input_val}] = {formatted_val}")
                else:
                    # State reference but index out of range
                    input_lines.append(f"{prefix} Input {j}: State[{input_val}]")
            else:
                # Direct value - show the raw value
                formatted_val = format_value(input_val)
                input_lines.append(f"{prefix} Input {j}: {formatted_val}")

        # Format outputs
        outputs = command.get("outputs", [])
        output_lines = []

        for j, output_idx in enumerate(outputs):
            # Find usage info
            usage_info = state_usage.get(output_idx, [])
            # Filter out this command itself
            usage_info = [(cmd_idx, inp_idx) for cmd_idx, inp_idx in usage_info if cmd_idx != i]

            if usage_info:
                # Sort by command index for consistent output
                usage_info.sort(key=lambda x: x[0])
                next_cmd = usage_info[0][0]
                usage_str = f" (→ Command {next_cmd})"
            else:
                usage_str = " (unused)"

            output_lines.append(f"  └─ Output: State[{output_idx}]{usage_str}")

        # Combine all lines for this command
        lines.append(cmd_line)
        lines.extend(input_lines)
        lines.extend(output_lines)
        lines.append("")  # Empty line between commands

    # Remove the last empty line if it exists
    if lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)