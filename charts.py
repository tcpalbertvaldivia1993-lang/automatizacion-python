"""Report charts: sales by product, sales over time and the trend of sales
from one run (week) to the next.

Each function saves a PNG image (without a title: the report adds it). The first
two return (title, data), so the report can also show the table. The name of the
data index ("Product", "Day" or "Month") is used as the table header.
"""

import matplotlib

matplotlib.use("Agg")  # draws to files, without opening windows
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter, MaxNLocator

from formatting import number

# Chart colors: a single color for the data and soft greys for everything else.
BAR_COLOR = "#2a78d6"
INCOMPLETE_BAR_COLOR = "#86b6ef"  # same blue, lighter: months with incomplete data
SHARP_CHANGE_COLOR = "#d03b3b"  # alert red, the same as in the email
BACKGROUND_COLOR = "#fcfcfb"
MUTED_TEXT_COLOR = "#52514e"
GRID_COLOR = "#e4e3df"

# With real data there can be thousands of products and years of dates:
MAX_PRODUCTS = 10      # the product chart only shows the best sellers
MAX_DAILY_DAYS = 62    # with more days than this, sales are grouped by month
MAX_RUNS = 12          # the trend chart shows the last 12 weeks

# Axis numbers with thousands separators and no decimals: 1,400,000
AXIS_FORMAT = FuncFormatter(lambda value, _: number(value, 0))


def _prepare_axes(width=8, height=4.5):
    """Creates a figure with the style shared by all the charts."""
    figure, axes = plt.subplots(figsize=(width, height), dpi=120)
    figure.patch.set_facecolor(BACKGROUND_COLOR)
    axes.set_facecolor(BACKGROUND_COLOR)
    for side in ["top", "right", "left"]:
        axes.spines[side].set_visible(False)
    axes.spines["bottom"].set_color(GRID_COLOR)
    axes.tick_params(colors=MUTED_TEXT_COLOR, length=0)
    axes.set_axisbelow(True)
    return figure, axes


def _save(figure, path):
    figure.tight_layout()
    figure.savefig(path, facecolor=BACKGROUND_COLOR)
    plt.close(figure)


def sales_by_product_chart(clean, path):
    """Horizontal bars with the amount sold of each product, from highest to lowest.

    If there are more than MAX_PRODUCTS products, only the best sellers are shown.
    """
    total_products = clean["product"].nunique()
    data = clean.groupby("product")["amount"].sum().nlargest(MAX_PRODUCTS).sort_values()
    data.index.name = "Product"
    if total_products > MAX_PRODUCTS:
        title = f"Top {MAX_PRODUCTS} products by sales (of {total_products})"
    else:
        title = "Sales by product"

    figure, axes = _prepare_axes(height=0.45 * len(data) + 0.8)
    axes.barh(data.index, data.values, color=BAR_COLOR, height=0.7)
    axes.grid(axis="x", color=GRID_COLOR, linewidth=0.8)
    axes.spines["bottom"].set_visible(False)
    # Label with the value at the end of each bar.
    for position, value in enumerate(data.values):
        axes.text(value, position, f"  {number(value)}", va="center", fontsize=9, color=MUTED_TEXT_COLOR)
    axes.set_xlim(0, data.max() * 1.25)  # room for the label of the longest bar
    axes.xaxis.set_major_locator(MaxNLocator(5))  # few ticks, so they don't overlap
    axes.xaxis.set_major_formatter(AXIS_FORMAT)
    _save(figure, path)
    return title, data.sort_values(ascending=False)


def sales_over_time_chart(clean, path):
    """Columns with the amount sold each day, or each month if there are many days.

    Days (or months) without sales show as 0, so they don't look consecutive.
    If the first or last month doesn't have data for all its days, it's marked as
    incomplete (lighter color and a *), so it doesn't look like a drop in sales.
    """
    dates = pd.to_datetime(clean["date"])
    first, last = dates.min(), dates.max()
    incomplete = set()
    if (last - first).days + 1 > MAX_DAILY_DAYS:
        title, header, frequency = "Sales by month", "Month", "MS"
        label_format, table_format = "%m/%Y", "%Y-%m"
        period = dates.dt.to_period("M").dt.to_timestamp()
        if first.day != 1:
            incomplete.add(first.to_period("M").to_timestamp())
        if not last.is_month_end:
            incomplete.add(last.to_period("M").to_timestamp())
    else:
        title, header, frequency = "Sales by day", "Day", "D"
        label_format, table_format = "%d/%m", "%Y-%m-%d"
        period = dates

    grouped = clean["amount"].groupby(period).sum()
    everything = pd.date_range(grouped.index.min(), grouped.index.max(), freq=frequency)
    data = grouped.reindex(everything, fill_value=0)
    is_incomplete = [moment in incomplete for moment in data.index]

    figure, axes = _prepare_axes()
    labels = [
        moment.strftime(label_format) + ("*" if partial else "")
        for moment, partial in zip(data.index, is_incomplete)
    ]
    colors = [INCOMPLETE_BAR_COLOR if partial else BAR_COLOR for partial in is_incomplete]
    axes.bar(labels, data.values, color=colors, width=0.7)
    axes.grid(axis="y", color=GRID_COLOR, linewidth=0.8)
    axes.yaxis.set_major_formatter(AXIS_FORMAT)
    if len(data) > 12:
        figure.autofmt_xdate()
    if incomplete:
        note = f"* Incomplete month: the data runs from {first:%d/%m/%Y} to {last:%d/%m/%Y}."
        figure.text(0.01, 0.01, note, fontsize=9, color=MUTED_TEXT_COLOR)
    _save(figure, path)

    data.index = [
        moment.strftime(table_format) + (" (incomplete)" if partial else "")
        for moment, partial in zip(data.index, is_incomplete)
    ]
    data.index.name = header
    return title, data


def trend_chart(history, path):
    """Columns with the net sales of each run (each week), from the oldest to the
    most recent. The ones that changed sharply compared with the average of the
    previous ones are red, with the % on top.

    history must come from alerts.mark_sharp_changes (columns change and sharp).
    """
    data = history.tail(MAX_RUNS)
    labels = [f"{date:%d/%m}" for date in pd.to_datetime(data["date"])]
    # Two runs on the same day would have the same label and overlap: they get numbered.
    labels = [l if labels.count(l) == 1 else f"{l} ({i + 1})" for i, l in enumerate(labels)]
    colors = [SHARP_CHANGE_COLOR if sharp else BAR_COLOR for sharp in data["sharp"]]

    figure, axes = _prepare_axes(height=3.6)
    axes.bar(labels, data["net_sales"], color=colors, width=0.6)
    axes.grid(axis="y", color=GRID_COLOR, linewidth=0.8)
    axes.yaxis.set_major_formatter(AXIS_FORMAT)
    axes.set_ylim(min(0, data["net_sales"].min()), data["net_sales"].max() * 1.18)
    # With few weeks the bars would be huge: room is kept for at least 6,
    # and the chart fills up from left to right.
    axes.set_xlim(-0.6, max(len(data), 6) - 0.4)
    # Only sharp changes get a label, so the chart isn't full of numbers.
    for position, (value, change, sharp) in enumerate(
            zip(data["net_sales"], data["change"], data["sharp"])):
        if sharp:
            axes.text(position, value, f"{'+' if change > 0 else ''}{number(change, 0)}%",
                      ha="center", va="bottom", fontsize=9, fontweight="bold",
                      color=SHARP_CHANGE_COLOR)
    _save(figure, path)
