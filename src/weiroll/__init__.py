"""
Weiroll Python SDK - A simple and efficient operation-chaining language for the EVM.

Weiroll is a language for writing programs that take advantage of the EVM's
unique capabilities, allowing for efficient execution of multiple operations
in a single transaction.

Basic usage:
```python
from weiroll import Contract, Planner

# Create contract wrappers
token = Contract.create_contract(token_contract)
vault = Contract.create_contract(vault_contract)

# Build a plan
with Planner() as planner:
    # Approve tokens
    planner.add(token.approve(vault.address, amount))
    
    # Deposit into vault
    planner.add(vault.deposit(amount))
    
    # Generate the plan for execution
    plan = planner.plan()
```
"""

from .constants import CallType, ArgType
from .command import Command, CommandArg
from .contract import Contract, ContractFunction, FunctionCall, StateValue
from .planner import Planner
from .decoder import Decoder, DecodedCommand, DecodedPlan
from .exceptions import WeirollError, InvalidContractError, EmptyABIError

__all__ = [
    # Main classes
    "Contract",
    "Planner",
    "Decoder",
    
    # Core components
    "ContractFunction",
    "FunctionCall",
    "StateValue",
    "Command",
    "CommandArg",
    "DecodedCommand",
    "DecodedPlan",
    
    # Enums and constants
    "CallType",
    "ArgType",
    
    # Exceptions
    "WeirollError",
    "InvalidContractError",
    "EmptyABIError",
]