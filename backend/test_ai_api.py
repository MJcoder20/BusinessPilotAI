import asyncio
import json
import pytest
from unittest.mock import patch

from starlette.requests import Request

from app.models import Conversation, ChatMessage, User
from app.main import unexpected_exception_handler


def get_ai_auth_headers(
    client,
    db_session,
    email="ai-test@example.com",
):
    password = "SecurePassword123!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "AI Test User",
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code == 201

    user = (
        db_session.query(User)
        .filter(User.email == email)
        .first()
    )

    assert user is not None

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    return {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        )
    }

def test_chat_creates_conversation_and_saves_messages(client, db_session):
    headers = get_ai_auth_headers(client, db_session)
    with patch(
        "app.api.ai.ask_businesspilot",
        return_value="Your business has 5 customers.",
    ) as mock_agent:
        response = client.post(
            "/api/v1/ai/chat",
            json={"message": "How many customers do we have?"},
            headers=headers,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["conversation_id"]
    assert data["response"] == "Your business has 5 customers."

    mock_agent.assert_called_once_with(
        question="How many customers do we have?",
        user_id=1,
        conversation_id=data["conversation_id"],
    )

    messages = (
        db_session.query(ChatMessage)
        .filter(ChatMessage.conversation_id == data["conversation_id"])
        .order_by(ChatMessage.id)
        .all()
    )

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "How many customers do we have?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Your business has 5 customers."


def test_chat_saves_normalized_gemini_response(client, db_session):
    headers = get_ai_auth_headers(client, db_session)
    normalized_response = "You have 5 customers."

    with patch(
        "app.api.ai.ask_businesspilot",
        return_value=normalized_response,
    ):
        response = client.post(
            "/api/v1/ai/chat",
            json={"message": "How many customers do we have?"},
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json()["response"] == normalized_response

    conversation_id = response.json()["conversation_id"]

    assistant_message = (
        db_session.query(ChatMessage)
        .filter(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.role == "assistant",
        )
        .first()
    )

    assert assistant_message is not None
    assert assistant_message.content == normalized_response

def test_chat_reuses_existing_conversation(client, db_session):
    headers = get_ai_auth_headers(client, db_session)
    user = db_session.query(User).filter(
        User.email == "ai-test@example.com"
    ).first()

    conversation = Conversation(
        id="existing-chat-001",
        title="Previous conversation",
        owner_id=user.id,
    )

    db_session.add(conversation)
    db_session.commit()

    with patch(
        "app.api.ai.ask_businesspilot",
        return_value="Your revenue is $5,000.",
    ) as mock_agent:
        response = client.post(
            "/api/v1/ai/chat",
            headers=headers,
            json={
                "message": "What is our revenue?",
                "conversation_id": "existing-chat-001",
            },
        )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "existing-chat-001"

    mock_agent.assert_called_once_with(
        question="What is our revenue?",
        user_id=user.id,
        conversation_id="existing-chat-001",
    )

    messages = (
        db_session.query(ChatMessage)
        .filter(
            ChatMessage.conversation_id == "existing-chat-001"
        )
        .all()
    )

    assert len(messages) == 2


def test_chat_returns_404_for_unknown_conversation(client, db_session):
    headers = get_ai_auth_headers(client, db_session)
    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Hello",
            "conversation_id": "unknown-chat-001",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


def test_chat_returns_500_when_agent_fails(client, db_session):
    headers = get_ai_auth_headers(client, db_session)
    with patch(
        "app.api.ai.ask_businesspilot",
        side_effect=RuntimeError("Internal model failure"),
    ):
        response = client.post(
            "/api/v1/ai/chat",
            headers=headers,
            json={"message": "Show dashboard"},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to process chat request"


def test_chat_rejects_empty_message(client, db_session):
    headers = get_ai_auth_headers(client, db_session)
    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": ""},
    )

    assert response.status_code == 422


def test_chat_rejects_message_over_4000_characters(client, db_session):
    headers = get_ai_auth_headers(client, db_session)
    response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "A" * 4001},
    )

    assert response.status_code == 422


def test_chat_stream_returns_tokens_and_persists_response(
    client,
    db_session,
):
    headers = get_ai_auth_headers(client, db_session)
    user = db_session.query(User).filter(
        User.email == "ai-test@example.com"
    ).first()

    assert user is not None
    user_id = user.id
    with patch(
        "app.api.ai.stream_businesspilot",
        return_value=iter(["Your ", "revenue ", "is $5000."]),
    ) as mock_stream:
        response = client.post(
            "/api/v1/ai/chat/stream",
            headers=headers,
            json={"message": "Show revenue"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]

    assert events[0].get("conversation_id")
    conversation_id = events[0]["conversation_id"]

    tokens = [
        event["token"]
        for event in events
        if "token" in event
    ]

    assert tokens == ["Your ", "revenue ", "is $5000."]
    assert events[-1] == {"done": True}

    mock_stream.assert_called_once_with(
        "Show revenue",
        user_id,
        conversation_id,
    )

    messages = (
        db_session.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .all()
    )

    assert len(messages) == 2
    assert any(
        message.role == "assistant"
        and message.content == "Your revenue is $5000."
        for message in messages
    )


def test_chat_stream_reuses_existing_conversation(
    client,
    db_session,
):
    headers = get_ai_auth_headers(client, db_session)
    user = db_session.query(User).filter(
        User.email == "ai-test@example.com"
    ).first()
    conversation = Conversation(
        id="stream-chat-001",
        title="Existing stream conversation",
        owner_id=user.id,
    )

    db_session.add(conversation)
    db_session.commit()

    with patch(
        "app.api.ai.stream_businesspilot",
        return_value=iter(["Hello ", "again."]),
    ):
        response = client.post(
            "/api/v1/ai/chat/stream",
            headers=headers,
            json={
                "message": "Continue",
                "conversation_id": "stream-chat-001",
            },
        )

    assert response.status_code == 200

    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]

    assert events[0]["conversation_id"] == "stream-chat-001"
    assert {"done": True} in events


