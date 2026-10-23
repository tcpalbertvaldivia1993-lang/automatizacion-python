"""Number formatting shared by the report and the charts."""


def number(value, decimals=2):
    """Formats a number with thousands separators: 1234567.891 -> "1,234,567.89"."""
    return f"{value:,.{decimals}f}"
