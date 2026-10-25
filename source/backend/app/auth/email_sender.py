"""Отправка писем через SMTP (Mailpit в dev)."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

logger = logging.getLogger("app.auth.email")


@dataclass(frozen=True, slots=True)
class OutboundEmail:
    to_address: str
    subject: str
    text_body: str


class EmailSender(Protocol):
    def send(self, message: OutboundEmail) -> None: ...


class SmtpEmailSender:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        from_address: str,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._from_address = from_address
        self._username = username
        self._password = password
        self._use_tls = use_tls

    def send(self, message: OutboundEmail) -> None:
        email = EmailMessage()
        email["From"] = self._from_address
        email["To"] = message.to_address
        email["Subject"] = message.subject
        email.set_content(message.text_body)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
                if self._use_tls:
                    smtp.starttls()
                if self._username and self._password:
                    smtp.login(self._username, self._password)
                smtp.send_message(email)
        except OSError:
            logger.exception("smtp_send_failed to_domain=%s", _email_domain(message.to_address))
            raise


class LoggingEmailSender:
    """Запасной отправитель для тестов: пишет в лог без SMTP."""

    def send(self, message: OutboundEmail) -> None:
        logger.info(
            "email_queued to_domain=%s subject=%s",
            _email_domain(message.to_address),
            message.subject,
        )


def _email_domain(address: str) -> str:
    if "@" not in address:
        return "unknown"
    return address.rsplit("@", 1)[-1].lower()


def build_verify_email(to_address: str, *, verify_url: str) -> OutboundEmail:
    return OutboundEmail(
        to_address=to_address,
        subject="Подтверждение email - Java Blueprints",
        text_body=(
            "Подтвердите адрес электронной почты для Java Blueprints.\n\n"
            f"Ссылка (действует ограниченное время):\n{verify_url}\n\n"
            "Если вы не регистрировались, проигнорируйте это письмо.\n"
        ),
    )


def build_password_reset_email(to_address: str, *, reset_url: str) -> OutboundEmail:
    return OutboundEmail(
        to_address=to_address,
        subject="Сброс пароля - Java Blueprints",
        text_body=(
            "Запрошен сброс пароля для Java Blueprints.\n\n"
            f"Ссылка (короткий срок жизни):\n{reset_url}\n\n"
            "Если вы не запрашивали сброс, проигнорируйте это письмо.\n"
        ),
    )
