from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.models import User
from app.services import supabase_auth


@pytest.fixture
def supabase_identity(monkeypatch):
    supabase_id = str(uuid4())
    email = "link-test@example.com"

    class MockResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": supabase_id,
                "email": email,
                "email_confirmed_at": datetime.now(timezone.utc).isoformat(),
                "user_metadata": {"full_name": "Link Test"},
            }

    monkeypatch.setattr(
        supabase_auth.httpx,
        "get",
        lambda *args, **kwargs: MockResponse(),
    )

    return {
        "id": supabase_id,
        "email": email,
        "claims": {
            "sub": supabase_id,
            "email": email,
        },
    }


@pytest.fixture
def unverified_local_user(db_session, supabase_identity):
    user = User(
        full_name="Link Test",
        email=supabase_identity["email"],
        password_hash=hash_password("OriginalPassword123!"),
        role="employee",
        is_active=True,
        is_verified=False,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def test_link_supabase_user_success(
    db_session,
    supabase_identity,
    unverified_local_user,
):
    original_id = unverified_local_user.id
    original_password_hash = unverified_local_user.password_hash

    linked_user = supabase_auth.link_supabase_user(
        db=db_session,
        access_token="mock-access-token",
        claims=supabase_identity["claims"],
        password="OriginalPassword123!",
    )

    assert linked_user.id == original_id
    assert linked_user.supabase_user_id == supabase_identity["id"]
    assert linked_user.email == supabase_identity["email"]
    assert linked_user.role == "employee"
    assert linked_user.is_active is True
    assert linked_user.is_verified is True
    assert linked_user.password_hash == original_password_hash


def test_link_supabase_user_rejects_wrong_password(
    db_session,
    supabase_identity,
    unverified_local_user,
):
    original_supabase_id = unverified_local_user.supabase_user_id

    with pytest.raises(
        ValueError,
        match="existing account password is incorrect",
    ):
        supabase_auth.link_supabase_user(
            db=db_session,
            access_token="mock-access-token",
            claims=supabase_identity["claims"],
            password="WrongPassword123!",
        )

    db_session.refresh(unverified_local_user)

    assert unverified_local_user.supabase_user_id == original_supabase_id
    assert unverified_local_user.is_verified is False


def test_link_supabase_user_rejects_already_verified_account(
    db_session,
    supabase_identity,
    unverified_local_user,
):
    unverified_local_user.is_verified = True
    db_session.commit()

    with pytest.raises(
        ValueError,
        match="not eligible for automatic linking",
    ):
        supabase_auth.link_supabase_user(
            db=db_session,
            access_token="mock-access-token",
            claims=supabase_identity["claims"],
            password="OriginalPassword123!",
        )

    db_session.refresh(unverified_local_user)

    assert unverified_local_user.supabase_user_id is None
    assert unverified_local_user.is_verified is True


def test_link_supabase_user_rejects_unconfirmed_email(
    db_session,
    monkeypatch,
    supabase_identity,
    unverified_local_user,
):
    class MockResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": supabase_identity["id"],
                "email": supabase_identity["email"],
                "email_confirmed_at": None,
            }

    monkeypatch.setattr(
        supabase_auth.httpx,
        "get",
        lambda *args, **kwargs: MockResponse(),
    )

    with pytest.raises(
        ValueError,
        match="confirm your email address",
    ):
        supabase_auth.link_supabase_user(
            db=db_session,
            access_token="mock-access-token",
            claims=supabase_identity["claims"],
            password="OriginalPassword123!",
        )

    db_session.refresh(unverified_local_user)

    assert unverified_local_user.supabase_user_id is None
    assert unverified_local_user.is_verified is False


def test_link_endpoint_rejects_missing_bearer_token(client):
    response = client.post(
        "/api/v1/auth/supabase/link",
        json={"password": "OriginalPassword123!"},
    )

    assert response.status_code == 401


def test_link_endpoint_rejects_invalid_bearer_token(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.api.auth.decode_supabase_access_token",
        lambda token: None,
    )

    response = client.post(
        "/api/v1/auth/supabase/link",
        headers={"Authorization": "Bearer invalid-token"},
        json={"password": "OriginalPassword123!"},
    )

    assert response.status_code == 401

def test_link_endpoint_success(
    client,
    db_session,
    monkeypatch,
    supabase_identity,
    unverified_local_user,
):
    monkeypatch.setattr(
        "app.api.auth.decode_supabase_access_token",
        lambda token: supabase_identity["claims"],
    )

    original_id = unverified_local_user.id

    response = client.post(
        "/api/v1/auth/supabase/link",
        headers={"Authorization": "Bearer mock-access-token"},
        json={"password": "OriginalPassword123!"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == original_id
    assert data["email"] == supabase_identity["email"]
    assert data["role"] == "employee"
    assert data["is_verified"] is True
    assert "password_hash" not in data


def test_link_endpoint_rejects_wrong_password(
    client,
    monkeypatch,
    supabase_identity,
    unverified_local_user,
):
    monkeypatch.setattr(
        "app.api.auth.decode_supabase_access_token",
        lambda token: supabase_identity["claims"],
    )

    response = client.post(
        "/api/v1/auth/supabase/link",
        headers={"Authorization": "Bearer mock-access-token"},
        json={"password": "WrongPassword123!"},
    )

    assert response.status_code == 403
    assert "password is incorrect" in response.json()["detail"]