import os
import pytest
from sqlalchemy import create_engine, inspect, BigInteger
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from alembic.config import Config
from alembic.script import ScriptDirectory

from backend.app.db.base import Base
import backend.app.models as models
from backend.app.models.legacy import LegacyBase
from backend.app.config import settings

CANONICAL_TABLE_NAMES = {
    "users",
    "merchants",
    "merchant_users",
    "provider_connections",
    "payments",
    "payment_events",
    "devices",
    "device_sessions",
    "voice_notifications",
    "audit_logs",
    "outbox_events",
}

CANONICAL_MODEL_CLASSES = [
    models.User,
    models.Merchant,
    models.MerchantUser,
    models.ProviderConnection,
    models.Payment,
    models.PaymentEvent,
    models.Device,
    models.DeviceSession,
    models.VoiceNotification,
    models.AuditLog,
    models.OutboxEvent,
]


def test_all_eleven_canonical_models_registered():
    """1. Verify exactly 11 canonical models are defined and distinct."""
    assert len(CANONICAL_MODEL_CLASSES) == 11
    class_names = {cls.__name__ for cls in CANONICAL_MODEL_CLASSES}
    assert class_names == {
        "User",
        "Merchant",
        "MerchantUser",
        "ProviderConnection",
        "Payment",
        "PaymentEvent",
        "Device",
        "DeviceSession",
        "VoiceNotification",
        "AuditLog",
        "OutboxEvent",
    }


def test_all_expected_tables_in_canonical_metadata():
    """2. Verify Base.metadata contains the canonical tables."""
    metadata_tables = set(Base.metadata.tables.keys())
    assert CANONICAL_TABLE_NAMES.issubset(metadata_tables)


def test_no_legacy_tables_in_canonical_metadata():
    """3. Verify zero legacy prototype tables leaked into canonical Base.metadata."""
    legacy_tables = set(LegacyBase.metadata.tables.keys())
    canonical_tables = set(Base.metadata.tables.keys())

    # Ensure none of the legacy prototype tables exist in canonical metadata
    overlap = canonical_tables.intersection({
        "customers",
        "legacy_payments",
        "legacy_webhook_events",
        "merchant_profiles",
        "products",
        "recovery_actions",
        "sale_items",
        "sales",
    })
    assert len(overlap) == 0, f"Legacy tables leaked into canonical Base.metadata: {overlap}"


def test_alembic_can_locate_migration():
    """4. Verify Alembic config and ScriptDirectory discover migration scripts."""
    ini_path = os.path.abspath("backend/alembic.ini")
    config = Config(ini_path)
    script_dir = ScriptDirectory.from_config(config)

    revisions = list(script_dir.walk_revisions())
    assert len(revisions) >= 1
    rev_ids = [rev.revision for rev in revisions]
    assert "0001_initial_schema" in rev_ids


def test_migration_head_is_correct():
    """5. Verify the current head revision is an expected migration head."""
    ini_path = os.path.abspath("backend/alembic.ini")
    config = Config(ini_path)
    script_dir = ScriptDirectory.from_config(config)

    head = script_dir.get_current_head()
    assert head in ["0001_initial_schema", "0002_user_sessions"]


def test_postgresql_ddl_generation_succeeds():
    """6. Verify all 11 canonical tables compile cleanly to PostgreSQL DDL."""
    pg_dialect = postgresql.dialect()
    for table_name, table in Base.metadata.tables.items():
        ddl = str(CreateTable(table).compile(dialect=pg_dialect))
        assert f"CREATE TABLE {table_name}" in ddl


def test_important_unique_constraints_exist():
    """7. Verify primary idempotency and security unique constraints."""
    metadata = Base.metadata

    # 1. User email uniqueness
    users = metadata.tables["users"]
    assert users.c.email.unique is True or any(idx.unique for idx in users.indexes if "email" in [c.name for c in idx.columns])

    # 2. MerchantUser membership uniqueness
    merchant_users = metadata.tables["merchant_users"]
    mu_uqs = [set(c.name for c in uq.columns) for uq in merchant_users.constraints if hasattr(uq, "columns")]
    assert {"merchant_id", "user_id"} in mu_uqs

    # 3. ProviderConnection uniqueness
    pc = metadata.tables["provider_connections"]
    pc_uqs = [set(c.name for c in uq.columns) for uq in pc.constraints if hasattr(uq, "columns")]
    assert {"merchant_id", "provider", "provider_account_reference"} in pc_uqs

    # 4. Payment Level 2 Idempotency uniqueness
    payments = metadata.tables["payments"]
    pay_uqs = [set(c.name for c in uq.columns) for uq in payments.constraints if hasattr(uq, "columns")]
    assert {"provider", "provider_payment_id"} in pay_uqs

    # 5. PaymentEvent Level 1 Idempotency uniqueness
    pe = metadata.tables["payment_events"]
    pe_uqs = [set(c.name for c in uq.columns) for uq in pe.constraints if hasattr(uq, "columns")]
    assert {"provider", "event_id"} in pe_uqs

    # 6. DeviceSession token hash uniqueness
    ds = metadata.tables["device_sessions"]
    ds_uqs = [set(c.name for c in uq.columns) for uq in ds.constraints if hasattr(uq, "columns")]
    assert {"session_token_hash"} in ds_uqs


