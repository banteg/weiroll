#!/usr/bin/env python
"""
Weiroll Tree Renderer Demo

This script shows the enhanced tree visualization in action with color support.
"""
from weiroll import Contract, Planner, Decoder
from weiroll.utils.terminal_colors import get_color_mode
import ape
from ape import networks
import argparse


def main():
    """Run the demo to show enhanced tree rendering."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Weiroll Tree Renderer Demo with Color Support")
    parser.add_argument("--color", "-c", choices=["auto", "on", "off"], default="auto",
                        help="Control color output (auto, on, off)")
    args = parser.parse_args()
    
    # Set color mode based on arguments
    color_mode = None  # Auto by default
    if args.color == "on":
        color_mode = True
    elif args.color == "off":
        color_mode = False
        
    # Show current color mode
    color_status = "ON" if get_color_mode() else "OFF"
    print(f"Color support auto-detected: {color_status}")
    if color_mode is not None:
        force_status = "ON" if color_mode else "OFF"
        print(f"Color mode forced: {force_status}")
    
    # Connect to the network
    with networks.parse_network_choice("ethereum:mainnet:http://127.0.0.1:8545"):
        # Create some contracts
        token = Contract(ape.Contract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))  # DAI
        vault = Contract(ape.Contract("0xd8063123BBA3B480569244AE66BFE72B6c84b00d"))  # yearn vault

        # Create user address
        user = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

        # Example 1: Simple deposit/withdrawal flow
        print("\n===== Example 1: Vault Deposit/Withdrawal Flow =====")
        planner1 = Planner()
        assets = planner1.add(token.balanceOf(user))
        shares = planner1.add(vault.deposit(assets, user))
        planner1.add(vault.redeem(shares, user, user))
        print(planner1.show_tree(use_color=color_mode))

        # Example 2: Simple math operations with clear dependencies
        print("\n===== Example 2: Math operations with dependencies =====")
        planner2 = Planner()
        a = planner2.add(token.balanceOf(user))               # Get balance
        b = planner2.add(token.allowance(user, vault.address))  # Get allowance
        c = planner2.add(token.approve(vault.address, a))     # Approve the exact balance
        d = planner2.add(vault.deposit(a, user))              # Deposit the exact balance
        planner2.add(vault.redeem(d, user, user))             # Redeem all shares
        print(planner2.show_tree(use_color=color_mode))

        # Example 3: Multiple usages of a single value
        print("\n===== Example 3: Multiple usages of a single value =====")
        planner3 = Planner()
        balance = planner3.add(token.balanceOf(user))
        half_balance = balance  # Just for demonstration - normally would divide
        
        # Use the same balance value in multiple operations
        planner3.add(token.approve(vault.address, balance))
        planner3.add(vault.deposit(half_balance, user))
        planner3.add(token.transfer(user, half_balance))
        print(planner3.show_tree(use_color=color_mode))
        
        # Example 4: Decoded plan with color
        print("\n===== Example 4: Decoded Plan with Color =====")
        # Get the commands and state from planner3
        plan = planner3.plan()
        # Decode the plan with color support
        decoded_plan = Decoder.decode_plan(
            plan["commands"], 
            plan["state"],
            use_color=color_mode
        )
        print(decoded_plan)


if __name__ == "__main__":
    main()