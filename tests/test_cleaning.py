import pandas as pd

from datetime import date

from cleaning import (
    calculate_metrics,
    clean_sales,
    parse_date,
    parse_price,
    parse_quantity,
)


def create_df(rows):
    columns = ["order_id", "date", "customer", "product", "quantity", "unit_price"]
    return pd.DataFrame(rows, columns=columns)


def test_parse_price():
    assert parse_price("7,50") == 7.5
    assert parse_price("899.99 €") == 899.99
    assert parse_price("£899.99") == 899.99
    assert parse_price("abc") is None
    assert parse_price("") is None


def test_parse_quantity():
    assert parse_quantity("3") == 3
    assert parse_quantity("-2") == -2   # return
    assert parse_quantity("2.5") is None
    assert parse_quantity("two") is None
    assert parse_quantity("") is None


def test_parse_date():
    assert parse_date("2026-09-01") == date(2026, 9, 1)
    assert parse_date("2026-09-01 08:26:00") == date(2026, 9, 1)  # with time
    assert parse_date("2026-09-01 08:26") == date(2026, 9, 1)
    assert parse_date("2026-13-45") is None   # impossible month and day
    assert parse_date("2026-02-30") is None   # February doesn't have 30 days
    assert parse_date("01/09/2026") is None   # different format
    assert parse_date("yesterday") is None
    assert parse_date("") is None
    assert parse_date("2099-01-15") is None   # future date


def test_invalid_dates_are_discarded():
    df = create_df([
        ["1", "2026-13-45", "Alice", "Keyboard", "1", "10"],
        ["2", "", "Alice", "Keyboard", "1", "10"],
        ["3", "2026-09-01", "Alice", "Keyboard", "1", "10"],
    ])
    clean, discarded = clean_sales(df)
    assert list(clean["order_id"]) == ["3"]
    assert list(discarded["reason"]) == ["empty or invalid date"] * 2


def test_time_is_removed_from_the_date():
    df = create_df([["1", "2026-09-01 08:26:00", "Alice", "Keyboard", "1", "10"]])
    clean, _ = clean_sales(df)
    assert clean.loc[0, "date"] == "2026-09-01"


def test_duplicates_with_spaces_are_removed():
    df = create_df([
        ["1", "2026-09-01", " Alice ", "Keyboard", "1", "10"],
        ["1", "2026-09-01", "Alice", "Keyboard", "1", "10"],
    ])
    clean, discarded = clean_sales(df)
    assert len(clean) == 1
    assert clean.loc[0, "customer"] == "Alice"
    assert discarded.loc[0, "reason"] == "duplicate row"


def test_invalid_quantities_and_prices_are_discarded():
    df = create_df([
        ["1", "2026-09-01", "Alice", "Keyboard", "", "10"],
        ["2", "2026-09-01", "Alice", "Keyboard", "0", "10"],
        ["3", "2026-09-01", "Alice", "Keyboard", "1", "abc"],
        ["4", "2026-09-01", "Alice", "Keyboard", "1", "-5"],
        ["5", "2026-09-01", "Alice", "Keyboard", "2", "10"],
    ])
    clean, discarded = clean_sales(df)
    assert list(clean["order_id"]) == ["5"]
    assert len(discarded) == 4


def test_metrics():
    df = create_df([
        ["1", "2026-09-01", "Alice", "Keyboard", "2", "10"],
        ["1", "2026-09-01", "Alice", "Mouse", "1", "5"],
        ["2", "2026-09-02", "Luke", "Monitor", "1", "100"],
    ])
    clean, _ = clean_sales(df)
    metrics = calculate_metrics(clean)
    assert metrics == {
        "net_sales": 125.0,
        "returns": 0.0,
        "orders": 2,
        "avg_order_value": 62.5,
    }


def test_returns_are_subtracted_and_dont_count_as_orders():
    df = create_df([
        ["1", "2026-09-01", "Alice", "Keyboard", "2", "10"],
        ["C1", "2026-09-02", "Alice", "Keyboard", "-1", "10"],  # cancels 1 keyboard
    ])
    clean, discarded = clean_sales(df)
    assert discarded.empty
    metrics = calculate_metrics(clean)
    assert metrics == {
        "net_sales": 10.0,
        "returns": 10.0,
        "orders": 1,
        "avg_order_value": 10.0,
    }
