import asyncio
from email.message import EmailMessage
from typing import Iterable
import aiosmtplib

from .settings import settings

class SMTPPool:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._client: aiosmtplib.SMTP | None = None

    async def _ensure_client(self) -> aiosmtplib.SMTP:
        if self._client is None or not getattr(self._client, "is_connected", False):
            self._client = aiosmtplib.SMTP(
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                start_tls=settings.SMTP_STARTTLS,
                timeout=settings.TIMEOUT,
            )
            await self._client.connect()
            if settings.SMTP_STARTTLS:
                await self._client.starttls()
            await self._client.login(settings.SMTP_USER, settings.SMTP_PASS)
        return self._client

    async def send(self, msg: EmailMessage):
        async with self._lock:
            client = await self._ensure_client()
            return await client.send_message(msg)

pool = SMTPPool()


def make_from_header(domain: str | None) -> str:
    d = (domain or settings.DEFAULT_DOMAIN).strip().lower()
    display = settings.DISPLAY_NAMES.get(d, "mailer")
    addr = f"{settings.FROM_LOCALPART}@{d}"
    return f'{display} <{addr}>'


def build_message(
    to: Iterable[str],
    subject: str,
    text: str | None,
    html: str | None,
    headers: dict[str, str] | None,
    from_domain: str | None,             # ← nuevo parámetro
) -> EmailMessage:
    if not text and not html:
        text = "(sin contenido)"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = make_from_header(from_domain)
    msg["To"] = ", ".join(to)

    if headers:
        for k, v in headers.items():
            kl = k.lower()
            if kl not in {"from", "to", "subject"}:
                msg[k] = v

    if text:
        msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    if "List-Unsubscribe" not in msg:
        msg["List-Unsubscribe"] = "<mailto:unsubscribe@send.horus.com>"

    return msg


async def send_with_retries(msg: EmailMessage, retries: int | None = None):
    retries = retries or settings.RETRIES
    delay = 0.5
    for attempt in range(retries):
        try:
            return await pool.send(msg)
        except Exception:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 8.0)
