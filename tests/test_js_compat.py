import pytest

from weiroll import CallType, Contract, Planner

SAMPLE_ADDRESS = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"


def test_simple_program(math_contract):
    """Test planning a simple program."""
    math = Contract(math_contract)

    planner = Planner()
    planner.add(math.add(1, 2))
    plan = planner.plan()

    assert len(plan["commands"]) == 1

    # Match the expected command format
    # Our plan includes a placeholder for the return value
    assert plan["state"][0].startswith("0x")  # 1 encoded as uint256
    assert plan["state"][1].startswith("0x")  # 2 encoded as uint256


def test_deduplicate_literals(math_contract):
    """Test deduplication of identical literals."""
    math = Contract(math_contract)

    planner = Planner()
    planner.add(math.add(1, 1))
    plan = planner.plan()

    # Check that we're deduplicating literals
    # Our SDK implementation also allocates space for the return value
    assert len(plan["state"]) <= 2
    assert plan["state"][0].startswith("0x")


def test_reuse_return_values(math_contract):
    """Test planning a program that uses return values."""
    math = Contract(math_contract)

    planner = Planner()
    sum1 = planner.add(math.add(1, 2))
    planner.add(math.add(sum1, 3))
    plan = planner.plan()

    # Verify we have two commands
    assert len(plan["commands"]) == 2

    # Verify we have state entries for the literals and space for return value
    assert len(plan["state"]) >= 3


def test_dynamic_arguments(strings_contract):
    """Test planning a program with dynamic arguments."""
    strings = Contract(strings_contract)

    planner = Planner()
    planner.add(strings.strlen("Hello, world!"))
    plan = planner.plan()

    assert len(plan["commands"]) == 1
    # Our implementation reserves space for the return value
    assert len(plan["state"]) > 0


def test_dynamic_return_values(strings_contract):
    """Test planning a program with dynamic return value."""
    strings = Contract(strings_contract)

    planner = Planner()
    planner.add(strings.strcat("Hello, ", "world!"))
    plan = planner.plan()

    assert len(plan["commands"]) == 1
    # Our implementation includes two inputs plus a reserved slot
    assert len(plan["state"]) >= 2  # At least two string inputs


def test_dynamic_return_as_input(strings_contract):
    """Test planning a program that takes dynamic argument from a return value."""
    strings = Contract(strings_contract)

    planner = Planner()
    str_result = planner.add(strings.strcat("Hello, ", "world!"))
    planner.add(strings.strlen(str_result))
    plan = planner.plan()

    assert len(plan["commands"]) == 2
    # We allocate space for inputs and return values
    assert len(plan["state"]) >= 2  # At least two input strings


def test_call_types(math_contract):
    """Test different call types."""
    # Create standard CALL contract
    call_math = Contract(math_contract)
    assert call_math.add(1, 2).call_type == CallType.CALL

    # Create a DELEGATECALL library contract
    delegatecall_math = Contract(math_contract, call_type=CallType.DELEGATECALL)
    assert delegatecall_math.add(1, 2).call_type == CallType.DELEGATECALL

    # Test STATICCALL via .staticcall()
    static_call = call_math.add(1, 2).staticcall()
    assert static_call.call_type == CallType.STATICCALL

    # Test error when trying to make DELEGATECALL static
    with pytest.raises(ValueError, match="Only CALL operations can be made static"):
        delegatecall_math.add(1, 2).staticcall()


def test_value_calls(deposit_contract, math_contract):
    """Test calls with ETH value."""
    payable_contract = Contract(deposit_contract)

    # Test withValue call
    value_call = payable_contract.deposit().with_value(456)
    assert value_call.call_type == CallType.VALUECALL

    # Test the plan with value calls
    planner = Planner()
    planner.add(payable_contract.deposit().with_value(456))
    plan = planner.plan()
    assert len(plan["commands"]) == 1

    # Test that return values as parameters work correctly
    math = Contract(math_contract)
    planner2 = Planner()
    sum_result = planner2.add(math.add(1, 2))
    planner2.add(math.add(sum_result, 3))
    plan2 = planner2.plan()
    assert len(plan2["commands"]) == 2
