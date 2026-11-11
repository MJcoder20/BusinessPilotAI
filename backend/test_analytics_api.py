from datetime import date, timedelta
from decimal import Decimal

from app.models import User


def get_analytics_auth_headers(
    client,
    db_session,
    role="manager",
    email="analytics-manager@example.com",
):
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Analytics Test User",
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
    name="Analytics Test Customer",
    email="analytics.test@example.com",
    company="Analytics Test Company",
):
    response = client.post(
        "/api/v1/customers/",
        headers=headers,
        json={
            "name": name,
            "email": email,
            "company": company,
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def create_test_product(
    client,
    headers,
    sku="ANALYTICS-TEST-001",
    stock=20,
    price="100.00",
):
    response = client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": sku,
            "name": "Analytics Test Product",
            "unit_price": price,
            "stock_quantity": stock,
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def create_test_order(
    client,
    headers,
    customer_id,
    product_id,
    order_number="ANALYTICS-ORDER-001",
    quantity=2,
):
    return client.post(
        "/api/v1/sales-orders/",
        headers=headers,
        json={
            "order_number": order_number,
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": quantity,
                }
            ],
        },
    )


def create_test_invoice(
    client,
    headers,
    customer_id,
    invoice_number="ANALYTICS-INVOICE-001",
    amount="500.00",
    issue_date=None,
    due_date=None,
):
    today = date.today()

    return client.post(
        "/api/v1/invoices/",
        headers=headers,
        json={
            "invoice_number": invoice_number,
            "customer_id": customer_id,
            "amount": amount,
            "issue_date": (issue_date or today).isoformat(),
            "due_date": (due_date or today + timedelta(days=30)).isoformat(),
        },
    )




