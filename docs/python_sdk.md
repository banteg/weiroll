# Weiroll Python SDK

The Weiroll Python SDK provides a high-level interface for creating and executing complex transactions on the Ethereum blockchain. It allows you to orchestrate multiple contract calls with interdependencies in a single atomic transaction.

## Installation

```bash
pip install weiroll
# or with uv
uv install weiroll
```

## Core Components

### Contract

The `Contract` class wraps Ape contracts to make them compatible with Weiroll.

```python
from weiroll import Contract, CallType
from ape import Contract as ApeContract

# Basic contract wrapping
dai = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))

# Create a contract with a specific call type
library = Contract(ApeContract("0x1234..."), call_type=CallType.DELEGATECALL)
```

Contract methods can be accessed directly:

```python
# Methods can be accessed as attributes
transfer_fn = dai.transfer

# Function signatures are preserved
print(transfer_fn)  # Shows function signature and call type
```

#### Call Types

Weiroll supports different call types:

- `CallType.CALL` - Standard external call (default)
- `CallType.STATICCALL` - Read-only call that cannot modify state
- `CallType.DELEGATECALL` - Call that executes in the context of the caller
- `CallType.VALUECALL` - Call that sends ETH

Example with value call:

```python
# Send ETH with a function call
payable_fn = contract.deposit.with_value(1000000000000000000)  # 1 ETH
```

### Planner

The `Planner` class orchestrates a sequence of contract calls:

```python
from weiroll import Planner

# Create a planner
planner = Planner()

# Or use context manager
with Planner() as planner:
    # Add operations here
    pass
```

#### Adding Operations

Operations are added with `planner.add()`:

```python
# Add a simple operation
planner.add(token.transfer(recipient, amount))

# Capture the result for use in subsequent operations
balance = planner.add(token.balanceOf(user))
planner.add(vault.deposit(balance, user))
```

#### Data Dependencies

Weiroll tracks dependencies between operations automatically:

```python
# Create a sequence of dependent operations
balance = planner.add(token.balanceOf(user))
allowance = planner.add(token.allowance(user, spender))
planner.add(token.transferFrom(user, recipient, min(balance, allowance)))
```

#### Visualizing Plans

Use `planner.show_tree()` to visualize the execution plan:

```python
print(planner.show_tree())

# Example output:
# Command 0: balanceOf(address) -> uint256 @ 0x6B17... [CALL]
#   ├─ Input 0: State[0] = 0xd8dA6BF2...
#   └─ Output: State[1] (→ Command 1)
#
# Command 1: deposit(uint256, address) -> uint256 @ 0xd806... [CALL]
#   ├─ Input 0: State[1] (from Command 0 output)
#   ├─ Input 1: State[0] = 0xd8dA6BF2...
#   └─ Output: State[2] (→ Command 2)
```

#### Generating Plans

Use `planner.plan()` to generate the encoded plan for execution:

```python
plan = planner.plan()

# Returns a dictionary with encoded commands and state
# {
#   'commands': ['0x...', '0x...', ...], 
#   'state': ['0x...', '0x...', ...]
# }
```

### Decoder

The `Decoder` class provides utilities for decoding and visualizing execution plans:

```python
from weiroll import Decoder

# Decode a plan from commands and state
decoded_plan = Decoder.decode_plan(plan["commands"], plan["state"])

# Print the decoded plan (uses show_tree() format)
print(decoded_plan)

# Show plan tree explicitly
print(decoded_plan.show_tree())

# Get detailed information about a command
decoded_cmd = Decoder.decode_command_with_abi(
    command_data,
    contract_address="0x1234..."
)
```

#### Plan Reconstruction

You can convert a decoded plan back to a Planner for further operations:

```python
# Convert a decoded plan to a Planner
reconstructed_planner = Decoder.to_planner(decoded_plan)

# Generate a new plan from the reconstructed planner
new_plan = reconstructed_planner.plan()
```

## Advanced Usage

### Working with Arrays

When using functions that accept arrays (like Uniswap swap paths), always convert addresses to strings:

```python
# Create a swap path with string addresses
path = [
    str(dai.address),
    str(weth.address),
    str(usdc.address)
]

# Use the path in a swap operation
planner.add(
    router.swapExactTokensForTokens(
        amount_in,
        amount_out_min,
        path,  # array of string addresses
        recipient,
        deadline
    )
)
```

### Handling Tuples and Complex Return Values

For functions that return multiple values or tuples:

```python
# The function output is automatically processed
result = planner.add(complex_function())

# Use tuple elements in subsequent calls
planner.add(another_function(result))
```

### Different Call Types

Change the call type for specific operations:

```python
# Make a static call (read-only)
balance = planner.add(token.balanceOf(user).staticcall())

# Make a call with ETH value
planner.add(contract.deposit.with_value(1 * 10**18)())
```

## Exception Handling

The SDK provides custom exceptions:

- `WeirollError` - Base exception for all Weiroll errors
- `InvalidContractError` - Raised when a contract is invalid
- `EmptyABIError` - Raised when a contract has no ABI

## Development

```bash
# Run tests
uv run pytest tests/

# Format code
uv run ruff format .

# Check code style
uv run ruff check .
```