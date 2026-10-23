"""Functions to clean the sales data, detect errors and calculate the metrics.

This module is used both by main.py (automatic runs) and by the notebook.
"""

from datetime import date, datetime

import pandas as pd

# Accepted date formats: date only, or date with time (common in real data).
DATE_FORMATS = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
REQUIRED_COLUMNS = ["order_id", "date", "customer", "product", "quantity", "unit_price"]


def check_columns(df):
    """Raises an error if the file is missing any required column."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in the file: {', '.join(missing)}")


def strip_spaces(df):
    """Removes leading and trailing spaces, and leaves a single space between words."""
    df = df.copy()
    for column in df.columns:
        df[column] = df[column].str.strip().str.replace(r"\s+", " ", regex=True)
    return df


def parse_price(text):
    """Converts a price written as text to a number.

    Accepts recoverable formats such as "7,50" or "£899.99".
    Returns None if the price can't be understood (for example "abc").
    """
    if pd.isna(text) or text == "":
        return None
    clean = text.replace("€", "").replace("£", "").replace("$", "").replace(" ", "").replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None


def parse_date(text):
    """Converts a "YYYY-MM-DD" date (with or without time) to a Python date.

    The time, if any, is dropped: only the day matters.
    Returns None if it's empty, malformed (for example "yesterday"),
    doesn't exist in the calendar (for example "2026-13-45") or is in the future.
    """
    if pd.isna(text) or text == "":
        return None
    for date_format in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, date_format).date()
            break
        except ValueError:
            continue
    else:
        return None  # it didn't match any format
    if parsed > date.today():
        return None
    return parsed


def parse_quantity(text):
    """Converts a quantity to an integer. Returns None if it's not valid.

    Negative quantities are valid: they are returns or cancellations.
    """
    if pd.isna(text) or text == "":
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if not value.is_integer():
        return None
    return int(value)


def clean_sales(df):
    """Cleans the sales DataFrame.

    Returns two DataFrames:
      - clean: the correct rows, with quantity and price already as numbers.
      - discarded: the removed rows, with a "reason" column.
    """
    check_columns(df)
    df = strip_spaces(df)

    discards = []

    # 1. Duplicate rows (checked after stripping spaces,
    #    so " Alice Smith " and "Alice Smith" count as the same).
    is_duplicate = df.duplicated(keep="first")
    duplicates = df[is_duplicate].copy()
    duplicates["reason"] = "duplicate row"
    discards.append(duplicates)
    df = df[~is_duplicate].copy()

    # 2. Empty, malformed, impossible or future dates.
    dates = df["date"].apply(parse_date)
    bad_date = dates.isna()
    bad_dates = df[bad_date].copy()
    bad_dates["reason"] = "empty or invalid date"
    discards.append(bad_dates)
    df = df[~bad_date].copy()
    # All valid dates are stored as "YYYY-MM-DD", without time.
    df["date"] = dates[~bad_date].astype(str)

    # 3. Empty or invalid quantities. A negative quantity is NOT removed:
    #    it's a return or cancellation and will be subtracted from sales.
    df["quantity_num"] = df["quantity"].apply(parse_quantity)
    bad_quantity = df["quantity_num"].isna() | (df["quantity_num"] == 0)
    bad = df[bad_quantity].copy()
    bad["reason"] = "empty or invalid quantity"
    discards.append(bad)
    df = df[~bad_quantity].copy()

    # 4. Malformed, empty or non-positive prices.
    df["price_num"] = df["unit_price"].apply(parse_price)
    bad_price = df["price_num"].isna() | (df["price_num"] <= 0)
    bad = df[bad_price].copy()
    bad["reason"] = "empty or malformed price"
    discards.append(bad)
    df = df[~bad_price].copy()

    # Final columns with the already converted values.
    df["quantity"] = df["quantity_num"].astype(int)
    df["unit_price"] = df["price_num"]
    df["amount"] = (df["quantity"] * df["unit_price"]).round(2)
    clean = df.drop(columns=["quantity_num", "price_num"]).reset_index(drop=True)

    discarded = pd.concat(discards)[REQUIRED_COLUMNS + ["reason"]]
    return clean, discarded.reset_index(drop=True)


def calculate_metrics(clean):
    """Calculates net sales, returns, number of orders and average order value.

    Net sales already have returns and cancellations subtracted.
    Only orders with at least one sale line (positive quantity) count as orders.
    """
    net_sales = round(float(clean["amount"].sum()), 2)
    # abs and not a minus sign: with no returns, -0.0 would show as "-0.00".
    returns = round(abs(float(clean.loc[clean["amount"] < 0, "amount"].sum())), 2)
    orders = int(clean.loc[clean["quantity"] > 0, "order_id"].nunique())
    average = round(net_sales / orders, 2) if orders else 0.0
    return {
        "net_sales": net_sales,
        "returns": returns,
        "orders": orders,
        "avg_order_value": average,
    }
