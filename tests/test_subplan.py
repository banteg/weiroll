import pytest

from ape import Contract as ApeContract
from eth_abi import encode
from weiroll import Contract, Planner, SubplanValue
from weiroll.constants import CommandType


def test_subplan_basic(simple_contract, executor_contract):
    """Test basic subplan functionality"""
    # Create contract wrappers
    contract = Contract(simple_contract)
    executor = Contract(executor_contract, call_type=1)  # CALL
    
    # Create a subplan
    subplan = Planner()
    result = subplan.add(contract.add(5, 10))
    
    # Create a main planner
    planner = Planner()
    
    # Add the subplan to the main planner
    planner.addSubplan(executor.execute(SubplanValue(subplan), planner.state_value))
    
    # Verify the command
    assert len(planner.commands) == 1
    cmd = planner.commands[0]
    assert cmd.command_type == CommandType.SUBPLAN
    assert hasattr(cmd, "subplan")
    assert cmd.subplan is subplan
    
    # Verify input args
    assert len(cmd.inputs) == 2
    # First arg should be a subplan
    assert cmd.inputs[0].is_subplan
    # Second arg should be state
    assert cmd.inputs[1].is_state
    
    # Generate the plan
    plan = planner.plan()
    
    # The plan should have encoded the subplan as part of the state
    assert len(plan["commands"]) == 1
    # At minimum, we expect the commands to be encoded
    assert len(plan["state"]) >= 1


def test_subplan_return_values(simple_contract, executor_contract):
    """Test that return values from subplans are accessible in the parent plan"""
    # Create contract wrappers
    contract = Contract(simple_contract)
    executor = Contract(executor_contract, call_type=1)  # CALL
    
    # Create a subplan that adds 5 + 10
    subplan = Planner()
    result = subplan.add(contract.add(5, 10))
    
    # Create a main planner
    planner = Planner()
    
    # Add the subplan to the main planner
    planner.addSubplan(executor.execute(SubplanValue(subplan), planner.state_value))
    
    # Use the result from the subplan in a subsequent call
    planner.add(contract.multiply(result, 2))
    
    # Verify we have two commands
    assert len(planner.commands) == 2
    
    # Verify the first command is a subplan
    assert planner.commands[0].command_type == CommandType.SUBPLAN
    
    # Verify the second command uses the result as input
    multiply_cmd = planner.commands[1]
    assert multiply_cmd.command_type == CommandType.CALL
    assert len(multiply_cmd.inputs) == 2
    assert multiply_cmd.inputs[0].index == result.index
    
    # Generate the plan
    plan = planner.plan()
    
    # The plan should have commands for both operations
    assert len(plan["commands"]) == 2


def test_subplan_chaining(simple_contract, executor_contract):
    """Test chaining multiple subplans"""
    # Create contract wrappers
    contract = Contract(simple_contract)
    executor = Contract(executor_contract, call_type=1)  # CALL
    
    # Create first subplan that adds 5 + 10
    subplan1 = Planner()
    result1 = subplan1.add(contract.add(5, 10))
    
    # Create second subplan that multiplies the result by 2
    subplan2 = Planner()
    result2 = subplan2.add(contract.multiply(result1, 2))
    
    # Create a main planner
    planner = Planner()
    
    # Add both subplans to the main planner
    planner.addSubplan(executor.execute(SubplanValue(subplan1), planner.state_value))
    planner.addSubplan(executor.execute(SubplanValue(subplan2), planner.state_value))
    
    # Verify we have two commands
    assert len(planner.commands) == 2
    
    # Verify both commands are subplans
    assert planner.commands[0].command_type == CommandType.SUBPLAN
    assert planner.commands[1].command_type == CommandType.SUBPLAN
    
    # Generate the plan
    plan = planner.plan()
    
    # The plan should have commands for both subplans
    assert len(plan["commands"]) == 2


