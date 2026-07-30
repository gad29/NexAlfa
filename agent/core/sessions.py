"""
NexAlfa Session Manager
Multi-session support — each channel conversation maps to an isolated session.
Inspired by OpenClaw's session model.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

logger = logging.getLogger("nex.sessions")


@dataclass
class Message:
    """A single message in a session."""

    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    thinking: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    channel: Optional[str] = None  # which channel this came from
    metadata: dict = field(default_factory=dict)

    def to_llm_message(self) -> dict:
        """Convert to LLM-compatible message dict."""
        msg = {"role": self.role, "content": self.content}
        if self.name:
            msg["name"] = self.name
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        return msg


@dataclass
class Session:
    """An isolated conversation session."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    messages: list[Message] = field(default_factory=list)
    channel: Optional[str] = None
    channel_id: Optional[str] = None  # channel-specific identifier (chat_id, etc.)
    agent_name: str = "default"
    model: Optional[str] = None  # override model for this session
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)
    is_active: bool = True
    summary: str = ""  # Rolling summary of older messages

    # Context window settings
    MAX_WINDOW_MESSAGES: int = 20  # Max recent messages to send to LLM
    SUMMARIZE_THRESHOLD: int = 30  # Trigger summarization when > this many messages

    def add_message(self, role: str, content: str, **kwargs) -> Message:
        """Add a message to the session."""
        msg = Message(role=role, content=content, channel=self.channel, **kwargs)
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def get_llm_messages(self) -> list[dict]:
        """Get all messages in LLM-compatible format."""
        return [m.to_llm_message() for m in self.messages]

    def get_windowed_messages(self, max_messages: int = None) -> list[dict]:
        """Get messages for LLM with sliding window.
        Returns: system prompt + summary of old context + last N messages.
        This prevents context from growing unbounded."""
        max_msg = max_messages or self.MAX_WINDOW_MESSAGES
        non_system = [m for m in self.messages if m.role != "system"]

        # If within window, return all
        if len(non_system) <= max_msg:
            return [m.to_llm_message() for m in self.messages]

        # Build windowed context
        result = []

        # 1. Keep system messages
        for m in self.messages:
            if m.role == "system":
                result.append(m.to_llm_message())

        # 2. Inject summary of older messages if available
        if self.summary:
            result.append({
                "role": "system",
                "content": f"[Conversation summary so far]\n{self.summary}",
            })

        # 3. Keep last N messages (preserving tool call chains)
        recent = non_system[-max_msg:]
        for m in recent:
            result.append(m.to_llm_message())

        return result

    def get_messages_for_summarization(self) -> list[dict]:
        """Get the older messages that should be summarized."""
        non_system = [m for m in self.messages if m.role != "system"]
        if len(non_system) <= self.MAX_WINDOW_MESSAGES:
            return []
        # Return messages outside the window (the old ones)
        overflow = non_system[:-self.MAX_WINDOW_MESSAGES]
        return [{"role": m.role, "content": m.content[:300]} for m in overflow
                if m.role in ("user", "assistant") and m.content.strip()]

    def needs_summarization(self) -> bool:
        """Check if conversation is long enough to need summarization."""
        non_system = [m for m in self.messages if m.role != "system"]
        return len(non_system) > self.SUMMARIZE_THRESHOLD

    def apply_summary_and_compact(self, summary: str):
        """Apply a new summary and remove old messages from the window."""
        self.summary = summary
        # Keep system messages + last N messages
        system_msgs = [m for m in self.messages if m.role == "system"]
        non_system = [m for m in self.messages if m.role != "system"]
        if len(non_system) > self.MAX_WINDOW_MESSAGES:
            self.messages = system_msgs + non_system[-self.MAX_WINDOW_MESSAGES:]
        self.updated_at = time.time()
        logger.info(f"Session {self.id}: compacted to {len(self.messages)} messages with summary")

    def get_last_n_messages(self, n: int) -> list[Message]:
        """Get the last N messages."""
        return self.messages[-n:]

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def token_estimate(self) -> int:
        """Rough token estimate (4 chars ≈ 1 token)."""
        total_chars = sum(len(m.content) for m in self.messages)
        return total_chars // 4

    def compact(self, keep_last: int = 10) -> list[Message]:
        """Compact the session — keep system messages + last N messages.
        Returns the removed messages for archival."""
        system_msgs = [m for m in self.messages if m.role == "system"]
        non_system = [m for m in self.messages if m.role != "system"]

        if len(non_system) <= keep_last:
            return []

        removed = non_system[:-keep_last]
        kept = non_system[-keep_last:]
        self.messages = system_msgs + kept
        self.updated_at = time.time()
        return removed


class SessionManager:
    """Manages multiple conversation sessions."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._channel_map: dict[str, str] = {}  # channel_key -> session_id

    def create_session(
        self,
        channel: Optional[str] = None,
        channel_id: Optional[str] = None,
        name: str = "",
        agent_name: str = "default",
    ) -> Session:
        """Create a new session."""
        session = Session(
            channel=channel,
            channel_id=channel_id,
            name=name or f"Session {len(self._sessions) + 1}",
            agent_name=agent_name,
        )
        self._sessions[session.id] = session

        # Map channel identifier to session
        if channel and channel_id:
            key = f"{channel}:{channel_id}"
            self._channel_map[key] = session.id

        logger.info(f"Session created: {session.id} [{channel}:{channel_id}]")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_or_create_for_channel(
        self, channel: str, channel_id: str, agent_name: str = "default"
    ) -> Session:
        """Get existing session for a channel or create a new one."""
        key = f"{channel}:{channel_id}"
        if key in self._channel_map:
            session = self._sessions.get(self._channel_map[key])
            if session and session.is_active:
                return session

        return self.create_session(
            channel=channel,
            channel_id=channel_id,
            agent_name=agent_name,
        )

    def reset_session(self, session_id: str) -> Optional[Session]:
        """Reset a session (clear messages, keep metadata)."""
        session = self._sessions.get(session_id)
        if session:
            session.messages.clear()
            session.updated_at = time.time()
            logger.info(f"Session reset: {session_id}")
        return session

    def list_sessions(self, active_only: bool = True) -> list[Session]:
        """List all sessions."""
        sessions = list(self._sessions.values())
        if active_only:
            sessions = [s for s in sessions if s.is_active]
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    def get_session_history(self, session_id: str, last_n: Optional[int] = None) -> list[Message]:
        """Get message history for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        if last_n:
            return session.get_last_n_messages(last_n)
        return session.messages

    def close_session(self, session_id: str):
        """Mark a session as inactive."""
        session = self._sessions.get(session_id)
        if session:
            session.is_active = False
            logger.info(f"Session closed: {session_id}")

    def get_stats(self) -> dict:
        """Get session statistics."""
        active = [s for s in self._sessions.values() if s.is_active]
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": len(active),
            "total_messages": sum(s.message_count for s in self._sessions.values()),
            "channels": list({s.channel for s in active if s.channel}),
        }
