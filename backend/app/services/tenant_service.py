"""
VoiceLedger Tenant Isolation & Security Service.

Enforces server-side tenant isolation across all merchant-owned resources.
Guarantees that possession of a resource UUID never grants unauthorized access
and enforces query-level scoping on (resource_id, merchant_id).
"""
import uuid
from typing import Optional, Any
from sqlalchemy.orm import Session

from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.models.payment import Payment
from backend.app.models.payment_event import PaymentEvent
from backend.app.models.device import Device
from backend.app.models.device_session import DeviceSession
from backend.app.models.voice_notification import VoiceNotification
from backend.app.models.provider_connection import ProviderConnection
from backend.app.models.audit_log import AuditLog
from backend.app.core.logging import logger


class TenantAccessDeniedError(Exception):
    """Base exception for tenant authorization failures."""
    pass


class CrossTenantAccessError(TenantAccessDeniedError):
    """Raised when an authenticated user attempts to access another merchant's resource."""
    pass


class InsufficientRoleError(TenantAccessDeniedError):
    """Raised when a user lacks the required RBAC role within a merchant organization."""
    pass


class MerchantInactiveError(TenantAccessDeniedError):
    """Raised when a merchant organization is suspended or deactivated."""
    pass


class TenantService:
    """
    Authoritative service for verifying merchant tenancy and scoping resource access.
    """

    def verify_merchant_membership(
        self,
        db: Session,
        user_id: uuid.UUID,
        merchant_id: uuid.UUID,
    ) -> MerchantUser:
        """
        Verify that user_id has an active membership in merchant_id.
        Rejects arbitrary merchant IDs and verifies merchant status.
        """
        membership = (
            db.query(MerchantUser)
            .join(Merchant, MerchantUser.merchant_id == Merchant.id)
            .filter(
                MerchantUser.user_id == user_id,
                MerchantUser.merchant_id == merchant_id,
            )
            .first()
        )
        if not membership:
            logger.warning(
                "Unauthorized tenant access attempt: user_id=%s requested merchant_id=%s without membership",
                user_id,
                merchant_id,
            )
            raise CrossTenantAccessError("User is not a member of the requested merchant organization")

        if membership.merchant.status != "ACTIVE":
            raise MerchantInactiveError("Merchant organization is not active")

        return membership

    def get_payment_for_merchant(
        self,
        db: Session,
        payment_id: uuid.UUID,
        merchant_id: uuid.UUID,
    ) -> Optional[Payment]:
        """
        Retrieve Payment scoped strictly to merchant_id at query level.
        Prevents IDOR by asserting (id, merchant_id) compound match.
        """
        return (
            db.query(Payment)
            .filter(
                Payment.id == payment_id,
                Payment.merchant_id == merchant_id,
            )
            .first()
        )

    def get_payment_event_for_merchant(
        self,
        db: Session,
        event_id: uuid.UUID,
        merchant_id: uuid.UUID,
    ) -> Optional[PaymentEvent]:
        """
        Retrieve PaymentEvent scoped strictly to merchant_id at query level.
        """
        return (
            db.query(PaymentEvent)
            .filter(
                PaymentEvent.id == event_id,
                PaymentEvent.merchant_id == merchant_id,
            )
            .first()
        )

    def get_device_for_merchant(
        self,
        db: Session,
        device_id: uuid.UUID,
        merchant_id: uuid.UUID,
    ) -> Optional[Device]:
        """
        Retrieve Device scoped strictly to merchant_id at query level.
        """
        return (
            db.query(Device)
            .filter(
                Device.id == device_id,
                Device.merchant_id == merchant_id,
            )
            .first()
        )

    def get_device_session_for_merchant(
        self,
        db: Session,
        session_id: uuid.UUID,
        merchant_id: uuid.UUID,
    ) -> Optional[DeviceSession]:
        """
        Retrieve DeviceSession scoped to merchant_id through indirect relation:
        DeviceSession -> Device -> Merchant.
        """
        return (
            db.query(DeviceSession)
            .join(Device, DeviceSession.device_id == Device.id)
            .filter(
                DeviceSession.id == session_id,
                Device.merchant_id == merchant_id,
            )
            .first()
        )

    def get_voice_notification_for_merchant(
        self,
        db: Session,
        notification_id: uuid.UUID,
        merchant_id: uuid.UUID,
    ) -> Optional[VoiceNotification]:
        """
        Retrieve VoiceNotification scoped strictly to merchant_id at query level.
        """
        return (
            db.query(VoiceNotification)
            .filter(
                VoiceNotification.id == notification_id,
                VoiceNotification.merchant_id == merchant_id,
            )
            .first()
        )

    def get_provider_connection_for_merchant(
        self,
        db: Session,
        connection_id: uuid.UUID,
        merchant_id: uuid.UUID,
    ) -> Optional[ProviderConnection]:
        """
        Retrieve ProviderConnection scoped strictly to merchant_id at query level.
        """
        return (
            db.query(ProviderConnection)
            .filter(
                ProviderConnection.id == connection_id,
                ProviderConnection.merchant_id == merchant_id,
            )
            .first()
        )

    def get_audit_log_for_merchant(
        self,
        db: Session,
        log_id: uuid.UUID,
        merchant_id: uuid.UUID,
    ) -> Optional[AuditLog]:
        """
        Retrieve AuditLog scoped strictly to merchant_id at query level.
        """
        return (
            db.query(AuditLog)
            .filter(
                AuditLog.id == log_id,
                AuditLog.merchant_id == merchant_id,
            )
            .first()
        )

    def assert_resource_ownership(
        self,
        resource: Any,
        merchant_id: uuid.UUID,
        db: Optional[Session] = None,
    ) -> None:
        """
        Assert that a given loaded entity belongs to the expected merchant.
        Handles direct and indirect (DeviceSession) ownership, even when relations are unloaded.
        """
        if resource is None:
            return

        if hasattr(resource, "merchant_id"):
            if resource.merchant_id != merchant_id:
                raise CrossTenantAccessError("Cross-tenant resource access violation")
        elif isinstance(resource, DeviceSession):
            if resource.device is not None:
                if resource.device.merchant_id != merchant_id:
                    raise CrossTenantAccessError("Cross-tenant device session access violation")
            elif db is not None:
                dev = db.query(Device).filter(Device.id == resource.device_id).first()
                if not dev or dev.merchant_id != merchant_id:
                    raise CrossTenantAccessError("Cross-tenant device session access violation")

    def update_device_for_merchant(
        self,
        db: Session,
        device_id: uuid.UUID,
        merchant_id: uuid.UUID,
        device_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[Device]:
        """
        Update Device attributes scoped strictly to merchant_id at query level.
        Guarantees that cross-tenant mutations are prevented.
        """
        device = (
            db.query(Device)
            .filter(
                Device.id == device_id,
                Device.merchant_id == merchant_id,
            )
            .first()
        )
        if not device:
            return None

        if device_name is not None:
            device.device_name = device_name
        if status is not None:
            device.status = status

        db.commit()
        db.refresh(device)
        return device

    def delete_device_for_merchant(
        self,
        db: Session,
        device_id: uuid.UUID,
        merchant_id: uuid.UUID,
    ) -> bool:
        """
        Delete Device scoped strictly to merchant_id at query level.
        Prevents unauthorized deletion across tenants.
        """
        device = (
            db.query(Device)
            .filter(
                Device.id == device_id,
                Device.merchant_id == merchant_id,
            )
            .first()
        )
        if not device:
            return False

        db.delete(device)
        db.commit()
        return True


tenant_service = TenantService()
