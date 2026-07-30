"""
NexAlfa Conversation Store
SQLite-backed full conversation history — every message, every channel, searchable.
Inspired by OpenClaw Dev Mode's WhatsApp history logger.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

import aiosqlite

from agent.config.settings import get_settings

logger = logging.getLogger("nex.memory.conversation")

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    channel TEXT,
    channel_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    thinking TEXT,
    tool_calls TEXT,
    metadata TEXT DEFAULT '{}',
    timestamp REAL NOT NULL,
    created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_channel ON conversations(channel, channel_id);
CREATE INDEX IF NOT EXISTS idx_conv_timestamp ON conversations(timestamp);
CREATE INDEX IF NOT EXISTS idx_conv_role ON conversations(role);

CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
    content, tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    importance REAL DEFAULT 0.5,
    source_session TEXT,
    metadata TEXT DEFAULT '{}',
    created_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_mem_category ON memories(category);
CREATE INDEX IF NOT EXISTS idx_mem_importance ON memories(importance DESC);

CREATE TABLE IF NOT EXISTS user_facts (
    id TEXT PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    source TEXT,
    created_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_uf_key ON user_facts(key);
"""


class ConversationStore:
    """Persists all conversations to SQLite for full history + search."""

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or get_settings().db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Open DB and create tables."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(CREATE_TABLES)
        await self._db.commit()
        logger.info(f"Conversation store initialized: {self._db_path}")

    async def close(self):
        if self._db:
            await self._db.close()

    async def save_message(
        self,
        message_id: str,
        session_id: str,
        role: str,
        content: str,
        channel: Optional[str] = None,
        channel_id: Optional[str] = None,
        thinking: Optional[str] = None,
        tool_calls: Optional[list] = None,
        metadata: Optional[dict] = None,
        timestamp: Optional[float] = None,
    ):
        """Save a message to the conversation store."""
        ts = timestamp or time.time()
        await self._db.execute(
            """INSERT OR REPLACE INTO conversations
            (id, session_id, channel, channel_id, role, content, thinking, tool_calls, metadata, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                message_id,
                session_id,
                channel,
                channel_id,
                role,
                content,
                thinking,
                json.dumps(tool_calls) if tool_calls else None,
                json.dumps(metadata or {}),
                ts,
            ),
        )
        # Update FTS index
        await self._db.execute(
            "INSERT INTO conversations_fts(rowid, content) VALUES (last_insert_rowid(), ?)",
            (content,),
        )
        await self._db.commit()

    async def search_conversations(
        self, query: str, limit: int = 20, channel: Optional[str] = None
    ) -> list[dict]:
        """Full-text search across all conversations."""
        if channel:
            cursor = await self._db.execute(
                """SELECT c.* FROM conversations c
                JOIN conversations_fts f ON c.rowid = f.rowid
                WHERE conversations_fts MATCH ? AND c.channel = ?
                ORDER BY c.timestamp DESC LIMIT ?""",
                (query, channel, limit),
            )
        else:
            cursor = await self._db.execute(
                """SELECT c.* FROM conversations c
                JOIN conversations_fts f ON c.rowid = f.rowid
                WHERE conversations_fts MATCH ?
                ORDER BY c.timestamp DESC LIMIT ?""",
                (query, limit),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_session_messages(
        self, session_id: str, limit: Optional[int] = None
    ) -> list[dict]:
        """Get all messages in a session."""
        sql = "SELECT * FROM conversations WHERE session_id = ? ORDER BY timestamp ASC"
        params = [session_id]
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        cursor = await self._db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_recent_messages(
        self, limit: int = 50, channel: Optional[str] = None
    ) -> list[dict]:
        """Get the most recent messages across all sessions."""
        if channel:
            cursor = await self._db.execute(
                "SELECT * FROM conversations WHERE channel = ? ORDER BY timestamp DESC LIMIT ?",
                (channel, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Memory entries ──────────────────────────────────────

    async def save_memory(
        self,
        memory_id: str,
        category: str,
        content: str,
        importance: float = 0.5,
        source_session: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """Save a memory entry."""
        now = time.time()
        await self._db.execute(
            """INSERT OR REPLACE INTO memories
            (id, category, content, importance, source_session, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (memory_id, category, content, importance, source_session, json.dumps(metadata or {}), now, now),
        )
        await self._db.commit()

    async def get_memories(
        self, category: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """Get memory entries."""
        if category:
            cursor = await self._db.execute(
                "SELECT * FROM memories WHERE category = ? ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (category, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM memories ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── User facts ──────────────────────────────────────────

    async def save_user_fact(
        self, key: str, value: str, confidence: float = 0.5, source: Optional[str] = None
    ):
        """Save or update a fact about the user."""
        fact_id = f"uf_{key}"
        now = time.time()
        await self._db.execute(
            """INSERT OR REPLACE INTO user_facts (id, key, value, confidence, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (fact_id, key, value, confidence, source, now, now),
        )
        await self._db.commit()

    async def get_user_facts(self) -> list[dict]:
        """Get all known user facts."""
        cursor = await self._db.execute(
            "SELECT * FROM user_facts ORDER BY confidence DESC, updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_stats(self) -> dict:
        """Get store statistics."""
        msg_count = await self._db.execute("SELECT COUNT(*) FROM conversations")
        mem_count = await self._db.execute("SELECT COUNT(*) FROM memories")
        fact_count = await self._db.execute("SELECT COUNT(*) FROM user_facts")
        return {
            "total_messages": (await msg_count.fetchone())[0],
            "total_memories": (await mem_count.fetchone())[0],
            "total_user_facts": (await fact_count.fetchone())[0],
        }
