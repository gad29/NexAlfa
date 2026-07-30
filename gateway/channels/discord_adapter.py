"""
NexAlfa Discord Channel Adapter
Uses discord.py for full Discord bot support.
"""

from __future__ import annotations

import logging
from typing import Optional

from gateway.channels.base import BaseChannel
from gateway.message import InboundMessage, OutboundMessage, MessageType
from agent.config.settings import get_settings

logger = logging.getLogger("nex.channels.discord")


class DiscordChannel(BaseChannel):
    name = "discord"
    display_name = "Discord"

    def __init__(self):
        super().__init__()
        self._client = None

    def is_configured(self) -> bool:
        return bool(get_settings().channels.discord_bot_token)

    async def start(self):
        if not self.is_configured():
            logger.warning("Discord not configured — skipping")
            return

        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        settings = get_settings()

        @self._client.event
        async def on_ready():
            logger.info(f"✅ Discord connected as {self._client.user}")

        @self._client.event
        async def on_message(msg):
            if msg.author == self._client.user:
                return
            # Only respond to DMs or when mentioned
            if not isinstance(msg.channel, discord.DMChannel) and self._client.user not in msg.mentions:
                return

            content = msg.content.replace(f"<@{self._client.user.id}>", "").strip()
            inbound = InboundMessage(
                channel="discord",
                channel_id=str(msg.channel.id),
                sender_id=str(msg.author.id),
                sender_name=str(msg.author),
                content=content,
                type=MessageType.TEXT,
                raw=msg,
            )
            response = await self._dispatch(inbound)
            if response:
                text = response.format_with_thinking(settings.dev_mode.show_thinking)
                # Discord 2000 char limit
                for i in range(0, len(text), 1900):
                    await msg.channel.send(text[i:i + 1900])

        import asyncio
        asyncio.create_task(self._client.start(settings.channels.discord_bot_token))
        self._running = True

    async def stop(self):
        if self._client:
            await self._client.close()
        self._running = False

    async def send(self, message: OutboundMessage):
        if not self._client:
            return
        channel = self._client.get_channel(int(message.channel_id))
        if channel:
            text = message.format_with_thinking(get_settings().dev_mode.show_thinking)
            await channel.send(text[:1900])

    def is_configured(self) -> bool:
        return bool(get_settings().channels.discord_bot_token)
