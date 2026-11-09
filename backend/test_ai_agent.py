
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


if __name__ == "__main__":
    test_dashboard_question()
    test_top_customers_question()
    test_low_stock_question()
    test_overdue_invoices_question()

    print("\nAll AI agent tests passed!")
