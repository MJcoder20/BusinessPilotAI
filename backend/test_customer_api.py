
from decimal import Decimal


def test_create_customer(client):
    response = client.post(
        "/api/v1/customers/",
        json={
            "name": "Test Customer",
            "email": "test.customer@example.com",
            "company": "Test Company",
            "industry": "Technology",
            "country": "Palestine",
            "credit_limit": "5000.00",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Test Customer"
    assert data["email"] == "test.customer@example.com"
    assert data["company"] == "Test Company"
    assert Decimal(data["credit_limit"]) == Decimal("5000.00")
    assert "id" in data


def test_create_customer_duplicate_email(client):
    payload = {
        "name": "First Customer",
        "email": "duplicate@example.com",
    }

    first_response = client.post("/api/v1/customers/", json=payload)
    second_response = client.post(
        "/api/v1/customers/",
        json={**payload, "name": "Second Customer"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_list_and_search_customers(client):
    client.post(
        "/api/v1/customers/",
        json={
            "name": "Alpha Technologies",
            "email": "alpha@example.com",
            "industry": "Technology",
        },
    )

    client.post(
        "/api/v1/customers/",
        json={
            "name": "Beta Industries",
            "email": "beta@example.com",
            "industry": "Manufacturing",
        },
    )

    response = client.get("/api/v1/customers/?search=Alpha")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["name"] == "Alpha Technologies"


def test_get_nonexistent_customer(client):
    response = client.get("/api/v1/customers/999999")

    assert response.status_code == 404


def test_update_customer(client):
    create_response = client.post(
        "/api/v1/customers/",
        json={
            "name": "Original Name",
            "email": "update@example.com",
        },
    )

    customer_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/v1/customers/{customer_id}",
        json={
            "name": "Updated Name",
            "email": "update@example.com",
            "company": "Updated Company",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Name"
    assert update_response.json()["company"] == "Updated Company"


def test_delete_customer(client):
    create_response = client.post(
        "/api/v1/customers/",
        json={
            "name": "Customer To Delete",
            "email": "delete@example.com",
        },
    )

    customer_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/customers/{customer_id}"
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/v1/customers/{customer_id}"
    )

    assert get_response.status_code == 404


def test_invalid_customer_pagination(client):
    response = client.get("/api/v1/customers/?page=0")

    assert response.status_code == 400

    response = client.get("/api/v1/customers/?page_size=101")

    assert response.status_code == 400
