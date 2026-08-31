"""Tests for anti-hallucination guards, empty catalog, and catalog voice intents."""
from backend.app.services.llm_service import llm_service
from backend.app.schemas.voice import VoiceProcessRequest
from backend.app.agents.merchant_agent import merchant_agent
from backend.app.models import Merchant, Product


def test_empty_catalog_blocks_sale(db_session):
    merchant = db_session.query(Merchant).filter(Merchant.is_current_active == True).first()
    # Deactivate all products for this merchant
    db_session.query(Product).filter(Product.merchant_id == merchant.id).update({"is_active": False})
    db_session.commit()

    result = llm_service.extract_transaction("2 coffee 60 rupaye", catalog_items=[])
    assert result.intent in ("general_qa", "record_sale")
    if result.intent == "general_qa":
        assert "catalog" in (result.explanation or "").lower()

    resp = merchant_agent.process_merchant_command(
        db_session, VoiceProcessRequest(text="2 coffee 60 rupaye")
    )
    assert resp.action_taken in ("CATALOG_EMPTY", "SALE_VALIDATION_FAILED", "QUERY_ANSWERED")


def test_unknown_product_rejected_without_price(db_session):
    from backend.app.schemas.voice import VoiceExtractionResult, VoiceItemExtracted

    merchant = db_session.query(Merchant).filter(Merchant.is_current_active == True).first()
    db_session.query(Product).filter(Product.merchant_id == merchant.id).update({"is_active": False})
    db_session.add(Product(merchant_id=merchant.id, name="chai", price=20.0, category="Beverages", is_active=True))
    db_session.commit()

    fake_extraction = VoiceExtractionResult(
        intent="record_sale",
        raw_text="1 unicorn becha",
        items=[VoiceItemExtracted(product_name="unicorn", quantity=1)],
    )
    result = llm_service.validate_extraction(fake_extraction, ["chai"])
    assert result.intent == "general_qa"
    assert "catalog" in (result.explanation or "").lower()


def test_list_catalog_intent():
    result = llm_service.extract_transaction("Menu dikhao", catalog_items=["chai", "coffee"])
    assert result.intent == "list_catalog"


def test_search_catalog_intent():
    result = llm_service.extract_transaction("Coffee ka price kya hai", catalog_items=["chai", "coffee"])
    assert result.intent == "search_catalog"
    assert result.product_name == "coffee"


def test_merchant_agent_list_catalog(db_session):
    resp = merchant_agent.process_merchant_command(
        db_session, VoiceProcessRequest(text="Menu dikhao", context="catalog")
    )
    assert resp.action_taken == "CATALOG_LISTED"
    assert "items" in resp.agent_reply.lower() or "catalog" in resp.agent_reply.lower()
