from typing import Any, Callable, Dict, List, Optional, Union, cast

from eth_abi import encode
from eth_utils import function_signature_to_4byte_selector, to_bytes, to_hex, to_checksum_address, is_address

from .constants import CallType
from .command import Command, CommandArg


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
        if self.call_type != CallType.CALL:
            raise ValueError("Cannot send value with non-CALL type functions")
        
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
    
    def __init__(self, address: str, abi: List[Dict[str, Any]]):
        if not is_address(address):
            raise ValueError(f"Invalid address: {address}")
        
        self.address = to_checksum_address(address)
        self.abi = abi
        self.functions: Dict[str, ContractFunction] = {}
        
        self._process_abi()
    
    def _process_abi(self):
        """Process the ABI to extract function signatures."""
        for item in self.abi:
            if item.get('type') != 'function':
                continue
            
            fn_name = item.get('name', '')
            inputs = item.get('inputs', [])
            input_types = [inp.get('type', '') for inp in inputs]
            signature = f"{fn_name}({','.join(input_types)})"
            
            self.functions[fn_name] = ContractFunction(self, fn_name, signature)
    
    def __getattr__(self, name: str) -> Any:
        """Allow accessing functions as attributes."""
        if name in self.functions:
            return self.functions[name]
        
        raise AttributeError(f"Contract has no function '{name}'")
    
    @staticmethod
    def createContract(contract_obj: Any) -> 'Contract':
        """Create a Contract from an ethers.js or web3.py contract object."""
        # This is a simplified version - actual implementation would need
        # to handle different contract library formats
        if hasattr(contract_obj, 'address') and hasattr(contract_obj, 'abi'):
            return Contract(contract_obj.address, contract_obj.abi)
        
        raise ValueError("Unsupported contract object type")


class StateValue:
    """Represents a value in the Weiroll VM state."""
    
    def __init__(self, index: int, is_dynamic: bool = False):
        self.index = index
        self.is_dynamic = is_dynamic
    
    def to_arg(self) -> CommandArg:
        """Convert to a CommandArg."""
        return CommandArg(index=self.index, is_dynamic=self.is_dynamic)