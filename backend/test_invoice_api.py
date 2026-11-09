
from decimal import Decimal


def create_test_customer(client, email="invoice.test@example.com"):
    response = client.post(
        "/api/v1/customers/",
        json={
            "name": "Invoice Test Customer",
            "email": email,
        },
    )

    assert response.status_code == 201
    return response.json()


def create_test_product(client):
    response = client.post(
        "/api/v1/products/",
        json={
            "sku": "INVOICE-TEST-001",
            "name": "Invoice Test Product",
            "unit_price": "100.00",
            "stock_quantity": 20,
        },
    )

    assert response.status_code == 201
    return response.json()


def create_test_order(client, customer_id, product_id):
    response = client.post(
        "/api/v1/sales-orders/",
        json={
            "order_number": "INVOICE-TEST-ORDER",
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 2,
                }
            ],
        },
    )

    assert response.status_code == 201
    return response.json()


def create_test_invoice(
    client,
    customer_id,
    invoice_number="TEST-INVOICE-001",
    amount="500.00",
    sales_order_id=None,
    issue_date="2026-01-01",
    due_date="2026-12-01",
):
    return client.post(
        "/api/v1/invoices/",
        json={
            "invoice_number": invoice_number,
            "customer_id": customer_id,
            "sales_order_id": sales_order_id,
            "amount": amount,
            "issue_date": issue_date,
            "due_date": due_date,
        },
    )


def test_create_invoice(client):
    customer = create_test_customer(client)

    response = create_test_invoice(
        client,
        customer["id"],
    )

    assert response.status_code == 201

    data = response.json()

    assert data["invoice_number"] == "TEST-INVOICE-001"
    assert data["customer_id"] == customer["id"]
    assert data["sales_order_id"] is None
    assert Decimal(data["amount"]) == Decimal("500.00")
    assert Decimal(data["amount_paid"]) == Decimal("0.00")
    assert data["status"] == "unpaid"


def test_create_invoice_with_sales_order(client):
    customer = create_test_customer(client)
    product = create_test_product(client)

    order = create_test_order(
        client,
        customer["id"],
        product["id"],
    )

    response = create_test_invoice(
        client,
        customer["id"],
        sales_order_id=order["id"],
    )

    assert response.status_code == 201
    assert response.json()["sales_order_id"] == order["id"]


def test_create_invoice_with_nonexistent_customer(client):
    response = create_test_invoice(
        client,
        customer_id=999999,
    )

    assert response.status_code == 404


def test_create_invoice_with_nonexistent_sales_order(client):
    customer = create_test_customer(client)

    response = create_test_invoice(
        client,
        customer["id"],
        sales_order_id=999999,
    )

    assert response.status_code == 404


def test_create_invoice_with_order_from_another_customer(client):
    customer1 = create_test_customer(
        client,
        email="customer1.invoice@example.com",
    )
    customer2 = create_test_customer(
        client,
        email="customer2.invoice@example.com",
    )
    product = create_test_product(client)

    order = create_test_order(
        client,
        customer1["id"],
        product["id"],
    )

    response = create_test_invoice(
        client,
        customer2["id"],
        sales_order_id=order["id"],
    )

    assert response.status_code == 409


def test_create_invoice_with_due_date_before_issue_date(client):
    customer = create_test_customer(client)

    response = create_test_invoice(
        client,
        customer["id"],
        issue_date="2026-06-10",
        due_date="2026-06-01",
    )

    assert response.status_code == 422


