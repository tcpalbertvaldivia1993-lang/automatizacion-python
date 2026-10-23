"""Automation tool: cleans sales files and generates reports.

Usage:
    venv/bin/python main.py                              # uses data/sample_sales.csv
    venv/bin/python main.py path/to/my_sales.csv         # a CSV file
    venv/bin/python main.py path/to/my_sales.xlsx        # an Excel file
    venv/bin/python main.py path/to/folder/              # every CSV and Excel in the folder
    venv/bin/python main.py data/real/online_retail.csv --currency £

Options:
    --currency SYMBOL     currency symbol in the report (default €)
    --move-processed      when finished, moves each file processed without errors
                          to a "processed/" subfolder next to it (useful when scheduled)
    --send-email          sends the reports by email (settings in .env,
                          see .env.example)
    --history PATH        saves the totals of each run in that CSV and alerts if
                          sales or orders change sharply compared with the
                          average of the 4 previous runs
    --threshold PERCENT   how much it has to change to alert (default 30%)
    --product-threshold PERCENT
                          how much one of the 10 best-selling products has to
                          change to mention it in the email (default 50%)

Results (results/ folder):
    <file name>/clean_sales.csv       -> data already cleaned
    <file name>/discarded_rows.csv    -> removed rows and the reason
    <file name>/report.html           -> report with metrics and charts
    <file name>/charts/               -> PNG images of the charts
    summary.html                      -> comparison of files (only with a folder)
    trend.png                         -> sales of each run (only with --history)
    run.log                           -> log of every run
"""

import argparse
import base64
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

import alerts
import send_email
from charts import sales_by_product_chart, sales_over_time_chart, trend_chart
from cleaning import calculate_metrics, clean_sales
from formatting import number

RESULTS_FOLDER = Path("results")
DEFAULT_FILE = Path("data/sample_sales.csv")
EXTENSIONS = {".csv", ".xlsx", ".xls"}

# HTML templates for the reports. autoescape stops a text from the data
# (for example a product called "<b>Offer</b>") from being read as HTML.
TEMPLATES = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent / "templates"),
    autoescape=select_autoescape(),
)
TEMPLATES.filters["number"] = number  # in the templates: {{ value | number }}


