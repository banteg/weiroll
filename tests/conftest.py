import ape
import pytest


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