def test_duplicate_invoice_number(client):
    customer = create_test_customer(client)

    first = create_test_invoice(
        client,
        customer["id"],
        invoice_number="DUPLICATE-INVOICE",
    )

    second = create_test_invoice(
        client,
        customer["id"],
        invoice_number="DUPLICATE-INVOICE",
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_create_invoice_with_invalid_amount(client):
    customer = create_test_customer(client)

    response = create_test_invoice(
        client,
        customer["id"],
        amount="0",
    )

    assert response.status_code == 422


def test_list_and_get_invoices(client):
    customer = create_test_customer(client)

    created = create_test_invoice(
        client,
        customer["id"],
    )

    invoice_id = created.json()["id"]

    list_response = client.get("/api/v1/invoices/")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(
        f"/api/v1/invoices/{invoice_id}"
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == invoice_id
    assert detail_response.json()["invoice_number"] == "TEST-INVOICE-001"


def test_get_nonexistent_invoice(client):
    response = client.get("/api/v1/invoices/999999")

    assert response.status_code == 404


def test_filter_invoices_by_status(client):
    customer = create_test_customer(client)

    invoice = create_test_invoice(
        client,
        customer["id"],
    )

    invoice_id = invoice.json()["id"]

    payment = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": "100.00"},
    )

    assert payment.status_code == 200

    unpaid = client.get(
        "/api/v1/invoices/",
        params={"status": "unpaid"},
    )

    partially_paid = client.get(
        "/api/v1/invoices/",
        params={"status": "partially_paid"},
    )

    assert unpaid.status_code == 200
    assert len(unpaid.json()) == 0

    assert partially_paid.status_code == 200
    assert len(partially_paid.json()) == 1


def test_filter_invoices_by_customer(client):
    customer1 = create_test_customer(
        client,
        email="filter1@example.com",
    )
    customer2 = create_test_customer(
        client,
        email="filter2@example.com",
    )

    create_test_invoice(
        client,
        customer1["id"],
        invoice_number="FILTER-INVOICE-1",
    )

    create_test_invoice(
        client,
        customer2["id"],
        invoice_number="FILTER-INVOICE-2",
    )

    response = client.get(
        "/api/v1/invoices/",
        params={"customer_id": customer1["id"]},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["customer_id"] == customer1["id"]


def test_filter_overdue_invoices(client):
    customer = create_test_customer(client)

    overdue = create_test_invoice(
        client,
        customer["id"],
        invoice_number="OVERDUE-INVOICE",
        issue_date="2025-01-01",
        due_date="2025-02-01",
    )

    current = create_test_invoice(
        client,
        customer["id"],
        invoice_number="CURRENT-INVOICE",
        issue_date="2026-01-01",
        due_date="2026-12-01",
    )

    assert overdue.status_code == 201
    assert current.status_code == 201

    response = client.get(
        "/api/v1/invoices/",
        params={"overdue_only": True},
    )

    assert response.status_code == 200

    invoices = response.json()

    assert len(invoices) == 1
    assert invoices[0]["invoice_number"] == "OVERDUE-INVOICE"


def test_overdue_filter_excludes_fully_paid_invoices(client):
    customer = create_test_customer(client)

    invoice = create_test_invoice(
        client,
        customer["id"],
        issue_date="2025-01-01",
        due_date="2025-02-01",
    )

    invoice_id = invoice.json()["id"]

    payment = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": "500.00"},
    )

    assert payment.status_code == 200
    assert payment.json()["status"] == "paid"

    response = client.get(
        "/api/v1/invoices/",
        params={"overdue_only": True},
    )

    assert response.status_code == 200
    assert len(response.json()) == 0


def test_record_partial_payment(client):
    customer = create_test_customer(client)

    invoice = create_test_invoice(
        client,
        customer["id"],
        amount="500.00",
    )

    invoice_id = invoice.json()["id"]

    response = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": "200.00"},
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["amount_paid"]) == Decimal("200.00")
    assert data["status"] == "partially_paid"


def test_record_full_payment(client):
    customer = create_test_customer(client)

    invoice = create_test_invoice(
        client,
        customer["id"],
        amount="500.00",
    )

    invoice_id = invoice.json()["id"]

    response = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": "500.00"},
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["amount_paid"]) == Decimal("500.00")
    assert data["status"] == "paid"


def test_multiple_payments_complete_invoice(client):
    customer = create_test_customer(client)

    invoice = create_test_invoice(
        client,
        customer["id"],
        amount="500.00",
    )

    invoice_id = invoice.json()["id"]

    first_payment = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": "200.00"},
    )

    second_payment = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": "300.00"},
    )

    assert first_payment.status_code == 200
    assert second_payment.status_code == 200

    data = second_payment.json()

    assert Decimal(data["amount_paid"]) == Decimal("500.00")
    assert data["status"] == "paid"


def test_payment_exceeding_outstanding_balance(client):
    customer = create_test_customer(client)

    invoice = create_test_invoice(
        client,
        customer["id"],
        amount="500.00",
    )

    invoice_id = invoice.json()["id"]

    response = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": "600.00"},
    )

    assert response.status_code == 409

    current_invoice = client.get(
        f"/api/v1/invoices/{invoice_id}"
    )

    assert Decimal(current_invoice.json()["amount_paid"]) == Decimal("0.00")
    assert current_invoice.json()["status"] == "unpaid"


def test_payment_on_nonexistent_invoice(client):
    response = client.post(
        "/api/v1/invoices/999999/payments",
        json={"amount": "100.00"},
    )

    assert response.status_code == 404


def test_payment_with_invalid_amount(client):
    customer = create_test_customer(client)

    invoice = create_test_invoice(
        client,
        customer["id"],
    )

    response = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        json={"amount": "0"},
    )

    assert response.status_code == 422
