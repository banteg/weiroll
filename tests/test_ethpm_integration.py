import pytest
from ethpm_types import ContractType
from weiroll import Contract, Planner, CallType
from weiroll.exceptions import InvalidContractError, EmptyABIError


# Skip test if ape is not installed
try:
    from ape import Contract as ApeContract
    APE_AVAILABLE = True
except ImportError:
    APE_AVAILABLE = False

pytestmark = pytest.mark.skipif(not APE_AVAILABLE, reason="ape is not installed")


def test_ethpm_contract_adapter(ape_dai):
    """Test integration with ethpm_types ContractType."""
    # Get contract model data from the Ape contract
    contract_type = ContractType.model_validate({"abi": ape_dai.contract_type.abi})
    
    # Get the ABI data directly
    model_data = contract_type.model_dump()
    abi_list = model_data['abi']
    
    # Create Weiroll contract directly with the ABI data
    weiroll_contract = Contract(str(ape_dai.address), abi_list)
    
    # Verify contract was properly created
    assert weiroll_contract.address.lower() == str(ape_dai.address).lower()
    assert len(weiroll_contract.functions) > 0
    assert "transfer" in weiroll_contract.functions
    assert "balanceOf" in weiroll_contract.functions
    assert "approve" in weiroll_contract.functions
    assert weiroll_contract.call_type == CallType.CALL
    
    # Test a simple plan with the contract
    planner = Planner()
    recipient = "0x0987654321098765432109876543210987654321"
    amount = 100 * 10**18  # 100 DAI
    
    # Add a transfer operation
    planner.add(weiroll_contract.transfer(recipient, amount))
    
    # Generate the plan
    plan = planner.plan()
    
    # Check that plan contains expected command
    assert len(plan["commands"]) == 1
    # transfer(address,uint256) selector is 0xa9059cbb
    assert "0xa9059cbb" in plan["commands"][0]
    
    # Test creating a library contract
    library_contract = Contract(str(ape_dai.address), abi_list, CallType.DELEGATECALL)
    assert library_contract.call_type == CallType.DELEGATECALL