def test_important_foreign_keys_and_delete_behavior():
    """8. Verify foreign keys and cascade/restrict safety."""
    metadata = Base.metadata

    # Payments must RESTRICT delete to protect financial records
    pay_fks = {fk.target_fullname: fk for fk in metadata.tables["payments"].foreign_keys}
    assert "merchants.id" in pay_fks
    assert pay_fks["merchants.id"].ondelete == "RESTRICT"

    # PaymentEvents must SET NULL to preserve audit trail
    pe_fks = {fk.target_fullname: fk for fk in metadata.tables["payment_events"].foreign_keys}
    assert "merchants.id" in pe_fks
    assert pe_fks["merchants.id"].ondelete == "SET NULL"
    assert "payments.id" in pe_fks
    assert pe_fks["payments.id"].ondelete == "SET NULL"

    # AuditLogs must SET NULL to prevent log destruction
    al_fks = {fk.target_fullname: fk for fk in metadata.tables["audit_logs"].foreign_keys}
    assert "merchants.id" in al_fks
    assert al_fks["merchants.id"].ondelete == "SET NULL"

    # Devices and memberships cascade on merchant deletion
    dev_fks = {fk.target_fullname: fk for fk in metadata.tables["devices"].foreign_keys}
    assert "merchants.id" in dev_fks
    assert dev_fks["merchants.id"].ondelete == "CASCADE"


def test_important_indexes_exist():
    """9. Verify critical query and worker indexes."""
    metadata = Base.metadata

    # Outbox worker claim index: (status, available_at, created_at)
    outbox_idx_cols = [[c.name for c in idx.columns] for idx in metadata.tables["outbox_events"].indexes]
    assert ["status", "available_at", "created_at"] in outbox_idx_cols

    # Payments merchant lookup: (merchant_id, created_at) and (merchant_id, status, created_at)
    pay_idx_cols = [[c.name for c in idx.columns] for idx in metadata.tables["payments"].indexes]
    assert ["merchant_id", "created_at"] in pay_idx_cols
    assert ["merchant_id", "status", "created_at"] in pay_idx_cols


def test_amount_minor_is_bigint():
    """10. Verify amount_minor is BigInteger and compiles to BIGINT in PostgreSQL."""
    col = Base.metadata.tables["payments"].c.amount_minor
    assert isinstance(col.type, BigInteger)
    pg_ddl = col.type.compile(dialect=postgresql.dialect())
    assert pg_ddl == "BIGINT"


def test_postgresql_jsonb_fields():
    """11. Verify JSONB fields on AuditLog and OutboxEvent."""
    pg_dialect = postgresql.dialect()

    audit_meta_type = Base.metadata.tables["audit_logs"].c.metadata.type.compile(dialect=pg_dialect)
    assert audit_meta_type == "JSONB"

    outbox_payload_type = Base.metadata.tables["outbox_events"].c.payload.type.compile(dialect=pg_dialect)
    assert outbox_payload_type == "JSONB"


def test_postgresql_inet_field():
    """12. Verify INET field on AuditLog."""
    ip_type = Base.metadata.tables["audit_logs"].c.ip_address.type.compile(dialect=postgresql.dialect())
    assert ip_type == "INET"


def test_live_postgresql_schema_matches_canonical_models():
    """13. Integration check: verify live PostgreSQL schema matches canonical models."""
    if not settings.DATABASE_URL.startswith("postgresql"):
        pytest.skip("PostgreSQL DATABASE_URL not configured")

    try:
        engine = create_engine(settings.DATABASE_URL)
        insp = inspect(engine)
        db_tables = set(insp.get_table_names())
    except Exception as exc:
        pytest.skip(f"Live PostgreSQL unreachable: {exc}")

    # Confirm all 11 canonical tables exist in live PostgreSQL
    assert CANONICAL_TABLE_NAMES.issubset(db_tables)
    assert "alembic_version" in db_tables

    # Confirm payment amount_minor is bigint in live PostgreSQL
    pay_cols = {c["name"]: c for c in insp.get_columns("payments")}
    assert "amount_minor" in pay_cols
    assert str(pay_cols["amount_minor"]["type"]).upper() == "BIGINT"
