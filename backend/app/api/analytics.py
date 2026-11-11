
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import (
    Customer,
    Product,
    SalesOrder,
    Invoice,
    User,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

    outstanding = total_invoiced - total_collected

    overdue_count = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.due_date < date.today(),
            Invoice.amount > Invoice.amount_paid
        )
        .scalar()
        or 0
    )

    return {
        "total_customers": total_customers,
        "total_products": total_products,
        "total_orders": total_orders,
        "total_sales": total_sales,
        "total_invoiced": total_invoiced,
        "total_collected": total_collected,
        "outstanding_balance": outstanding,
        "overdue_invoices": overdue_count,
    }


@router.get("/revenue")
def revenue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = (
        db.query(
            func.date(SalesOrder.created_at).label("date"),
            func.sum(SalesOrder.total_amount).label("revenue"),
        )
        .filter(SalesOrder.status != "cancelled")
        .group_by(func.date(SalesOrder.created_at))
        .order_by(func.date(SalesOrder.created_at))
        .all()
    )

    return [
        {
            "date": str(row.date),
            "revenue": row.revenue or Decimal("0.00")
        }
        for row in results
    ]


@router.get("/top-customers")
def top_customers(
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = (
        db.query(
            Customer.id,
            Customer.name,
            Customer.company,
            func.sum(SalesOrder.total_amount).label("total_spent"),
        )
        .join(SalesOrder, SalesOrder.customer_id == Customer.id)
        .filter(SalesOrder.status != "cancelled")
        .group_by(Customer.id, Customer.name, Customer.company)
        .order_by(func.sum(SalesOrder.total_amount).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "customer_id": row.id,
            "name": row.name,
            "company": row.company,
            "total_spent": row.total_spent,
        }
        for row in results
    ]


@router.get("/low-stock")
def low_stock(
    threshold: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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


@router.get("/overdue-invoices")
def overdue_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
            "amount": invoice.amount,
            "amount_paid": invoice.amount_paid,
            "outstanding_balance": (
                invoice.amount - invoice.amount_paid
            ),
            "due_date": invoice.due_date,
        }
        for invoice in invoices
    ]
