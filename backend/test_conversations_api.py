from app.models import Conversation, ChatMessage, User


def get_conversation_auth_headers(
    client,
    db_session,
    email="conversation-test@example.com",
):
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Conversation Test User",
            "email": email,
            "password": "SecurePassword123!",
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
            "password": "SecurePassword123!",
        },
    )

    assert login_response.status_code == 200

    return {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        )
    }


def test_create_conversation(client, db_session):
    headers = get_conversation_auth_headers(client, db_session)

    response = client.post(
        "/api/v1/conversations",
        json={"title": "Business overview"},
        headers=headers,
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

    user = db_session.query(User).filter(
        User.email == "conversation-test@example.com"
    ).first()

    assert conversation.owner_id == user.id

def test_list_conversations(client, db_session):
    headers = get_conversation_auth_headers(client, db_session)

    user = db_session.query(User).filter(
        User.email == "conversation-test@example.com"
    ).first()

    first = Conversation(
        id="conversation-list-001",
        title="First conversation",
        owner_id=user.id,
    )

    second = Conversation(
        id="conversation-list-002",
        title="Second conversation",
        owner_id=user.id,
    )

    db_session.add_all([first, second])
    db_session.commit()

    response = client.get(
        "/api/v1/conversations",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["id"] for item in data} == {
        "conversation-list-001",
        "conversation-list-002",
    }


def test_list_conversations_returns_empty_list(client, db_session):
    headers = get_conversation_auth_headers(client, db_session)

    response = client.get(
        "/api/v1/conversations",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []

def test_get_conversation_with_messages(client, db_session):
    headers = get_conversation_auth_headers(client, db_session)

    user = db_session.query(User).filter(
        User.email == "conversation-test@example.com"
    ).first()

    conversation = Conversation(
        id="conversation-detail-001",
        title="Customer analysis",
        owner_id=user.id,
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
        f"/api/v1/conversations/{conversation.id}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == conversation.id
    assert data["title"] == "Customer analysis"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "Who is our top customer?"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content"] == (
        "Sarah Ahmed is your top customer."
    )

def test_get_conversation_without_messages(client, db_session):
    headers = get_conversation_auth_headers(client, db_session)

    user = db_session.query(User).filter(
        User.email == "conversation-test@example.com"
    ).first()

    conversation = Conversation(
        id="conversation-empty-001",
        title="Empty conversation",
        owner_id=user.id,
    )

    db_session.add(conversation)
    db_session.commit()

    response = client.get(
        f"/api/v1/conversations/{conversation.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == conversation.id
    assert response.json()["messages"] == []

def test_get_nonexistent_conversation(client, db_session):
    headers = get_conversation_auth_headers(client, db_session)

    response = client.get(
        "/api/v1/conversations/nonexistent-conversation",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"

def test_delete_conversation(client, db_session):
    headers = get_conversation_auth_headers(client, db_session)

    user = db_session.query(User).filter(
        User.email == "conversation-test@example.com"
    ).first()

    conversation = Conversation(
        id="conversation-delete-001",
        title="Conversation to delete",
        owner_id=user.id,
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
        f"/api/v1/conversations/{conversation.id}",
        headers=headers,
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

def test_delete_nonexistent_conversation(client, db_session):
    headers = get_conversation_auth_headers(client, db_session)

    response = client.delete(
        "/api/v1/conversations/nonexistent-conversation",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"

def test_create_conversation_uses_default_title(client, db_session):
    headers = get_conversation_auth_headers(client, db_session)

    response = client.post(
        "/api/v1/conversations",
        json={},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["title"] == "New conversation"

def test_users_can_only_list_their_own_conversations(client, db_session):
    owner_headers = get_conversation_auth_headers(
        client,
        db_session,
        email="conversation-owner@example.com",
    )

    other_headers = get_conversation_auth_headers(
        client,
        db_session,
        email="conversation-other@example.com",
    )

    owner = db_session.query(User).filter(
        User.email == "conversation-owner@example.com"
    ).first()

    conversation = Conversation(
        id="private-conversation-001",
        title="Private business discussion",
        owner_id=owner.id,
    )

    db_session.add(conversation)
    db_session.commit()

    owner_response = client.get(
        "/api/v1/conversations",
        headers=owner_headers,
    )

    other_response = client.get(
        "/api/v1/conversations",
        headers=other_headers,
    )

    assert owner_response.status_code == 200
    assert len(owner_response.json()) == 1

    assert other_response.status_code == 200
    assert other_response.json() == []

def test_user_cannot_retrieve_another_users_conversation(
    client,
    db_session,
):
    owner_headers = get_conversation_auth_headers(
        client,
        db_session,
        email="retrieve-owner@example.com",
    )

    other_headers = get_conversation_auth_headers(
        client,
        db_session,
        email="retrieve-other@example.com",
    )

    owner = db_session.query(User).filter(
        User.email == "retrieve-owner@example.com"
    ).first()

    conversation = Conversation(
        id="private-conversation-002",
        title="Confidential discussion",
        owner_id=owner.id,
    )

    db_session.add(conversation)
    db_session.commit()

    response = client.get(
        f"/api/v1/conversations/{conversation.id}",
        headers=other_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"

def test_user_cannot_delete_another_users_conversation(
    client,
    db_session,
):
    owner_headers = get_conversation_auth_headers(
        client,
        db_session,
        email="delete-owner@example.com",
    )

    other_headers = get_conversation_auth_headers(
        client,
        db_session,
        email="delete-other@example.com",
    )

    owner = db_session.query(User).filter(
        User.email == "delete-owner@example.com"
    ).first()

    conversation = Conversation(
        id="private-conversation-003",
        title="Protected discussion",
        owner_id=owner.id,
    )

    db_session.add(conversation)
    db_session.commit()

    response = client.delete(
        f"/api/v1/conversations/{conversation.id}",
        headers=other_headers,
    )

    assert response.status_code == 404

    # Verify that the original conversation still exists.
    remaining = db_session.query(Conversation).filter(
        Conversation.id == conversation.id
    ).first()

    assert remaining is not None
    assert remaining.owner_id == owner.id