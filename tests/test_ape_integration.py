import pytest
from ape import Contract as ApeContract

from weiroll import CallType, Contract, Planner

pytestmark = pytest.mark.skipif(not hasattr(ApeContract, "__module__"), reason="ape is not installed")


def test_ape_contract_adapter(ape_dai, recipient):
    """Test integration with Ape contracts."""
    # Create a Weiroll contract from the Ape contract
    weiroll_contract = Contract.create_contract(ape_dai)

    # Verify contract was properly created
    assert weiroll_contract.address.lower() == str(ape_dai.address).lower()
    assert len(weiroll_contract.functions) > 0
    assert "transfer" in weiroll_contract.functions
    assert "balanceOf" in weiroll_contract.functions
    assert "approve" in weiroll_contract.functions
    assert weiroll_contract.call_type == CallType.CALL

    # Test a simple plan with the contract
    planner = Planner()
    amount = 100 * 10**18  # 100 DAI

    # Add a transfer operation
    planner.add(weiroll_contract.transfer(str(recipient.address), amount))

    # Generate the plan
    plan = planner.plan()

    # Check that plan contains expected command
    assert len(plan["commands"]) == 1
    # transfer(address,uint256) selector is 0xa9059cbb
    assert "0xa9059cbb" in plan["commands"][0]

    # Test creating a library contract
    library_contract = Contract.create_library(ape_dai)
    assert library_contract.call_type == CallType.DELEGATECALL
