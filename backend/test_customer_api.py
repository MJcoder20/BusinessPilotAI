
from decimal import Decimal

from app.models import User

def get_auth_headers(
    client,
    db_session,
    role="employee",
    email="customer-test@example.com",
):
    # Register a test account.
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Customer Test User",
            "email": email,
            "password": "SecurePassword123!",
        },
    )

    assert register_response.status_code == 201

    # Assign the role directly in the isolated test database.
    user = db_session.query(User).filter(
        User.email == email
    ).first()

    assert user is not None

    user.role = role
    db_session.flush()

    # Log in and obtain an access token.
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SecurePassword123!",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    return {
        "Authorization": f"Bearer {access_token}"
    }

def test_create_customer(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="manager"
    )

    response = client.post(
        "/api/v1/customers/",
        headers=headers,
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


def test_create_customer_duplicate_email(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="manager"
    )

    payload = {
        "name": "First Customer",
        "email": "duplicate@example.com",
    }

    first_response = client.post("/api/v1/customers/", headers=headers, json=payload)
    second_response = client.post(
        "/api/v1/customers/",
        headers=headers,
        json={**payload, "name": "Second Customer"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_list_and_search_customers(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="manager"
    )

    client.post(
        "/api/v1/customers/",
        headers=headers,
        json={
            "name": "Alpha Technologies",
            "email": "alpha@example.com",
            "industry": "Technology",
        },
    )

    client.post(
        "/api/v1/customers/",
        headers=headers,
        json={
            "name": "Beta Industries",
            "email": "beta@example.com",
            "industry": "Manufacturing",
        },
    )

    response = client.get("/api/v1/customers/?search=Alpha", headers=headers)

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["name"] == "Alpha Technologies"


def test_get_nonexistent_customer(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="employee"
    )

    response = client.get("/api/v1/customers/999999", headers=headers)

    assert response.status_code == 404


def test_update_customer(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="manager"
    )

    create_response = client.post(
        "/api/v1/customers/",
        headers=headers,
        json={
            "name": "Original Name",
            "email": "update@example.com",
        },
    )

    customer_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/v1/customers/{customer_id}",
        headers=headers,
        json={
            "name": "Updated Name",
            "email": "update@example.com",
            "company": "Updated Company",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Name"
    assert update_response.json()["company"] == "Updated Company"


def test_delete_customer(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="admin"
    )

    create_response = client.post(
        "/api/v1/customers/",
        headers=headers,
        json={
            "name": "Customer To Delete",
            "email": "delete@example.com",
        },
    )

    customer_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/customers/{customer_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/v1/customers/{customer_id}",
        headers=headers,
    )

    assert get_response.status_code == 404


def test_invalid_customer_pagination(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="employee"
    )

    response = client.get("/api/v1/customers/?page=0", headers=headers)

    assert response.status_code == 400

    response = client.get("/api/v1/customers/?page_size=101", headers=headers)

    assert response.status_code == 400

def test_employee_cannot_create_customer(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="employee",
        email="employee-create@example.com",
    )

    response = client.post(
        "/api/v1/customers/",
        headers=headers,
        json={
            "name": "Unauthorized Customer",
            "email": "unauthorized@example.com",
        },
    )

    assert response.status_code == 403


def test_employee_cannot_update_customer(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="employee",
        email="employee-update@example.com",
    )

    response = client.put(
        "/api/v1/customers/1",
        headers=headers,
        json={
            "name": "Unauthorized Update",
            "email": "unauthorized-update@example.com",
        },
    )

    assert response.status_code == 403


def test_employee_cannot_delete_customer(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="employee",
        email="employee-delete@example.com",
    )

    response = client.delete(
        "/api/v1/customers/1",
        headers=headers,
    )

    assert response.status_code == 403


def test_manager_cannot_delete_customer(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="manager",
        email="manager-delete@example.com",
    )

    response = client.delete(
        "/api/v1/customers/1",
        headers=headers,
    )

    assert response.status_code == 403


def test_admin_can_delete_customer(client, db_session):
    headers = get_auth_headers(
        client, db_session, role="admin",
        email="admin-delete@example.com",
    )

    create_response = client.post(
        "/api/v1/customers/",
        headers=headers,
        json={
            "name": "Admin Test Customer",
            "email": "admin-customer@example.com",
        },
    )

    assert create_response.status_code == 201

    customer_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/customers/{customer_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204