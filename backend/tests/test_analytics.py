import io
import uuid
import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.user import User
from backend.app.models.merchant import Merchant
from backend.app.models.merchant_user import MerchantUser
from backend.app.models.product import Product
from backend.app.models.sale import Sale, SaleItem
from backend.app.core.security import create_access_token, hash_password

pg_engine = create_engine(settings.DATABASE_URL)
PGTestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@pytest.fixture
def db():
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
def merchant_with_auth(db):
    u = User(
        email=f"analytics_{uuid.uuid4().hex[:6]}@test.local",
        hashed_password=hash_password("Pass123!"),
        full_name="Analytics Owner",
        is_active=True,
    )
    m = Merchant(
        name="Gupta Medical Store",
        business_type="Pharmacy & Medical",
        currency="INR",
        status="ACTIVE",
    )
    db.add_all([u, m])
    db.commit()

    mu = MerchantUser(
        merchant_id=m.id,
        user_id=u.id,
        role="OWNER",
    )
    db.add(mu)
    db.commit()

    token = create_access_token(user_id=u.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Merchant-ID": str(m.id),
    }
    return m, headers


def test_sales_analytics_periods(client, db, merchant_with_auth):
    """Test Day, Week, Month sales metrics computation."""
    m, headers = merchant_with_auth

    # Add sample catalog products
    p1 = Product(merchant_id=m.id, name="paracetamol 500", price_minor=2000, category="Pharmacy", is_active=True)
    p2 = Product(merchant_id=m.id, name="vitamin c", price_minor=5000, category="Pharmacy", is_active=True)
    db.add_all([p1, p2])
    db.commit()

    # Record 2 sales
    sale_payload1 = {
        "items": [{"product_name": "paracetamol 500", "quantity": 2, "unit_price": 20.0}],
        "customer_name": "Rahul Verma",
        "auto_create_payment_link": False,
    }
    res1 = client.post("/api/sales", json=sale_payload1, headers=headers)
    assert res1.status_code == 201

    sale_payload2 = {
        "items": [{"product_name": "vitamin c", "quantity": 1, "unit_price": 50.0}],
        "customer_name": "Priya Singh",
        "auto_create_payment_link": False,
    }
    res2 = client.post("/api/sales", json=sale_payload2, headers=headers)
    assert res2.status_code == 201

    # Fetch Analytics Summary
    res = client.get("/api/sales/analytics/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "periods" in data
    assert "today" in data["periods"]
    assert "week" in data["periods"]
    assert "month" in data["periods"]
    assert "all_time" in data["periods"]

    today = data["periods"]["today"]
    assert today["orders_count"] == 2
    assert today["total_gmv"] == 90.0
    assert today["total_outstanding"] == 90.0

    # Catalog summary
    assert "catalog_summary" in data
    assert len(data["catalog_summary"]) >= 2


def test_sales_analytics_excel_export(client, db, merchant_with_auth):
    """Test generating and exporting multi-sheet Excel spreadsheet (.xlsx)."""
    m, headers = merchant_with_auth

    res = client.get("/api/sales/analytics/export/excel", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "Content-Disposition" in res.headers
    assert "VoiceLedger_Report_" in res.headers["Content-Disposition"]

    # Verify openpyxl can parse the generated workbook
    wb = openpyxl.load_workbook(io.BytesIO(res.content))
    sheet_names = wb.sheetnames
    assert "Sales Analytics Summary" in sheet_names
    assert "Catalog & Products" in sheet_names
    assert "Sales Transactions Ledger" in sheet_names

    ws1 = wb["Sales Analytics Summary"]
    assert "Sales & Performance Report" in str(ws1["A1"].value)
