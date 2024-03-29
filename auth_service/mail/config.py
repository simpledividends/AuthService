# FIXME: Make pretty subjects, senders, text and html templates

from pydantic import BaseModel


class Sender(BaseModel):
    username: str
    name: str


BASE_SENDER = Sender(username="noreply", name="Simple Dividends")

REGISTRATION_EMAIL_SUBJECT = "Подтверждение регистрации"
REGISTRATION_EMAIL_SENDER = BASE_SENDER
REGISTRATION_EMAIL_TEXT_TEMPLATE = """
Ссылка для подтверждения email: {link}
"""
REGISTRATION_MAIL_HTML = "registration.html"

CHANGE_EMAIL_SUBJECT = "Подтверждение смены email"
CHANGE_EMAIL_SENDER = BASE_SENDER
CHANGE_EMAIL_TEXT_TEMPLATE = """
Ссылка для подтверждения email: {link}
"""
CHANGE_EMAIL_HTML = "change_email.html"

RESET_PASSWORD_SUBJECT = "Сброс пароля"  # nosec
RESET_PASSWORD_SENDER = BASE_SENDER  # nosec
RESET_PASSWORD_TEXT_TEMPLATE = (   # nosec
    """
        Ссылка для Сброса пароля: {link}
    """
)
RESET_PASSWORD_HTML = "reset_password.html"  # nosec
