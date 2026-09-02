"""
VoiceLedger Razorpay Webhook Verification.

Implements cryptographically rigorous, timing-safe HMAC-SHA256 signature verification
over exact raw request body bytes, strictly isolating Razorpay webhook authentication.
"""
import hashlib
import hmac
import json
from typing import Dict, Any, Optional

from backend.app.config import settings
from backend.app.core.logging import logger
from backend.app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderValidationError,
)


class RazorpayWebhookVerifier:
    """
    Cryptographic verifier for inbound Razorpay webhooks.

    Invariants:
    - Uses exact raw body bytes (UTF-8) as HMAC message.
    - Never parses or re-serializes JSON before signature check.
    - Uses hmac.compare_digest for constant-time comparison against timing attacks.
    - Secrets are never logged or returned in error messages.
    """

    def __init__(self, webhook_secret: Optional[str] = None):
        self._secret = webhook_secret

    def _get_secret(self, explicit_secret: Optional[str] = None) -> str:
        """Resolve and validate webhook secret without leaking it."""
        if explicit_secret is not None:
            secret = explicit_secret.strip()
        elif self._secret is not None:
            secret = self._secret.strip()
        else:
            secret = settings.RAZORPAY_WEBHOOK_SECRET.strip()

        if not secret:
            raise ProviderAuthenticationError(
                "Razorpay webhook secret is not configured",
                provider="RAZORPAY",
            )
        return secret

    def compute_signature(self, raw_body: bytes, secret: Optional[str] = None) -> str:
        """
        Compute HMAC-SHA256 hex digest for given raw body bytes.
        """
        if not isinstance(raw_body, bytes):
            if isinstance(raw_body, str):
                raw_body = raw_body.encode("utf-8")
            else:
                raise ProviderValidationError(
                    "Raw webhook body must be bytes or string",
                    provider="RAZORPAY",
                )

        sec = self._get_secret(secret)
        return hmac.new(
            key=sec.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

    def verify_signature(
        self,
        raw_body: bytes,
        signature: Optional[str],
        secret: Optional[str] = None,
    ) -> bool:
        """
        Verify incoming Razorpay webhook signature.

        Args:
            raw_body: Exact raw request payload bytes.
            signature: Value of X-Razorpay-Signature header.
            secret: Optional override secret; falls back to configured secret.

        Returns:
            bool: True if signature matches cryptographically; False otherwise.
        """
        if not signature or not isinstance(signature, str) or not signature.strip():
            logger.warning("Razorpay webhook rejected: missing or empty signature header")
            return False

        if not isinstance(raw_body, (bytes, str)):
            logger.warning("Razorpay webhook rejected: invalid raw body type")
            return False

        try:
            expected_signature = self.compute_signature(raw_body, secret=secret)
        except ProviderAuthenticationError:
            raise
        except Exception as exc:
            logger.error("Unexpected error computing Razorpay signature: %s", exc)
            return False

        received_sig = signature.strip().lower()
        # Constant-time comparison prevents timing attacks (T2 threat model)
        matches = hmac.compare_digest(expected_signature.lower(), received_sig)
        if not matches:
            logger.warning("Razorpay webhook rejected: signature mismatch")
        return matches

    def verify_and_parse(
        self,
        raw_body: bytes,
        signature: Optional[str],
        secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify signature and parse JSON payload only upon cryptographic success.

        Raises:
            ProviderAuthenticationError: If signature is missing, empty, or invalid.
            ProviderValidationError: If body is malformed JSON.
        """
        if not self.verify_signature(raw_body, signature, secret=secret):
            raise ProviderAuthenticationError(
                "Invalid or missing Razorpay webhook signature",
                provider="RAZORPAY",
            )

        try:
            body_str = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else str(raw_body)
            payload = json.loads(body_str)
            if not isinstance(payload, dict):
                raise ValueError("Parsed JSON root is not an object")
            return payload
        except Exception as exc:
            logger.warning("Razorpay webhook payload JSON decoding failed: %s", exc)
            raise ProviderValidationError(
                "Malformed JSON in Razorpay webhook payload",
                provider="RAZORPAY",
            ) from exc

    def __repr__(self) -> str:
        sec = self._secret or settings.RAZORPAY_WEBHOOK_SECRET
        masked = f"{sec[:4]}..." if sec and len(sec) > 4 else "***"
        return f"<RazorpayWebhookVerifier secret='{masked}'>"


razorpay_webhook_verifier = RazorpayWebhookVerifier()
