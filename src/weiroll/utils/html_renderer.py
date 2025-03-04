"""
HTML rendering utilities for Weiroll plans.

Provides functions to render a plan as HTML for display in environments like Jupyter notebooks and Marimo.
"""

from typing import Any, Dict, List, Optional
import colorcet as cc


def render_html(
    commands: List[Dict[str, Any]],
    state: List[Any],
    call_types: List[str],
    state_sources: Dict[int, tuple],
    state_usage: Dict[int, list],
) -> str:
    """
    Render a plan as HTML for display in notebook environments like Jupyter and Marimo.

    Args:
        commands: List of command dictionaries
        state: List of state values
        call_types: List of call types (e.g. "CALL", "STATICCALL")
        state_sources: Maps state index to the command that produced it
        state_usage: Maps state index to commands that use it as input

    Returns:
        str: HTML representation of the plan
    """
    if not commands:
        return "<div class='weiroll-plan'><p><em>Empty plan (no commands)</em></p></div>"

    # Use colorcet's glasbey color palette for better visual distinction
    # cc.b_glasbey_hv is already a list of hex color strings
    state_colors = cc.b_glasbey_hv

    # Build HTML representation with CSS that works on both light and dark backgrounds
    html = [
        "<style>",
        ":root {",
        "  --weiroll-bg: rgba(0, 0, 0, 0.03);",
        "  --weiroll-text: #333333;",
        "  --weiroll-command-header: #1967D2;",
        "  --weiroll-function-name: #0F9D58;",
        "  --weiroll-command-call: #0F9D58;",
        "  --weiroll-command-staticcall: #007B83;",
        "  --weiroll-command-delegatecall: #C65B00;",
        "  --weiroll-tree-branch: #777777;",
        "  --weiroll-address: #9D5700;",
        "  --weiroll-input-label: #555555;",
        "  --weiroll-output-label: #9D5700;",
        "  --weiroll-value-string: #0F9D58;",
        "  --weiroll-value-number: #9D5700;",
        "  --weiroll-value-bool: #007B83;",
        "  --weiroll-value-address: #9D5700;",
        "  --weiroll-value-bytes: #9C27B0;",
        "  --weiroll-unused: #777777;",
        "  --weiroll-subplan: #C62828;",
        "  --weiroll-param-name: #007B83;",
        "  --weiroll-arrow: #777777;",
        "  --weiroll-highlight-bg: rgba(255, 255, 200, 0.3);",
        "  --weiroll-row-highlight: rgba(200, 200, 255, 0.2);",
        "}",
        "",
        "@media (prefers-color-scheme: dark) {",
        "  :root {",
        "    --weiroll-bg: rgba(255, 255, 255, 0.05);",
        "    --weiroll-text: #E8EAED;",
        "    --weiroll-command-header: #4285F4;",
        "    --weiroll-function-name: #0F9D58;",
        "    --weiroll-command-call: #34A853;",
        "    --weiroll-command-staticcall: #00ACC1;",
        "    --weiroll-command-delegatecall: #FBBC05;",
        "    --weiroll-tree-branch: #9AA0A6;",
        "    --weiroll-address: #F4B400;",
        "    --weiroll-input-label: #E8EAED;",
        "    --weiroll-output-label: #F4B400;",
        "    --weiroll-value-string: #34A853;",
        "    --weiroll-value-number: #F4B400;",
        "    --weiroll-value-bool: #00ACC1;",
        "    --weiroll-value-address: #F4B400;",
        "    --weiroll-value-bytes: #9C27B0;",
        "    --weiroll-unused: #9AA0A6;",
        "    --weiroll-subplan: #DB4437;",
        "    --weiroll-param-name: #00ACC1;",
        "    --weiroll-arrow: #9AA0A6;",
        "    --weiroll-highlight-bg: rgba(255, 255, 100, 0.2);",
        "    --weiroll-row-highlight: rgba(150, 150, 255, 0.15);",
        "  }",
        "}",
        "",
        ".weiroll-plan { font-family: monospace; white-space: pre; line-height: 1.2; color: var(--weiroll-text); background: var(--weiroll-bg); padding: 10px; border-radius: 4px; }",
        ".weiroll-plan div { margin: 0; padding: 0; }",
        ".weiroll-plan .command-header { font-weight: bold; color: var(--weiroll-command-header); margin-top: 10px; }",
        ".weiroll-plan .command-call { color: var(--weiroll-command-call); }",
        ".weiroll-plan .command-staticcall { color: var(--weiroll-command-staticcall); }",
        ".weiroll-plan .command-delegatecall { color: var(--weiroll-command-delegatecall); }",
        ".weiroll-plan .command-type { font-style: italic; }",
        ".weiroll-plan .tree-branch { color: var(--weiroll-tree-branch); }",
        ".weiroll-plan .function-name { color: var(--weiroll-function-name); }",
        ".weiroll-plan .address { color: var(--weiroll-address); }",
        ".weiroll-plan .input-label { color: var(--weiroll-input-label); font-weight: 600; }",
        ".weiroll-plan .output-label { color: var(--weiroll-output-label); }",
        ".weiroll-plan .value-string { color: var(--weiroll-value-string); }",
        ".weiroll-plan .value-number { color: var(--weiroll-value-number); }",
        ".weiroll-plan .value-bool { color: var(--weiroll-value-bool); }",
        ".weiroll-plan .value-address { color: var(--weiroll-value-address); }",
        ".weiroll-plan .value-bytes { color: var(--weiroll-value-bytes); }",
        ".weiroll-plan .unused { color: var(--weiroll-unused); font-style: italic; }",
        ".weiroll-plan .subplan { color: var(--weiroll-subplan); }",
        ".weiroll-plan .param-name { color: var(--weiroll-param-name); }",
        ".weiroll-plan .arrow { color: var(--weiroll-arrow); }",
    ]

    # Add state-specific styles with colors
    for i, color in enumerate(state_colors):
        html.append(f".weiroll-plan .state-{i} {{ color: {color}; font-weight: bold; }}")

    # Add CSS variables for state colors
    html.append(":root {")
    for i, color in enumerate(state_colors):
        html.append(f"  --state-{i}-color: {color};")
    html.append("}")

    # Add interactivity styles
    html.extend(
        [
            # Hover interactivity styles
            ".weiroll-plan div[data-state-used], .weiroll-plan div[data-state-source] { transition: background-color 0.15s ease; }",
            ".weiroll-plan [data-state-ref] { transition: background-color 0.15s ease; cursor: pointer; }",
            ".weiroll-plan .highlighted-state { background-color: var(--weiroll-highlight-bg) !important; text-decoration: underline; }",
            ".weiroll-plan .highlighted-row { background-color: var(--weiroll-row-highlight) !important; }",
            "</style>",
            "<script>",
            "function highlightState(stateId) {",
            "  // Unhighlight any previously highlighted elements",
            "  clearHighlight();",
            "  ",
            "  // Highlight all state references with this ID",
            "  document.querySelectorAll(`[data-state-ref='${stateId}']`).forEach(el => {",
            "    el.classList.add('highlighted-state');",
            "  });",
            "  ",
            "  // Highlight all rows that use or produce this state",
            "  document.querySelectorAll(`div[data-state-used='${stateId}']`).forEach(el => {",
            "    el.classList.add('highlighted-row');",
            "  });",
            "  document.querySelectorAll(`div[data-state-source='${stateId}']`).forEach(el => {",
            "    el.classList.add('highlighted-row');",
            "  });",
            "}",
            "",
            "function clearHighlight() {",
            "  document.querySelectorAll('.highlighted-state').forEach(el => {",
            "    el.classList.remove('highlighted-state');",
            "  });",
            "  document.querySelectorAll('.highlighted-row').forEach(el => {",
            "    el.classList.remove('highlighted-row');",
            "  });",
            "}",
            "</script>",
            "<div class='weiroll-plan'>",
        ]
    )

    # Format each command
    for i, command in enumerate(commands):
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
            header_line += f"<span class='function-name'>{contract_name}</span> @ <span class='address'>{target}</span>"
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
                    state_ref = (
                        f"<span class='{state_color_class}' data-state-ref='{numeric_val}' "
                        + f"onmouseover='highlightState({numeric_val})' "
                        + f"onmouseout='clearHighlight()'>State[{numeric_val}]</span>"
                    )

                    if source_cmd >= 0:
                        # Show source command
                        cmd_ref = f"<span class='function-name'>Command {source_cmd}</span>"
                        html.append(
                            f"<div data-command-idx='{i}' data-state-used='{numeric_val}'>  <span class='tree-branch'>{branch_char}</span> <span class='input-label'>{input_label}</span> {state_ref} (from {cmd_ref} output)</div>"
                        )
                    elif numeric_val < len(state):
                        # It's an initial state value
                        from ..utils.formatters import format_value

                        value_formatted = format_value(state[numeric_val])

                        # Format value based on type
                        value_class = "value-string"
                        if isinstance(state[numeric_val], str):
                            if state[numeric_val].startswith("0x"):
                                if len(state[numeric_val]) == 42:  # Ethereum address
                                    value_class = "value-address"
                                else:
                                    value_class = "value-bytes"
                            else:
                                value_class = "value-string"
                        elif isinstance(state[numeric_val], (int, float)):
                            value_class = "value-number"
                        elif isinstance(state[numeric_val], bool):
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
                from ..utils.formatters import format_value

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
                if "function" in commands[i]:
                    function_sig = commands[i].get("function", "")
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
                if isinstance(numeric_output_val, int) and numeric_output_val in state_usage:
                    for cmd_idx, input_idx in state_usage[numeric_output_val]:
                        if cmd_idx > i:  # Only consider future commands
                            cmd = commands[cmd_idx]
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
                                            param.split(" ")[1] if len(param.split(" ")) > 1 else param.split(" ")[0]
                                        )

                            usage_details.append((cmd_idx, function_name, param_name, param_full))

                # Format the output line with usage information
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
        if i < len(commands) - 1:
            html.append("<div style='height: 10px;'></div>")

    # Close container div
    html.append("</div>")

    return "".join(html)
