from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from app.ai.tools import business_tools
from sqlalchemy.engine import make_url
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are BusinessPilot AI, an intelligent business assistant.

Your responsibilities:
- Answer business questions using the available business tools.
- Retrieve real business data whenever a question requires it.
- Never invent customers, products, invoices, revenue, or statistics.
- Explain financial figures clearly.
- Use accurate and professional business language.
- If data is unavailable, say so honestly.
- Never claim to have performed an action that you did not perform.
- You currently have READ-ONLY access to business analytics.

When answering:
- Summarize the results clearly.
- Use bullet points or tables when useful.
- Include relevant numbers and monetary values.
- Explain important business findings in simple language.

For low-stock questions:
- Always call get_low_stock_products.
- Use threshold 10 by default.
- Never ask the user for a threshold unless they specify a different one.
- If the tool returns an empty list, explain that no products
  are at or below the threshold.
  
Tool error handling:
- If a business tool returns an error field, treat the operation as failed.
- Never interpret an error response as valid business data.
- Never invent or estimate missing results when a tool fails.
- Clearly tell the user that the requested business data
  is temporarily unavailable.
- Do not repeatedly call a tool that has returned a database error.
- Continue answering only when the available data is sufficient
  and reliable.
"""


def get_chat_model():
    """Create the configured chat model provider."""

    if settings.chat_model_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is required when using Gemini."
            )

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
        )

    return ChatOllama(
        model=settings.ollama_model,
        temperature=0,
        base_url=settings.ollama_base_url,
    )


model = get_chat_model()

# Convert SQLAlchemy's PostgreSQL URL into a psycopg-compatible URL.
database_url = make_url(
    settings.resolved_database_url
).set(
    drivername="postgresql"
).render_as_string(hide_password=False)


# Create a connection pool that opens during application startup.
connection_pool = ConnectionPool(
    conninfo=database_url,
    min_size=settings.checkpoint_pool_min_size,
    max_size=settings.checkpoint_pool_max_size,
    kwargs={
        "autocommit": True,
        "prepare_threshold": 0,
    },
    open=False,
)


# Initialize the PostgreSQL checkpoint saver.
checkpointer = PostgresSaver(connection_pool)


# Compile the agent using persistent PostgreSQL memory.
agent = create_agent(
    model=model,
    tools=business_tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)


def initialize_agent_storage():
    """Open the connection pool and initialize checkpoint tables."""
    connection_pool.open(wait=True)
    checkpointer.setup()
    logger.info("LangGraph PostgreSQL checkpoint storage initialized.")


def close_agent_storage():
    """Close the PostgreSQL connection pool."""
    connection_pool.close()
    logger.info("LangGraph PostgreSQL connection pool closed.")

def normalize_ai_response(content) -> str:
    """Convert model output into plain text."""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ).strip()

    return str(content)

def ask_businesspilot(
    question: str,
    conversation_id: str = "default",
) -> str:
    try:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": question,
                    }
                ]
            },
            config={
                "configurable": {
                    "thread_id": conversation_id,
                }
            },
        )

        return normalize_ai_response(
            result["messages"][-1].content
        )

    except Exception:
        logging.exception(
            "BusinessPilot AI generation failed."
        )

        return (
            "I'm sorry, but BusinessPilot AI is temporarily "
            "unavailable. Please check the AI service and try again."
        )


def stream_businesspilot(
    question: str,
    conversation_id: str = "default",
):
    """
    Stream the AI response token by token while preserving
    LangGraph conversation memory.
    """

    try:
        for message_chunk, metadata in agent.stream(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": question,
                    }
                ]
            },
            config={
                "configurable": {
                    "thread_id": conversation_id,
                }
            },
            stream_mode="messages",
        ):

            if metadata.get("langgraph_node") == "model":
                content = message_chunk.content

                if isinstance(content, str):
                    if content:
                        yield content

                elif isinstance(content, list):
                    for block in content:
                        if (
                            isinstance(block, dict)
                            and block.get("type") == "text"
                            and isinstance(block.get("text"), str)
                        ):
                            yield block["text"]

    except Exception:
        logging.exception(
            "BusinessPilot AI streaming generation failed."
        )

        raise RuntimeError(
            "BusinessPilot AI is temporarily unavailable. "
            "Please check the AI service and try again."
        ) from None