"""Tests for anti-hallucination guards, empty catalog, and multi-turn catalog voice intents."""
from unittest.mock import patch
from backend.app.services.llm_service import llm_service
from backend.app.schemas.voice import VoiceProcessRequest, VoiceExtractionResult, VoiceItemExtracted
from backend.app.agents.merchant_agent import merchant_agent
from backend.app.models import Merchant, Product


def test_empty_catalog_records_sale_dynamically(db_session):
    merchant = db_session.query(Merchant).filter(Merchant.is_current_active == True).first()
    db_session.query(Product).filter(Product.merchant_id == merchant.id).update({"is_active": False})
    db_session.commit()

    mock_extraction = VoiceExtractionResult(
        intent="record_sale",
        items=[VoiceItemExtracted(product_name="coffee", quantity=2, unit_price=30.0)],
        raw_text="2 coffee 60 rupaye",
    )

    with patch("backend.app.services.llm_service.llm_service.extract_transaction", return_value=mock_extraction):
        resp = merchant_agent.process_merchant_command(
            db_session, VoiceProcessRequest(text="2 coffee 60 rupaye", speak_response=False)
        )
        assert resp.action_taken == "SALE_CREATED"
        assert resp.sale is not None
        assert resp.sale["total_amount"] == 60.0


def test_open_catalog_dynamic_product_sale(db_session):
    fake_extraction = VoiceExtractionResult(
        intent="record_sale",
        raw_text="1 burger 100",
        items=[VoiceItemExtracted(product_name="burger", quantity=1, unit_price=100.0)],
    )
    result = llm_service.validate_extraction(fake_extraction, [])
    assert result.intent == "record_sale"
    assert len(result.items) == 1


def test_merchant_agent_list_catalog(db_session):
    mock_list_extraction = VoiceExtractionResult(
        intent="list_catalog",
        raw_text="Menu dikhao",
    )

    with patch("backend.app.services.llm_service.llm_service.extract_transaction", return_value=mock_list_extraction):
        resp = merchant_agent.process_merchant_command(
            db_session, VoiceProcessRequest(text="Menu dikhao", context="catalog", speak_response=False)
        )
        assert resp.action_taken == "CATALOG_LISTED"
        assert "items" in resp.agent_reply.lower() or "catalog" in resp.agent_reply.lower()


def test_multi_turn_catalog_add_product(db_session):
    # Turn 1: User says "Add product" without price/name
    turn1_extraction = VoiceExtractionResult(
        intent="add_to_catalog",
        raw_text="Add product",
        items=[],
        explanation="Product add karne ke liye product ka naam aur price bolein.",
    )

    with patch("backend.app.services.llm_service.llm_service.extract_transaction", return_value=turn1_extraction):
        resp1 = merchant_agent.process_merchant_command(
            db_session,
            VoiceProcessRequest(
                text="Add product",
                context="catalog",
                speak_response=False,
            ),
        )
        assert resp1.action_taken == "CATALOG_ADD_PRICE_REQUIRED"
        assert "naam" in resp1.agent_reply.lower() or "price" in resp1.agent_reply.lower() or "add" in resp1.agent_reply.lower()

    # Turn 2: User responds "Burger 100 rupaye" with history
    turn2_extraction = VoiceExtractionResult(
        intent="add_to_catalog",
        raw_text="Burger 100 rupaye",
        items=[VoiceItemExtracted(product_name="cheeseburger", unit_price=100.0, category="Snacks")],
        explanation="Cheeseburger Rs. 100 me catalog me add ho gaya.",
    )

    history = [
        {"role": "user", "content": "Add product"},
        {"role": "assistant", "content": resp1.agent_reply},
    ]

    with patch("backend.app.services.llm_service.llm_service.extract_transaction", return_value=turn2_extraction):
        resp2 = merchant_agent.process_merchant_command(
            db_session,
            VoiceProcessRequest(
                text="Burger 100 rupaye",
                context="catalog",
                speak_response=False,
                history=history,
            ),
        )
        assert resp2.action_taken in ["CATALOG_ITEM_ADDED", "CATALOG_ITEMS_ADDED"]
        assert "cheeseburger" in resp2.agent_reply.lower()


def test_catalog_search_product_price(db_session):
    merchant = db_session.query(Merchant).filter(Merchant.is_current_active == True).first()
    # Add a unique product
    p = Product(merchant_id=merchant.id, name="Special Masala Dosa", price=85.0, unit="plate", category="South Indian", is_active=True)
    db_session.add(p)
    db_session.commit()

    search_extraction = VoiceExtractionResult(
        intent="search_catalog",
        product_name="special masala dosa",
        raw_text="Special Masala Dosa ka price kya hai",
    )

    with patch("backend.app.services.llm_service.llm_service.extract_transaction", return_value=search_extraction):
        resp = merchant_agent.process_merchant_command(
            db_session,
            VoiceProcessRequest(
                text="Special Masala Dosa ka price kya hai",
                context="catalog",
                speak_response=False,
            ),
        )
        assert resp.action_taken == "CATALOG_SEARCHED"
        assert "85" in resp.agent_reply or "dosa" in resp.agent_reply.lower()
