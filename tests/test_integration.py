from weiroll import Contract, Planner


def test_simple_addition(math_contract, events_contract):
    """Test a simple addition program similar to JavaScript tests."""
    # Create Contract instances
    math = Contract(math_contract)
    events = Contract(events_contract)

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


def test_string_operations(strings_contract, events_contract):
    """Test string operations similar to JavaScript tests."""
    # Create Contract instances
    strings = Contract(strings_contract)
    events = Contract(events_contract)

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


def test_value_call(payable_contract, events_contract):
    """Test payable function calls with value."""
    # Create Contract instances
    payable = Contract(payable_contract)
    events = Contract(events_contract)

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
