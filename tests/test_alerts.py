import pandas as pd
import pytest

import alerts
import main
import send_email
from tests.test_send_email import CONFIG, SAMPLE_CSV, FakeServer

WEEK_1 = {"net_sales": 1000.0, "returns": 0.0, "orders": 10, "avg_order_value": 100.0}


@pytest.fixture
def fake_email(tmp_path, monkeypatch):
    """Results in a temporary folder and emails to a fake server."""
    monkeypatch.setattr(main, "RESULTS_FOLDER", tmp_path)
    monkeypatch.setattr(send_email, "read_config", lambda: CONFIG)
    monkeypatch.setattr(send_email.smtplib, "SMTP", FakeServer)
    FakeServer.sent.clear()
    return FakeServer.sent


def test_sum_metrics_of_several_files():
    other = {"net_sales": 500.0, "returns": 20.0, "orders": 5, "avg_order_value": 100.0}
    assert alerts.sum_metrics([WEEK_1, other]) == {
        "net_sales": 1500.0, "returns": 20.0, "orders": 15, "avg_order_value": 100.0,
    }


def test_reference_is_the_average_of_the_last_4_runs(tmp_path):
    path = tmp_path / "history.csv"
    assert alerts.read_reference(path) is None
    alerts.save_run(path, WEEK_1)
    alerts.save_run(path, {**WEEK_1, "net_sales": 2000.0})
    # At the start there are fewer than 4: the average of the ones available is used.
    assert alerts.read_reference(path) == {"net_sales": 1500.0, "orders": 10.0, "weeks": 2}
    for sales in [3000.0, 4000.0, 5000.0]:
        alerts.save_run(path, {**WEEK_1, "net_sales": sales})
    # With 5 runs, the first one (1,000) is no longer included: (2000+3000+4000+5000) / 4
    assert alerts.read_reference(path)["net_sales"] == 3500.0
    assert path.read_text(encoding="utf-8").count("date") == 1  # the header only once


@pytest.mark.parametrize("sales, sharp", [(1100, False), (1300, True), (750, False), (700, True)])
def test_sharp_change_depending_on_threshold(sales, sharp):
    changes = alerts.compare({**WEEK_1, "net_sales": sales}, WEEK_1, threshold=30)
    assert changes[0]["key"] == "net_sales"
    assert changes[0]["sharp"] is sharp


def test_without_previous_sales_no_percentage_is_calculated():
    changes = alerts.compare(WEEK_1, {**WEEK_1, "net_sales": 0}, threshold=30)
    assert changes[0]["change"] is None and not changes[0]["sharp"]


def test_email_warns_about_a_sharp_drop(tmp_path, fake_email):
    # The previous 4 weeks sold 2,000 € in 16 orders; this one, 1,375.99 € in 8.
    history = tmp_path / "history.csv"
    for _ in range(4):
        alerts.save_run(history, {**WEEK_1, "net_sales": 2000.0, "orders": 16})
    results = [(SAMPLE_CSV, main.process_file(SAMPLE_CSV, "€"))]
    comparison = main.compare_with_previous(results, history, threshold=30)
    main.send_by_email(results, "€", comparison)

    message = fake_email[0][1]
    assert "⚠ Net sales -31%" in message["Subject"]
    assert "⚠ Orders -50%" in message["Subject"]
    body = message.get_body(preferencelist=("html",)).get_content()
    assert "Sharp change" in body and "-31.2%" in body and "(drop)" in body
    assert "the average of the previous 4 weeks" in body
    assert alerts.read_history(history)["net_sales"].iloc[-1] == 1375.99


def test_mark_sharp_changes_with_the_average():
    history = pd.DataFrame({"net_sales": [1000.0, 1100.0, 700.0, 1000.0, 1000.0, 600.0]})
    marked = alerts.mark_sharp_changes(history, threshold=30)
    # 1st: nothing before · +10% · 700 vs 1,050 (-33%) · +7% · +5% · 600 vs 950 (-37%)
    assert marked["sharp"].tolist() == [False, False, True, False, False, True]
    assert round(marked["change"][5], 1) == -36.8


