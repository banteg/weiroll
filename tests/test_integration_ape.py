import pytest
from weiroll import Contract, Planner, CallType

# We'll use ape's pytest plugin for testing
try:
    from ape import Contract as ApeContract, accounts, project
    from ape.api.address import Address
    APE_AVAILABLE = True
except ImportError:
    APE_AVAILABLE = False

# Skip tests if ape is not installed
pytestmark = pytest.mark.skipif(not APE_AVAILABLE, reason="ape is not installed")

# Simple ERC20 ABI for testing
ERC20_ABI = [
    {
        "type": "function",
        "name": "balanceOf",
        "inputs": [{"type": "address", "name": "account"}],
        "outputs": [{"type": "uint256", "name": "balance"}],
        "stateMutability": "view"
    },
    {
        "type": "function",
        "name": "transfer",
        "inputs": [
            {"type": "address", "name": "to"},
            {"type": "uint256", "name": "amount"}
        ],
        "outputs": [{"type": "bool", "name": "success"}],
        "stateMutability": "nonpayable"
    }
]


@pytest.fixture
def token_abi():
    """Return ERC20 token ABI."""
    return ERC20_ABI


def test_contract_adapter_mock():
    """Test creating a Weiroll contract from a mock object."""
    # Create a mock contract with address and abi attributes
    class MockContract:
        def __init__(self):
            self.address = "0x1234567890123456789012345678901234567890"
            self.abi = ERC20_ABI
            
            # For ape style test
            class ContractType:
                def __init__(self):
                    self.abi = ERC20_ABI
                    
            self.contract_type = ContractType()
    
    # Create the mock object
    mock_contract = MockContract()
    
    # Test web3.py style
    weiroll_contract = Contract.createContract(mock_contract)
    assert weiroll_contract.address.lower() == mock_contract.address.lower()
    assert weiroll_contract.call_type == CallType.CALL
    assert "balanceOf" in weiroll_contract.functions
    assert "transfer" in weiroll_contract.functions
    
    # Test ape style with contract_type attribute
    new_mock = MockContract()  # Create a new instance
    new_mock.abi = None  # Remove abi to force using contract_type path
    weiroll_contract_ape = Contract.createContract(new_mock)
    assert weiroll_contract_ape.address.lower() == new_mock.address.lower()
    assert weiroll_contract_ape.call_type == CallType.CALL
    assert "balanceOf" in weiroll_contract_ape.functions
    assert "transfer" in weiroll_contract_ape.functions
    
    # Test library flag
    library_contract = Contract.createLibrary(mock_contract)
    assert library_contract.call_type == CallType.DELEGATECALL


def test_planner_integration_with_mock():
    """Test integrating with the planner using a mock contract."""
    # Create a mock contract
    class MockContract:
        def __init__(self):
            self.address = "0x1234567890123456789012345678901234567890"
            self.abi = ERC20_ABI
            
            class ContractType:
                def __init__(self):
                    self.abi = ERC20_ABI
                    
            self.contract_type = ContractType()
    
    # Setup contracts
    token = MockContract()
    recipient_address = "0x0987654321098765432109876543210987654321"
    
    # Wrap with Weiroll
    weiroll_token = Contract.createContract(token)
    
    # Create a plan
    planner = Planner()
    
    # Add operations to the plan
    amount = 1000 * 10**18  # 1000 tokens
    planner.add(weiroll_token.transfer(recipient_address, amount))
    
    # Generate the plan
    plan = planner.plan()
    
    # Verify plan structure
    assert len(plan["commands"]) == 1
    assert len(plan["state"]) >= 2  # Should have at least recipient address and amount
    
    # Check function encoding (should contain transfer selector)
    # transfer(address,uint256) selector is 0xa9059cbb
    command_hex = plan["commands"][0]
    assert command_hex.startswith("0xa9059cbb"), f"Expected transfer selector in {command_hex}"