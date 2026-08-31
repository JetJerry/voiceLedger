import pytest
from backend.app.models import Merchant, Product, Sale
from backend.app.schemas.voice import VoiceProcessRequest
from backend.app.agentic.graph import build_voiceledger_graph, run_voiceledger_agent_workflow
from backend.app.agentic.state import VoiceLedgerState


def test_langgraph_workflow_empty_catalog(db_session):
    """Test that LangGraph guardrails catch empty catalog and prompt merchant to add products."""
    m = Merchant(
        name="Fresh Mart",
        username="fresh_mart",
        business_type="Kirana & Grocery",
        is_active=True,
        is_current_active=True,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)

    # Empty catalog: user asks to sell chai
    req = VoiceProcessRequest(text="2 chai 40 rupaye", voice_lang="hi", speak_response=True)
    res = run_voiceledger_agent_workflow(db_session, req, merchant_id=m.id)

    assert res.action_taken in ["CATALOG_EMPTY", "SALE_VALIDATION_FAILED", "QUERY_ANSWERED"]
    assert "catalog" in res.agent_reply.lower() or "product" in res.agent_reply.lower()


def test_langgraph_workflow_add_product_to_catalog(db_session):
    """Test LangGraph executing add_to_catalog tool with dynamic attributes."""
    m = Merchant(
        name="City Pharmacy",
        username="city_pharma",
        business_type="Pharmacy & Medical",
        is_active=True,
        is_current_active=True,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)

    req = VoiceProcessRequest(text="Menu mein paracetamol add karo 50 rupaye", voice_lang="hi")
    res = run_voiceledger_agent_workflow(db_session, req, merchant_id=m.id)

    assert res.action_taken in ["CATALOG_ITEM_ADDED", "CATALOG_ADDED", "CATALOG_UPDATED"]
    assert "paracetamol" in res.agent_reply.lower() or "50" in res.agent_reply

    # Verify DB insertion
    p = db_session.query(Product).filter(Product.merchant_id == m.id, Product.name.ilike("%paracetamol%")).first()
    assert p is not None
    assert p.price == 50.0


def test_langgraph_workflow_record_sale_and_payment_status(db_session):
    """Test LangGraph recording a sale and then checking payment status."""
    m = Merchant(
        name="Snack Bar",
        username="snack_bar",
        business_type="Cafe & Fast Food",
        is_active=True,
        is_current_active=True,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)

    # Add product
    p = Product(merchant_id=m.id, name="samosa", price=25.0, category="Snacks", is_active=True)
    db_session.add(p)
    db_session.commit()

    # 1. Record Sale via LangGraph
    req_sale = VoiceProcessRequest(text="2 samosa 50 rs", voice_lang="hi")
    res_sale = run_voiceledger_agent_workflow(db_session, req_sale, merchant_id=m.id)

    assert res_sale.action_taken in ["SALE_CREATED", "SALE_RECORDED"]
    assert "samosa" in res_sale.agent_reply.lower() or "50" in res_sale.agent_reply

    # 2. Check Payment Status via LangGraph
    req_status = VoiceProcessRequest(text="Payment aaya kya?", voice_lang="hi")
    res_status = run_voiceledger_agent_workflow(db_session, req_status, merchant_id=m.id)

    assert res_status.action_taken in ["PAYMENT_STATUS_CHECKED", "QUERY_ANSWERED"]
    assert "samosa" in res_status.agent_reply.lower() or "pending" in res_status.agent_reply.lower() or "50" in res_status.agent_reply
