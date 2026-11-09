from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String, DateTime, Numeric, ForeignKey, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    title: Mapped[str] = mapped_column(
        String(200), nullable=False
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False
    )

    estimated_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    probability: Mapped[int] = mapped_column(default=0)

    stage: Mapped[str] = mapped_column(
        String(50), default="qualification"
    )

    expected_close_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="opportunities"
    )