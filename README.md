# Weiroll

Weiroll is a language for writing programs that take advantage of the EVM's unique capabilities, allowing for efficient execution of multiple operations in a single transaction.

The Python SDK provides a simple and efficient way to create operation chains, build complex DeFi strategies, and execute them on-chain.

## Features

- **Contract Integration**: Seamless integration with Ape contracts
- **Command Execution**: Create and execute sequences of contract calls
- **Plan Visualization**: Display plans as dependency trees with detailed formatting
- **Plan Decoding**: Decode encoded plans with enhanced visualization
- **Plan Reconstruction**: Recreate Planner objects from decoded plans
- **Value Formatting**: Format large numbers and token amounts for readability

## Installation

```bash
pip install weiroll  # FIXME package name tbd
# or
uv add weiroll
```

## Quick Start

```python
from weiroll import Contract, Planner
from ape import Contract as ApeContract

# Create contract wrappers
token = Contract(ApeContract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))
vault = Contract(ApeContract("0xd8063123BBA3B480569244AE66BFE72B6c84b00d"))

# Create a plan
with Planner() as planner:
    # Create a sequence of operations with data dependencies
    balance = planner.add(token.balanceOf("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"))
    shares = planner.add(vault.deposit(balance, "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"))
    planner.add(vault.redeem(shares, "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"))
    
    # Display the plan as a tree
    print(planner.show_tree())
    
    # Generate the encoded plan for execution
    plan = planner.plan()
```

Here is an example tree visualization:
```
Command 0: balanceOf(address holder) -> uint256 @ 0x6B175474E89094C44Da98b954EedeAC495271d0F [CALL]
  ├─ Input 0: State[0] = 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
  └─ Output: State[1] (→ Command 1)

Command 1: deposit(uint256 assets, address receiver) -> uint256 @ 0xd8063123BBA3B480569244AE66BFE72B6c84b00d [CALL]
  ├─ Input 0: State[1] (from Command 0 output)
  ├─ Input 1: State[0] = 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
  └─ Output: State[2] (→ Command 2)

Command 2: redeem(uint256 shares, address receiver, address owner) -> uint256 @ 0xd8063123BBA3B480569244AE66BFE72B6c84b00d [CALL]
  ├─ Input 0: State[2] (from Command 1 output)
  ├─ Input 1: State[0] = 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
  ├─ Input 2: State[0] = 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
  └─ Output: State[3] (unused)
```

## Overview of the VM

Under the hood, the Weiroll VM executes a list of commands from start to finish. Each command is encoded as a `bytes32` value that represents a single operation for the VM to perform.

## Command structure

Each command is a `bytes32` containing the following fields (MSB first):

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
┌───────┬─┬───────────┬─┬───────────────────────────────────────┐
│  sel  │f│    in     │o│              target                   │
└───────┴─┴───────────┴─┴───────────────────────────────────────┘
```

 - `sel` is the 4-byte function selector to call
 - `f` is a flags byte that specifies calltype, and whether this is an extended command
 - `in` is an array of 1-byte argument specifications described below, for the input arguments
 - `o` is the 1-byte argument specification described below, for the return value
 - `target` is the address to call

### Flags

The 1-byte flags argument `f` has the following field structure:

```
  0   1   2   3   4   5   6   7
┌───┬───┬───────────────┬────────┐
│tup│ext│   reserved    │calltype│
└───┴───┴───────────────┴────────┘
```

If `tup` is set, the return for this command will be assigned to the state slot directly, without any attempt at processing or decoding.

The `ext` bit signifies that this is an extended command, and as such the next command should be treated as 32-byte `in` list of indices, rather than the 6-byte list in the packed command struct.

Bits 2-5 are reserved for future use.

The 2-bit `calltype` is treated as a `uint16` that specifies the type of call. The value that selects the corresponding call type is described in the table below:

```
   ┌──────┬───────────────────┐
   │ 0x00 │  DELEGATECALL     │
   ├──────┼───────────────────┤
   │ 0x01 │  CALL             │
   ├──────┼───────────────────┤
   │ 0x02 │  STATICCALL       │
   ├──────┼───────────────────┤
   │ 0x03 │  CALL with value  │
   └──────┴───────────────────┘
```

If `calltype` equals `CALL with value`, then the first argument in the `in` input list is taken to be the amount of ETH that will be supplied to the call, and the rest of the arguments are the arguments to the called function, both processed as described below.

### Input/output list (in/o) format


Each 1-byte argument specifier value describes how each input or output argument should be treated, and has the following fields (MSB first):

```
  0   1   2   3   4   5   6   7
