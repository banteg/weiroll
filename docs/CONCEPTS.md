# Weiroll: Core Concepts and Architecture

## Introduction

Weiroll is a simple yet powerful operation-chaining/scripting language designed specifically for the Ethereum Virtual Machine (EVM). It enables the sequential execution of contract calls in a single transaction, with the ability to use the output from one operation as an input to subsequent operations.

This document explains how Weiroll works, its core architecture, and the concepts it introduces.

## Core Architecture

Weiroll operates through a simple Virtual Machine (VM) contract that interprets and executes a series of commands. The VM takes two main inputs:

1. **Commands Array** (`bytes32[]`): A list of encoded instructions specifying what functions to call
2. **State Array** (`bytes[]`): A dynamic array that stores input values and receives output values

The VM executes each command in sequence, using and modifying the state array as it goes.

### Command Structure

Each command is a 32-byte value that contains all the information needed to execute a specific function call:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
┌───────┬─┬───────────┬─┬───────────────────────────────────────┐
│  sel  │f│    in     │o│              target                   │
└───────┴─┴───────────┴─┴───────────────────────────────────────┘
```

- `sel`: 4-byte function selector 
- `f`: 1-byte flags specifying call type and other options
- `in`: 6 bytes of input argument specifications
- `o`: 1-byte output argument specification
- `target`: 20-byte address of the contract to call

For functions with more than 6 inputs, Weiroll uses an "extended command" format where a second command word contains the additional input specifications.

### State and Data Flow

The state array is the mechanism through which data flows between operations. Each element in the state array is a `bytes` value. State slots can contain:

1. **Literal values**: Constant values provided as inputs
2. **Return values**: Output from previous operations
3. **Placeholder values**: Reserved spaces for future outputs

Each command specifies which slots to use for inputs and which slot to write the output to, enabling a pipeline of operations where data flows naturally through the sequence.

## Key Concepts

### 1. Call Types

Weiroll supports four different call types:

- **DELEGATECALL**: Executes code in the context of the calling contract, preserving `msg.sender` and storage access
- **CALL**: Normal external call to another contract, where `msg.sender` becomes the VM's address
- **STATICCALL**: Like CALL but disallows state modifications
- **CALL with value**: Like CALL but also sends ETH with the call

The call type is specified in the flags byte of each command.

### 2. Argument Types and Encoding

Commands can operate on two types of arguments:

- **Fixed-length**: 32-byte values like `uint256`, `address`, etc.
- **Dynamic-length**: Variable-sized data like `string`, `bytes`, arrays, etc.

The argument specification in each command indicates:
- Which state slot to use for the argument
- Whether the argument is fixed or dynamic length
- Special operations like using the entire state array as an argument

### 3. Operation Chaining

The most powerful concept in Weiroll is operation chaining - using the output of one function call as the input to another. This enables complex multi-step operations to be executed atomically in a single transaction.

Example flow:
1. Get token balance from Token A
2. Use that balance to swap for Token B
3. Use resulting Token B amount to provide liquidity
4. Use LP tokens to stake in a rewards contract

All in a single transaction, without needing to know intermediate values in advance.

### 4. Libraries vs. Contracts

Weiroll makes a distinction between:

- **Libraries**: Functions called via DELEGATECALL that operate in the VM's context
- **Contracts**: External contracts called via normal CALL that maintain their own context

Libraries are ideal for stateless utilities and operations that need to access or modify the VM's state directly. External contracts are used for interacting with existing protocols and external state.

### 5. Value Passing

For payable functions, Weiroll supports sending ETH along with function calls. This can be:

- A fixed amount specified when planning the transaction
- A dynamic amount determined by a previous operation

This enables complex value-carrying operations like flash loans, atomic swaps, and liquidity operations.

## SDK Architecture

While the on-chain VM is simple, the SDK provides a powerful planning interface that:

1. **Abstracts Contract Interfaces**: Wraps contract interfaces for easy function calls
2. **Manages State Allocation**: Intelligently assigns state slots for values
3. **Optimizes Storage**: Deduplicates identical literals and reuses freed slots
4. **Encodes Commands**: Generates properly encoded commands for the VM
5. **Provides Type Safety**: Ensures type compatibility between operations

## Advanced Features

### Subplans

The full Weiroll JavaScript SDK supports subplans, which allow for nested VM instances. This is useful for:

- Flash loan callbacks
- Delegated execution
- Conditional execution based on runtime values

Subplans can have their own commands and state but can share return values with the parent plan.

### Tuple Returns

Some functions return multiple values (tuples). Weiroll handles these by:

1. Capturing the entire return value as a raw bytes object
2. Using special tuple extraction functions to access individual elements

This enables working with complex return types like those from Uniswap, Compound, or custom data structures.

## Performance Considerations

Weiroll is designed to be gas-efficient:

- Commands are densely packed to minimize storage costs
- State management reuses slots when possible
- Input encoding is optimized for common patterns
- The VM itself is simple and has low overhead

However, there are some limitations:

- Each command requires reading and interpreting bytecode on-chain
- State manipulation has associated gas costs
- Dynamic arguments incur additional encoding/decoding overhead

## Security Model

The Weiroll VM executes exactly what it's given - there are no built-in security checks beyond what the EVM itself provides. This means:

1. The security of a Weiroll script depends on the security of the contracts it calls
2. The party constructing the commands has complete control over what will be executed
3. Users should only execute commands from trusted sources or verify commands before execution

## Use Cases

Weiroll is particularly well-suited for:

1. **DeFi Automation**: Complex multi-step trading, lending, and liquidity operations
2. **Smart Contract Composability**: Chaining calls across multiple protocols
3. **Meta-Transactions**: Executing operations on behalf of users
4. **Gas Optimization**: Reducing multi-transaction workflows to a single transaction
5. **Conditional Execution**: Executing different paths based on runtime conditions

## Implementation Approaches

There are multiple ways to use Weiroll in a project:

1. **Direct VM Instance**: Deploy the VM and execute commands directly
2. **Contract Integration**: Integrate the VM into an existing contract
3. **Proxy Execution**: Use a proxy contract that delegates to the VM
4. **SDK Integration**: Build the VM execution into a custom application

Each approach has different trade-offs in terms of flexibility, security, and gas efficiency.

## Conclusion

Weiroll represents a powerful pattern for operation chaining on Ethereum. It combines the simplicity of a minimal VM with the flexibility to execute arbitrary sequences of operations. By focusing on the core concept of data flow between operations, it enables complex workflows that would otherwise require multiple transactions or complex custom contract development.

The combination of the on-chain VM and the planning SDK creates a powerful tool for Ethereum developers looking to build more efficient and flexible applications.