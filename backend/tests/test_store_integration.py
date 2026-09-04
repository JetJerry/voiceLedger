"""
Targeted Integration Tests for VoiceLedger Store, Catalog, and Sales.

Verifies:
1. Product CRUD with merchant tenant isolation.
2. Cross-merchant IDOR protection (Merchant A cannot access Merchant B's catalog or sales).
3. Inventory stock adjustments and audit trail.
4. Multi-item Sale creation, minor-unit calculations, and status tracking.
5. Sales period analytics summary.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.user import User
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.core.security import create_access_token, hash_password

pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def db():
    """Transactional session rolled back cleanly after each test."""
    conn = pg_engine.connect()
    trans = conn.begin()
    session = PGTestSessionLocal(bind=conn)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def client(db):
    """FastAPI TestClient with overridden get_db to share transaction."""
    from backend.app.db.session import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def merchant_a(db):
    """Fixture providing Merchant A and its authenticated user."""
    uid = uuid.uuid4()
    mid = uuid.uuid4()

    user = User(
        id=uid,
        email=f"owner_{uid.hex[:6]}@storea.com",
        hashed_password=hash_password("password123"),
        full_name="Owner A",
        is_active=True,
    )
    merchant = Merchant(
        id=mid,
        name="Store Alpha",
        business_type="Kirana & Retail",
        status="ACTIVE",
        currency="INR",
    )
    membership = MerchantUser(
        id=uuid.uuid4(),
        merchant_id=mid,
        user_id=uid,
        role="OWNER",
    )
    db.add_all([user, merchant, membership])
    db.flush()

    token = create_access_token(user_id=user.id, email=user.email)
    return merchant, user, token


@pytest.fixture
def merchant_b(db):
    """Fixture providing Merchant B and its authenticated user."""
    uid = uuid.uuid4()
    mid = uuid.uuid4()

    user = User(
        id=uid,
        email=f"owner_{uid.hex[:6]}@storeb.com",
        hashed_password=hash_password("password123"),
        full_name="Owner B",
        is_active=True,
    )
    merchant = Merchant(
        id=mid,
        name="Store Beta",
        business_type="Cafe & Restaurant",
        status="ACTIVE",
        currency="INR",
    )
    membership = MerchantUser(
        id=uuid.uuid4(),
        merchant_id=mid,
        user_id=uid,
        role="OWNER",
    )
    db.add_all([user, merchant, membership])
    db.flush()

    token = create_access_token(user_id=user.id, email=user.email)
    return merchant, user, token


def test_product_crud_and_tenant_isolation(client, merchant_a, merchant_b):
    m_a, _, token_a = merchant_a
    m_b, _, token_b = merchant_b

    headers_a = {"Authorization": f"Bearer {token_a}", "X-Merchant-ID": str(m_a.id)}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Merchant-ID": str(m_b.id)}

    # 1. Merchant A creates product
    res = client.post(
        "/api/v1/store/products",
        headers=headers_a,
        json={
            "name": "Masala Chai",
            "price": 25.0,
            "category": "Beverages",
            "unit": "cup",
            "stock_quantity": 100,
            "track_inventory": True,
        },
    )
    assert res.status_code == 201
    prod_a = res.json()
    assert prod_a["name"] == "masala chai"
    assert prod_a["price"] == 25.0
    assert prod_a["price_minor"] == 2500
    prod_id = prod_a["id"]

    # 2. Merchant A lists products -> finds it
    res_list_a = client.get("/api/v1/store/products", headers=headers_a)
    assert res_list_a.status_code == 200
    items_a = res_list_a.json()
    assert len(items_a) == 1
    assert items_a[0]["id"] == prod_id

    # 3. Merchant B lists products -> isolated (0 products)
    res_list_b = client.get("/api/v1/store/products", headers=headers_b)
    assert res_list_b.status_code == 200
    items_b = res_list_b.json()
    assert len(items_b) == 0

    # 4. Merchant B attempts to fetch Merchant A's product -> 404 (IDOR protected)
    res_idor = client.get(f"/api/v1/store/products/{prod_id}", headers=headers_b)
    assert res_idor.status_code == 404

    # 5. Inventory adjustment for Merchant A
    res_inv = client.post(
        "/api/v1/store/inventory/adjust",
        headers=headers_a,
        json={
            "product_id": prod_id,
            "delta": 20,
            "reason": "restock",
        },
    )
    assert res_inv.status_code == 200
    inv_data = res_inv.json()
    assert inv_data["previous_quantity"] == 100
    assert inv_data["new_quantity"] == 120


def test_sales_creation_and_analytics(client, merchant_a):
    m_a, _, token_a = merchant_a
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Merchant-ID": str(m_a.id)}

    # Create 2 products
    res_p1 = client.post(
        "/api/v1/store/products",
        headers=headers_a,
        json={"name": "Samosa", "price": 20.0, "category": "Snacks"},
    )
    res_p2 = client.post(
        "/api/v1/store/products",
        headers=headers_a,
        json={"name": "Cold Coffee", "price": 60.0, "category": "Beverages"},
    )
    p1 = res_p1.json()
    p2 = res_p2.json()

    # Create a Sale
    sale_payload = {
        "customer_name": "Rahul Verma",
        "customer_phone": "+919876543210",
        "auto_create_payment_link": False,
        "items": [
            {"product_name": "Samosa", "quantity": 3, "unit_price": 20.0, "product_id": p1["id"]},
            {"product_name": "Cold Coffee", "quantity": 2, "unit_price": 60.0, "product_id": p2["id"]},
        ],
    }
    res_sale = client.post("/api/v1/store/sales", headers=headers_a, json=sale_payload)
    assert res_sale.status_code == 201
    sale_data = res_sale.json()
    # 3 * 20 + 2 * 60 = 60 + 120 = 180
    assert sale_data["total_amount"] == 180.0
    assert sale_data["outstanding_amount"] == 180.0
    assert sale_data["status"] == "PENDING"
    assert len(sale_data["items"]) == 2

    # Query analytics summary
    res_analytics = client.get("/api/v1/store/analytics/summary", headers=headers_a)
    assert res_analytics.status_code == 200
    analytics = res_analytics.json()
    today_stats = analytics["periods"]["today"]
    assert today_stats["orders_count"] == 1
    assert today_stats["total_gmv"] == 180.0
    assert today_stats["total_outstanding"] == 180.0
