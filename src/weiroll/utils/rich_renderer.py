"""
Rich rendering utilities for Weiroll plans.

Provides functions to render a plan using the rich library for beautiful terminal output
and HTML export capabilities.
"""

from typing import Any, Dict, List, Optional, Tuple
import colorcet as cc
from rich.console import Console
from rich.tree import Tree
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.style import Style
from rich.box import ROUNDED

from ..utils.formatters import format_value, format_contract_name


def render_rich(
    commands: List[Dict[str, Any]],
    state: List[Any],
    call_types: List[str],
    state_sources: Dict[int, Tuple[int, int]],
    state_usage: Dict[int, List[Tuple[int, int]]],
) -> Console:
    """
    Render a plan using rich for display in terminal and HTML export.

    Args:
        commands: List of command dictionaries
        state: List of state values
        call_types: List of call types (e.g. "CALL", "STATICCALL")
        state_sources: Maps state index to the command that produced it
        state_usage: Maps state index to commands that use it as input

    Returns:
        Console: Rich console object that can be printed or exported to HTML
    """
    if not commands:
        console = Console()
        console.print("[italic]Empty plan (no commands)[/italic]")
        return console

    # Use colorcet's glasbey color palette for better visual distinction
    # Convert hex colors to RGB tuples for consistent handling
    state_colors = []
    for color in cc.b_glasbey_hv:
        if isinstance(color, str) and color.startswith("#"):
            # Convert hex to RGB tuple
            r = int(color[1:3], 16) / 255.0
            g = int(color[3:5], 16) / 255.0
            b = int(color[5:7], 16) / 255.0
            state_colors.append((r, g, b))
        else:
            # Already an RGB tuple
            state_colors.append(color)

    # Create a rich console with recording enabled for HTML export
    console = Console(highlight=False, record=True)

    # Create a main tree for the entire plan
    plan_tree = Tree("Weiroll Plan", guide_style="dim")

    # Process each command
    for i, command in enumerate(commands):
        call_type = call_types[i] if i < len(call_types) else "CALL"
        command_type = command.get("command_type", "CALL")
        target = command.get("to", "0x0000000000000000000000000000000000000000")
        function = command.get("function", f"function({command.get('selector', '0x00000000')})")
        contract_name = command.get("contract_name", "")
        inputs = command.get("inputs", [])
        outputs = command.get("outputs", [])

        # Create command header
        header_text = Text()
        header_text.append(f"Command[{i}]: ", style="bold blue")

        if contract_name:
            header_text.append(format_contract_name(contract_name), style="green")
            header_text.append(" @ ")
            header_text.append(target, style="yellow")
        else:
            header_text.append(target, style="yellow")

        # Style based on call type
        call_type_style = "green"
        if call_type.lower() == "staticcall":
            call_type_style = "cyan"
        elif call_type.lower() == "delegatecall":
            call_type_style = "yellow"

        header_text.append(f" [{call_type}]", style=f"bold {call_type_style}")

        # Create command node
        cmd_node = plan_tree.add(header_text)

        # Add function signature
        function_text = Text(function, style="green")
        fn_node = cmd_node.add(function_text)

        # Process inputs
        if inputs:
            inputs_table = Table(show_header=False, box=None, padding=(0, 1, 0, 0))
            inputs_table.add_column("Label", style="bright_white")
            inputs_table.add_column("Value")
            inputs_table.add_column("Source")

            for j, input_val in enumerate(inputs):
                # Process parameter info
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

                # Process state reference for numeric values
                if isinstance(input_val, int) or (isinstance(input_val, str) and input_val.isdigit()):
                    try:
                        numeric_val = int(input_val)

                        # For state references
                        if isinstance(numeric_val, int) and numeric_val >= 0:
                            # Determine color for this state slot
                            color_idx = numeric_val % len(state_colors)
                            rgb = state_colors[color_idx]
                            hex_color = f"#{int(rgb[0] * 255):02x}{int(rgb[1] * 255):02x}{int(rgb[2] * 255):02x}"

                            state_ref = Text(f"State[{numeric_val}]", style=f"bold {hex_color}")

                            source_text = ""
                            if source_cmd >= 0:
                                source_text = Text(f"Command[{source_cmd}] output", style="green")
                            elif numeric_val < len(state):
                                state_value = state[numeric_val]
                                if state_value != "0x" and state_value != "" and state_value is not None:
                                    value_formatted = format_value(state_value)

                                    # Style based on type
                                    value_style = "default"
                                    if isinstance(state_value, str):
                                        if state_value.startswith("0x"):
                                            if len(state_value) == 42:  # Ethereum address
                                                value_style = "yellow"
                                            else:
                                                value_style = "magenta"
                                        else:
                                            value_style = "green"
                                    elif isinstance(state_value, (int, float)):
                                        value_style = "bright_yellow"
                                    elif isinstance(state_value, bool):
                                        value_style = "bright_cyan"

                                    source_text = Text(f"= {value_formatted}", style=value_style)

                            inputs_table.add_row(input_label, state_ref, source_text)

                        # For negative indices (special values)
                        elif isinstance(numeric_val, int) and numeric_val < 0:
                            if "command_type" in command and command["command_type"] == "SUBPLAN":
                                if numeric_val == -1:
                                    special_text = Text("<Subplan>", style="bright_magenta")
                                else:
                                    special_text = Text(f"<Special Value: {numeric_val}>", style="bright_magenta")
                            else:
                                special_text = Text(f"<Special Value: {numeric_val}>", style="magenta")

                            inputs_table.add_row(input_label, special_text, "")

                    except (ValueError, TypeError):
                        # Non-numeric state reference
                        value_text = Text(str(input_val), style="green")
                        inputs_table.add_row(input_label, value_text, "")
                else:
                    # Non-integer input
                    value_text = Text(format_value(input_val), style="green")
                    inputs_table.add_row(input_label, value_text, "")

            fn_node.add(inputs_table)

        # Process outputs
        if outputs:
            outputs_table = Table(show_header=False, box=None, padding=(0, 1, 0, 0))
            outputs_table.add_column("Label", style="bright_yellow")
            outputs_table.add_column("Value")
            outputs_table.add_column("Usage")

            for output_val in outputs:
                # Create a numeric value for the output
                try:
                    numeric_output_val = int(output_val)
                except (ValueError, TypeError):
                    numeric_output_val = output_val

                # Extract output type if available
                output_type = ""
                if "function" in command:
                    function_sig = command.get("function", "")
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

                # Determine color for this state slot
                if isinstance(numeric_output_val, int):
                    color_idx = numeric_output_val % len(state_colors)
                    rgb = state_colors[color_idx]
                    hex_color = f"#{int(rgb[0] * 255):02x}{int(rgb[1] * 255):02x}{int(rgb[2] * 255):02x}"

                    state_ref = Text(f"State[{numeric_output_val}]", style=f"bold {hex_color}")

                    # Find if output is used by later commands
                    usage_text = Text()
                    if numeric_output_val in state_usage:
                        usage_details = []
                        for cmd_idx, input_idx in state_usage[numeric_output_val]:
                            if cmd_idx > i:  # Only consider future commands
                                cmd = commands[cmd_idx]
                                function_name = cmd.get("function", "")
                                if "(" in function_name:
                                    function_name = function_name.split("(")[0]

                                # Try to get parameter name
                                param_name = f"param{input_idx}"

                                function_sig = cmd.get("function", "")
                                if "(" in function_sig and ")" in function_sig:
                                    params_section = function_sig.split("(")[1].split(")")[0]
                                    params = params_section.split(",")
                                    if input_idx < len(params):
                                        param = params[input_idx].strip()
                                        if " " in param:
                                            param_name = (
                                                param.split(" ")[1]
                                                if len(param.split(" ")) > 1
                                                else param.split(" ")[0]
                                            )

                                usage_details.append((cmd_idx, function_name, param_name))

                        if usage_details:
                            usage_text.append("→ ", style="dim")
                            for idx, (cmd_idx, fn_name, param_name) in enumerate(usage_details):
                                if idx > 0:
                                    usage_text.append(", ")

                                usage_text.append(f"Command[{cmd_idx}]", style="green")
                                if fn_name and param_name:
                                    usage_text.append(f" {fn_name}.{param_name}", style="cyan")
                        else:
                            usage_text = Text("(unused in future commands)", style="dim")
                    else:
                        usage_text = Text("(unused in future commands)", style="dim")

                    outputs_table.add_row(output_label, state_ref, usage_text)
                else:
                    # Non-numeric output
                    value_text = Text(str(output_val), style="green")
                    outputs_table.add_row(output_label, value_text, "")

            fn_node.add(outputs_table)

    # Print the tree to the console
    console.print(plan_tree)

    return console


