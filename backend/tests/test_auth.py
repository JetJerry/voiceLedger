import pytest
from backend.app.models import Merchant


def test_admin_login_success(client):
    """Test successful admin login."""
    payload = {
        "username": "admin",
        "password": "admin123",
        "role": "admin",
    }
    res = client.post("/api/auth/login", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["role"] == "admin"
    assert data["user"]["role"] == "admin"
    assert data["token"].startswith("admin-token-")


def test_admin_login_invalid_password(client):
    """Test admin login with wrong password."""
    payload = {
        "username": "admin",
        "password": "wrongpassword",
        "role": "admin",
    }
    res = client.post("/api/auth/login", json=payload)
    assert res.status_code == 401
    assert "Invalid admin credentials" in res.json()["detail"]


def test_merchant_login_and_terminal_context(client, db_session):
    """Test merchant login sets active store context."""
    m = Merchant(
        name="Gupta General Store",
        username="gupta_store",
        password="password123",
        business_type="Kirana & Retail",
        is_active=True,
        is_current_active=False,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)

    payload = {
        "username": "gupta_store",
        "password": "password123",
        "role": "merchant",
    }
    res = client.post("/api/auth/login", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["role"] == "merchant"
    assert data["user"]["name"] == "Gupta General Store"
    assert data["user"]["username"] == "gupta_store"

    # Verify merchant is now active terminal in DB
    db_session.refresh(m)
    assert m.is_current_active is True


def test_merchant_register_new_store(client, db_session):
    """Test registering a brand new shopkeeper store with credentials."""
    payload = {
        "name": "Apollo Pharmacy Outlet",
        "username": "apollo_pharm",
        "password": "apollo_pass_123",
        "business_type": "Pharmacy & Medical",
        "phone": "+919876599999",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["role"] == "merchant"
    assert data["user"]["name"] == "Apollo Pharmacy Outlet"
    assert data["user"]["business_type"] == "Pharmacy & Medical"

    # Try duplicate registration
    res_dup = client.post("/api/auth/register", json=payload)
    assert res_dup.status_code == 400


def test_get_demo_accounts(client):
    """Test getting demo accounts for 1-click login on login portal."""
    res = client.get("/api/auth/demo-accounts")
    assert res.status_code == 200
    data = res.json()
    assert "admin" in data
    assert data["admin"]["username"] == "admin"
    assert "merchants" in data
    assert len(data["merchants"]) > 0
