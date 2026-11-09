import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Conversation, ChatMessage
from app.schemas.ai import ChatRequest, ChatResponse
from app.ai.agent import ask_businesspilot

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai",
    tags=["AI Assistant"],
)


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    conversation_id = request.conversation_id or str(uuid4())

    try:
        # 1. Find or create the conversation.
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

        if conversation_id and request.conversation_id and not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        if not conversation:
            conversation = Conversation(
                id=conversation_id,
                title=request.message.strip()[:200],
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

        # 2. Save the user's message.
        user_message = ChatMessage(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
        )

        db.add(user_message)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()

        # 3. Ask the LangGraph agent.
        ai_response = ask_businesspilot(
            question=request.message,
            conversation_id=conversation_id,
        )

        # 4. Save the AI response.
        assistant_message = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=ai_response,
        )

        db.add(assistant_message)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()

        # 5. Return the response.
        return ChatResponse(
            conversation_id=conversation_id,
            response=ai_response,
        )

    except HTTPException:
        raise

    except Exception:
        db.rollback()
        logger.exception("Failed to process AI chat request")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat request",
        )
