import pytest
from ape import networks, Contract as ApeContract
from weiroll import Contract, Planner, Decoder


def test_planner_repr_html():
    """Test that Planner objects support HTML representation."""
    planner = Planner()
    
    # Simple empty planner should have HTML representation
    html_repr = planner._repr_html_()
    assert html_repr is not None
    assert "<div class='weiroll-plan'>" in html_repr
    assert "Empty plan" in html_repr


def test_planner_with_commands_repr_html():
    """Test that Planner objects with commands have proper HTML representation."""
    with networks.parse_network_choice('ethereum:mainnet:http://127.0.0.1:8545'):
        # Create a basic plan with a token transfer
        planner = Planner()
        
        # Use a well-known token contract (DAI)
        dai_address = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
        dai = Contract(ApeContract(dai_address))
        
        # Add a simple transfer
        recipient = "0x0000000000000000000000000000000000000123"
        amount = 1000 * 10**18
        planner.add(dai.transfer(recipient, amount))
        
        # Check HTML representation 
        html_repr = planner._repr_html_()
        assert html_repr is not None
        assert "<div class='weiroll-plan'>" in html_repr
        assert "transfer" in html_repr
        assert recipient in html_repr
        
        # Ensure style elements are present
        assert "<style>" in html_repr
        assert ".weiroll-plan" in html_repr
        
        # Check tree structure elements
        assert "tree-branch" in html_repr
        assert "command-header" in html_repr


def test_decoded_planner_repr_html():
    """Test that decoded planners also support HTML representation."""
    with networks.parse_network_choice('ethereum:mainnet:http://127.0.0.1:8545'):
        # Create a basic plan with a token transfer
        planner = Planner()
        
        # Use a well-known token contract (DAI)
        dai_address = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
        dai = Contract(ApeContract(dai_address))
        
        # Add a simple transfer
        recipient = "0x0000000000000000000000000000000000000123"
        amount = 1000 * 10**18
        planner.add(dai.transfer(recipient, amount))
        
        # Generate and decode the plan
        plan = planner.plan()
        decoded_planner = Decoder.decode_plan(plan["commands"], plan["state"])
        
        # Check HTML representation
        html_repr = decoded_planner._repr_html_()
        assert html_repr is not None
        assert "<div class='weiroll-plan'>" in html_repr
        assert "transfer" in html_repr
        assert recipient in html_repr


if __name__ == "__main__":
    # This allows running the test directly for debugging
    with networks.parse_network_choice('ethereum:mainnet:http://127.0.0.1:8545'):
        test_planner_repr_html()
        test_planner_with_commands_repr_html()
        test_decoded_planner_repr_html()
        print("All tests passed!")