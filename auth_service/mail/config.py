# FIXME: Make pretty subjects, senders, text and html templates

REGISTRATION_EMAIL_SUBJECT = "Подтверждение регистрации"
REGISTRATION_EMAIL_SENDER = "noreply@{domain}"
REGISTRATION_EMAIL_TEXT_TEMPLATE = """
Ссылка для подтверждения email: {link}
"""
REGISTRATION_MAIL_HTML = "registration.html"

CHANGE_EMAIL_SUBJECT = "Подтверждение смены email"
CHANGE_EMAIL_SENDER = "noreply@{domain}"
CHANGE_EMAIL_TEXT_TEMPLATE = """
Ссылка для подтверждения email: {link}
"""
CHANGE_EMAIL_HTML = "change_email.html"

RESET_PASSWORD_SUBJECT = "Сброс пароля"
RESET_PASSWORD_SENDER = "noreply@{domain}"
RESET_PASSWORD_TEXT_TEMPLATE = """
Ссылка для Сброса пароля: {link}
"""
RESET_PASSWORD_HTML = "reset_password.html"
