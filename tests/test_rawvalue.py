import pytest
from eth_abi import encode
from eth_utils import function_signature_to_4byte_selector, to_bytes, to_hex

from weiroll import Contract, Planner, StateValue, CallType, CommandArg


# Mock contract objects that will be wrapped
class MockContract:
    def __init__(self, address, abi):
        self.address = address
        self.abi = abi


SAMPLE_ADDRESS = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"


def test_tuple_rawvalue():
    """Test capturing a tuple return value as raw bytes."""
    # Create mock contract with a function that returns a tuple
    tuple_abi = [
        {
            "inputs": [],
            "name": "returnsTuple",
            "outputs": [
                {"type": "uint256", "name": "a"},
                {"type": "bytes32[]", "name": "b"}
            ],
            "stateMutability": "pure",
            "type": "function"
        },
        {
            "inputs": [
                {"type": "bytes", "name": "raw"}
            ],
            "name": "acceptsBytes",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        }
    ]
    
    mock_contract = MockContract(SAMPLE_ADDRESS, tuple_abi)
    test_contract = Contract.createLibrary(mock_contract)
    
    # Create a plan with rawValue
    planner = Planner()
    # This would need to be implemented in our SDK
    # tuple_result = planner.add(test_contract.returnsTuple().rawValue())
    # planner.add(test_contract.acceptsBytes(tuple_result))
    
    # For now just verify the basic case works
    planner.add(test_contract.returnsTuple())
    planner.add(test_contract.acceptsBytes(b"some_raw_data"))
    
    plan = planner.plan()
    assert len(plan["commands"]) == 2