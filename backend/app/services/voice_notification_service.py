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
import base64
from datetime import datetime, timezone
import hashlib
import logging
from typing import Optional, Dict, Any, Set
import uuid

from sqlalchemy.orm import Session

from backend.app.models.device import Device, DeviceStatus
from backend.app.models.payment import Payment
from backend.app.models.voice_notification import VoiceNotification, VoiceNotificationStatus
from backend.app.providers.tts.base import TTSProvider, AudioResult
from backend.app.providers.tts.mock import MockTTSProvider
from backend.app.services.voice_formatter import format_voice_phrase
from backend.app.services.websocket_manager import merchant_ws_manager

logger = logging.getLogger("voiceledger.voice.service")

# Allowed audio MIME types for Soundbox hardware streaming
ALLOWED_AUDIO_TYPES = frozenset({"audio/wav", "audio/mpeg", "audio/mp3"})
MAX_AUDIO_BYTES = 2 * 1024 * 1024  # 2 MB max for Soundbox announcements


class VoiceNotificationError(Exception):
    """Base exception for voice notification subsystem."""
    pass


class VoiceNotificationNotFoundError(VoiceNotificationError):
    """Raised when a specified VoiceNotification record does not exist."""
    pass


class VoiceNotificationForbiddenError(VoiceNotificationError):
    """Raised when a device or merchant attempts to ACK a notification it does not own."""
    pass


class VoiceNotificationAudioError(VoiceNotificationError):
    """Raised when audio artifact is invalid, missing, or exceeds maximum payload size."""
    pass


