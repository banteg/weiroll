from typing import Any, Dict, Tuple, Optional

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

        # Get function signature from contracts if available
        function_signature = get_function_signature(command, contracts)
        call_type = call_types[i]

        # Format the command line header
        cmd_line = f"Command {i}: {function_signature} @ {to_address} [{call_type}]"

        # Format inputs
        inputs = command.get("inputs", [])
        input_lines = []

        for j, input_val in enumerate(inputs):
            # Get parameter type from function signature if available
            param_type = get_parameter_type(command, j, contracts)

            # Determine the prefix based on position
            is_last_input = j == len(inputs) - 1
            has_output = bool(command.get("outputs", []))

            prefix = "  └─" if is_last_input and not has_output else "  ├─"

            # Check if this input is a reference to a previous command's output
            is_state_reference = False
            source_cmd = -1

            if isinstance(input_val, int):
                source_cmd, _ = state_sources.get(input_val, (-1, -1))
                is_state_reference = source_cmd >= 0

            # Format state reference or direct value
            if isinstance(input_val, int) and input_val < len(state):
                # Regular state reference (from initial state)
                state_val = state[input_val] if input_val < len(state) else None
                formatted_val = format_value(state_val)
                input_lines.append(f"{prefix} Input {j}{param_type}: State[{input_val}] = {formatted_val}")
            elif is_state_reference:
                # Reference to previous command's output
                input_lines.append(
                    f"{prefix} Input {j}{param_type}: State[{input_val}] (from Command {source_cmd} output)"
                )
            else:
                # Direct value - show the raw value
                formatted_val = format_value(input_val)
                input_lines.append(f"{prefix} Input {j}{param_type}: {formatted_val}")

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


def get_function_signature(command: dict[str, Any], contracts: dict[str, Any] | None = None) -> str:
    """
    Get function signature from contracts dictionary or fallback to command's function field.
    
    Args:
        command: Command dictionary containing 'to', 'selector', and 'function' fields
        contracts: Optional dictionary of contract objects to decode function selectors
        
    Returns:
        Function signature string
    """
    function_signature = command.get("function", "")
    
    # If we have valid contracts dictionary, try to get a better function signature
    if contracts and isinstance(contracts, dict):
        target_addr = command.get("to", "").lower() if isinstance(command.get("to", ""), str) else ""
        selector = command.get("selector", "").lower() if isinstance(command.get("selector", ""), str) else ""
        
        # Try to get function signature from contracts
        if target_addr and selector and target_addr in contracts:
            contract = contracts.get(target_addr)
            if contract:
                # Implementation depends on how contracts are structured
                # This is just a placeholder for the actual implementation
                method_signature = get_method_signature_from_contract(contract, selector)
                if method_signature:
                    return method_signature
    
    return function_signature


def get_parameter_type(command: dict[str, Any], param_index: int, contracts: dict[str, Any] | None = None) -> str:
    """
    Get parameter type for a given parameter index in a command.
    
    Args:
        command: Command dictionary
        param_index: Index of the parameter
        contracts: Optional dictionary of contract objects
        
    Returns:
        Parameter type string with surrounding parentheses, or empty string if unknown
    """
    # If contracts dictionary is available, try to derive parameter types from it
    if contracts and isinstance(contracts, dict):
        target_addr = command.get("to", "").lower() if isinstance(command.get("to", ""), str) else ""
        selector = command.get("selector", "").lower() if isinstance(command.get("selector", ""), str) else ""
        
        if target_addr and selector and target_addr in contracts:
            contract = contracts.get(target_addr)
            if contract:
                param_type = get_param_type_from_contract(contract, selector, param_index)
                if param_type:
                    return f" ({param_type})"
    
    return ""


def get_method_signature_from_contract(contract: Any, selector: str) -> Optional[str]:
    """
    Extract method signature from contract using selector.
    This implementation depends on the structure of the contract objects.
    
    Args:
        contract: Contract object
        selector: Function selector (4 bytes hex string)
        
    Returns:
        Method signature string or None if not found
    """
    # Placeholder - implementation depends on the structure of contract objects
    # In a real implementation, this would look up the function in the contract's ABI
    return None


def get_param_type_from_contract(contract: Any, selector: str, param_index: int) -> Optional[str]:
    """
    Get parameter type for a specific parameter in a function.
    This implementation depends on the structure of the contract objects.
    
    Args:
        contract: Contract object
        selector: Function selector (4 bytes hex string)
        param_index: Index of the parameter
        
    Returns:
        Parameter type string or None if not found
    """
    # Placeholder - implementation depends on the structure of contract objects
    # In a real implementation, this would look up the parameter type in the contract's ABI
    return None
