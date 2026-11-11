from decimal import Decimal

from app.models import User


def get_product_auth_headers(
    client,
    db_session,
    role="employee",
    email="product-test@example.com",
):
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Product Test User",
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

def test_create_product(client, db_session):
    headers = get_product_auth_headers(
        client, db_session, role="manager"
    )
    response = client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": "TEST-001",
            "name": "Test Laptop",
            "description": "A test laptop",
            "unit_price": "1200.00",
            "stock_quantity": 15,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["sku"] == "TEST-001"
    assert data["name"] == "Test Laptop"
    assert Decimal(data["unit_price"]) == Decimal("1200.00")
    assert data["stock_quantity"] == 15


def test_create_product_duplicate_sku(client, db_session):
    headers = get_product_auth_headers(
        client, db_session, role="manager"
    )
    payload = {
        "sku": "DUP-001",
        "name": "First Product",
        "unit_price": "100.00",
        "stock_quantity": 10,
    }

    first = client.post("/api/v1/products/", headers=headers, json=payload)
    second = client.post(
        "/api/v1/products/",
        headers=headers,
        json={**payload, "name": "Second Product"},
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_list_products(client, db_session):
    headers = get_product_auth_headers(
        client, db_session, role="manager"
    )
    client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": "LIST-001",
            "name": "Product One",
            "unit_price": "50.00",
            "stock_quantity": 5,
        },
    )

    client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": "LIST-002",
            "name": "Product Two",
            "unit_price": "75.00",
            "stock_quantity": 8,
        },
    )

    response = client.get("/api/v1/products/", headers=headers)

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["sku"] == "LIST-002"


def test_get_product(client, db_session):
    manager_headers = get_product_auth_headers(
        client, db_session, role="manager", email="product-manager-get@example.com",
    )
    employee_headers = get_product_auth_headers(
        client, db_session, role="employee", email="product-employee-get@example.com",
    )
    create_response = client.post(
        "/api/v1/products/",
        headers=manager_headers,
        json={
            "sku": "GET-001",
            "name": "Product To Retrieve",
            "unit_price": "200.00",
            "stock_quantity": 20,
        },
    )
    assert create_response.status_code == 201, create_response.text

    product_id = create_response.json()["id"]

    response = client.get(f"/api/v1/products/{product_id}",headers=employee_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Product To Retrieve"


def test_get_nonexistent_product(client, db_session):
    headers = get_product_auth_headers(
        client, db_session, role="employee"
    )
    response = client.get("/api/v1/products/999999", headers=headers)

    assert response.status_code == 404


def test_update_product(client, db_session):
    headers = get_product_auth_headers(
        client, db_session, role="manager"
    )
    create_response = client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": "UPDATE-001",
            "name": "Original Product",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    product_id = create_response.json()["id"]

    response = client.put(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={
            "sku": "UPDATE-001",
            "name": "Updated Product",
            "description": "Updated description",
            "unit_price": "150.00",
            "stock_quantity": 25,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Updated Product"
    assert Decimal(data["unit_price"]) == Decimal("150.00")
    assert data["stock_quantity"] == 25


def test_update_product_with_duplicate_sku(client, db_session):
    headers = get_product_auth_headers(
        client, db_session, role="manager"
    )
    first = client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": "SKU-001",
            "name": "First Product",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    second = client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": "SKU-002",
            "name": "Second Product",
            "unit_price": "200.00",
            "stock_quantity": 20,
        },
    )

    second_id = second.json()["id"]

    response = client.put(
        f"/api/v1/products/{second_id}",
        headers=headers,
        json={
            "sku": "SKU-001",
            "name": "Updated Second Product",
            "unit_price": "200.00",
            "stock_quantity": 20,
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert response.status_code == 409


def test_update_nonexistent_product(client, db_session):
    headers = get_product_auth_headers(
        client, db_session, role="manager"
    )
    response = client.put(
        "/api/v1/products/999999",
        headers=headers,
        json={
            "sku": "MISSING-001",
            "name": "Missing Product",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    assert response.status_code == 404


def test_delete_product(client, db_session):
    headers = get_product_auth_headers(
        client, db_session, role="admin"
    )
    create_response = client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": "DELETE-001",
            "name": "Product To Delete",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    product_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/products/{product_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/v1/products/{product_id}",
        headers=headers,
    )

    assert get_response.status_code == 404


def test_delete_nonexistent_product(client, db_session):
    headers = get_product_auth_headers(
        client, db_session, role="admin"
    )
    response = client.delete("/api/v1/products/999999", headers=headers)

    assert response.status_code == 404


def test_product_validation(client, db_session):
    headers = get_product_auth_headers(
        client, db_session, role="manager"
    )
    response = client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": "A",
            "name": "X",
            "unit_price": "-10.00",
            "stock_quantity": -5,
        },
    )

    assert response.status_code == 422



def test_cannot_delete_product_used_in_sales_order(client, db_session):
    manager_headers = get_product_auth_headers(
        client, db_session, role="manager", email="product-order-manager@example.com",
    )
    admin_headers = get_product_auth_headers(
        client, db_session, role="admin", email="product-order-admin@example.com",
    )
    employee_headers = get_product_auth_headers(
        client, db_session, role="employee", email="product-order-employee@example.com",
    )
    # 1. Create a customer.
    customer_response = client.post(
        "/api/v1/customers/",
        headers=manager_headers,
        json={
            "name": "Order Test Customer",
            "email": "order.test@example.com",
        },
    )

    assert customer_response.status_code == 201, customer_response.text
    customer_id = customer_response.json()["id"]

    # 2. Create a product.
    product_response = client.post(
        "/api/v1/products/",
        headers=manager_headers,
        json={
            "sku": "ORDER-TEST-001",
            "name": "Order Test Laptop",
            "unit_price": "1000.00",
            "stock_quantity": 20,
        },
    )

    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]

    # 3. Create a sales order for 3 units.
    order_response = client.post(
        "/api/v1/sales-orders/",
        headers=manager_headers,
        json={
            "order_number": "TEST-ORDER-001",
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 3,
                }
            ],
        },
    )

    assert order_response.status_code == 201, order_response.text

    # 4. Verify stock was deducted.
    product_after_order = client.get(
        f"/api/v1/products/{product_id}",
        headers=employee_headers,
    )

    assert product_after_order.status_code == 200
    assert product_after_order.json()["stock_quantity"] == 17

    # 5. Attempt to delete the referenced product.
    delete_response = client.delete(
        f"/api/v1/products/{product_id}",
        headers=admin_headers,
    )

    assert delete_response.status_code == 409

    # 6. Verify the product still exists.
    final_response = client.get(
        f"/api/v1/products/{product_id}",
        headers=employee_headers,
    )

    assert final_response.status_code == 200
    assert final_response.json()["stock_quantity"] == 17


