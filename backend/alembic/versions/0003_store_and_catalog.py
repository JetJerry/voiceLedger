"""Store catalog, inventory, sales ledger, and merchant profiles schema

Revision ID: 0003_store_and_catalog
Revises: 0002_user_sessions
Create Date: 2026-09-04 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_store_and_catalog"
down_revision: Union[str, None] = "0002_user_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. products table
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("category", sa.String(length=100), server_default="General", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=50), server_default="piece", nullable=True),
        sa.Column("stock_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("track_inventory", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["merchant_id"],
            ["merchants.id"],
            name="fk_products_merchant_id_merchants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
    )
    op.create_index("ix_products_merchant_id", "products", ["merchant_id"], unique=False)
    op.create_index("ix_products_name", "products", ["name"], unique=False)
    op.create_index("ix_products_category", "products", ["category"], unique=False)
    op.create_index("ix_products_is_active", "products", ["is_active"], unique=False)
    op.create_index("ix_products_merchant_name", "products", ["merchant_id", "name"], unique=False)
    op.create_index("ix_products_merchant_category", "products", ["merchant_id", "category"], unique=False)
    op.create_index("ix_products_merchant_active", "products", ["merchant_id", "is_active"], unique=False)

    # 2. sales table
    op.create_table(
        "sales",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_phone", sa.String(length=50), nullable=True),
        sa.Column("total_amount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("received_amount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("outstanding_amount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), server_default="PENDING", nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("razorpay_order_id", sa.String(length=100), nullable=True),
        sa.Column("razorpay_payment_link_id", sa.String(length=100), nullable=True),
        sa.Column("razorpay_payment_link_url", sa.String(length=500), nullable=True),
        sa.Column("raw_voice_transcript", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["merchant_id"],
            ["merchants.id"],
            name="fk_sales_merchant_id_merchants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name="fk_sales_payment_id_payments",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sales"),
    )
    op.create_index("ix_sales_merchant_id", "sales", ["merchant_id"], unique=False)
    op.create_index("ix_sales_customer_name", "sales", ["customer_name"], unique=False)
    op.create_index("ix_sales_status", "sales", ["status"], unique=False)
    op.create_index("ix_sales_payment_id", "sales", ["payment_id"], unique=False)
    op.create_index("ix_sales_razorpay_order_id", "sales", ["razorpay_order_id"], unique=False)
    op.create_index("ix_sales_razorpay_payment_link_id", "sales", ["razorpay_payment_link_id"], unique=False)
    op.create_index("ix_sales_created_at", "sales", ["created_at"], unique=False)
    op.create_index("ix_sales_merchant_status", "sales", ["merchant_id", "status"], unique=False)
    op.create_index("ix_sales_merchant_created", "sales", ["merchant_id", "created_at"], unique=False)

    # 3. sale_items table
    op.create_table(
        "sale_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sale_id", sa.String(length=50), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sales.id"],
            name="fk_sale_items_sale_id_sales",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_sale_items_product_id_products",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sale_items"),
    )
    op.create_index("ix_sale_items_sale_id", "sale_items", ["sale_id"], unique=False)
    op.create_index("ix_sale_items_product_id", "sale_items", ["product_id"], unique=False)

    # 4. merchant_profiles table
    op.create_table(
        "merchant_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["merchant_id"],
            ["merchants.id"],
            name="fk_merchant_profiles_merchant_id_merchants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_merchant_profiles"),
        sa.UniqueConstraint("merchant_id", name="uq_merchant_profiles_merchant_id"),
    )
    op.create_index("ix_merchant_profiles_merchant_id", "merchant_profiles", ["merchant_id"], unique=False)


def downgrade() -> None:
    op.drop_table("merchant_profiles")
    op.drop_table("sale_items")
    op.drop_table("sales")
    op.drop_table("products")
