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
                "source_cmd": source_cmd
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
                                        
                            usage_details.append({
                                "cmd_idx": cmd_idx,
                                "fn_name": function_name,
                                "param_name": param_name,
                                "param_full": param_full
                            })
                
                output_data["usage_details"] = usage_details
                processed_outputs.append(output_data)
                
        processed_commands.append({
            "index": i,
            "call_type": call_type,
            "command_type": command_type,
            "target": target,
            "function": function,
            "contract_name": contract_name,
            "call_type_class": f"command-{call_type.lower()}",
            "inputs": processed_inputs,
            "outputs": processed_outputs
        })

    # Define the Jinja2 template
    template_str = """
<style>
:root {
  --weiroll-bg: rgba(0, 0, 0, 0.03);
  --weiroll-text: #333333;
  --weiroll-command-header: #1967D2;
  --weiroll-function-name: #0F9D58;
  --weiroll-command-call: #0F9D58;
  --weiroll-command-staticcall: #007B83;
  --weiroll-command-delegatecall: #C65B00;
  --weiroll-tree-branch: #777777;
  --weiroll-address: #9D5700;
  --weiroll-input-label: #555555;
  --weiroll-output-label: #9D5700;
  --weiroll-value-string: #0F9D58;
  --weiroll-value-number: #9D5700;
  --weiroll-value-bool: #007B83;
  --weiroll-value-address: #9D5700;
  --weiroll-value-bytes: #9C27B0;
  --weiroll-unused: #777777;
  --weiroll-subplan: #C62828;
  --weiroll-param-name: #007B83;
  --weiroll-arrow: #777777;
  --weiroll-highlight-bg: rgba(255, 255, 200, 0.3);
  --weiroll-row-highlight: rgba(200, 200, 255, 0.2);
  --weiroll-arg-highlight: rgba(255, 200, 255, 0.3);
}

@media (prefers-color-scheme: dark) {
  :root {
    --weiroll-bg: rgba(255, 255, 255, 0.05);
    --weiroll-text: #E8EAED;
    --weiroll-command-header: #4285F4;
    --weiroll-function-name: #0F9D58;
    --weiroll-command-call: #34A853;
    --weiroll-command-staticcall: #00ACC1;
    --weiroll-command-delegatecall: #FBBC05;
    --weiroll-tree-branch: #9AA0A6;
    --weiroll-address: #F4B400;
    --weiroll-input-label: #E8EAED;
    --weiroll-output-label: #F4B400;
    --weiroll-value-string: #34A853;
    --weiroll-value-number: #F4B400;
    --weiroll-value-bool: #00ACC1;
    --weiroll-value-address: #F4B400;
    --weiroll-value-bytes: #9C27B0;
    --weiroll-unused: #9AA0A6;
    --weiroll-subplan: #DB4437;
    --weiroll-param-name: #00ACC1;
    --weiroll-arrow: #9AA0A6;
    --weiroll-highlight-bg: rgba(255, 255, 100, 0.2);
    --weiroll-row-highlight: rgba(150, 150, 255, 0.15);
    --weiroll-arg-highlight: rgba(255, 200, 255, 0.2);
  }
}

.weiroll-plan { font-family: monospace; line-height: 1.4; color: var(--weiroll-text); background: var(--weiroll-bg); padding: 10px; border-radius: 4px; }
.weiroll-plan div { margin: 0; padding: 0; }
.weiroll-plan .command-row { display: flex; flex-wrap: wrap; align-items: baseline; padding: 2px 0; }
.weiroll-plan .command-inputs-container, .weiroll-plan .command-outputs-container { position: relative; }
/* Tree view CSS based on Kate Morley's tree view implementation */
.weiroll-plan .tree {
  --spacing: 1.5rem;
  --radius: 10px;
}

.weiroll-plan .tree li {
  display: block;
  position: relative;
  padding-left: calc(2 * var(--spacing) - var(--radius) - 2px);
}

.weiroll-plan .tree ul {
  margin-left: calc(var(--radius) - var(--spacing));
  padding-left: 0;
}

.weiroll-plan .tree ul li {
  border-left: 2px solid var(--weiroll-tree-branch);
}

.weiroll-plan .tree ul li:last-child {
  border-color: transparent;
}

.weiroll-plan .tree ul li::before {
  content: '';
  display: block;
  position: absolute;
  top: calc(var(--spacing) / -2);
  left: -2px;
  width: calc(var(--spacing) + 2px);
  height: calc(var(--spacing) + 1px);
  border: solid var(--weiroll-tree-branch);
  border-width: 0 0 2px 2px;
}

.weiroll-plan .tree li::after {
  content: '';
  display: block;
  position: absolute;
  top: calc(var(--spacing) / 2 - var(--radius));
  left: calc(var(--spacing) - var(--radius) - 1px);
  width: calc(2 * var(--radius));
  height: calc(2 * var(--radius));
  border-radius: 50%;
  background: var(--weiroll-tree-branch);
  z-index: 0;
}

/* Simple tree view without collapsible functionality */
.weiroll-plan .tree-simple li {
  display: block;
  position: relative;
  padding-left: 1.2em;
  margin-bottom: 0.5em;
}

.weiroll-plan .tree-simple li::before {
  content: '';
  display: block;
  position: absolute;
  top: 0.5em;
  left: 0;
  width: 0.5em;
  height: 0.5em;
  border-radius: 50%;
  background-color: var(--weiroll-tree-branch);
}

.weiroll-plan .tree-simple li:last-child {
  margin-bottom: 0;
}

/* Command styling */
.weiroll-plan .command-row {
  padding: 0.1em 0;
}

.weiroll-plan .command-header {
  margin-top: 1.5em;
  padding-bottom: 0.5em;
}

.weiroll-plan .command-container {
  margin-bottom: 1.5em;
  padding-left: 0.5em;
}
.weiroll-plan .command-separator { height: 10px; }
.weiroll-plan .command-header { font-weight: bold; color: var(--weiroll-command-header); margin-top: 10px; }
.weiroll-plan .command-call { color: var(--weiroll-command-call); }
.weiroll-plan .command-staticcall { color: var(--weiroll-command-staticcall); }
.weiroll-plan .command-delegatecall { color: var(--weiroll-command-delegatecall); }
.weiroll-plan .command-type { font-style: italic; }
.weiroll-plan .tree-branch { color: var(--weiroll-tree-branch); }
.weiroll-plan .function-name { color: var(--weiroll-function-name); }
.weiroll-plan .address { color: var(--weiroll-address); }
.weiroll-plan .input-label { color: var(--weiroll-input-label); }
.weiroll-plan .output-label { color: var(--weiroll-output-label); }
.weiroll-plan .value-string { color: var(--weiroll-value-string); }
.weiroll-plan .value-number { color: var(--weiroll-value-number); }
.weiroll-plan .value-bool { color: var(--weiroll-value-bool); }
.weiroll-plan .value-address { color: var(--weiroll-value-address); }
.weiroll-plan .value-bytes { color: var(--weiroll-value-bytes); }
.weiroll-plan .unused { color: var(--weiroll-unused); font-style: italic; }
.weiroll-plan .subplan { color: var(--weiroll-subplan); }
.weiroll-plan .param-name { color: var(--weiroll-param-name); }
.weiroll-plan .arrow { color: var(--weiroll-arrow); }

{% for i, color in state_colors %}
.weiroll-plan .state-{{ i }} { color: {{ color }}; font-weight: bold; }
{% endfor %}

:root {
{% for i, color in state_colors %}
  --state-{{ i }}-color: {{ color }};
{% endfor %}
}

/* Interactivity styles */
.weiroll-plan div[data-state-used], .weiroll-plan div[data-state-source] { transition: background-color 0.15s ease; }
.weiroll-plan [data-state-ref] { transition: background-color 0.15s ease; cursor: pointer; }
.weiroll-plan .highlighted-state { background-color: var(--weiroll-highlight-bg) !important; text-decoration: underline; }
.weiroll-plan .highlighted-row { background-color: var(--weiroll-row-highlight) !important; }
.weiroll-plan .highlighted-arg { background-color: var(--weiroll-arg-highlight) !important; }
</style>

<script>
function highlightState(stateId) {
  // Unhighlight any previously highlighted elements
  clearHighlight();
  
  // Highlight all state references with this ID
  document.querySelectorAll(`[data-state-ref='${stateId}']`).forEach(el => {
    el.classList.add('highlighted-state');
  });
  
  // Highlight all rows that use or produce this state
  document.querySelectorAll(`div[data-state-used='${stateId}']`).forEach(el => {
    el.classList.add('highlighted-row');
  });
  document.querySelectorAll(`div[data-state-source='${stateId}']`).forEach(el => {
    el.classList.add('highlighted-row');
  });
  
  // Highlight all arguments that use this state
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

<div class='weiroll-plan'>
{% for cmd in commands %}
  <div class='command-header'>Command {{ cmd.index }}: 
    {% if cmd.contract_name %}
    <span class='function-name'>{{ cmd.contract_name }}</span> @ <span class='address'>{{ cmd.target }}</span>
    {% else %}
    <span class='address'>{{ cmd.target }}</span>
    {% endif %}
  </div>
  
  <div class='{{ cmd.call_type_class }}'>
    <span class='function-name'>{{ cmd.function }}</span> 
    <span class='command-type'>[{% if cmd.command_type != "CALL" %}{{ cmd.call_type }}, {{ cmd.command_type }}]{% else %}{{ cmd.call_type }}]{% endif %}</span>
  </div>
  
  {# Process inputs and outputs in a Kate Morley-style tree view #}
  <div class="command-container">
    <ul class="tree">
      <li>
        <ul>
          {# Process inputs #}
          {% for input in cmd.inputs %}
            <li class="command-row" data-command-idx='{{ cmd.index }}'{% if input.is_state_ref and input.numeric_val is defined %} data-state-used='{{ input.numeric_val }}'{% endif %}>
              <span class='input-label'>{{ input.input_label }}:</span>
              
              {% if input.is_state_ref is defined and input.is_state_ref %}
                {# State reference #}
                <span class='{{ input.state_color_class }}' data-state-ref='{{ input.numeric_val }}' 
                      onmouseover='highlightState({{ input.numeric_val }})' 
                      onmouseout='clearHighlight()'>State[{{ input.numeric_val }}]</span>
                
                {% if input.has_source is defined and input.has_source %}
                  <span>(from <span class='function-name'>Command {{ input.source_cmd }}</span> output)</span>
                {% elif input.is_initial_state is defined and input.is_initial_state %}
                  <span>= <span class='{{ input.value_class }}'>{{ input.value_formatted }}</span></span>
                {% endif %}
                
              {% elif input.is_special_value is defined and input.is_special_value %}
                {# Special value (negative index) #}
                {% if input.is_subplan is defined and input.is_subplan %}
                  {% if input.numeric_val == -1 %}
                  <span class='subplan'>&lt;Subplan&gt;</span>
                  {% else %}
                  <span class='subplan'>&lt;Special Value: {{ input.numeric_val }}&gt;</span>
                  {% endif %}
                {% else %}
                  <span class='state-ref'>&lt;Special Value: {{ input.numeric_val }}&gt;</span>
                {% endif %}
                
              {% else %}
                {# Regular value #}
                <span class='value-string'>{{ input.value_text if input.value_text is defined else input.value }}</span>
              {% endif %}
            </li>
          {% endfor %}
          
          {# Process outputs #}
          {% if cmd.outputs %}
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
          {% endif %}
        </ul>
      </li>
    </ul>
  </div>
  
  {% if not loop.last %}
  <div class="command-separator"></div>
  {% endif %}
{% endfor %}
</div>
"""

    # Prepare data for the template
    template_data = {
        "commands": processed_commands,
        "state_colors": [(i, color) for i, color in enumerate(state_colors)]
    }
    
    # Render the template
    template = Template(template_str)
    return template.render(**template_data)
