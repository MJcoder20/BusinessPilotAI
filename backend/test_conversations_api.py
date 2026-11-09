
from app.models import Conversation, ChatMessage


def test_create_conversation(client, db_session):
    response = client.post(
        "/api/v1/conversations",
        json={"title": "Business overview"},
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"]
    assert data["title"] == "Business overview"
    assert data["created_at"] is not None
    assert data["updated_at"] is not None

    conversation = (
        db_session.query(Conversation)
        .filter(Conversation.id == data["id"])
        .first()
    )

    assert conversation is not None


def test_list_conversations(client, db_session):
    first = Conversation(
        id="conversation-list-001",
        title="First conversation",
    )
    second = Conversation(
        id="conversation-list-002",
        title="Second conversation",
    )

    db_session.add_all([first, second])
    db_session.commit()

    response = client.get("/api/v1/conversations")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["id"] for item in data} == {
        "conversation-list-001",
        "conversation-list-002",
    }


def test_list_conversations_returns_empty_list(client):
    response = client.get("/api/v1/conversations")

    assert response.status_code == 200
    assert response.json() == []


def test_get_conversation_with_messages(client, db_session):
    conversation = Conversation(
        id="conversation-detail-001",
        title="Customer analysis",
    )

    db_session.add(conversation)
    db_session.flush()

    messages = [
        ChatMessage(
            conversation_id=conversation.id,
            role="user",
            content="Who is our top customer?",
        ),
        ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content="Sarah Ahmed is your top customer.",
        ),
    ]

    db_session.add_all(messages)
    db_session.commit()

    response = client.get(
        f"/api/v1/conversations/{conversation.id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == conversation.id
    assert data["title"] == "Customer analysis"
    assert len(data["messages"]) == 2

    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == (
        "Who is our top customer?"
    )

    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content"] == (
        "Sarah Ahmed is your top customer."
    )


def test_get_conversation_without_messages(client, db_session):
    conversation = Conversation(
        id="conversation-empty-001",
        title="Empty conversation",
    )

    db_session.add(conversation)
    db_session.commit()

    response = client.get(
        f"/api/v1/conversations/{conversation.id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == conversation.id
    assert data["messages"] == []


def test_get_nonexistent_conversation(client):
    response = client.get(
        "/api/v1/conversations/nonexistent-conversation"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


def test_delete_conversation(client, db_session):
    conversation = Conversation(
        id="conversation-delete-001",
        title="Conversation to delete",
    )

    db_session.add(conversation)
    db_session.flush()

    message = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content="Delete this conversation.",
    )

    db_session.add(message)
    db_session.commit()

    response = client.delete(
        f"/api/v1/conversations/{conversation.id}"
    )

    assert response.status_code == 204
    assert response.content == b""

    assert (
        db_session.query(Conversation)
        .filter(Conversation.id == conversation.id)
        .first()
        is None
    )

    assert (
        db_session.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .all()
        == []
    )


def test_delete_nonexistent_conversation(client):
    response = client.delete(
        "/api/v1/conversations/nonexistent-conversation"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


def test_create_conversation_uses_default_title(client):
    response = client.post(
        "/api/v1/conversations",
        json={},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "New conversation"