def render_rich_html(
    commands: List[Dict[str, Any]],
    state: List[Any],
    call_types: List[str],
    state_sources: Dict[int, Tuple[int, int]],
    state_usage: Dict[int, List[Tuple[int, int]]],
) -> str:
    """
    Render a plan as HTML using rich's HTML export capability.

    Args:
        commands: List of command dictionaries
        state: List of state values
        call_types: List of call types (e.g. "CALL", "STATICCALL")
        state_sources: Maps state index to the command that produced it
        state_usage: Maps state index to commands that use it as input

    Returns:
        str: HTML representation of the plan with colors
    """
    # Create a console with recording enabled for HTML export
    console = render_rich(commands, state, call_types, state_sources, state_usage)

    # Export to HTML with external CSS for better customization
    html = console.export_html(inline_styles=False)

    # Add custom CSS for light/dark mode support
    custom_css = """
<style>
    /* Base styles */
    .weiroll-plan pre {
        background-color: transparent !important;
        margin: 0;
        padding: 10px;
    }
    
    .weiroll-plan code {
        background-color: transparent !important;
    }
    
    /* Light mode styles */
    @media (prefers-color-scheme: light) {
        .weiroll-plan {
            color: #333;
        }
        /* Input labels - typically white in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffffff"] {
            color: #555 !important;
        }
        /* Output labels - typically yellow in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffff00"] {
            color: #9D5700 !important;
        }
        /* Unused in future commands - typically dim in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #7f7f7f"],
        .weiroll-plan span[class^="r"][style*="color: #8a8a8a"] {
            color: #777 !important;
        }
    }
    
    /* Dark mode styles */
    @media (prefers-color-scheme: dark) {
        body {
            background-color: #1e1e1e !important;
        }
        .weiroll-plan {
            color: #eee !important;
        }
        /* Command headers - typically blue in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #000080"] {
            color: #569CD6 !important;
        }
        /* Input labels - typically white in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffffff"] {
            color: #aaa !important;
        }
        /* Output labels - typically yellow in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffff00"] {
            color: #FFB74D !important;
        }
        /* Unused in future commands - typically dim in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #7f7f7f"],
        .weiroll-plan span[class^="r"][style*="color: #8a8a8a"] {
            color: #999 !important;
        }
        /* Addresses - typically yellow in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #808000"] {
            color: #90CAF9 !important;
        }
        /* Function names - typically green in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #008000"] {
            color: #81C784 !important;
        }
        /* State references - keep their colors but make them slightly brighter */
        .weiroll-plan span[class^="r"][style*="font-weight: bold"] {
            filter: brightness(1.2);
        }
    }
</style>
"""

    # Wrap the content in a div with the weiroll-plan class and add custom CSS
    html = html.replace("<body>", f"<body>\n{custom_css}\n<div class='weiroll-plan'>")
    html = html.replace("</body>", "</div>\n</body>")

    # Fix media query by adding @ symbol if missing
    html = html.replace("media (prefers-color-scheme:", "@media (prefers-color-scheme:")


