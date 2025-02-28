from weiroll import Contract, Planner


class MockContract:
    def __init__(self, address, abi):
        self.address = address
        self.abi = abi


def test_array_in_planner():
    """Test to investigate array handling in the Planner"""
    # Create a contract with a function that accepts an array
    address = "0x1234567890123456789012345678901234567890"
    abi = [
        {
            "type": "function",
            "name": "swapExactTokensForTokens",
            "inputs": [
                {"name": "amountIn", "type": "uint256"},
                {"name": "amountOutMin", "type": "uint256"},
                {"name": "path", "type": "address[]"},  # Array of addresses
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"},
            ],
            "outputs": [{"name": "amounts", "type": "uint256[]"}],
            "stateMutability": "nonpayable",
        }
    ]

    # Create contract instance
    mock_contract = MockContract(address, abi)
    contract = Contract.create_contract(mock_contract)

    # Create planner
    planner = Planner()

    # Test values
    amount_in = 1000 * 10**18
    amount_min = 0
    path = ["0x6B175474E89094C44Da98b954EedeAC495271d0F", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"]
    to_address = "0x0987654321098765432109876543210987654321"
    deadline = 1000000000

    # Debug print the path array
    print(f"Path array: {path}")
    print(f"Path array type: {type(path)}")
    print(f"Path array elements types: {[type(x) for x in path]}")

    # Add the function call to the planner
    planner.add(contract.swapExactTokensForTokens(amount_in, amount_min, path, to_address, deadline))

    # Try to get the plan - this is where we expect the error
    try:
        plan = planner.plan()
        print("Plan successful!")
        print(f"Commands: {len(plan['commands'])}")
        print(f"State: {len(plan['state'])}")
    except ValueError as e:
        print(f"Error: {e}")

        # Debug: print state values
        for i, val in enumerate(planner.state):
            print(f"State[{i}]: {val} (type: {type(val)})")


if __name__ == "__main__":
    test_array_in_planner()
