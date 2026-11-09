from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    String, Date, DateTime, Numeric,
    ForeignKey, func, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    __table_args__ = (
        CheckConstraint("amount >= 0", name="check_invoice_amount"),
        CheckConstraint(
            "amount_paid >= 0 AND amount_paid <= amount",
            name="check_invoice_payment"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    invoice_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )

    sales_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_orders.id")
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )

    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(
        String(30), default="unpaid"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="invoices"
    )

    sales_order: Mapped["SalesOrder"] = relationship(
        back_populates="invoices"
    )

    @property
    def outstanding_balance(self) -> Decimal:
        return self.amount - self.amount_paid