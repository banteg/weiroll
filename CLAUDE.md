# Weiroll Development Guide

CLAUDE DO NOT EDIT FILES MARKED "BUNNY VISION"

## Python SDK

### Overview
The Python SDK provides bindings to interact with the Weiroll VM. It allows creating plans, wrapping contracts, and generating command sequences to execute on-chain.

### Key Features
- **Command Execution:** Create and execute sequences of contract calls
- **Plan Visualization:** Display plans as trees with `planner.show_tree()`
- **Plan Decoding:** Decode encoded plans with enhanced visualization using `Decoder`
- **Value Formatting:** Format large numbers and token amounts for readability

### Build Commands
- Run Python tests: `uv run pytest tests/`
- Run single test: `uv run pytest tests/test_file.py::test_name -v`

### Contract Adapters
Weiroll provides adapters for different contract interfaces:

2. **Ape contracts**:
   ```python
   from ape import Contract as ApeContract
   from weiroll import Contract
   
   ape_contract = ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F")
   contract = Contract(ape_contract)
   ```

3. **Direct ABI**:
   ```python
   from weiroll import Contract
   contract = Contract(address, abi_list)
   ```

4. **With ethpm_types**:
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
```

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
  - Run all tests: `uv run ape test`
  - Run specific tests: `uv run ape test tests/test_file.py -v`
- **Test framework:** pytest with Ape's testing plugin
- **Fixtures:** Common contracts and accounts available in conftest.py
- **Integration tests:** Tests for both web3.py and ape contracts
- **Live contracts:** Tests use real mainnet contracts via forking

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