#!/usr/bin/env python
"""
Tests the fix for the planner visualization issue with approve function.

This script demonstrates the correct visualization of command dependencies
in weiroll by running the example that previously had issues.
"""
from ape import accounts, networks
from ape_tokens import tokens
import weiroll

def main():
    """Run test for fixed command visualization"""
    with networks.parse_network_choice('ethereum:mainnet:http://127.0.0.1:8545'):
        print("=== Testing Improved Command Visualization ===")
        
        # Set up the test contracts and accounts
        token = weiroll.Contract(tokens['DAI'])
        dev = accounts.test_accounts[0]
        recipient = accounts.test_accounts[1]
        
        print("\nTest 1: The original issue case")
        planner = weiroll.Planner()
        amount = planner.add(token.balanceOf(str(dev)))
        planner.add(token.approve(str(recipient), amount))
        
        # Print the commands to help debug
        print("\nCommand structure:")
        for i, cmd in enumerate(planner.commands):
            print(f"Command {i}:")
            print(f"  Inputs: {[getattr(arg, 'index', 'unknown') for arg in cmd.inputs]}")
            if cmd.output:
                print(f"  Output: index={cmd.output.index}")
            else:
                print("  Output: None")
        
        # Show tree with fixed visualization
        print("\nCommand Tree (fixed):")
        print(planner.show_tree())
        
        # Print the plan for reference
        plan = planner.plan()
        print("\nEncoded Plan:")
        for key, value in plan.items():
            print(f"{key}: {value}")

if __name__ == "__main__":
    main()