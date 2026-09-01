"""
Unit tests for Pure Agentic LLM extraction schemas, prompts, and validations.
"""

from backend.app.services.llm_service import llm_service, BaseLLMProvider, _build_extraction_prompt
from backend.app.schemas.voice import VoiceExtractionResult, VoiceItemExtracted


def test_build_extraction_prompt():
    prompt = _build_extraction_prompt(
        text="2 coffee 60 rupaye",
        catalog_items=["coffee", "sandwich", "tea"],
        business_type="Cafe & Fast Food",
    )
    assert "coffee" in prompt
    assert "Cafe & Fast Food" in prompt
    assert "STRICT AGENT INSTRUCTIONS" in prompt


def test_base_llm_provider_parsing():
    provider = BaseLLMProvider()
    raw_data = {
        "intent": "record_sale",
        "items": [
            {"product_name": "coffee", "quantity": 2, "unit_price": 30.0},
            {"product_name": "sandwich", "quantity": 1, "unit_price": 60.0},
        ],
        "payment_status": "pending",
        "explanation": "2 coffee aur 1 sandwich record kiya gaya.",
    }
    parsed = provider._parse_extraction_response("2 coffee aur 1 sandwich", raw_data)
    assert parsed.intent == "record_sale"
    assert len(parsed.items) == 2
    assert parsed.items[0].product_name == "coffee"
    assert parsed.items[0].quantity == 2
    assert parsed.items[0].unit_price == 30.0


def test_open_catalog_validation_guard():
    raw = VoiceExtractionResult(
        intent="record_sale",
        items=[VoiceItemExtracted(product_name="chai", quantity=1, unit_price=20.0)],
        raw_text="1 chai 20 rs",
    )
    validated = llm_service.validate_extraction(raw, catalog_items=[])
    assert validated.intent == "record_sale"
    assert len(validated.items) == 1
