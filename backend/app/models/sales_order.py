from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String, DateTime, Numeric, ForeignKey, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    order_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), default="pending"
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="orders"
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="sales_order",
        cascade="all, delete-orphan"
    )

    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="sales_order"
    )