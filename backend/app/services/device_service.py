"""
VoiceLedger Soundbox Device Service.

Implements the physical Soundbox device management, provisioning, authentication,
and heartbeat boundary.

Invariants:
1. One Merchant Ownership: Every device belongs to exactly one merchant.
2. Token Hashing at Rest: Raw device secrets and session tokens are NEVER stored in PostgreSQL.
   Only SHA-256 hashes are persisted.
3. One-Time Secret Exposure: Raw device secrets are returned strictly once during initial registration.
4. Constant-Time Hash Comparison: Token and secret checks use hmac.compare_digest to eliminate
   timing attack vectors.
5. Inactive Device Protection: Inactive or revoked devices cannot authenticate or send heartbeats.
6. Zero Financial Logic: Strictly downstream hardware identity; never mutates payments or balances.
"""
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import logging
import secrets
from typing import Tuple, List, Optional
import uuid

from sqlalchemy.orm import Session

from backend.app.models.merchant import Merchant
from backend.app.models.device import Device, DeviceStatus, DeviceType
from backend.app.models.device_session import DeviceSession, DeviceSessionStatus

logger = logging.getLogger("voiceledger.devices.service")


class DeviceError(Exception):
    """Base exception for device service failures."""
    pass


class DeviceNotFoundError(DeviceError):
    """Raised when a requested device is not found."""
    pass


class DeviceInactiveError(DeviceError):
    """Raised when an operation is attempted on an inactive or revoked device."""
    pass


class DeviceAuthenticationError(DeviceError):
    """Raised when device credentials or secrets are invalid."""
    pass


class DeviceSessionInvalidError(DeviceError):
    """Raised when a device session token is invalid, expired, or revoked."""
    pass


class DeviceService:
    """Core service for Soundbox device registration, authentication, and telemetry."""

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Compute a SHA-256 hex digest for storage or lookup."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def register_device(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        device_name: str,
        device_type: str = DeviceType.SOUNDBOX.value,
    ) -> Tuple[Device, str]:
        """
        Register a new Soundbox under an active merchant.
        Generates a high-entropy provisioning secret returned strictly once.
        """
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant or merchant.status != "ACTIVE":
            raise DeviceInactiveError(f"Merchant {merchant_id} is inactive or does not exist")

        # Generate cryptographically secure random device secret
        raw_secret = f"devsec_{secrets.token_urlsafe(32)}"
        token_hash = self.hash_token(raw_secret)

        device = Device(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            device_name=device_name.strip(),
            device_type=device_type,
            status=DeviceStatus.ACTIVE.value,
            device_token_hash=token_hash,
            last_seen_at=None,
        )
        db.add(device)
        db.flush()

        logger.info(
            "Registered new device id=%s name='%s' for merchant_id=%s",
            device.id,
            device.device_name,
            merchant_id,
        )
        return device, raw_secret

    def authenticate_device(
        self,
        db: Session,
        device_id: uuid.UUID,
        raw_secret: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_duration_hours: int = 24,
    ) -> Tuple[DeviceSession, str]:
        """
        Authenticate a physical Soundbox using its provisioned secret.
        Creates a new active DeviceSession and returns the session bearer token.
        """
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise DeviceAuthenticationError("Invalid device identifier or secret")

        if device.status != DeviceStatus.ACTIVE.value:
            raise DeviceInactiveError(f"Device {device_id} is {device.status} (must be ACTIVE)")

        if not device.device_token_hash:
            raise DeviceAuthenticationError("Device has no provisioned secret")

        # Constant-time comparison against stored SHA-256 hash
        computed_hash = self.hash_token(raw_secret)
        if not hmac.compare_digest(device.device_token_hash, computed_hash):
            logger.warning("Failed authentication attempt for device id=%s", device_id)
            raise DeviceAuthenticationError("Invalid device identifier or secret")

        # Issue active session bearer token
        raw_session_token = f"devsess_{secrets.token_urlsafe(32)}"
        session_hash = self.hash_token(raw_session_token)

        now = datetime.now(timezone.utc)
        session = DeviceSession(
            id=uuid.uuid4(),
            device_id=device.id,
            session_token_hash=session_hash,
            status=DeviceSessionStatus.CONNECTED.value,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=now + timedelta(hours=session_duration_hours),
            last_activity_at=now,
        )
        db.add(session)

        device.last_seen_at = now
        db.flush()

        logger.info("Authenticated device id=%s (session_id=%s)", device.id, session.id)
        return session, raw_session_token

    def record_heartbeat(
        self,
        db: Session,
        device_id: uuid.UUID,
        raw_session_token: str,
    ) -> Device:
        """
        Validate device session and record telemetry heartbeat, keeping device online.
        """
        token_hash = self.hash_token(raw_session_token)
        session = (
            db.query(DeviceSession)
            .filter(
                DeviceSession.device_id == device_id,
                DeviceSession.session_token_hash == token_hash,
            )
            .first()
        )

        if not session or not session.is_active:
            raise DeviceSessionInvalidError("Invalid, expired, or revoked device session")

        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise DeviceNotFoundError("Device not found")

        if device.status != DeviceStatus.ACTIVE.value:
            raise DeviceInactiveError(f"Device {device_id} is {device.status} (cannot send heartbeat)")

        now = datetime.now(timezone.utc)
        session.last_activity_at = now
        device.last_seen_at = now
        db.flush()

        return device

    def list_devices(
        self,
        db: Session,
        merchant_id: uuid.UUID,
        online_threshold_seconds: int = 300,
    ) -> List[Tuple[Device, bool]]:
        """
        List all devices belonging to a merchant with dynamically computed online status.
        """
        devices = (
            db.query(Device)
            .filter(Device.merchant_id == merchant_id)
            .order_by(Device.created_at.desc())
            .all()
        )

        now = datetime.now(timezone.utc)
        result = []
        for d in devices:
            is_online = False
            if d.status == DeviceStatus.ACTIVE.value and d.last_seen_at:
                delta = (now - d.last_seen_at).total_seconds()
                is_online = delta <= online_threshold_seconds
            result.append((d, is_online))

        return result

    def verify_device_session(
        self,
        db: Session,
        raw_session_token: str,
    ) -> Tuple[Device, DeviceSession]:
        """
        Verify an incoming device session token for WebSocket connection or operations.
        Validates token hash, active status, unexpired state, and active parent device.
        Updates telemetry activity timestamps.
        """
        token_hash = self.hash_token(raw_session_token)
        session = (
            db.query(DeviceSession)
            .filter(DeviceSession.session_token_hash == token_hash)
            .first()
        )

        if not session:
            raise DeviceSessionInvalidError("Invalid device session token")
        if not session.is_active:
            raise DeviceSessionInvalidError("Device session is expired or revoked")

        device = db.query(Device).filter(Device.id == session.device_id).first()
        if not device:
            raise DeviceNotFoundError("Associated device not found")

        if device.status != DeviceStatus.ACTIVE.value:
            raise DeviceInactiveError(f"Device {device.id} is {device.status} (must be ACTIVE)")

        now = datetime.now(timezone.utc)
        session.last_activity_at = now
        device.last_seen_at = now
        db.flush()

        return device, session


# Global singleton device service
device_service = DeviceService()
