from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.services.sales_service import sales_service
from backend.app.services.reconciliation_service import reconciliation_service


def test_full_payment_reconciliation(db_session):
    # 1. Create Sale (2 Burger = ₹200)
    sale = sales_service.create_sale(
        db_session,
        SaleCreate(
            customer_name="Rahul",
            items=[SaleItemCreate(product_name="burger", quantity=2)]
        )
    )
    assert sale.status == "PENDING"
    assert sale.total_amount == 200.0

    # 2. Reconcile ₹200 Payment
    res = reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id="pay_full_123",
        amount_in_inr=200.0,
        status="captured",
        sale_id=sale.id
    )

    assert res["result"] == "MATCHED"
    assert res["sale_status"] == "PAID"
    assert res["received"] == 200.0
    assert res["outstanding"] == 0.0


def test_partial_payment_reconciliation(db_session):
    # 1. Create Sale (Pizza = ₹300)
    sale = sales_service.create_sale(
        db_session,
        SaleCreate(
            customer_name="Amit",
            items=[SaleItemCreate(product_name="pizza", quantity=1)]
        )
    )
    assert sale.total_amount == 300.0

    # 2. Pay ₹150 (Partial)
    res = reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id="pay_partial_123",
        amount_in_inr=150.0,
        status="captured",
        sale_id=sale.id
    )

    assert res["result"] == "MATCHED"
    assert res["sale_status"] == "PARTIAL"
    assert res["received"] == 150.0
    assert res["outstanding"] == 150.0

    # 3. Pay remaining ₹150 -> becomes PAID
    res2 = reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id="pay_partial_second_123",
        amount_in_inr=150.0,
        status="captured",
        sale_id=sale.id
    )
    assert res2["sale_status"] == "PAID"
    assert res2["outstanding"] == 0.0


def test_unmatched_payment(db_session):
    res = reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id="pay_unknown_999",
        amount_in_inr=500.0,
        status="captured",
        sale_id="non_existent_sale_id"
    )
    assert res["result"] == "UNMATCHED"


def test_idempotent_reconciliation(db_session):
    sale = sales_service.create_sale(
        db_session,
        SaleCreate(
            customer_name="Neha",
            items=[SaleItemCreate(product_name="burger", quantity=1)]
        )
    )
    # First attempt
    res1 = reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id="pay_idemp_1",
        amount_in_inr=100.0,
        status="captured",
        sale_id=sale.id
    )
    assert res1["result"] == "MATCHED"

    # Duplicate attempt
    res2 = reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id="pay_idemp_1",
        amount_in_inr=100.0,
        status="captured",
        sale_id=sale.id
    )
    assert res2["result"] == "ALREADY_PROCESSED"
