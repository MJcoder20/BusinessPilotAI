
import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models import (
    Customer,
    Product,
    SalesOrder,
    OrderItem,
    Invoice,
    Opportunity,
)


def money(value):
    return Decimal(str(value)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


CUSTOMERS = [
    {
        "name": f"Demo Customer {i:02d}",
        "email": f"demo.customer{i:02d}@businesspilot.example",
        "company": f"Demo Company {i:02d}",
        "industry": [
            "Technology", "Retail", "Healthcare",
            "Education", "Manufacturing",
        ][(i - 1) % 5],
        "country": [
            "Palestine", "Jordan", "UAE",
            "Egypt", "Saudi Arabia",
        ][(i - 1) % 5],
        "phone": f"+970590000{i:03d}",
        "credit_limit": money(5000 + i * 1000),
    }
    for i in range(1, 21)
]


PRODUCTS = [
    {
        "sku": f"DEMO-SKU-{i:03d}",
        "name": [
            "Business Laptop", "Wireless Mouse", "Mechanical Keyboard",
            "USB-C Hub", "Monitor 27 Inch", "Office Chair",
            "Standing Desk", "Webcam HD", "Headset Pro",
            "External SSD", "Network Router", "Tablet",
            "Smartphone", "Docking Station", "Portable Projector",
        ][i - 1],
        "description": "Synthetic demonstration inventory item.",
        "unit_price": money([
            899.00, 24.50, 79.99, 45.00, 279.00,
            189.00, 349.00, 59.99, 89.00, 119.00,
            149.00, 499.00, 699.00, 159.00, 429.00,
        ][i - 1]),
        "stock_quantity": [
            3, 25, 18, 8, 12, 7, 20, 9, 30,
            5, 14, 6, 22, 10, 16,
        ][i - 1],
    }
    for i in range(1, 16)
]


ORDER_STATUSES = (
    ["pending"] * 4
    + ["confirmed"] * 5
    + ["processing"] * 5
    + ["shipped"] * 5
    + ["delivered"] * 8
    + ["cancelled"] * 3
)


def seed_database(db):
    today = date.today()
    now = datetime.now(timezone.utc)

    inserted = {
        "customers": 0,
        "products": 0,
        "orders": 0,
        "order_items": 0,
        "invoices": 0,
        "opportunities": 0,
    }

    # Customers
    customers_by_email = {}

    for data in CUSTOMERS:
        customer = (
            db.query(Customer)
            .filter(Customer.email == data["email"])
            .first()
        )

        if customer is None:
            customer = Customer(**data)
            db.add(customer)
            inserted["customers"] += 1

        customers_by_email[data["email"]] = customer

    db.flush()

    # Products
    products_by_sku = {}

    for data in PRODUCTS:
        product = (
            db.query(Product)
            .filter(Product.sku == data["sku"])
            .first()
        )

        if product is None:
            product = Product(**data)
            db.add(product)
            inserted["products"] += 1

        products_by_sku[data["sku"]] = product

    db.flush()

    # Sales orders and their line items
    orders_by_number = {}

    for i, status in enumerate(ORDER_STATUSES, start=1):
        order_number = f"DEMO-SO-{i:03d}"

        order = (
            db.query(SalesOrder)
            .filter(SalesOrder.order_number == order_number)
            .first()
        )

        if order is None:
            customer_index = (i - 1) % len(CUSTOMERS)
            customer = customers_by_email[
                CUSTOMERS[customer_index]["email"]
            ]

            item_count = 1 + (i % 3)
            total = money(0)

            order = SalesOrder(
                order_number=order_number,
                customer_id=customer.id,
                status=status,
                total_amount=money(0),
                created_at=now - timedelta(days=30 - i),
            )

            db.add(order)
            db.flush()

            for j in range(item_count):
                product_index = (i * 3 + j) % len(PRODUCTS)
                product = products_by_sku[
                    PRODUCTS[product_index]["sku"]
                ]

                quantity = 1 + ((i + j) % 3)
                unit_price = product.unit_price

                db.add(
                    OrderItem(
                        sales_order_id=order.id,
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=unit_price,
                    )
                )

                total += unit_price * quantity
                inserted["order_items"] += 1

            order.total_amount = money(total)
            inserted["orders"] += 1

        orders_by_number[order_number] = order

    db.flush()

    # Invoices: overdue, upcoming, unpaid, partially paid, and paid
    for i in range(1, 26):
        invoice_number = f"DEMO-INV-{i:03d}"

        existing = (
            db.query(Invoice)
            .filter(Invoice.invoice_number == invoice_number)
            .first()
        )

        if existing is not None:
            continue

        order = orders_by_number[f"DEMO-SO-{i:03d}"]

        if i <= 8:
            due_date = today - timedelta(days=i * 3)
        else:
            due_date = today + timedelta(days=(i - 8) * 4)

        issue_date = due_date - timedelta(days=30)
        amount = money(order.total_amount)

        if i % 4 == 0:
            amount_paid = amount
            status = "paid"
        elif i % 4 == 1:
            amount_paid = money(amount * Decimal("0.40"))
            status = "partially_paid"
        else:
            amount_paid = money(0)
            status = "unpaid"

        db.add(
            Invoice(
                invoice_number=invoice_number,
                customer_id=order.customer_id,
                sales_order_id=order.id,
                amount=amount,
                amount_paid=amount_paid,
                issue_date=issue_date,
                due_date=due_date,
                status=status,
            )
        )

        inserted["invoices"] += 1

    # Sales opportunities
    stages = [
        "qualification",
        "needs_analysis",
        "proposal",
        "negotiation",
        "closed_won",
        "closed_lost",
    ]

    for i in range(1, 11):
        title = f"DEMO - Sales Opportunity {i:02d}"

        existing = (
            db.query(Opportunity)
            .filter(Opportunity.title == title)
            .first()
        )

        if existing is not None:
            continue

        customer = customers_by_email[
            CUSTOMERS[(i - 1) % len(CUSTOMERS)]["email"]
        ]

        db.add(
            Opportunity(
                title=title,
                customer_id=customer.id,
                estimated_value=money(3000 + i * 2500),
                probability=min(10 + i * 8, 90),
                stage=stages[(i - 1) % len(stages)],
                expected_close_date=(
                    now + timedelta(days=15 * i)
                ),
            )
        )

        inserted["opportunities"] += 1

    db.flush()
    return inserted


def main():
    parser = argparse.ArgumentParser(
        description="Seed synthetic BusinessPilot AI demo data."
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the demo data. Without this flag, only preview.",
    )

    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="Explicitly authorize writes to a remote/production database.",
    )

    args = parser.parse_args()

    database_url = make_url(settings.resolved_database_url)
    host = database_url.host or "unknown"
    database = database_url.database or "unknown"

    local_hosts = {"localhost", "127.0.0.1", "::1", "db"}
    is_remote = host not in local_hosts
    is_production = settings.app_env == "production"

    print(f"\nDatabase host: {host}")
    print(f"Database name: {database}")
    print(f"Application environment: {settings.app_env}")

    if args.apply and (is_remote or is_production):
        if not args.confirm_production:
            parser.error(
                "Remote/production writes require --confirm-production."
            )

    db = SessionLocal()

    try:
        inserted = seed_database(db)

        print("\nDemo data summary:")

        for name, count in inserted.items():
            print(f"  {name}: {count}")

        if args.apply:
            db.commit()
            print("\nDemo data committed successfully.")
        else:
            db.rollback()
            print("\nDry run complete. No changes were committed.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
