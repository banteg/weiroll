"""
Demo of Weiroll Subplan functionality for flash loans and callbacks.

This demonstrates how to:
1. Create subplans for nested execution contexts
2. Use subplans for flash loan implementations
3. Chain multiple operations within a subplan
4. Access return values across plan boundaries

Flash loans are a good use case for subplans because they require:
- A callback pattern (lend → callback → repay)
- Multiple operations within the callback
- Access to external state (loan amount)
"""

import ape
from ape import Contract as ApeContract, networks
from eth_utils import to_wei
from weiroll import Contract, Planner, SubplanValue


def main():
    # Set up contracts (mocked for demo purposes)
    # In a real scenario, we'd use actual contract addresses
    lending_pool = Contract(
        ApeContract("0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9")  # Aave lending pool
    )
    dai = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))  # DAI token
    weth = Contract(ApeContract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"))  # WETH
    router = Contract(ApeContract("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"))  # Uniswap router

    # Set up the flash loan amount
    loan_amount = to_wei(1000, "ether")  # 1000 DAI
    recipient = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # vitalik.eth

    # Create a subplan for the flash loan callback
    # This will be executed during the flash loan callback
    subplan = Planner()

    # 1. In the subplan, we can perform multiple operations with the borrowed tokens
    
    # Get the borrowed token balance
    balance = subplan.add(dai.balanceOf(ape.accounts.test_accounts[0]))
    
    # Approve DAI for Uniswap
    subplan.add(dai.approve(router.address, balance))
    
    # Path for token swap: DAI -> WETH
    path = [str(dai.address), str(weth.address)]
    deadline = 9999999999  # Far future
    
    # Swap the borrowed DAI for WETH
    eth_amount = subplan.add(
        router.swapExactTokensForTokens(
            balance,  # Amount in
            0,  # Min amount out (0 for demo)
            path,  # Swap path
            recipient,  # Recipient
            deadline  # Deadline
        )
    )
    
    # Now create the main planner that will perform the flash loan
    planner = Planner()
    
    # Execute flash loan with the subplan callback
    # The flash loan function takes:
    # - Asset address
    # - Amount to borrow
    # - Recipient 
    # - The subplan (callback operations)
    # - The current VM state
    planner.addSubplan(
        lending_pool.flashLoan(
            recipient,
            dai.address,
            loan_amount,
            SubplanValue(subplan),
            planner.state_value
        )
    )
    
    # Show the execution plan
    print("Execution Plan:")
    print(planner.show_tree())
    
    # Get the actual commands and state for VM execution
    plan = planner.plan()
    
    print(f"\nGenerated {len(plan['commands'])} commands and {len(plan['state'])} state items")
    print("Commands:", plan["commands"])


if __name__ == "__main__":
    with networks.ethereum.mainnet.use_provider('http://127.0.0.1:8545'):
        main()
