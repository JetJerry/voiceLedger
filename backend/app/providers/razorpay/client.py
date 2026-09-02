"""
VoiceLedger Razorpay API Client.

A lightweight, isolated HTTP client for server-to-server communication with
Razorpay's REST API. Strictly maps network and HTTP errors to VoiceLedger's
provider-independent exception hierarchy and guarantees zero credential leakage.
"""
from typing import Dict, Any, Optional
import httpx

from backend.app.config import settings
from backend.app.core.logging import logger
from backend.app.core.security import sanitize_sensitive_data
from backend.app.providers.exceptions import (
    ProviderAuthenticationError,
    ProviderResourceNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)


class RazorpayClient:
    """
    Isolated client for interacting with Razorpay REST API.
    Authenticates using HTTP Basic Auth (key_id, key_secret).
    """
    DEFAULT_BASE_URL: str = "https://api.razorpay.com/v1"
    DEFAULT_TIMEOUT: float = 10.0

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._key_id = (key_id if key_id is not None else settings.RAZORPAY_KEY_ID).strip()
        self._key_secret = (key_secret if key_secret is not None else settings.RAZORPAY_KEY_SECRET).strip()
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout or self.DEFAULT_TIMEOUT

    def _ensure_credentials(self) -> None:
        """Verify credentials are configured before executing network operations."""
        if not self._key_id or not self._key_secret:
            raise ProviderAuthenticationError(
                "Razorpay API credentials (key_id / key_secret) are not configured",
                provider="RAZORPAY",
            )

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Fetch a payment by its Razorpay transaction ID (e.g. 'pay_H93Xskd9').

        Returns:
            Dict[str, Any]: Raw Razorpay payment JSON payload.

        Raises:
            ProviderAuthenticationError: If API credentials fail (HTTP 401 / 403).
            ProviderResourceNotFoundError: If payment does not exist (HTTP 404).
            ProviderValidationError: If payment ID is malformed or invalid response (HTTP 400).
            ProviderUnavailableError: On gateway errors (HTTP 5xx, timeouts, connection drops).
        """
        if not payment_id or not isinstance(payment_id, str):
            raise ProviderValidationError(
                "Payment ID must be a non-empty string",
                provider="RAZORPAY",
            )

        clean_payment_id = payment_id.strip()
        self._ensure_credentials()

        url = f"{self.base_url}/payments/{clean_payment_id}"
        auth = (self._key_id, self._key_secret)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, auth=auth)
        except httpx.TimeoutException as exc:
            logger.warning("Razorpay API request timed out for payment %s", clean_payment_id)
            raise ProviderUnavailableError(
                "Upstream Razorpay API request timed out",
                provider="RAZORPAY",
            ) from exc
        except httpx.NetworkError as exc:
            logger.warning("Razorpay API network error for payment %s: %s", clean_payment_id, exc)
            raise ProviderUnavailableError(
                "Could not connect to Razorpay payment gateway",
                provider="RAZORPAY",
            ) from exc
        except Exception as exc:
            logger.error("Unexpected error connecting to Razorpay for payment %s: %s", clean_payment_id, exc)
            raise ProviderUnavailableError(
                "Unexpected communication failure with Razorpay gateway",
                provider="RAZORPAY",
            ) from exc

        return self._handle_response(response, payment_id=clean_payment_id)

    def _handle_response(self, response: httpx.Response, payment_id: str) -> Dict[str, Any]:
        """Handle HTTP status codes and safely parse response body."""
        status_code = response.status_code

        # Attempt to parse response body as JSON
        try:
            body = response.json()
            sanitized_body = sanitize_sensitive_data(body)
        except Exception:
            body = None
            sanitized_body = {"raw_text": response.text[:200]}

        if status_code == 200:
            if not isinstance(body, dict):
                raise ProviderValidationError(
                    "Malformed response from Razorpay API: expected JSON object",
                    provider="RAZORPAY",
                    raw_response=sanitized_body,
                )
            return body

        error_description = ""
        if isinstance(body, dict) and "error" in body:
            err_data = body["error"]
            if isinstance(err_data, dict):
                error_description = err_data.get("description", "")

        if status_code in (401, 403):
            logger.warning("Razorpay authentication failed for payment %s (HTTP %s)", payment_id, status_code)
            raise ProviderAuthenticationError(
                "Razorpay API authentication failed: invalid key_id or key_secret",
                provider="RAZORPAY",
                raw_response=sanitized_body,
            )

        if status_code == 404:
            logger.info("Razorpay payment %s not found (HTTP 404)", payment_id)
            raise ProviderResourceNotFoundError(
                f"Razorpay payment '{payment_id}' not found",
                provider="RAZORPAY",
                raw_response=sanitized_body,
            )

        if status_code in (400, 422):
            msg = f"Razorpay validation error: {error_description}" if error_description else "Invalid Razorpay request"
            raise ProviderValidationError(
                msg,
                provider="RAZORPAY",
                raw_response=sanitized_body,
            )

        if status_code >= 500:
            logger.warning("Razorpay server error HTTP %s for payment %s", status_code, payment_id)
            raise ProviderUnavailableError(
                f"Razorpay gateway returned server error (HTTP {status_code})",
                provider="RAZORPAY",
                raw_response=sanitized_body,
            )

        raise ProviderUnavailableError(
            f"Unexpected HTTP status {status_code} from Razorpay gateway",
            provider="RAZORPAY",
            raw_response=sanitized_body,
        )

    def __repr__(self) -> str:
        masked_key = f"{self._key_id[:8]}..." if len(self._key_id) > 8 else "***"
        return f"<RazorpayClient key_id='{masked_key}' base_url='{self.base_url}'>"
