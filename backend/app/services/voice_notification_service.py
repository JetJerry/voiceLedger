"""
VoiceLedger Voice Notification Service.

Converts canonical financial payment events into localized voice notifications
and synthesized audio artifacts for physical Soundbox playback.

CRITICAL INVARIANTS:
1. Downstream Consumer Only: Voice synthesis is purely downstream; it is NEVER
   a financial source of truth.
2. Failure Isolation: If TTS synthesis fails, the VoiceNotification transitions
   to FAILED, but the underlying Payment and ledger records remain 100% successful.
3. Idempotency: Processing the same event twice returns the existing notification
   without duplicating database records or re-synthesizing audio.
4. Selective Notification: Announces ONLY actionable lifecycle events (captured,
   authorized, refunded, partially refunded). Skips created/failed states.
5. Zero Razorpay Coupling: Consumes canonical events exclusively. Contains zero
   imports from Razorpay SDKs.
"""
from datetime import datetime, timezone
import hashlib
import logging
from typing import Optional, Dict, Any
import uuid

from sqlalchemy.orm import Session

from backend.app.models.device import Device, DeviceStatus
from backend.app.models.payment import Payment
from backend.app.models.voice_notification import VoiceNotification, VoiceNotificationStatus
from backend.app.providers.tts.base import TTSProvider, AudioResult
from backend.app.providers.tts.mock import MockTTSProvider
from backend.app.services.voice_formatter import format_voice_phrase

logger = logging.getLogger("voiceledger.voice.service")


class VoiceNotificationService:
    """Core service managing voice phrase formatting, TTS synthesis, and notification lifecycle."""

    def __init__(self, default_tts_provider: Optional[TTSProvider] = None):
        self._default_provider = default_tts_provider or MockTTSProvider()
        # In-memory deterministic audio cache: SHA-256(text:language) -> AudioResult
        self._audio_cache: Dict[str, AudioResult] = {}
        # Notification-to-audio mapping: notification_id -> AudioResult
        self._notification_audio: Dict[uuid.UUID, AudioResult] = {}

    def _cache_key(self, text: str, language: str, provider_id: str = "") -> str:
        raw = f"{text.strip()}:{language.strip().lower()}:{provider_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def clear_cache(self) -> None:
        """Clear in-memory audio caches."""
        self._audio_cache.clear()
        self._notification_audio.clear()

    async def process_payment_event_for_voice(
        self,
        db: Session,
        event_payload: Dict[str, Any],
        tts_provider: Optional[TTSProvider] = None,
        target_device_id: Optional[uuid.UUID] = None,
        language: str = "en-IN",
    ) -> Optional[VoiceNotification]:
        """
        Process a canonical payment event, construct the localized phrase, synthesize
        TTS audio, and persist the VoiceNotification record.

        :param db: Active SQLAlchemy Session.
        :param event_payload: Canonical event dict (must include event_type, payment_id, merchant_id, amount_minor).
        :param tts_provider: Optional TTSProvider override (defaults to MockTTSProvider).
        :param target_device_id: Optional specific device to target.
        :param language: Spoken language code (e.g. 'en-IN', 'hi-IN').
        :return: Persisted VoiceNotification, or None if the event should not be announced.
        """
        event_type = str(event_payload.get("event_type", ""))
        amount_minor = event_payload.get("amount_minor")
        currency = str(event_payload.get("currency", "INR"))

        # 1. Filter non-notifiable events
        phrase = format_voice_phrase(
            event_type=event_type,
            amount_minor=amount_minor,
            currency=currency,
            language=language,
        )
        if not phrase:
            logger.info("Event type '%s' is not configured for voice announcements; skipping", event_type)
            return None

        # 2. Extract and validate entity identifiers
        raw_merchant_id = event_payload.get("merchant_id")
        raw_payment_id = event_payload.get("payment_id")
        if not raw_merchant_id or not raw_payment_id:
            logger.warning("Event missing merchant_id or payment_id: %r", event_payload)
            return None

        merchant_id = uuid.UUID(str(raw_merchant_id))
        payment_id = uuid.UUID(str(raw_payment_id))

        # 3. Resolve target soundbox device
        device_id = target_device_id
        if device_id is None:
            device = (
                db.query(Device)
                .filter(
                    Device.merchant_id == merchant_id,
                    Device.status == DeviceStatus.ACTIVE.value,
                )
                .first()
            )
            if not device:
                logger.info(
                    "Merchant %s has no active soundbox devices; skipping voice notification persistence",
                    merchant_id,
                )
                return None
            device_id = device.id
        else:
            # Verify explicit device belongs to the merchant
            device = (
                db.query(Device)
                .filter(Device.id == device_id, Device.merchant_id == merchant_id)
                .first()
            )
            if not device:
                logger.warning("Specified device %s does not belong to merchant %s", device_id, merchant_id)
                return None

        # 4. Idempotency Check: Prevent duplicate notifications for same (payment_id, device_id)
        existing = (
            db.query(VoiceNotification)
            .filter(
                VoiceNotification.payment_id == payment_id,
                VoiceNotification.device_id == device_id,
            )
            .first()
        )
        if existing:
            logger.info(
                "VoiceNotification already exists for payment %s and device %s (idempotent noop)",
                payment_id,
                device_id,
            )
            return existing

        # 5. Create VoiceNotification record (PENDING)
        now = datetime.now(timezone.utc)
        notification = VoiceNotification(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            device_id=device_id,
            payment_id=payment_id,
            message=phrase,
            status=VoiceNotificationStatus.PENDING.value,
            attempt_count=1,
            created_at=now,
            last_attempt_at=now,
        )
        db.add(notification)
        db.flush()

        # 6. Synthesize TTS Audio
        provider = tts_provider or self._default_provider
        use_cache = (tts_provider is None)
        provider_name = provider.__class__.__name__
        cache_key = self._cache_key(phrase, language, provider_name)

        try:
            if use_cache and cache_key in self._audio_cache:
                audio_res = self._audio_cache[cache_key]
            else:
                audio_res = await provider.synthesize(text=phrase, language=language)
                if use_cache:
                    self._audio_cache[cache_key] = audio_res

            # Success: transition to QUEUED (audio ready for soundbox playback)
            notification.status = VoiceNotificationStatus.QUEUED.value
            notification.delivered_at = datetime.now(timezone.utc)
            self._notification_audio[notification.id] = audio_res
            logger.info("Synthesized voice audio for notification id=%s", notification.id)

        except Exception as exc:
            # Failure Isolation: Mark notification FAILED, record error, NEVER fail payment!
            logger.warning(
                "TTS synthesis failed for notification id=%s (error: %s). Financial state remains intact.",
                notification.id,
                exc,
            )
            notification.status = VoiceNotificationStatus.FAILED.value
            notification.error_message = str(exc)[:500]

        db.commit()
        db.refresh(notification)
        return notification

    def get_audio_artifact(self, notification_id: uuid.UUID) -> Optional[AudioResult]:
        """Retrieve the synthesized audio artifact associated with a VoiceNotification."""
        return self._notification_audio.get(notification_id)


# Global singleton service
voice_notification_service = VoiceNotificationService()
