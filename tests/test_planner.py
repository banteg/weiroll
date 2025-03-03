from eth_utils import function_signature_to_4byte_selector, to_bytes

from weiroll.command import Command, CommandArg
from weiroll.constants import CallType
from weiroll.contract import Contract, StateValue
from weiroll.planner import Planner


def test_planner_basic(simple_contract):
    # Create a Contract instance
    contract = Contract(simple_contract)

    # Create a Planner
    planner = Planner()

    # Add a function call to the plan
    result = planner.add(contract.add(5, 10))

    # Verify the state values
    assert len(planner.state) == 2  # Two inputs: 5 and 10
    assert planner.state[0] == 5
    assert planner.state[1] == 10

    # Verify the command
    assert len(planner.commands) == 1
    cmd = planner.commands[0]
    assert cmd.function_selector == function_signature_to_4byte_selector("add(uint256,uint256)")
    assert cmd.target == to_bytes(hexstr=simple_contract.address)
    assert len(cmd.inputs) == 2
    assert cmd.inputs[0].index == 0
    assert cmd.inputs[1].index == 1
    assert cmd.output.index == 2

    # Verify the result StateValue
    assert isinstance(result, StateValue)
    assert result.index == 2

    # Generate the plan
    plan = planner.plan()

    # Verify the encoded plan
    assert len(plan["commands"]) == 1
    assert len(plan["state"]) == 3  # 2 inputs + 1 output
    assert plan["state"][0].startswith("0x")  # Encoded uint256
    assert plan["state"][1].startswith("0x")  # Encoded uint256
    assert plan["state"][2] == "0x"  # Empty placeholder for output


def test_planner_chained_operations(multi_function_contract):
    # Create a Contract instance
    contract = Contract(multi_function_contract)

    # Create a Planner
    planner = Planner()

    # Chain operations: (5 + 10) * 2
    sum_result = planner.add(contract.add(5, 10))
    planner.add(contract.multiply(sum_result, 2))

    # Verify the state
    assert len(planner.state) == 3  # Three inputs: 5, 10, and 2

    # Verify the commands
    assert len(planner.commands) == 2

    # Verify the plan
    plan = planner.plan()
    assert len(plan["commands"]) == 2
    assert len(plan["state"]) == 5  # 3 inputs + 2 outputs


def test_planner_with_value_call(deposit_contract):
    # Create a Contract instance
    contract = Contract(deposit_contract)

    # Get the deposit function and set it to use CALL
    deposit_fn = contract.deposit

    # Create a Planner
    planner = Planner()

    # Check if deposit function has outputs
    has_outputs = deposit_fn.method_abis[0].outputs and len(deposit_fn.method_abis[0].outputs) > 0
    expected_state_entries = 1  # At least value
    if has_outputs:
        expected_state_entries += 1  # Plus output if there are outputs

    # Add a value call
    planner.add(deposit_fn().with_value(1000000000000000000))  # 1 ETH

    # Verify the command
    assert len(planner.commands) == 1
    cmd = planner.commands[0]
    assert cmd.call_type == CallType.VALUECALL
    assert len(cmd.inputs) == 1  # Value is added as first input

    # Generate the plan
    plan = planner.plan()

    # Verify the encoded plan
    assert len(plan["commands"]) == 1
    assert len(plan["state"]) == expected_state_entries  # Value (and output if applicable)


def test_planner_with_extended_inputs(multi_function_contract):
    """Test planner with extended inputs (more than 6 arguments)."""
    planner = Planner()
    contract = Contract(multi_function_contract)

    # Create 10 inputs (more than the default 6 allowed in a standard command)
    inputs = []
    for i in range(10):
        state_index = planner._add_to_state(i)
        inputs.append(CommandArg(index=state_index))
    
    # Create a command with the extended inputs
    command = Command(
        function_selector=function_signature_to_4byte_selector("test(uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256)"),
        target=to_bytes(hexstr=multi_function_contract.address),
        inputs=inputs,
        output=CommandArg(index=10),
        call_type=CallType.CALL,
    )
    
    # Add the command to the planner
    planner.commands.append(command)
    
    # Generate the plan
    plan = planner.plan()
    
    # With new format, we should have only one command that's encoded as 64 bytes
    assert len(plan["commands"]) == 1
    
    # Verify the command is correctly encoded
    decoded_cmd = Command.decode(bytes.fromhex(plan["commands"][0][2:]))  # Remove '0x' prefix
    
    # Check the command has the EXT_BIT flag set
    assert decoded_cmd.extended_inputs
    
    # Check it has the right number of inputs
    assert len(decoded_cmd.inputs) == 10
    
    # Check that the inputs are properly preserved
    for i, input_arg in enumerate(decoded_cmd.inputs):
        assert input_arg.index == inputs[i].index
    
    # Check output is correct
    assert decoded_cmd.output.index == 10


def test_planner_with_no_output_functions(deposit_contract):
    """Test that functions with no outputs are handled correctly."""
    # Create a Contract instance
    contract = Contract(deposit_contract)

    # Get the deposit function
    deposit_fn = contract.deposit

    # Create a Planner
    planner = Planner()

    # Add a call to a function with no outputs
    result = planner.add(deposit_fn())

    # Verify that the result is None if function has no outputs
    has_outputs = deposit_fn.method_abis[0].outputs and len(deposit_fn.method_abis[0].outputs) > 0
    if not has_outputs:
        assert result is None
    else:
        assert result is not None

    # Verify the command
    assert len(planner.commands) == 1
    cmd = planner.commands[0]
    
    # Verify the command's output is None if the function has no outputs
    if not has_outputs:
        assert cmd.output is None
    else:
        assert cmd.output is not None

    # Generate the plan
    plan = planner.plan()

    # Verify the encoded plan
    assert len(plan["commands"]) == 1
    
    # If no outputs, state should only have the arguments (if any)
    expected_state_entries = 0  # No inputs
    assert len(plan["state"]) == expected_state_entries
