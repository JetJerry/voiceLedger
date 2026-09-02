# Canonical VoiceLedger Models
from backend.app.models.user import User
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.models.provider_connection import ProviderConnection
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.payment_event import PaymentEvent, EventProcessingStatus
from backend.app.models.device import Device, DeviceStatus, DeviceType
from backend.app.models.device_session import DeviceSession, DeviceSessionStatus
from backend.app.models.voice_notification import VoiceNotification, VoiceNotificationStatus
from backend.app.models.audit_log import AuditLog
from backend.app.models.outbox_event import OutboxEvent, OutboxStatus

# Legacy prototype models preserved for backward compatibility
from backend.app.models.legacy import (
    Customer,
    Product,
    Sale,
    SaleItem,
    RecoveryAction,
    MerchantProfile,
    WebhookEvent,
)

__all__ = [
    # Canonical VoiceLedger Models
    "User",
    "Merchant",
    "MerchantUser",
    "ProviderConnection",
    "Payment",
    "PaymentStatus",
    "PaymentEvent",
    "EventProcessingStatus",
    "Device",
    "DeviceStatus",
    "DeviceType",
    "DeviceSession",
    "DeviceSessionStatus",
    "VoiceNotification",
    "VoiceNotificationStatus",
    "AuditLog",
    "OutboxEvent",
    "OutboxStatus",
    # Legacy Prototype Models
    "Customer",
    "Product",
    "Sale",
    "SaleItem",
    "RecoveryAction",
    "MerchantProfile",
    "WebhookEvent",
]
