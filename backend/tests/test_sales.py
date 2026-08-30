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
