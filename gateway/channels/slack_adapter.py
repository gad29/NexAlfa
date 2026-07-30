"""
NexAlfa Slack Channel Adapter
Uses slack-sdk with Socket Mode (no public URL needed).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from gateway.channels.base import BaseChannel
from gateway.message import InboundMessage, OutboundMessage, MessageType
from agent.config.settings import get_settings

logger = logging.getLogger("nex.channels.slack")


class SlackChannel(BaseChannel):
    name = "slack"
    display_name = "Slack"

    def __init__(self):
        super().__init__()
        self._client = None
        self._socket_client = None

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.channels.slack_bot_token and settings.channels.slack_app_token)

    async def start(self):
        if not self.is_configured():
            logger.warning("Slack not configured — skipping")
            return

        from slack_sdk.web.async_client import AsyncWebClient
        from slack_sdk.socket_mode.aiohttp import SocketModeClient
        from slack_sdk.socket_mode.request import SocketModeRequest
        from slack_sdk.socket_mode.response import SocketModeResponse

        settings = get_settings()
        self._client = AsyncWebClient(token=settings.channels.slack_bot_token)
        self._socket_client = SocketModeClient(
            app_token=settings.channels.slack_app_token,
            web_client=self._client,
        )

        async def handle_event(client: SocketModeClient, req: SocketModeRequest):
            if req.type == "events_api":
                event = req.payload.get("event", {})
                if event.get("type") == "message" and not event.get("bot_id"):
                    inbound = InboundMessage(
                        channel="slack",
                        channel_id=event.get("channel", ""),
                        sender_id=event.get("user", ""),
                        sender_name=event.get("user", ""),
                        content=event.get("text", ""),
                        type=MessageType.TEXT,
                        raw=event,
                    )
                    response = await self._dispatch(inbound)
                    if response:
                        await self._client.chat_postMessage(
                            channel=inbound.channel_id,
                            text=response.format_with_thinking(settings.dev_mode.show_thinking),
                        )
                await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))

        self._socket_client.socket_mode_request_listeners.append(handle_event)
        asyncio.create_task(self._socket_client.connect())
        self._running = True
        logger.info("✅ Slack channel started (Socket Mode)")

    async def stop(self):
        if self._socket_client:
            await self._socket_client.close()
        self._running = False

    async def send(self, message: OutboundMessage):
        if self._client:
            await self._client.chat_postMessage(
                channel=message.channel_id,
                text=message.format_with_thinking(get_settings().dev_mode.show_thinking),
            )
