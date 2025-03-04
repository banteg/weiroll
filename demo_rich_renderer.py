#!/usr/bin/env python3
"""
Demo script for the rich renderer in weiroll.

This script creates a simple plan and demonstrates the rich renderer output.
"""

from src.weiroll.planner import Planner
from src.weiroll.utils.rich_renderer import render_rich, render_rich_html
from rich.console import Console


def main():
    # Create a simple planner with some commands
    planner = Planner()

    # Import necessary modules for creating a plan
    from ape import Contract, accounts
    from src.weiroll.contract import ContractFunction

    # Create a dummy plan
    print("Creating a sample plan...")

    # Add some state values
    state_index_1 = planner._add_literal_to_state("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")  # vitalik.eth
    state_index_2 = planner._add_literal_to_state(1000000000000000000)  # 1 ETH in wei

    # Create some dummy commands
    command_dict_1 = {
        "to": "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI address
        "function": "transfer(address recipient, uint256 amount)",
        "selector": "0xa9059cbb",
        "inputs": [state_index_1, state_index_2],
        "outputs": [3],
        "command_type": "CALL",
        "contract_name": "DAI Stablecoin",
        "input_sources": [-1, -1],
    }

    command_dict_2 = {
        "to": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH address
        "function": "deposit() -> uint256 balance",
        "selector": "0xd0e30db0",
        "inputs": [state_index_2],
        "outputs": [4],
        "command_type": "CALL",
        "contract_name": "Wrapped Ether",
        "input_sources": [-1],
    }

    # Build state mapping
    state_sources = {
        3: (0, 0),  # Command 0, output 0
        4: (1, 0),  # Command 1, output 0
    }

    state_usage = {
        0: [(0, 0)],  # Used in command 0, input 0
        1: [(0, 1), (1, 0)],  # Used in command 0, input 1 and command 1, input 0
    }

    # Create a list of commands and state
    commands = [command_dict_1, command_dict_2]
    state = ["0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", 1000000000000000000, None, None, None]
    call_types = ["CALL", "CALL"]

    # Render with rich
    print("\nRendering with rich to console:\n")
    console = render_rich(commands, state, call_types, state_sources, state_usage)

    # Export to HTML using the render_rich_html function
    print("\nExporting to HTML...\n")
    html = render_rich_html(commands, state, call_types, state_sources, state_usage)

    # Save HTML to file
    with open("rich_output.html", "w") as f:
        f.write(html)

    print(f"HTML output saved to rich_output.html")
    print("You can open this file in a browser to see the rich HTML output.")


if __name__ == "__main__":
    main()
