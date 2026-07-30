"""
NexAlfa Telegram Channel Adapter
Uses python-telegram-bot for full Telegram Bot API support.
"""

from __future__ import annotations

import logging
from typing import Optional

from gateway.channels.base import BaseChannel
from gateway.message import InboundMessage, OutboundMessage, MessageType
from agent.config.settings import get_settings

logger = logging.getLogger("nex.channels.telegram")


class TelegramChannel(BaseChannel):
    name = "telegram"
    display_name = "Telegram"

    def __init__(self):
        super().__init__()
        self._app = None

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.channels.telegram_bot_token)

    async def start(self):
        if not self.is_configured():
            logger.warning("Telegram not configured — skipping")
            return

        from telegram.ext import ApplicationBuilder, MessageHandler as TGHandler, filters

        settings = get_settings()
        self._app = ApplicationBuilder().token(settings.channels.telegram_bot_token).build()

        # Handle all text messages
        async def handle_message(update, context):
            if not update.message or not update.message.text:
                return

            inbound = InboundMessage(
                channel="telegram",
                channel_id=str(update.effective_chat.id),
                sender_id=str(update.effective_user.id),
                sender_name=update.effective_user.full_name or "",
                content=update.message.text,
                type=MessageType.TEXT,
                raw=update,
            )

            response = await self._dispatch(inbound)
            if response:
                text = response.format_with_thinking(get_settings().dev_mode.show_thinking)
                # Split long messages (Telegram 4096 char limit)
                for i in range(0, len(text), 4000):
                    await update.message.reply_text(text[i:i + 4000])

        self._app.add_handler(TGHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        self._running = True
        logger.info("✅ Telegram channel started")

    async def stop(self):
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        self._running = False
        logger.info("Telegram channel stopped")

    async def send(self, message: OutboundMessage):
        if not self._app:
            return
        text = message.format_with_thinking(get_settings().dev_mode.show_thinking)
        await self._app.bot.send_message(
            chat_id=int(message.channel_id),
            text=text[:4000],
        )
