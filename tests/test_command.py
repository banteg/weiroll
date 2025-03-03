from eth_utils import function_signature_to_4byte_selector, to_bytes

from weiroll.command import EXT_BIT, Command, CommandArg
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
    assert isinstance(encoded, bytes)
    assert len(encoded) == 32  # The command itself must be 32 bytes

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
    """Test encoding and decoding a command with more than 6 inputs."""
    # Create a command with 8 inputs (exceeding the standard 6)
    selector = bytes.fromhex("12345678")
    target = bytes.fromhex("1111111111111111111122222222222222222222")

    # Create 8 inputs
    inputs = [CommandArg(index=i) for i in range(8)]

    cmd = Command(
        function_selector=selector,
        target=target,
        inputs=inputs,
        output=CommandArg(index=10),
        call_type=CallType.CALL,
    )

    # The command should use extended encoding
    assert cmd.extended_inputs

    # Encode the command
    encoded = cmd.encode()

    # Extended command should be 64 bytes (two 32-byte words)
    assert isinstance(encoded, bytes)
    assert len(encoded) == 64

    # Verify the extended flag is set in the encoded command
    assert (encoded[4] & EXT_BIT) != 0

    # For extended commands, the 6 bytes after the flags should be zeros
    for i in range(5, 11):
        assert encoded[i] == 0

    # Decode the command
    decoded = Command.decode(encoded)

    # Verify all properties are preserved
    assert decoded.function_selector == selector
    assert decoded.target == target
    assert len(decoded.inputs) == 8
    assert decoded.extended_inputs

    # Check that all input indices were preserved
    for i, arg in enumerate(decoded.inputs):
        assert arg.index == inputs[i].index

    # Verify output
    assert decoded.output.index == 10