"""
Rich rendering utilities for Weiroll plans.

Provides functions to render a plan using the rich library for beautiful terminal output
and HTML export capabilities.
"""

from typing import Any, Dict, List, Optional, Tuple
import colorcet as cc
from rich.console import Console
from rich.tree import Tree
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.style import Style
from rich.box import ROUNDED

from ..utils.formatters import format_value, format_contract_name


def render_rich(
    commands: List[Dict[str, Any]],
    state: List[Any],
    call_types: List[str],
    state_sources: Dict[int, Tuple[int, int]],
    state_usage: Dict[int, List[Tuple[int, int]]],
) -> Console:
    """
    Render a plan using rich for display in terminal and HTML export.

    Args:
        commands: List of command dictionaries
        state: List of state values
        call_types: List of call types (e.g. "CALL", "STATICCALL")
        state_sources: Maps state index to the command that produced it
        state_usage: Maps state index to commands that use it as input

    Returns:
        Console: Rich console object that can be printed or exported to HTML
    """
    if not commands:
        console = Console()
        console.print("[italic]Empty plan (no commands)[/italic]")
        return console

    # Use colorcet's glasbey color palette for better visual distinction
    # Convert hex colors to RGB tuples for consistent handling
    state_colors = []
    for color in cc.b_glasbey_hv:
        if isinstance(color, str) and color.startswith("#"):
            # Convert hex to RGB tuple
            r = int(color[1:3], 16) / 255.0
            g = int(color[3:5], 16) / 255.0
            b = int(color[5:7], 16) / 255.0
            state_colors.append((r, g, b))
        else:
            # Already an RGB tuple
            state_colors.append(color)

    # Create a rich console with recording enabled for HTML export
    console = Console(highlight=False, record=True)

    # Create a main tree for the entire plan
    plan_tree = Tree("Weiroll Plan", guide_style="dim")

    # Process each command
    for i, command in enumerate(commands):
        call_type = call_types[i] if i < len(call_types) else "CALL"
        command_type = command.get("command_type", "CALL")
        target = command.get("to", "0x0000000000000000000000000000000000000000")
        function = command.get("function", f"function({command.get('selector', '0x00000000')})")
        contract_name = command.get("contract_name", "")
        inputs = command.get("inputs", [])
        outputs = command.get("outputs", [])

        # Create command header
        header_text = Text()
        header_text.append(f"Command[{i}]: ", style="bold blue")

        if contract_name:
            header_text.append(format_contract_name(contract_name), style="green")
            header_text.append(" @ ")
            header_text.append(target, style="yellow")
        else:
            header_text.append(target, style="yellow")

        # Style based on call type
        call_type_style = "green"
        if call_type.lower() == "staticcall":
            call_type_style = "cyan"
        elif call_type.lower() == "delegatecall":
            call_type_style = "yellow"

        header_text.append(f" [{call_type}]", style=f"bold {call_type_style}")

        # Create command node
        cmd_node = plan_tree.add(header_text)

        # Add function signature
        function_text = Text(function, style="green")
        fn_node = cmd_node.add(function_text)

        # Process inputs
        if inputs:
            inputs_table = Table(show_header=False, box=None, padding=(0, 1, 0, 0))
            inputs_table.add_column("Label", style="bright_white")
            inputs_table.add_column("Value")
            inputs_table.add_column("Source")

            for j, input_val in enumerate(inputs):
                # Process parameter info
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

                # Process state reference for numeric values
                if isinstance(input_val, int) or (isinstance(input_val, str) and input_val.isdigit()):
                    try:
                        numeric_val = int(input_val)

                        # For state references
                        if isinstance(numeric_val, int) and numeric_val >= 0:
                            # Determine color for this state slot
                            color_idx = numeric_val % len(state_colors)
                            rgb = state_colors[color_idx]
                            hex_color = f"#{int(rgb[0] * 255):02x}{int(rgb[1] * 255):02x}{int(rgb[2] * 255):02x}"

                            state_ref = Text(f"State[{numeric_val}]", style=f"bold {hex_color}")

                            source_text = ""
                            if source_cmd >= 0:
                                source_text = Text(f"Command[{source_cmd}] output", style="green")
                            elif numeric_val < len(state):
                                state_value = state[numeric_val]
                                if state_value != "0x" and state_value != "" and state_value is not None:
                                    value_formatted = format_value(state_value)

                                    # Style based on type
                                    value_style = "default"
                                    if isinstance(state_value, str):
                                        if state_value.startswith("0x"):
                                            if len(state_value) == 42:  # Ethereum address
                                                value_style = "yellow"
                                            else:
                                                value_style = "magenta"
                                        else:
                                            value_style = "green"
                                    elif isinstance(state_value, (int, float)):
                                        value_style = "bright_yellow"
                                    elif isinstance(state_value, bool):
                                        value_style = "bright_cyan"

                                    source_text = Text(f"= {value_formatted}", style=value_style)

                            inputs_table.add_row(input_label, state_ref, source_text)

                        # For negative indices (special values)
                        elif isinstance(numeric_val, int) and numeric_val < 0:
                            if "command_type" in command and command["command_type"] == "SUBPLAN":
                                if numeric_val == -1:
                                    special_text = Text("<Subplan>", style="bright_magenta")
                                else:
                                    special_text = Text(f"<Special Value: {numeric_val}>", style="bright_magenta")
                            else:
                                special_text = Text(f"<Special Value: {numeric_val}>", style="magenta")

                            inputs_table.add_row(input_label, special_text, "")

                    except (ValueError, TypeError):
                        # Non-numeric state reference
                        value_text = Text(str(input_val), style="green")
                        inputs_table.add_row(input_label, value_text, "")
                else:
                    # Non-integer input
                    value_text = Text(format_value(input_val), style="green")
                    inputs_table.add_row(input_label, value_text, "")

            fn_node.add(inputs_table)

        # Process outputs
        if outputs:
            outputs_table = Table(show_header=False, box=None, padding=(0, 1, 0, 0))
            outputs_table.add_column("Label", style="bright_yellow")
            outputs_table.add_column("Value")
            outputs_table.add_column("Usage")

            for output_val in outputs:
                # Create a numeric value for the output
                try:
                    numeric_output_val = int(output_val)
                except (ValueError, TypeError):
                    numeric_output_val = output_val

                # Extract output type if available
                output_type = ""
                if "function" in command:
                    function_sig = command.get("function", "")
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

                # Determine color for this state slot
                if isinstance(numeric_output_val, int):
                    color_idx = numeric_output_val % len(state_colors)
                    rgb = state_colors[color_idx]
                    hex_color = f"#{int(rgb[0] * 255):02x}{int(rgb[1] * 255):02x}{int(rgb[2] * 255):02x}"

                    state_ref = Text(f"State[{numeric_output_val}]", style=f"bold {hex_color}")

                    # Find if output is used by later commands
                    usage_text = Text()
                    if numeric_output_val in state_usage:
                        usage_details = []
                        for cmd_idx, input_idx in state_usage[numeric_output_val]:
                            if cmd_idx > i:  # Only consider future commands
                                cmd = commands[cmd_idx]
                                function_name = cmd.get("function", "")
                                if "(" in function_name:
                                    function_name = function_name.split("(")[0]

                                # Try to get parameter name
                                param_name = f"param{input_idx}"

                                function_sig = cmd.get("function", "")
                                if "(" in function_sig and ")" in function_sig:
                                    params_section = function_sig.split("(")[1].split(")")[0]
                                    params = params_section.split(",")
                                    if input_idx < len(params):
                                        param = params[input_idx].strip()
                                        if " " in param:
                                            param_name = (
                                                param.split(" ")[1]
                                                if len(param.split(" ")) > 1
                                                else param.split(" ")[0]
                                            )

                                usage_details.append((cmd_idx, function_name, param_name))

                        if usage_details:
                            usage_text.append("→ ", style="dim")
                            for idx, (cmd_idx, fn_name, param_name) in enumerate(usage_details):
                                if idx > 0:
                                    usage_text.append(", ")

                                usage_text.append(f"Command[{cmd_idx}]", style="green")
                                if fn_name and param_name:
                                    usage_text.append(f" {fn_name}.{param_name}", style="cyan")
                        else:
                            usage_text = Text("(unused in future commands)", style="dim")
                    else:
                        usage_text = Text("(unused in future commands)", style="dim")

                    outputs_table.add_row(output_label, state_ref, usage_text)
                else:
                    # Non-numeric output
                    value_text = Text(str(output_val), style="green")
                    outputs_table.add_row(output_label, value_text, "")

            fn_node.add(outputs_table)

    # Print the tree to the console
    console.print(plan_tree)

    return console


