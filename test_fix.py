#!/usr/bin/env python
"""
Tests the enhanced planner visualization with improved command dependencies
and contract information display.

This script demonstrates the enhanced tree visualization features in weiroll.
"""
from ape import accounts, networks, Contract as ApeContract
from ape_tokens import tokens
import weiroll

def main():
    """Run test for enhanced command visualization"""
    with networks.parse_network_choice('ethereum:mainnet:http://127.0.0.1:8545'):
        print("=== Testing Enhanced Tree Visualization ===")
        
        # Set up the test contracts and accounts
        token = weiroll.Contract(tokens['DAI'])
        # Use a direct address for the yearn vault
        vault_address = "0xdA816459F1AB5631232FE5e97a05BBBb94970c95"  # yvDAI vault
        vault = weiroll.Contract(ApeContract(vault_address))
        dev = accounts.test_accounts[0]
        recipient = accounts.test_accounts[1]
        
        print("\nExample: Vault Deposit Flow with Contract Names")
        planner = weiroll.Planner()
        
        # Create a balanced deposit flow using multiple contracts
        amount = planner.add(token.balanceOf(str(dev)))
        planner.add(token.approve(str(vault.address), amount))
        shares = planner.add(vault.deposit(amount, str(dev)))
        
        # Show tree with enhanced visualization
        print("\nEnhanced Command Tree:")
        print(planner.show_tree())
        
if __name__ == "__main__":
    main()