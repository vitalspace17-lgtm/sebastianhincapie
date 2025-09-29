from __future__ import annotations

import asyncio
from email.message import EmailMessage
from typing import Iterable
import aiosmtplib

from .settings import settings


class SMTPPool:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._client: aiosmtplib.SMTP | None = None

    async def _ensure_client(self) -> aiosmtplib.SMTP:
        if self._client is not None and getattr(self._client, "is_connected", False):
            return self._client

        timeout = getattr(settings, "SMTP_TIMEOUT", getattr(settings, "TIMEOUT", 60.0))
        use_ssl = bool(getattr(settings, "SMTP_SSL", False))            # ← TLS implícito (465)
        do_starttls = bool(getattr(settings, "SMTP_STARTTLS", False))   # ← STARTTLS (587)

        if use_ssl:
            # SMTPS (TLS implícito), típico puerto 465
            self._client = aiosmtplib.SMTP(
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                use_tls=True,
                timeout=timeout,
            )
            await self._client.connect()
        else:
            # Conexión en claro, con opción STARTTLS
            self._client = aiosmtplib.SMTP(
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                start_tls=False,
                timeout=timeout,
            )
            await self._client.connect()
            if do_starttls:
                await self._client.starttls()

        # Login solo si hay credenciales
        if getattr(settings, "SMTP_USER", ""):
            await self._client.login(settings.SMTP_USER, getattr(settings, "SMTP_PASS", ""))

        return self._client

    async def send(self, msg: EmailMessage):
        async with self._lock:
            client = await self._ensure_client()
            return await client.send_message(msg)


pool = SMTPPool()


def make_from_header(domain: str | None) -> str:
    d = (domain or getattr(settings, "DEFAULT_DOMAIN", "")).strip().lower()
    display = getattr(settings, "DISPLAY_NAMES", {}).get(d, getattr(settings, "FROM_NAME", "mailer"))
    local = getattr(settings, "FROM_LOCALPART", "mailer")
    addr = f"{local}@{d}" if d else getattr(settings, "FROM_EMAIL", "mailer@example.com")
    return f'{display} <{addr}>'


def build_message(
    to: Iterable[str],
    subject: str,
    text: str | None = None,
    html: str | None = None,
    headers: dict[str, str] | None = None,
    from_domain: str | None = None,
    body_text: str | None = None,
    body_html: str | None = None,
) -> EmailMessage:
    # Compat: aceptar body_text/body_html
    if body_text is not None and text is None:
        text = body_text
    if body_html is not None and html is None:
        html = body_html

    if not text and not html:
        text = "(sin contenido)"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = make_from_header(from_domain)
    msg["To"] = ", ".join(to)

    if headers:
        for k, v in headers.items():
            if k.lower() not in {"from", "to", "subject"}:
                msg[k] = v

    if text:
        msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    if "List-Unsubscribe" not in msg:
        msg["List-Unsubscribe"] = "<mailto:unsubscribe@send.horus.com>"

    return msg


async def send_with_retries(msg: EmailMessage, retries: int | None = None):
    retries = retries or getattr(settings, "RETRIES", 3)
    delay = 0.5
    for attempt in range(retries):
        try:
            return await pool.send(msg)
        except Exception:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 8.0)