def render_rich_html(
    commands: List[Dict[str, Any]],
    state: List[Any],
    call_types: List[str],
    state_sources: Dict[int, Tuple[int, int]],
    state_usage: Dict[int, List[Tuple[int, int]]],
) -> str:
    """
    Render a plan as HTML using rich's HTML export capability.

    Args:
        commands: List of command dictionaries
        state: List of state values
        call_types: List of call types (e.g. "CALL", "STATICCALL")
        state_sources: Maps state index to the command that produced it
        state_usage: Maps state index to commands that use it as input

    Returns:
        str: HTML representation of the plan with colors
    """
    # Create a console with recording enabled for HTML export
    console = render_rich(commands, state, call_types, state_sources, state_usage)

    # Export to HTML with external CSS for better customization
    html = console.export_html(inline_styles=False)

    # Add custom CSS for light/dark mode support
    custom_css = """
<style>
    /* Base styles */
    .weiroll-plan pre {
        background-color: transparent !important;
        margin: 0;
        padding: 10px;
    }
    
    .weiroll-plan code {
        background-color: transparent !important;
    }
    
    /* Light mode styles */
    @media (prefers-color-scheme: light) {
        .weiroll-plan {
            color: #333;
        }
        /* Input labels - typically white in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffffff"] {
            color: #555 !important;
        }
        /* Output labels - typically yellow in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffff00"] {
            color: #9D5700 !important;
        }
        /* Unused in future commands - typically dim in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #7f7f7f"],
        .weiroll-plan span[class^="r"][style*="color: #8a8a8a"] {
            color: #777 !important;
        }
    }
    
    /* Dark mode styles */
    @media (prefers-color-scheme: dark) {
        body {
            background-color: #1e1e1e !important;
        }
        .weiroll-plan {
            color: #eee !important;
        }
        /* Command headers - typically blue in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #000080"] {
            color: #569CD6 !important;
        }
        /* Input labels - typically white in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffffff"] {
            color: #aaa !important;
        }
        /* Output labels - typically yellow in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffff00"] {
            color: #FFB74D !important;
        }
        /* Unused in future commands - typically dim in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #7f7f7f"],
        .weiroll-plan span[class^="r"][style*="color: #8a8a8a"] {
            color: #999 !important;
        }
        /* Addresses - typically yellow in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #808000"] {
            color: #90CAF9 !important;
        }
        /* Function names - typically green in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #008000"] {
            color: #81C784 !important;
        }
        /* State references - keep their colors but make them slightly brighter */
        .weiroll-plan span[class^="r"][style*="font-weight: bold"] {
            filter: brightness(1.2);
        }
    }
</style>
"""


