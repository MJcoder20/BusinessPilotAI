from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr


class CustomerCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    industry: str | None = None
    country: str | None = None
    credit_limit: Decimal = Decimal("0.00")


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str | None
    company: str | None
    industry: str | None
    country: str | None
    credit_limit: Decimal
    created_at: datetime