def test_dashboard_with_empty_database(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    response = client.get(
        "/api/v1/analytics/dashboard",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_customers"] == 0
    assert data["total_products"] == 0
    assert data["total_orders"] == 0
    assert Decimal(str(data["total_sales"])) == Decimal("0.00")
    assert Decimal(str(data["total_invoiced"])) == Decimal("0.00")
    assert Decimal(str(data["total_collected"])) == Decimal("0.00")
    assert Decimal(str(data["outstanding_balance"])) == Decimal("0.00")
    assert data["overdue_invoices"] == 0


def test_dashboard_totals(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    customer = create_test_customer(client, headers)
    product = create_test_product(
        client,
        headers,
        stock=20,
        price="250.00",
    )

    order = create_test_order(
        client,
        headers,
        customer["id"],
        product["id"],
        quantity=4,
    )

    assert order.status_code == 201

    invoice = create_test_invoice(
        client,
        headers,
        customer["id"],
        amount="1000.00",
    )

    assert invoice.status_code == 201

    payment = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        headers=headers,
        json={"amount": "400.00"},
    )

    assert payment.status_code == 200

    response = client.get(
        "/api/v1/analytics/dashboard",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_customers"] == 1
    assert data["total_products"] == 1
    assert data["total_orders"] == 1
    assert Decimal(str(data["total_sales"])) == Decimal("1000.00")
    assert Decimal(str(data["total_invoiced"])) == Decimal("1000.00")
    assert Decimal(str(data["total_collected"])) == Decimal("400.00")
    assert Decimal(str(data["outstanding_balance"])) == Decimal("600.00")
    assert data["overdue_invoices"] == 0


def test_dashboard_excludes_cancelled_orders_from_sales(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    customer = create_test_customer(client, headers)
    product = create_test_product(client, headers)

    order = create_test_order(
        client,
        headers,
        customer["id"],
        product["id"],
    )

    assert order.status_code == 201

    cancel = client.post(
        f"/api/v1/sales-orders/{order.json()['id']}/cancel",
        headers=headers,
    )

    assert cancel.status_code == 200

    response = client.get(
        "/api/v1/analytics/dashboard",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_orders"] == 1
    assert Decimal(str(data["total_sales"])) == Decimal("0.00")


def test_dashboard_counts_overdue_unpaid_invoices(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)
    customer = create_test_customer(client, headers)

    invoice = create_test_invoice(
        client,
        headers,
        customer["id"],
        issue_date=date.today() - timedelta(days=30),
        due_date=date.today() - timedelta(days=5),
    )

    assert invoice.status_code == 201

    response = client.get(
        "/api/v1/analytics/dashboard",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["overdue_invoices"] == 1


def test_revenue_with_no_orders(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    response = client.get(
        "/api/v1/analytics/revenue",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_revenue_groups_orders_by_date(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    customer = create_test_customer(client, headers)
    product = create_test_product(
        client,
        headers,
        price="100.00",
    )

    first_order = create_test_order(
        client,
        headers,
        customer["id"],
        product["id"],
        order_number="REVENUE-ORDER-1",
        quantity=2,
    )

    second_order = create_test_order(
        client,
        headers,
        customer["id"],
        product["id"],
        order_number="REVENUE-ORDER-2",
        quantity=3,
    )

    assert first_order.status_code == 201
    assert second_order.status_code == 201

    response = client.get(
        "/api/v1/analytics/revenue",
        headers=headers,
    )

    assert response.status_code == 200

    revenue = response.json()

    assert len(revenue) == 1
    assert Decimal(str(revenue[0]["revenue"])) == Decimal("500.00")
    assert revenue[0]["date"] == date.today().isoformat()


def test_revenue_excludes_cancelled_orders(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    customer = create_test_customer(client, headers)
    product = create_test_product(client, headers)

    order = create_test_order(
        client,
        headers,
        customer["id"],
        product["id"],
    )

    assert order.status_code == 201

    cancel = client.post(
        f"/api/v1/sales-orders/{order.json()['id']}/cancel",
        headers=headers,
    )

    assert cancel.status_code == 200

    response = client.get(
        "/api/v1/analytics/revenue",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []



def test_top_customers_with_no_orders(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    create_test_customer(client, headers)

    response = client.get(
        "/api/v1/analytics/top-customers",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_top_customers_orders_by_total_spent(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    customer1 = create_test_customer(
        client,
        headers,
        name="Customer One",
        email="customer.one.analytics@example.com",
        company="Company One",
    )

    customer2 = create_test_customer(
        client,
        headers,
        name="Customer Two",
        email="customer.two.analytics@example.com",
        company="Company Two",
    )

    product = create_test_product(
        client,
        headers,
        price="100.00",
    )

    order1 = create_test_order(
        client,
        headers,
        customer1["id"],
        product["id"],
        order_number="TOP-CUSTOMER-ORDER-1",
        quantity=2,
    )

    order2 = create_test_order(
        client,
        headers,
        customer2["id"],
        product["id"],
        order_number="TOP-CUSTOMER-ORDER-2",
        quantity=5,
    )

    assert order1.status_code == 201
    assert order2.status_code == 201

    response = client.get(
        "/api/v1/analytics/top-customers",
        headers=headers,
    )

    assert response.status_code == 200

    customers = response.json()

    assert len(customers) == 2
    assert customers[0]["customer_id"] == customer2["id"]
    assert customers[0]["name"] == "Customer Two"
    assert customers[0]["company"] == "Company Two"
    assert Decimal(str(customers[0]["total_spent"])) == Decimal("500.00")

    assert customers[1]["customer_id"] == customer1["id"]
    assert Decimal(str(customers[1]["total_spent"])) == Decimal("200.00")


def test_top_customers_respects_limit(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    product = create_test_product(client, headers)

    for index in range(3):
        customer = create_test_customer(
            client,
            headers,
            name=f"Limit Customer {index}",
            email=f"limit{index}@analytics.example.com",
        )

        order = create_test_order(
            client,
            headers,
            customer["id"],
            product["id"],
            order_number=f"LIMIT-ORDER-{index}",
            quantity=index + 1,
        )

        assert order.status_code == 201

    response = client.get(
        "/api/v1/analytics/top-customers",
        params={"limit": 2},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_top_customers_excludes_cancelled_orders(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    customer = create_test_customer(client, headers)
    product = create_test_product(client, headers)

    order = create_test_order(
        client,
        headers,
        customer["id"],
        product["id"],
    )

    assert order.status_code == 201

    cancel = client.post(
        f"/api/v1/sales-orders/{order.json()['id']}/cancel",
        headers=headers,
    )

    assert cancel.status_code == 200

    response = client.get(
        "/api/v1/analytics/top-customers",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []



def test_low_stock_with_no_products(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    response = client.get(
        "/api/v1/analytics/low-stock",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_low_stock_returns_products_below_threshold(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    create_test_product(
        client,
        headers,
        sku="LOW-STOCK-001",
        stock=3,
    )

    create_test_product(
        client,
        headers,
        sku="LOW-STOCK-002",
        stock=8,
    )

    create_test_product(
        client,
        headers,
        sku="NORMAL-STOCK-001",
        stock=20,
    )

    response = client.get(
        "/api/v1/analytics/low-stock",
        params={"threshold": 10},
        headers=headers,
    )

    assert response.status_code == 200

    products = response.json()

    assert len(products) == 2
    assert products[0]["sku"] == "LOW-STOCK-001"
    assert products[0]["stock_quantity"] == 3
    assert products[1]["sku"] == "LOW-STOCK-002"
    assert products[1]["stock_quantity"] == 8


def test_low_stock_includes_product_at_threshold(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    create_test_product(
        client,
        headers,
        sku="EXACT-THRESHOLD-001",
        stock=10,
    )

    response = client.get(
        "/api/v1/analytics/low-stock",
        params={"threshold": 10},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["stock_quantity"] == 10



def test_overdue_invoices_with_no_invoices(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    response = client.get(
        "/api/v1/analytics/overdue-invoices",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_overdue_invoices_returns_outstanding_balances(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    customer = create_test_customer(client, headers)

    invoice = create_test_invoice(
        client,
        headers,
        customer["id"],
        amount="500.00",
        issue_date=date.today() - timedelta(days=30),
        due_date=date.today() - timedelta(days=10),
    )

    assert invoice.status_code == 201

    payment = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        json={"amount": "200.00"},
        headers=headers,
    )

    assert payment.status_code == 200

    response = client.get(
        "/api/v1/analytics/overdue-invoices",
        headers=headers,
    )

    assert response.status_code == 200

    invoices = response.json()

    assert len(invoices) == 1

    data = invoices[0]

    assert data["invoice_id"] == invoice.json()["id"]
    assert data["invoice_number"] == "ANALYTICS-INVOICE-001"
    assert Decimal(str(data["amount"])) == Decimal("500.00")
    assert Decimal(str(data["amount_paid"])) == Decimal("200.00")
    assert Decimal(str(data["outstanding_balance"])) == Decimal("300.00")


def test_overdue_invoices_excludes_fully_paid_invoices(client, db_session):
    headers = get_analytics_auth_headers(client, db_session)

    customer = create_test_customer(client, headers)

    invoice = create_test_invoice(
        client,
        headers,
        customer["id"],
        issue_date=date.today() - timedelta(days=30),
        due_date=date.today() - timedelta(days=10),
    )

    assert invoice.status_code == 201

    payment = client.post(
        f"/api/v1/invoices/{invoice.json()['id']}/payments",
        json={"amount": "500.00"},
        headers=headers,
    )

    assert payment.status_code == 200

    response = client.get(
        "/api/v1/analytics/overdue-invoices",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_analytics_endpoints_require_authentication(client):
    endpoints = [
        "/api/v1/analytics/dashboard",
        "/api/v1/analytics/revenue",
        "/api/v1/analytics/top-customers",
        "/api/v1/analytics/low-stock",
        "/api/v1/analytics/overdue-invoices",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)

        assert response.status_code == 401, (
            f"{endpoint} should require authentication"
        )


def test_employee_can_access_all_analytics_endpoints(client, db_session):
    headers = get_analytics_auth_headers(
        client,
        db_session,
        role="employee",
        email="analytics-employee@example.com",
    )

    endpoints = [
        "/api/v1/analytics/dashboard",
        "/api/v1/analytics/revenue",
        "/api/v1/analytics/top-customers",
        "/api/v1/analytics/low-stock",
        "/api/v1/analytics/overdue-invoices",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint, headers=headers)

        assert response.status_code == 200, (
            f"Employee should access {endpoint}"
        )
