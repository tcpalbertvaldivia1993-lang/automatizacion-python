"""Sending the reports by email (SMTP).

The settings (server, user, password and recipient) are read from the project's
.env file, which is NOT uploaded to GitHub. See .env.example.
They can also be given as environment variables, which take priority over .env.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent / ".env"
KEYS = ["SMTP_SERVER", "SMTP_PORT", "EMAIL_USER", "EMAIL_PASSWORD", "EMAIL_TO"]


def read_config(path=CONFIG_FILE):
    """Reads the KEY=value lines of .env and checks that none is missing."""
    config = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip().strip('"').strip("'")
    for key in KEYS:
        if os.environ.get(key):
            config[key] = os.environ[key]

    missing = [key for key in KEYS if not config.get(key)]
    if missing:
        raise ValueError(f"Missing email settings in {path.name}: {', '.join(missing)}. "
                         "Copy .env.example to .env and fill it in.")
    return config


def build_message(config, subject, html, attachments, images=()):
    """Creates the email: HTML body and the reports as attached files.

    attachments is a list of (name the recipient will see, file path).
    images is a list of (identifier, path of a PNG) shown inside the body: in the
    HTML they go as <img src="cid:identifier">. Gmail blocks base64 images, but it
    does show these, which travel as parts of the message.
    """
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["EMAIL_USER"]
    message["To"] = config["EMAIL_TO"]  # several recipients: separated by commas
    # Plain text for email programs that don't show HTML.
    message.set_content("Automatically generated sales summary. "
                        "The full reports are attached: open them with your browser.")
    message.add_alternative(html, subtype="html")
    html_part = message.get_body(preferencelist=("html",))
    for identifier, path in images:
        html_part.add_related(path.read_bytes(), maintype="image", subtype="png",
                              cid=f"<{identifier}>")
    for name, path in attachments:
        message.add_attachment(path.read_bytes(), maintype="text", subtype="html", filename=name)
    return message


def send(config, message):
    """Sends the message over an encrypted connection (STARTTLS), as Gmail and Outlook require."""
    context = ssl.create_default_context()
    with smtplib.SMTP(config["SMTP_SERVER"], int(config["SMTP_PORT"]), timeout=30) as server:
        server.starttls(context=context)
        server.login(config["EMAIL_USER"], config["EMAIL_PASSWORD"])
        server.send_message(message)
