"""
NexAlfa Base Channel Adapter
All channel adapters inherit from this.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, Optional

from gateway.message import InboundMessage, OutboundMessage

logger = logging.getLogger("nex.channels")

# Type for the message handler callback
MessageHandler = Callable[[InboundMessage], Coroutine[Any, Any, Optional[OutboundMessage]]]


class BaseChannel(ABC):
    """Base class for all channel adapters."""

    name: str = ""
    display_name: str = ""

    def __init__(self):
        self._handler: Optional[MessageHandler] = None
        self._running = False

    def set_handler(self, handler: MessageHandler):
        """Set the callback for processing inbound messages."""
        self._handler = handler

    @abstractmethod
    async def start(self):
        """Start listening for messages."""
        ...

    @abstractmethod
    async def stop(self):
        """Stop the channel adapter."""
        ...

    @abstractmethod
    async def send(self, message: OutboundMessage):
        """Send a message through this channel."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if this channel has the required configuration."""
        ...

    @property
    def is_running(self) -> bool:
        return self._running

    async def _dispatch(self, message: InboundMessage) -> Optional[OutboundMessage]:
        """Dispatch an inbound message to the handler."""
        if self._handler:
            return await self._handler(message)
        logger.warning(f"No handler set for channel {self.name}")
        return None

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "configured": self.is_configured(),
            "running": self._running,
        }
