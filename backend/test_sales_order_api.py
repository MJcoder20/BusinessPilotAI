
from decimal import Decimal


def create_test_customer(client, email="sales.test@example.com"):
    response = client.post(
        "/api/v1/customers/",
        json={
            "name": "Sales Test Customer",
            "email": email,
        },
    )

    assert response.status_code == 201
    return response.json()


def create_test_product(
    client,
    sku="SALES-TEST-001",
    stock=20,
    price="100.00",
):
    response = client.post(
        "/api/v1/products/",
        json={
            "sku": sku,
            "name": "Sales Test Product",
            "unit_price": price,
            "stock_quantity": stock,
        },
    )

    assert response.status_code == 201
    return response.json()


def create_test_order(
    client,
    customer_id,
    product_id,
    order_number="SALES-ORDER-001",
    quantity=2,
):
    return client.post(
        "/api/v1/sales-orders/",
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


def test_create_sales_order(client):
    customer = create_test_customer(client)
    product = create_test_product(client, stock=20, price="250.00")

    response = create_test_order(
        client,
        customer["id"],
        product["id"],
        quantity=3,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["order_number"] == "SALES-ORDER-001"
    assert data["status"] == "pending"
    assert Decimal(data["total_amount"]) == Decimal("750.00")
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 3
    assert Decimal(data["items"][0]["unit_price"]) == Decimal("250.00")

    updated_product = client.get(
        f"/api/v1/products/{product['id']}"
    )

    assert updated_product.json()["stock_quantity"] == 17


def test_create_order_with_nonexistent_customer(client):
    product = create_test_product(client)

    response = create_test_order(
        client,
        customer_id=999999,
        product_id=product["id"],
    )

    assert response.status_code == 404


def test_create_order_with_nonexistent_product(client):
    customer = create_test_customer(client)

    response = create_test_order(
        client,
        customer_id=customer["id"],
        product_id=999999,
    )

    assert response.status_code == 404


def test_create_order_with_insufficient_stock(client):
    customer = create_test_customer(client)
    product = create_test_product(client, stock=2)

    response = create_test_order(
        client,
        customer["id"],
        product["id"],
        quantity=5,
    )

    assert response.status_code == 409

    updated_product = client.get(
        f"/api/v1/products/{product['id']}"
    )

    assert updated_product.json()["stock_quantity"] == 2

    orders = client.get("/api/v1/sales-orders/")

    assert orders.status_code == 200
    assert len(orders.json()) == 0


def test_duplicate_order_number(client):
    customer = create_test_customer(client)
    product = create_test_product(client)

    first = create_test_order(
        client,
        customer["id"],
        product["id"],
        order_number="DUPLICATE-ORDER",
    )

    second = create_test_order(
        client,
        customer["id"],
        product["id"],
        order_number="DUPLICATE-ORDER",
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_duplicate_product_ids_are_merged(client):
    customer = create_test_customer(client)
    product = create_test_product(client, stock=20, price="50.00")

    response = client.post(
        "/api/v1/sales-orders/",
        json={
            "order_number": "MERGED-ORDER",
            "customer_id": customer["id"],
            "items": [
                {"product_id": product["id"], "quantity": 2},
                {"product_id": product["id"], "quantity": 3},
            ],
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 5
    assert Decimal(data["total_amount"]) == Decimal("250.00")

    updated_product = client.get(
        f"/api/v1/products/{product['id']}"
    )

    assert updated_product.json()["stock_quantity"] == 15


def test_list_and_get_sales_orders(client):
    customer = create_test_customer(client)
    product = create_test_product(client)

    created = create_test_order(
        client,
        customer["id"],
        product["id"],
    )

    order_id = created.json()["id"]

    list_response = client.get("/api/v1/sales-orders/")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(
        f"/api/v1/sales-orders/{order_id}"
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == order_id
    assert len(detail_response.json()["items"]) == 1


def test_get_nonexistent_sales_order(client):
    response = client.get("/api/v1/sales-orders/999999")

    assert response.status_code == 404


def test_valid_order_status_transitions(client):
    customer = create_test_customer(client)
    product = create_test_product(client)

    order = create_test_order(
        client,
        customer["id"],
        product["id"],
    )

    order_id = order.json()["id"]

    for new_status in ["confirmed", "processing", "shipped", "delivered"]:
        response = client.patch(
            f"/api/v1/sales-orders/{order_id}/status",
            json={"status": new_status},
        )

        assert response.status_code == 200
        assert response.json()["status"] == new_status


def test_invalid_order_status_transition(client):
    customer = create_test_customer(client)
    product = create_test_product(client)

    order = create_test_order(
        client,
        customer["id"],
        product["id"],
    )

    order_id = order.json()["id"]

    response = client.patch(
        f"/api/v1/sales-orders/{order_id}/status",
        json={"status": "shipped"},
    )

    assert response.status_code == 409

    current_order = client.get(
        f"/api/v1/sales-orders/{order_id}"
    )

    assert current_order.json()["status"] == "pending"


def test_cancel_order_restores_stock(client):
    customer = create_test_customer(client)
    product = create_test_product(client, stock=20)

    order = create_test_order(
        client,
        customer["id"],
        product["id"],
        quantity=4,
    )

    order_id = order.json()["id"]

    product_after_order = client.get(
        f"/api/v1/products/{product['id']}"
    )

    assert product_after_order.json()["stock_quantity"] == 16

    response = client.post(
        f"/api/v1/sales-orders/{order_id}/cancel"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    product_after_cancel = client.get(
        f"/api/v1/products/{product['id']}"
    )

    assert product_after_cancel.json()["stock_quantity"] == 20


def test_cannot_cancel_already_cancelled_order(client):
    customer = create_test_customer(client)
    product = create_test_product(client)

    order = create_test_order(
        client,
        customer["id"],
        product["id"],
    )

    order_id = order.json()["id"]

    first_cancel = client.post(
        f"/api/v1/sales-orders/{order_id}/cancel"
    )

    second_cancel = client.post(
        f"/api/v1/sales-orders/{order_id}/cancel"
    )

    assert first_cancel.status_code == 200
    assert second_cancel.status_code == 409


def test_cannot_cancel_shipped_order(client):
    customer = create_test_customer(client)
    product = create_test_product(client)

    order = create_test_order(
        client,
        customer["id"],
        product["id"],
    )

    order_id = order.json()["id"]

    for new_status in ["confirmed", "processing", "shipped"]:
        response = client.patch(
            f"/api/v1/sales-orders/{order_id}/status",
            json={"status": new_status},
        )

        assert response.status_code == 200

    cancel_response = client.post(
        f"/api/v1/sales-orders/{order_id}/cancel"
    )

    assert cancel_response.status_code == 409

    updated_product = client.get(
        f"/api/v1/products/{product['id']}"
    )

    assert updated_product.json()["stock_quantity"] == 18
