from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.services.sales_service import sales_service


def test_create_sale_deterministic_calculation(db_session):
    sale_in = SaleCreate(
        items=[
            SaleItemCreate(product_name="coffee", quantity=2, unit_price=50.0),
            SaleItemCreate(product_name="sandwich", quantity=1, unit_price=80.0)
        ],
        raw_voice_transcript="2 coffee aur 1 sandwich diya"
    )

    sale = sales_service.create_sale(db_session, sale_in)
    
    assert sale.id.startswith("sale_")
    # coffee=50*2 + sandwich=80*1 = 180
    assert sale.total_amount == 180.0
    assert sale.received_amount == 0.0
    assert sale.outstanding_amount == 180.0
    assert sale.status == "PENDING"
    assert sale.razorpay_payment_link_url is not None
    assert len(sale.items) == 2


def test_dynamic_product_price_matching(db_session):
    merchant = sales_service.get_or_create_merchant(db_session)
    prod, price = sales_service.find_product_price(db_session, merchant.id, "coffee")
    assert prod is not None
    assert price == 50.0


def test_open_catalog_any_category(db_session):
    """Verify that shopkeepers can add ANY product of ANY custom category with open schema."""
    # Add an apparel item
    p1 = sales_service.add_or_update_product(
        db_session,
        name="Cotton Kurta",
        price=750.0,
        category="Apparel & Clothing",
        unit="piece",
        description="Handloom cotton regular fit"
    )
    assert p1.id is not None
    assert p1.name == "cotton kurta"
    assert p1.price == 750.0
    assert p1.category == "Apparel & Clothing"
    assert p1.unit == "piece"

    # Add a hardware item
    p2 = sales_service.add_or_update_product(
        db_session,
        name="Steel Hammer",
        price=220.0,
        category="Hardware & Tools",
        unit="piece",
        description="Heavy duty claw hammer"
    )
    assert p2.id is not None
    assert p2.name == "steel hammer"
    assert p2.price == 220.0


def test_voice_add_to_catalog(db_session):
    """Verify that shopkeepers can add menu items via natural voice input."""
    from backend.app.agents.merchant_agent import merchant_agent
    from backend.app.schemas.voice import VoiceProcessRequest

    req = VoiceProcessRequest(text="Menu mein Butter Chicken add karo 350 rupaye", speak_response=False)
    resp = merchant_agent.process_merchant_command(db_session, req)

    assert resp.action_taken == "CATALOG_ITEM_ADDED"
    assert "butter chicken" in resp.agent_reply.lower() or "350" in resp.agent_reply

    # Check that product is now in the database
    merchant = sales_service.get_or_create_merchant(db_session)
    prod, price = sales_service.find_product_price(db_session, merchant.id, "butter chicken")
    assert prod is not None
    assert price == 350.0

