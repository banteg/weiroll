# Weiroll Development Guide

## Python SDK

### Overview
The Python SDK provides bindings to interact with the Weiroll VM. It allows creating plans, wrapping contracts, and generating command sequences to execute on-chain.

### Key Features
- **Command Execution:** Create and execute sequences of contract calls
- **Subplans:** Create nested execution contexts for flash loans and callbacks
- **State Replacement:** Replace planner state during execution for advanced use cases
- **Plan Visualization:** Display plans as trees with `planner.show_tree()`
- **Plan Decoding:** Decode encoded plans with enhanced visualization using `Decoder`
- **Plan Reconstruction:** Recreate Planner objects from decoded plans
- **Value Formatting:** Format large numbers and token amounts for readability
- **Command Dependencies:** Visualize data flow between commands

### Build Commands
- Run Python tests: `uv run pytest tests/`
- Run single test: `uv run pytest tests/test_file.py::test_name -v`
- Run linting: `uv run ruff check .`
- Format code: `uv run ruff format .`

### Contract Adapters
Weiroll provides adapters for different contract interfaces:

1. **Ape contracts**:
   ```python
   from ape import Contract as ApeContract
   from weiroll import Contract
   
   ape_contract = ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F")
   contract = Contract(ape_contract)
   ```

2. **Direct ABI**:
   ```python
   from weiroll import Contract
   contract = Contract(address, abi_list)
   ```

3. **With ethpm_types**:
   ```python
   from ethpm_types import ContractType
   contract_type = ContractType.model_validate_json(json_text)
   model_data = contract_type.model_dump()
   contract = Contract(address, model_data['abi'])
   ```

### Plan Decoding Features

Weiroll supports detailed plan decoding and visualization:

```python
from weiroll import Decoder

# Decode a plan from commands and state
decoded_plan = Decoder.decode_plan(commands, state)

# View in tree format (same as planner.show_tree())
print(decoded_plan)

# Get detailed information about a specific command
detailed_cmd = Decoder.decode_command_with_abi(
    command_data,
    contract_address="0x1234..."
)

# Convert a decoded plan back to a Planner
reconstructed_planner = Decoder.to_planner(decoded_plan)

# Create a new plan from the reconstructed planner
new_plan = reconstructed_planner.plan()
```

The decoder provides detailed visualization showing:
- Command function signatures with parameter types
- Command dependencies and data flow between commands
- State values formatted for readability
- Source commands for each state value used as input

Value formatting will automatically:
- Format token amounts with 18 decimals as "N × 10^18"
- Format ETH values with appropriate units (ETH, gwei, wei)
- Maintain checksummed addresses
- Truncate long hex strings for readability

### Exception Handling
Custom exceptions available in `weiroll.exceptions`:

- `WeirollError`: Base exception for all Weiroll-related errors
- `InvalidContractError`: Raised when a contract object is invalid or unsupported
- `EmptyABIError`: Raised when a contract ABI is empty or None

### Usage Examples

#### Basic Plan Creation and Execution
```python
from weiroll import Contract, Planner, CallType

# Create a contract wrapper
contract = Contract(web3_contract)  # For web3.py contracts
# OR
contract = Contract(ape_contract)   # For ape contracts

# Create a planner and add operations
planner = Planner()
recipient = "0x0987654321098765432109876543210987654321"
amount = 100 * 10**18  # 100 tokens
planner.add(contract.transfer(recipient, amount))

# Visualize the plan
print(planner.show_tree())

# Get the serialized plan
plan = planner.plan()
# Contains commands and state for VM execution
```