┌───┬───────────────────────────┐
│var│           idx             │
└───┴───────────────────────────┘
```

The `var` flag indicates if the indexed value should be treated as fixed- or variable-length. If `var == 0b0`, the argument is fixed-length, and `idx`, is treated as the index into the state array at which the value is located. The state entry at that index must be exactly 32 bytes long.

If `var == 0b10000000`, the indexed value is treated as variable-length, and `idx` is treated as the index into the state array at which the value is located. The value must be a multiple of 32 bytes long.

The vm handles the "head" part of ABI-encoding and decoding for variable-length values, so the state elements for these should be the "tail" part of the encoding - for example, a string encodes as a 32 byte length field followed by the string data, padded to a 32-byte boundary, and an array of `uint`s is a 32 byte count followed by the concatenation of all the uints.

There are two special values `idx` can equal to which modify the encoder behavior, specified in the below table:

```
   ┌──────┬───────────────────┐
   │ 0xfe │  USE_STATE        │
   ├──────┼───────────────────┤
   │ 0xff │  END_OF_ARGS      │
   └──────┴───────────────────┘
```

If `idx` equals `USE_STATE` inside of an `in` list byte, then the parameter at that position is constructed by feeding the entire state array into `abi.encode` and passing it to the function as a single argument. If it's specified as part of the `o` output target, then the output of that command is written directly to the state instead via `abi.decode`.

The special `idx` value `END_OF_ARGS` indicates the end of the parameter list, no encoding action will be taken, and all further bytes in the list will be ignored. If the first byte in the input list is `END_OF_ARGS`, then the function will be called with no parameters. If `o` equals `END_OF_ARGS`, then it specifies that the command's return should be ignored.

### Examples

#### Fixed length input and output values

Suppose you want to construct a command to call the following function:

```solidity
function add(uint a, uint b) external returns (uint);
```

`sel` should be set to the function selector for this function, and `target` to the address of the deployed contract containing this function.

`f` should specify this is a delegatecall (`0x00`), `in` needs to specify two input values of fixed length (`var == 0b0`). The remaining four input parameters are unneeded and should be set to `0xff`. Supposing the two inputs should come from state elements 0 and 1, the encoded `in` data is thus `0x000001ffffffff`.

`out` needs to specify that the output value is fixed length (`var == 0b0`). Supposing the output should be written to state element 2, the encoded `out` data is thus `0x02`.

#### Variable length input and output values

Suppose you want to construct a command to call the following function:

```solidity
function concatBytes32(bytes32[] inputs) external returns (bytes);
```

`sel` should be set to the function selector for this function, and `target` to the address of the deployed contract containing this function.

`f` should specify this is a delegatecall (`0x00`), `in` needs to specify one input value of variable length (`var == 0b10000000`), that is an array of 32-byte words (`idx == 0b1000000`). The remaining five input parameters are unneeded and should be set to `0xff`. Supposing the input comes from state element 0, the encoded `in` data is thus `0x00c0ffffffffff`.

`out` needs to specify that the output value is variable length (`var == 0b10000000`). Supposing the output value should be written to state element 1, the encoded `out` data is thus `0x81`.

## Command execution

Command execution takes place in 4 stages:

 1. Command decoding
 2. Input encoding
 3. Call
 4. Output decoding

Command decoding is straightforward and described above in "Command structure".

### Input encoding

Input arguments must be collected from the state and assembled into a valid ABI-encoded string to be passed to the function being called. The vm allocates an array large enough to store the input data. Observing the `var` flag on each input argument specifier, it then either copies the value directly from the relevant state index to the input array, or writes out a pointer to the value, and appends the value to the array. The result is a valid ABI-encoded byte string. The function selector is inserted at the beginning of the input data in this stage.

### Call

Next, the vm calls the target contract with the encoded input data. A `delegatecall` is normally used for vm library contracts, meaning the execution takes place in the vm's context rather than the contract's own, and a normal `call` is used for calling out to external contracts directly (like to an `ERC20.transfer` function). The intention is that users of the executor will themselves `delegatecall` it, meaning that all operations take place in the user's contract's context, or will seem to come directly from a user's contract address for external calls.

### Output decoding

Finally, the return data is decoded by following the output argument specifier, in the same fashion as the 'input encoding' stage. Only one return value is supported.
