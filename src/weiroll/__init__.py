"""
Weiroll Python SDK - A simple and efficient operation-chaining language for the EVM.

Weiroll is a language for writing programs that take advantage of the EVM's
unique capabilities, allowing for efficient execution of multiple operations
in a single transaction.

Basic usage:
```python
from weiroll import Contract, Planner

# Create contract wrappers
token = Contract(token_contract)
vault = Contract(vault_contract)

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

from .command import Command, CommandArg
from .constants import ArgType, CallType, CommandType
from .contract import Contract, ContractFunction, FunctionCall, StateValue, SubplanValue
from .decoder import DecodedCommand, DecodedPlan, Decoder
from .exceptions import EmptyABIError, InvalidContractError, WeirollError
from .planner import Planner

__all__ = [
    # Enums and constants
    "ArgType",
    "CallType",
    "CommandType",
    # Main classes
    "Command",
    "CommandArg",
    "Contract",
    # Core components
    "ContractFunction",
    "DecodedCommand",
    "DecodedPlan",
    "Decoder",
    "FunctionCall",
    "Planner",
    "StateValue",
    "SubplanValue",
    # Exceptions
    "EmptyABIError",
    "InvalidContractError",
    "WeirollError",
]
