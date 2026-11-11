from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import verify_password
from app.models import RefreshToken, User
from app.services.refresh_tokens import hash_refresh_token

def test_register_creates_employee_account(client, db_session):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Employee",
            "email": "employee@example.com",
            "password": "SecurePassword123!",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["full_name"] == "Test Employee"
    assert data["email"] == "employee@example.com"
    assert data["role"] == "employee"
    assert data["is_active"] is True
    assert "password" not in data
    assert "password_hash" not in data

    user = db_session.query(User).filter_by(
        email="employee@example.com"
    ).first()

    assert user is not None
    assert verify_password("SecurePassword123!", user.password_hash)


def test_register_rejects_duplicate_email(client):
    payload = {
        "full_name": "Test Employee",
        "email": "duplicate@example.com",
        "password": "SecurePassword123!",
    }

    first_response = client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    second_response = client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_register_does_not_allow_role_escalation(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Admin",
            "email": "notadmin@example.com",
            "password": "SecurePassword123!",
            "role": "admin",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "employee"


def test_login_returns_access_token_and_current_user(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Login Test",
            "email": "login@example.com",
            "password": "SecurePassword123!",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "SecurePassword123!",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["expires_in"] == 900
    assert data["user"]["email"] == "login@example.com"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {data['access_token']}"
        },
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "login@example.com"


def test_login_rejects_incorrect_password(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Login Test",
            "email": "wrong-password@example.com",
            "password": "SecurePassword123!",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrong-password@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer invalid-token"},
    ],
)
def test_current_user_rejects_invalid_credentials(client, headers):
    response = client.get(
        "/api/v1/auth/me",
        headers=headers,
    )

    assert response.status_code == 401

def test_register_rate_limit_returns_429(client):
    responses = [
        client.post(
            "/api/v1/auth/register",
            json={
                "full_name": f"Rate Test {i}",
                "email": f"rate-test-{i}@example.com",
                "password": "SecurePassword123!",
            },
        )
        for i in range(4)
    ]

    assert all(
        response.status_code == 201
        for response in responses[:3]
    )

    assert responses[3].status_code == 429


def create_test_user_and_login(client, email="refresh@example.com"):
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Refresh Test",
            "email": email,
            "password": "SecurePassword123!",
        },
    )

    return client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SecurePassword123!",
        },
    )


def test_login_sets_secure_refresh_cookie(client):
    response = create_test_user_and_login(client)

    assert response.status_code == 200

    cookie = response.headers["set-cookie"].lower()

    assert "businesspilot_refresh_token=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/api/v1/auth" in cookie


def test_refresh_rotates_token_and_rejects_replay(client):
    login_response = create_test_user_and_login(client)
    assert login_response.status_code == 200

    old_token = client.cookies.get("businesspilot_refresh_token")
    assert old_token

    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]

    new_token = client.cookies.get("businesspilot_refresh_token")

    assert new_token
    assert new_token != old_token

    replay_response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://localhost:5173"},
        cookies={"businesspilot_refresh_token": old_token},
    )

    assert replay_response.status_code == 401


def test_refresh_rejects_expired_token(client, db_session):
    login_response = create_test_user_and_login(client)
    assert login_response.status_code == 200

    raw_token = client.cookies.get("businesspilot_refresh_token")
    assert raw_token

    token_record = db_session.query(RefreshToken).filter_by(
        token_hash=hash_refresh_token(raw_token)
    ).first()

    assert token_record is not None

    token_record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 401

    cookie = response.headers["set-cookie"].lower()

    assert "businesspilot_refresh_token=" in cookie
    assert "max-age=0" in cookie
    assert "httponly" in cookie
    assert "path=/api/v1/auth" in cookie


def test_logout_revokes_refresh_token(client, db_session):
    login_response = create_test_user_and_login(client)
    assert login_response.status_code == 200

    raw_token = client.cookies.get("businesspilot_refresh_token")
    assert raw_token

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 204

    token_record = db_session.query(RefreshToken).filter_by(
        token_hash=hash_refresh_token(raw_token)
    ).first()

    assert token_record is not None
    assert token_record.revoked_at is not None

    cookie = response.headers["set-cookie"].lower()
    assert "max-age=0" in cookie


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
    ],
)
def test_cookie_endpoints_reject_untrusted_origin(client, endpoint):
    response = client.post(
        endpoint,
        headers={"Origin": "https://malicious.example"},
    )

    assert response.status_code == 403