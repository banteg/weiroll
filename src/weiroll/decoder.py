import logging
from functools import lru_cache
from typing import Any, Union

from ape import Contract as ApeContract
from eth_utils import function_signature_to_4byte_selector, to_checksum_address, to_hex

from .command import Command, CommandArg
from .planner import Planner

# Set up logger
logger = logging.getLogger("weiroll.decoder")
# Set to debug level
logger.setLevel(logging.DEBUG)
# Add console handler if not already present
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)


class Decoder:
    """
    Decoder for Weiroll commands and plans.

    This class provides utilities to decode Weiroll commands and plans
    into enhanced Planner objects with additional metadata for visualization.

    Example:
        ```python
        # Generate a plan
        planner = Planner()
        # ... add operations ...
        plan = planner.plan()

        # Decode the plan for visualization
        decoded_planner = Decoder.decode_plan(plan["commands"], plan["state"])

        # View as a tree (same format as planner.show_tree())
        print(decoded_planner)  # __str__ now uses show_tree() format

        # Use the decoded planner directly
        new_plan = decoded_planner.plan()
        ```
    """

    @staticmethod
    def decode_extended_inputs(command_data: Union[str, bytes]) -> list[int]:
        """
        Decode extended inputs from a specialized extended inputs command.

        Args:
            command_data: The extended inputs command data

        Returns:
            list[int]: List of state indices for extended inputs
        """
        # Use the Command class to decode the extended inputs command
        cmd = Command.decode(command_data)

        # Check if this is actually an extended inputs command
        if cmd.function_selector != b"\xff\xff\xff\xff":
            return []

        # Extract the input indices
        return [arg.index for arg in cmd.inputs]

    @staticmethod
    def decode_command(command_data: Union[str, bytes]) -> Command:
        """
        Decode a command from bytes32 or hex string and enhance it with metadata.

        Args:
            command_data: The command data to decode (bytes32 or hex string)

        Returns:
            Command: A decoded command with enhanced metadata

        Raises:
            ValueError: If the command data is invalid
        """
        # Use the existing Command class to decode
        cmd = Command.decode(command_data)

        # Store raw command string for reference
        cmd.raw_command = to_hex(command_data) if isinstance(command_data, bytes) else command_data

        # Add function_info for enhanced display
        cmd.function_info = None

        # Try to get function info
        target_address = to_checksum_address("0x" + cmd.target.hex())
        selector_hex = "0x" + cmd.function_selector.hex()

        # Try to look up with ape if available
        try:
            contract = ApeContract(target_address)

            # Try to get the signature from the contract's identifier_lookup
            # Try to use decode_input to get the correct function signature
            try:
                # Log the selector for debugging
                logger.debug(f"Processing selector: {selector_hex}")

                # Try to get the function info from identifier_lookup
                if hasattr(contract, "identifier_lookup") and selector_hex in contract.identifier_lookup:
                    identifier = contract.identifier_lookup[selector_hex]
                    function_signature = identifier.signature
                    function_name = identifier.name
                    logger.debug(f"Matched function via identifier_lookup: {function_signature}")
                else:
                    # Use decode_input with enough data for the function to be identified
                    try:
                        selector_bytes = bytes.fromhex(
                            selector_hex[2:] if selector_hex.startswith("0x") else selector_hex
                        )
                        # Add more placeholders to handle functions with multiple args
                        min_calldata = selector_bytes + b"\x00" * 128  # 4 parameters x 32 bytes

                        # Try to get the function signature from decode_input
                        decoded_input = contract.decode_input(min_calldata)
                        if decoded_input and len(decoded_input) > 0:
                            # First element is the function signature string
                            function_signature = decoded_input[0]
                            function_name = function_signature.split("(")[0]
                            logger.debug(f"Matched function via decode_input: {function_signature}")
                        else:
                            # If no signature found, use a generic one
                            function_name = "function"
                            function_signature = f"function({selector_hex})"
                            logger.debug(f"Using generic function signature for selector: {selector_hex}")
                    except Exception as e:
                        logger.debug(f"Error in decode_input: {e}")
                        # Fall back to a simpler selector-based name
                        function_name = "function"
                        function_signature = f"function({selector_hex})"

                cmd.function_info = {
                    "name": function_name,
                    "signature": function_signature,
                    "selector": selector_hex,  # Keep the original selector
                }
            except Exception as e:
                logger.debug(f"Error looking up function by identifier: {e}")
        except Exception as e:
            logger.debug(f"Error looking up function info: {e}")

        return cmd

    @staticmethod
    def decode_plan(commands: list[Union[str, bytes]], state: list[str], lookup_function_info: bool = True) -> Planner:
        """
        Decode a full Weiroll plan into an enhanced Planner object.

        Args:
            commands: List of command data (bytes32 or hex strings)
            state: List of state values
            lookup_function_info: Whether to try to lookup additional function info

        Returns:
            Planner: An enhanced Planner object with decoded metadata
        """
        # Create a new planner to hold the decoded plan
        planner = Planner()

        # First decode commands with basic information
        decoded_commands = [Decoder.decode_command(cmd) for cmd in commands]

        # Clean up state values for display
        clean_state = []
        for value in state:
            if isinstance(value, bytes):
                clean_state.append(to_hex(value))
            else:
                clean_state.append(value)

        # Process command pairs for extended inputs
        i = 0
        while i < len(commands) - 1:
            cmd_data = commands[i]
            next_cmd_data = commands[i + 1]

            # Check if current command is extended and next is an extended inputs command
            try:
                # Decode main command
                cmd = Command.decode(cmd_data)

                if cmd.extended_inputs:
                    # Decode extended inputs from next command
                    extended_indices = Decoder.decode_extended_inputs(next_cmd_data)

                    if extended_indices:
                        logger.debug(f"Found {len(extended_indices)} extended inputs for command {i}")

                        # Add extended inputs to the decoded command
                        decoded_commands[i].inputs.extend([CommandArg(index=idx) for idx in extended_indices])

                        # Skip the extended inputs command as it's been processed
                        i += 2
                        continue
            except Exception as e:
                logger.debug(f"Error processing extended inputs at command {i}: {e}")

            # Move to next command if no extended inputs found
            i += 1

        # If lookup_function_info is True, try to enhance command info
        if lookup_function_info:
            # Create a dictionary of target addresses
            target_addresses = {}
            for cmd in decoded_commands:
                target_addr = to_checksum_address("0x" + cmd.target.hex())
                if target_addr not in target_addresses:
                    target_addresses[target_addr] = []
                target_addresses[target_addr].append(cmd)

            # For each target address, try to get ABI and function info in bulk
            for target, cmds in target_addresses.items():
                # Try with ape if available
                contract = ApeContract(target)

                # For each command targeting this contract
                for cmd in cmds:
                    # Only process if function info not already set
                    if not hasattr(cmd, "function_info") or not cmd.function_info:
                        # Try to get the signature from the contract's identifier_lookup
                        # Try to use decode_input to get the correct function signature for this selector
                        try:
                            # Check identifier_lookup first (most reliable)
                            selector = "0x" + cmd.function_selector.hex()
                            logger.debug(f"Processing selector in decode_plan: {selector}")

                            # Use identifier lookup when available
                            if hasattr(contract, "identifier_lookup") and selector in contract.identifier_lookup:
                                # Get function details from identifier lookup
                                identifier = contract.identifier_lookup[selector]
                                function_signature = identifier.signature
                                function_name = identifier.name
                                logger.debug(f"Matched function via identifier_lookup: {function_signature}")
                            else:
                                # Try to get a better signature from decode_input
                                try:
                                    selector_bytes = bytes.fromhex(
                                        selector[2:] if selector.startswith("0x") else selector
                                    )
                                    # Use more zeros to handle functions with multiple parameters
                                    min_calldata = selector_bytes + b"\x00" * 128  # Support up to 4 parameters

                                    # Use decode_input to get the function signature
                                    decoded_input = contract.decode_input(min_calldata)
                                    if decoded_input and len(decoded_input) > 0:
                                        # First element is the function signature string
                                        function_signature = decoded_input[0]
                                        function_name = function_signature.split("(")[0]
                                        logger.debug(f"Matched via decode_input: {function_signature}")
                                    else:
                                        # Default fallback if no signature found
                                        function_signature = f"function({selector})"
                                        function_name = "function"
                                except Exception as e:
                                    logger.debug(f"Error using decode_input: {e}")
                                    # Fall back to a basic name
                                    function_signature = f"function({selector})"
                                    function_name = "function"

                            cmd.function_info = {
                                "name": function_name,
                                "signature": function_signature,
                                "selector": selector,  # Keep the original selector
                            }
                        except Exception as e:
                            logger.debug(f"Error using decode_input for cmd: {e}")
                            if hasattr(contract, "identifier_lookup") and selector in contract.identifier_lookup:
                                identifier = contract.identifier_lookup[selector]
                                cmd.function_info = {
                                    "name": identifier.name,
                                    "signature": identifier.signature,
                                    "selector": selector,  # Use the actual selector from the command
                                }

        # Set the planner's properties
        planner.commands = decoded_commands
        planner.state = clean_state

        # Find the highest state index to set next_state_index
        max_state_index = 0
        for cmd in decoded_commands:
            if cmd.output is not None and not isinstance(cmd.output.index, str) and cmd.output.index > max_state_index:
                max_state_index = cmd.output.index
            for inp in cmd.inputs:
                if not isinstance(inp.index, str) and inp.index > max_state_index:
                    max_state_index = inp.index

        planner.next_state_index = max_state_index + 1

        # Add metadata to the planner for enhanced display
        planner.is_decoded = True

        # Store the original __str__ method and override it to use show_tree by default
        from types import MethodType

        original_str = planner.__str__
        planner._original_str = original_str  # Save original for reference
        planner.__str__ = MethodType(lambda self: self.show_tree(), planner)

        return planner

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_selector_for_function(name: str, input_types: list[str]) -> str:
        """
        Calculate a function selector from name and input types.

        Args:
            name: Function name
            input_types: List of input type strings

        Returns:
            str: The 4-byte function selector as a hex string
        """
        signature = f"{name}({','.join(input_types)})"
        return to_hex(function_signature_to_4byte_selector(signature))

    @staticmethod
    def decode_command_with_abi(
        command_data: Union[str, bytes], abi: list[dict[str, Any]] | None = None, contract_address: str | None = None
    ) -> Command:
        """
        Decode a command with ABI information for enhanced readability.

        Args:
            command_data: The command data to decode (bytes32 or hex string)
            abi: The ABI for the target contract (optional if contract_address is provided)
            contract_address: The contract address to look up (optional if abi is provided)

        Returns:
            Command: A decoded command with enhanced metadata
        """
        # First get a basic decoded command
        cmd = Decoder.decode_command(command_data)

        # Use contract address from decoded command if not provided
        if not contract_address:
            contract_address = to_checksum_address("0x" + cmd.target.hex())

        # Find the function in the ABI using one of several approaches
        fn_selector = "0x" + cmd.function_selector.hex()
        function_signature = None

        # Only attempt to look up if not already found
        if not hasattr(cmd, "function_info") or not cmd.function_info:
            # 1. Try to get the function signature from the contract's identifier_lookup
            contract = ApeContract(contract_address)
            # Try to use decode_input to get the correct function signature for this selector
            try:
                logger.debug(f"Processing selector in decode_command_with_abi: {fn_selector}")

                # For other selectors, use decode_input
                selector_bytes = bytes.fromhex(fn_selector[2:] if fn_selector.startswith("0x") else fn_selector)
                min_calldata = selector_bytes + b"\x00" * 32  # Add one parameter of zeros

                # Use decode_input to get the function signature
                decoded_input = contract.decode_input(min_calldata)
                if decoded_input and len(decoded_input) > 0:
                    # First element is the function signature string
                    function_signature = decoded_input[0]
                    function_name = function_signature.split("(")[0]

                cmd.function_info = {
                    "name": function_name,
                    "signature": function_signature,
                    "selector": fn_selector,  # Keep the original selector
                }
            except Exception as e:
                # Fall back to identifier_lookup if decode_input fails
                logger.debug(f"Error using decode_input in decode_command_with_abi: {e}")
                if hasattr(contract, "identifier_lookup") and fn_selector in contract.identifier_lookup:
                    identifier = contract.identifier_lookup[fn_selector]
                    function_signature = identifier.signature
                    # Use the actual selector from the command to ensure we get the correct function
                    cmd.function_info = {
                        "name": identifier.name,
                        "signature": function_signature,
                        "selector": fn_selector,
                    }

        # 2. Try to find the function in the provided ABI
        if (not hasattr(cmd, "function_info") or not cmd.function_info) and abi:
            # Try to match the function by selector
            for item in abi:
                if item.get("type") != "function":
                    continue

                name = item.get("name", "")
                inputs = item.get("inputs", [])

                # Skip if no name or no inputs section
                if not name or inputs is None:
                    continue

                # Extract input types
                input_types = []
                for inp in inputs:
                    if isinstance(inp, dict) and "type" in inp:
                        input_types.append(inp["type"])
                    else:
                        # If input doesn't have a type, skip this function
                        logger.warning(f"Skipping function {name} due to missing input type")
                        break
                else:
                    # Calculate selector for this function
                    calculated_selector = Decoder._get_selector_for_function(name, input_types)

                    # If selectors match, we found the function
                    if calculated_selector == fn_selector:
                        function_signature = f"{name}({','.join(input_types)})"

                        # Set function info on the decoded command
                        cmd.function_info = {
                            "name": name,
                            "signature": function_signature,
                            "inputs": inputs,
                            "outputs": item.get("outputs"),
                        }
                        break

            # 3. Try to use 4byte.directory API or other signature sources
            # We'll only implement this placeholder for now - future enhancement
            if (not hasattr(cmd, "function_info") or not cmd.function_info) and not function_signature:
                # Placeholder for possible future enhancement:
                # - Query 4byte.directory API
                # - Use local signature database
                # - Check etherscan API
                pass

            # Add minimal function info if only signature is available
            if (not hasattr(cmd, "function_info") or not cmd.function_info) and function_signature:
                name = function_signature.split("(")[0]
                cmd.function_info = {"name": name, "signature": function_signature}

        return cmd

    @staticmethod
    def to_planner(decoded_planner: Planner) -> Planner:
        """
        Create a fresh Planner object from a decoded planner.

        This is useful when you want to modify a plan that was previously decoded.
        It creates a new clean Planner without the decoding-specific attributes.

        Args:
            decoded_planner: The decoded planner to convert

        Returns:
            Planner: A fresh Planner object with the same commands and state

        Example:
            ```python
            # Decode a plan
            plan = planner.plan()
            decoded = Decoder.decode_plan(plan["commands"], plan["state"])

            # Display it
            print(decoded)  # Uses show_tree() by default

            # Convert to a fresh Planner for additional operations
            new_planner = Decoder.to_planner(decoded)
            ```
        """
        # Create a new planner
        planner = Planner()

        # Copy state
        for state_value in decoded_planner.state:
            planner.state.append(state_value)

        # Set next_state_index to match the decoded planner
        planner.next_state_index = decoded_planner.next_state_index

        # Copy commands
        for cmd in decoded_planner.commands:
            planner.commands.append(cmd)

        return planner