def setup_logging():
    """Saves the messages in results/run.log and also shows them on screen."""
    RESULTS_FOLDER.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(RESULTS_FOLDER / "run.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    # matplotlib writes internal warnings that don't matter in our log.
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def read_file(file):
    """Reads a CSV or an Excel file. Everything is read as text so we can detect the errors ourselves."""
    if file.suffix.lower() == ".csv":
        return pd.read_csv(file, dtype=str, keep_default_na=False)
    return pd.read_excel(file, dtype=str, keep_default_na=False)


def find_files(path):
    """Returns the list of files to process: the file itself, or the ones in the folder."""
    if path.is_dir():
        return sorted(f for f in path.iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONS)
    return [path]


def create_charts(clean, output_folder):
    """Generates the charts in <output_folder>/charts/.

    Returns a list with (title, image, data) for each chart.
    """
    folder = output_folder / "charts"
    folder.mkdir(exist_ok=True)
    charts = []
    for name, function in [
        ("sales_by_product.png", sales_by_product_chart),
        ("sales_over_time.png", sales_over_time_chart),
    ]:
        title, data = function(clean, folder / name)
        charts.append((title, f"charts/{name}", data))
    return charts


def embedded_image(path):
    """Converts a PNG into text (base64) to put it inside the HTML.

    That way the report is a single file: it can be sent by email and shows complete.
    """
    content = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{content}"


def write_report(output_folder, file, original_rows, clean, discarded, metrics, charts, currency):
    """Creates the HTML report from the templates/report.html template."""
    reasons = discarded["reason"].value_counts()
    html = TEMPLATES.get_template("report.html").render(
        file=file,
        file_name=file.name,
        run_date=f"{datetime.now():%d/%m/%Y %H:%M}",
        currency=currency,
        metrics=metrics,
        charts=[
            {
                "title": title,
                "image": embedded_image(output_folder / image),
                "header": data.index.name,
                "rows": list(data.items()),
            }
            for title, image, data in charts
        ],
        quality={
            "original": original_rows,
            "valid": len(clean),
            "discarded": len(discarded),
            "discarded_percent": 100 * len(discarded) / original_rows,
            "reasons": list(reasons.items()),
        },
    )
    path = output_folder / "report.html"
    path.write_text(html, encoding="utf-8")
    return path


def process_file(file, currency):
    """Cleans a file and generates its results in results/<file name>/.

    Returns the metrics, or None if the file couldn't be processed.
    """
    logging.info("Processing %s", file)
    try:
        df = read_file(file)
    except FileNotFoundError:
        logging.error("File not found: %s", file)
        return None
    except Exception as error:  # damaged file, unknown format...
        logging.error("Couldn't read %s: %s", file, error)
        return None
    logging.info("Rows read: %d", len(df))

    try:
        clean, discarded = clean_sales(df)
    except ValueError as error:
        logging.error("%s: %s", file.name, error)
        return None

    for reason, n in discarded["reason"].value_counts().items():
        logging.warning("Discarded %d rows because of: %s", n, reason)
    logging.info("Valid rows: %d", len(clean))
    if clean.empty:
        logging.error("%s: no valid rows left", file.name)
        return None

    metrics = calculate_metrics(clean)
    logging.info("Metrics: %s", metrics)

    output_folder = RESULTS_FOLDER / file.stem
    output_folder.mkdir(exist_ok=True)
    clean.to_csv(output_folder / "clean_sales.csv", index=False)
    discarded.to_csv(output_folder / "discarded_rows.csv", index=False)
    charts = create_charts(clean, output_folder)
    report_path = write_report(output_folder, file, len(df), clean, discarded,
                               metrics, charts, currency)
    logging.info("Report generated in %s", report_path)
    return metrics


def write_summary(results, currency, trend=None):
    """Creates results/summary.html with one row per file, to compare them.

    trend is the path of the weekly trend chart, if there is one.
    """
    errors = sum(1 for _, metrics in results if metrics is None)
    html = TEMPLATES.get_template("summary.html").render(
        run_date=f"{datetime.now():%d/%m/%Y %H:%M}",
        currency=currency,
        trend=embedded_image(trend) if trend else None,
        succeeded=len(results) - errors,
        errors=errors,
        rows=[
            {"name": file.name, "metrics": metrics, "link": f"{file.stem}/report.html"}
            for file, metrics in results
        ],
    )
    path = RESULTS_FOLDER / "summary.html"
    path.write_text(html, encoding="utf-8")
    return path


def sales_by_product(files):
    """Adds up the amount of each product in the clean data of all the files."""
    cleaned = [pd.read_csv(RESULTS_FOLDER / file.stem / "clean_sales.csv",
                           usecols=["product", "amount"], dtype={"product": str})
               for file in files]
    return pd.concat(cleaned).groupby("product")["amount"].sum()


def compare_products_with_previous(files, history_path, threshold):
    """Saves the sales per product in their history and finds the ones that changed the most.

    Returns the list of those products, or None if there's nothing to compare with.
    """
    path = alerts.product_history_path(history_path)
    current = sales_by_product(files)
    reference = alerts.read_products_reference(path)
    alerts.save_products(path, current)
    if reference is None:
        return None
    changes = alerts.compare_products(current, reference, threshold)
    for c in changes:  # information only: not an alert
        logging.info("Product that changed the most: %s %+.1f%%", c["product"], c["change"])
    return changes


def compare_with_previous(results, history_path, threshold,
                          product_threshold=alerts.DEFAULT_PRODUCT_THRESHOLD):
    """Saves the totals and the sales per product of this run in the history files
    and compares them with the average of the last runs.

    Returns {"weeks": ..., "changes": [...], "products": [...]}, where "weeks" is
    how many runs go into the average, or None if there's nothing to compare with.
    """
    files = [file for file, metrics in results if metrics is not None]
    if not files:
        return None
    totals = alerts.sum_metrics([metrics for _, metrics in results if metrics is not None])
    # The reference is read before saving: this run isn't part of its own average.
    reference = alerts.read_reference(history_path)
    alerts.save_run(history_path, totals)
    products = compare_products_with_previous(files, history_path, product_threshold)
    if reference is None:
        logging.info("First run with history: next time there will be something to compare with")
        return None

    changes = alerts.compare(totals, reference, threshold)
    for c in changes:
        if c["sharp"]:
            logging.warning("Sharp change in %s: %+.1f%% compared with the average of the %d "
                            "previous runs", c["name"].lower(), c["change"], reference["weeks"])
    return {"weeks": reference["weeks"], "changes": changes, "products": products or []}


def create_trend_chart(history_path, threshold):
    """Draws results/trend.png with the sales of the last runs.

    Returns the path of the chart, or None if there are still fewer than two runs.
    """
    history = alerts.read_history(history_path)
    if len(history) < 2:
        return None
    path = RESULTS_FOLDER / "trend.png"
    trend_chart(alerts.mark_sharp_changes(history, threshold), path)
    logging.info("Trend chart generated in %s", path)
    return path


def send_by_email(results, currency, comparison=None, trend=None):
    """Sends an email with the metrics of each file and their HTML reports attached.

    If there's a comparison with the previous runs, the email shows it and the
    subject warns about sharp changes. If there's a trend chart, it goes in the body.
    """
    config = send_email.read_config()
    succeeded = [file for file, metrics in results if metrics is not None]
    errors = len(results) - len(succeeded)
    date = f"{datetime.now():%d/%m/%Y}"

    html = TEMPLATES.get_template("email.html").render(
        run_date=date,
        currency=currency,
        succeeded=len(succeeded),
        errors=errors,
        rows=[{"name": file.name, "metrics": metrics} for file, metrics in results],
        comparison=comparison,
        trend=trend is not None,
    )
    subject = f"Sales report · {date}"
    if errors:
        subject += f" · ⚠ {errors} with errors"
    for c in (comparison or {}).get("changes", []):
        if c["sharp"]:
            subject += f" · ⚠ {c['name']} {c['change']:+.0f}%"
    attachments = [(f"report_{file.stem}.html", RESULTS_FOLDER / file.stem / "report.html")
                   for file in succeeded]

    images = [("trend", trend)] if trend else []  # in the template: cid:trend
    message = send_email.build_message(config, subject, html, attachments, images)
    send_email.send(config, message)
    logging.info("Email sent to %s with %d %s", config["EMAIL_TO"], len(attachments),
                 "report attached" if len(attachments) == 1 else "reports attached")


def move_to_processed(file):
    """Moves the file to a "processed/" subfolder so it isn't processed again."""
    destination = file.parent / "processed"
    destination.mkdir(exist_ok=True)
    shutil.move(file, destination / file.name)
    logging.info("Moved to %s", destination / file.name)


def parse_args():
    parser = argparse.ArgumentParser(description="Cleans sales files and generates reports.")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_FILE,
                        help="CSV/Excel file, or a folder with several")
    parser.add_argument("--currency", default="€", help="currency symbol (default €)")
    parser.add_argument("--move-processed", action="store_true",
                        help="move each file processed without errors to processed/")
    parser.add_argument("--send-email", action="store_true",
                        help="send the reports by email (settings in .env)")
    parser.add_argument("--history", type=Path,
                        help="CSV where the totals of each run are saved to compare them "
                             "with the average of the 4 previous ones and alert about "
                             "sharp changes")
    parser.add_argument("--threshold", type=float, default=alerts.DEFAULT_THRESHOLD,
                        help="%% rise or fall considered sharp (default 30)")
    parser.add_argument("--product-threshold", type=float,
                        default=alerts.DEFAULT_PRODUCT_THRESHOLD,
                        help="%% change of a product to mention it (default 50)")
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging()
    logging.info("Run started with %s", args.path)

    files = find_files(args.path)
    if args.history:  # in case the history files are in the same folder: they aren't sales
        histories = {args.history.resolve(),
                     alerts.product_history_path(args.history).resolve()}
        files = [f for f in files if f.resolve() not in histories]
    if not files:
        logging.info("No CSV or Excel files in %s. Nothing to do.", args.path)
        logging.info("Run finished")
        return

    results = []
    for file in files:
        metrics = process_file(file, args.currency)
        results.append((file, metrics))
        if metrics is not None and args.move_processed:
            move_to_processed(file)

    comparison = trend = None
    if args.history:
        comparison = compare_with_previous(results, args.history, args.threshold,
                                           args.product_threshold)
        trend = create_trend_chart(args.history, args.threshold)

    if args.path.is_dir():
        logging.info("Summary generated in %s", write_summary(results, args.currency, trend))

    errors = sum(1 for _, metrics in results if metrics is None)
    email_failed = False
    if args.send_email:
        try:
            send_by_email(results, args.currency, comparison, trend)
        except Exception as error:  # incomplete settings, no internet, wrong password...
            logging.error("Couldn't send the email: %s", error)
            email_failed = True

    logging.info("Run finished: %d files succeeded, %d with errors",
                 len(results) - errors, errors)
    if errors or email_failed:
        sys.exit(1)  # so the scheduled task or GitHub Actions know something failed


if __name__ == "__main__":
    main()
