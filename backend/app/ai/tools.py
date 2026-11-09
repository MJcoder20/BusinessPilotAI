
from datetime import date
from decimal import Decimal

from langchain.tools import tool
from sqlalchemy import func

from app.core.database import SessionLocal
from app.models import Customer, Product, SalesOrder, Invoice


@tool
def get_business_dashboard() -> dict:
    """Get overall business KPIs, including customers, products, orders,
    sales, collected payments, outstanding balances, and overdue invoices."""

    with SessionLocal() as db:
        total_customers = db.query(func.count(Customer.id)).scalar() or 0
        total_products = db.query(func.count(Product.id)).scalar() or 0
        total_orders = db.query(func.count(SalesOrder.id)).scalar() or 0

        total_sales = (
            db.query(func.sum(SalesOrder.total_amount))
            .filter(SalesOrder.status != "cancelled")
            .scalar()
            or Decimal("0.00")
        )

        total_invoiced = (
            db.query(func.sum(Invoice.amount)).scalar()
            or Decimal("0.00")
        )

        total_collected = (
            db.query(func.sum(Invoice.amount_paid)).scalar()
            or Decimal("0.00")
        )

        overdue_count = (
            db.query(func.count(Invoice.id))
            .filter(
                Invoice.due_date < date.today(),
                Invoice.amount > Invoice.amount_paid,
            )
            .scalar()
            or 0
        )

        return {
            "total_customers": total_customers,
            "total_products": total_products,
            "total_orders": total_orders,
            "total_sales": str(total_sales),
            "total_invoiced": str(total_invoiced),
            "total_collected": str(total_collected),
            "outstanding_balance": str(
                total_invoiced - total_collected
            ),
            "overdue_invoices": overdue_count,
        }


@tool
def get_top_customers(limit: int = 5) -> list[dict]:
    """Find customers ranked by the total value of their non-cancelled sales orders.
    Use this when asked about top, best, or highest-value customers."""

    if limit < 1 or limit > 20:
        return [{"error": "Limit must be between 1 and 20."}]

    with SessionLocal() as db:
        results = (
            db.query(
                Customer.id,
                Customer.name,
                Customer.company,
                func.sum(
                    SalesOrder.total_amount
                ).label("total_spent"),
            )
            .join(
                SalesOrder,
                SalesOrder.customer_id == Customer.id,
            )
            .filter(SalesOrder.status != "cancelled")
            .group_by(
                Customer.id,
                Customer.name,
                Customer.company,
            )
            .order_by(
                func.sum(SalesOrder.total_amount).desc()
            )
            .limit(limit)
            .all()
        )

        return [
            {
                "customer_id": row.id,
                "name": row.name,
                "company": row.company,
                "total_spent": str(row.total_spent),
            }
            for row in results
        ]


@tool
def get_low_stock_products(threshold: int = 10) -> list[dict]:
    """Retrieve products with stock_quantity <= threshold.
        Always use this tool for inventory shortage questions.
        The default threshold is 10 units.
        If the user does not specify a threshold, use 10.
        Never ask the user for a threshold unless they explicitly want
        a different threshold."""

    if threshold < 0 or threshold > 100000:
        return [{"error": "Threshold must be between 0 and 100000."}]

    with SessionLocal() as db:
        products = (
            db.query(Product)
            .filter(Product.stock_quantity <= threshold)
            .order_by(Product.stock_quantity.asc())
            .all()
        )

        return [
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "stock_quantity": product.stock_quantity,
            }
            for product in products
        ]


@tool
def get_overdue_invoices() -> list[dict]:
    """Find invoices past their due date that still have an outstanding balance.
    Use this when asked about overdue or unpaid invoices."""

    with SessionLocal() as db:
        invoices = (
            db.query(Invoice)
            .filter(
                Invoice.due_date < date.today(),
                Invoice.amount > Invoice.amount_paid,
            )
            .order_by(Invoice.due_date.asc())
            .all()
        )

        return [
            {
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_id": invoice.customer_id,
                "amount": str(invoice.amount),
                "amount_paid": str(invoice.amount_paid),
                "outstanding_balance": str(
                    invoice.amount - invoice.amount_paid
                ),
                "due_date": invoice.due_date.isoformat(),
            }
            for invoice in invoices
        ]


@tool
def get_daily_revenue() -> list[dict]:
    """Get sales revenue grouped by day, excluding cancelled sales orders.
    Use this for questions about daily revenue and sales trends."""

    with SessionLocal() as db:
        results = (
            db.query(
                func.date(SalesOrder.created_at).label("date"),
                func.sum(
                    SalesOrder.total_amount
                ).label("revenue"),
            )
            .filter(SalesOrder.status != "cancelled")
            .group_by(func.date(SalesOrder.created_at))
            .order_by(func.date(SalesOrder.created_at))
            .all()
        )

        return [
            {
                "date": str(row.date),
                "revenue": str(
                    row.revenue or Decimal("0.00")
                ),
            }
            for row in results
        ]


business_tools = [
    get_business_dashboard,
    get_top_customers,
    get_low_stock_products,
    get_overdue_invoices,
    get_daily_revenue,
]
