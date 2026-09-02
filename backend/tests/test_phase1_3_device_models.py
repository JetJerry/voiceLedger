import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from backend.app.models.merchant import Merchant
from backend.app.models.device import Device, DeviceStatus, DeviceType
from backend.app.models.device_session import DeviceSession, DeviceSessionStatus


def test_device_creation_and_defaults():
    """Verify Device model instantiates with UUID, default status PAIRING, and SOUNDBOX type."""
    merchant_id = uuid.uuid4()
    device = Device(
        merchant_id=merchant_id,
        device_name="Counter 1 Soundbox",
    )
    assert isinstance(device.id, uuid.UUID)
    assert device.merchant_id == merchant_id
    assert device.device_name == "Counter 1 Soundbox"
    assert device.device_type == DeviceType.SOUNDBOX.value
    assert device.status == DeviceStatus.PAIRING.value
    assert device.public_key is None
    assert device.device_token_hash is None
    assert device.last_seen_at is None
    assert isinstance(device.created_at, datetime)
    assert isinstance(device.updated_at, datetime)


def test_device_type_and_status_validation():
    """Verify device status and hardware type constraints."""
    merchant_id = uuid.uuid4()

    valid_statuses = [
        DeviceStatus.PAIRING,
        DeviceStatus.ACTIVE,
        DeviceStatus.OFFLINE,
        DeviceStatus.DISABLED,
        DeviceStatus.REVOKED,
    ]
    for s in valid_statuses:
        d = Device(merchant_id=merchant_id, device_name="D", status=s)
        assert d.status == s.value

    valid_types = [
        DeviceType.SOUNDBOX,
        DeviceType.ANDROID_APP,
        DeviceType.POS_TERMINAL,
        DeviceType.OTHER,
    ]
    for t in valid_types:
        d = Device(merchant_id=merchant_id, device_name="D", device_type=t)
        assert d.device_type == t.value

    # Reject invalid status
    with pytest.raises(ValueError, match="Invalid device status"):
        Device(merchant_id=merchant_id, device_name="D", status="ONLINE")

    # Reject invalid device type
    with pytest.raises(ValueError, match="Invalid device type"):
        Device(merchant_id=merchant_id, device_name="D", device_type="SMARTWATCH")


def test_device_merchant_relationship_and_foreign_key():
    """Verify bidirectional relationship between Merchant and Device."""
    merchant = Merchant(name="South Indian Tiffin")
    device = Device(
        device_name="Kitchen Soundbox",
        device_type=DeviceType.SOUNDBOX,
        merchant=merchant,
    )
    assert device.merchant is merchant
    assert device in merchant.devices

    # Verify foreign key constraint details
    table = Device.__table__
    fks = {fk.target_fullname: fk for fk in table.foreign_keys}
    assert "merchants.id" in fks
    assert fks["merchants.id"].ondelete == "CASCADE"
    assert table.c.merchant_id.nullable is False


def test_device_session_creation_and_lifecycle():
    """Verify DeviceSession creation, token hash, active/expired lifecycle checks."""
    device_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    future_expiry = now + timedelta(hours=24)

    session = DeviceSession(
        device_id=device_id,
        session_token_hash="5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
        expires_at=future_expiry,
        ip_address="192.168.1.100",
        user_agent="VoiceLedger-Soundbox-Firmware/1.0",
    )
    assert isinstance(session.id, uuid.UUID)
    assert session.device_id == device_id
    assert session.status == DeviceSessionStatus.CONNECTED.value
    assert session.expires_at == future_expiry
    assert session.is_active is True
    assert session.is_expired is False


def test_device_session_expiration():
    """Verify session expiry detection."""
    device_id = uuid.uuid4()
    past_expiry = datetime.now(timezone.utc) - timedelta(minutes=5)

    expired_session = DeviceSession(
        device_id=device_id,
        session_token_hash="hash123",
        expires_at=past_expiry,
    )
    assert expired_session.is_expired is True
    assert expired_session.is_active is False


