"""
VoiceLedger Payment Provider Abstraction Layer.
"""
from backend.app.providers.base import (
    PaymentProvider,
    register_provider,
    get_provider,
)
from backend.app.providers.schemas import (
    NormalizedPayment,
    NormalizedPaymentEvent,
    PaymentMethodType,
)
from backend.app.providers.exceptions import (
    ProviderError,
    ProviderUnavailableError,
    ProviderAuthenticationError,
    ProviderResourceNotFoundError,
    ProviderValidationError,
)
from backend.app.providers.razorpay import RazorpayProvider, RazorpayClient

# Register authoritative default Razorpay provider instance
register_provider(RazorpayProvider())

__all__ = [
    "PaymentProvider",
    "register_provider",
    "get_provider",
    "NormalizedPayment",
    "NormalizedPaymentEvent",
    "PaymentMethodType",
    "ProviderError",
    "ProviderUnavailableError",
    "ProviderAuthenticationError",
    "ProviderResourceNotFoundError",
    "ProviderValidationError",
    "RazorpayProvider",
    "RazorpayClient",
]
