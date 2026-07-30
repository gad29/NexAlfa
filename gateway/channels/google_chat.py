"""
NexAlfa Google Chat Channel Adapter
Uses Google Chat API via service account or OAuth credentials.
Requires Google Workspace account.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import httpx

from gateway.channels.base import BaseChannel
from gateway.message import InboundMessage, OutboundMessage, MessageType
from agent.config.settings import get_settings

logger = logging.getLogger("nex.channels.google_chat")


class GoogleChatChannel(BaseChannel):
    name = "google_chat"
    display_name = "Google Chat"

    def __init__(self):
        super().__init__()
        self._credentials = None
        self._http_client: Optional[httpx.AsyncClient] = None

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.channels.google_chat_credentials_file)

    async def start(self):
        if not self.is_configured():
            logger.warning("Google Chat not configured — skipping")
            return

        settings = get_settings()
        try:
            # Load service account credentials
            creds_path = settings.channels.google_chat_credentials_file
            with open(creds_path, "r") as f:
                self._credentials = json.load(f)

            self._http_client = httpx.AsyncClient(
                base_url="https://chat.googleapis.com/v1",
                timeout=15,
            )

            self._running = True
            logger.info("✅ Google Chat channel started (webhook mode)")
        except Exception as e:
            logger.error(f"Google Chat setup failed: {e}")

    async def stop(self):
        if self._http_client:
            await self._http_client.aclose()
        self._running = False

    async def send(self, message: OutboundMessage):
        """Send a message to Google Chat space."""
        if not self._http_client:
            return

        settings = get_settings()
        text = message.format_with_thinking(settings.dev_mode.show_thinking)

        try:
            # Get access token
            access_token = await self._get_access_token()
            if not access_token:
                logger.error("Failed to get Google Chat access token")
                return

            await self._http_client.post(
                f"/spaces/{message.channel_id}/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"text": text[:4096]},
            )
        except Exception as e:
            logger.error(f"Google Chat send failed: {e}")

    async def _get_access_token(self) -> Optional[str]:
        """Get OAuth2 access token from service account."""
        try:
            import jwt
            import time

            now = int(time.time())
            payload = {
                "iss": self._credentials.get("client_email"),
                "scope": "https://www.googleapis.com/auth/chat.bot",
                "aud": "https://oauth2.googleapis.com/token",
                "iat": now,
                "exp": now + 3600,
            }

            signed_jwt = jwt.encode(
                payload,
                self._credentials.get("private_key"),
                algorithm="RS256",
            )

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": signed_jwt,
                    },
                )
                return resp.json().get("access_token")
        except ImportError:
            logger.error("PyJWT not installed. Install with: pip install pyjwt")
            return None
        except Exception as e:
            logger.error(f"Token error: {e}")
            return None

    async def handle_webhook(self, data: dict) -> Optional[InboundMessage]:
        """Handle incoming Google Chat event (bot message, etc.)."""
        try:
            event_type = data.get("type")

            if event_type == "MESSAGE":
                msg = data.get("message", {})
                sender = data.get("user", {})
                space = data.get("space", {})

                return InboundMessage(
                    channel="google_chat",
                    channel_id=space.get("name", ""),
                    sender_id=sender.get("name", ""),
                    sender_name=sender.get("displayName", ""),
                    content=msg.get("text", ""),
                    type=MessageType.TEXT,
                    raw=data,
                )
            return None
        except Exception as e:
            logger.error(f"Google Chat webhook parse error: {e}")
            return None