def test_replace_state(simple_contract, executor_contract):
    """Test the replaceState functionality"""
    # Create contract wrappers
    contract = Contract(simple_contract)
    executor = Contract(executor_contract, call_type=1)  # CALL
    
    # Create a planner
    planner = Planner()
    
    # Add a command
    sum_result = planner.add(contract.add(5, 10))
    
    # Replace the state
    planner.replaceState(executor.processState(planner.state_value))
    
    # Verify we have two commands
    assert len(planner.commands) == 2
    
    # Verify the second command is a RAWCALL
    assert planner.commands[1].command_type == CommandType.RAWCALL
    
    # Generate the plan
    plan = planner.plan()
    
    # The plan should have commands for both operations
    assert len(plan["commands"]) == 2


def test_validation_errors():
    """Test validation errors for subplans and replaceState"""
    # Create a planner
    planner = Planner()
    subplan = Planner()
    
    # Test errors that should be raised
    with pytest.raises(ValueError, match="SubplanValue arguments can only be used with addSubplan"):
        # Cannot use SubplanValue with regular add
        planner.add(DummyFunctionCall(args=[SubplanValue(subplan)]))
    
    with pytest.raises(ValueError, match="Subplans must take planner and state arguments"):
        # Missing state argument
        planner.addSubplan(DummyFunctionCall(args=[SubplanValue(subplan)]))
    
    with pytest.raises(ValueError, match="Subplans must take planner and state arguments"):
        # Missing subplan argument
        planner.addSubplan(DummyFunctionCall(args=[planner.state_value]))
    
    with pytest.raises(ValueError, match="Subplans can only take one planner argument"):
        # Multiple subplan arguments
        planner.addSubplan(
            DummyFunctionCall(args=[SubplanValue(subplan), SubplanValue(subplan), planner.state_value])
        )
    
    with pytest.raises(ValueError, match="Subplans can only take one state argument"):
        # Multiple state arguments
        planner.addSubplan(
            DummyFunctionCall(args=[SubplanValue(subplan), planner.state_value, planner.state_value])
        )
    
    with pytest.raises(ValueError, match="Function replacing state must return a value"):
        # replaceState with no return value
        planner.replaceState(DummyFunctionCall(args=[planner.state_value], has_output=False))
    
    with pytest.raises(ValueError, match="SubplanValue cannot be used with replaceState"):
        # Cannot use SubplanValue with replaceState
        planner.replaceState(DummyFunctionCall(args=[SubplanValue(subplan)]))


def test_circular_reference():
    """Test that circular references in subplans are detected"""
    # Create planners
    planner1 = Planner()
    
    # Create self-reference which is a simple case of circular reference
    planner1.addSubplan(DummyFunctionCall(args=[SubplanValue(planner1), planner1.state_value]))
    
    # Verify circular reference is detected
    with pytest.raises(ValueError, match="A planner cannot contain itself"):
        planner1.plan()


def test_tree_view(simple_contract, executor_contract):
    """Test that the tree view properly shows subplans"""
    # Create contract wrappers
    contract = Contract(simple_contract)
    executor = Contract(executor_contract, call_type=1)  # CALL
    
    # Create a subplan
    subplan = Planner()
    result = subplan.add(contract.add(5, 10))
    
    # Create a main planner
    planner = Planner()
    
    # Add the subplan to the main planner
    planner.addSubplan(executor.execute(SubplanValue(subplan), planner.state_value))
    
    # Render the tree view
    tree = planner.show_tree()
    
    # The tree should include the command type SUBPLAN
    assert "SUBPLAN" in tree


# Helper class for testing with dummy function calls
class DummyFunctionCall:
    def __init__(self, args=None, has_output=True):
        self.args = args or []
        self.selector = b"\x00\x00\x00\x00"
        self.target = b"\x00" * 20
        self.call_type = 1  # CALL
        
        # Create a dummy method ABI
        class DummyMethodABI:
            def __init__(self, has_output=True):
                self.outputs = [DummyABIOutput()] if has_output else []
        
        class DummyABIOutput:
            def __init__(self):
                self.canonical_type = "bytes[]"
        
        self.method_abi = DummyMethodABI(has_output)