class VoiceNotificationService:
    """Core service managing voice phrase formatting, TTS synthesis, and notification lifecycle."""

    def __init__(self, default_tts_provider: Optional[TTSProvider] = None):
        self._default_provider = default_tts_provider or MockTTSProvider()
        # In-memory deterministic audio cache: SHA-256(text:language) -> AudioResult
        self._audio_cache: Dict[str, AudioResult] = {}
        # Notification-to-audio mapping: notification_id -> AudioResult
        self._notification_audio: Dict[uuid.UUID, AudioResult] = {}
        # In-process set of notification IDs currently being replayed to prevent duplicates
        self._in_flight_replays: Set[uuid.UUID] = set()

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

    def prepare_audio_payload(
        self,
        notification: VoiceNotification,
        audio_result: AudioResult,
        max_bytes: int = MAX_AUDIO_BYTES,
    ) -> Dict[str, Any]:
        """
        Validate audio artifact and construct the canonical JSON WebSocket payload
        for Soundbox streaming.

        Validations:
        - Audio artifact bytes must exist and be non-empty.
        - Content type must be in ALLOWED_AUDIO_TYPES.
        - Audio byte length must not exceed max_bytes.
        """
        if not audio_result or not audio_result.audio_bytes:
            raise VoiceNotificationAudioError("Missing or empty audio artifact bytes")

        if audio_result.content_type.lower() not in ALLOWED_AUDIO_TYPES:
            raise VoiceNotificationAudioError(
                f"Disallowed audio content-type '{audio_result.content_type}'. Allowed: {sorted(ALLOWED_AUDIO_TYPES)}"
            )

        if len(audio_result.audio_bytes) > max_bytes:
            raise VoiceNotificationAudioError(
                f"Audio payload size ({len(audio_result.audio_bytes)} bytes) exceeds maximum limit ({max_bytes} bytes)"
            )

        encoded_audio = base64.b64encode(audio_result.audio_bytes).decode("utf-8")

        return {
            "type": "voice_notification",
            "notification_id": str(notification.id),
            "payment_id": str(notification.payment_id),
            "device_id": str(notification.device_id),
            "merchant_id": str(notification.merchant_id),
            "audio_content_type": audio_result.content_type,
            "audio_data": encoded_audio,
            "text": notification.message,
            "duration_seconds": audio_result.duration_seconds,
        }

    async def dispatch_notification_to_device(
        self,
        notification: VoiceNotification,
        audio_result: Optional[AudioResult] = None,
    ) -> bool:
        """
        Stream validated audio notification directly to the targeted Soundbox WebSocket.
        Returns True if delivered, False if device is currently offline or send failed.
        """
        audio = audio_result or self.get_audio_artifact(notification.id)
        if not audio:
            logger.warning("No audio artifact available for notification %s", notification.id)
            return False

        payload = self.prepare_audio_payload(notification, audio)
        delivered = await merchant_ws_manager.send_to_device(notification.device_id, payload)
        if delivered:
            logger.info("Successfully dispatched audio notification %s to device %s", notification.id, notification.device_id)
        else:
            logger.info("Device %s is offline or unreachable; notification %s pending playback", notification.device_id, notification.id)
        return delivered

    def record_playback_ack(
        self,
        db: Session,
        device_id: uuid.UUID,
        notification_id: uuid.UUID,
        ack_status: str,
        error_detail: Optional[str] = None,
    ) -> VoiceNotification:
        """
        Acknowledge audio playback from an authenticated Soundbox device.

        Invariants:
        1. Device Isolation: Device must own the notification (notification.device_id == device_id).
        2. Idempotency: Repeated PLAYED ACKs return the DELIVERED record without errors or duplicates.
        3. Canonical Lifecycle: PLAYED maps to DELIVERED; FAILED maps to FAILED.
        4. Financial Ledger Untouched: Only updates VoiceNotification; zero mutation to payments.
        """
        notification = (
            db.query(VoiceNotification)
            .filter(VoiceNotification.id == notification_id)
            .first()
        )
        if not notification:
            raise VoiceNotificationNotFoundError(f"VoiceNotification '{notification_id}' not found")

        if notification.device_id != device_id:
            raise VoiceNotificationForbiddenError(
                f"Device '{device_id}' is not authorized to ACK notification '{notification_id}'"
            )

        status_norm = (ack_status or "PLAYED").strip().upper()

        # Idempotent no-op for duplicate successful playback ACKs
        if notification.status == VoiceNotificationStatus.DELIVERED.value and status_norm in ("PLAYED", "DELIVERED"):
            logger.info("Duplicate PLAYED ACK for notification %s (idempotent noop)", notification_id)
            return notification

        if status_norm in ("PLAYED", "DELIVERED"):
            notification.status = VoiceNotificationStatus.DELIVERED.value
            notification.delivered_at = datetime.now(timezone.utc)
            notification.error_message = None
            logger.info("Notification %s successfully marked DELIVERED via Soundbox ACK", notification_id)
        elif status_norm == "FAILED":
            notification.status = VoiceNotificationStatus.FAILED.value
            notification.error_message = (error_detail or "Soundbox playback reported failure")[:500]
            logger.warning("Soundbox playback failed for notification %s: %s", notification_id, notification.error_message)
        else:
            logger.warning("Unrecognized playback ACK status '%s' for notification %s; ignored", ack_status, notification_id)

        db.commit()
        db.refresh(notification)
        return notification

    async def replay_pending_notifications_for_device(
        self,
        db: Session,
        device_id: uuid.UUID,
        limit: int = 50,
    ) -> int:
        """
        Query and replay unacknowledged QUEUED voice notifications for an authenticated device.

        Invariants:
        1. Device Isolation: Replays strictly for the authenticated device_id.
        2. Status Filter: Only QUEUED notifications are replayed (never DELIVERED or FAILED).
        3. Deterministic Order: Replays oldest-first (created_at ASC).
        4. Audio Resilience: Re-synthesizes audio via default TTS provider if audio is missing/evicted.
        5. Duplicate In-Flight Protection: Prevents parallel replay of the same notification.
        6. State Preservation: Notification remains QUEUED until client sends PLAYED ACK.
        """
        pending_notifications = (
            db.query(VoiceNotification)
            .filter(
                VoiceNotification.device_id == device_id,
                VoiceNotification.status == VoiceNotificationStatus.QUEUED.value,
            )
            .order_by(VoiceNotification.created_at.asc())
            .limit(limit)
            .all()
        )

        if not pending_notifications:
            return 0

        replayed_count = 0
        for notification in pending_notifications:
            if notification.id in self._in_flight_replays:
                continue

            self._in_flight_replays.add(notification.id)
            try:
                # Ensure audio artifact is available
                audio = self.get_audio_artifact(notification.id)
                if not audio:
                    cache_key = self._cache_key(notification.message, "en-IN", self._default_provider.__class__.__name__)
                    if cache_key in self._audio_cache:
                        audio = self._audio_cache[cache_key]
                    else:
                        try:
                            audio = await self._default_provider.synthesize(text=notification.message)
                            self._audio_cache[cache_key] = audio
                        except Exception as exc:
                            logger.warning(
                                "TTS synthesis failed for offline replay of notification %s: %s",
                                notification.id,
                                exc,
                            )
                            continue
                    self._notification_audio[notification.id] = audio

                delivered = await self.dispatch_notification_to_device(notification, audio)
                if delivered:
                    notification.attempt_count += 1
                    notification.last_attempt_at = datetime.now(timezone.utc)
                    replayed_count += 1
            except Exception as exc:
                logger.error(
                    "Unexpected error during replay of notification %s to device %s: %s",
                    notification.id,
                    device_id,
                    exc,
                )
            finally:
                self._in_flight_replays.discard(notification.id)

        db.commit()
        return replayed_count


# Global singleton service
voice_notification_service = VoiceNotificationService()
