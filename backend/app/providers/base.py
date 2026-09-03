"""
VoiceLedger Abstract Payment Provider Contract.

Defines the boundary between external payment gateways and VoiceLedger's core
financial ledger, idempotency engine, and webhook verification pipeline.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from backend.app.providers.schemas import NormalizedPayment, NormalizedPaymentEvent


class PaymentProvider(ABC):
    """
    Abstract Payment Provider Contract.

    Every payment gateway integration (Razorpay, future banks/providers) must
    implement this contract. Isolates VoiceLedger from gateway-specific SDKs,
    wire formats, and naming schemes.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Canonical identifier for this provider (e.g. 'RAZORPAY').
        Used for provider-scoped database queries, idempotency keys, and audit logs.
        """
        pass

    @abstractmethod
    def fetch_payment(self, provider_payment_id: str) -> NormalizedPayment:
        """
        Retrieve payment details from the provider gateway by its transaction reference.

        Returns:
            NormalizedPayment: Authoritative, provider-independent payment record.

        Raises:
            ProviderResourceNotFoundError: When transaction ID is unknown to provider.
            ProviderUnavailableError: When provider network/API is down or timed out.
            ProviderAuthenticationError: When merchant credentials or API keys fail.
            ProviderValidationError: When input format is invalid.
        """
        pass

    @abstractmethod
    def verify_payment_status(self, provider_payment_id: str) -> NormalizedPayment:
        """
        Verify the latest authoritative payment state directly with the upstream gateway.
        Guarantees that client-reported or device-reported success is never trusted blindly.
        """
        pass

    @abstractmethod
    def normalize_payment_payload(self, raw_payload: Dict[str, Any]) -> NormalizedPayment:
        """
        Translate a provider-specific raw payment dictionary into a canonical
        NormalizedPayment structure.
        """
        pass

    @abstractmethod
    def normalize_event_payload(
        self,
        raw_payload: Dict[str, Any],
        raw_payload_bytes: Optional[bytes] = None,
    ) -> NormalizedPaymentEvent:
        """
        Translate a provider-specific raw webhook/notification payload into a canonical
        NormalizedPaymentEvent structure for Level 1 idempotency processing.
        """
        pass


# Global provider registry mapping uppercase provider names to adapter instances
_PROVIDER_REGISTRY: Dict[str, PaymentProvider] = {}


def register_provider(provider: PaymentProvider) -> None:
    """Register a concrete PaymentProvider instance in the global registry."""
    _PROVIDER_REGISTRY[provider.provider_name.upper()] = provider


def get_provider(provider_name: str) -> PaymentProvider:
    """
    Retrieve a registered PaymentProvider adapter by name.

    Raises:
        ProviderResourceNotFoundError: If the provider is not registered.
    """
    from backend.app.providers.exceptions import ProviderResourceNotFoundError

    name = (provider_name or "").upper().strip()
    provider = _PROVIDER_REGISTRY.get(name)
    if not provider:
        raise ProviderResourceNotFoundError(
            f"Payment provider '{provider_name}' is not registered",
            provider=provider_name,
        )
    return provider