def test_employee_cannot_create_product(client, db_session):
    headers = get_product_auth_headers(
        client, db_session,
        role="employee",
        email="product-employee-create@example.com",
    )

    response = client.post(
        "/api/v1/products/",
        headers=headers,
        json={
            "sku": "AUTH-001",
            "name": "Unauthorized Product",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    assert response.status_code == 403


def test_employee_cannot_update_product(client, db_session):
    manager_headers = get_product_auth_headers(
        client, db_session,
        role="manager",
        email="product-manager-update@example.com",
    )
    employee_headers = get_product_auth_headers(
        client, db_session,
        role="employee",
        email="product-employee-update@example.com",
    )

    created = client.post(
        "/api/v1/products/",
        headers=manager_headers,
        json={
            "sku": "AUTH-002",
            "name": "Original Product",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    product_id = created.json()["id"]

    response = client.put(
        f"/api/v1/products/{product_id}",
        headers=employee_headers,
        json={
            "sku": "AUTH-002",
            "name": "Modified Product",
            "unit_price": "150.00",
            "stock_quantity": 20,
        },
    )

    assert response.status_code == 403


def test_employee_cannot_delete_product(client, db_session):
    manager_headers = get_product_auth_headers(
        client, db_session,
        role="manager",
        email="product-manager-delete@example.com",
    )
    employee_headers = get_product_auth_headers(
        client, db_session,
        role="employee",
        email="product-employee-delete@example.com",
    )

    created = client.post(
        "/api/v1/products/",
        headers=manager_headers,
        json={
            "sku": "AUTH-003",
            "name": "Protected Product",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    product_id = created.json()["id"]

    response = client.delete(
        f"/api/v1/products/{product_id}",
        headers=employee_headers,
    )

    assert response.status_code == 403


def test_manager_cannot_delete_product(client, db_session):
    manager_headers = get_product_auth_headers(
        client, db_session,
        role="manager",
        email="product-manager-restricted@example.com",
    )

    created = client.post(
        "/api/v1/products/",
        headers=manager_headers,
        json={
            "sku": "AUTH-004",
            "name": "Admin Only Product",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    product_id = created.json()["id"]

    response = client.delete(
        f"/api/v1/products/{product_id}",
        headers=manager_headers,
    )

    assert response.status_code == 403


def test_admin_can_delete_product(client, db_session):
    admin_headers = get_product_auth_headers(
        client, db_session,
        role="admin",
        email="product-admin-delete@example.com",
    )

    created = client.post(
        "/api/v1/products/",
        headers=admin_headers,
        json={
            "sku": "AUTH-005",
            "name": "Admin Deletable Product",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    assert created.status_code == 201

    product_id = created.json()["id"]

    response = client.delete(
        f"/api/v1/products/{product_id}",
        headers=admin_headers,
    )

    assert response.status_code == 204