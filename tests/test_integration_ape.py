import pytest

# We'll use ape's pytest plugin for testing
from ape import Contract as ApeContract

from weiroll import CallType, Contract, Planner

# Skip tests if ape is not installed
pytestmark = pytest.mark.skipif(not hasattr(ApeContract, "__module__"), reason="ape is not installed")

# Simple ERC20 ABI for testing
ERC20_ABI = [
    {
        "type": "function",
        "name": "balanceOf",
        "inputs": [{"type": "address", "name": "account"}],
        "outputs": [{"type": "uint256", "name": "balance"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "transfer",
        "inputs": [{"type": "address", "name": "to"}, {"type": "uint256", "name": "amount"}],
        "outputs": [{"type": "bool", "name": "success"}],
        "stateMutability": "nonpayable",
    },
]


@pytest.fixture
def token_abi():
    """Return ERC20 token ABI."""
    return ERC20_ABI


def test_contract_adapter_mock(ape_dai):
    """Test creating a Weiroll contract from a mock object."""
    # Use the ape_dai fixture which is a real Ape Contract

    # Create a Weiroll contract from the Ape contract
    weiroll_contract = Contract(ape_dai)
    assert weiroll_contract.address.lower() == ape_dai.address.lower()
    assert weiroll_contract.call_type == CallType.CALL
    assert "balanceOf" in weiroll_contract.functions
    assert "transfer" in weiroll_contract.functions

    # Test library flag (DELEGATECALL)
    library_contract = Contract(ape_dai, call_type=CallType.DELEGATECALL)
    assert library_contract.call_type == CallType.DELEGATECALL


def test_planner_integration_with_mock(ape_dai, recipient):
    """Test integrating with the planner using a real Ape contract."""
    # Use the ape_dai fixture for the token
    # Use the recipient fixture for the recipient address

    # Wrap with Weiroll
    weiroll_token = Contract(ape_dai)

    # Create a plan
    planner = Planner()

    # Add operations to the plan
    amount = 1000 * 10**18  # 1000 tokens
    planner.add(weiroll_token.transfer(recipient.address, amount))

    # Generate the plan
    plan = planner.plan()

    # Verify plan structure
    assert len(plan["commands"]) == 1
    assert len(plan["state"]) >= 2  # Should have at least recipient address and amount

    # Check function encoding (should contain transfer selector)
    # transfer(address,uint256) selector is 0xa9059cbb
    command_hex = plan["commands"][0]
    assert command_hex.startswith("0xa9059cbb"), f"Expected transfer selector in {command_hex}"