"""
Rich rendering utilities for Weiroll plans.

Provides functions to render a plan using the rich library for beautiful terminal output
and HTML export capabilities.
"""

from typing import Any, Dict, List, Optional, Tuple
import colorcet as cc
from rich.console import Console
from rich.tree import Tree
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.style import Style
from rich.box import ROUNDED

from ..utils.formatters import format_value, format_contract_name


def render_rich(
    commands: List[Dict[str, Any]],
    state: List[Any],
    call_types: List[str],
    state_sources: Dict[int, Tuple[int, int]],
    state_usage: Dict[int, List[Tuple[int, int]]],
) -> Console:
    """
    Render a plan using rich for display in terminal and HTML export.

    Args:
        commands: List of command dictionaries
        state: List of state values
        call_types: List of call types (e.g. "CALL", "STATICCALL")
        state_sources: Maps state index to the command that produced it
        state_usage: Maps state index to commands that use it as input

    Returns:
        Console: Rich console object that can be printed or exported to HTML
    """
    if not commands:
        console = Console()
        console.print("[italic]Empty plan (no commands)[/italic]")
        return console

    # Use colorcet's glasbey color palette for better visual distinction
    # Convert hex colors to RGB tuples for consistent handling
    state_colors = []
    for color in cc.b_glasbey_hv:
        if isinstance(color, str) and color.startswith("#"):
            # Convert hex to RGB tuple
            r = int(color[1:3], 16) / 255.0
            g = int(color[3:5], 16) / 255.0
            b = int(color[5:7], 16) / 255.0
            state_colors.append((r, g, b))
        else:
            # Already an RGB tuple
            state_colors.append(color)

    # Create a rich console with recording enabled for HTML export
    console = Console(highlight=False, record=True)

    # Create a main tree for the entire plan
    plan_tree = Tree("Weiroll Plan", guide_style="dim")

    # Process each command
    for i, command in enumerate(commands):
        call_type = call_types[i] if i < len(call_types) else "CALL"
        command_type = command.get("command_type", "CALL")
        target = command.get("to", "0x0000000000000000000000000000000000000000")
        function = command.get("function", f"function({command.get('selector', '0x00000000')})")
        contract_name = command.get("contract_name", "")
        inputs = command.get("inputs", [])
        outputs = command.get("outputs", [])

        # Create command header
        header_text = Text()
        header_text.append(f"Command[{i}]: ", style="bold blue")

        if contract_name:
            header_text.append(format_contract_name(contract_name), style="green")
            header_text.append(" @ ")
            header_text.append(target, style="yellow")
        else:
            header_text.append(target, style="yellow")

        # Style based on call type
        call_type_style = "green"
        if call_type.lower() == "staticcall":
            call_type_style = "cyan"
        elif call_type.lower() == "delegatecall":
            call_type_style = "yellow"

        header_text.append(f" [{call_type}]", style=f"bold {call_type_style}")

        # Create command node
        cmd_node = plan_tree.add(header_text)

        # Add function signature
        function_text = Text(function, style="green")
        fn_node = cmd_node.add(function_text)

        # Process inputs
        if inputs:
            inputs_table = Table(show_header=False, box=None, padding=(0, 1, 0, 0))
            inputs_table.add_column("Label", style="bright_white")
            inputs_table.add_column("Value")
            inputs_table.add_column("Source")

            for j, input_val in enumerate(inputs):
                # Process parameter info
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

                # Process state reference for numeric values
                if isinstance(input_val, int) or (isinstance(input_val, str) and input_val.isdigit()):
                    try:
                        numeric_val = int(input_val)

                        # For state references
                        if isinstance(numeric_val, int) and numeric_val >= 0:
                            # Determine color for this state slot
                            color_idx = numeric_val % len(state_colors)
                            rgb = state_colors[color_idx]
                            hex_color = f"#{int(rgb[0] * 255):02x}{int(rgb[1] * 255):02x}{int(rgb[2] * 255):02x}"

                            state_ref = Text(f"State[{numeric_val}]", style=f"bold {hex_color}")

                            source_text = ""
                            if source_cmd >= 0:
                                source_text = Text(f"Command[{source_cmd}] output", style="green")
                            elif numeric_val < len(state):
                                state_value = state[numeric_val]
                                if state_value != "0x" and state_value != "" and state_value is not None:
                                    value_formatted = format_value(state_value)

                                    # Style based on type
                                    value_style = "default"
                                    if isinstance(state_value, str):
                                        if state_value.startswith("0x"):
                                            if len(state_value) == 42:  # Ethereum address
                                                value_style = "yellow"
                                            else:
                                                value_style = "magenta"
                                        else:
                                            value_style = "green"
                                    elif isinstance(state_value, (int, float)):
                                        value_style = "bright_yellow"
                                    elif isinstance(state_value, bool):
                                        value_style = "bright_cyan"

                                    source_text = Text(f"= {value_formatted}", style=value_style)

                            inputs_table.add_row(input_label, state_ref, source_text)

                        # For negative indices (special values)
                        elif isinstance(numeric_val, int) and numeric_val < 0:
                            if "command_type" in command and command["command_type"] == "SUBPLAN":
                                if numeric_val == -1:
                                    special_text = Text("<Subplan>", style="bright_magenta")
                                else:
                                    special_text = Text(f"<Special Value: {numeric_val}>", style="bright_magenta")
                            else:
                                special_text = Text(f"<Special Value: {numeric_val}>", style="magenta")

                            inputs_table.add_row(input_label, special_text, "")

                    except (ValueError, TypeError):
                        # Non-numeric state reference
                        value_text = Text(str(input_val), style="green")
                        inputs_table.add_row(input_label, value_text, "")
                else:
                    # Non-integer input
                    value_text = Text(format_value(input_val), style="green")
                    inputs_table.add_row(input_label, value_text, "")

            fn_node.add(inputs_table)

        # Process outputs
        if outputs:
            outputs_table = Table(show_header=False, box=None, padding=(0, 1, 0, 0))
            outputs_table.add_column("Label", style="bright_yellow")
            outputs_table.add_column("Value")
            outputs_table.add_column("Usage")

            for output_val in outputs:
                # Create a numeric value for the output
                try:
                    numeric_output_val = int(output_val)
                except (ValueError, TypeError):
                    numeric_output_val = output_val

                # Extract output type if available
                output_type = ""
                if "function" in command:
                    function_sig = command.get("function", "")
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

                # Determine color for this state slot
                if isinstance(numeric_output_val, int):
                    color_idx = numeric_output_val % len(state_colors)
                    rgb = state_colors[color_idx]
                    hex_color = f"#{int(rgb[0] * 255):02x}{int(rgb[1] * 255):02x}{int(rgb[2] * 255):02x}"

                    state_ref = Text(f"State[{numeric_output_val}]", style=f"bold {hex_color}")

                    # Find if output is used by later commands
                    usage_text = Text()
                    if numeric_output_val in state_usage:
                        usage_details = []
                        for cmd_idx, input_idx in state_usage[numeric_output_val]:
                            if cmd_idx > i:  # Only consider future commands
                                cmd = commands[cmd_idx]
                                function_name = cmd.get("function", "")
                                if "(" in function_name:
                                    function_name = function_name.split("(")[0]

                                # Try to get parameter name
                                param_name = f"param{input_idx}"

                                function_sig = cmd.get("function", "")
                                if "(" in function_sig and ")" in function_sig:
                                    params_section = function_sig.split("(")[1].split(")")[0]
                                    params = params_section.split(",")
                                    if input_idx < len(params):
                                        param = params[input_idx].strip()
                                        if " " in param:
                                            param_name = (
                                                param.split(" ")[1]
                                                if len(param.split(" ")) > 1
                                                else param.split(" ")[0]
                                            )

                                usage_details.append((cmd_idx, function_name, param_name))

                        if usage_details:
                            usage_text.append("→ ", style="dim")
                            for idx, (cmd_idx, fn_name, param_name) in enumerate(usage_details):
                                if idx > 0:
                                    usage_text.append(", ")

                                usage_text.append(f"Command[{cmd_idx}]", style="green")
                                if fn_name and param_name:
                                    usage_text.append(f" {fn_name}.{param_name}", style="cyan")
                        else:
                            usage_text = Text("(unused in future commands)", style="dim")
                    else:
                        usage_text = Text("(unused in future commands)", style="dim")

                    outputs_table.add_row(output_label, state_ref, usage_text)
                else:
                    # Non-numeric output
                    value_text = Text(str(output_val), style="green")
                    outputs_table.add_row(output_label, value_text, "")

            fn_node.add(outputs_table)

    # Print the tree to the console
    console.print(plan_tree)

    return console


