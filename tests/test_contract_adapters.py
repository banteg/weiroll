import pytest
from ethpm_types import MethodABI

from weiroll import CallType, Contract
from weiroll.exceptions import EmptyABIError, InvalidContractError


def test_ape_contract_adapter(math_contract):
    """Test that ape contracts can be properly wrapped."""
    # Use the math_contract fixture which has 'add' function
    # Create Weiroll contract
    weiroll_contract = Contract(math_contract)

    # Verify contract properties
    assert weiroll_contract.address == "0x1234567890123456789012345678901234567890"
    assert "add" in weiroll_contract.functions
    assert weiroll_contract.call_type == CallType.CALL

    # Create a library contract
    library_contract = Contract(math_contract, call_type=CallType.DELEGATECALL)
    assert library_contract.call_type == CallType.DELEGATECALL
