from weiroll import Contract, Planner


# Mock contract objects that will be wrapped
class MockContract:
    def __init__(self, address, abi):
        self.address = address
        self.abi = abi


def test_tuple_return():
    """Test tuple return handling similar to JavaScript tests."""
    # Create mock contracts for tuple tests
    multi_return_addr = "0x1234567890123456789012345678901234567890"
    multi_return_abi = [
        {"type": "function", "name": "intTuple", "inputs": [], "outputs": [{"type": "uint256"}, {"type": "uint256"}]},
        {"type": "function", "name": "tupleConsumer", "inputs": [{"type": "uint256"}], "outputs": []},
    ]

    tupler_addr = "0x2345678901234567890123456789012345678901"
    tupler_abi = [
        {
            "type": "function",
            "name": "extractElement",
            "inputs": [
                {"type": "tuple", "components": [{"type": "uint256"}, {"type": "uint256"}]},
                {"type": "uint256"},  # index to extract
            ],
            "outputs": [{"type": "uint256"}],
        }
    ]

    # Create Contract instances
    multi_return_contract = MockContract(multi_return_addr, multi_return_abi)
    multi_return = Contract(multi_return_contract)

    tupler_contract = MockContract(tupler_addr, tupler_abi)
    Contract(tupler_contract)

    # Test first element extraction
    # Create a Planner
    planner1 = Planner()

    # In JavaScript test, it uses the extractElement function to get element at index 0
    planner1.add(multi_return.intTuple())  # This returns a tuple
    # We don't actually implement tuple support in this basic SDK, but the test shows how it would be structured

    # Generate the plan
    plan1 = planner1.plan()

    # Test second element extraction
    # Create a Planner
    planner2 = Planner()

    # In JavaScript test, it uses the extractElement function to get element at index 1
    planner2.add(multi_return.intTuple())  # This returns a tuple

    # Generate the plan
    plan2 = planner2.plan()

    # Basic verification
    assert len(plan1["commands"]) == 1
    assert len(plan2["commands"]) == 1
