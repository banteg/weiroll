from weiroll import Contract, Planner


# Mock contract objects that will be wrapped
class MockContract:
    def __init__(self, address, abi):
        self.address = address
        self.abi = abi


def test_simple_addition():
    """Test a simple addition program similar to JavaScript tests."""
    # Create mock contract with Math library
    math_addr = "0x1234567890123456789012345678901234567890"
    math_abi = [
        {
            "type": "function",
            "name": "add",
            "inputs": [{"type": "uint256"}, {"type": "uint256"}],
            "outputs": [{"type": "uint256"}],
        }
    ]

    events_addr = "0x2345678901234567890123456789012345678901"
    events_abi = [{"type": "function", "name": "logUint", "inputs": [{"type": "uint256"}], "outputs": []}]

    # Create Contract instances
    math_contract = MockContract(math_addr, math_abi)
    math = Contract.create_contract(math_contract)

    events_contract = MockContract(events_addr, events_abi)
    events = Contract.create_contract(events_contract)

    # Create a Planner
    planner = Planner()

    # Calculate Fibonacci sequence: 1, 1, 2, 3, 5, 8, 13, 21, 34, 55
    a = 1
    b = 1

    # Create function calls
    for _i in range(8):
        ret_val = planner.add(math.add(a, b))
        a = b
        b = ret_val

    # Add a call to log the final result
    planner.add(events.logUint(b))

    # Generate the plan
    plan = planner.plan()

    # Verify plan structure
    assert len(plan["commands"]) == 9  # 8 additions + 1 log
    assert len(plan["state"]) > 0

    # The final b value should be 55


def test_string_operations():
    """Test string operations similar to JavaScript tests."""
    # Create mock contract with Strings library
    strings_addr = "0x1234567890123456789012345678901234567890"
    strings_abi = [
        {
            "type": "function",
            "name": "strcat",
            "inputs": [{"type": "string"}, {"type": "string"}],
            "outputs": [{"type": "string"}],
        },
        {"type": "function", "name": "strlen", "inputs": [{"type": "string"}], "outputs": [{"type": "uint256"}]},
    ]

    events_addr = "0x2345678901234567890123456789012345678901"
    events_abi = [
        {"type": "function", "name": "logString", "inputs": [{"type": "string"}], "outputs": []},
        {"type": "function", "name": "logUint", "inputs": [{"type": "uint256"}], "outputs": []},
    ]

    # Create Contract instances
    strings_contract = MockContract(strings_addr, strings_abi)
    strings = Contract.create_contract(strings_contract)

    events_contract = MockContract(events_addr, events_abi)
    events = Contract.create_contract(events_contract)

    # Create a Planner for concatenation
    concat_planner = Planner()
    test_string = "Hello, world!"

    # Concatenate strings
    result = concat_planner.add(strings.strcat(test_string, test_string))
    concat_planner.add(events.logString(result))

    # Generate the concatenation plan
    concat_plan = concat_planner.plan()

    # Create a Planner for string length
    strlen_planner = Planner()

    # Get string length
    length = strlen_planner.add(strings.strlen(test_string))
    strlen_planner.add(events.logUint(length))

    # Generate the length plan
    strlen_plan = strlen_planner.plan()

    # Verify plans
    assert len(concat_plan["commands"]) == 2
    assert len(strlen_plan["commands"]) == 2


def test_value_call():
    """Test payable function calls with value."""
    payable_addr = "0x3456789012345678901234567890123456789012"
    payable_abi = [
        {"type": "function", "name": "pay", "inputs": [], "outputs": [], "stateMutability": "payable"},
        {"type": "function", "name": "balance", "inputs": [], "outputs": [{"type": "uint256"}]},
    ]

    events_addr = "0x2345678901234567890123456789012345678901"
    events_abi = [{"type": "function", "name": "logUint", "inputs": [{"type": "uint256"}], "outputs": []}]

    # Create Contract instances
    payable_contract = MockContract(payable_addr, payable_abi)
    payable = Contract.create_contract(payable_contract)

    events_contract = MockContract(events_addr, events_abi)
    events = Contract.create_contract(events_contract)

    # Create a Planner
    planner = Planner()

    # Add a value call (1 ETH = 10^18 wei)
    amount = 1_000_000_000_000_000_000
    planner.add(payable.pay().with_value(amount))

    # Check balance
    balance = planner.add(payable.balance())
    planner.add(events.logUint(balance))

    # Generate the plan
    plan = planner.plan()

    # Verify the plan contains the correct commands
    assert len(plan["commands"]) == 3

    # Check that value is encoded correctly
    first_command_inputs = [arg.index for arg in planner.commands[0].inputs]
    assert len(first_command_inputs) == 1  # The value
    assert planner.state[first_command_inputs[0]] == amount
