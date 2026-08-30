from backend.app.services.llm_service import llm_service


def test_hinglish_sale_extraction():
    speech = "Rahul ko do burger diye, 100 each."
    result = llm_service.extract_transaction(speech, catalog_items=["burger", "pizza", "coke"])
    
    assert result.intent == "record_sale"
    assert result.customer_name == "Rahul"
    assert len(result.items) >= 1
    assert result.items[0].product_name == "burger"
    assert result.items[0].quantity == 2


def test_hinglish_pending_query():
    query = "Aaj kitna paisa pending hai?"
    result = llm_service.extract_transaction(query)
    assert result.intent in ["query_pending", "query_daily"]


def test_customer_status_query():
    query = "Rahul ka payment aaya kya?"
    result = llm_service.extract_transaction(query)
    assert result.intent == "query_status"
    assert result.customer_name == "Rahul"


def test_trigger_recovery_query():
    query = "Amit ko recovery link bhej do"
    result = llm_service.extract_transaction(query)
    assert result.intent == "trigger_recovery"
    assert result.customer_name == "Amit"
