"""
Unit tests for Merchant Agent and LangGraph Workflow execution.
"""

from unittest.mock import patch
from backend.app.schemas.voice import VoiceProcessRequest, VoiceExtractionResult, VoiceItemExtracted
from backend.app.agents.merchant_agent import merchant_agent
from backend.app.services.reconciliation_service import reconciliation_service


def test_merchant_agent_record_sale(db_session):
    mock_extraction = VoiceExtractionResult(
        intent="record_sale",
        items=[
            VoiceItemExtracted(product_name="coffee", quantity=2, unit_price=40.0),
            VoiceItemExtracted(product_name="sandwich", quantity=1, unit_price=40.0),
        ],
        raw_text="do coffee aur ek sandwich 120 rupaye",
        payment_status="pending",
    )

    with patch("backend.app.services.llm_service.llm_service.extract_transaction", return_value=mock_extraction):
        req = VoiceProcessRequest(text="do coffee aur ek sandwich 120 rupaye", speak_response=False)
        resp = merchant_agent.process_merchant_command(db_session, req)
        
        assert resp.action_taken == "SALE_CREATED"
        assert resp.sale is not None
        assert resp.sale["total_amount"] > 0
        assert "sale record ho gaya" in resp.agent_reply.lower() or "120" in resp.agent_reply


def test_merchant_agent_check_payment_arrival(db_session):
    # 1. Record a sale
    mock_sale_extraction = VoiceExtractionResult(
        intent="record_sale",
        items=[VoiceItemExtracted(product_name="coffee", quantity=2, unit_price=50.0)],
        raw_text="do coffee 100 rupaye",
        payment_status="pending",
    )

    with patch("backend.app.services.llm_service.llm_service.extract_transaction", return_value=mock_sale_extraction):
        create_resp = merchant_agent.process_merchant_command(
            db_session,
            VoiceProcessRequest(text="do coffee 100 rupaye", speak_response=False)
        )
        sale_id = create_resp.sale["id"]
        total = create_resp.sale["total_amount"]

    mock_status_extraction = VoiceExtractionResult(
        intent="check_payment_status",
        product_name="coffee",
        items=[VoiceItemExtracted(product_name="coffee", quantity=1)],
        raw_text="Payment aaya kya?",
        payment_status="pending",
    )

    with patch("backend.app.services.llm_service.llm_service.extract_transaction", return_value=mock_status_extraction):
        # 2. Check payment arrival when unpaid
        check_req = VoiceProcessRequest(text="Payment aaya kya?", speak_response=False)
        check_resp = merchant_agent.process_merchant_command(db_session, check_req)
        
        assert check_resp.action_taken == "PAYMENT_STATUS_CHECKED"
        assert "PENDING" in check_resp.agent_reply or "pending" in check_resp.agent_reply.lower()

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
        assert "PARTIAL" in check_resp_partial.agent_reply or "baaki" in check_resp_partial.agent_reply.lower()

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
        assert any(w in check_resp_full.agent_reply.lower() for w in ["paid", "receive", "haan", "mil", "chuka"])
