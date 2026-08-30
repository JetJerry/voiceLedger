from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.services.sales_service import sales_service


def test_create_sale_deterministic_calculation(db_session):
    sale_in = SaleCreate(
        customer_name="Rahul",
        customer_phone="+919876543210",
        items=[
            SaleItemCreate(product_name="burger", quantity=2),
            SaleItemCreate(product_name="coke", quantity=1)
        ],
        raw_voice_transcript="Rahul ko 2 burger aur 1 coke diya"
    )

    sale = sales_service.create_sale(db_session, sale_in)
    
    assert sale.id.startswith("sale_")
    assert sale.customer_name == "Rahul"
    # burger=100*2 + coke=40*1 = 240
    assert sale.total_amount == 240.0
    assert sale.received_amount == 0.0
    assert sale.outstanding_amount == 240.0
    assert sale.status == "PENDING"
    assert sale.razorpay_payment_link_url is not None
    assert len(sale.items) == 2


def test_fuzzy_product_matching(db_session):
    merchant = sales_service.get_or_create_merchant(db_session)
    prod, price = sales_service.find_product_price(db_session, merchant.id, "cheese burger")
    assert prod is not None
    assert price == 150.0
