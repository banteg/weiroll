// SPDX-License-Identifier: MIT

pragma solidity ^0.8.11;

import "./AuthVM.sol";

/**
 * @title AuthVMFactory
 * @notice Factory for deploying user-owned Weiroll VM instances
 * @dev Deploys new AuthVM instances with the caller as the owner
 */
contract AuthVMFactory {
    event VMCreated(address indexed owner, address indexed vm);
    
    /**
     * @notice Mapping of user address to their deployed VM
     */
    mapping(address => address) public userVMs;
    
    /**
     * @notice Check if a user has already deployed a VM
     * @param user Address to check
     * @return true if the user has deployed a VM
     */
    function hasVM(address user) external view returns (bool) {
        return userVMs[user] != address(0);
    }
    
    /**
     * @notice Get a user's VM address
     * @param user Address to lookup
     * @return VM address (or zero address if none)
     */
    function getVM(address user) external view returns (address) {
        return userVMs[user];
    }
    
    /**
     * @notice Create a new VM for the sender
     * @dev Will revert if the sender already has a VM
     * @return vm Address of the newly created VM
     */
    function createVM() external returns (address vm) {
        require(userVMs[msg.sender] == address(0), "VM already exists");
        
        // Deploy new VM with caller as owner
        AuthVM newVM = new AuthVM();
        vm = address(newVM);
        
        // Store mapping
        userVMs[msg.sender] = vm;
        
        emit VMCreated(msg.sender, vm);
    }
    
    /**
     * @notice Create a VM or get existing one
     * @dev Returns existing VM if one exists, otherwise creates new one
     * @return vm Address of the VM
     */
    function getOrCreateVM() external returns (address vm) {
        vm = userVMs[msg.sender];
        
        if (vm == address(0)) {
            // No VM exists, create new one
            AuthVM newVM = new AuthVM();
            vm = address(newVM);
            
            userVMs[msg.sender] = vm;
            
            emit VMCreated(msg.sender, vm);
        }
    }
}