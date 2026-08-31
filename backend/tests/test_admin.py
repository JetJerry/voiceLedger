import pytest
from backend.app.models import Merchant, Product, Sale, SaleItem
from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.services.sales_service import sales_service


def test_admin_metrics_and_multi_merchant_isolation(client, db_session):
    """Test platform-wide metrics and multi-merchant separation."""
    # 1. Create two separate merchants
    m1 = Merchant(name="Vendor Kirana 1", business_type="Kirana & Grocery", is_active=True, is_current_active=True)
    m2 = Merchant(name="Vendor Bakery 2", business_type="Bakery & Sweets", is_active=True, is_current_active=False)
    db_session.add_all([m1, m2])
    db_session.commit()
    db_session.refresh(m1)
    db_session.refresh(m2)

    # 2. Add products
    p1 = Product(merchant_id=m1.id, name="rice 5kg", price=250.0, category="Grocery")
    p2 = Product(merchant_id=m2.id, name="chocolate cake", price=450.0, category="Bakery")
    db_session.add_all([p1, p2])
    db_session.commit()

    # 3. Create sales for m1
    s1 = Sale(id="sale_admin_1", merchant_id=m1.id, total_amount=500.0, received_amount=500.0, outstanding_amount=0.0, status="PAID")
    # Create sales for m2
    s2 = Sale(id="sale_admin_2", merchant_id=m2.id, total_amount=450.0, received_amount=200.0, outstanding_amount=250.0, status="PARTIAL")
    db_session.add_all([s1, s2])
    db_session.commit()

    # 4. Check Platform Metrics API
    res = client.get("/api/admin/metrics")
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["total_merchants"] >= 2
    assert metrics["total_gmv"] >= 950.0
    assert metrics["total_collected"] >= 700.0
    assert metrics["total_outstanding"] >= 250.0

    # 5. Check Merchant Directory API
    res_list = client.get("/api/admin/merchants")
    assert res_list.status_code == 200
    merchants = res_list.json()
    m1_data = next(m for m in merchants if m["id"] == m1.id)
    assert m1_data["name"] == "Vendor Kirana 1"
    assert m1_data["total_sales_volume"] == 500.0
    assert m1_data["is_current_active"] is True

    m2_data = next(m for m in merchants if m["id"] == m2.id)
    assert m2_data["name"] == "Vendor Bakery 2"
    assert m2_data["total_sales_volume"] == 450.0
    assert m2_data["total_outstanding"] == 250.0


def test_admin_onboard_and_switch_merchant(client, db_session):
    """Test onboarding a new merchant and switching the active terminal context."""
    # 1. Onboard new shopkeeper
    payload = {
        "name": "Sharma Electronics & Audio",
        "business_type": "Electronics & Mobile",
        "phone": "+919876599999",
        "currency": "INR",
    }
    res = client.post("/api/admin/merchants", json=payload)
    assert res.status_code == 200
    new_m = res.json()
    assert new_m["id"] is not None
    assert new_m["name"] == "Sharma Electronics & Audio"
    assert new_m["business_type"] == "Electronics & Mobile"

    # 2. Switch active store terminal to this new merchant
    res_switch = client.post(f"/api/admin/merchants/{new_m['id']}/set-active")
    assert res_switch.status_code == 200
    switch_data = res_switch.json()
    assert switch_data["status"] == "success"
    assert switch_data["active_merchant"]["id"] == new_m["id"]

    # 3. Verify that sales_service now automatically picks up the new active merchant
    active_in_db = sales_service.get_or_create_merchant(db_session)
    assert active_in_db.id == new_m["id"]
    assert active_in_db.name == "Sharma Electronics & Audio"


def test_admin_update_and_deactivate_merchant(client, db_session):
    """Test updating merchant details and toggling active status."""
    m = Merchant(name="City Hardware Depot", business_type="Hardware & Tools", is_active=True)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)

    # 1. Update phone and business type
    res_update = client.put(
        f"/api/admin/merchants/{m.id}",
        json={"phone": "+919876511111", "business_type": "Tools & Sanitary"}
    )
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["phone"] == "+919876511111"
    assert updated["business_type"] == "Tools & Sanitary"

    # 2. Deactivate merchant
    res_del = client.delete(f"/api/admin/merchants/{m.id}")
    assert res_del.status_code == 200
    db_session.refresh(m)
    assert m.is_active is False
