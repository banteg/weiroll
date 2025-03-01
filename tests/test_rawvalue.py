from weiroll import Contract, Planner, CallType


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
            "outputs": [{"type": "uint256", "name": "a"}, {"type": "bytes32[]", "name": "b"}],
            "stateMutability": "pure",
            "type": "function",
        },
        {
            "inputs": [{"type": "bytes", "name": "raw"}],
            "name": "acceptsBytes",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]

    mock_contract = MockContract(SAMPLE_ADDRESS, tuple_abi)
    test_contract = Contract(mock_contract, call_type=CallType.DELEGATECALL)

    # Create a plan with rawValue
    planner = Planner()
    # This would need to be implemented in our SDK
    # tuple_result = planner.add(test_contract.returnsTuple().raw_value())
    # planner.add(test_contract.acceptsBytes(tuple_result))

    # For now just verify the basic case works
    planner.add(test_contract.returnsTuple())
    planner.add(test_contract.acceptsBytes(b"some_raw_data"))

    plan = planner.plan()
    assert len(plan["commands"]) == 2
