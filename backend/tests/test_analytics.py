import io
import openpyxl
import pytest
from backend.app.models import Merchant, Product, Sale, SaleItem


def test_sales_analytics_periods(client, db_session):
    """Test Day, Week, Month sales metrics computation."""
    m = Merchant(
        name="Gupta Medical Store",
        username="gupta_med",
        business_type="Pharmacy & Medical",
        is_active=True,
        is_current_active=True,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)

    # Add sample catalog products
    p1 = Product(merchant_id=m.id, name="paracetamol 500", price=20.0, category="Pharmacy", is_active=True)
    p2 = Product(merchant_id=m.id, name="vitamin c", price=50.0, category="Pharmacy", is_active=True)
    db_session.add_all([p1, p2])
    db_session.commit()

    # Record 2 sales
    sale_payload1 = {
        "items": [{"product_name": "paracetamol 500", "quantity": 2, "unit_price": 20.0}],
        "customer_name": "Rahul Verma",
        "auto_create_payment_link": False,
    }
    client.post("/api/sales", json=sale_payload1)

    sale_payload2 = {
        "items": [{"product_name": "vitamin c", "quantity": 1, "unit_price": 50.0}],
        "customer_name": "Priya Singh",
        "auto_create_payment_link": False,
    }
    client.post("/api/sales", json=sale_payload2)

    # Fetch Analytics Summary
    res = client.get("/api/sales/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert "periods" in data
    assert "today" in data["periods"]
    assert "week" in data["periods"]
    assert "month" in data["periods"]
    assert "all_time" in data["periods"]

    today = data["periods"]["today"]
    assert today["orders_count"] == 2
    assert today["total_gmv"] == 90.0
    assert today["total_outstanding"] == 90.0

    # Catalog summary
    assert "catalog_summary" in data
    assert len(data["catalog_summary"]) >= 2


def test_sales_analytics_excel_export(client, db_session):
    """Test generating and exporting multi-sheet Excel spreadsheet (.xlsx)."""
    res = client.get("/api/sales/analytics/export/excel")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "Content-Disposition" in res.headers
    assert "VoiceLedger_Sales_Report_" in res.headers["Content-Disposition"]

    # Verify openpyxl can parse the generated workbook
    wb = openpyxl.load_workbook(io.BytesIO(res.content))
    sheet_names = wb.sheetnames
    assert "Sales Analytics Summary" in sheet_names
    assert "Product Catalog & Stock" in sheet_names
    assert "Sales Transactions Ledger" in sheet_names

    ws1 = wb["Sales Analytics Summary"]
    assert "Sales & Performance Report" in str(ws1["A1"].value)
