from unittest.mock import MagicMock

from app.core.config import settings
from app.main import engine


def mock_database_connection(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr(
        engine,
        "connect",
        lambda: connection,
    )
    return connection


def test_health_endpoint(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_with_gemini_configured(client, monkeypatch):
    mock_database_connection(monkeypatch)

    monkeypatch.setattr(
        settings,
        "chat_model_provider",
        "gemini",
    )
    monkeypatch.setattr(
        settings,
        "gemini_api_key",
        "test-gemini-key",
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "connected",
        "ai_provider": "gemini",
        "ai_status": "configured",
    }


def test_readiness_with_gemini_key_missing(client, monkeypatch):
    mock_database_connection(monkeypatch)

    monkeypatch.setattr(
        settings,
        "chat_model_provider",
        "gemini",
    )
    monkeypatch.setattr(
        settings,
        "gemini_api_key",
        None,
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "status": "not_ready",
        "database": "connected",
        "ai_provider": "gemini",
        "ai_status": "not_configured",
    }


def test_readiness_when_database_is_unavailable(client, monkeypatch):
    connection = MagicMock()
    connection.__enter__.return_value.execute.side_effect = Exception(
        "Database unavailable"
    )

    monkeypatch.setattr(
        engine,
        "connect",
        lambda: connection,
    )
    monkeypatch.setattr(
        settings,
        "chat_model_provider",
        "gemini",
    )
    monkeypatch.setattr(
        settings,
        "gemini_api_key",
        "test-gemini-key",
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["database"] == "disconnected"
