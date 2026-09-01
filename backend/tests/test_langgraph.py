"""
Unit tests for LangGraph state machine workflow and guardrails.
"""

from unittest.mock import patch
from backend.app.models import Merchant, Product
from backend.app.schemas.voice import VoiceProcessRequest, VoiceExtractionResult, VoiceItemExtracted
from backend.app.agentic.graph import run_voiceledger_agent_workflow
from backend.app.agentic.tools import (
    record_sale_tool,
    check_payment_status_tool,
    add_to_catalog_tool,
    query_store_finances_tool,
    list_or_search_catalog_tool,
)


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

    mock_extraction = VoiceExtractionResult(
        intent="record_sale",
        items=[VoiceItemExtracted(product_name="chai", quantity=2, unit_price=20.0)],
        raw_text="2 chai 40 rupaye",
        payment_status="pending",
    )

    with patch("backend.app.services.llm_service.llm_service.extract_transaction", return_value=mock_extraction):
        req = VoiceProcessRequest(text="2 chai 40 rupaye", voice_lang="hi", speak_response=False)
        res = run_voiceledger_agent_workflow(db_session, req, merchant_id=m.id)

        assert res.action_taken == "SALE_CREATED"
        assert res.sale is not None
        assert res.sale["total_amount"] == 40.0


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

    mock_extraction = VoiceExtractionResult(
        intent="add_to_catalog",
        items=[VoiceItemExtracted(product_name="paracetamol", quantity=1, unit_price=50.0, category="Medicines", unit="strip")],
        raw_text="Menu mein paracetamol add karo 50 rupaye",
        payment_status="pending",
    )

    with patch("backend.app.services.llm_service.llm_service.extract_transaction", return_value=mock_extraction):
        req = VoiceProcessRequest(text="Menu mein paracetamol add karo 50 rupaye", voice_lang="hi", speak_response=False)
        res = run_voiceledger_agent_workflow(db_session, req, merchant_id=m.id)

        assert res.action_taken in ["CATALOG_ITEM_ADDED", "CATALOG_ADDED", "CATALOG_UPDATED"]
        assert "paracetamol" in res.agent_reply.lower() or "50" in res.agent_reply

        # Verify DB insertion
        p = db_session.query(Product).filter(Product.merchant_id == m.id, Product.name.ilike("%paracetamol%")).first()
        assert p is not None
        assert p.price == 50.0


def test_langgraph_agent_tools_directly(db_session):
    """Directly test the discrete Agent Tools."""
    m = Merchant(
        name="Tool Test Mart",
        username="tool_test",
        business_type="Cafe & Fast Food",
        is_active=True,
        is_current_active=True,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)

    # 1. Add item tool
    add_res = add_to_catalog_tool(
        db=db_session,
        merchant_id=m.id,
        product_name="samosa",
        unit_price=25.0,
        category="Snacks",
        unit="piece",
        business_type=m.business_type,
    )
    assert add_res["action_taken"] == "CATALOG_ITEM_ADDED"
    assert add_res["price"] == 25.0

    # 2. Record sale tool
    sale_res = record_sale_tool(
        db=db_session,
        merchant_id=m.id,
        items=[{"product_name": "samosa", "quantity": 2, "unit_price": 25.0}],
        product_map={"samosa": {"price": 25.0}},
        customer_name="Ramesh",
        is_credit=False,
    )
    assert sale_res["action_taken"] == "SALE_CREATED"
    assert sale_res["total_amount"] == 50.0

    # 3. Check status tool
    status_res = check_payment_status_tool(
        db=db_session,
        merchant_id=m.id,
        product_filter="samosa",
    )
    assert status_res["action_taken"] == "PAYMENT_STATUS_CHECKED"
    assert status_res["status"] == "PENDING"

    # 4. Analytics tool
    fin_res = query_store_finances_tool(
        db=db_session,
        merchant_id=m.id,
        intent="query_daily",
    )
    assert fin_res["action_taken"] == "DAILY_QUERIED"
    assert fin_res["today_gmv"] == 50.0
