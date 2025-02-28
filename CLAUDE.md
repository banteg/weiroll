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
   from weiroll import Contract
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

### Testing
- **Command**: `uv run pytest tests/`
- **Test framework:** pytest
- **Mocking:** unittest.mock for contract mocks
- **Integration tests:** Tests for web3.py and ape integrations
- **Test data**: `tests/data/` directory contains example ABIs for testing

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