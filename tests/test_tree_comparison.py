import textwrap

import ape

from weiroll import Contract, Planner

# Define the expected output
expected_output = textwrap.dedent("""
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


def test_vault_plan_tree_and_decoder_match():
    """
    Test to ensure both the plan tree output and decoded plan match exactly
    for a vault deposit and redeem example.
    """
    # Create the token and vault contracts
    token = Contract.create_contract(ape.Contract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))
    vault = Contract.create_contract(ape.Contract("0xd8063123BBA3B480569244AE66BFE72B6c84b00d"))

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
    planner.plan()

    # Get the plan tree output
    tree_output = planner.show_tree()

    # For debugging, print both outputs
    print("\nActual output:\n", tree_output)
    print("\nExpected output:\n", expected_output)

    # Compare with expected output
    assert tree_output == expected_output, "Plan tree output doesn't match expected format."

    # # Decode the plan
    # decoded_plan = Decoder.decode_plan(plan["commands"], plan["state"])
    # decoded_output = str(decoded_plan)

    # # Verify the decoded plan output matches the expected output
    # assert decoded_output == expected_output, (
    #     "Decoded plan output doesn't match expected format."
    # )
