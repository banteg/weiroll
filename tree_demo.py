"""
Weiroll Demo - Enhanced Decoder with Tree Visualization

This script demonstrates the enhanced plan decoder that now matches
the show_tree() format and provides better visualization of command
dependencies in Weiroll execution plans.
"""

import sys
sys.path.append('./src')

from weiroll import Planner, Contract, Decoder, CallType

# Create a basic contract adapter for demo purposes
class DemoContract:
    def __init__(self, address, name="DemoContract"):
        self.address = address
        self.name = name
        self.abi = [
            {
                'inputs': [{'type': 'address'}, {'type': 'uint256'}],
                'name': 'approve',
                'outputs': [{'type': 'bool'}],
                'stateMutability': 'nonpayable',
                'type': 'function'
            },
            {
                'inputs': [{'type': 'uint256'}],
                'name': 'deposit',
                'outputs': [],
                'stateMutability': 'nonpayable',
                'type': 'function'
            },
            {
                'inputs': [{'type': 'uint256'}],
                'name': 'stake',
                'outputs': [],
                'stateMutability': 'nonpayable',
                'type': 'function'
            },
            {
                'inputs': [],
                'name': 'getReward',
                'outputs': [{'type': 'uint256'}],
                'stateMutability': 'view',
                'type': 'function'
            },
            {
                'inputs': [{'type': 'address'}, {'type': 'address'}, {'type': 'uint256'}],
                'name': 'transferFrom',
                'outputs': [{'type': 'bool'}],
                'stateMutability': 'nonpayable',
                'type': 'function'
            }
        ]

# Create a complex DeFi scenario with token approval, vault deposit, and farming
def generate_complex_plan():
    # Create contracts
    token = Contract.create_contract(DemoContract("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC"))
    vault = Contract.create_contract(DemoContract("0x3Fe65692bfCD0e6CF84cB1E7d24108E434A7587e", "Vault"))
    farm = Contract.create_contract(DemoContract("0x8B3d70d628Ebd30D4A2ea82DB95bA2e906c71633", "Farm"))
    
    # Create planner
    planner = Planner()
    
    # User address
    user = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    
    # Amount to deposit (100 USDC)
    amount = 100_000_000  # 6 decimals for USDC
    
    # Step 1: Approve vault to spend tokens
    approval = planner.add(token.approve(vault.address, amount))
    
    # Step 2: Transfer tokens from user to vault (simulate deposit)
    transfer = planner.add(token.transferFrom(user, vault.address, amount))
    
    # Step 3: Deposit into vault
    deposit = planner.add(vault.deposit(amount))
    
    # Step 4: Stake into farm
    stake = planner.add(farm.stake(amount))
    
    # Step 5: Get reward (to see how many tokens we'll earn)
    reward = planner.add(farm.getReward())
    
    return planner

def main():
    print("Weiroll Enhanced Decoder Demo\n")
    
    # Generate a complex DeFi plan
    planner = generate_complex_plan()
    
    # Create and encode the plan
    plan = planner.plan()
    
    print("=== Original Plan Tree ===")
    print(planner.show_tree())
    print()
    
    # Decode the plan
    decoded_plan = Decoder.decode_plan(plan["commands"], plan["state"])
    
    print("=== Decoded Plan Tree ===")
    print(decoded_plan)  # Uses show_tree() format by default now
    print()
    
    # Demonstrate converting back to a Planner
    print("=== Converting Decoded Plan back to Planner ===")
    reconstructed_planner = Decoder.to_planner(decoded_plan)
    
    # Show that both plans have the same structure
    print(f"Original planner: {len(planner.commands)} commands, {len(planner.state)} state entries")
    print(f"Reconstructed planner: {len(reconstructed_planner.commands)} commands, {len(reconstructed_planner.state)} state entries")
    
    # Generate a new plan from the reconstructed planner 
    reconstructed_plan = reconstructed_planner.plan()
    print(f"Reconstructed plan has {len(reconstructed_plan['commands'])} commands")

if __name__ == "__main__":
    main()