from datetime import datetime, timezone, timedelta
from backend.app.schemas.sale import SaleCreate, SaleItemCreate
from backend.app.services.sales_service import sales_service
from backend.app.services.recovery_service import recovery_service


def test_recovery_priority_queue(db_session):
    # 1. Create a sale
    sale = sales_service.create_sale(
        db_session,
        SaleCreate(
            customer_name="Amit",
            customer_phone="+919876543211",
            items=[SaleItemCreate(product_name="pizza", quantity=3)]  # ₹900
        )
    )

    # 2. Query recovery queue
    queue = recovery_service.get_recovery_queue(db_session)
    assert len(queue) >= 1
    item = next(q for q in queue if q.sale_id == sale.id)
    assert item.customer_name == "Amit"
    assert item.outstanding_amount == 900.0
    assert item.priority_level == "HIGH"

    # 3. Trigger recovery action
    action = recovery_service.trigger_recovery_action(db_session, sale_id=sale.id)
    assert action["status"] == "SENT"
    assert action["channel"] == "whatsapp"
    assert "900.00" in action["message"]
