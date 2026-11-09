
from decimal import Decimal


def test_create_product(client):
    response = client.post(
        "/api/v1/products/",
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


def test_create_product_duplicate_sku(client):
    payload = {
        "sku": "DUP-001",
        "name": "First Product",
        "unit_price": "100.00",
        "stock_quantity": 10,
    }

    first = client.post("/api/v1/products/", json=payload)
    second = client.post(
        "/api/v1/products/",
        json={**payload, "name": "Second Product"},
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_list_products(client):
    client.post(
        "/api/v1/products/",
        json={
            "sku": "LIST-001",
            "name": "Product One",
            "unit_price": "50.00",
            "stock_quantity": 5,
        },
    )

    client.post(
        "/api/v1/products/",
        json={
            "sku": "LIST-002",
            "name": "Product Two",
            "unit_price": "75.00",
            "stock_quantity": 8,
        },
    )

    response = client.get("/api/v1/products/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["sku"] == "LIST-002"


def test_get_product(client):
    create_response = client.post(
        "/api/v1/products/",
        json={
            "sku": "GET-001",
            "name": "Product To Retrieve",
            "unit_price": "200.00",
            "stock_quantity": 20,
        },
    )

    product_id = create_response.json()["id"]

    response = client.get(f"/api/v1/products/{product_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Product To Retrieve"


def test_get_nonexistent_product(client):
    response = client.get("/api/v1/products/999999")

    assert response.status_code == 404


def test_update_product(client):
    create_response = client.post(
        "/api/v1/products/",
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


def test_update_product_with_duplicate_sku(client):
    first = client.post(
        "/api/v1/products/",
        json={
            "sku": "SKU-001",
            "name": "First Product",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    second = client.post(
        "/api/v1/products/",
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


def test_update_nonexistent_product(client):
    response = client.put(
        "/api/v1/products/999999",
        json={
            "sku": "MISSING-001",
            "name": "Missing Product",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    assert response.status_code == 404


def test_delete_product(client):
    create_response = client.post(
        "/api/v1/products/",
        json={
            "sku": "DELETE-001",
            "name": "Product To Delete",
            "unit_price": "100.00",
            "stock_quantity": 10,
        },
    )

    product_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/products/{product_id}"
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/v1/products/{product_id}"
    )

    assert get_response.status_code == 404


def test_delete_nonexistent_product(client):
    response = client.delete("/api/v1/products/999999")

    assert response.status_code == 404


def test_product_validation(client):
    response = client.post(
        "/api/v1/products/",
        json={
            "sku": "A",
            "name": "X",
            "unit_price": "-10.00",
            "stock_quantity": -5,
        },
    )

    assert response.status_code == 422



def test_cannot_delete_product_used_in_sales_order(client):
    # 1. Create a customer.
    customer_response = client.post(
        "/api/v1/customers/",
        json={
            "name": "Order Test Customer",
            "email": "order.test@example.com",
        },
    )

    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    # 2. Create a product.
    product_response = client.post(
        "/api/v1/products/",
        json={
            "sku": "ORDER-TEST-001",
            "name": "Order Test Laptop",
            "unit_price": "1000.00",
            "stock_quantity": 20,
        },
    )

    assert product_response.status_code == 201
    product_id = product_response.json()["id"]

    # 3. Create a sales order for 3 units.
    order_response = client.post(
        "/api/v1/sales-orders/",
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

    assert order_response.status_code == 201
    assert order_response.json()["total_amount"] == "3000.00"

    # 4. Verify stock was deducted.
    product_after_order = client.get(
        f"/api/v1/products/{product_id}"
    )

    assert product_after_order.status_code == 200
    assert product_after_order.json()["stock_quantity"] == 17

    # 5. Attempt to delete the referenced product.
    delete_response = client.delete(
        f"/api/v1/products/{product_id}"
    )

    assert delete_response.status_code == 409

    # 6. Verify the product still exists.
    final_response = client.get(
        f"/api/v1/products/{product_id}"
    )

    assert final_response.status_code == 200
    assert final_response.json()["stock_quantity"] == 17
