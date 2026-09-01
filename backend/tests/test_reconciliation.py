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


def test_payment_reconciliation_db_persistence(db_session):
    from backend.app.models import Sale, Payment
    from backend.app.api.dashboard import get_dashboard_summary

    # 1. Create a sale
    sale = sales_service.create_sale(
        db_session,
        SaleCreate(
            customer_name="Priya",
            items=[SaleItemCreate(product_name="notebook", quantity=3, unit_price=50.0)]
        )
    )
    assert sale.status == "PENDING"
    assert sale.total_amount == 150.0

    # 2. Reconcile payment
    reconciliation_service.process_payment_event(
        db=db_session,
        razorpay_payment_id="pay_persisted_test_123",
        amount_in_inr=150.0,
        status="captured",
        sale_id=sale.id
    )

    # 3. Expire in-memory cache to force a fresh SELECT from SQLite
    db_session.expire_all()

    fresh_sale = db_session.query(Sale).filter(Sale.id == sale.id).first()
    assert fresh_sale.status == "PAID"
    assert fresh_sale.received_amount == 150.0
    assert fresh_sale.outstanding_amount == 0.0

    # 4. Verify Payment record exists in DB
    payment = db_session.query(Payment).filter(Payment.razorpay_payment_id == "pay_persisted_test_123").first()
    assert payment is not None
    assert payment.amount == 150.0
    assert payment.status == "captured"

    # 5. Verify Dashboard summary reflects updated paid status
    summary = get_dashboard_summary(merchant_id=sale.merchant_id, db=db_session)
    assert summary.paid_count >= 1
    found = any(s.id == sale.id and s.status == "PAID" and s.received_amount == 150.0 for s in summary.recent_sales)
    assert found is True

