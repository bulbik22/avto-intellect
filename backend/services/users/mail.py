import os
import smtplib
import ssl
from email.message import EmailMessage


def send_code(email, purpose, code):
    subject = {
        "confirm": "Подтверждение регистрации",
        "reset": "Восстановление пароля",
    }[purpose]
    message = EmailMessage()
    message["From"] = os.getenv("SMTP_FROM", "no-reply@avto-intellect.local")
    message["To"] = email
    message["Subject"] = f"Авто-Интеллект — {subject}"
    message.set_content(f"{subject}\n\nВаш код: {code}\nСрок действия — 10 минут.")

    host = os.getenv("SMTP_HOST", "127.0.0.1")
    security = os.getenv("SMTP_SECURITY", "none")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    if security not in ("none", "starttls", "ssl"):
        raise ValueError("Invalid SMTP_SECURITY")
    if bool(username) != bool(password) or (username and security == "none"):
        raise ValueError("SMTP credentials require both fields and TLS")

    port = int(os.getenv("SMTP_PORT", "1025"))
    if security == "ssl":
        client = smtplib.SMTP_SSL(host, port, timeout=8, context=ssl.create_default_context())
    else:
        client = smtplib.SMTP(host, port, timeout=8)
    with client:
        if security == "starttls":
            client.starttls(context=ssl.create_default_context())
        if username:
            client.login(username, password)
        client.send_message(message)
