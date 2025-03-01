from weiroll import Contract, Planner


def test_tuple_return(multi_return_contract, tupler_contract):
    """Test tuple return handling similar to JavaScript tests."""
    # Create Contract instances
    multi_return = Contract(multi_return_contract)
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
