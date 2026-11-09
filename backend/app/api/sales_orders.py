from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models import Customer, Product, SalesOrder, OrderItem
from app.schemas.sales_order import (
    SalesOrderCreate,
    SalesOrderResponse,
)
from app.schemas.sales_order import SalesOrderStatusUpdate


router = APIRouter(
    prefix="/sales-orders",
    tags=["Sales Orders"]
)


@router.post(
    "/",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_201_CREATED
)
def create_sales_order(
    order_data: SalesOrderCreate,
    db: Session = Depends(get_db)
):
    try:
        # 1. Verify the customer exists.
        customer = db.query(Customer).filter(
            Customer.id == order_data.customer_id
        ).first()

        if not customer:
            raise HTTPException(
                status_code=404,
                detail="Customer not found."
            )

        # 2. Prevent duplicate order numbers.
        existing_order = db.query(SalesOrder).filter(
            SalesOrder.order_number == order_data.order_number
        ).first()

        if existing_order:
            raise HTTPException(
                status_code=409,
                detail="Order number already exists."
            )

        # 3. Combine repeated product IDs into one quantity.
        quantities = {}

        for item in order_data.items:
            quantities[item.product_id] = (
                quantities.get(item.product_id, 0) + item.quantity
            )

        # 4. Lock and validate products in a consistent order.
        products = {}

        for product_id in sorted(quantities):
            product = (
                db.query(Product)
                .filter(Product.id == product_id)
                .with_for_update()
                .first()
            )

            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product {product_id} not found."
                )

            if product.stock_quantity < quantities[product_id]:
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient stock for product {product.name}."
                )

            products[product_id] = product

        # 5. Calculate the total using database prices.
        total = Decimal("0.00")

        for product_id, quantity in quantities.items():
            total += products[product_id].unit_price * quantity

        # 6. Create the order.
        order = SalesOrder(
            order_number=order_data.order_number,
            customer_id=order_data.customer_id,
            status="pending",
            total_amount=total
        )

        db.add(order)
        db.flush()

        # 7. Create order items and reduce inventory.
        for product_id, quantity in quantities.items():
            product = products[product_id]

            order_item = OrderItem(
                sales_order_id=order.id,
                product_id=product_id,
                quantity=quantity,
                unit_price=product.unit_price
            )

            db.add(order_item)
            product.stock_quantity -= quantity

        db.commit()

        # 8. Reload the order with its items.
        saved_order = (
            db.query(SalesOrder)
            .options(joinedload(SalesOrder.items))
            .filter(SalesOrder.id == order.id)
            .first()
        )

        return saved_order

    except Exception:
        db.rollback()
        raise


@router.get("/", response_model=list[SalesOrderResponse])
def get_sales_orders(db: Session = Depends(get_db)):
    return (
        db.query(SalesOrder)
        .options(joinedload(SalesOrder.items))
        .order_by(SalesOrder.id.desc())
        .all()
    )


@router.get("/{order_id}", response_model=SalesOrderResponse)
def get_sales_order(
    order_id: int,
    db: Session = Depends(get_db)
):
    order = (
        db.query(SalesOrder)
        .options(joinedload(SalesOrder.items))
        .filter(SalesOrder.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found."
        )

    return order


@router.patch("/{order_id}/status",
              response_model=SalesOrderResponse)
def update_order_status(
    order_id: int,
    status_data: SalesOrderStatusUpdate,
    db: Session = Depends(get_db)
):
    order = (
        db.query(SalesOrder)
        .filter(SalesOrder.id == order_id)
        .with_for_update()
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found."
        )

    transitions = {
        "pending": "confirmed",
        "confirmed": "processing",
        "processing": "shipped",
        "shipped": "delivered"
    }

    expected_status = transitions.get(order.status)

    if status_data.status != expected_status:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid status transition from {order.status}."
        )

    order.status = status_data.status

    db.commit()
    db.refresh(order)

    return order


@router.post("/{order_id}/cancel",
             response_model=SalesOrderResponse)
def cancel_sales_order(
    order_id: int,
    db: Session = Depends(get_db)
):
    try:
        order = (
            db.query(SalesOrder)
            .filter(SalesOrder.id == order_id)
            .with_for_update()
            .first()
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Sales order not found."
            )

        if order.status == "cancelled":
            raise HTTPException(
                status_code=409,
                detail="Order is already cancelled."
            )

        if order.status in ["shipped", "delivered"]:
            raise HTTPException(
                status_code=409,
                detail="Cannot cancel an order that has been shipped."
            )

        for item in order.items:
            product = (
                db.query(Product)
                .filter(Product.id == item.product_id)
                .with_for_update()
                .first()
            )

            if not product:
                raise HTTPException(
                    status_code=409,
                    detail=f"Product {item.product_id} no longer exists."
                )

            product.stock_quantity += item.quantity

        order.status = "cancelled"

        db.commit()
        db.refresh(order)

        return order

    except Exception:
        db.rollback()
        raise