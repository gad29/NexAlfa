"""
NexAlfa Normalized Message Model
All channel adapters normalize their platform-specific messages into this model.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    COMMAND = "command"
    SYSTEM = "system"


@dataclass
class Attachment:
    """A file/media attachment."""
    type: str  # image, audio, video, file
    url: Optional[str] = None
    data: Optional[bytes] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    size: Optional[int] = None


@dataclass
class InboundMessage:
    """A message received from any channel — normalized."""
    id: str = field(default_factory=lambda: str(uuid4()))
    channel: str = ""  # telegram, discord, slack, whatsapp, google_chat, email, webchat
    channel_id: str = ""  # channel-specific chat/room identifier
    sender_id: str = ""  # channel-specific sender identifier
    sender_name: str = ""
    content: str = ""
    type: MessageType = MessageType.TEXT
    attachments: list[Attachment] = field(default_factory=list)
    reply_to: Optional[str] = None  # ID of message being replied to
    timestamp: float = field(default_factory=time.time)
    raw: Any = None  # original platform message

    @property
    def is_command(self) -> bool:
        return self.content.startswith("/")


@dataclass
class OutboundMessage:
    """A message to send to a channel — normalized."""
    channel: str = ""
    channel_id: str = ""
    content: str = ""
    thinking: Optional[str] = None  # 💭 reasoning (dev-mode)
    reply_to: Optional[str] = None
    attachments: list[Attachment] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def format_with_thinking(self, show_thinking: bool = True) -> str:
        """Format content with thinking prefix if enabled."""
        if self.thinking and show_thinking:
            return f"💭 Reasoning:\n{self.thinking}\n\n{self.content}"
        return self.content
