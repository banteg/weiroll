from eth_utils import function_signature_to_4byte_selector, to_bytes

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
    assert len(plan["state"]) >= 2  # At least value + output


def test_planner_with_extended_inputs(multi_function_contract):
    """Test planner with extended inputs (more than 6 arguments)."""
    # Create a Contract instance
    contract = Contract(multi_function_contract)
    
    # Create a planner
    planner = Planner()
    
    # Create a command with 10 inputs to trigger extended inputs
    from weiroll.command import Command, CommandArg
    
    # Create input arguments (10 of them)
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
    
    # Check that we got two commands (original + extended inputs)
    assert len(plan["commands"]) == 2
    
    # Verify the extended inputs command follows the main command
    main_cmd = Command.decode(plan["commands"][0])
    ext_cmd = Command.decode(plan["commands"][1])
    
    # Check the main command has the EXT_BIT flag set
    assert main_cmd.extended_inputs == True
    
    # Check the extended inputs command has the special marker
    assert ext_cmd.function_selector == b"\xFF\xFF\xFF\xFF"
    
    # Check the extended inputs command has the right number of inputs
    assert len(ext_cmd.inputs) == 4  # Should have inputs 6-9
    
    # We can't fully test the decoder because it tries to look up contract info
    # Just verify the raw command fields directly
    assert len(main_cmd.inputs) > 6  # With our dummy inputs added
    assert ext_cmd.function_selector == b"\xFF\xFF\xFF\xFF"
    assert len(ext_cmd.inputs) == 4  # 4 extended inputs
