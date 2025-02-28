import pytest
from eth_utils import function_signature_to_4byte_selector, to_bytes

from weiroll.command import Command, CommandArg
from weiroll.constants import CallType


def test_command_arg_encoding():
    # Test fixed-length argument
    fixed_arg = CommandArg(index=5)
    assert fixed_arg.encode() == bytes([5])
    
    # Test variable-length argument
    var_arg = CommandArg(index=10, is_dynamic=True)
    assert var_arg.encode() == bytes([0x80 | 10])
    
    # Test decoding
    decoded_fixed = CommandArg.from_byte(5)
    assert decoded_fixed.index == 5
    assert not decoded_fixed.is_dynamic
    
    decoded_var = CommandArg.from_byte(0x8A)
    assert decoded_var.index == 10
    assert decoded_var.is_dynamic


def test_command_encoding():
    # Create a command for a function like: function add(uint256 a, uint256 b) returns (uint256)
    selector = function_signature_to_4byte_selector("add(uint256,uint256)")
    target = to_bytes(hexstr="0x1234567890123456789012345678901234567890")
    
    # Input arguments at state indices 0 and 1
    inputs = [CommandArg(index=0), CommandArg(index=1)]
    
    # Output at state index 2
    output = CommandArg(index=2)
    
    cmd = Command(
        function_selector=selector,
        target=target,
        inputs=inputs,
        output=output,
        call_type=CallType.DELEGATECALL
    )
    
    encoded = cmd.encode()
    assert len(encoded) == 32  # Must be 32 bytes
    
    # Decode and verify
    decoded = Command.decode(encoded)
    assert decoded.function_selector == selector
    assert decoded.target == target
    assert len(decoded.inputs) == 2
    assert decoded.inputs[0].index == 0
    assert decoded.inputs[1].index == 1
    assert decoded.output.index == 2
    assert decoded.call_type == CallType.DELEGATECALL
    assert not decoded.is_tuple_return
    assert not decoded.extended_inputs


def test_command_with_calltype():
    # Test different call types
    selector = function_signature_to_4byte_selector("transfer(address,uint256)")
    target = to_bytes(hexstr="0x1234567890123456789012345678901234567890")
    inputs = [CommandArg(index=0), CommandArg(index=1)]
    output = CommandArg(index=2)
    
    # Test CALL
    call_cmd = Command(
        function_selector=selector,
        target=target,
        inputs=inputs,
        output=output,
        call_type=CallType.CALL
    )
    
    encoded_call = call_cmd.encode()
    decoded_call = Command.decode(encoded_call)
    assert decoded_call.call_type == CallType.CALL
    
    # Test STATICCALL
    static_cmd = Command(
        function_selector=selector,
        target=target,
        inputs=inputs,
        output=output,
        call_type=CallType.STATICCALL
    )
    
    encoded_static = static_cmd.encode()
    decoded_static = Command.decode(encoded_static)
    assert decoded_static.call_type == CallType.STATICCALL
    
    # Test VALUECALL
    value_cmd = Command(
        function_selector=selector,
        target=target,
        inputs=inputs,
        output=output,
        call_type=CallType.VALUECALL
    )
    
    encoded_value = value_cmd.encode()
    decoded_value = Command.decode(encoded_value)
    assert decoded_value.call_type == CallType.VALUECALL