def render_rich_html(
    commands: List[Dict[str, Any]],
    state: List[Any],
    call_types: List[str],
    state_sources: Dict[int, Tuple[int, int]],
    state_usage: Dict[int, List[Tuple[int, int]]],
) -> str:
    """
    Render a plan as HTML using rich's HTML export capability.

    Args:
        commands: List of command dictionaries
        state: List of state values
        call_types: List of call types (e.g. "CALL", "STATICCALL")
        state_sources: Maps state index to the command that produced it
        state_usage: Maps state index to commands that use it as input

    Returns:
        str: HTML representation of the plan with colors
    """
    # Create a console with recording enabled for HTML export
    console = render_rich(commands, state, call_types, state_sources, state_usage)

    # Export to HTML with external CSS for better customization
    html = console.export_html(inline_styles=False)

    # Add custom CSS for light/dark mode support
    custom_css = """
<style>
    /* Base styles */
    .weiroll-plan pre {
        background-color: transparent !important;
        margin: 0;
        padding: 10px;
    }
    
    .weiroll-plan code {
        background-color: transparent !important;
    }
    
    /* Light mode styles */
    @media (prefers-color-scheme: light) {
        .weiroll-plan {
            color: #333;
        }
        /* Input labels - typically white in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffffff"] {
            color: #555 !important;
        }
        /* Output labels - typically yellow in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffff00"] {
            color: #9D5700 !important;
        }
        /* Unused in future commands - typically dim in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #7f7f7f"],
        .weiroll-plan span[class^="r"][style*="color: #8a8a8a"] {
            color: #777 !important;
        }
    }
    
    /* Dark mode styles */
    @media (prefers-color-scheme: dark) {
        body {
            background-color: #1e1e1e !important;
        }
        .weiroll-plan {
            color: #eee !important;
        }
        /* Command headers - typically blue in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #000080"] {
            color: #569CD6 !important;
        }
        /* Input labels - typically white in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffffff"] {
            color: #aaa !important;
        }
        /* Output labels - typically yellow in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #ffff00"] {
            color: #FFB74D !important;
        }
        /* Unused in future commands - typically dim in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #7f7f7f"],
        .weiroll-plan span[class^="r"][style*="color: #8a8a8a"] {
            color: #999 !important;
        }
        /* Addresses - typically yellow in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #808000"] {
            color: #90CAF9 !important;
        }
        /* Function names - typically green in Rich output */
        .weiroll-plan span[class^="r"][style*="color: #008000"] {
            color: #81C784 !important;
        }
        /* State references - keep their colors but make them slightly brighter */
        .weiroll-plan span[class^="r"][style*="font-weight: bold"] {
            filter: brightness(1.2);
        }
    }
</style>
"""

    # Wrap the content in a div with the weiroll-plan class and add custom CSS
    html = html.replace("<body>", f"<body>\n{custom_css}\n<div class='weiroll-plan'>")
    html = html.replace("</body>", "</div>\n</body>")

    return html
