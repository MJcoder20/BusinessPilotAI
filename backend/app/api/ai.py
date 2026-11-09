import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Conversation, ChatMessage
from app.schemas.ai import ChatRequest, ChatResponse
from app.ai.agent import ask_businesspilot, stream_businesspilot

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


@router.post("/chat/stream")
def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Stream BusinessPilot AI responses using Server-Sent Events (SSE).
    """

    # 1. Find or create conversation and save user message.
    try:
        conversation = None

        if request.conversation_id:
            conversation = (
                db.query(Conversation)
                .filter(Conversation.id == request.conversation_id)
                .first()
            )

            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found.",
                )

        else:
            conversation = Conversation()
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

        conversation_id = str(conversation.id)

        user_message = ChatMessage(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
        )

        db.add(user_message)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()

    except HTTPException:
        db.rollback()
        db.close()
        raise

    except Exception:
        db.rollback()
        logger.exception(
            "Failed to prepare AI streaming request."
        )
        db.close()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare chat request.",
        )

    # 2. Generate the streaming response.
    def generate():
        full_response = ""

        try:
            # Send conversation ID to frontend.
            yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"

            # Stream AI response.
            for chunk in stream_businesspilot(
                request.message,
                conversation_id,
            ):
                full_response += chunk

                yield f"data: {json.dumps({'token': chunk})}\n\n"

            # Save complete assistant response.
            if full_response:
                assistant_message = ChatMessage(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_response,
                )

                db.add(assistant_message)
                conversation.updated_at = datetime.now(timezone.utc)
                db.commit()

            # Signal completion.
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception:
            db.rollback()

            logger.exception(
                "Streaming AI response failed."
            )

            yield f"data: {json.dumps({'error': 'An error occurred while generating the AI response.'})}\n\n"

        finally:
            db.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )