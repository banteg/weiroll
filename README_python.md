# Weiroll Python SDK

A Python SDK for Weiroll - a simple and efficient operation-chaining language for the EVM.

## Installation

```bash
pip install weiroll
```

## Basic Usage

The Python SDK allows you to construct Weiroll command chains, which you can then execute through your preferred method for interacting with the EVM.

### Creating a Contract

```python
from weiroll import Contract

# Create a contract instance from ABI and address
contract = Contract("0x1234567890123456789012345678901234567890", abi)

# Or when using web3.py
from web3 import Web3
w3 = Web3(Web3.HTTPProvider("..."))
token_contract = w3.eth.contract(address="0x...", abi=token_abi)
token = Contract.createContract(token_contract)
```

### Planning Operations

```python
from weiroll import Planner

# Create a planner
planner = Planner()

# Add operations to the plan
balance = planner.add(token.balanceOf(user_address))
allowance = planner.add(token.allowance(user_address, spender_address))

# Chain operations by using previous results
if_sufficient = planner.add(token.transfer(recipient, balance))

# Add value call (for payable functions)
planner.add(contract.deposit().withValue(1000000000000000000))  # 1 ETH
```

### Generating Commands and State

```python
# Generate the plan
plan = planner.plan()

# Get commands and state arrays
commands = plan["commands"]
state = plan["state"]

# These can be used with a deployed Weiroll VM
```

## Advanced Usage

### Call Types

You can specify different call types:

```python
from weiroll import CallType

# Default is DELEGATECALL
result1 = planner.add(library.someFunction(arg1, arg2))

# For external contracts, use CALL
result2 = planner.add(external.someFunction(arg1, arg2))

# For view functions, use STATICCALL (not directly supported yet, but will be added)

# For payable functions, use CALL with value
result3 = planner.add(payable.deposit().withValue(web3.toWei(1, "ether")))
```

### Handling Complex Data Types

The SDK supports various Ethereum data types:

```python
# Integers
planner.add(contract.setValue(123))

# Strings
planner.add(contract.setName("Weiroll"))

# Addresses (as hex strings)
planner.add(contract.setAddress("0x1234567890123456789012345678901234567890"))

# Byte arrays
planner.add(contract.setData(b"\x01\x02\x03"))

# Arrays
planner.add(contract.setArray([1, 2, 3]))
```

## Integration with Web3

While this SDK focuses on encoding and decoding Weiroll commands, you can integrate it with web3.py to execute them:

```python
import web3
from weiroll import Planner, Contract

# Create a web3.py instance
w3 = web3.Web3(web3.HTTPProvider("https://..."))

# Get your VM instance
vm_address = "0x..."
vm_abi = [...]  # ABI for the Weiroll VM
vm_contract = w3.eth.contract(address=vm_address, abi=vm_abi)

# Create your plan
planner = Planner()
# ... add operations ...

# Get commands and state
plan = planner.plan()
commands = plan["commands"]
state = plan["state"]

# Execute through web3.py
tx_hash = vm_contract.functions.execute(commands, state).transact({'from': w3.eth.accounts[0]})
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
```

## Notes

- This SDK only handles the encoding and preparation of Weiroll commands
- You need to deploy the Weiroll VM separately
- Execution of the commands happens on-chain