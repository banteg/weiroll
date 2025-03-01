# Weiroll Python Documentation

Welcome to the Weiroll Python SDK documentation. Weiroll is a language for writing programs that take advantage of the EVM's unique capabilities, allowing for efficient execution of multiple operations in a single transaction.

## Table of Contents

- [Python SDK Overview](python_sdk.md) - Core components and usage
- [Examples](examples.md) - Practical examples for various use cases
- [Solidity Integration](solidity_integration.md) - How to integrate with Solidity contracts

## What is Weiroll?

Weiroll is a simple and efficient operation-chaining/scripting language for the Ethereum Virtual Machine (EVM). It allows you to:

1. **Create sequences of contract calls** that execute atomically in a single transaction
2. **Build complex DeFi strategies** with interdependent steps
3. **Optimize gas usage** by batching operations
4. **Visualize dependencies** between operations
5. **Decode and analyze** execution plans

## Quick Start

```python
from weiroll import Contract, Planner
from ape import Contract as ApeContract

# Create contract wrappers
token = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))
vault = Contract(ApeContract("0xd8063123BBA3B480569244AE66BFE72B6c84b00d"))

# User address
user = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

# Create a plan with dependent operations
planner = Planner()
balance = planner.add(token.balanceOf(user))
shares = planner.add(vault.deposit(balance, user))
planner.add(vault.redeem(shares, user, user))

# Visualize the plan
print(planner.show_tree())

# Generate encoded plan for execution
plan = planner.plan()
```

## Development

To set up the development environment:

```bash
# Clone the repository
git clone https://github.com/banteg/weiroll.git
cd weiroll

# Install dependencies
uv venv
source .venv/bin/activate
uv install -e .

# Run tests
uv run pytest tests/

# Format code
uv run ruff format .
```

## License

MIT License