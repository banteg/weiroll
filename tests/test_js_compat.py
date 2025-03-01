import pytest

from weiroll import CallType, Contract, Planner


# Mock contract objects that will be wrapped
class MockContract:
    def __init__(self, address, abi):
        self.address = address
        self.abi = abi


SAMPLE_ADDRESS = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"


def get_math_contract():
    # Create mock contract with Math library
    math_abi = [
        {
            "inputs": [
                {"internalType": "uint256", "name": "a", "type": "uint256"},
                {"internalType": "uint256", "name": "b", "type": "uint256"},
            ],
            "name": "add",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "pure",
            "type": "function",
        }
    ]

    math_contract = MockContract(SAMPLE_ADDRESS, math_abi)
    return Contract(math_contract)


def get_strings_contract():
    # Create mock contract with Strings library
    strings_abi = [
        {
            "inputs": [
                {"internalType": "string", "name": "a", "type": "string"},
                {"internalType": "string", "name": "b", "type": "string"},
            ],
            "name": "strcat",
            "outputs": [{"internalType": "string", "name": "", "type": "string"}],
            "stateMutability": "pure",
            "type": "function",
        },
        {
            "inputs": [{"internalType": "string", "name": "x", "type": "string"}],
            "name": "strlen",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "pure",
            "type": "function",
        },
    ]

    strings_contract = MockContract(SAMPLE_ADDRESS, strings_abi)
    return Contract(strings_contract)


def test_simple_program():
    """Test planning a simple program."""
    math = get_math_contract()

    planner = Planner()
    planner.add(math.add(1, 2))
    plan = planner.plan()

    assert len(plan["commands"]) == 1

    # Match the expected command format
    # Our plan includes a placeholder for the return value
    assert plan["state"][0].startswith("0x")  # 1 encoded as uint256
    assert plan["state"][1].startswith("0x")  # 2 encoded as uint256


def test_deduplicate_literals():
    """Test deduplication of identical literals."""
    math = get_math_contract()

    planner = Planner()
    planner.add(math.add(1, 1))
    plan = planner.plan()

    # Check that we're deduplicating literals
    # Our SDK implementation also allocates space for the return value
    assert len(plan["state"]) <= 2
    assert plan["state"][0].startswith("0x")


def test_reuse_return_values():
    """Test planning a program that uses return values."""
    math = get_math_contract()

    planner = Planner()
    sum1 = planner.add(math.add(1, 2))
    planner.add(math.add(sum1, 3))
    plan = planner.plan()

    # Verify we have two commands
    assert len(plan["commands"]) == 2

    # Verify we have state entries for the literals and space for return value
    assert len(plan["state"]) >= 3


def test_dynamic_arguments():
    """Test planning a program with dynamic arguments."""
    strings = get_strings_contract()

    planner = Planner()
    planner.add(strings.strlen("Hello, world!"))
    plan = planner.plan()

    assert len(plan["commands"]) == 1
    # Our implementation reserves space for the return value
    assert len(plan["state"]) > 0


def test_dynamic_return_values():
    """Test planning a program with dynamic return value."""
    strings = get_strings_contract()

    planner = Planner()
    planner.add(strings.strcat("Hello, ", "world!"))
    plan = planner.plan()

    assert len(plan["commands"]) == 1
    # Our implementation includes two inputs plus a reserved slot
    assert len(plan["state"]) >= 2  # At least two string inputs


def test_dynamic_return_as_input():
    """Test planning a program that takes dynamic argument from a return value."""
    strings = get_strings_contract()

    planner = Planner()
    str_result = planner.add(strings.strcat("Hello, ", "world!"))
    planner.add(strings.strlen(str_result))
    plan = planner.plan()

    assert len(plan["commands"]) == 2
    # We allocate space for inputs and return values
    assert len(plan["state"]) >= 2  # At least two input strings


def test_call_types():
    """Test different call types."""
    # Create standard CALL contract
    call_math = get_math_contract()
    assert call_math.add(1, 2).call_type == CallType.CALL

    # Create a DELEGATECALL library contract
    delegatecall_abi = [
        {
            "inputs": [{"type": "uint256"}, {"type": "uint256"}],
            "name": "add",
            "outputs": [{"type": "uint256"}],
            "stateMutability": "pure",
            "type": "function",
        }
    ]

    mock_library = MockContract(SAMPLE_ADDRESS, delegatecall_abi)
    delegatecall_math = Contract(mock_library, call_type=CallType.DELEGATECALL)
    assert delegatecall_math.add(1, 2).call_type == CallType.DELEGATECALL

    # Test STATICCALL via .staticcall()
    static_call = call_math.add(1, 2).staticcall()
    assert static_call.call_type == CallType.STATICCALL

    # Test error when trying to make DELEGATECALL static
    with pytest.raises(ValueError, match="Only CALL operations can be made static"):
        delegatecall_math.add(1, 2).staticcall()


def test_value_calls():
    """Test calls with ETH value."""
    # Create a payable function contract
    payable_abi = [
        {
            "inputs": [{"type": "uint256"}],
            "name": "deposit",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function",
        }
    ]

    mock_contract = MockContract(SAMPLE_ADDRESS, payable_abi)
    payable_contract = Contract(mock_contract)

    # Test withValue call
    value_call = payable_contract.deposit(123).with_value(456)
    assert value_call.call_type == CallType.VALUECALL

    # Test the plan with value calls
    planner = Planner()
    planner.add(payable_contract.deposit(123).with_value(456))
    plan = planner.plan()
    assert len(plan["commands"]) == 1

    # Test that return values as parameters work correctly
    math = get_math_contract()
    planner2 = Planner()
    sum_result = planner2.add(math.add(1, 2))
    planner2.add(math.add(sum_result, 3))
    plan2 = planner2.plan()
    assert len(plan2["commands"]) == 2
