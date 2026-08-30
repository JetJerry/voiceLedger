from backend.app.services.llm_service import llm_service


def test_dynamic_product_sale_extraction():
    speech = "do coffee aur ek sandwich 120 rupaye"
    result = llm_service.extract_transaction(speech, catalog_items=["coffee", "sandwich", "tea"])
    
    assert result.intent == "record_sale"
    assert len(result.items) >= 2
    coffee = next((it for it in result.items if "coffee" in it.product_name), None)
    assert coffee is not None
    assert coffee.quantity == 2


def test_voice_payment_arrival_check():
    query = "Payment aaya kya?"
    result = llm_service.extract_transaction(query)
    assert result.intent == "check_payment_status"


def test_product_specific_payment_arrival_check():
    query = "Coffee ka payment aaya kya?"
    result = llm_service.extract_transaction(query, catalog_items=["coffee", "tea"])
    assert result.intent == "check_payment_status"
    assert result.product_name == "coffee"


def test_pending_balance_query():
    query = "Kitna paisa pending hai?"
    result = llm_service.extract_transaction(query)
    assert result.intent == "query_pending"
