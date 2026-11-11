from decimal import Decimal

from app.models import User


def get_invoice_auth_headers(
    client,
    db_session,
    role="manager",
    email="invoice-manager@example.com",
):
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Invoice Test User",
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert register_response.status_code == 201

    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None

    user.role = role
    db_session.flush()

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert login_response.status_code == 200

    return {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }


def create_test_customer(
    client,
    headers,
    email="invoice.test@example.com",
):
    response = client.post(
        "/api/v1/customers/",
        headers=headers,
        json={
            "name": "Invoice Test Customer",
            "email": email,
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def create_test_product(client, headers):
    response = client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": "INVOICE-TEST-001",
            "name": "Invoice Test Product",
            "unit_price": "100.00",
            "stock_quantity": 20,
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def create_test_order(client, headers, customer_id, product_id):
    response = client.post(
        "/api/v1/sales-orders/",
        headers=headers,
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

    assert response.status_code == 201, response.text
    return response.json()


def create_test_invoice(
    client,
    headers,
    customer_id,
    invoice_number="TEST-INVOICE-001",
    amount="500.00",
    sales_order_id=None,
    issue_date="2026-01-01",
    due_date="2026-12-01",
):
    return client.post(
        "/api/v1/invoices/",
        headers=headers,
        json={
            "invoice_number": invoice_number,
            "customer_id": customer_id,
            "sales_order_id": sales_order_id,
            "amount": amount,
            "issue_date": issue_date,
            "due_date": due_date,
        },
    )

def test_create_invoice(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-create@example.com",
    )

    customer = create_test_customer(client, manager_headers)

    response = create_test_invoice(
        client,
        manager_headers,
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

def test_create_invoice_with_sales_order(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-with-order@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(client, manager_headers)

    order = create_test_order(
        client,
        manager_headers,
        customer["id"],
        product["id"],
    )

    response = create_test_invoice(
        client,
        manager_headers,
        customer["id"],
        sales_order_id=order["id"],
    )

    assert response.status_code == 201
    assert response.json()["sales_order_id"] == order["id"]

def test_create_invoice_with_nonexistent_customer(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-missing-customer@example.com",
    )

    response = create_test_invoice(
        client,
        manager_headers,
        customer_id=999999,
    )

    assert response.status_code == 404

def test_create_invoice_with_nonexistent_sales_order(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-missing-order@example.com",
    )

    customer = create_test_customer(client, manager_headers)

    response = create_test_invoice(
        client,
        manager_headers,
        customer["id"],
        sales_order_id=999999,
    )

    assert response.status_code == 404

def test_create_invoice_with_order_from_another_customer(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-wrong-customer@example.com",
    )

    customer1 = create_test_customer(
        client, manager_headers,
        email="customer1.invoice@example.com",
    )
    customer2 = create_test_customer(
        client, manager_headers,
        email="customer2.invoice@example.com",
    )
    product = create_test_product(client, manager_headers)

    order = create_test_order(
        client,
        manager_headers,
        customer1["id"],
        product["id"],
    )

    response = create_test_invoice(
        client,
        manager_headers,
        customer2["id"],
        sales_order_id=order["id"],
    )

    assert response.status_code == 409

def test_create_invoice_with_due_date_before_issue_date(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-invalid-dates@example.com",
    )

    customer = create_test_customer(client, manager_headers)

    response = create_test_invoice(
        client,
        manager_headers,
        customer["id"],
        issue_date="2026-06-10",
        due_date="2026-06-01",
    )

    assert response.status_code == 422

def test_duplicate_invoice_number(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-duplicate@example.com",
    )

    customer = create_test_customer(client, manager_headers)

    first = create_test_invoice(
        client,
        manager_headers,
        customer["id"],
        invoice_number="DUPLICATE-INVOICE",
    )

    second = create_test_invoice(
        client,
        manager_headers,
        customer["id"],
        invoice_number="DUPLICATE-INVOICE",
    )

    assert first.status_code == 201
    assert second.status_code == 409
def test_create_invoice_with_invalid_amount(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-invalid-amount@example.com",
    )

    customer = create_test_customer(client, manager_headers)

    response = create_test_invoice(
        client,
        manager_headers,
        customer["id"],
        amount="0",
    )

    assert response.status_code == 422

def test_list_and_get_invoices(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-list@example.com",
    )
    employee_headers = get_invoice_auth_headers(
        client, db_session,
        role="employee",
        email="invoice-employee-list@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    created = create_test_invoice(
        client, manager_headers, customer["id"],
    )

    invoice_id = created.json()["id"]

    list_response = client.get(
        "/api/v1/invoices/",
        headers=employee_headers,
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(
        f"/api/v1/invoices/{invoice_id}",
        headers=employee_headers,
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == invoice_id
    assert detail_response.json()["invoice_number"] == "TEST-INVOICE-001"

def test_get_nonexistent_invoice(client, db_session):
    employee_headers = get_invoice_auth_headers(
        client, db_session,
        role="employee",
        email="invoice-employee-missing@example.com",
    )

    response = client.get(
        "/api/v1/invoices/999999",
        headers=employee_headers,
    )

    assert response.status_code == 404


def test_filter_invoices_by_status(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-status-filter@example.com",
    )
    employee_headers = get_invoice_auth_headers(
        client, db_session,
        role="employee",
        email="invoice-employee-status-filter@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    invoice = create_test_invoice(
        client, manager_headers, customer["id"],
    )

    payment = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        headers=manager_headers,
        json={"amount": "100.00"},
    )

    assert payment.status_code == 200

    unpaid = client.get(
        "/api/v1/invoices/",
        headers=employee_headers,
        params={"status": "unpaid"},
    )

    partially_paid = client.get(
        "/api/v1/invoices/",
        headers=employee_headers,
        params={"status": "partially_paid"},
    )

    assert unpaid.status_code == 200
    assert len(unpaid.json()) == 0

    assert partially_paid.status_code == 200
    assert len(partially_paid.json()) == 1

def test_filter_invoices_by_customer(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-customer-filter@example.com",
    )
    employee_headers = get_invoice_auth_headers(
        client, db_session,
        role="employee",
        email="invoice-employee-customer-filter@example.com",
    )

    customer1 = create_test_customer(
        client, manager_headers,
        email="filter1@example.com",
    )
    customer2 = create_test_customer(
        client, manager_headers,
        email="filter2@example.com",
    )

    create_test_invoice(
        client, manager_headers, customer1["id"],
        invoice_number="FILTER-INVOICE-1",
    )
    create_test_invoice(
        client, manager_headers, customer2["id"],
        invoice_number="FILTER-INVOICE-2",
    )

    response = client.get(
        "/api/v1/invoices/",
        headers=employee_headers,
        params={"customer_id": customer1["id"]},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["customer_id"] == customer1["id"]

def test_filter_overdue_invoices(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-overdue-filter@example.com",
    )
    employee_headers = get_invoice_auth_headers(
        client, db_session,
        role="employee",
        email="invoice-employee-overdue-filter@example.com",
    )

    customer = create_test_customer(client, manager_headers)

    overdue = create_test_invoice(
        client, manager_headers, customer["id"],
        invoice_number="OVERDUE-INVOICE",
        issue_date="2025-01-01",
        due_date="2025-02-01",
    )

    current = create_test_invoice(
        client, manager_headers, customer["id"],
        invoice_number="CURRENT-INVOICE",
        issue_date="2026-01-01",
        due_date="2026-12-01",
    )

    assert overdue.status_code == 201
    assert current.status_code == 201

    response = client.get(
        "/api/v1/invoices/",
        headers=employee_headers,
        params={"overdue_only": True},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["invoice_number"] == "OVERDUE-INVOICE"

def test_overdue_filter_excludes_fully_paid_invoices(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-paid-overdue@example.com",
    )
    employee_headers = get_invoice_auth_headers(
        client, db_session,
        role="employee",
        email="invoice-employee-paid-overdue@example.com",
    )

    customer = create_test_customer(client, manager_headers)

    invoice = create_test_invoice(
        client, manager_headers, customer["id"],
        issue_date="2025-01-01",
        due_date="2025-02-01",
    )

    payment = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        headers=manager_headers,
        json={"amount": "500.00"},
    )

    assert payment.status_code == 200
    assert payment.json()["status"] == "paid"

    response = client.get(
        "/api/v1/invoices/",
        headers=employee_headers,
        params={"overdue_only": True},
    )

    assert response.status_code == 200
    assert len(response.json()) == 0

def test_record_partial_payment(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-partial-payment@example.com",
    )
    employee_headers = get_invoice_auth_headers(
        client, db_session,
        role="employee",
        email="invoice-employee-partial-payment@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    invoice = create_test_invoice(
        client, manager_headers, customer["id"],
        amount="500.00",
    )

    response = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        headers=manager_headers,
        json={"amount": "200.00"},
    )

    assert response.status_code == 200

    data = response.json()
    assert Decimal(data["amount_paid"]) == Decimal("200.00")
    assert data["status"] == "partially_paid"

    employee_response = client.get(
        f"/api/v1/invoices/{invoice.json()['id']}",
        headers=employee_headers,
    )

    assert employee_response.status_code == 200
    assert Decimal(employee_response.json()["amount_paid"]) == Decimal("200.00")

def test_record_full_payment(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-full-payment@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    invoice = create_test_invoice(
        client, manager_headers, customer["id"],
        amount="500.00",
    )

    response = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        headers=manager_headers,
        json={"amount": "500.00"},
    )

    assert response.status_code == 200

    data = response.json()
    assert Decimal(data["amount_paid"]) == Decimal("500.00")
    assert data["status"] == "paid"

def test_multiple_payments_complete_invoice(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-multiple-payments@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    invoice = create_test_invoice(
        client, manager_headers, customer["id"],
        amount="500.00",
    )

    invoice_id = invoice.json()["id"]

    first_payment = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        headers=manager_headers,
        json={"amount": "200.00"},
    )

    second_payment = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        headers=manager_headers,
        json={"amount": "300.00"},
    )

    assert first_payment.status_code == 200
    assert second_payment.status_code == 200

    data = second_payment.json()
    assert Decimal(data["amount_paid"]) == Decimal("500.00")
    assert data["status"] == "paid"

def test_payment_exceeding_outstanding_balance(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-excess-payment@example.com",
    )
    employee_headers = get_invoice_auth_headers(
        client, db_session,
        role="employee",
        email="invoice-employee-excess-payment@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    invoice = create_test_invoice(
        client, manager_headers, customer["id"],
        amount="500.00",
    )

    invoice_id = invoice.json()["id"]

    response = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        headers=manager_headers,
        json={"amount": "600.00"},
    )

    assert response.status_code == 409

    current_invoice = client.get(
        f"/api/v1/invoices/{invoice_id}",
        headers=employee_headers,
    )

    assert Decimal(current_invoice.json()["amount_paid"]) == Decimal("0.00")
    assert current_invoice.json()["status"] == "unpaid"

def test_payment_on_nonexistent_invoice(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-missing-payment@example.com",
    )

    response = client.post(
        "/api/v1/invoices/999999/payments",
        headers=manager_headers,
        json={"amount": "100.00"},
    )

    assert response.status_code == 404

def test_payment_with_invalid_amount(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-invalid-payment@example.com",
    )

    customer = create_test_customer(client, manager_headers)

    invoice = create_test_invoice(
        client,
        manager_headers,
        customer["id"],
    )

    response = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        headers=manager_headers,
        json={"amount": "0"},
    )

    assert response.status_code == 422

def test_employee_cannot_create_invoice(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-employee-create@example.com",
    )
    employee_headers = get_invoice_auth_headers(
        client, db_session,
        role="employee",
        email="invoice-employee-create@example.com",
    )

    customer = create_test_customer(client, manager_headers)

    response = create_test_invoice(
        client,
        employee_headers,
        customer["id"],
    )

    assert response.status_code == 403

def test_employee_cannot_record_payment(client, db_session):
    manager_headers = get_invoice_auth_headers(
        client, db_session,
        email="invoice-manager-employee-payment@example.com",
    )
    employee_headers = get_invoice_auth_headers(
        client, db_session,
        role="employee",
        email="invoice-employee-payment@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    invoice = create_test_invoice(
        client, manager_headers, customer["id"],
    )

    response = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        headers=employee_headers,
        json={"amount": "100.00"},
    )

    assert response.status_code == 403

    current_invoice = client.get(
        f"/api/v1/invoices/{invoice.json()['id']}",
        headers=employee_headers,
    )

    assert current_invoice.status_code == 200
    assert Decimal(current_invoice.json()["amount_paid"]) == Decimal("0.00")

def test_admin_can_create_invoice_and_record_payment(client, db_session):
    admin_headers = get_invoice_auth_headers(
        client, db_session,
        role="admin",
        email="invoice-admin-permissions@example.com",
    )

    customer = create_test_customer(client, admin_headers)

    invoice = create_test_invoice(
        client,
        admin_headers,
        customer["id"],
        amount="500.00",
    )

    assert invoice.status_code == 201

    payment = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        headers=admin_headers,
        json={"amount": "200.00"},
    )

    assert payment.status_code == 200
    assert Decimal(payment.json()["amount_paid"]) == Decimal("200.00")
    assert payment.json()["status"] == "partially_paid"