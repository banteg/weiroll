import pytest
from unittest.mock import MagicMock
from weiroll import Contract, CallType
from weiroll.exceptions import InvalidContractError, EmptyABIError
from dataclasses import dataclass


def test_web3py_contract_adapter():
    """Test that web3.py contracts can be properly wrapped."""
    # Create mock web3.py contract
    mock_web3_contract = MagicMock()
    mock_web3_contract.address = "0x1234567890123456789012345678901234567890"
    mock_web3_contract.abi = [
        {
            "type": "function",
            "name": "transfer",
            "inputs": [
                {"type": "address"},
                {"type": "uint256"}
            ],
            "outputs": [
                {"type": "bool"}
            ]
        }
    ]
    
    # Create Weiroll contract
    weiroll_contract = Contract.create_contract(mock_web3_contract)
    
    # Verify contract properties
    assert weiroll_contract.address == "0x1234567890123456789012345678901234567890"
    assert "transfer" in weiroll_contract.functions
    assert weiroll_contract.call_type == CallType.CALL
    
    # Create a library contract
    library_contract = Contract.create_library(mock_web3_contract)
    assert library_contract.call_type == CallType.DELEGATECALL


def test_ape_contract_adapter(mocker):
    """Test that ape contracts can be properly wrapped."""
    # Create mock ABI
    mock_abi = [
        {
            "type": "function",
            "name": "balanceOf",
            "inputs": [
                {"type": "address"}
            ],
            "outputs": [
                {"type": "uint256"}
            ]
        }
    ]
    
    # Mock the Contract class _process_abi method so we don't actually call it
    mocker.patch.object(Contract, '_process_abi')
    
    # Create mock contract_type with model_dump method
    mock_contract_type = MagicMock()
    mock_contract_type.model_dump.return_value = {'abi': mock_abi}
    
    # Create mock ape contract
    mock_ape_contract = MagicMock()
    mock_ape_contract.address = "0x1234567890123456789012345678901234567890"
    mock_ape_contract.contract_type = mock_contract_type
    
    # Create Weiroll contract
    weiroll_contract = Contract.create_contract(mock_ape_contract)
    
    # Verify contract properties
    assert weiroll_contract.address == "0x1234567890123456789012345678901234567890"
    # We mocked _process_abi, so functions won't be populated
    assert weiroll_contract.call_type == CallType.CALL
    
    # Create a library contract
    library_contract = Contract.create_library(mock_ape_contract)
    assert library_contract.call_type == CallType.DELEGATECALL


def test_unsupported_contract_type():
    """Test that unsupported contract types raise appropriate errors."""
    # Create a simple object with just an address (no abi or contract_type)
    class UnsupportedContract:
        def __init__(self):
            self.address = "0x1234567890123456789012345678901234567890"
    
    unsupported_obj = UnsupportedContract()
    
    # Should raise InvalidContractError for missing both abi and contract_type
    with pytest.raises(InvalidContractError, match="Unsupported contract object type"):
        Contract.create_contract(unsupported_obj)
        
    # Create a contract_type that doesn't have proper ABI access methods
    class ContractTypeWithoutAbi:
        pass
        
    class IncompleteContract:
        def __init__(self):
            self.address = "0x1234567890123456789012345678901234567890"
            self.contract_type = ContractTypeWithoutAbi()
    
    incomplete_obj = IncompleteContract()
    
    # Should raise InvalidContractError for unusable contract_type
    with pytest.raises(InvalidContractError, match="Could not get valid ABI from contract_type"):
        Contract.create_contract(incomplete_obj)


def test_empty_abi_error():
    """Test that empty ABIs raise appropriate errors."""
    # Create a contract with empty ABI
    mock_contract = MagicMock()
    mock_contract.address = "0x1234567890123456789012345678901234567890"
    mock_contract.abi = []
    
    # Should raise EmptyABIError for empty ABI
    with pytest.raises(EmptyABIError, match="Contract ABI cannot be empty"):
        Contract.create_contract(mock_contract)
    
    # Create a contract with None ABI
    none_abi_contract = MagicMock()
    none_abi_contract.address = "0x1234567890123456789012345678901234567890"
    none_abi_contract.abi = None
    
    # Test init directly
    with pytest.raises(EmptyABIError, match="Contract ABI cannot be empty or None"):
        Contract(none_abi_contract.address, none_abi_contract.abi)