# Weiroll Python SDK Documentation

This directory contains comprehensive documentation for the Weiroll Python SDK.

## Table of Contents

### Core Documentation

- [Index](index.md) - Overview and quick start guide
- [Python SDK](python_sdk.md) - Core components and API reference
- [Examples](examples.md) - Practical examples for various use cases
- [Solidity Integration](solidity_integration.md) - How to integrate with Solidity contracts

### Conceptual Documentation

- [Concepts](CONCEPTS.md) - Core concepts and architecture of Weiroll
- [SDK Usage](SDK_USAGE.md) - Detailed usage guide with code examples

## What's New in This Version

The documentation has been updated to reflect significant changes in the Weiroll Python SDK:

1. **Exclusive Ape Support**: The SDK now exclusively supports [Ape](https://github.com/ApeWorX/ape) contracts (Web3.py support has been removed)

2. **Enhanced Plan Visualization**: Improved tree visualization with better formatting and data flow representation

3. **Advanced Plan Decoding**: More detailed decoding capabilities with human-readable function signatures

4. **Plan Reconstruction**: Ability to convert decoded plans back to Planner objects

5. **Simplified API**: More consistent and intuitive interfaces throughout the library

## Quick Reference

```python
from weiroll import Contract, Planner
from ape import Contract as ApeContract

# Create contract wrapper
token = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))

# Create planner and add operations
planner = Planner()
planner.add(token.transfer("0x0987654321098765432109876543210987654321", 100 * 10**18))

# Visualize and generate plan
print(planner.show_tree())
plan = planner.plan()
```

## Development

```bash
# Run tests
uv run pytest tests/

# Format code
uv run ruff format .

# Check code style
uv run ruff check .
```