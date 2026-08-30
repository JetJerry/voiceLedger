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
