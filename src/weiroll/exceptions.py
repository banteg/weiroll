"""Custom exceptions for the Weiroll Python SDK."""


class WeirollError(Exception):
    """Base exception for all Weiroll-related errors."""

    pass


class InvalidContractError(WeirollError):
    """Raised when a contract object is invalid or unsupported."""

    pass


class EmptyABIError(InvalidContractError):
    """Raised when a contract ABI is empty or None."""

    pass
