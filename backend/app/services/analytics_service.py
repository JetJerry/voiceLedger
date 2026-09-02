import io
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.models.legacy import LegacyMerchant as Merchant, Product, Sale, SaleItem
from backend.app.services.sales_service import sales_service

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class AnalyticsService:
    def get_period_sales_analytics(self, db: Session, merchant_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculates sales and product metrics segmented by Today (Day), This Week (7 Days),
        This Month (30 Days), and All-Time.
        """
        if merchant_id:
            merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        else:
            merchant = sales_service.get_or_create_merchant(db)

        if not merchant:
            return {}

        now_naive = datetime.utcnow()
        today_start = datetime(now_naive.year, now_naive.month, now_naive.day)
        week_start = now_naive - timedelta(days=7)
        month_start = now_naive - timedelta(days=30)

        all_sales = db.query(Sale).filter(Sale.merchant_id == merchant.id).order_by(Sale.created_at.desc()).all()
        products = db.query(Product).filter(Product.merchant_id == merchant.id).all()

        def _normalize_dt(dt: Optional[datetime]) -> datetime:
            if dt is None:
                return datetime.min
            return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt

        def _compute_period_stats(sales_list: List[Sale]) -> Dict[str, Any]:
            count = len(sales_list)
            gmv = sum(s.total_amount for s in sales_list)
            collected = sum(s.received_amount for s in sales_list)
            outstanding = sum(s.outstanding_amount for s in sales_list)
            paid_count = sum(1 for s in sales_list if s.status == "PAID")
            pending_count = sum(1 for s in sales_list if s.status == "PENDING")
            partial_count = sum(1 for s in sales_list if s.status == "PARTIAL")
            collection_rate = (collected / gmv * 100.0) if gmv > 0 else 100.0

            # Count product units and revenue in this period
            product_sales: Dict[str, Dict[str, Any]] = {}
            for s in sales_list:
                for it in s.items:
                    p_name = it.product_name.lower().strip()
                    if p_name not in product_sales:
                        product_sales[p_name] = {"units": 0, "revenue": 0.0}
                    product_sales[p_name]["units"] += it.quantity
                    product_sales[p_name]["revenue"] += it.subtotal

            top_products = [
                {"name": name, "units": data["units"], "revenue": round(data["revenue"], 2)}
                for name, data in sorted(product_sales.items(), key=lambda x: x[1]["revenue"], reverse=True)
            ]

            return {
                "orders_count": count,
                "total_gmv": round(gmv, 2),
                "total_collected": round(collected, 2),
                "total_outstanding": round(outstanding, 2),
                "paid_orders_count": paid_count,
                "pending_orders_count": pending_count,
                "partial_orders_count": partial_count,
                "collection_rate": round(collection_rate, 1),
                "top_products": top_products[:5],
                "product_sales_map": product_sales,
            }

        # Filter sales for each period safely
        sales_today = [s for s in all_sales if _normalize_dt(s.created_at) >= today_start]
        sales_week = [s for s in all_sales if _normalize_dt(s.created_at) >= week_start]
        sales_month = [s for s in all_sales if _normalize_dt(s.created_at) >= month_start]

        today_stats = _compute_period_stats(sales_today)
        week_stats = _compute_period_stats(sales_week)
        month_stats = _compute_period_stats(sales_month)
        all_time_stats = _compute_period_stats(all_sales)

        # Catalog performance summary
        catalog_summary = []
        for p in products:
            attrs = {}
            if p.attributes:
                try:
                    attrs = json.loads(p.attributes)
                except Exception:
                    attrs = {}

            p_name = p.name.lower().strip()
            month_p = month_stats["product_sales_map"].get(p_name, {"units": 0, "revenue": 0.0})
            all_p = all_time_stats["product_sales_map"].get(p_name, {"units": 0, "revenue": 0.0})

            catalog_summary.append({
                "id": p.id,
                "name": p.name,
                "category": p.category or "General",
                "price": p.price,
                "unit": p.unit or "piece",
                "description": p.description or "",
                "attributes": attrs,
                "is_active": p.is_active,
                "units_sold_month": month_p["units"],
                "units_sold_all_time": all_p["units"],
                "revenue_all_time": round(all_p["revenue"], 2),
            })

        return {
            "merchant": {
                "id": merchant.id,
                "name": merchant.name,
                "business_type": merchant.business_type,
                "currency": merchant.currency or "INR",
            },
            "generated_at": now_naive.isoformat(),
            "periods": {
                "today": today_stats,
                "week": week_stats,
                "month": month_stats,
                "all_time": all_time_stats,
            },
            "catalog_summary": catalog_summary,
        }

    def generate_excel_report(self, db: Session, merchant_id: Optional[int] = None) -> bytes:
        """
        Generates a professionally styled Excel workbook (.xlsx) with 3 sheets:
        1. Executive Sales Analytics (Day / Week / Month Summary)
        2. Product Catalog & Performance
        3. Detailed Sales Transactions Ledger
        """
        analytics = self.get_period_sales_analytics(db, merchant_id)
        merchant_info = analytics.get("merchant", {})
        merchant_id_val = merchant_info.get("id")
        
        all_sales = db.query(Sale).filter(Sale.merchant_id == merchant_id_val).order_by(Sale.created_at.desc()).all()

        wb = openpyxl.Workbook()
        
        # Styles
        font_title = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
        font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        font_bold = Font(name="Calibri", size=11, bold=True)
        font_regular = Font(name="Calibri", size=11)
        font_sub = Font(name="Calibri", size=10, italic=True, color="555555")

        fill_primary = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")     # Indigo
        fill_secondary = PatternFill(start_color="059669", end_color="059669", fill_type="solid")   # Emerald
        fill_dark = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")        # Slate Dark
        fill_row_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        fill_paid = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        fill_pending = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
        fill_partial = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid")

        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")

        thin_border = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0")
        )

        # ─────────────────────────────────────────────────────────────
        # SHEET 1: 📊 EXECUTIVE SUMMARY (Day / Week / Month)
        # ─────────────────────────────────────────────────────────────
        ws1 = wb.active
        ws1.title = "Sales Analytics Summary"
        ws1.views.sheetView[0].showGridLines = True

        # Header Title Banner
        ws1.merge_cells("A1:G2")
        title_cell = ws1["A1"]
        title_cell.value = f"📊 {merchant_info.get('name', 'Store')} — Sales & Performance Report"
        title_cell.font = font_title
        title_cell.fill = fill_primary
        title_cell.alignment = align_center

        ws1["A3"] = f"Business Type: {merchant_info.get('business_type', 'Retail')}  |  Currency: {merchant_info.get('currency', 'INR')}  |  Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
        ws1["A3"].font = font_sub

        # Period Table Headers
        period_headers = [
            "Period",
            "Orders Count",
            f"Gross Sales ({merchant_info.get('currency', 'INR')})",
            f"Collected Amount ({merchant_info.get('currency', 'INR')})",
            f"Outstanding Amount ({merchant_info.get('currency', 'INR')})",
            "Paid Orders",
            "Collection Rate",
        ]
        
        row_idx = 5
        for col_idx, h in enumerate(period_headers, start=1):
            c = ws1.cell(row=row_idx, column=col_idx, value=h)
            c.font = font_header
            c.fill = fill_dark
            c.alignment = align_center
            c.border = thin_border

        # Period Data Rows
        periods_data = [
            ("📅 Today (Last 24h)", analytics["periods"]["today"]),
            ("📅 This Week (7 Days)", analytics["periods"]["week"]),
            ("📅 This Month (30 Days)", analytics["periods"]["month"]),
            ("🏆 All-Time Total", analytics["periods"]["all_time"]),
        ]

        row_idx = 6
        for period_label, stats in periods_data:
            ws1.cell(row=row_idx, column=1, value=period_label).font = font_bold
            ws1.cell(row=row_idx, column=2, value=stats["orders_count"]).alignment = align_center
            ws1.cell(row=row_idx, column=3, value=stats["total_gmv"]).number_format = "₹#,##0.00"
            ws1.cell(row=row_idx, column=4, value=stats["total_collected"]).number_format = "₹#,##0.00"
            ws1.cell(row=row_idx, column=5, value=stats["total_outstanding"]).number_format = "₹#,##0.00"
            ws1.cell(row=row_idx, column=6, value=f"{stats['paid_orders_count']} / {stats['orders_count']}").alignment = align_center
            ws1.cell(row=row_idx, column=7, value=f"{stats['collection_rate']}%").alignment = align_center

            for c_idx in range(1, 8):
                cell = ws1.cell(row=row_idx, column=c_idx)
                cell.border = thin_border
                if row_idx % 2 == 0:
                    cell.fill = fill_row_zebra
            row_idx += 1

        # Top Selling Products Section
        row_idx += 2
        ws1.merge_cells(f"A{row_idx}:D{row_idx}")
        top_title = ws1[f"A{row_idx}"]
        top_title.value = "🔥 Top Selling Products (This Month)"
        top_title.font = font_header
        top_title.fill = fill_secondary
        top_title.alignment = align_left

        row_idx += 1
        top_headers = ["Rank", "Product Name", "Units Sold", f"Total Revenue ({merchant_info.get('currency', 'INR')})"]
        for c_idx, h in enumerate(top_headers, start=1):
            c = ws1.cell(row=row_idx, column=c_idx, value=h)
            c.font = font_bold
            c.fill = fill_dark
            c.font = font_header
            c.alignment = align_center
            c.border = thin_border

        top_prods = analytics["periods"]["month"].get("top_products", [])
        row_idx += 1
        if not top_prods:
            ws1.cell(row=row_idx, column=1, value="No product sales recorded in the last 30 days.")
            ws1.merge_cells(f"A{row_idx}:D{row_idx}")
            row_idx += 1
        else:
            for rank, tp in enumerate(top_prods, start=1):
                ws1.cell(row=row_idx, column=1, value=f"#{rank}").alignment = align_center
                ws1.cell(row=row_idx, column=2, value=tp["name"].title()).font = font_bold
                ws1.cell(row=row_idx, column=3, value=tp["units"]).alignment = align_center
                ws1.cell(row=row_idx, column=4, value=tp["revenue"]).number_format = "₹#,##0.00"
                for c_idx in range(1, 5):
                    ws1.cell(row=row_idx, column=c_idx).border = thin_border
                row_idx += 1

        # ─────────────────────────────────────────────────────────────
        # SHEET 2: 📦 PRODUCT CATALOG & PERFORMANCE
        # ─────────────────────────────────────────────────────────────
        ws2 = wb.create_sheet(title="Product Catalog & Stock")
        ws2.views.sheetView[0].showGridLines = True

        ws2.merge_cells("A1:H2")
        cat_title = ws2["A1"]
        cat_title.value = "📦 Complete Product Catalog & Sales Performance"
        cat_title.font = font_title
        cat_title.fill = fill_primary
        cat_title.alignment = align_center

        cat_headers = [
            "Item ID",
            "Product Name",
            "Category",
            "Unit Price (₹)",
            "Unit of Measure",
            "Dynamic Attributes / Specs",
            "Units Sold (Month)",
            "Total Revenue Generated (₹)",
        ]

        row_idx = 4
        for c_idx, h in enumerate(cat_headers, start=1):
            c = ws2.cell(row=row_idx, column=c_idx, value=h)
            c.font = font_header
            c.fill = fill_dark
            c.alignment = align_center
            c.border = thin_border

        row_idx = 5
        for item in analytics.get("catalog_summary", []):
            attrs_text = ", ".join([f"{k}: {v}" for k, v in item["attributes"].items()]) or "Standard"
            ws2.cell(row=row_idx, column=1, value=item["id"]).alignment = align_center
            ws2.cell(row=row_idx, column=2, value=item["name"].title()).font = font_bold
            ws2.cell(row=row_idx, column=3, value=item["category"]).alignment = align_center
            ws2.cell(row=row_idx, column=4, value=item["price"]).number_format = "₹#,##0.00"
            ws2.cell(row=row_idx, column=5, value=item["unit"]).alignment = align_center
            ws2.cell(row=row_idx, column=6, value=attrs_text)
            ws2.cell(row=row_idx, column=7, value=item["units_sold_month"]).alignment = align_center
            ws2.cell(row=row_idx, column=8, value=item["revenue_all_time"]).number_format = "₹#,##0.00"

            for c_idx in range(1, 9):
                cell = ws2.cell(row=row_idx, column=c_idx)
                cell.border = thin_border
                if row_idx % 2 == 1:
                    cell.fill = fill_row_zebra
            row_idx += 1

        # ─────────────────────────────────────────────────────────────
        # SHEET 3: 🧾 DETAILED SALES TRANSACTIONS LEDGER
        # ─────────────────────────────────────────────────────────────
        ws3 = wb.create_sheet(title="Sales Transactions Ledger")
        ws3.views.sheetView[0].showGridLines = True

        ws3.merge_cells("A1:J2")
        sales_title = ws3["A1"]
        sales_title.value = "🧾 Complete Sales Transactions & Payment Ledger"
        sales_title.font = font_title
        sales_title.fill = fill_primary
        sales_title.alignment = align_center

        sales_headers = [
            "Sale ID",
            "Date & Time",
            "Customer Name",
            "Customer Phone",
            "Items Purchased",
            "Total Amount (₹)",
            "Received Amount (₹)",
            "Outstanding (₹)",
            "Payment Status",
            "Razorpay Payment Link",
        ]

        row_idx = 4
        for c_idx, h in enumerate(sales_headers, start=1):
            c = ws3.cell(row=row_idx, column=c_idx, value=h)
            c.font = font_header
            c.fill = fill_dark
            c.alignment = align_center
            c.border = thin_border

        row_idx = 5
        for s in all_sales:
            items_str = ", ".join([f"{it.quantity}x {it.product_name} (₹{it.subtotal:.2f})" for it in s.items])
            date_str = s.created_at.strftime("%d-%m-%Y %H:%M") if s.created_at else "N/A"

            customer_phone_str = s.customer.phone if (s.customer and s.customer.phone) else "N/A"
            ws3.cell(row=row_idx, column=1, value=s.id).alignment = align_center
            ws3.cell(row=row_idx, column=2, value=date_str).alignment = align_center
            ws3.cell(row=row_idx, column=3, value=s.customer_name or "Walk-in Customer")
            ws3.cell(row=row_idx, column=4, value=customer_phone_str).alignment = align_center
            ws3.cell(row=row_idx, column=5, value=items_str)
            ws3.cell(row=row_idx, column=6, value=s.total_amount).number_format = "₹#,##0.00"
            ws3.cell(row=row_idx, column=7, value=s.received_amount).number_format = "₹#,##0.00"
            ws3.cell(row=row_idx, column=8, value=s.outstanding_amount).number_format = "₹#,##0.00"
            
            # Status styling
            status_cell = ws3.cell(row=row_idx, column=9, value=s.status)
            status_cell.alignment = align_center
            status_cell.font = font_bold
            if s.status == "PAID":
                status_cell.fill = fill_paid
            elif s.status == "PENDING":
                status_cell.fill = fill_pending
            elif s.status == "PARTIAL":
                status_cell.fill = fill_partial

            ws3.cell(row=row_idx, column=10, value=s.razorpay_payment_link_url or "N/A")

            for c_idx in range(1, 11):
                ws3.cell(row=row_idx, column=c_idx).border = thin_border

            row_idx += 1

        # Auto-fit column widths across all sheets
        for sheet in [ws1, ws2, ws3]:
            for col in sheet.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.row in [1, 2]: # Skip merged title banner
                        continue
                    val = str(cell.value or "")
                    if len(val) > max_len:
                        max_len = len(val)
                sheet.column_dimensions[col_letter].width = max(max_len + 4, 12)

        # Output to bytes
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()


analytics_service = AnalyticsService()
