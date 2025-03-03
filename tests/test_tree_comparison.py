
import ape

from weiroll import Contract, Decoder, Planner


def test_vault_plan_tree_and_decoder_match():
    """
    Test to ensure both the plan tree output and decoded plan match correctly.

    This test creates a simple vault deposit/redeem flow and verifies that
    the decoder is enhancing both the planner and tree visualization as expected.
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

    # Get the plan tree output from planner
    tree_output = planner.show_tree()

    # Make sure it's not empty - this verifies the tree renderer works
    assert "Command 0:" in tree_output
    assert "balanceOf" in tree_output
    assert "deposit" in tree_output
    assert "redeem" in tree_output

    # Decode the plan
    decoded_plan = Decoder.decode_plan(plan["commands"], plan["state"])

    # Verify the decoded plan has the is_decoded flag set
    assert hasattr(decoded_plan, "is_decoded")
    assert decoded_plan.is_decoded is True

    # Verify commands have function_info
    for cmd in decoded_plan.commands:
        assert hasattr(cmd, "function_info")
        assert cmd.function_info is not None

    # Check that the decoded plan has proper function info
    # Each command should have function_info with proper signature matching what we see in the tree output
    assert "balanceOf" in decoded_plan.commands[0].function_info.get("signature")
    assert "deposit" in decoded_plan.commands[1].function_info.get("signature")
    assert "redeem" in decoded_plan.commands[2].function_info.get("signature")
