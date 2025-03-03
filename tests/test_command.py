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
        function_selector=selector, target=target, inputs=inputs, output=output, call_type=CallType.DELEGATECALL
    )

    encoded = cmd.encode()
    assert isinstance(encoded, list)
    assert len(encoded) == 1  # For regular commands, list has 1 element
    assert len(encoded[0]) == 32  # The command itself must be 32 bytes

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
    call_cmd = Command(function_selector=selector, target=target, inputs=inputs, output=output, call_type=CallType.CALL)

    encoded_call = call_cmd.encode()
    decoded_call = Command.decode(encoded_call)
    assert decoded_call.call_type == CallType.CALL

    # Test STATICCALL
    static_cmd = Command(
        function_selector=selector, target=target, inputs=inputs, output=output, call_type=CallType.STATICCALL
    )

    encoded_static = static_cmd.encode()
    decoded_static = Command.decode(encoded_static)
    assert decoded_static.call_type == CallType.STATICCALL

    # Test VALUECALL
    value_cmd = Command(
        function_selector=selector, target=target, inputs=inputs, output=output, call_type=CallType.VALUECALL
    )

    encoded_value = value_cmd.encode()
    decoded_value = Command.decode(encoded_value)
    assert decoded_value.call_type == CallType.VALUECALL


def test_command_with_extended_inputs():
    # Create a command with more than 6 inputs
    selector = function_signature_to_4byte_selector("complexFunction(uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256)")
    target = to_bytes(hexstr="0x1234567890123456789012345678901234567890")
    
    # Create 8 inputs (more than the 6 allowed in a single command)
    inputs = [CommandArg(index=i) for i in range(8)]
    
    # Output at state index 10
    output = CommandArg(index=10)
    
    cmd = Command(
        function_selector=selector,
        target=target,
        inputs=inputs,
        output=output
    )
    
    # Verify this is an extended inputs command
    assert cmd.extended_inputs
    
    # Encode the command
    encoded = cmd.encode()
    
    # Verify the encoding produced a list with 2 elements
    assert isinstance(encoded, list)
    assert len(encoded) == 2
    assert len(encoded[0]) == 32  # Main command is 32 bytes
    assert len(encoded[1]) == 32  # Extended inputs command is 32 bytes
    
    # The first 4 bytes of the extended inputs command should be the special marker
    assert encoded[1][0:4] == b"\xFF\xFF\xFF\xFF"
    # The 5th byte should be the number of extended inputs (2 in this case)
    assert encoded[1][4] == 2
    
    # Now decode the command
    decoded = Command.decode(encoded)
    
    # Verify the decoded command matches the original
    assert decoded.function_selector == selector
    assert decoded.target == target
    assert len(decoded.inputs) == 8  # Should have all 8 inputs
    
    # Check all input indices are correct
    for i, arg in enumerate(decoded.inputs):
        assert arg.index == i
    
    # Check output index
    assert decoded.output.index == 10
