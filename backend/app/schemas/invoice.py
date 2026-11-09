
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceCreate(BaseModel):
    invoice_number: str = Field(min_length=2, max_length=50)
    customer_id: int = Field(gt=0)
    sales_order_id: int | None = Field(default=None, gt=0)
    amount: Decimal = Field(gt=0)
    issue_date: date
    due_date: date


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    customer_id: int
    sales_order_id: int | None
    amount: Decimal
    amount_paid: Decimal
    issue_date: date
    due_date: date
    status: str
    created_at: datetime
