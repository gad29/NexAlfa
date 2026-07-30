"""
NexAlfa Email Channel Adapter
SMTP for sending, IMAP for receiving. Supports rich HTML responses.
"""

from __future__ import annotations

import asyncio
import email
import logging
from email.mime.text import MIMEText
from typing import Optional

from gateway.channels.base import BaseChannel
from gateway.message import InboundMessage, OutboundMessage, MessageType
from agent.config.settings import get_settings

logger = logging.getLogger("nex.channels.email")


class EmailChannel(BaseChannel):
    name = "email"
    display_name = "Email"

    def __init__(self):
        super().__init__()
        self._polling_task = None

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(
            settings.channels.email_address
            and settings.channels.email_password
            and settings.channels.email_smtp_host
            and settings.channels.email_imap_host
        )

    async def start(self):
        if not self.is_configured():
            logger.warning("Email not configured — skipping")
            return

        # Start IMAP polling
        self._polling_task = asyncio.create_task(self._poll_inbox())
        self._running = True
        logger.info("✅ Email channel started")

    async def stop(self):
        if self._polling_task:
            self._polling_task.cancel()
        self._running = False

    async def send(self, message: OutboundMessage):
        """Send an email via SMTP."""
        settings = get_settings()
        try:
            import aiosmtplib

            msg = MIMEText(message.content, "plain", "utf-8")
            msg["From"] = settings.channels.email_address
            msg["To"] = message.channel_id  # channel_id = recipient email
            msg["Subject"] = f"Re: Nex"

            await aiosmtplib.send(
                msg,
                hostname=settings.channels.email_smtp_host,
                port=settings.channels.email_smtp_port,
                username=settings.channels.email_address,
                password=settings.channels.email_password,
                use_tls=True,
            )
        except Exception as e:
            logger.error(f"Email send failed: {e}")

    async def _poll_inbox(self):
        """Poll IMAP for new emails periodically."""
        settings = get_settings()
        while self._running:
            try:
                import aioimaplib

                imap = aioimaplib.IMAP4_SSL(
                    host=settings.channels.email_imap_host,
                    port=settings.channels.email_imap_port,
                )
                await imap.wait_hello_from_server()
                await imap.login(settings.channels.email_address, settings.channels.email_password)
                await imap.select("INBOX")

                # Search for unseen messages
                _, data = await imap.search("UNSEEN")
                if data and data[0]:
                    for msg_id in data[0].split():
                        _, msg_data = await imap.fetch(str(msg_id, "utf-8"), "(RFC822)")
                        if msg_data:
                            raw_email = email.message_from_bytes(msg_data[1])
                            sender = raw_email.get("From", "")
                            subject = raw_email.get("Subject", "")
                            body = ""

                            if raw_email.is_multipart():
                                for part in raw_email.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                        break
                            else:
                                body = raw_email.get_payload(decode=True).decode("utf-8", errors="replace")

                            inbound = InboundMessage(
                                channel="email",
                                channel_id=sender,
                                sender_id=sender,
                                sender_name=sender,
                                content=f"[Subject: {subject}]\n{body}",
                                type=MessageType.TEXT,
                            )

                            response = await self._dispatch(inbound)
                            if response:
                                await self.send(response)

                            # Mark as seen
                            await imap.store(str(msg_id, "utf-8"), "+FLAGS", "\\Seen")

                await imap.logout()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Email polling error: {e}")

            await asyncio.sleep(30)  # Poll every 30 seconds
