
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.core.database import get_db
from app.models import Invoice, Customer, SalesOrder, User
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    PaymentCreate,
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("/", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    invoice_data: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "manager")),
):
    customer = db.query(Customer).filter(
        Customer.id == invoice_data.customer_id
    ).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    if invoice_data.sales_order_id is not None:
        order = db.query(SalesOrder).filter(
            SalesOrder.id == invoice_data.sales_order_id
        ).first()

        if not order:
            raise HTTPException(status_code=404, detail="Sales order not found.")

        if order.customer_id != invoice_data.customer_id:
            raise HTTPException(
                status_code=409,
                detail="Sales order does not belong to this customer."
            )

    if invoice_data.due_date < invoice_data.issue_date:
        raise HTTPException(
            status_code=422,
            detail="Due date cannot be earlier than issue date."
        )

    existing = db.query(Invoice).filter(
        Invoice.invoice_number == invoice_data.invoice_number
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Invoice number already exists."
        )

    invoice = Invoice(
        invoice_number=invoice_data.invoice_number,
        customer_id=invoice_data.customer_id,
        sales_order_id=invoice_data.sales_order_id,
        amount=invoice_data.amount,
        amount_paid=Decimal("0.00"),
        issue_date=invoice_data.issue_date,
        due_date=invoice_data.due_date,
        status="unpaid"
    )

    try:
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice
    except Exception:
        db.rollback()
        raise


@router.get("/", response_model=list[InvoiceResponse])
def get_invoices(
    status: str | None = None,
    customer_id: int | None = Query(default=None, gt=0),
    overdue_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Invoice)

    if status:
        query = query.filter(Invoice.status == status)

    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    if overdue_only:
        query = query.filter(
            Invoice.due_date < date.today(),
            Invoice.amount > Invoice.amount_paid
        )

    return query.order_by(Invoice.id.desc()).all()


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    return invoice


@router.post("/{invoice_id}/payments", response_model=InvoiceResponse)
def record_payment(
    invoice_id: int,
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "manager")),
):
    try:
        invoice = (
            db.query(Invoice)
            .filter(Invoice.id == invoice_id)
            .with_for_update()
            .first()
        )

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        outstanding = invoice.amount - invoice.amount_paid

        if payment_data.amount > outstanding:
            raise HTTPException(
                status_code=409,
                detail="Payment exceeds the outstanding balance."
            )

        invoice.amount_paid += payment_data.amount

        if invoice.amount_paid == invoice.amount:
            invoice.status = "paid"
        else:
            invoice.status = "partially_paid"

        db.commit()
        db.refresh(invoice)

        return invoice

    except Exception:
        db.rollback()
        raise
