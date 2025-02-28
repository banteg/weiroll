# Weiroll Development Guide

## Python SDK

### Overview
The Python SDK provides bindings to interact with the Weiroll VM. It allows creating plans, wrapping contracts, and generating command sequences to execute on-chain.

### Build Commands
- Run Python tests: `uv run pytest tests/`
- Run single test: `uv run pytest tests/test_file.py::test_name -v`

### Features
- **Contract adapters:** Support for both web3.py and ape contracts
- **Planner:** Build and serialize execution plans
- **Command generation:** Create command sequences for the VM
- **Exception handling:** Custom exceptions for robust error handling

### Example Usage
```python
from weiroll import Contract, Planner, CallType

# Create a contract wrapper
contract = Contract.createContract(web3_contract)  # For web3.py contracts
# OR
contract = Contract.createContract(ape_contract)   # For ape contracts

# Create a planner and add operations
planner = Planner()
planner.add(contract.someFunction(arg1, arg2))

# Get the serialized plan
plan = planner.plan()
```

### Testing
- **Test framework:** pytest
- **Mocking:** unittest.mock for contract mocks
- **Integration tests:** Tests for web3.py and ape integrations

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