#### Creating and Using Subplans
```python
from weiroll import Contract, Planner, SubplanValue

# Create an executor contract wrapper
executor = Contract(executor_contract)  # Contract that can execute subplans

# Create a subplan for a flash loan callback
subplan = Planner()

# Add operations to the subplan
borrowed_balance = subplan.add(token.balanceOf(my_address))
# Perform operations with borrowed funds
swap_result = subplan.add(router.swapExactTokensForTokens(
    borrowed_balance, 0, path, recipient, deadline
))

# Create main planner
planner = Planner()

# Add the subplan to be executed by a flash loan
planner.addSubplan(
    lending_pool.flashLoan(
        recipient,
        token.address,
        loan_amount,
        SubplanValue(subplan),  # The subplan to execute in the callback
        planner.state_value     # The current VM state
    )
)

# You can continue using return values from the subplan
planner.add(logger.logSuccess(swap_result))

# Generate the final plan
plan = planner.plan()
```

#### Plan Decoding and Visualization
```python
from weiroll import Decoder, Planner, Contract

# Assume we have a plan from somewhere
plan = {
    "commands": ["0x095ea7b3..."],
    "state": ["0x..."]
}

# Decode the plan to make it human-readable
decoded_plan = Decoder.decode_plan(plan["commands"], plan["state"])

# Display the plan in tree format (same as planner.show_tree())
print(decoded_plan)

# Example output:
# Command 0: balanceOf(address holder) -> uint256 @ 0x6B17547... [CALL]
#   ├─ Input 0: State[0] = 0xd8dA6BF2...
#   └─ Output: State[1] (→ Command 1)
#
# Command 1: deposit(uint256 assets, address receiver) -> uint256 @ 0xd8063... [CALL]
#   ├─ Input 0: State[1] (from Command 0 output)
#   ├─ Input 1: State[0] = 0xd8dA6BF2...
#   └─ Output: State[2] (→ Command 2)

# Optionally reconstruct a Planner from the decoded plan
reconstructed_planner = Decoder.to_planner(decoded_plan)
```

### Working with Address Arrays
When using functions that take arrays of addresses (like Uniswap's swap paths), 
always convert the addresses to strings:

```python
from ape import Contract as ApeContract
from weiroll import Contract, Planner

# Get token contracts
dai = ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F")
usdc = ApeContract("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
weth = ApeContract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")

# Wrap Uniswap router for weiroll
router = Contract.createContract(ApeContract("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"))

# Create swap path with string addresses
path = [str(dai.address), str(weth.address), str(usdc.address)]

# Use the path in a swap operation
planner = Planner()
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

### Testing
- **Commands**: 
  - Run all tests: `uv run pytest tests/`
  - Run specific tests: `uv run pytest tests/test_file.py::test_name -v`
  - Run with increased verbosity: `uv run pytest -vv`
- **Linting and Formatting**:
  - Check code style: `uv run ruff check .`
  - Fix code style issues: `uv run ruff check --fix .`
  - Format code: `uv run ruff format .`
- **Test framework:** pytest with Ape's testing plugin
- **Fixtures:** Common contracts and accounts available in conftest.py
- **Integration tests:** Tests for both web3.py and ape contracts
- **Live contracts:** Tests use real mainnet contracts via forking
- **Test patterns:** Test files follow the format `test_*.py` with functions named `test_*`

## Solidity (Contract Development)

### Build Commands
- Install dependencies: `npm install`
- Run all tests: `npm run test` or `npx hardhat test`
- Run single test: `npx hardhat test test/VM.js --grep "test description"`
- Format code: `npm run format`
- Lint Solidity: `npx solhint contracts/**/*.sol`

### Code Style Guidelines
- **Solidity version:** ^0.8.11
- **License:** MIT (SPDX-License-Identifier: MIT)
- **Naming conventions:** 
  - Variables: camelCase
  - Constants: ALL_CAPS
- **Formatting:**
  - 4 spaces indentation
  - Order: license, pragma, imports, contract
- **Optimizations:**
  - Use unchecked blocks for counter increments: `unchecked {++i;}`
  - Prefer custom errors over require strings
- **Assembly:** Used for performance-critical operations
- **Testing:** Hardhat with Waffle/Mocha using describe/it pattern
- **Documentation:** Use minimal inline comments for complex logic