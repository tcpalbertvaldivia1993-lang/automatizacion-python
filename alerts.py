"""Sharp change alerts: compares each run with the previous ones.

Each run saves its totals in a history file (a CSV with one row per run). The
next time, the new totals are compared with the AVERAGE of the last 4 runs: if
sales or orders go up or down by more than the threshold, it's a sharp change.
The average is used instead of just the previous week because sales vary a lot
from one week to the next: with real data, comparing only with the previous
week raised an alert almost every week.

Sales per product are also saved in another history file, to report which of
the best sellers have changed a lot. That isn't an alert, just information: a
single large order already changes a product's sales a lot.
"""

from datetime import datetime

import pandas as pd

DEFAULT_THRESHOLD = 30  # in %
REFERENCE_WEEKS = 4     # compared with the average of the last 4 runs
# Metrics that are watched and the name they have in the alert.
WATCHED = {"net_sales": "Net sales", "orders": "Orders"}

# Each product on its own varies much more than the total, so its threshold is higher.
DEFAULT_PRODUCT_THRESHOLD = 50  # in %
# Only the best sellers on average are watched: a product going from
# 10 € to 3 € isn't interesting.
MAX_WATCHED_PRODUCTS = 10
MAX_SHOWN_PRODUCTS = 5  # in the email, the 5 that changed the most


def sum_metrics(metrics_list):
    """Combines the metrics of several files into the totals of the run."""
    sales = round(sum(m["net_sales"] for m in metrics_list), 2)
    orders = sum(m["orders"] for m in metrics_list)
    return {
        "net_sales": sales,
        "returns": round(sum(m["returns"] for m in metrics_list), 2),
        "orders": orders,
        "avg_order_value": round(sales / orders, 2) if orders else 0.0,
    }


def read_history(path):
    """Reads the whole history (one row per run). Empty if it doesn't exist yet."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def read_reference(path, weeks=REFERENCE_WEEKS):
    """Calculates the average of the watched metrics over the last runs.

    Returns a dictionary with those averages and how many runs were used
    ("weeks", fewer than 4 at the start), or None if there's no history yet.
    """
    last = read_history(path).tail(weeks)
    if last.empty:
        return None
    reference = {key: float(last[key].mean()) for key in WATCHED}
    reference["weeks"] = len(last)
    return reference


def mark_sharp_changes(history, threshold=DEFAULT_THRESHOLD, weeks=REFERENCE_WEEKS):
    """Adds to the history the % change in sales compared with the average of the
    previous runs, and whether that change is sharp. Used to color the trend
    chart with the same rule as the alert."""
    history = history.copy()
    # shift: each row is compared with the ones before it, not with itself.
    average = history["net_sales"].shift().rolling(weeks, min_periods=1).mean()
    history["change"] = (100 * (history["net_sales"] - average) / average).where(average > 0)
    history["sharp"] = history["change"].abs() >= threshold  # NaN (no data) gives False
    return history


def save_run(path, totals):
    """Appends the totals of this run to the end of the history."""
    row = pd.DataFrame([{"date": f"{datetime.now():%Y-%m-%d %H:%M}", **totals}])
    path.parent.mkdir(parents=True, exist_ok=True)
    row.to_csv(path, mode="a", header=not path.exists(), index=False)


def compare(current, reference, threshold=DEFAULT_THRESHOLD):
    """Compares the watched metrics with the average of the previous runs.

    Returns a list with one dictionary per metric. "change" is the % variation
    (None if the average was 0 or negative and it makes no sense to calculate it)
    and "sharp" says whether the change exceeds the threshold, up or down.
    """
    changes = []
    for key, name in WATCHED.items():
        average, now = float(reference[key]), float(current[key])
        change = 100 * (now - average) / average if average > 0 else None
        changes.append({
            "key": key,
            "name": name,
            "reference": average,
            "current": now,
            "change": change,
            "sharp": change is not None and abs(change) >= threshold,
        })
    return changes


def product_history_path(history_path):
    """The per-product history sits next to the totals one: history.csv -> history_products.csv."""
    return history_path.with_name(f"{history_path.stem}_products.csv")


def save_products(path, sales_by_product):
    """Appends to the per-product history one row for each product in this run."""
    rows = pd.DataFrame({
        # With seconds, to tell apart two runs in a row.
        "date": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
        "product": sales_by_product.index,
        "sales": sales_by_product.round(2).values,
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, mode="a", header=not path.exists(), index=False)


def read_products_reference(path, weeks=REFERENCE_WEEKS):
    """Returns the average sales of each product over the last runs,
    or None if there's no history yet. A product not sold one week counts as 0."""
    if not path.exists():
        return None
    history = pd.read_csv(path, dtype={"product": str})
    if history.empty:
        return None
    dates = history["date"].drop_duplicates().tail(weeks)
    last = history[history["date"].isin(dates)]
    table = last.pivot_table(index="date", columns="product", values="sales", aggfunc="sum")
    return table.fillna(0).mean()


def compare_products(current, reference, threshold=DEFAULT_PRODUCT_THRESHOLD,
                     maximum=MAX_WATCHED_PRODUCTS, show=MAX_SHOWN_PRODUCTS):
    """Finds the products that changed the most among the best sellers on average.

    current and reference are the sales per product (Series with the product as
    index). A product not sold this time counts as 0 (-100 %). Returns at most
    `show` products that changed at least the threshold, from the largest change
    to the smallest (up or down).
    """
    watched = reference[reference > 0].nlargest(maximum)
    changes = []
    for product, average in watched.items():
        now = float(current.get(product, 0.0))
        change = 100 * (now - average) / average
        if abs(change) >= threshold:
            changes.append({"product": product, "reference": float(average),
                            "current": now, "change": change})
    return sorted(changes, key=lambda c: abs(c["change"]), reverse=True)[:show]
