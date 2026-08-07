"""Отправка писем пользователям.

Сервис нарочно не знает ничего про регистрацию: это общий канал доставки,
через который позже пойдут и уведомления (события по облигациям и т.п.).
Провайдер — любой SMTP-сервер, настраивается через окружение (EmailSettings).
"""
import logging
from email.message import EmailMessage

import aiosmtplib

from src.config import email_settings
from src.logging_setup import integration_call

logger = logging.getLogger(__name__)

# Имя интеграции в логах: пишется в logs/email.log.
SERVICE = "email"


class EmailSendError(Exception):
    """Не удалось отправить письмо."""


class EmailService:

    def __init__(self, settings=email_settings):
        self.settings = settings

    async def send(self, to: str, subject: str, body: str) -> None:
        with integration_call(SERVICE, "send", to=to, subject=subject) as call:
            if not self.settings.SMTP_HOST:
                call.skipped("smtp_not_configured")
                # SMTP не настроен — режим разработки: письмо уходит в лог целиком,
                # иначе локально не получить код подтверждения.
                logger.warning("SMTP не настроен, письмо не отправлено. To=%s Body:\n%s", to, body)
                return

            message = EmailMessage()
            message["From"] = self.settings.EMAIL_FROM
            message["To"] = to
            message["Subject"] = subject
            message.set_content(body)

            # 465 — implicit TLS, остальные порты (обычно 587) — STARTTLS.
            use_tls = self.settings.SMTP_PORT == 465

            call.add(host=self.settings.SMTP_HOST, port=self.settings.SMTP_PORT)
            call.detail(sender=self.settings.EMAIL_FROM, body=body)

            try:
                await aiosmtplib.send(
                    message,
                    hostname=self.settings.SMTP_HOST,
                    port=self.settings.SMTP_PORT,
                    username=self.settings.SMTP_USER,
                    password=self.settings.SMTP_PASSWORD,
                    use_tls=use_tls,
                    start_tls=not use_tls or None,
                )
            except Exception as error:
                raise EmailSendError(str(error)) from error
