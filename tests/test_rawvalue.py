from weiroll import CallType, Contract, Planner
from weiroll.command import Command
from weiroll.constants import TUP_BIT

import pytest


def test_raw_value_method(multi_return_contract):
    """Test that the raw_value method properly sets the is_tuple_return flag."""
    # Create a contract object from the fixture
    test_contract = Contract(multi_return_contract)
    
    # Create a standard function call
    fn_call = test_contract.intTuple()
    assert not hasattr(fn_call, 'is_tuple_return') or not fn_call.is_tuple_return
    
    # Create a raw value function call
    raw_fn_call = test_contract.intTuple().raw_value()
    assert raw_fn_call.is_tuple_return is True
    
    # Ensure they have different is_tuple_return values but same other properties
    assert fn_call.selector == raw_fn_call.selector
    assert fn_call.target == raw_fn_call.target
    assert fn_call.call_type == raw_fn_call.call_type


def test_planner_with_raw_value(math_contract):
    """Test that the planner correctly processes raw_value calls."""
    # Create a contract and planner
    test_contract = Contract(math_contract)
    planner = Planner()
    
    # Add a normal call
    result = planner.add(test_contract.add(5, 10))
    
    # Add a raw_value call - this won't actually be used as raw bytes,
    # but we're just testing the flag gets set
    raw_result = planner.add(test_contract.add(7, 13).raw_value())
    
    # Check that the commands were created properly
    assert len(planner.commands) == 2
    assert not planner.commands[0].is_tuple_return  # Normal call
    assert planner.commands[1].is_tuple_return      # Raw value call
    
    # Generate the plan
    plan = planner.plan()
    assert len(plan["commands"]) == 2


def test_raw_value_execution(multi_return_contract):
    """Test that the raw_value method works for functions returning multiple values."""
    test_contract = Contract(multi_return_contract)
    planner = Planner()
    
    # Regular tuple unpacking - should return the first value (0xbad)
    first_element = planner.add(test_contract.intTuple())
    
    # With raw_value, we should capture all return values as a single bytes value
    all_elements = planner.add(test_contract.intTuple().raw_value())
    
    # Verify commands were created correctly
    assert len(planner.commands) == 2
    
    # Check the is_tuple_return flag is set correctly
    assert not planner.commands[0].is_tuple_return  # Regular call only captures first element
    assert planner.commands[1].is_tuple_return      # Raw value call captures all elements
    
    # Plan should be encodable without errors
    plan = planner.plan()
    assert len(plan["commands"]) == 2
    
    # Generate command for inspection
    command_bytes = planner.commands[1].encode()
    
    # Ensure the command is properly encoded as bytes
    assert isinstance(command_bytes, bytes)
    assert len(command_bytes) >= 32
