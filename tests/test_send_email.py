from pathlib import Path

import pytest

import main
import send_email

SAMPLE_CSV = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"

CONFIG = {
    "SMTP_SERVER": "smtp.example.com",
    "SMTP_PORT": "587",
    "EMAIL_USER": "me@example.com",
    "EMAIL_PASSWORD": "secret",
    "EMAIL_TO": "boss@example.com",
}


class FakeServer:
    """Imitates smtplib.SMTP without connecting to the internet; records what it's asked."""

    sent = []

    def __init__(self, server, port, timeout):
        self.data = {"server": server, "port": port}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def starttls(self, context):
        self.data["encrypted"] = True

    def login(self, user, password):
        self.data["login"] = (user, password)

    def send_message(self, message):
        FakeServer.sent.append((self.data, message))


@pytest.fixture(autouse=True)
def no_environment_variables(monkeypatch):
    for key in send_email.KEYS:
        monkeypatch.delenv(key, raising=False)


def test_read_config(tmp_path):
    file = tmp_path / ".env"
    file.write_text(
        "# comment\n" + "\n".join(f"{k}={v}" for k, v in CONFIG.items()) + "\n",
        encoding="utf-8",
    )
    assert send_email.read_config(file) == CONFIG


def test_incomplete_config_gives_a_clear_error(tmp_path):
    file = tmp_path / ".env"
    file.write_text("SMTP_SERVER=smtp.gmail.com\n", encoding="utf-8")
    with pytest.raises(ValueError, match="EMAIL_PASSWORD"):
        send_email.read_config(file)


def test_build_message_with_attachment(tmp_path):
    report = tmp_path / "report.html"
    report.write_text("<h1>Hello</h1>", encoding="utf-8")
    message = send_email.build_message(CONFIG, "Subject", "<p>body</p>",
                                       [("report_x.html", report)])
    assert message["To"] == "boss@example.com"
    attachments = list(message.iter_attachments())
    assert [a.get_filename() for a in attachments] == ["report_x.html"]


def test_send_by_email_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "RESULTS_FOLDER", tmp_path)
    monkeypatch.setattr(send_email, "read_config", lambda: CONFIG)
    monkeypatch.setattr(send_email.smtplib, "SMTP", FakeServer)
    FakeServer.sent.clear()

    broken = tmp_path / "broken.csv"
    results = [(SAMPLE_CSV, main.process_file(SAMPLE_CSV, "€")), (broken, None)]
    main.send_by_email(results, "€")

    data, message = FakeServer.sent[0]
    assert data == {"server": "smtp.example.com", "port": 587, "encrypted": True,
                    "login": ("me@example.com", "secret")}
    assert "1 with errors" in message["Subject"]
    body = message.get_body(preferencelist=("html",)).get_content()
    assert "1,375.99 €" in body
    assert "broken.csv" in body and "Couldn't be processed" in body
    assert [a.get_filename() for a in message.iter_attachments()] == ["report_sample_sales.html"]
