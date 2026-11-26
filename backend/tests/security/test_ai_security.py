
import pytest

from app.ai.tools import (
    business_tools,
    get_top_customers,
    get_low_stock_products,
)


EXPECTED_TOOLS = {
    "get_business_dashboard",
    "get_top_customers",
    "get_low_stock_products",
    "get_overdue_invoices",
    "get_daily_revenue",
}


def test_agent_exposes_only_approved_read_only_tools():
    actual_tools = {business_tool.name for business_tool in business_tools}

    assert actual_tools == EXPECTED_TOOLS


@pytest.mark.parametrize("limit", [0, -1, 21, 100])
def test_invalid_customer_limits_are_rejected_without_database_access(
    monkeypatch, limit
):
    def block_database_access():
        raise AssertionError("Database access should not occur.")

    monkeypatch.setattr(
        "app.ai.tools.SessionLocal",
        block_database_access,
    )

    result = get_top_customers.invoke({"limit": limit})

    assert result == [{"error": "Limit must be between 1 and 20."}]


@pytest.mark.parametrize("threshold", [-1, 100001, 200000])
def test_invalid_stock_thresholds_are_rejected_without_database_access(
    monkeypatch, threshold
):
    def block_database_access():
        raise AssertionError("Database access should not occur.")

    monkeypatch.setattr(
        "app.ai.tools.SessionLocal",
        block_database_access,
    )

    result = get_low_stock_products.invoke({"threshold": threshold})

    assert result == [{"error": "Threshold must be between 0 and 100000."}]
