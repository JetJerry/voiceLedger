"""
VoiceLedger Payment Provider Exception Hierarchy.

Establishes a clean, provider-independent exception hierarchy for all payment
gateway operations, isolating the core domain from vendor-specific error codes.
"""
from typing import Optional, Any


class ProviderError(Exception):
    """
    Base exception for all payment provider operations.
    Captures provider name and optional raw gateway response for audit/troubleshooting.
    """
    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        raw_response: Optional[Any] = None,
        error_code: Optional[str] = None,
    ):
        self.message = message
        self.provider = provider
        self.raw_response = raw_response
        self.error_code = error_code
        super().__init__(message)


class ProviderUnavailableError(ProviderError):
    """
    Raised when the payment provider gateway is unreachable, connection timed out,
    or returning transient HTTP 5xx responses.
    """
    pass


class ProviderAuthenticationError(ProviderError):
    """
    Raised when provider API credentials, merchant keys, or webhook signatures
    fail authentication or authorization.
    """
    pass


class ProviderResourceNotFoundError(ProviderError):
    """
    Raised when a queried entity (e.g. payment ID, order ID, refund) does not exist
    at the upstream provider.
    """
    pass


class ProviderValidationError(ProviderError):
    """
    Raised when request parameters, currency, amount, or payload structures fail
    provider validation checks.
    """
    pass
