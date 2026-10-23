import pandas as pd

from charts import MAX_PRODUCTS, sales_by_product_chart, sales_over_time_chart


def create_clean():
    return pd.DataFrame({
        "date": ["2026-09-01", "2026-09-01", "2026-09-04"],
        "product": ["Keyboard", "Mouse", "Keyboard"],
        "amount": [20.0, 5.0, 10.0],
    })


def test_sales_by_product(tmp_path):
    path = tmp_path / "product.png"
    title, data = sales_by_product_chart(create_clean(), path)
    assert path.exists()
    assert title == "Sales by product"
    assert data.to_dict() == {"Keyboard": 30.0, "Mouse": 5.0}


def test_with_many_products_only_the_best_sellers_are_shown(tmp_path):
    clean = pd.DataFrame({
        "date": ["2026-09-01"] * 15,
        "product": [f"Product {i}" for i in range(15)],
        "amount": [float(i) for i in range(15)],
    })
    title, data = sales_by_product_chart(clean, tmp_path / "product.png")
    assert len(data) == MAX_PRODUCTS
    assert data.index[0] == "Product 14"
    assert title == f"Top {MAX_PRODUCTS} products by sales (of 15)"


def test_sales_by_day_fills_days_without_sales(tmp_path):
    path = tmp_path / "day.png"
    title, data = sales_over_time_chart(create_clean(), path)
    assert path.exists()
    assert title == "Sales by day"
    assert data.to_dict() == {
        "2026-09-01": 25.0,
        "2026-09-02": 0.0,
        "2026-09-03": 0.0,
        "2026-09-04": 10.0,
    }


def test_with_many_days_it_groups_by_month(tmp_path):
    clean = pd.DataFrame({
        "date": ["2026-01-01", "2026-01-20", "2026-04-30"],
        "product": ["Keyboard"] * 3,
        "amount": [10.0, 5.0, 7.0],
    })
    title, data = sales_over_time_chart(clean, tmp_path / "month.png")
    assert title == "Sales by month"
    assert data.to_dict() == {"2026-01": 15.0, "2026-02": 0.0, "2026-03": 0.0, "2026-04": 7.0}


def test_incomplete_months_are_marked(tmp_path):
    clean = pd.DataFrame({
        "date": ["2026-01-10", "2026-02-15", "2026-04-05"],  # starts on the 10th and ends on the 5th
        "product": ["Keyboard"] * 3,
        "amount": [10.0, 5.0, 7.0],
    })
    _, data = sales_over_time_chart(clean, tmp_path / "month.png")
    assert list(data.index) == [
        "2026-01 (incomplete)",
        "2026-02",
        "2026-03",
        "2026-04 (incomplete)",
    ]
