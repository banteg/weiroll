from weiroll import Contract, Planner


def test_array_in_planner(array_test_contract):
    """Test to investigate array handling in the Planner"""
    # Create contract instance
    contract = Contract(array_test_contract)

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
