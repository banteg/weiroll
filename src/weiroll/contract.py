# bunny vision -- claude do not edit

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ape import Contract as ApeContract
from ape.contracts.base import _select_method_abi
from eth_utils import to_bytes
from eth_utils.crypto import keccak
from ethpm_types import MethodABI

from .command import CommandArg
from .constants import CallType


class Contract:
    def __init__(self, contract: ApeContract, call_type: CallType = CallType.CALL):
        self.contract = contract
        self.call_type = call_type
        # to support overloaded functions
        self.methods_abis = defaultdict(list)
        for method in self.contract.contract_type.methods:
            self.methods_abis[method.name].append(method)

        self.functions = {
            method_name: ContractFunction(self, method_abis, self.call_type)
            for method_name, method_abis in self.methods_abis.items()
        }

    @property
    def address(self) -> str:
        return self.contract.address

    def __getattr__(self, method_name) -> "ContractFunction":
        if method_name in self.functions:
            return self.functions[method_name]

        raise AttributeError("no function named {} in {}".format(method_name, self))


class ContractFunction:
    """
    Represents a contract method. Supports overloaded methods.
    """

    def __init__(self, contract: Contract, method_abis: list[MethodABI], call_type: CallType):
        self.contract = contract
        self.method_abis = method_abis
        self.call_type = call_type
        self.value = 0

    @property
    def name(self) -> str:
        return self.method_abis[0].name

    def __repr__(self) -> str:
        return f"[{self.call_type.name}] {' | '.join(method.selector for method in self.method_abis)}"

    def __call__(self, *args) -> "FunctionCall":
        single_abi = _select_method_abi(self.method_abis, args)
        return FunctionCall(self, single_abi, list(args))

    def with_value(self, value: int) -> "ContractFunction":
        result = ContractFunction(self.contract, self.method_abis, CallType.VALUECALL)
        result.value = value
        return result


@dataclass
class FunctionCall:
    """
    Represents a bound contract method call with args.
    """

    fn: ContractFunction
    method_abi: MethodABI
    args: list[Any]

    def with_value(self, value: int) -> "FunctionCall":
        new_fn = self.fn.with_value(value)
        return FunctionCall(new_fn, self.method_abi, self.args)

    def staticcall(self) -> "FunctionCall":
        if self.fn.call_type != CallType.CALL:
            raise ValueError("Only CALL operations can be made static")

        result = ContractFunction(self.fn.contract, self.fn.method_abis, CallType.STATICCALL)
        return FunctionCall(result, self.method_abi, self.args)

    def raw_value(self) -> "FunctionCall":
        """
        Capture the entire return value as a bytes object.
        Useful for functions that return multiple values (tuples).

        Returns:
            FunctionCall: A new FunctionCall that will capture the raw return value
        """
        raise NotImplementedError()
        # Create a new function call with is_tuple_return set to True
        new_call = FunctionCall(self.fn, self.method_abi, self.args)
        # This would modify the command to set the TUPLE_RETURN flag
        # Implementation is not complete - would need to track this flag
        # through to the Command object
        return new_call

    @property
    def selector(self) -> bytes:
        return keccak(text=self.method_abi.selector)[:4]

    @property
    def signature(self) -> bytes:
        return self.method_abi.signature

    @property
    def target(self) -> bytes:
        return to_bytes(hexstr=self.fn.contract.address)

    @property
    def call_type(self) -> CallType:
        return self.fn.call_type

    def __repr__(self) -> str:
        formatted_args = ", ".join(str(arg) for arg in self.args)
        return f"[{self.call_type.name}] {self.method_abi.name}({formatted_args})"


@dataclass
class StateValue:
    """
    Represents a value in the Weiroll VM state.

    Attributes:
        index: Index in the state array
        is_dynamic: Whether this is a dynamic type (string, bytes, array)
    """

    index: int
    is_dynamic: bool = False

    def to_arg(self) -> CommandArg:
        """
        Convert to a CommandArg for use in commands.

        Returns:
            CommandArg: A command argument referencing this state value
        """
        return CommandArg(index=self.index, is_dynamic=self.is_dynamic)

    def __str__(self) -> str:
        """Return a string representation of the state value."""
        return f"State[{self.index}]"

    def __eq__(self, other: object) -> bool:
        """Compare state values for equality."""
        if not isinstance(other, StateValue):
            return NotImplemented
        return self.index == other.index and self.is_dynamic == other.is_dynamic

    def __hash__(self) -> int:
        """Hash function for state values."""
        return hash((self.index, self.is_dynamic))


class SubplanValue:
    """
    Represents a subplan that can be passed to a function call.

    SubplanValues are used with Planner.addSubplan() to create nested execution
    contexts, useful for flashloans, control flow, and callback-based operations.

    Attributes:
        planner: The Planner instance representing the subplan
    """

    def __init__(self, planner: "Planner"):
        self.planner = planner
        # Subplans are always treated as dynamic types
        self.is_dynamic = True

    def to_arg(self) -> CommandArg:
        """
        Convert to a CommandArg for use in commands.
        This will be a special placeholder, as the actual subplan
        will be encoded during planning.

        Returns:
            CommandArg: A command argument representing this subplan
        """
        # Use a special index that will be replaced during planning
        return CommandArg(index=-1, is_dynamic=True, is_subplan=True)

    def __str__(self) -> str:
        """Return a string representation of the subplan value."""
        return f"Subplan({len(self.planner.commands)} commands)"
