import textwrap

import ape

from weiroll import Contract, Decoder, Planner, CallType


# Define the expected output for the vault plan tree test
expected_vault_plan_output = textwrap.dedent("""
Command 0: balanceOf(address holder) -> uint256 @ 0x6B175474E89094C44Da98b954EedeAC495271d0F [CALL]
  ├─ Input 0: State[0] = 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
  └─ Output: State[1] (→ Command 1)

Command 1: deposit(uint256 assets, address receiver) -> uint256 @ 0xd8063123BBA3B480569244AE66BFE72B6c84b00d [CALL]
  ├─ Input 0: State[1] (from Command 0 output)
  ├─ Input 1: State[0] = 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
  └─ Output: State[2] (→ Command 2)

Command 2: redeem(uint256 shares, address receiver, address owner) -> uint256 @ 0xd8063123BBA3B480569244AE66BFE72B6c84b00d [CALL]
  ├─ Input 0: State[2] (from Command 1 output)
  ├─ Input 1: State[0] = 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
  ├─ Input 2: State[0] = 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
  └─ Output: State[3] (unused)
""").strip()


def test_command_decoding():
    """Test that commands can be properly decoded."""
    # Create a mock command as bytes32
    command_hex = "0x771602f7000001ffffffffff1234567890123456789012345678901234567890"

    # Decode the command
    decoded = Decoder.decode_command(command_hex)

    # Verify decoded fields
    assert decoded.selector == "0x771602f7"
    assert decoded.target == "0x1234567890123456789012345678901234567890"
    assert decoded.call_type == "DELEGATECALL"
    assert decoded.inputs == [0, 1]
    assert decoded.output is None
    assert not decoded.is_tuple_return
    assert not decoded.is_extended


def test_plan_decoding(math_contract):
    """Test that a full plan can be decoded."""
    # Create a test planner and generate a plan using the math_contract fixture
    math = Contract(math_contract, call_type=CallType.DELEGATECALL)

    # Create a planner with a few operations
    planner = Planner()
    sum1 = planner.add(math.add(1, 2))
    planner.add(math.add(sum1, 3))

    # Generate the plan
    plan = planner.plan()

    # Decode the plan
    decoded = Decoder.decode_plan(plan["commands"], plan["state"])

    # Verify the plan structure
    assert len(decoded.commands) == 2
    assert decoded.commands[0].target.lower() == math_contract.address.lower()
    assert decoded.commands[1].target.lower() == math_contract.address.lower()

    # Check that we can stringify the plan for display
    plan_str = str(decoded)
    assert "Command 0:" in plan_str
    assert "Command 1:" in plan_str


def test_various_command_types():
    """Test decoding commands with different call types."""
    # Create test command bytes for different call types
    commands = {
        "delegatecall": "0x771602f7000001ffffffffff1234567890123456789012345678901234567890",
        "call": "0x771602f7010001ffffffffff1234567890123456789012345678901234567890",
        "staticcall": "0x771602f7020001ffffffffff1234567890123456789012345678901234567890",
        "valuecall": "0x771602f7030001ffffffffff1234567890123456789012345678901234567890",
    }

    # Verify each call type is correctly decoded
    decoded_delegatecall = Decoder.decode_command(commands["delegatecall"])
    assert decoded_delegatecall.call_type == "DELEGATECALL"

    decoded_call = Decoder.decode_command(commands["call"])
    assert decoded_call.call_type == "CALL"

    decoded_staticcall = Decoder.decode_command(commands["staticcall"])
    assert decoded_staticcall.call_type == "STATICCALL"

    decoded_valuecall = Decoder.decode_command(commands["valuecall"])
    assert decoded_valuecall.call_type == "VALUECALL"


def test_decoder_state_handling():
    """Test that state values are properly displayed in the decoded plan."""
    # Create a simple plan with some state values
    commands = ["0x771602f7000001ffffffffff1234567890123456789012345678901234567890"]
    state = [
        "0x0000000000000000000000000000000000000000000000000000000000000001",
        "0x0000000000000000000000000000000000000000000000000000000000000002",
        "0x",  # Empty state for the output slot
    ]

    # Decode the plan
    decoded = Decoder.decode_plan(commands, state)

    # Check state formatting
    assert len(decoded.state) == 3

    # Convert to string and check the format
    plan_str = str(decoded)
    assert "Command 0:" in plan_str


