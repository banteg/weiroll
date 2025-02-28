# Weiroll SDK Usage Guide

This guide demonstrates how to use the Python SDK for Weiroll to create and execute operation chains.

## Installation

```bash
pip install weiroll
```

## Basic Usage

### Creating Contract Wrappers

The first step is to create wrappers for the contracts you want to interact with:

```python
from weiroll import Contract
from web3 import Web3

# Connect to web3
w3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/YOUR_API_KEY'))

# Create contract wrappers
dai = w3.eth.contract(address='0x6B175474E89094C44Da98b954EedeAC495271d0F', abi=dai_abi)
weth = w3.eth.contract(address='0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', abi=weth_abi)
uniswap = w3.eth.contract(address='0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D', abi=uniswap_abi)

# Create Weiroll contract wrappers
dai_contract = Contract.createContract(dai)
weth_contract = Contract.createContract(weth)
uniswap_contract = Contract.createContract(uniswap)

# For stateless libraries that use delegatecall
math_library = Contract.createLibrary(math_contract)
```

### Planning Operations

Once you have contract wrappers, you can create a plan:

```python
from weiroll import Planner

# Create a planner
planner = Planner()

# Get approval for Uniswap to spend DAI
planner.add(dai_contract.approve(uniswap_contract.address, 1000 * 10**18))

# Swap DAI for WETH
# The result will be the amount of WETH received
weth_amount = planner.add(
    uniswap_contract.swapExactTokensForTokens(
        1000 * 10**18,  # amount of DAI to swap
        0,              # minimum amount of WETH to receive
        [dai_contract.address, weth_contract.address],  # swap path
        my_address,     # recipient
        w3.eth.get_block('latest').timestamp + 1800  # deadline
    )
)

# Use the resulting WETH amount in another operation
planner.add(weth_contract.transfer(recipient_address, weth_amount))
```

### Generating the Plan

After adding all operations, generate the plan:

```python
plan = planner.plan()

# The plan contains the encoded commands and state
commands = plan["commands"]  # bytes32[] of commands
state = plan["state"]        # bytes[] of initial state
```

### Executing the Plan

To execute the plan, you need a deployed Weiroll VM contract:

```python
# Get the VM contract
vm = w3.eth.contract(address=vm_address, abi=vm_abi)

# Execute the plan
tx_hash = vm.functions.execute(commands, state).transact({
    'from': my_address,
    'gas': 500000
})

# Wait for the transaction to be mined
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
```

## Advanced Usage

### Call Types

Different call types can be used depending on the interaction:

```python
# Default - CALL for regular contracts
erc20 = Contract.createContract(token_contract)  # Uses CALL

# DELEGATECALL for libraries
math = Contract.createLibrary(math_contract)  # Uses DELEGATECALL

# STATICCALL for read-only operations
result = planner.add(
    erc20.balanceOf(address).staticcall()  # Convert to STATICCALL
)
```

### Value Calls (ETH Transfer)

For functions that require ETH:

```python
# Send 1 ETH with the deposit call
planner.add(
    weth_contract.deposit().withValue(1 * 10**18)
)

# Execute with total value
vm.functions.execute(commands, state).transact({
    'from': my_address,
    'value': 1 * 10**18,  # Send 1 ETH with the transaction
    'gas': 500000
})
```

### Dynamic Arguments

The SDK handles different Ethereum data types:

```python
# Strings
planner.add(contract.setName("Weiroll"))

# Bytes
planner.add(contract.setData(b"\x01\x02\x03"))

# Arrays
planner.add(contract.setArray([1, 2, 3]))

# Using return values from previous operations
amount = planner.add(token.balanceOf(my_address))
planner.add(token.transfer(recipient, amount))
```

## Integration with Web3 Libraries

The SDK is designed to work with common web3 libraries:

### Web3.py

```python
from web3 import Web3
from weiroll import Contract, Planner

w3 = Web3(Web3.HTTPProvider('...'))
contract = w3.eth.contract(address='0x...', abi=[...])
weiroll_contract = Contract.createContract(contract)

planner = Planner()
# Add operations...
plan = planner.plan()

vm = w3.eth.contract(address='0x...', abi=vm_abi)
vm.functions.execute(plan["commands"], plan["state"]).transact({
    'from': w3.eth.accounts[0]
})
```

### eth-brownie

```python
from brownie import Contract as BrownieContract
from weiroll import Contract, Planner

token = BrownieContract.from_abi("Token", "0x...", [...])
weiroll_token = Contract.createContract(token)

planner = Planner()
# Add operations...
plan = planner.plan()

vm = BrownieContract.from_abi("VM", "0x...", vm_abi)
vm.execute(plan["commands"], plan["state"], {'from': accounts[0]})
```

## Error Handling

Handle errors properly when using the SDK:

```python
try:
    planner.add(token.transfer(recipient, amount))
    plan = planner.plan()
except ValueError as e:
    print(f"Planning error: {e}")

try:
    tx_hash = vm.functions.execute(plan["commands"], plan["state"]).transact({
        'from': my_address
    })
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    # Check if transaction was successful
    if receipt.status == 0:
        print("Transaction failed")
except Exception as e:
    print(f"Execution error: {e}")
```

## Best Practices

1. **Gas Efficiency**:
   - Group related operations to minimize gas costs
   - Be mindful of dynamic data size impact on gas costs

2. **Security**:
   - Validate plans before executing
   - Use STATICCALL for read-only operations
   - Test plans thoroughly before deploying

3. **Performance**:
   - Reuse values when possible
   - Keep dynamic data sizes small when possible

4. **Integration**:
   - Use separate VM instances for different applications
   - Consider implementing a dedicated safety layer around VM execution

## Conclusion

The Weiroll Python SDK provides a powerful way to build and execute transaction chains on Ethereum. By following this guide, you can create efficient and flexible operation sequences that execute atomically in a single transaction.