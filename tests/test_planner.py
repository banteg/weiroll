import pytest
import json
from eth_utils import function_signature_to_4byte_selector, to_bytes, to_hex

from weiroll.constants import CallType
from weiroll.contract import Contract, ContractFunction, FunctionCall, StateValue
from weiroll.planner import Planner


class MockContract:
    def __init__(self, address, abi):
        self.address = address
        self.abi = abi


def test_planner_basic():
    # Create a simplified contract with a basic function
    address = "0x1234567890123456789012345678901234567890"
    abi = [
        {
            "type": "function",
            "name": "add",
            "inputs": [
                {"type": "uint256"},
                {"type": "uint256"}
            ],
            "outputs": [
                {"type": "uint256"}
            ]
        }
    ]
    
    # Create a Contract instance
    mock_contract = MockContract(address, abi)
    contract = Contract.createContract(mock_contract)
    
    # Create a Planner
    planner = Planner()
    
    # Add a function call to the plan
    result = planner.add(contract.add(5, 10))
    
    # Verify the state values
    assert len(planner.state) == 2  # Two inputs: 5 and 10
    assert planner.state[0] == 5
    assert planner.state[1] == 10
    
    # Verify the command
    assert len(planner.commands) == 1
    cmd = planner.commands[0]
    assert cmd.function_selector == function_signature_to_4byte_selector("add(uint256,uint256)")
    assert cmd.target == to_bytes(hexstr=address)
    assert len(cmd.inputs) == 2
    assert cmd.inputs[0].index == 0
    assert cmd.inputs[1].index == 1
    assert cmd.output.index == 2
    
    # Verify the result StateValue
    assert isinstance(result, StateValue)
    assert result.index == 2
    
    # Generate the plan
    plan = planner.plan()
    
    # Verify the encoded plan
    assert len(plan["commands"]) == 1
    assert len(plan["state"]) == 3  # 2 inputs + 1 output
    assert plan["state"][0].startswith("0x")  # Encoded uint256
    assert plan["state"][1].startswith("0x")  # Encoded uint256
    assert plan["state"][2] == "0x"  # Empty placeholder for output


def test_planner_chained_operations():
    # Create a simplified contract with multiple functions
    address = "0x1234567890123456789012345678901234567890"
    abi = [
        {
            "type": "function",
            "name": "add",
            "inputs": [
                {"type": "uint256"},
                {"type": "uint256"}
            ],
            "outputs": [
                {"type": "uint256"}
            ]
        },
        {
            "type": "function",
            "name": "multiply",
            "inputs": [
                {"type": "uint256"},
                {"type": "uint256"}
            ],
            "outputs": [
                {"type": "uint256"}
            ]
        }
    ]
    
    # Create a Contract instance
    mock_contract = MockContract(address, abi)
    contract = Contract.createContract(mock_contract)
    
    # Create a Planner
    planner = Planner()
    
    # Chain operations: (5 + 10) * 2
    sum_result = planner.add(contract.add(5, 10))
    final_result = planner.add(contract.multiply(sum_result, 2))
    
    # Verify the state
    assert len(planner.state) == 3  # Three inputs: 5, 10, and 2
    
    # Verify the commands
    assert len(planner.commands) == 2
    
    # Verify the plan
    plan = planner.plan()
    assert len(plan["commands"]) == 2
    assert len(plan["state"]) == 5  # 3 inputs + 2 outputs


def test_planner_with_value_call():
    # Create a simplified contract with a payable function
    address = "0x1234567890123456789012345678901234567890"
    abi = [
        {
            "type": "function",
            "name": "deposit",
            "inputs": [],
            "outputs": [],
            "stateMutability": "payable"
        }
    ]
    
    # Create a Contract instance
    mock_contract = MockContract(address, abi)
    contract = Contract.createContract(mock_contract)
    
    # Get the deposit function and set it to use CALL
    deposit_fn = contract.deposit
    
    # Create a Planner
    planner = Planner()
    
    # Add a value call
    planner.add(deposit_fn().withValue(1000000000000000000))  # 1 ETH
    
    # Verify the command
    assert len(planner.commands) == 1
    cmd = planner.commands[0]
    assert cmd.call_type == CallType.VALUECALL
    assert len(cmd.inputs) == 1  # Value is added as first input
    
    # Generate the plan
    plan = planner.plan()
    
    # Verify the encoded plan
    assert len(plan["commands"]) == 1
    assert len(plan["state"]) >= 2  # At least value + output