def test_show_tree_format(math_contract):
    """Test that the show_tree method formats plans in the correct tree format."""
    # Create a test planner with dependent commands using the math_contract fixture
    math = Contract(math_contract, call_type=CallType.DELEGATECALL)

    # Create a planner with a few operations where outputs are used as inputs
    planner = Planner()
    a = planner.add(math.add(1, 2))
    b = planner.add(math.add(3, 4))
    planner.add(math.add(a, b))

    # Generate the plan
    plan = planner.plan()

    # Get the original tree format
    planner.show_tree()

    # Decode the plan
    decoded = Decoder.decode_plan(plan["commands"], plan["state"])

    # Get the decoded tree format
    decoded_tree = decoded.show_tree()

    # Both should show command structure and data dependencies
    assert "Command 0:" in decoded_tree
    assert "Command 1:" in decoded_tree
    assert "Command 2:" in decoded_tree
    assert "Input" in decoded_tree
    assert "Output" in decoded_tree

    # Check for data flow references (Command 2 should use outputs from Commands 0 and 1)
    assert "→ Command 2" in decoded_tree

    # The string representation should now match the tree format
    assert str(decoded) == decoded_tree


def test_planner_reconstruction(math_contract):
    """Test that a plan can be converted back to a Planner object."""
    # Create a test planner using the math_contract fixture
    math = Contract(math_contract, call_type=CallType.DELEGATECALL)

    # Create a planner with operations
    planner = Planner()
    a = planner.add(math.add(1, 2))
    planner.add(math.add(a, 3))

    # Generate the original plan
    original_plan = planner.plan()

    # Decode the plan
    decoded = Decoder.decode_plan(original_plan["commands"], original_plan["state"])

    # Convert back to a planner
    reconstructed_planner = Decoder.to_planner(decoded)

    # Generate plan from reconstructed planner
    reconstructed_plan = reconstructed_planner.plan()

    # Both plans should have the same structure
    assert len(original_plan["commands"]) == len(reconstructed_plan["commands"])
    assert len(original_plan["state"]) == len(reconstructed_plan["state"])

    # State values may not be identical due to ABI encoding differences,
    # but the command structure should be preserved
    assert len(reconstructed_planner.commands) == len(planner.commands)

    # Check that we have the same next_state_index
    assert reconstructed_planner.next_state_index == planner.next_state_index


def test_vault_plan_tree_and_decoder_match():
    """
    Test to ensure both the plan tree output and decoded plan match exactly
    for a vault deposit and redeem example.
    """
    # Create the token and vault contracts
    token = Contract(ape.Contract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))
    vault = Contract(ape.Contract("0xd8063123BBA3B480569244AE66BFE72B6c84b00d"))

    # Set up the user address and amount
    user = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    
    # Create the planner and add operations
    planner = Planner()
    assets = planner.add(token.balanceOf(user))
    shares = planner.add(vault.deposit(assets, user))
    # We need to use positional arguments as the contract doesn't support keyword args
    # The order matters: shares, receiver, owner for the redeem function
    planner.add(vault.redeem(shares, user, user))

    # Generate the plan
    plan = planner.plan()

    # Get the plan tree output
    tree_output = planner.show_tree()

    # Compare with expected output
    assert tree_output == expected_vault_plan_output, "Plan tree output doesn't match expected format."

    # Decode the plan
    decoded_plan = Decoder.decode_plan(plan["commands"], plan["state"])
    decoded_output = str(decoded_plan)

    # Verify the decoded plan output matches the expected output
    assert decoded_output == expected_vault_plan_output, (
        "Decoded plan output doesn't match expected format."
    )

    # Convert back to a Planner object
    reconstructed_planner = Decoder.to_planner(decoded_plan)
    
    # Generate a new plan from the reconstructed planner
    reconstructed_plan = reconstructed_planner.plan()
    
    # Check that the original and reconstructed plans have the same structure
    assert len(plan["commands"]) == len(reconstructed_plan["commands"])
    assert len(plan["state"]) == len(reconstructed_plan["state"])
    
    # Check that the reconstructed planner generates the same tree output
    reconstructed_tree = reconstructed_planner.show_tree()
    assert reconstructed_tree == expected_vault_plan_output, (
        "Reconstructed planner tree output doesn't match expected format."
    )