import shutil
from pathlib import Path

import pandas as pd
import pytest

import main

SAMPLE_CSV = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"


@pytest.fixture(autouse=True)
def temporary_results(tmp_path, monkeypatch):
    """The test results go to a temporary folder, not to results/."""
    folder = tmp_path / "results"
    folder.mkdir()
    monkeypatch.setattr(main, "RESULTS_FOLDER", folder)
    return folder


def test_excel_gives_the_same_as_csv(tmp_path):
    excel = tmp_path / "sales.xlsx"
    pd.read_csv(SAMPLE_CSV, dtype=str, keep_default_na=False).to_excel(excel, index=False)
    assert main.process_file(excel, "€") == main.process_file(SAMPLE_CSV, "€")


def test_results_in_one_folder_per_file(temporary_results):
    main.process_file(SAMPLE_CSV, "£")
    folder = temporary_results / "sample_sales"
    assert (folder / "clean_sales.csv").exists()
    assert (folder / "charts" / "sales_by_product.png").exists()
    html = (folder / "report.html").read_text(encoding="utf-8")
    assert "1,375.99 £" in html                      # number format and chosen currency
    assert html.count("data:image/png;base64,") == 2  # both charts go inside the HTML


def test_the_html_doesnt_run_text_from_the_data(tmp_path, temporary_results):
    file = tmp_path / "weird.csv"
    file.write_text(
        "order_id,date,customer,product,quantity,unit_price\n"
        "1,2026-09-01,Alice,<script>alert(1)</script>,1,10\n",
        encoding="utf-8",
    )
    main.process_file(file, "€")
    html = (temporary_results / "weird" / "report.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_summary_html(tmp_path, temporary_results):
    broken = tmp_path / "broken.csv"
    broken.write_text("order,total\n1,10\n", encoding="utf-8")
    results = [(SAMPLE_CSV, main.process_file(SAMPLE_CSV, "€")), (broken, None)]
    html = main.write_summary(results, "€").read_text(encoding="utf-8")
    assert 'href="sample_sales/report.html"' in html
    assert "Couldn't be processed" in html


def test_file_without_the_right_columns_returns_none(tmp_path):
    broken = tmp_path / "broken.csv"
    broken.write_text("order,total\n1,10\n", encoding="utf-8")
    assert main.process_file(broken, "€") is None


def test_find_files_only_csv_and_excel(tmp_path):
    for name in ["b.csv", "a.xlsx", "notes.txt"]:
        (tmp_path / name).write_text("", encoding="utf-8")
    (tmp_path / "processed").mkdir()
    assert [f.name for f in main.find_files(tmp_path)] == ["a.xlsx", "b.csv"]


def test_move_to_processed(tmp_path):
    file = tmp_path / "sales.csv"
    shutil.copy(SAMPLE_CSV, file)
    main.move_to_processed(file)
    assert not file.exists()
    assert (tmp_path / "processed" / "sales.csv").exists()
