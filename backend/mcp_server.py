"""
VoiceLedger Model Context Protocol (MCP) Server.
Exposes VoiceLedger Razorpay Payment Collection & Verification capabilities as MCP tools.
"""

import json
from typing import Optional, List, Dict, Any

try:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("VoiceLedger-Razorpay-MCP")
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("VoiceLedger-Razorpay-MCP")
    except Exception:
        # Fallback dummy class if running in minimal environment
        class DummyMCP:
            def tool(self):
                return lambda f: f
            def run(self):
                pass
        mcp = DummyMCP()

from backend.app.db.session import SessionLocal
from backend.app.services.sales_service import sales_service
from backend.app.services.reconciliation_service import reconciliation_service
from backend.app.services.recovery_service import recovery_service
from backend.app.services.razorpay_service import razorpay_service
from backend.app.schemas.sale import SaleCreate, SaleItemCreate


@mcp.tool()
def get_dashboard_metrics() -> Dict[str, Any]:
    """
    Returns real-time VoiceLedger merchant metrics: Today's Sales, Total Collected, Total Outstanding, and status counts.
    """
    db = SessionLocal()
    try:
        summary = sales_service.get_sales_summary(db)
        return summary
    finally:
        db.close()


@mcp.tool()
def check_payment_arrival(sale_id: Optional[str] = None, customer_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies whether a customer's payment has arrived and been reconciled with Razorpay.
    """
    db = SessionLocal()
    try:
        if sale_id:
            sale = sales_service.get_sale_by_id(db, sale_id)
            if not sale:
                return {"found": False, "message": f"Sale with ID {sale_id} not found."}
            return {
                "found": True,
                "sale_id": sale.id,
                "customer_name": sale.customer_name,
                "total_expected": sale.total_amount,
                "received_amount": sale.received_amount,
                "outstanding_amount": sale.outstanding_amount,
                "status": sale.status,
                "is_paid": sale.status == "PAID",
                "payment_link": sale.razorpay_payment_link_url
            }
        else:
            # Query recent sales
            sales = sales_service.get_sales(db, limit=5)
            return {
                "recent_sales": [
                    {
                        "sale_id": s.id,
                        "customer": s.customer_name,
                        "expected": s.total_amount,
                        "received": s.received_amount,
                        "outstanding": s.outstanding_amount,
                        "status": s.status,
                    }
                    for s in sales
                ]
            }
    finally:
        db.close()


@mcp.tool()
def record_voice_sale(items: List[Dict[str, Any]], customer_name: Optional[str] = "Valued Customer", customer_phone: Optional[str] = None) -> Dict[str, Any]:
    """
    Records a product sale (e.g. 2 coffee, 1 sandwich) and automatically generates a Razorpay test payment link.
    Each item in items must have 'product_name' (str) and 'quantity' (int).
    """
    db = SessionLocal()
    try:
        sale_items = [
            SaleItemCreate(product_name=it["product_name"], quantity=int(it["quantity"]))
            for it in items
        ]
        sale = sales_service.create_sale(
            db,
            SaleCreate(
                customer_name=customer_name or "Valued Customer",
                customer_phone=customer_phone,
                items=sale_items
            )
        )
        return {
            "status": "created",
            "sale_id": sale.id,
            "total_amount": sale.total_amount,
            "payment_link_url": sale.razorpay_payment_link_url,
            "status": sale.status
        }
    finally:
        db.close()


@mcp.tool()
def simulate_webhook_payment(sale_id: str, amount: float, status: str = "captured") -> Dict[str, Any]:
    """
    Simulates a Razorpay webhook event (payment.captured) and triggers deterministic reconciliation.
    """
    db = SessionLocal()
    try:
        payload = razorpay_service.simulate_test_webhook_payload(
            sale_id=sale_id,
            amount=amount,
            status=status
        )
        reconciliation = reconciliation_service.reconcile_from_webhook_payload(db, payload)
        return {
            "status": "simulated_success",
            "reconciliation": reconciliation
        }
    finally:
        db.close()


@mcp.tool()
def trigger_revenue_recovery() -> Dict[str, Any]:
    """
    Scans all pending and overdue transactions and executes automated multi-channel recovery workflows.
    """
    db = SessionLocal()
    try:
        result = recovery_service.evaluate_and_execute_recovery(db)
        return result
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
