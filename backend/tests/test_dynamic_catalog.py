import pytest
from backend.app.models.legacy import LegacyMerchant as Merchant, Product


def test_dynamic_attributes_fruit_seller(client, db_session):
    """Test dynamic attributes for a fruit & veg seller (origin, shelf_life, organic)."""
    m = Merchant(name="Green Apple Fresh Mart", business_type="Fruits & Vegetables", is_active=True, is_current_active=True)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)

    payload = {
        "name": "Kashmiri Royal Apple",
        "price": 180.0,
        "category": "Fruits",
        "unit": "kg",
        "description": "Crisp, sweet organic apples from Kashmir",
        "attributes": {
            "origin": "Kashmir",
            "organic": True,
            "shelf_life": "7 days",
            "grade": "Grade A",
        }
    }
    res = client.post("/api/sales/catalog/products", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "kashmiri royal apple"
    assert data["price"] == 180.0
    assert data["unit"] == "kg"
    assert data["attributes"]["origin"] == "Kashmir"
    assert data["attributes"]["organic"] is True
    assert data["attributes"]["grade"] == "Grade A"


def test_dynamic_attributes_pharmacy(client, db_session):
    """Test dynamic attributes for a pharmacy store (dosage, manufacturer, expiry, prescription)."""
    payload = {
        "name": "Augmentin 625 Duo",
        "price": 210.50,
        "category": "Antibiotics",
        "unit": "strip",
        "description": "Amoxicillin and Potassium Clavulanate",
        "attributes": {
            "dosage": "625mg",
            "manufacturer": "GSK",
            "expiry_date": "2027-08",
            "rx_required": True,
            "tablets_per_strip": 10,
        }
    }
    res = client.post("/api/sales/catalog/products", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "augmentin 625 duo"
    assert data["attributes"]["dosage"] == "625mg"
    assert data["attributes"]["manufacturer"] == "GSK"
    assert data["attributes"]["rx_required"] is True


def test_dynamic_attributes_update(client, db_session):
    """Test updating dynamic attributes on an existing product."""
    payload = {
        "name": "Premium Cotton Kurta",
        "price": 899.0,
        "category": "Apparel",
        "unit": "piece",
        "attributes": {"size": "L", "color": "Navy Blue", "fabric": "Cotton"}
    }
    res = client.post("/api/sales/catalog/products", json=payload)
    assert res.status_code == 200
    prod_id = res.json()["id"]

    # Update size and price
    update_payload = {
        "price": 999.0,
        "attributes": {"size": "XL", "color": "Navy Blue", "fabric": "100% Khadi Cotton"}
    }
    res_update = client.put(f"/api/sales/catalog/products/{prod_id}", json=update_payload)
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["price"] == 999.0
    assert updated["attributes"]["size"] == "XL"
    assert updated["attributes"]["fabric"] == "100% Khadi Cotton"
