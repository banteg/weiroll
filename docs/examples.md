# Weiroll Examples

This document provides practical examples of using the Weiroll Python SDK for various use cases. These examples demonstrate how to compose complex transaction sequences with interdependencies.

## Basic Examples

### Token Transfer

Simple token transfer operation using an ERC20 contract:

```python
from weiroll import Contract, Planner
from ape import Contract as ApeContract

# Create contract wrapper
token = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))  # DAI

# Create planner
planner = Planner()

# Prepare parameters
recipient = "0x0987654321098765432109876543210987654321"
amount = 100 * 10**18  # 100 tokens

# Add the transfer operation
planner.add(token.transfer(recipient, amount))

# Generate the plan
plan = planner.plan()
```

### Balance Check and Transfer

Check balance before transferring:

```python
# Create contract wrapper for an ERC20 token
token = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))

# Create planner
planner = Planner()

# Define user and recipient
user = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
recipient = "0x0987654321098765432109876543210987654321"

# First get the balance
balance = planner.add(token.balanceOf(user))

# Then transfer half of the balance
planner.add(token.transfer(recipient, balance / 2))
```

## DeFi Examples

### Vault Deposit and Withdrawal

Deposit tokens into a vault and withdraw:

```python
# Create contract wrappers
token = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))
vault = Contract(ApeContract("0xd8063123BBA3B480569244AE66BFE72B6c84b00d"))

# Create planner
planner = Planner()

# User address
user = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

# First approve the vault to spend tokens
amount = 1000 * 10**18  # 1000 tokens
planner.add(token.approve(vault.address, amount))

# Deposit into the vault and receive shares
shares = planner.add(vault.deposit(amount, user))

# Later withdraw the tokens
planner.add(vault.withdraw(shares, user, user))

# Visualize the plan
print(planner.show_tree())
```

### Token Swap on Uniswap

Swap tokens using Uniswap:

```python
# Create contract wrappers
dai = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))
weth = Contract(ApeContract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"))
uniswap = Contract(ApeContract("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"))  # Router

# Create planner
planner = Planner()

# User address
user = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

# Amount to swap
amount_in = 100 * 10**18  # 100 DAI
min_amount_out = 0.01 * 10**18  # Minimum 0.01 WETH to receive
deadline = 1672531200  # Unix timestamp for deadline

# First approve the router to spend DAI
planner.add(dai.approve(uniswap.address, amount_in))

# Create the swap path (IMPORTANT: use string addresses)
path = [str(dai.address), str(weth.address)]

# Execute the swap
planner.add(
    uniswap.swapExactTokensForTokens(
        amount_in,
        min_amount_out,
        path,
        user,
        deadline
    )
)
```

### Lending and Borrowing

Deposit collateral and borrow assets:

```python
# Create contract wrappers
usdc = Contract(ApeContract("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"))
aave = Contract(ApeContract("0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"))  # Lending pool

# Create planner
planner = Planner()

# User address
user = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

# Amount to deposit as collateral
collateral_amount = 1000 * 10**6  # 1000 USDC

# First approve the lending pool to spend USDC
planner.add(usdc.approve(aave.address, collateral_amount))

# Deposit USDC as collateral
planner.add(aave.deposit(usdc.address, collateral_amount, user, 0))

# Borrow ETH against the collateral
borrow_amount = 0.1 * 10**18  # 0.1 ETH
planner.add(
    aave.borrow(
        "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # ETH address in Aave
        borrow_amount,
        2,  # Variable interest rate
        0,  # Referral code
        user
    )
)
```

## Advanced Examples

### Multi-step DeFi Strategy

A complex yield farming strategy:

```python
# Create contract wrappers
dai = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))
weth = Contract(ApeContract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"))
uni_router = Contract(ApeContract("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"))
farm = Contract(ApeContract("0x6d225e974fa404d25ffb84ed6e242ffa18ef6430"))

# Create planner
planner = Planner()

# User address
user = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

# 1. Get user's DAI balance
balance = planner.add(dai.balanceOf(user))

# 2. Approve Uniswap to spend DAI
planner.add(dai.approve(uni_router.address, balance))

# 3. Swap half of DAI for WETH
swap_amount = planner.add(dai.balanceOf(user) / 2)
deadline = 1672531200  # Unix timestamp for deadline
path = [str(dai.address), str(weth.address)]

eth_amount = planner.add(
    uni_router.swapExactTokensForTokens(
        swap_amount,
        0,  # Min amount out (accepting any price)
        path,
        user,
        deadline
    )
)

# 4. Approve tokens for the farm
planner.add(dai.approve(farm.address, balance - swap_amount))
planner.add(weth.approve(farm.address, eth_amount))

# 5. Deposit both tokens into the farm
planner.add(farm.deposit(dai.address, balance - swap_amount))
planner.add(farm.deposit(weth.address, eth_amount))

# Visualize the complex plan
print(planner.show_tree())
```

### Plan Decoding and Reconstruction

Decode and reconstruct a plan:

```python
from weiroll import Decoder

# Original plan
planner = create_complex_plan()  # Function that creates a complex plan
plan = planner.plan()

# Decode the plan
decoded_plan = Decoder.decode_plan(plan["commands"], plan["state"])

# Display the decoded plan
print("Decoded Plan:")
print(decoded_plan)

# Convert back to a Planner
reconstructed_planner = Decoder.to_planner(decoded_plan)

# Generate a new plan from the reconstructed planner
new_plan = reconstructed_planner.plan()

# Verify the plans are equivalent
assert len(plan["commands"]) == len(new_plan["commands"])
```

## Using Different Call Types

### Static Calls for Reading Data

Use static calls to guarantee no state changes:

```python
# Create contract wrapper
token = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))

# Create planner
planner = Planner()

# Make a static call to read balance
balance = planner.add(token.balanceOf("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045").staticcall())

# Use the balance in a subsequent call
planner.add(token.transfer("0x0987654321098765432109876543210987654321", balance / 2))
```

### Value Calls with ETH

Send ETH with function calls:

```python
# Create contract wrapper
weth = Contract(ApeContract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"))

# Create planner
planner = Planner()

# Deposit ETH to get WETH (requires sending value)
planner.add(weth.deposit.with_value(1 * 10**18)())
```