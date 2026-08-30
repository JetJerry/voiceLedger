from backend.app.schemas.voice import VoiceProcessRequest
from backend.app.agents.merchant_agent import merchant_agent


def test_merchant_agent_record_sale(db_session):
    req = VoiceProcessRequest(text="Rahul ko do burger aur ek coke diya")
    resp = merchant_agent.process_merchant_command(db_session, req)
    
    assert resp.action_taken == "SALE_CREATED"
    assert resp.sale is not None
    assert resp.sale["customer_name"] == "Rahul"
    # burger=100*2 + coke=40*1 = 240
    assert resp.sale["total_amount"] == 240.0
    assert "₹240.00 ka sale record ho gaya" in resp.agent_reply


def test_merchant_agent_query_pending(db_session):
    # First create a sale
    merchant_agent.process_merchant_command(
        db_session,
        VoiceProcessRequest(text="Amit ko ek pizza diya")
    )

    req = VoiceProcessRequest(text="Aaj kitna paisa pending hai?")
    resp = merchant_agent.process_merchant_command(db_session, req)
    
    assert resp.action_taken == "QUERY_ANSWERED"
    assert "pending" in resp.agent_reply.lower() or "baaki" in resp.agent_reply.lower()
