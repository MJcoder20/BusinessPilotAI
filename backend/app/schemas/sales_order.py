from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class OrderItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class SalesOrderCreate(BaseModel):
    order_number: str = Field(min_length=2, max_length=50)
    customer_id: int = Field(gt=0)
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    unit_price: Decimal


class SalesOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    customer_id: int
    status: str
    total_amount: Decimal
    created_at: datetime
    items: list[OrderItemResponse]

    
class SalesOrderStatusUpdate(BaseModel):
    status: Literal[
        "confirmed",
        "processing",
        "shipped",
        "delivered"
    ]