// SPDX-License-Identifier: MIT

pragma solidity ^0.8.11;

import "./VM.sol";
import "./auth/DSAuth.sol";

/**
 * @title AuthVM
 * @notice A Weiroll VM implementation with auth protection
 * @dev Extends the VM with ds-auth pattern for access control
 */
contract AuthVM is VM, DSAuth {
    event Executed(bytes32[] commands, bytes[] initialState);
    
    /**
     * @notice Execute a series of commands with authorization check
     * @param commands Array of encoded commands to execute
     * @param state Initial state array
     * @return result Final state after execution
     */
    function execute(bytes32[] calldata commands, bytes[] memory state) 
        external 
        auth 
        returns (bytes[] memory result) 
    {
        emit Executed(commands, state);
        return _execute(commands, state);
    }
    
    /**
     * @notice Execute commands with value sent along with the transaction
     * @param commands Array of encoded commands to execute
     * @param state Initial state array
     * @return result Final state after execution
     */
    function executeWithValue(bytes32[] calldata commands, bytes[] memory state) 
        external 
        payable 
        auth 
        returns (bytes[] memory result) 
    {
        emit Executed(commands, state);
        return _execute(commands, state);
    }
}