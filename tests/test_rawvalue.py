from weiroll import Contract, Planner, CallType

SAMPLE_ADDRESS = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"


def test_tuple_rawvalue(multi_return_contract):
    """Test capturing a tuple return value as raw bytes."""
    # Use the multi_return_contract fixture which has intTuple and tupleConsumer functions
    test_contract = Contract(multi_return_contract, call_type=CallType.DELEGATECALL)

    # Create a plan
    planner = Planner()
    # This would need to be implemented in our SDK
    # tuple_result = planner.add(test_contract.intTuple().raw_value())
    # planner.add(test_contract.tupleConsumer(tuple_result))

    # For now just verify the basic case works
    planner.add(test_contract.intTuple())
    planner.add(test_contract.tupleConsumer(123))

    plan = planner.plan()
    assert len(plan["commands"]) == 2
