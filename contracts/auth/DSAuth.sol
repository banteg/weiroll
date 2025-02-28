// SPDX-License-Identifier: MIT

pragma solidity ^0.8.11;

/// @title DSAuth - Authorization pattern from Dappsys
/// @dev Based on ds-auth: https://github.com/dapphub/ds-auth

abstract contract DSAuthority {
    function canCall(
        address src, address dst, bytes4 sig
    ) public view virtual returns (bool);
}

contract DSAuthEvents {
    event LogSetAuthority(address indexed authority);
    event LogSetOwner(address indexed owner);
}

contract DSAuth is DSAuthEvents {
    address public owner;
    DSAuthority public authority;

    constructor() {
        owner = msg.sender;
        emit LogSetOwner(msg.sender);
    }

    function setOwner(address owner_) public auth {
        owner = owner_;
        emit LogSetOwner(owner);
    }

    function setAuthority(DSAuthority authority_) public auth {
        authority = authority_;
        emit LogSetAuthority(address(authority));
    }

    modifier auth {
        require(isAuthorized(msg.sender, msg.sig), "ds-auth-unauthorized");
        _;
    }

    function isAuthorized(address src, bytes4 sig) internal view returns (bool) {
        if (src == owner) {
            return true;
        } else if (address(authority) == address(0)) {
            return false;
        } else {
            return authority.canCall(src, address(this), sig);
        }
    }
}