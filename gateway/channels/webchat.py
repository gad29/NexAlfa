"""
NexAlfa WebChat Channel Adapter
Built-in WebSocket-based chat — powers the web app and serves as the reference adapter.
"""

from __future__ import annotations

import logging
from typing import Optional

from gateway.channels.base import BaseChannel
from gateway.message import InboundMessage, OutboundMessage, MessageType

logger = logging.getLogger("nex.channels.webchat")


class WebChatChannel(BaseChannel):
    """WebSocket-based chat channel. Messages routed by the gateway's Socket.IO server."""

    name = "webchat"
    display_name = "WebChat"

    def __init__(self):
        super().__init__()
        # WebChat doesn't need its own listener — the gateway Socket.IO handles it
        self._connected_clients: dict[str, dict] = {}

    async def start(self):
        self._running = True
        logger.info("WebChat channel ready (handled by gateway Socket.IO)")

    async def stop(self):
        self._running = False

    async def send(self, message: OutboundMessage):
        """WebChat sends are handled by the gateway's Socket.IO emit."""
        # This is a no-op — the gateway emits directly to the client
        pass

    def is_configured(self) -> bool:
        return True  # Always configured — it's built-in

    def register_client(self, sid: str, metadata: dict = None):
        """Register a connected WebChat client."""
        self._connected_clients[sid] = metadata or {}
        logger.info(f"WebChat client connected: {sid}")

    def unregister_client(self, sid: str):
        """Unregister a disconnected client."""
        self._connected_clients.pop(sid, None)
        logger.info(f"WebChat client disconnected: {sid}")

    @property
    def connected_count(self) -> int:
        return len(self._connected_clients)
