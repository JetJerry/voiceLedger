import json
import hmac
import hashlib
from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.services.sales_service import sales_service
from backend.app.services.razorpay_service import razorpay_service


def test_webhook_endpoint_flow(client, db_session):
    # 1. Create a sale
    sale = sales_service.create_sale(
        db_session,
        SaleCreate(
            customer_name="Rahul",
            items=[SaleItemCreate(product_name="burger", quantity=2)]
        )
    )

    # 2. Prepare payload
    payload = {
        "entity": "event",
        "account_id": "acc_test",
        "event": "payment_link.paid",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_wh_test_1",
                    "amount": 20000,
                    "status": "captured",
                    "notes": {"sale_id": sale.id}
                }
            }
        }
    }
    raw_payload = json.dumps(payload).encode("utf-8")
    
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Event-Id": "evt_test_1"
    }
    
    # If webhook secret is active, calculate valid signature
    if razorpay_service.webhook_secret:
        sig = hmac.new(razorpay_service.webhook_secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()
        headers["X-Razorpay-Signature"] = sig

    response = client.post(
        "/api/webhooks/razorpay",
        content=raw_payload,
        headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["reconciliation"]["sale_status"] == "PAID"


def test_webhook_invalid_signature_rejected(client, db_session, monkeypatch):
    secret = "super_secret_webhook_key_123"
    monkeypatch.setattr(razorpay_service, "_webhook_secret", secret)

    payload = {
        "entity": "event",
        "event": "payment.captured",
        "payload": {
            "payment": {"entity": {"id": "pay_fake_1", "amount": 5000, "status": "captured"}}
        }
    }
    raw_payload = json.dumps(payload).encode("utf-8")

    # Send with invalid signature
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": "invalid_bogus_hmac_signature"
    }

    response = client.post(
        "/api/webhooks/razorpay",
        content=raw_payload,
        headers=headers
    )

    assert response.status_code == 400
    assert "Invalid Razorpay webhook signature" in response.json()["detail"]


def test_webhook_valid_signature_accepted(client, db_session, monkeypatch):
    secret = "my_custom_rzp_webhook_secret_99"
    monkeypatch.setattr(razorpay_service, "_webhook_secret", secret)

    # 1. Create a sale
    sale = sales_service.create_sale(
        db_session,
        SaleCreate(
            customer_name="Aarav",
            items=[SaleItemCreate(product_name="chai", quantity=1)]
        )
    )

    payload = {
        "entity": "event",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_sig_test_100",
                    "amount": 2000,
                    "status": "captured",
                    "notes": {"sale_id": sale.id}
                }
            }
        }
    }
    raw_payload = json.dumps(payload).encode("utf-8")

    # Generate valid HMAC-SHA256 signature using secret
    valid_sig = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": valid_sig,
        "X-Razorpay-Event-Id": "evt_sig_test_100"
    }

    response = client.post(
        "/api/webhooks/razorpay",
        content=raw_payload,
        headers=headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_merchant_onboarding_endpoint(client):
    payload = {
        "name": "Bharat Cafe",
        "currency": "INR"
    }

    response = client.post("/api/sales/catalog/merchant", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Bharat Cafe"
    assert data["currency"] == "INR"

    list_response = client.get("/api/sales/catalog/merchant")
    assert list_response.status_code == 200
    assert list_response.json()["name"] == "Bharat Cafe"
