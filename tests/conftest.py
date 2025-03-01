import ape
import pytest
from ape import Contract as ApeContract
from ape.contracts import ContractContainer
from ethpm_types import ContractType


@pytest.fixture
def ape_dai():
    return ape.Contract("0x6B175474E89094C44Da98b954EedeAC495271d0F")


@pytest.fixture
def ape_weth():
    return ape.Contract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")


@pytest.fixture
def ape_uniswap():
    return ape.Contract("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")


@pytest.fixture
def ape_farm():
    return ape.Contract("0x6d225e974fa404d25ffb84ed6e242ffa18ef6430")


@pytest.fixture
def dev():
    return ape.accounts.test_accounts[0]


@pytest.fixture
def recipient():
    return ape.accounts.test_accounts[1]


# Create fixtures for custom contract types used in tests


@pytest.fixture
def math_contract():
    """Math contract with add function"""
    address = "0x1234567890123456789012345678901234567890"
    abi = [
        {
            "type": "function",
            "name": "add",
            "inputs": [{"type": "uint256"}, {"type": "uint256"}],
            "outputs": [{"type": "uint256"}],
        }
    ]
    return create_ape_contract(address, abi)


@pytest.fixture
def events_contract():
    """Events contract with logging functions"""
    address = "0x2345678901234567890123456789012345678901"
    abi = [
        {"type": "function", "name": "logUint", "inputs": [{"type": "uint256"}], "outputs": []},
        {"type": "function", "name": "logString", "inputs": [{"type": "string"}], "outputs": []},
    ]
    return create_ape_contract(address, abi)


@pytest.fixture
def strings_contract():
    """Strings library contract"""
    address = "0x1234567890123456789012345678901234567890"
    abi = [
        {
            "type": "function",
            "name": "strcat",
            "inputs": [{"type": "string"}, {"type": "string"}],
            "outputs": [{"type": "string"}],
        },
        {"type": "function", "name": "strlen", "inputs": [{"type": "string"}], "outputs": [{"type": "uint256"}]},
    ]
    return create_ape_contract(address, abi)


@pytest.fixture
def payable_contract():
    """Contract with payable functions"""
    address = "0x3456789012345678901234567890123456789012"
    abi = [
        {"type": "function", "name": "pay", "inputs": [], "outputs": [], "stateMutability": "payable"},
        {"type": "function", "name": "balance", "inputs": [], "outputs": [{"type": "uint256"}]},
    ]
    return create_ape_contract(address, abi)


@pytest.fixture
def multi_return_contract():
    """Contract that returns multiple values"""
    address = "0x1234567890123456789012345678901234567890"
    abi = [
        {"type": "function", "name": "intTuple", "inputs": [], "outputs": [{"type": "uint256"}, {"type": "uint256"}]},
        {"type": "function", "name": "tupleConsumer", "inputs": [{"type": "uint256"}], "outputs": []},
    ]
    return create_ape_contract(address, abi)


@pytest.fixture
def tupler_contract():
    """Contract that works with tuples"""
    address = "0x2345678901234567890123456789012345678901"
    abi = [
        {
            "type": "function",
            "name": "extractElement",
            "inputs": [
                {"type": "tuple", "components": [{"type": "uint256"}, {"type": "uint256"}]},
                {"type": "uint256"},  # index to extract
            ],
            "outputs": [{"type": "uint256"}],
        }
    ]
    return create_ape_contract(address, abi)


@pytest.fixture
def array_test_contract():
    """Contract with functions that work with arrays"""
    address = "0x1234567890123456789012345678901234567890"
    abi = [
        {
            "type": "function",
            "name": "swapExactTokensForTokens",
            "inputs": [
                {"name": "amountIn", "type": "uint256"},
                {"name": "amountOutMin", "type": "uint256"},
                {"name": "path", "type": "address[]"},  # Array of addresses
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"},
            ],
            "outputs": [{"name": "amounts", "type": "uint256[]"}],
            "stateMutability": "nonpayable",
        }
    ]
    return create_ape_contract(address, abi)


@pytest.fixture
def simple_contract():
    """Contract with a basic function"""
    address = "0x1234567890123456789012345678901234567890"
    abi = [
        {
            "type": "function",
            "name": "add",
            "inputs": [{"type": "uint256"}, {"type": "uint256"}],
            "outputs": [{"type": "uint256"}],
        }
    ]
    return create_ape_contract(address, abi)


@pytest.fixture
def multi_function_contract():
    """Contract with multiple functions"""
    address = "0x1234567890123456789012345678901234567890"
    abi = [
        {
            "type": "function",
            "name": "add",
            "inputs": [{"type": "uint256"}, {"type": "uint256"}],
            "outputs": [{"type": "uint256"}],
        },
        {
            "type": "function",
            "name": "multiply",
            "inputs": [{"type": "uint256"}, {"type": "uint256"}],
            "outputs": [{"type": "uint256"}],
        },
    ]
    return create_ape_contract(address, abi)


@pytest.fixture
def deposit_contract():
    """Contract with a payable function"""
    address = "0x1234567890123456789012345678901234567890"
    abi = [{"type": "function", "name": "deposit", "inputs": [], "outputs": [], "stateMutability": "payable"}]
    return create_ape_contract(address, abi)


@pytest.fixture
def executor_contract():
    """Contract with functions for executing subplans"""
    address = "0x3456789012345678901234567890123456789012"
    abi = [
        {
            "type": "function",
            "name": "execute",
            "inputs": [
                {"name": "commands", "type": "bytes32[]"}, 
                {"name": "state", "type": "bytes[]"}
            ],
            "outputs": [{"name": "newState", "type": "bytes[]"}],
        },
        {
            "type": "function",
            "name": "processState",
            "inputs": [
                {"name": "state", "type": "bytes[]"}
            ],
            "outputs": [{"name": "newState", "type": "bytes[]"}],
        },
    ]
    return create_ape_contract(address, abi)


def create_ape_contract(address, abi):
    """Create an Ape contract with custom ABI"""
    # Create a ContractType with the given ABI 
    contract_type = ContractType(abi=abi, contractName="TestContract")

    # Create a ContractContainer with the contract type
    container = ContractContainer(contract_type=contract_type)

    # Return a contract instance at the given address
    return container.at(address)