def test_trend_chart_in_the_email(tmp_path, fake_email):
    history = tmp_path / "history.csv"
    alerts.save_run(history, WEEK_1)
    assert main.create_trend_chart(history, 30) is None  # with a single week there's no chart
    alerts.save_run(history, {**WEEK_1, "net_sales": 500.0})
    trend = main.create_trend_chart(history, 30)
    assert trend == tmp_path / "trend.png" and trend.exists()

    main.send_by_email([(SAMPLE_CSV, None)], "€", trend=trend)
    message = fake_email[0][1]
    assert 'src="cid:trend"' in message.get_body(preferencelist=("html",)).get_content()
    images = [p for p in message.walk() if p.get_content_type() == "image/png"]
    assert [p["Content-ID"] for p in images] == ["<trend>"]

    html = main.write_summary([(SAMPLE_CSV, None)], "€", trend).read_text(encoding="utf-8")
    assert "week by week" in html and "data:image/png;base64," in html


def test_first_run_doesnt_compare(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "RESULTS_FOLDER", tmp_path)
    results = [(SAMPLE_CSV, main.process_file(SAMPLE_CSV, "€"))]
    assert main.compare_with_previous(results, tmp_path / "history.csv", 30) is None
    assert (tmp_path / "history.csv").exists()
    assert (tmp_path / "history_products.csv").exists()


def test_products_that_changed_the_most():
    reference = pd.Series({"Laptop": 1000.0, "Monitor": 400.0, "Sleeve": 200.0,
                           "Mouse": 100.0, "Cable": 5.0})
    current = pd.Series({"Laptop": 950.0, "Monitor": 100.0, "Sleeve": 500.0, "Cable": 1.0,
                         "New": 900.0})
    changes = alerts.compare_products(current, reference, threshold=50, maximum=4, show=2)
    # Sleeve +150%, Mouse -100% (no sales), Monitor -75%, Laptop -5% (below the threshold).
    # Cable isn't among the 4 best sellers and New didn't sell before: they aren't watched.
    # The 2 largest changes are shown, rise or drop.
    assert [(c["product"], c["change"]) for c in changes] == [("Sleeve", 150.0), ("Mouse", -100.0)]


def test_products_reference_with_the_average(tmp_path):
    path = tmp_path / "history_products.csv"
    assert alerts.read_products_reference(path) is None
    for n, sales in enumerate([{"A": 10.0, "B": 20.0}, {"A": 30.0}]):
        alerts.save_products(path, pd.Series(sales))
        # The date has seconds: it's set by hand so the runs don't coincide.
        history = pd.read_csv(path)
        history.loc[history.index[-len(sales):], "date"] = f"2026-10-1{n} 08:00:00"
        history.to_csv(path, index=False)
    # B wasn't sold the second week: it counts as 0 in the average.
    assert alerts.read_products_reference(path).to_dict() == {"A": 20.0, "B": 10.0}


def test_products_in_the_email_are_information_only(tmp_path, fake_email):
    # Same total as before, but the Keyboard sold 500 € on average and now 51 €.
    history = tmp_path / "history.csv"
    alerts.save_run(history, {**WEEK_1, "net_sales": 1375.99, "orders": 8})
    alerts.save_products(alerts.product_history_path(history),
                         pd.Series({"Laptop": 899.99, "Keyboard": 500.0}))
    results = [(SAMPLE_CSV, main.process_file(SAMPLE_CSV, "€"))]
    comparison = main.compare_with_previous(results, history, threshold=30, product_threshold=50)
    assert [p["product"] for p in comparison["products"]] == ["Keyboard"]
    main.send_by_email(results, "€", comparison)

    message = fake_email[0][1]
    assert "⚠" not in message["Subject"]  # a product isn't a reason to alert
    body = message.get_body(preferencelist=("html",)).get_content()
    assert "Products that changed the most" in body and "Keyboard" in body
    assert "No sharp changes compared with the previous week" in body
