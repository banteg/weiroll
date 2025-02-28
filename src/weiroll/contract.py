from typing import Any, Dict, List, Optional, Union, TypeVar, cast
from collections.abc import Callable
from dataclasses import dataclass

from eth_abi import encode
from eth_utils import function_signature_to_4byte_selector, to_bytes, to_hex, to_checksum_address, is_address
from web3 import Web3
from ape import Contract as ApeContract

from .constants import CallType
from .command import Command, CommandArg
from .exceptions import InvalidContractError, EmptyABIError

T = TypeVar('T', bound='ContractFunction')


class ContractFunction:
    """
    Represents a function on a contract that can be called through Weiroll.
    
    Attributes:
        contract: The contract this function belongs to
        fn_name: Name of the function
        fn_sig: Function signature string (e.g. "transfer(address,uint256)")
        call_type: The type of call to make (CALL, DELEGATECALL, etc.)
        selector: 4-byte function selector derived from the signature
        value: ETH value to send with the call (only for VALUECALL)
    """
    
    def __init__(
        self, 
        contract: 'Contract', 
        fn_name: str, 
        fn_sig: str,
        call_type: CallType = CallType.DELEGATECALL
    ):
        self.contract = contract
        self.fn_name = fn_name
        self.fn_sig = fn_sig
        self.call_type = call_type
        self.selector = function_signature_to_4byte_selector(fn_sig)
        self.value = 0
    
    def __call__(self, *args) -> 'FunctionCall':
        """
        Create a function call with the given arguments.
        
        Args:
            *args: Arguments to pass to the function
            
        Returns:
            FunctionCall: A callable function with the specified arguments
        """
        return FunctionCall(self, list(args))
    
    def with_value(self, value: int) -> 'ContractFunction':
        """
        Set the ETH value for the call.
        
        Args:
            value: Amount of ETH in wei to send with the call
            
        Returns:
            ContractFunction: A new ContractFunction with VALUECALL type
        """
        # Create a copy with value call type
        result = ContractFunction(
            self.contract, self.fn_name, self.fn_sig, CallType.VALUECALL
        )
        result.value = value
        return result
        
    def __repr__(self) -> str:
        """Return a string representation of the function."""
        return f"ContractFunction(name='{self.fn_name}', sig='{self.fn_sig}', call_type={self.call_type.name})"


@dataclass
class FunctionCall:
    """
    Represents a call to a contract function with specific arguments.
    
    Attributes:
        fn: The ContractFunction being called
        args: Arguments to pass to the function
    """
    
    fn: ContractFunction
    args: list[Any]
    
    def with_value(self, value: int) -> 'FunctionCall':
        """
        Set the ETH value for the call.
        
        Args:
            value: Amount of ETH in wei to send with the call
            
        Returns:
            FunctionCall: A new FunctionCall with the specified value
        """
        new_fn = self.fn.with_value(value)
        return FunctionCall(new_fn, self.args)
        
    def staticcall(self) -> 'FunctionCall':
        """
        Convert a CALL to STATICCALL.
        
        Returns:
            FunctionCall: A new FunctionCall with STATICCALL type
            
        Raises:
            ValueError: If the call type is not CALL
        """
        if self.fn.call_type != CallType.CALL:
            raise ValueError("Only CALL operations can be made static")
            
        # Create a copy with static call type
        result = ContractFunction(
            self.fn.contract, self.fn.fn_name, self.fn.fn_sig, CallType.STATICCALL
        )
        return FunctionCall(result, self.args)
        
    def raw_value(self) -> 'FunctionCall':
        """
        Capture the entire return value as a bytes object.
        Useful for functions that return multiple values (tuples).
        
        Returns:
            FunctionCall: A new FunctionCall that will capture the raw return value
        """
        # Create a new function call with is_tuple_return set to True
        new_call = FunctionCall(self.fn, self.args)
        # This would modify the command to set the TUPLE_RETURN flag
        # Implementation is not complete - would need to track this flag
        # through to the Command object
        return new_call
    
    @property
    def selector(self) -> bytes:
        """
        Get the function selector (4-byte signature).
        
        Returns:
            bytes: The 4-byte function selector
        """
        return self.fn.selector
    
    @property
    def target(self) -> bytes:
        """
        Get the target contract address in bytes format.
        
        Returns:
            bytes: The contract address as bytes
        """
        return to_bytes(hexstr=self.fn.contract.address)
    
    @property
    def call_type(self) -> CallType:
        """
        Get the call type.
        
        Returns:
            CallType: The type of call (CALL, DELEGATECALL, etc.)
        """
        return self.fn.call_type
        
    def __repr__(self) -> str:
        """Return a string representation of the function call."""
        arg_str = ', '.join(str(arg) for arg in self.args)
        return f"FunctionCall({self.fn.fn_name}({arg_str}), call_type={self.call_type.name})"


