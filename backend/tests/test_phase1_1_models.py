import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import inspect
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from backend.app.models.user import User
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.models.provider_connection import ProviderConnection


def test_user_model_creation_and_defaults():
    """Verify User model instantiates with UUID, timestamps, and default booleans."""
    user = User(
        email="merchant_admin@example.com",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$fakehash123",
        full_name="Rajesh Sharma",
    )
    assert isinstance(user.id, uuid.UUID)
    assert user.email == "merchant_admin@example.com"
    assert user.full_name == "Rajesh Sharma"
    assert user.is_active is True
    assert user.is_superuser is False
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)

    # Security check: repr must not leak hashed password
    repr_str = repr(user)
    assert "merchant_admin@example.com" in repr_str
    assert "fakehash123" not in repr_str
    assert "password" not in repr_str.lower()


def test_merchant_model_creation_and_defaults():
    """Verify Merchant model instantiates with UUID, status, currency, and defaults."""
    merchant = Merchant(
        name="Sharma Electronics",
        business_type="Retail Electronics",
    )
    assert isinstance(merchant.id, uuid.UUID)
    assert merchant.name == "Sharma Electronics"
    assert merchant.business_type == "Retail Electronics"
    assert merchant.status == "ACTIVE"
    assert merchant.currency == "INR"
    assert isinstance(merchant.created_at, datetime)
    assert isinstance(merchant.updated_at, datetime)

    repr_str = repr(merchant)
    assert "Sharma Electronics" in repr_str
    assert "ACTIVE" in repr_str


def test_merchant_user_association_and_roles():
    """Verify MerchantUser membership association, default role, and bidirectional links."""
    merchant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    membership = MerchantUser(
        merchant_id=merchant_id,
        user_id=user_id,
        role="OWNER",
    )
    assert isinstance(membership.id, uuid.UUID)
    assert membership.merchant_id == merchant_id
    assert membership.user_id == user_id
    assert membership.role == "OWNER"
    assert isinstance(membership.created_at, datetime)

    # Default role should be STAFF if not explicitly set
    default_membership = MerchantUser(merchant_id=merchant_id, user_id=user_id)
    assert default_membership.role == "STAFF"


def test_provider_connection_model():
    """Verify ProviderConnection stores provider reference and status."""
    merchant_id = uuid.uuid4()
    conn = ProviderConnection(
        merchant_id=merchant_id,
        provider="razorpay",
        provider_account_reference="acc_rzp_prod_12345",
        status="ACTIVE",
        encrypted_credentials_reference="vault://secrets/merchants/sharma/razorpay",
    )
    assert isinstance(conn.id, uuid.UUID)
    assert conn.merchant_id == merchant_id
    assert conn.provider == "razorpay"
    assert conn.provider_account_reference == "acc_rzp_prod_12345"
    assert conn.status == "ACTIVE"
    assert conn.encrypted_credentials_reference == "vault://secrets/merchants/sharma/razorpay"

    repr_str = repr(conn)
    assert "razorpay" in repr_str
    assert "ACTIVE" in repr_str


def test_in_memory_relationship_wiring():
    """Verify bidirectional relationship binding between Merchant, User, and MerchantUser."""
    user = User(
        email="owner@store.com",
        hashed_password="hash",
        full_name="Store Owner",
    )
    merchant = Merchant(name="Corner Store")

    membership = MerchantUser(
        merchant=merchant,
        user=user,
        role="OWNER",
    )

    assert membership in user.merchant_memberships
    assert membership in merchant.user_memberships
    assert membership.user is user
    assert membership.merchant is merchant

    # Wire ProviderConnection to Merchant
    provider_conn = ProviderConnection(
        merchant=merchant,
        provider="razorpay",
        provider_account_reference="mid_123456",
    )
    assert provider_conn in merchant.provider_connections
    assert provider_conn.merchant is merchant


def test_table_metadata_and_foreign_keys():
    """Inspect SQLAlchemy metadata for primary keys, foreign keys, cascades, and nullability."""
    # 1. users table
    users_table = User.__table__
    assert users_table.name == "users"
    assert users_table.c.id.primary_key is True
    assert users_table.c.email.nullable is False
    assert users_table.c.email.unique is True
    assert users_table.c.hashed_password.nullable is False

    # 2. merchants table
    merchants_table = Merchant.__table__
    assert merchants_table.name == "merchants"
    assert merchants_table.c.id.primary_key is True
    assert merchants_table.c.name.nullable is False
    assert merchants_table.c.status.nullable is False

    # 3. merchant_users table
    mu_table = MerchantUser.__table__
    assert mu_table.name == "merchant_users"
    assert mu_table.c.id.primary_key is True
    assert mu_table.c.merchant_id.nullable is False
    assert mu_table.c.user_id.nullable is False

    # Verify Foreign Keys and ON DELETE CASCADE
    fks = {fk.target_fullname: fk for fk in mu_table.foreign_keys}
    assert "merchants.id" in fks
    assert fks["merchants.id"].ondelete == "CASCADE"
    assert "users.id" in fks
    assert fks["users.id"].ondelete == "CASCADE"

    # 4. provider_connections table
    pc_table = ProviderConnection.__table__
    assert pc_table.name == "provider_connections"
    assert pc_table.c.id.primary_key is True
    assert pc_table.c.merchant_id.nullable is False
    assert pc_table.c.provider.nullable is False
    assert pc_table.c.provider_account_reference.nullable is False

    pc_fks = {fk.target_fullname: fk for fk in pc_table.foreign_keys}
    assert "merchants.id" in pc_fks
    assert pc_fks["merchants.id"].ondelete == "CASCADE"


def test_unique_constraints_and_indexes():
    """Verify unique constraints and indexes defined on the foundation models."""
    mu_table = MerchantUser.__table__
    # Unique constraint on (merchant_id, user_id)
    unique_col_sets = [
        set(c.name for c in uq.columns)
        for uq in mu_table.constraints
        if hasattr(uq, "columns") and uq.name != "merchant_users_pkey"
    ]
    assert {"merchant_id", "user_id"} in unique_col_sets

    # Provider connections unique constraint on (merchant_id, provider, provider_account_reference)
    pc_table = ProviderConnection.__table__
    pc_unique_col_sets = [
        set(c.name for c in uq.columns)
        for uq in pc_table.constraints
        if hasattr(uq, "columns") and uq.name != "provider_connections_pkey"
    ]
    assert {"merchant_id", "provider", "provider_account_reference"} in pc_unique_col_sets

    # Check indexes on provider_connections
    pc_index_col_sets = [set(c.name for c in idx.columns) for idx in pc_table.indexes]
    assert {"merchant_id", "provider"} in pc_index_col_sets


def test_postgresql_ddl_compilation():
    """Verify all models generate valid PostgreSQL DDL with proper types."""
    pg_dialect = postgresql.dialect()

    for model in [User, Merchant, MerchantUser, ProviderConnection]:
        ddl = str(CreateTable(model.__table__).compile(dialect=pg_dialect))
        assert "UUID" in ddl
        assert "CREATE TABLE" in ddl
        if model in [MerchantUser, ProviderConnection]:
            assert "REFERENCES merchants (id) ON DELETE CASCADE" in ddl
