"""
HTML rendering utilities for Weiroll plans.

Provides functions to render a plan as HTML for display in environments like Jupyter notebooks and Marimo.
"""

from typing import Any, Dict, List, Optional
import colorcet as cc
from jinja2 import Template


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

    # Process command data for rendering
    processed_commands = []
    for i, command in enumerate(commands):
        call_type = call_types[i] if i < len(call_types) else "CALL"
        command_type = command.get("command_type", "CALL")
        target = command.get("to", "0x0000000000000000000000000000000000000000")
        function = command.get("function", f"function({command.get('selector', '0x00000000')})")
        contract_name = command.get("contract_name", "")
        inputs = command.get("inputs", [])
        outputs = command.get("outputs", [])

        # Process inputs
        processed_inputs = []
        for j, input_val in enumerate(inputs):
            is_last_input = j == len(inputs) - 1
            has_output = bool(outputs)
            branch_char = "└─" if is_last_input and not has_output else "├─"

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
                input_label = f"{param_type} {param_name}"
            elif param_type:
                input_label = f"{param_type}"
            else:
                input_label = f"Input {j}"

            # Get the source command
            source_cmd = -1
            if "input_sources" in command and j < len(command["input_sources"]):
                source_cmd = command["input_sources"][j]

            input_data = {
                "index": j,
                "value": input_val,
                "is_last": is_last_input,
                "has_output": has_output,
                "branch_char": branch_char,
                "param_type": param_type,
                "param_name": param_name,
                "input_label": input_label,
                "source_cmd": source_cmd,
            }

            # Process state reference for numeric values
            if isinstance(input_val, int) or (isinstance(input_val, str) and input_val.isdigit()):
                try:
                    numeric_val = int(input_val)
                    input_data["numeric_val"] = numeric_val

                    # For state references
                    if isinstance(numeric_val, int) and numeric_val >= 0:
                        input_data["is_state_ref"] = True
                        input_data["state_color_class"] = f"state-{numeric_val % 20}"

                        if source_cmd >= 0:
                            input_data["has_source"] = True
                        elif numeric_val < len(state):
                            input_data["is_initial_state"] = True
                            # Get formatted value
                            from ..utils.formatters import format_value

                            input_data["value_formatted"] = format_value(state[numeric_val])

                            # Determine value class
                            if isinstance(state[numeric_val], str):
                                if state[numeric_val].startswith("0x"):
                                    if len(state[numeric_val]) == 42:  # Ethereum address
                                        input_data["value_class"] = "value-address"
                                    else:
                                        input_data["value_class"] = "value-bytes"
                                else:
                                    input_data["value_class"] = "value-string"
                            elif isinstance(state[numeric_val], (int, float)):
                                input_data["value_class"] = "value-number"
                            elif isinstance(state[numeric_val], bool):
                                input_data["value_class"] = "value-bool"
                            else:
                                input_data["value_class"] = "value-string"
                    # For negative indices (special values)
                    elif isinstance(numeric_val, int) and numeric_val < 0:
                        input_data["is_special_value"] = True
                        if "command_type" in command and command["command_type"] == "SUBPLAN":
                            input_data["is_subplan"] = True
                except (ValueError, TypeError):
                    # Non-numeric state reference
                    pass
            else:
                # Non-integer input
                from ..utils.formatters import format_value

                input_data["value_text"] = format_value(input_val)

            processed_inputs.append(input_data)

        # Process outputs
        processed_outputs = []
        if outputs:
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
                    output_label = f"{output_type} output"
                else:
                    output_label = "Output"

                output_data = {
                    "value": output_val,
                    "numeric_val": numeric_output_val,
                    "output_type": output_type,
                    "output_label": output_label,
                    "color_idx": numeric_output_val % 20 if isinstance(numeric_output_val, int) else 0,
                }

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

                            usage_details.append(
                                {
                                    "cmd_idx": cmd_idx,
                                    "fn_name": function_name,
                                    "param_name": param_name,
                                    "param_full": param_full,
                                }
                            )

                output_data["usage_details"] = usage_details
                processed_outputs.append(output_data)

        processed_commands.append(
            {
                "index": i,
                "call_type": call_type,
                "command_type": command_type,
                "target": target,
                "function": function,
                "contract_name": contract_name,
                "call_type_class": f"command-{call_type.lower()}",
                "inputs": processed_inputs,
                "outputs": processed_outputs,
            }
        )

    # Define the Jinja2 template
    template_str = """
<div class='weiroll-plan'>
  <ul class="tree">
    {% for cmd in commands %}
      <li>
        <!-- Command level -->
        <div class='command-header'>Command {{ cmd.index }}: 
          {% if cmd.contract_name %}
            <span class='function-name'>{{ cmd.contract_name }}</span> @ <span class='address'>{{ cmd.target }}</span>
          {% else %}
            <span class='address'>{{ cmd.target }}</span>
          {% endif %}
        </div>
        <ul>
          <li>
            <!-- Method level -->
            <div class='{{ cmd.call_type_class }}'>
              <span class='function-name'>{{ cmd.function }}</span> 
              <span class='command-type'>[{% if cmd.command_type != "CALL" %}{{ cmd.call_type }}, {{ cmd.command_type }}{% else %}{{ cmd.call_type }}{% endif %}]</span>
            </div>
            <ul>
              <!-- Inputs -->
              {% for input in cmd.inputs %}
                <li class="command-row" data-command-idx='{{ cmd.index }}'{% if input.is_state_ref and input.numeric_val is defined %} data-state-used='{{ input.numeric_val }}'{% endif %}>
                  <span class='input-label'>{{ input.input_label }}:</span>
                  {% if input.is_state_ref is defined and input.is_state_ref %}
                    <span class='{{ input.state_color_class }}' data-state-ref='{{ input.numeric_val }}' 
                          onmouseover='highlightState({{ input.numeric_val }})' 
                          onmouseout='clearHighlight()'>State[{{ input.numeric_val }}]</span>
                    {% if input.has_source is defined and input.has_source %}
                      <span>(from <span class='function-name'>Command {{ input.source_cmd }}</span> output)</span>
                    {% elif input.is_initial_state is defined and input.is_initial_state %}
                      <span>= <span class='{{ input.value_class }}'>{{ input.value_formatted }}</span></span>
                    {% endif %}
                  {% elif input.is_special_value is defined and input.is_special_value %}
                    {% if input.is_subplan is defined and input.is_subplan %}
                      {% if input.numeric_val == -1 %}
                        <span class='subplan'><Subplan></span>
                      {% else %}
                        <span class='subplan'><Special Value: {{ input.numeric_val }}></span>
                      {% endif %}
                    {% else %}
                      <span class='state-ref'><Special Value: {{ input.numeric_val }}></span>
                    {% endif %}
                  {% else %}
                    <span class='value-string'>{{ input.value_text if input.value_text is defined else input.value }}</span>
                  {% endif %}
                </li>
              {% endfor %}
              <!-- Outputs -->
              {% for output in cmd.outputs %}
                <li class="command-row" data-command-idx='{{ cmd.index }}' data-state-source='{{ output.numeric_val }}'>
                  <span class='output-label'>{{ output.output_label }}:</span>
                  <span class='state-{{ output.color_idx }}' data-state-ref='{{ output.numeric_val }}' 
                        onmouseover='highlightState({{ output.numeric_val }})' 
                        onmouseout='clearHighlight()'>State[{{ output.numeric_val }}]</span>
                  {% if output.usage_details %}
                    <span class='arrow'>→</span>
                    {% if output.usage_details|length == 1 %}
                      {% set usage = output.usage_details[0] %}
                      <span class='function-name'>Command {{ usage.cmd_idx }}</span>
                      {% if usage.fn_name and usage.param_name %}
                        <span>(<span class='param-name' data-state-arg='{{ output.numeric_val }}'>{{ usage.fn_name }} {{ usage.param_full }}</span>)</span>
                      {% endif %}
                    {% else %}
                      {% for usage in output.usage_details %}
                        {% if not loop.first %}<span>, </span>{% endif %}
                        <span class='function-name'>Command {{ usage.cmd_idx }}</span>
                        {% if usage.fn_name and usage.param_name %}
                          <span>(<span class='param-name' data-state-arg='{{ output.numeric_val }}'>{{ usage.fn_name }} {{ usage.param_full }}</span>)</span>
                        {% endif %}
                      {% endfor %}
                    {% endif %}
                  {% else %}
                    <span class='unused'>(unused in future commands)</span>
                  {% endif %}
                </li>
              {% endfor %}
            </ul>
          </li>
        </ul>
      </li>
      {% if not loop.last %}
        <li class="command-separator"></li>
      {% endif %}
    {% endfor %}
  </ul>
</div>

<style>
  :root {
    --weiroll-text: #333333;
    --weiroll-command-header: #1967D2;
    --weiroll-function-name: #0F9D58;
    --weiroll-command-call: #0F9D58;
    --weiroll-command-staticcall: #007B83;
    --weiroll-command-delegatecall: #C65B00;
    --weiroll-address: #9D5700;
    --weiroll-input-label: #555555;
    --weiroll-output-label: #9D5700;
    --weiroll-value-string: #0F9D58;
    --weiroll-unused: #777777;
    --weiroll-subplan: #C62828;
    --weiroll-param-name: #007B83;
    --weiroll-arrow: #777777;
    --weiroll-row-highlight: rgba(200, 200, 255, 0.2);
    --weiroll-highlight-bg: rgba(255, 255, 200, 0.3);
    --weiroll-arg-highlight: rgba(255, 200, 255, 0.3);
  }

  .weiroll-plan {
    font-family: monospace;
    line-height: 1.4;
    color: var(--weiroll-text);
    margin: 0;
    padding: 0;
    background: none;
  }

  .weiroll-plan ul {
    padding-left: 1rem;
    list-style: none;
  }

  .weiroll-plan .command-header {
    font-weight: bold;
    color: var(--weiroll-command-header);
  }

  .weiroll-plan .function-name {
    color: var(--weiroll-function-name);
  }

  .weiroll-plan .address {
    color: var(--weiroll-address);
  }

  .weiroll-plan .input-label {
    color: var(--weiroll-input-label);
  }

  .weiroll-plan .output-label {
    color: var(--weiroll-output-label);
  }

  .weiroll-plan .command-call {
    color: var(--weiroll-command-call);
  }

  .weiroll-plan .command-staticcall {
    color: var(--weiroll-command-staticcall);
  }

  .weiroll-plan .command-delegatecall {
    color: var(--weiroll-command-delegatecall);
  }

  .weiroll-plan .command-type {
    font-style: italic;
  }

  .weiroll-plan .value-string {
    color: var(--weiroll-value-string);
  }

  .weiroll-plan .unused {
    color: var(--weiroll-unused);
    font-style: italic;
  }

  .weiroll-plan .subplan {
    color: var(--weiroll-subplan);
  }

  .weiroll-plan .arrow {
    color: var(--weiroll-arrow);
  }

  .weiroll-plan .param-name {
    color: var(--weiroll-param-name);
  }

  .weiroll-plan [data-state-ref] {
    cursor: pointer;
  }

  .weiroll-plan .highlighted-state {
    background-color: var(--weiroll-highlight-bg);
    text-decoration: underline;
  }

  .weiroll-plan .highlighted-row {
    background-color: var(--weiroll-row-highlight);
  }

  .weiroll-plan .highlighted-arg {
    background-color: var(--weiroll-arg-highlight);
  }
</style>

<script>
  function highlightState(stateId) {
    clearHighlight();
    // Highlight all state references
    document.querySelectorAll(`[data-state-ref='${stateId}']`).forEach(el => {
      el.classList.add('highlighted-state');
    });
    // Highlight command rows that use the state
    const usedRows = document.querySelectorAll(`li[data-state-used='${stateId}']`);
    usedRows.forEach(row => {
      const commandLi = row.closest('ul.tree > li');
      if (commandLi) commandLi.classList.add('highlighted-row');
    });
    // Highlight command rows that produce the state
    const sourceRows = document.querySelectorAll(`li[data-state-source='${stateId}']`);
    sourceRows.forEach(row => {
      const commandLi = row.closest('ul.tree > li');
      if (commandLi) commandLi.classList.add('highlighted-row');
    });
    // Highlight param names that use the state
    document.querySelectorAll(`span[data-state-arg='${stateId}']`).forEach(el => {
      el.classList.add('highlighted-arg');
    });
  }

  function clearHighlight() {
    document.querySelectorAll('.highlighted-state').forEach(el => {
      el.classList.remove('highlighted-state');
    });
    document.querySelectorAll('.highlighted-row').forEach(el => {
      el.classList.remove('highlighted-row');
    });
    document.querySelectorAll('.highlighted-arg').forEach(el => {
      el.classList.remove('highlighted-arg');
    });
  }
</script>
"""

    # Prepare data for the template
    template_data = {
        "commands": processed_commands,
        "state_colors": [(i, color) for i, color in enumerate(state_colors)],
    }

    # Render the template
    template = Template(template_str)
    return template.render(**template_data)
