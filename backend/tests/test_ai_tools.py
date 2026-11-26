
from app.ai.tools import (
    get_business_dashboard,
    get_top_customers,
    get_low_stock_products,
    get_overdue_invoices,
    get_daily_revenue,
)


def test_dashboard():
    result = get_business_dashboard.invoke({})

    assert isinstance(result, dict)
    assert "total_customers" in result
    assert "total_sales" in result
    print("Dashboard:", result)


def test_top_customers():
    result = get_top_customers.invoke({"limit": 5})

    assert isinstance(result, list)
    print("Top customers:", result)


def test_low_stock():
    result = get_low_stock_products.invoke({"threshold": 10})

    assert isinstance(result, list)
    print("Low-stock products:", result)


def test_overdue_invoices():
    result = get_overdue_invoices.invoke({})

    assert isinstance(result, list)
    print("Overdue invoices:", result)


def test_daily_revenue():
    result = get_daily_revenue.invoke({})

    assert isinstance(result, list)
    print("Daily revenue:", result)


if __name__ == "__main__":
    test_dashboard()
    test_top_customers()
    test_low_stock()
    test_overdue_invoices()
    test_daily_revenue()

    print("\nAll AI tool tests passed!")
