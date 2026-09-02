"""Initial consolidated schema for VoiceLedger canonical models

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-03 02:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    # 2. merchants table
    op.create_table(
        "merchants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("business_type", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="ACTIVE", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_merchants"),
    )
    op.create_index("ix_merchants_name", "merchants", ["name"], unique=False)
    op.create_index("ix_merchants_status", "merchants", ["status"], unique=False)

    # 3. merchant_users table
    op.create_table(
        "merchant_users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=50), server_default="STAFF", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], name="fk_merchant_users_merchant_id_merchants", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_merchant_users_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_merchant_users"),
        sa.UniqueConstraint("merchant_id", "user_id", name="uq_merchant_users_merchant_user"),
    )
    op.create_index("ix_merchant_users_merchant_id", "merchant_users", ["merchant_id"], unique=False)
    op.create_index("ix_merchant_users_merchant_user", "merchant_users", ["merchant_id", "user_id"], unique=False)
    op.create_index("ix_merchant_users_user_id", "merchant_users", ["user_id"], unique=False)

    # 4. provider_connections table
    op.create_table(
        "provider_connections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_account_reference", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="ACTIVE", nullable=False),
        sa.Column("encrypted_credentials_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], name="fk_provider_connections_merchant_id_merchants", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_provider_connections"),
        sa.UniqueConstraint("merchant_id", "provider", "provider_account_reference", name="uq_provider_connections_merchant_provider_account"),
    )
    op.create_index("ix_provider_connections_merchant_id", "provider_connections", ["merchant_id"], unique=False)
    op.create_index("ix_provider_connections_merchant_provider", "provider_connections", ["merchant_id", "provider"], unique=False)
    op.create_index("ix_provider_connections_provider", "provider_connections", ["provider"], unique=False)

    # 5. payments table
    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=False),
        sa.Column("provider_order_id", sa.String(length=255), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="CREATED", nullable=False),
        sa.Column("payer_reference", sa.String(length=255), nullable=True),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount_minor >= 0", name="ck_payments_amount_minor_non_negative"),
        sa.CheckConstraint("length(currency) = 3", name="ck_payments_currency_length"),
        sa.CheckConstraint("status IN ('CREATED', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'REFUNDED', 'PARTIALLY_REFUNDED')", name="ck_payments_status_valid"),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], name="fk_payments_merchant_id_merchants", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.UniqueConstraint("provider", "provider_payment_id", name="uq_payments_provider_payment_id"),
    )
    op.create_index("ix_payments_merchant_created_at", "payments", ["merchant_id", "created_at"], unique=False)
    op.create_index("ix_payments_merchant_id", "payments", ["merchant_id"], unique=False)
    op.create_index("ix_payments_merchant_status_created_at", "payments", ["merchant_id", "status", "created_at"], unique=False)
    op.create_index("ix_payments_provider", "payments", ["provider"], unique=False)
    op.create_index("ix_payments_provider_order_id", "payments", ["provider_order_id"], unique=False)
    op.create_index("ix_payments_provider_payment_id", "payments", ["provider", "provider_payment_id"], unique=False)
    op.create_index("ix_payments_status", "payments", ["status"], unique=False)

    # 6. payment_events table
    op.create_table(
        "payment_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=True),
        sa.Column("payment_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("processing_status", sa.String(length=50), server_default="RECEIVED", nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.CheckConstraint("processing_status IN ('RECEIVED', 'PROCESSING', 'PROCESSED', 'FAILED', 'DUPLICATE', 'IGNORED')", name="ck_payment_events_status_valid"),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], name="fk_payment_events_merchant_id_merchants", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], name="fk_payment_events_payment_id_payments", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_payment_events"),
        sa.UniqueConstraint("provider", "event_id", name="uq_payment_events_provider_event_id"),
    )
    op.create_index("ix_payment_events_event_id", "payment_events", ["event_id"], unique=False)
    op.create_index("ix_payment_events_event_type", "payment_events", ["event_type"], unique=False)
    op.create_index("ix_payment_events_merchant_id", "payment_events", ["merchant_id"], unique=False)
    op.create_index("ix_payment_events_payload_hash", "payment_events", ["provider", "payload_hash"], unique=False)
    op.create_index("ix_payment_events_payment_id", "payment_events", ["payment_id"], unique=False)
    op.create_index("ix_payment_events_processing_status", "payment_events", ["processing_status"], unique=False)
    op.create_index("ix_payment_events_provider", "payment_events", ["provider"], unique=False)
    op.create_index("ix_payment_events_provider_payment_id", "payment_events", ["provider_payment_id"], unique=False)
    op.create_index("ix_payment_events_provider_type_received", "payment_events", ["provider", "event_type", "received_at"], unique=False)

    # 7. devices table
    op.create_table(
        "devices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=False),
        sa.Column("device_type", sa.String(length=50), server_default="SOUNDBOX", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="PAIRING", nullable=False),
        sa.Column("public_key", sa.Text(), nullable=True),
        sa.Column("device_token_hash", sa.String(length=64), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("device_type IN ('SOUNDBOX', 'ANDROID_APP', 'POS_TERMINAL', 'OTHER')", name="ck_devices_type_valid"),
        sa.CheckConstraint("status IN ('PAIRING', 'ACTIVE', 'OFFLINE', 'DISABLED', 'REVOKED')", name="ck_devices_status_valid"),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], name="fk_devices_merchant_id_merchants", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_devices"),
    )
    op.create_index("ix_devices_merchant_id", "devices", ["merchant_id"], unique=False)
    op.create_index("ix_devices_merchant_name", "devices", ["merchant_id", "device_name"], unique=False)
    op.create_index("ix_devices_merchant_status", "devices", ["merchant_id", "status"], unique=False)
    op.create_index("ix_devices_status", "devices", ["status"], unique=False)

    # 8. device_sessions table
    op.create_table(
        "device_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="CONNECTED", nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('CONNECTED', 'DISCONNECTED', 'EXPIRED', 'REVOKED')", name="ck_device_sessions_status_valid"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name="fk_device_sessions_device_id_devices", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_device_sessions"),
        sa.UniqueConstraint("session_token_hash", name="uq_device_sessions_token_hash"),
    )
    op.create_index("ix_device_sessions_device_id", "device_sessions", ["device_id"], unique=False)
    op.create_index("ix_device_sessions_device_status", "device_sessions", ["device_id", "status"], unique=False)
    op.create_index("ix_device_sessions_expires_at", "device_sessions", ["expires_at"], unique=False)
    op.create_index("ix_device_sessions_status", "device_sessions", ["status"], unique=False)

    # 9. voice_notifications table
    op.create_table(
        "voice_notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="PENDING", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.CheckConstraint("attempt_count >= 0", name="ck_voice_notifications_attempt_count_positive"),
        sa.CheckConstraint("status IN ('PENDING', 'QUEUED', 'DELIVERED', 'FAILED', 'CANCELLED')", name="ck_voice_notifications_status_valid"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name="fk_voice_notifications_device_id_devices", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], name="fk_voice_notifications_merchant_id_merchants", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], name="fk_voice_notifications_payment_id_payments", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_voice_notifications"),
    )
    op.create_index("ix_voice_notifications_device_created_at", "voice_notifications", ["device_id", "created_at"], unique=False)
    op.create_index("ix_voice_notifications_device_id", "voice_notifications", ["device_id"], unique=False)
    op.create_index("ix_voice_notifications_merchant_id", "voice_notifications", ["merchant_id"], unique=False)
    op.create_index("ix_voice_notifications_merchant_status", "voice_notifications", ["merchant_id", "status"], unique=False)
    op.create_index("ix_voice_notifications_payment_id", "voice_notifications", ["payment_id"], unique=False)
    op.create_index("ix_voice_notifications_status", "voice_notifications", ["status"], unique=False)

    # 10. audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=True),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], name="fk_audit_logs_merchant_id_merchants", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_action_created_at", "audit_logs", ["action", "created_at"], unique=False)
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"], unique=False)
    op.create_index("ix_audit_logs_actor_type", "audit_logs", ["actor_type"], unique=False)
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    op.create_index("ix_audit_logs_merchant_created_at", "audit_logs", ["merchant_id", "created_at"], unique=False)
    op.create_index("ix_audit_logs_merchant_id", "audit_logs", ["merchant_id"], unique=False)
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"], unique=False)
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"], unique=False)

    # 11. outbox_events table
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", sa.UUID(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="PENDING", nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_retries", sa.Integer(), server_default="5", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.CheckConstraint("max_retries >= 0", name="ck_outbox_events_max_retries_positive"),
        sa.CheckConstraint("retry_count >= 0", name="ck_outbox_events_retry_count_positive"),
        sa.CheckConstraint("status IN ('PENDING', 'PROCESSING', 'PUBLISHED', 'FAILED', 'DEAD_LETTER')", name="ck_outbox_events_status_valid"),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
    )
    op.create_index("ix_outbox_events_aggregate", "outbox_events", ["aggregate_type", "aggregate_id"], unique=False)
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"], unique=False)
    op.create_index("ix_outbox_events_aggregate_type", "outbox_events", ["aggregate_type"], unique=False)
    op.create_index("ix_outbox_events_available_at", "outbox_events", ["available_at"], unique=False)
    op.create_index("ix_outbox_events_created_at", "outbox_events", ["created_at"], unique=False)
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"], unique=False)
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"], unique=False)
    op.create_index("ix_outbox_events_worker_claim", "outbox_events", ["status", "available_at", "created_at"], unique=False)


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("outbox_events")
    op.drop_table("audit_logs")
    op.drop_table("voice_notifications")
    op.drop_table("device_sessions")
    op.drop_table("devices")
    op.drop_table("payment_events")
    op.drop_table("payments")
    op.drop_table("provider_connections")
    op.drop_table("merchant_users")
    op.drop_table("merchants")
    op.drop_table("users")