class Contract:
    """
    Represents a contract that can be called through Weiroll.
    
    Attributes:
        address: The contract's Ethereum address
        abi: The contract's ABI
        functions: Dictionary of available functions by name
        call_type: The default call type for this contract
    """
    
    def __init__(
        self, 
        address: str, 
        abi: list[dict[str, Any]] | None, 
        call_type: CallType = CallType.CALL
    ):
        if not is_address(address):
            raise InvalidContractError(f"Invalid address: {address}")
        
        if not abi:
            raise EmptyABIError("Contract ABI cannot be empty or None")
            
        self.address = to_checksum_address(address)
        self.abi = abi
        self.functions: dict[str, ContractFunction] = {}
        self.call_type = call_type
        
        self._process_abi()
    
    def _process_abi(self) -> None:
        """
        Process the ABI to extract function signatures.
        
        Raises:
            EmptyABIError: If the contract ABI is empty
        """
        if not self.abi:
            raise EmptyABIError("Contract ABI cannot be empty")
            
        for item in self.abi:
            try:
                # For dictionary-style ABI entries (both web3.py and model_dump() results)
                if isinstance(item, dict):
                    # Skip non-function items
                    if item.get('type') != 'function':
                        continue
                    
                    fn_name = item.get('name', '')
                    inputs = item.get('inputs', [])
                    
                    # Process input types
                    input_types = []
                    for inp in inputs:
                        if isinstance(inp, dict) and 'type' in inp:
                            input_types.append(inp['type'])
                        else:
                            input_types.append('')
                    
                    # Create the function signature and add to functions dict
                    signature = f"{fn_name}({','.join(input_types)})"
                    self.functions[fn_name] = ContractFunction(self, fn_name, signature, self.call_type)
            except (KeyError, TypeError) as e:
                # Skip problematic ABI items but log specific errors
                # In a real implementation, you might want to use a logger here
                # logger.warning(f"Skipping ABI item due to {type(e).__name__}: {e}")
                continue
            except Exception as e:
                # Skip other unknown errors
                # logger.error(f"Unexpected error processing ABI item: {e}")
                continue
    
    def __getattr__(self, name: str) -> ContractFunction:
        """
        Allow accessing functions as attributes (e.g., contract.transfer).
        
        Args:
            name: The function name to look up
            
        Returns:
            ContractFunction: The contract function
            
        Raises:
            AttributeError: If the function doesn't exist
        """
        if name in self.functions:
            return self.functions[name]
        
        raise AttributeError(f"Contract has no function '{name}'")
        
    def __repr__(self) -> str:
        """Return a string representation of the contract."""
        function_count = len(self.functions)
        return f"Contract(address='{self.address}', functions={function_count}, call_type={self.call_type.name})"
    
    @staticmethod
    def create_contract(contract_obj: Any, call_type: CallType = CallType.CALL) -> 'Contract':
        """
        Create a Contract from a web3.py or ape contract object.
        By default, uses CALL call type for regular contracts.
        
        Args:
            contract_obj: A web3.py or ape contract object
            call_type: The call type to use for this contract
            
        Returns:
            Contract: A Weiroll Contract wrapper
            
        Raises:
            InvalidContractError: If the contract object is invalid or unsupported
            EmptyABIError: If the contract ABI is empty or None
            
        Examples:
            ```python
            # From web3.py
            from web3 import Web3
            from weiroll import Contract
            
            w3 = Web3(Web3.HTTPProvider('...'))
            token = w3.eth.contract(address='0x...', abi=TOKEN_ABI)
            weiroll_token = Contract.create_contract(token)
            
            # From ape
            from ape import Contract as ApeContract
            from weiroll import Contract
            
            token = ApeContract('0x...')
            weiroll_token = Contract.create_contract(token)
            ```
        """
        if not hasattr(contract_obj, 'address'):
            raise InvalidContractError("Contract object must have an address attribute")
            
        # Handle web3.py contracts
        if hasattr(contract_obj, 'abi'):
            if contract_obj.abi is not None:
                if not contract_obj.abi:  # Empty list
                    raise EmptyABIError("Contract ABI cannot be empty")
                return Contract(contract_obj.address, contract_obj.abi, call_type)
        # Missing abi property or it's None - attempt ape style
        
        # Handle ape contracts
        if hasattr(contract_obj, 'contract_type'):
            # Prioritize model_dump() pattern first since it handles ethpm_types correctly
            if hasattr(contract_obj.contract_type, 'model_dump'):
                try:
                    # Get ABI from model_dump
                    model_data = contract_obj.contract_type.model_dump()
                    if isinstance(model_data, dict) and 'abi' in model_data and model_data['abi'] is not None:
                        if not model_data['abi']:  # Empty list
                            raise EmptyABIError("Contract ABI cannot be empty")
                        return Contract(contract_obj.address, model_data['abi'], call_type)
                except Exception:
                    # Error calling model_dump - don't raise yet, try the direct abi attribute
                    pass
                    
            # Fallback to direct abi property if model_dump failed
            if hasattr(contract_obj.contract_type, 'abi'):
                if contract_obj.contract_type.abi is not None:
                    if not contract_obj.contract_type.abi:  # Empty list
                        raise EmptyABIError("Contract ABI cannot be empty")
                    return Contract(contract_obj.address, contract_obj.contract_type.abi, call_type)
            
            # If we got here, neither method worked
            raise InvalidContractError("Could not get valid ABI from contract_type")
        
        raise InvalidContractError("Unsupported contract object type. Must be a web3.py or ape contract.")
    
    @staticmethod
    def create_library(contract_obj: Any) -> 'Contract':
        """
        Create a Contract from a web3.py or ape contract object.
        Uses DELEGATECALL call type for library contracts.
        
        Args:
            contract_obj: A web3.py or ape contract object
            
        Returns:
            Contract: A Weiroll Contract wrapper with DELEGATECALL call type
            
        Raises:
            InvalidContractError: If the contract object is invalid or unsupported
            EmptyABIError: If the contract ABI is empty or None
        """
        return Contract.create_contract(contract_obj, CallType.DELEGATECALL)


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