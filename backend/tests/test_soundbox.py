import pytest
from backend.app.models import Merchant, Product, Sale, SaleItem
from backend.app.services.reconciliation_service import reconciliation_service
from backend.app.services.payment_announcement_service import payment_announcement_service
from backend.app.services.sales_service import sales_service
from backend.app.schemas.voice import VoiceProcessRequest
from backend.app.agents.merchant_agent import merchant_agent


def test_payment_arrival_creates_soundbox_voice_announcement(client, db_session):
    """Test that when a customer payment arrives, a voice soundbox announcement is automatically generated."""
    # 1. Create a Sale via API
    sale_payload = {
        "items": [{"product_name": "masala chai", "quantity": 2, "unit_price": 20.0}],
        "customer_name": "Vikas Sharma",
        "auto_create_payment_link": False,
    }
    res_sale = client.post("/api/sales", json=sale_payload)
    assert res_sale.status_code == 200
    sale_data = res_sale.json()
    sale_id = sale_data["id"]
    merchant_id = sale_data["merchant_id"]

    # 2. Simulate payment webhook arrival for this sale
    res_reconcile = reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id=f"pay_test_{sale_id[:6]}",
        amount_in_inr=40.0,
        status="captured",
        sale_id=sale_id,
    )
    assert res_reconcile["sale_status"] == "PAID"

    # 3. Check that soundbox announcement was created
    announcements = payment_announcement_service.get_unannounced_for_merchant(merchant_id)
    assert len(announcements) >= 1
    latest_ann = announcements[-1]
    assert latest_ann["sale_id"] == sale_id
    assert latest_ann["amount"] == 40.0
    assert "masala chai" in latest_ann["speech_text"] or "40" in latest_ann["speech_text"]
    assert "Payment receive ho gaya" in latest_ann["speech_text"]

    # 4. Fetch announcements via API
    res_api = client.get(f"/api/voice/payment-announcements?merchant_id={merchant_id}")
    assert res_api.status_code == 200
    api_anns = res_api.json()
    assert len(api_anns) >= 1

    # 5. Acknowledge announcement
    ann_id = latest_ann["id"]
    res_ack = client.post(f"/api/voice/payment-announcements/{ann_id}/ack")
    assert res_ack.status_code == 200
    assert res_ack.json()["acknowledged"] is True

    # Ensure it is no longer unannounced
    remaining = payment_announcement_service.get_unannounced_for_merchant(merchant_id)
    assert all(a["id"] != ann_id for a in remaining)


def test_merchant_agent_confirms_payment_via_voice(client, db_session):
    """Test vendor asking voice assistant if product payment has arrived."""
    # 1. Record sale and pay it
    sale_payload = {
        "items": [{"product_name": "chocolate cake", "quantity": 1, "unit_price": 350.0}],
        "customer_name": "Ananya Roy",
        "auto_create_payment_link": False,
    }
    res_sale = client.post("/api/sales", json=sale_payload)
    sale_id = res_sale.json()["id"]

    # 2. Pay it
    reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id=f"pay_cake_{sale_id[:6]}",
        amount_in_inr=350.0,
        status="captured",
        sale_id=sale_id,
    )

    # 3. Vendor asks voice assistant
    voice_req = VoiceProcessRequest(text="Payment aaya kya?", voice_lang="hi")
    agent_res = merchant_agent.process_merchant_command(db_session, voice_req)

    assert agent_res.action_taken in ["PAYMENT_STATUS_CHECKED", "QUERY_ANSWERED"]
    assert "PAID" in agent_res.agent_reply or "receive" in agent_res.agent_reply or "350" in agent_res.agent_reply