def test_chat_stream_returns_404_for_unknown_conversation(client, db_session):
    headers = get_ai_auth_headers(client, db_session)
    response = client.post(
        "/api/v1/ai/chat/stream",
        headers=headers,
        json={
            "message": "Continue",
            "conversation_id": "unknown-stream-chat",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."


def test_chat_stream_emits_error_when_generation_fails(
    client,
    db_session,
):
    headers = get_ai_auth_headers(client, db_session)
    def failing_stream(*args):
        yield "Partial "
        raise RuntimeError("Internal model failure")

    with patch(
        "app.api.ai.stream_businesspilot",
        side_effect=failing_stream,
    ):
        response = client.post(
            "/api/v1/ai/chat/stream",
            headers=headers,
            json={"message": "Generate a report"},
        )

    assert response.status_code == 200

    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]

    assert any("token" in event for event in events)

    error_events = [
        event for event in events
        if "error" in event
    ]

    assert len(error_events) == 1
    assert error_events[0]["error"] == (
        "An error occurred while generating the AI response."
    )

    # A partial assistant response must not be saved.
    assistant_messages = (
        db_session.query(ChatMessage)
        .filter(
            ChatMessage.role == "assistant",
            ChatMessage.conversation_id == events[0]["conversation_id"],
        )
        .all()
    )

    assert assistant_messages == []


def test_unexpected_exception_returns_safe_response():
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/test",
            "raw_path": b"/test",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "root_path": "",
        }
    )

    internal_error = "Database password: secret123"

    try:
        raise RuntimeError(internal_error)
    except RuntimeError as exc:
        response = asyncio.run(
            unexpected_exception_handler(request, exc)
        )

    assert response.status_code == 500

    response_data = json.loads(response.body)

    assert response_data["detail"] == (
        "An unexpected internal error occurred. Please try again later."
    )

    assert internal_error not in response.body.decode()


def test_chat_rate_limit_returns_429(client, db_session):
    headers = get_ai_auth_headers(client, db_session)

    with patch(
        "app.api.ai.ask_businesspilot",
        return_value="Test response",
    ) as mock_agent:
        responses = [
            client.post(
                "/api/v1/ai/chat",
                json={"message": "Test rate limiting"},
                headers=headers,
            )
            for _ in range(11)
        ]

    assert all(
        response.status_code == 200
        for response in responses[:10]
    )
    assert responses[10].status_code == 429
    assert mock_agent.call_count == 10

def test_chat_stream_rate_limit_returns_429(client, db_session):
    headers = get_ai_auth_headers(client, db_session)

    with patch(
        "app.api.ai.stream_businesspilot",
        return_value=iter(["Test response"]),
    ) as mock_stream:
        responses = [
            client.post(
                "/api/v1/ai/chat/stream",
                json={"message": "Test streaming rate limit"},
                headers=headers,
            )
            for _ in range(6)
        ]

    assert all(
        response.status_code == 200
        for response in responses[:5]
    )
    assert responses[5].status_code == 429
    assert mock_stream.call_count == 5


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/ai/chat",
        "/api/v1/ai/chat/stream",
    ],
)
def test_ai_chat_requires_authentication(client, endpoint):
    response = client.post(
        endpoint,
        json={"message": "Show my business dashboard"},
    )

    assert response.status_code == 401

def test_chat_cannot_access_another_users_conversation(
    client,
    db_session,
):
    owner_headers = get_ai_auth_headers(
        client,
        db_session,
        email="ai-owner@example.com",
    )

    owner = db_session.query(User).filter(
        User.email == "ai-owner@example.com"
    ).first()

    conversation = Conversation(
        id="private-ai-chat-001",
        title="Private conversation",
        owner_id=owner.id,
    )

    db_session.add(conversation)
    db_session.commit()

    other_headers = get_ai_auth_headers(
        client,
        db_session,
        email="ai-other@example.com",
    )

    with patch("app.api.ai.ask_businesspilot") as mock_agent:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Access this conversation",
                "conversation_id": "private-ai-chat-001",
            },
            headers=other_headers,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"
    mock_agent.assert_not_called()

    messages = db_session.query(ChatMessage).filter(
        ChatMessage.conversation_id == "private-ai-chat-001"
    ).all()

    assert messages == []

def test_chat_stream_cannot_access_another_users_conversation(
    client,
    db_session,
):
    owner_headers = get_ai_auth_headers(
        client,
        db_session,
        email="ai-stream-owner@example.com",
    )

    owner = db_session.query(User).filter(
        User.email == "ai-stream-owner@example.com"
    ).first()

    conversation = Conversation(
        id="private-stream-chat-001",
        title="Private streaming conversation",
        owner_id=owner.id,
    )

    db_session.add(conversation)
    db_session.commit()

    other_headers = get_ai_auth_headers(
        client,
        db_session,
        email="ai-stream-other@example.com",
    )

    with patch("app.api.ai.stream_businesspilot") as mock_stream:
        response = client.post(
            "/api/v1/ai/chat/stream",
            json={
                "message": "Access this private conversation",
                "conversation_id": "private-stream-chat-001",
            },
            headers=other_headers,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."
    mock_stream.assert_not_called()

    messages = db_session.query(ChatMessage).filter(
        ChatMessage.conversation_id == "private-stream-chat-001"
    ).all()

    assert messages == []