def test_device_session_revocation():
    """Verify session revocation timestamp and inactive state."""
    device_id = uuid.uuid4()
    future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    session = DeviceSession(
        device_id=device_id,
        session_token_hash="hash456",
        expires_at=future_expiry,
        status=DeviceSessionStatus.REVOKED,
        revoked_at=datetime.now(timezone.utc),
    )
    assert session.status == DeviceSessionStatus.REVOKED.value
    assert session.revoked_at is not None
    assert session.is_active is False


def test_device_to_session_relationship():
    """Verify bidirectional relationship between Device and DeviceSession."""
    device = Device(
        merchant_id=uuid.uuid4(),
        device_name="Billing Soundbox",
    )
    future_expiry = datetime.now(timezone.utc) + timedelta(hours=12)
    session = DeviceSession(
        session_token_hash="session_hash_789",
        expires_at=future_expiry,
    )

    device.sessions.append(session)
    assert session in device.sessions
    assert session.device is device

    # Session cascade delete configuration
    table = DeviceSession.__table__
    fks = {fk.target_fullname: fk for fk in table.foreign_keys}
    assert "devices.id" in fks
    assert fks["devices.id"].ondelete == "CASCADE"


def test_credential_and_repr_sanitization():
    """Verify that sensitive public keys, token hashes, and secrets are NEVER exposed in repr."""
    fake_pubkey = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A\n-----END PUBLIC KEY-----"
    fake_token_hash = "d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2"

    device = Device(
        merchant_id=uuid.uuid4(),
        device_name="Protected Terminal",
        public_key=fake_pubkey,
        device_token_hash=fake_token_hash,
    )
    device_repr = repr(device)
    assert "Protected Terminal" in device_repr
    assert "PUBLIC KEY" not in device_repr
    assert fake_token_hash not in device_repr

    session = DeviceSession(
        device_id=device.id,
        session_token_hash=fake_token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session_repr = repr(session)
    assert fake_token_hash not in session_repr


def test_device_session_unique_token_constraint():
    """Verify unique constraint on session_token_hash to prevent session collision/replay."""
    table = DeviceSession.__table__
    unique_col_sets = [
        set(c.name for c in uq.columns)
        for uq in table.constraints
        if hasattr(uq, "columns") and uq.name != "device_sessions_pkey"
    ]
    assert {"session_token_hash"} in unique_col_sets


def test_device_not_a_payment_authority():
    """Architectural invariant check: Device must NEVER have payment creation/confirmation attributes."""
    device_cols = set(Device.__table__.columns.keys())
    prohibited_financial_fields = {
        "amount",
        "amount_minor",
        "currency",
        "payment_status",
        "payment_id",
        "is_paid",
        "confirm_payment",
        "capture_payment",
    }
    overlap = device_cols.intersection(prohibited_financial_fields)
    assert len(overlap) == 0, f"Device model illegally contains financial fields: {overlap}"


def test_device_merchant_isolation_boundary():
    """Verify that Device cannot be associated with multiple merchants and Session strictly references Device."""
    # 1. Device belongs strictly to exactly one merchant
    assert Device.__table__.c.merchant_id.nullable is False

    # 2. DeviceSession does NOT have an independent merchant_id that could diverge from device.merchant_id
    assert "merchant_id" not in DeviceSession.__table__.columns
    assert DeviceSession.__table__.c.device_id.nullable is False


def test_postgresql_ddl_compilation():
    """Verify DDL compiles cleanly for Device and DeviceSession using PostgreSQL dialect."""
    pg_dialect = postgresql.dialect()

    device_ddl = str(CreateTable(Device.__table__).compile(dialect=pg_dialect))
    assert "CREATE TABLE devices" in device_ddl
    assert "UUID" in device_ddl
    assert "REFERENCES merchants (id) ON DELETE CASCADE" in device_ddl
    assert "CHECK (status IN ('PAIRING', 'ACTIVE', 'OFFLINE', 'DISABLED', 'REVOKED'))" in device_ddl

    session_ddl = str(CreateTable(DeviceSession.__table__).compile(dialect=pg_dialect))
    assert "CREATE TABLE device_sessions" in session_ddl
    assert "session_token_hash VARCHAR(64) NOT NULL" in session_ddl
    assert "REFERENCES devices (id) ON DELETE CASCADE" in session_ddl
    assert "UNIQUE (session_token_hash)" in session_ddl
