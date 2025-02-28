from typing import Any, Callable, Dict, List, Optional, Union, cast

from eth_abi import encode
from eth_utils import function_signature_to_4byte_selector, to_bytes, to_hex, to_checksum_address, is_address

from .constants import CallType
from .command import Command, CommandArg
from .exceptions import InvalidContractError, EmptyABIError


class ContractFunction:
    """Represents a function on a contract that can be called through Weiroll."""
    
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
        """Create a function call with the given arguments."""
        return FunctionCall(self, list(args))
    
    def withValue(self, value: int) -> 'ContractFunction':
        """Set the ETH value for the call."""
        # Create a copy with value call type
        result = ContractFunction(
            self.contract, self.fn_name, self.fn_sig, CallType.VALUECALL
        )
        result.value = value
        return result


class FunctionCall:
    """Represents a call to a contract function with specific arguments."""
    
    def __init__(self, fn: ContractFunction, args: List[Any]):
        self.fn = fn
        self.args = args
    
    def withValue(self, value: int) -> 'FunctionCall':
        """Set the ETH value for the call."""
        new_fn = self.fn.withValue(value)
        return FunctionCall(new_fn, self.args)
        
    def staticcall(self) -> 'FunctionCall':
        """Convert a CALL to STATICCALL."""
        if self.fn.call_type != CallType.CALL:
            raise ValueError("Only CALL operations can be made static")
            
        # Create a copy with static call type
        result = ContractFunction(
            self.fn.contract, self.fn.fn_name, self.fn.fn_sig, CallType.STATICCALL
        )
        return FunctionCall(result, self.args)
        
    def rawValue(self) -> 'FunctionCall':
        """Capture the entire return value as a bytes object.
        Useful for functions that return multiple values (tuples)."""
        # Create a new function call with is_tuple_return set to True
        new_call = FunctionCall(self.fn, self.args)
        # This would modify the command to set the TUPLE_RETURN flag
        # Implementation is not complete - would need to track this flag
        # through to the Command object
        return new_call
    
    @property
    def selector(self) -> bytes:
        """Get the function selector."""
        return self.fn.selector
    
    @property
    def target(self) -> bytes:
        """Get the target contract address."""
        return to_bytes(hexstr=self.fn.contract.address)
    
    @property
    def call_type(self) -> CallType:
        """Get the call type."""
        return self.fn.call_type


class Contract:
    """Represents a contract that can be called through Weiroll."""
    
    def __init__(self, address: str, abi: Optional[List[Dict[str, Any]]], call_type: CallType = CallType.CALL):
        if not is_address(address):
            raise InvalidContractError(f"Invalid address: {address}")
        
        if not abi:
            raise EmptyABIError("Contract ABI cannot be empty or None")
            
        self.address = to_checksum_address(address)
        self.abi = abi
        self.functions: Dict[str, ContractFunction] = {}
        self.call_type = call_type
        
        self._process_abi()
    
    def _process_abi(self):
        """Process the ABI to extract function signatures."""
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
            except Exception as e:
                # Skip problematic ABI items - let's be tolerant of unusual formats
                continue
    
    def __getattr__(self, name: str) -> Any:
        """Allow accessing functions as attributes."""
        if name in self.functions:
            return self.functions[name]
        
        raise AttributeError(f"Contract has no function '{name}'")
    
    @staticmethod
    def createContract(contract_obj: Any, call_type: CallType = CallType.CALL) -> 'Contract':
        """Create a Contract from a web3.py or ape contract object.
        By default, uses CALL call type for regular contracts.
        
        Supports:
        - web3.py contracts (contract_obj.address, contract_obj.abi)
        - ape contracts (contract_obj.address, contract_obj.contract_type.abi)
        
        Raises:
            InvalidContractError: If the contract object is invalid or unsupported
            EmptyABIError: If the contract ABI is empty or None
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
                except Exception as e:
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
    def createLibrary(contract_obj: Any) -> 'Contract':
        """Create a Contract from a web3.py or ape contract object.
        Uses DELEGATECALL call type for library contracts.
        
        Supports:
        - web3.py contracts (contract_obj.address, contract_obj.abi)
        - ape contracts (contract_obj.address, contract_obj.contract_type.abi)
        
        Raises:
            InvalidContractError: If the contract object is invalid or unsupported
            EmptyABIError: If the contract ABI is empty or None
        """
        return Contract.createContract(contract_obj, CallType.DELEGATECALL)


class StateValue:
    """Represents a value in the Weiroll VM state."""
    
    def __init__(self, index: int, is_dynamic: bool = False):
        self.index = index
        self.is_dynamic = is_dynamic
    
    def to_arg(self) -> CommandArg:
        """Convert to a CommandArg."""
        return CommandArg(index=self.index, is_dynamic=self.is_dynamic)