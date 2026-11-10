from unittest.mock import patch, MagicMock

from app.ai.agent import stream_businesspilot
from app.ai.agent import ask_businesspilot


def test_dashboard_question():
    answer = ask_businesspilot(
        "Give me an overview of my business."
    )

    print("\nDashboard answer:")
    print(answer)

    assert isinstance(answer, str)
    assert len(answer) > 0


def test_top_customers_question():
    answer = ask_businesspilot(
        "Who are my top 5 customers?"
    )

    print("\nTop customers answer:")
    print(answer)

    assert isinstance(answer, str)
    assert len(answer) > 0


def test_low_stock_question():
    answer = ask_businesspilot(
        "Which products have low stock?"
    )

    print("\nLow stock answer:")
    print(answer)

    assert isinstance(answer, str)
    assert len(answer) > 0


def test_overdue_invoices_question():
    answer = ask_businesspilot(
        "Do I have any overdue invoices?"
    )

    print("\nOverdue invoices answer:")
    print(answer)

    assert isinstance(answer, str)
    assert len(answer) > 0



def test_stream_businesspilot_handles_gemini_structured_chunks():
    gemini_chunk = MagicMock()
    gemini_chunk.content = [
        {
            "type": "text",
            "text": "Gemini response ",
            "extras": {"signature": "test-signature"},
        },
        {
            "type": "text",
            "text": "continues successfully.",
        },
        {
            "type": "image",
            "data": "ignored",
        },
    ]

    mock_agent = MagicMock()
    mock_agent.stream.return_value = iter([
        (
            gemini_chunk,
            {"langgraph_node": "model"},
        )
    ])

    with patch("app.ai.agent.agent", mock_agent):
        chunks = list(
            stream_businesspilot(
                "Test Gemini streaming",
                "gemini-test-001",
            )
        )

    assert chunks == [
        "Gemini response ",
        "continues successfully.",
    ]


def test_stream_businesspilot_handles_ollama_string_chunks():
    ollama_chunk = MagicMock()
    ollama_chunk.content = "Ollama response"

    mock_agent = MagicMock()
    mock_agent.stream.return_value = iter([
        (
            ollama_chunk,
            {"langgraph_node": "model"},
        )
    ])

    with patch("app.ai.agent.agent", mock_agent):
        chunks = list(
            stream_businesspilot(
                "Test Ollama streaming",
                "ollama-test-001",
            )
        )

    assert chunks == ["Ollama response"]


def test_stream_businesspilot_ignores_non_model_chunks():
    tool_chunk = MagicMock()
    tool_chunk.content = "Internal tool output"

    mock_agent = MagicMock()
    mock_agent.stream.return_value = iter([
        (
            tool_chunk,
            {"langgraph_node": "tools"},
        )
    ])

    with patch("app.ai.agent.agent", mock_agent):
        chunks = list(
            stream_businesspilot(
                "Test tool chunk filtering",
                "filter-test-001",
            )
        )

    assert chunks == []


def test_ask_businesspilot_normalizes_gemini_response():
    gemini_response = [
        {
            "type": "text",
            "text": "You have 5 customers.",
        },
        {
            "type": "image",
            "data": "ignored",
        },
    ]

    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "messages": [
            MagicMock(content=gemini_response),
        ]
    }

    with patch("app.ai.agent.agent", mock_agent):
        response = ask_businesspilot(
            "How many customers?",
            "gemini-normalization-test",
        )

    assert response == "You have 5 customers."
    assert isinstance(response, str)


if __name__ == "__main__":
    test_dashboard_question()
    test_top_customers_question()
    test_low_stock_question()
    test_overdue_invoices_question()

    print("\nAll AI agent tests passed!")
