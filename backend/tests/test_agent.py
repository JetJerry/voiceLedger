from backend.app.schemas.voice import VoiceProcessRequest
from backend.app.agents.merchant_agent import merchant_agent
from backend.app.services.reconciliation_service import reconciliation_service


def test_merchant_agent_record_sale(db_session):
    req = VoiceProcessRequest(text="do coffee aur ek sandwich 120 rupaye")
    resp = merchant_agent.process_merchant_command(db_session, req)
    
    assert resp.action_taken == "SALE_CREATED"
    assert resp.sale is not None
    assert resp.sale["total_amount"] > 0
    assert "sale record ho gaya" in resp.agent_reply


def test_merchant_agent_check_payment_arrival(db_session):
    # 1. Record a sale
    create_resp = merchant_agent.process_merchant_command(
        db_session,
        VoiceProcessRequest(text="do coffee 100 rupaye")
    )
    sale_id = create_resp.sale["id"]
    total = create_resp.sale["total_amount"]

    # 2. Check payment arrival when unpaid
    check_req = VoiceProcessRequest(text="Payment aaya kya?")
    check_resp = merchant_agent.process_merchant_command(db_session, check_req)
    
    assert check_resp.action_taken == "PAYMENT_STATUS_CHECKED"
    assert "PENDING" in check_resp.agent_reply or "nahi aaya" in check_resp.agent_reply

    # 3. Simulate partial payment (half)
    reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id="pay_test_arrival_partial",
        amount_in_inr=total / 2,
        status="captured",
        sale_id=sale_id
    )

    # 4. Check payment arrival for partial payment
    check_resp_partial = merchant_agent.process_merchant_command(db_session, check_req)
    assert check_resp_partial.action_taken == "PAYMENT_STATUS_CHECKED"
    assert "PARTIAL" in check_resp_partial.agent_reply

    # 5. Complete remaining payment
    reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id="pay_test_arrival_full",
        amount_in_inr=total / 2,
        status="captured",
        sale_id=sale_id
    )

    # 6. Check payment arrival for full payment
    check_resp_full = merchant_agent.process_merchant_command(db_session, check_req)
    assert check_resp_full.action_taken == "PAYMENT_STATUS_CHECKED"
    assert "PAID" in check_resp_full.agent_reply or "receive ho chuka hai" in check_resp_full.agent_reply
