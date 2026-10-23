"""Prepares the real "Online Retail" dataset (UCI) to use it with main.py.

These are real sales from a UK online shop between 2010 and 2011
(about 540,000 rows). Source: https://archive.ics.uci.edu/dataset/352/online+retail

Real data almost never comes with the columns our tool expects, so this script:
  1. Downloads the Excel file (only the first time).
  2. Sets aside the rows that aren't product sales (shipping, fees, adjustments)
     and saves them in data/real/online_retail_excluded.csv so they can be reviewed.
  3. Renames the columns to ours.
  4. Saves it as a CSV in data/real/online_retail.csv

Usage:
    venv/bin/python prepare_online_retail.py
    venv/bin/python main.py data/real/online_retail.csv
"""

import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
FOLDER = Path("data/real")
EXCEL = FOLDER / "Online Retail.xlsx"
OUTPUT_CSV = FOLDER / "online_retail.csv"
EXCLUDED_CSV = FOLDER / "online_retail_excluded.csv"

# Codes (StockCode) that aren't products in this dataset.
# Found by reviewing the codes that don't follow the usual "12345" or "12345A" format.
NOT_PRODUCTS = {
    "POST": "shipping",         # POSTAGE
    "DOT": "shipping",          # DOTCOM POSTAGE
    "C2": "shipping",           # CARRIAGE
    "BANK CHARGES": "fee",
    "AMAZONFEE": "fee",
    "CRUK": "fee",              # CRUK Commission
    "M": "adjustment",          # Manual
    "m": "adjustment",          # Manual
    "D": "adjustment",          # Discount
    "B": "adjustment",          # Adjust bad debt
    "S": "adjustment",          # SAMPLES
}

# Column in the original file -> column our tool expects.
COLUMNS = {
    "InvoiceNo": "order_id",
    "InvoiceDate": "date",
    "CustomerID": "customer",
    "Description": "product",
    "Quantity": "quantity",
    "UnitPrice": "unit_price",
}


def download():
    """Downloads and unzips the Excel file if it doesn't exist yet."""
    if EXCEL.exists():
        print(f"Already downloaded: {EXCEL}")
        return
    FOLDER.mkdir(parents=True, exist_ok=True)
    print("Downloading (about 23 MB)...")
    with urllib.request.urlopen(URL) as response:
        content = response.read()
    with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
        zip_file.extract(EXCEL.name, FOLDER)
    print(f"Saved in {EXCEL}")


def convert():
    """Reads the Excel file, sets aside what isn't a product, renames the columns and saves the CSV."""
    print("Reading the Excel file (it can take a couple of minutes)...")
    # dtype=str: everything is read as text, like main.py, so no errors are hidden.
    df = pd.read_excel(EXCEL, dtype=str)

    not_product = df["StockCode"].isin(NOT_PRODUCTS.keys())
    excluded = df[not_product].copy()
    excluded["type"] = excluded["StockCode"].map(NOT_PRODUCTS)
    excluded.to_csv(EXCLUDED_CSV, index=False)
    print(f"{len(excluded):,} rows set aside because they aren't products (in {EXCLUDED_CSV}):")
    for kind, n in excluded["type"].value_counts().items():
        print(f"  - {kind}: {n:,}")

    df = df[~not_product][list(COLUMNS)].rename(columns=COLUMNS)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"{len(df):,} rows saved in {OUTPUT_CSV}")


if __name__ == "__main__":
    download()
    convert()
