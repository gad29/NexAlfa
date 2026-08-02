"""
NexAlfa WhatsApp Channel Adapter
Supports two modes:
1. Bridge mode (default) — uses whatsapp-web.js via a Node.js subprocess (like OpenClaw)
2. Cloud API mode — direct Meta WhatsApp Business API
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from gateway.channels.base import BaseChannel
from gateway.message import InboundMessage, OutboundMessage, MessageType
from agent.config.settings import get_settings

logger = logging.getLogger("nex.channels.whatsapp")


class WhatsAppChannel(BaseChannel):
    name = "whatsapp"
    display_name = "WhatsApp"

    def __init__(self):
        super().__init__()
        self._mode = "bridge"  # or "cloud_api"
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_config(self):
        from gateway.config_store import get_config_store
        store = get_config_store()
        config = store.get_channel_config("whatsapp")
        mode = config.get("mode")
        if not mode:
            # Fallback to settings.py
            settings = get_settings()
            mode = "bridge" if settings.channels.whatsapp_bridge else "cloud_api"
        return mode, config

    def is_configured(self) -> bool:
        mode, config = self._get_config()
        if mode == "bridge":
            # Bridge mode: only configured if explicitly enabled via UI (mode in config)
            # or if a session file exists from a previous QR pairing
            import os
            session_exists = os.path.exists("/app/storage/whatsapp-session")
            explicitly_enabled = "mode" in config and config["mode"] == "bridge"
            return session_exists or explicitly_enabled
        
        settings = get_settings()
        token = config.get("access_token") or settings.channels.whatsapp_access_token
        phone_id = config.get("phone_number_id") or settings.channels.whatsapp_phone_number_id
        return bool(token and phone_id)

    async def start(self):
        mode, config = self._get_config()
        settings = get_settings()
        if mode == "bridge":
            self._mode = "bridge"
            logger.info("WhatsApp starting in bridge mode (whatsapp-web.js)")
            # Bridge mode: the gateway webhook endpoint handles incoming messages
            # The actual bridge runs as a separate process
        else:
            self._mode = "cloud_api"
            token = config.get("access_token") or settings.channels.whatsapp_access_token
            self._http_client = httpx.AsyncClient(
                base_url="https://graph.facebook.com/v21.0",
                headers={"Authorization": f"Bearer {token}"},
            )
            logger.info("WhatsApp starting in Cloud API mode")

        self._running = True
        logger.info(f"✅ WhatsApp channel started (mode: {self._mode})")

    async def stop(self):
        if self._http_client:
            await self._http_client.aclose()
        self._running = False

    async def send(self, message: OutboundMessage):
        """Send a message via WhatsApp."""
        settings = get_settings()
        text = message.format_with_thinking(settings.dev_mode.show_thinking)

        if self._mode == "cloud_api":
            await self._send_cloud_api(message.channel_id, text)
        else:
            await self._send_bridge(message.channel_id, text)

    async def _send_cloud_api(self, to: str, text: str):
        """Send via Meta WhatsApp Cloud API."""
        _, config = self._get_config()
        settings = get_settings()
        phone_id = config.get("phone_number_id") or settings.channels.whatsapp_phone_number_id
        try:
            response = await self._http_client.post(
                f"/{phone_id}/messages",
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": text[:4096]},
                },
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"WhatsApp Cloud API send failed: {e}")

    async def _send_bridge(self, to: str, text: str):
        """Send via bridge (HTTP to the bridge subprocess)."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "http://localhost:3001/send",  # Bridge process endpoint
                    json={"to": to, "message": text},
                    timeout=10,
                )
        except Exception as e:
            logger.error(f"WhatsApp bridge send failed: {e}")

    async def handle_webhook(self, data: dict) -> Optional[InboundMessage]:
        """Handle incoming webhook from WhatsApp (both modes)."""
        try:
            if self._mode == "cloud_api":
                return self._parse_cloud_api_webhook(data)
            else:
                return self._parse_bridge_webhook(data)
        except Exception as e:
            logger.error(f"WhatsApp webhook parse error: {e}")
            return None

    def _parse_cloud_api_webhook(self, data: dict) -> Optional[InboundMessage]:
        """Parse Meta Cloud API webhook payload."""
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return None

        msg = messages[0]
        if msg.get("type") != "text":
            return None

        contact = value.get("contacts", [{}])[0]
        return InboundMessage(
            channel="whatsapp",
            channel_id=msg["from"],
            sender_id=msg["from"],
            sender_name=contact.get("profile", {}).get("name", ""),
            content=msg["text"]["body"],
            type=MessageType.TEXT,
            raw=data,
        )

    def _parse_bridge_webhook(self, data: dict) -> Optional[InboundMessage]:
        """Parse bridge webhook payload."""
        return InboundMessage(
            channel="whatsapp",
            channel_id=data.get("from", ""),
            sender_id=data.get("from", ""),
            sender_name=data.get("sender_name", ""),
            content=data.get("message", ""),
            type=MessageType.TEXT,
            raw=data,
        )
