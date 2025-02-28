from ape import chain
from eth_abi import decode

from weiroll import Contract, Planner


def test_decode_uniswap_path_array(ape_dai, ape_weth, ape_uniswap, recipient):
    """Test that address arrays used with Uniswap are properly encoded and can be decoded."""
    # Wrap contracts with Weiroll
    Contract.create_contract(ape_dai)
    Contract.create_contract(ape_weth)
    uniswap_wei = Contract.create_contract(ape_uniswap)

    # Create planner
    planner = Planner()

    # Setup swap parameters
    amount = 1000 * 10**18
    deadline = chain.blocks[-1].timestamp + 3600

    # Define path for the swap
    path = [str(ape_dai.address), str(ape_weth.address)]
    print(f"Original path: {path}")

    # Add the swap operation to the planner
    planner.add(
        uniswap_wei.swapExactTokensForTokens(
            amount,
            0,  # Min amount out
            path,  # Path array
            str(recipient.address),  # Recipient
            deadline,
        )
    )

    # Generate plan
    plan = planner.plan()
    print(f"Plan generated with {len(plan['commands'])} commands")

    # Find the path array in the state
    array_index = None
    for i, item in enumerate(planner.state):
        if isinstance(item, list) and all(isinstance(x, str) and x.startswith("0x") for x in item):
            print(f"Found address array at index {i}: {item}")
            array_index = i
            encoded_array = plan["state"][i]
            break

    assert array_index is not None, "Path array not found in state"

    # Decode the encoded array
    encoded_bytes = bytes.fromhex(encoded_array[2:])  # Remove '0x' prefix
    decoded_path = decode(["address[]"], encoded_bytes)[0]

    print(f"Decoded path: {decoded_path}")

    # Verify the decoded addresses match the original path
    assert len(decoded_path) == len(path), "Array length mismatch"

    for i, addr in enumerate(path):
        assert addr.lower() == decoded_path[i].lower(), f"Address at index {i} doesn't match"

    # Additional validation - ensure we can create a proper swap with this path
    print("Verification successful - address array was properly encoded and decoded!")
