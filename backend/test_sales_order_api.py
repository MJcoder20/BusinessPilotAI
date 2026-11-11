from decimal import Decimal

from app.models import User


def get_sales_auth_headers(
    client,
    db_session,
    role="employee",
    email="sales-test@example.com",
):
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Sales Test User",
            "email": email,
            "password": "SecurePassword123!",
        },
    )

    assert register_response.status_code == 201

    user = db_session.query(User).filter(
        User.email == email
    ).first()

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
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        )
    }


def create_test_customer(
    client,
    headers,
    email="sales.test@example.com",
):
    response = client.post(
        "/api/v1/customers/",
        headers=headers,
        json={
            "name": "Sales Test Customer",
            "email": email,
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def create_test_product(
    client,
    headers,
    sku="SALES-TEST-001",
    stock=20,
    price="100.00",
):
    response = client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": sku,
            "name": "Sales Test Product",
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
    order_number="SALES-ORDER-001",
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

def test_create_sales_order(client, db_session):
    manager_headers = get_sales_auth_headers(
        client,
        db_session,
        role="manager",
        email="sales-manager-create@example.com",
    )

    employee_headers = get_sales_auth_headers(
        client,
        db_session,
        role="employee",
        email="sales-employee-create@example.com",
    )

    customer = create_test_customer(
        client,
        manager_headers,
    )

    product = create_test_product(
        client,
        manager_headers,
        stock=20,
        price="250.00",
    )

    response = create_test_order(
        client,
        manager_headers,
        customer["id"],
        product["id"],
        quantity=3,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["order_number"] == "SALES-ORDER-001"
    assert data["status"] == "pending"
    assert Decimal(data["total_amount"]) == Decimal("750.00")
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 3
    assert Decimal(data["items"][0]["unit_price"]) == Decimal("250.00")

    updated_product = client.get(
        f"/api/v1/products/{product['id']}",
        headers=employee_headers,
    )

    assert updated_product.json()["stock_quantity"] == 17

def test_create_order_with_nonexistent_customer(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-missing-customer@example.com",
    )

    product = create_test_product(client, manager_headers)

    response = create_test_order(
        client,
        manager_headers,
        customer_id=999999,
        product_id=product["id"],
    )

    assert response.status_code == 404

def test_create_order_with_nonexistent_product(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-missing-product@example.com",
    )

    customer = create_test_customer(client, manager_headers)

    response = create_test_order(
        client,
        manager_headers,
        customer_id=customer["id"],
        product_id=999999,
    )

    assert response.status_code == 404

def test_create_order_with_insufficient_stock(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-stock@example.com",
    )

    employee_headers = get_sales_auth_headers(
        client, db_session,
        role="employee",
        email="sales-employee-stock@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(
        client, manager_headers, stock=2
    )

    response = create_test_order(
        client,
        manager_headers,
        customer["id"],
        product["id"],
        quantity=5,
    )

    assert response.status_code == 409

    updated_product = client.get(
        f"/api/v1/products/{product['id']}",
        headers=employee_headers,
    )

    assert updated_product.json()["stock_quantity"] == 2

    orders = client.get(
        "/api/v1/sales-orders/",
        headers=employee_headers,
    )

    assert orders.status_code == 200
    assert len(orders.json()) == 0


def test_duplicate_order_number(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-duplicate@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(client, manager_headers)

    first = create_test_order(
        client,
        manager_headers,
        customer["id"],
        product["id"],
        order_number="DUPLICATE-ORDER",
    )

    second = create_test_order(
        client,
        manager_headers,
        customer["id"],
        product["id"],
        order_number="DUPLICATE-ORDER",
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 409

def test_duplicate_product_ids_are_merged(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-merged@example.com",
    )

    employee_headers = get_sales_auth_headers(
        client, db_session,
        role="employee",
        email="sales-employee-merged@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(
        client,
        manager_headers,
        stock=20,
        price="50.00",
    )

    response = client.post(
        "/api/v1/sales-orders/",
        headers=manager_headers,
        json={
            "order_number": "MERGED-ORDER",
            "customer_id": customer["id"],
            "items": [
                {"product_id": product["id"], "quantity": 2},
                {"product_id": product["id"], "quantity": 3},
            ],
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 5
    assert Decimal(data["total_amount"]) == Decimal("250.00")

    updated_product = client.get(
        f"/api/v1/products/{product['id']}",
        headers=employee_headers,
    )

    assert updated_product.json()["stock_quantity"] == 15


def test_list_and_get_sales_orders(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-list@example.com",
    )

    employee_headers = get_sales_auth_headers(
        client, db_session,
        role="employee",
        email="sales-employee-list@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(client, manager_headers)

    created = create_test_order(
        client,
        manager_headers,
        customer["id"],
        product["id"],
    )

    assert created.status_code == 201, created.text
    order_id = created.json()["id"]

    list_response = client.get(
        "/api/v1/sales-orders/",
        headers=employee_headers,
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(
        f"/api/v1/sales-orders/{order_id}",
        headers=employee_headers,
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == order_id
    assert len(detail_response.json()["items"]) == 1


def test_get_nonexistent_sales_order(client, db_session):
    employee_headers = get_sales_auth_headers(
        client, db_session,
        role="employee",
        email="sales-employee-missing-order@example.com",
    )

    response = client.get(
        "/api/v1/sales-orders/999999",
        headers=employee_headers,
    )

    assert response.status_code == 404


def test_valid_order_status_transitions(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-transitions@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(client, manager_headers)

    order = create_test_order(
        client,
        manager_headers,
        customer["id"],
        product["id"],
    )

    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    for new_status in ["confirmed", "processing", "shipped", "delivered"]:
        response = client.patch(
            f"/api/v1/sales-orders/{order_id}/status",
            headers=manager_headers,
            json={"status": new_status},
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == new_status

def test_invalid_order_status_transition(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-invalid-transition@example.com",
    )

    employee_headers = get_sales_auth_headers(
        client, db_session,
        role="employee",
        email="sales-employee-invalid-transition@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(client, manager_headers)

    order = create_test_order(
        client,
        manager_headers,
        customer["id"],
        product["id"],
    )

    order_id = order.json()["id"]

    response = client.patch(
        f"/api/v1/sales-orders/{order_id}/status",
        headers=manager_headers,
        json={"status": "shipped"},
    )

    assert response.status_code == 409

    current_order = client.get(
        f"/api/v1/sales-orders/{order_id}",
        headers=employee_headers,
    )

    assert current_order.json()["status"] == "pending"


def test_cancel_order_restores_stock(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-cancel-stock@example.com",
    )

    employee_headers = get_sales_auth_headers(
        client, db_session,
        role="employee",
        email="sales-employee-cancel-stock@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(
        client, manager_headers,
        sku="SALES-CANCEL-001",
        stock=20,
    )

    order = create_test_order(
        client, manager_headers,
        customer["id"], product["id"],
        order_number="SALES-CANCEL-ORDER-001",
        quantity=5,
    )

    assert order.status_code == 201, order.text

    cancel_response = client.post(
        f"/api/v1/sales-orders/{order.json()['id']}/cancel",
        headers=manager_headers,
    )

    assert cancel_response.status_code == 200, cancel_response.text

    updated_product = client.get(
        f"/api/v1/products/{product['id']}",
        headers=employee_headers,
    )

    assert updated_product.json()["stock_quantity"] == 20

def test_cannot_cancel_already_cancelled_order(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-cancel-twice@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(client, manager_headers)

    order = create_test_order(
        client, manager_headers,
        customer["id"], product["id"],
    )

    order_id = order.json()["id"]

    first_response = client.post(
        f"/api/v1/sales-orders/{order_id}/cancel",
        headers=manager_headers,
    )
    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/v1/sales-orders/{order_id}/cancel",
        headers=manager_headers,
    )
    assert second_response.status_code == 409


def test_cannot_cancel_shipped_order(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-cancel-shipped@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(client, manager_headers)

    order = create_test_order(
        client, manager_headers,
        customer["id"], product["id"],
    )

    order_id = order.json()["id"]

    for new_status in ["confirmed", "processing", "shipped"]:
        response = client.patch(
            f"/api/v1/sales-orders/{order_id}/status",
            headers=manager_headers,
            json={"status": new_status},
        )
        assert response.status_code == 200, response.text

    cancel_response = client.post(
        f"/api/v1/sales-orders/{order_id}/cancel",
        headers=manager_headers,
    )

    assert cancel_response.status_code == 409


def test_employee_cannot_create_sales_order(client, db_session):
    employee_headers = get_sales_auth_headers(
        client, db_session,
        role="employee",
        email="sales-employee-no-create@example.com",
    )

    response = client.post(
        "/api/v1/sales-orders/",
        headers=employee_headers,
        json={
            "order_number": "EMPLOYEE-FORBIDDEN-001",
            "customer_id": 1,
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )

    assert response.status_code == 403

def test_employee_cannot_update_order_status(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-no-employee-status@example.com",
    )
    employee_headers = get_sales_auth_headers(
        client, db_session,
        role="employee",
        email="sales-employee-no-status@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(client, manager_headers)
    order = create_test_order(
        client, manager_headers,
        customer["id"], product["id"],
    )

    response = client.patch(
        f"/api/v1/sales-orders/{order.json()['id']}/status",
        headers=employee_headers,
        json={"status": "confirmed"},
    )

    assert response.status_code == 403

def test_employee_cannot_cancel_sales_order(client, db_session):
    manager_headers = get_sales_auth_headers(
        client, db_session,
        role="manager",
        email="sales-manager-no-employee-cancel@example.com",
    )
    employee_headers = get_sales_auth_headers(
        client, db_session,
        role="employee",
        email="sales-employee-no-cancel@example.com",
    )

    customer = create_test_customer(client, manager_headers)
    product = create_test_product(client, manager_headers)
    order = create_test_order(
        client, manager_headers,
        customer["id"], product["id"],
    )

    response = client.post(
        f"/api/v1/sales-orders/{order.json()['id']}/cancel",
        headers=employee_headers,
    )

    assert response.status_code == 403
