// SPDX-License-Identifier: MIT

pragma solidity ^0.8.11;

import "../AuthVM.sol";
import "../auth/DSAuth.sol";

/**
 * @title TestAuthority
 * @notice A simple implementation of DSAuthority for testing purposes
 */
contract TestAuthority is DSAuthority {
    mapping(address => mapping(address => mapping(bytes4 => bool))) public permissions;

    /**
     * @notice Set permission for a caller to call a specific function on a target
     * @param src Source address that will call
     * @param dst Target contract that will be called
     * @param sig Function signature that will be called
     * @param allowed Whether to allow or disallow the call
     */
    function setPermission(address src, address dst, bytes4 sig, bool allowed) external {
        permissions[src][dst][sig] = allowed;
    }

    /**
     * @notice Check if a caller can call a specific function on a target
     * @param src Source address that will call
     * @param dst Target contract that will be called
     * @param sig Function signature that will be called
     * @return Whether the call is allowed
     */
    function canCall(address src, address dst, bytes4 sig) public view override returns (bool) {
        return permissions[src][dst][sig];
    }
}

/**
 * @title TestAuthVM
 * @notice A testable version of AuthVM with extra helper functions
 */
contract TestAuthVM is AuthVM {
    /**
     * @notice Execute commands with the given msg.sender for testing
     * @param commands Array of encoded commands to execute
     * @param state Initial state array
     * @param sender The address to use as msg.sender
     * @return result Final state after execution
     */
    function testExecuteAs(bytes32[] calldata commands, bytes[] memory state, address sender) 
        external 
        returns (bytes[] memory result) 
    {
        require(isAuthorized(sender, this.execute.selector), "Not authorized");
        return _execute(commands, state);
    }
}