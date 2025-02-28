# Weiroll Development Guide

## Python SDK

### Overview
The Python SDK provides bindings to interact with the Weiroll VM. It allows creating plans, wrapping contracts, and generating command sequences to execute on-chain.

### Build Commands
- Run Python tests: `uv run pytest tests/`
- Run single test: `uv run pytest tests/test_file.py::test_name -v`

### Contract Adapters
Weiroll provides adapters for different contract interfaces:

1. **Web3.py contracts**:
   ```python
   from weiroll import Contract
   contract = Contract.createContract(web3_contract)
   ```

2. **Ape contracts**:
   ```python
   from ape import Contract as ApeContract
   from weiroll import Contract
   
   ape_contract = ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F")
   contract = Contract.createContract(ape_contract)
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

### Exception Handling
Custom exceptions available in `weiroll.exceptions`:

- `WeirollError`: Base exception for all Weiroll-related errors
- `InvalidContractError`: Raised when a contract object is invalid or unsupported
- `EmptyABIError`: Raised when a contract ABI is empty or None

### Full Example Usage
```python
from weiroll import Contract, Planner, CallType

# Create a contract wrapper
contract = Contract.createContract(web3_contract)  # For web3.py contracts
# OR
contract = Contract.createContract(ape_contract)   # For ape contracts

# Create a planner and add operations
planner = Planner()
recipient = "0x0987654321098765432109876543210987654321"
amount = 100 * 10**18  # 100 tokens
planner.add(contract.transfer(recipient, amount))

# Get the serialized plan
plan = planner.plan()
# Contains commands and state for VM execution
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