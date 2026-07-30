"""
NexAlfa Memory Manager — The Learning Loop
The core Hermes-inspired system: learn from every interaction, create memories,
nudge skill creation, and build the user model.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional
from uuid import uuid4

from agent.config.settings import get_settings
from agent.memory.conversation import ConversationStore
from agent.memory.user_model import UserModel
from agent.memory.vector_store import VectorStore
from agent.memory.graphify_backend import graphify_backend

logger = logging.getLogger("nex.memory.manager")

MEMORY_MD_TEMPLATE = """# Nex Memory
> Auto-maintained knowledge base. Facts, patterns, and decisions Nex has learned.

{entries}

---
*{count} memories · Last updated: {updated_at}*
"""

MEMORY_EXTRACTION_PROMPT = """Analyze this conversation between the user and Nex.
Extract important information worth remembering for future conversations.

Return a JSON array of memory objects:
- "content": what to remember (be specific and concise)
- "category": one of [fact, decision, preference, pattern, project, skill_candidate]
- "importance": 0.0-1.0 (1.0 = critical to remember)

Categories:
- fact: factual information mentioned
- decision: decisions made during the conversation
- preference: user preferences expressed
- pattern: recurring patterns or workflows
- project: project-related context
- skill_candidate: a novel solution that could become a reusable skill

Only extract genuinely useful memories. Return [] if the conversation was trivial.
Example: [{"content": "User prefers dark mode UIs with glassmorphism", "category": "preference", "importance": 0.7}]"""

SKILL_CANDIDATE_PROMPT = """This conversation contained a novel solution to a problem.
Create a reusable skill definition in SKILL.md format.

The skill should:
1. Have a clear, descriptive name
2. Describe when to use it
3. Include the step-by-step approach
4. Be general enough to reuse

Return the SKILL.md content as a markdown string."""


class MemoryManager:
    """
    The learning loop — Nex's self-improving brain.

    After each conversation turn:
    1. Persist messages to SQLite (full history)
    2. Index messages in ChromaDB (semantic search)
    3. Extract memories from significant conversations
    4. Update user model with new facts
    5. Identify skill candidates
    6. Persist MEMORY.md
    """

    def __init__(self):
        self.store = ConversationStore()
        self.vectors = VectorStore()
        self.user_model = UserModel()
        self._settings = get_settings()

    async def initialize(self):
        """Initialize all memory subsystems."""
        await self.store.initialize()
        await self.vectors.initialize()
        logger.info("Memory manager initialized — learning loop active")

    async def close(self):
        """Clean shutdown."""
        await self.store.close()

    async def record_message(
        self,
        session_id: str,
        role: str,
        content: str,
        channel: Optional[str] = None,
        channel_id: Optional[str] = None,
        thinking: Optional[str] = None,
        tool_calls: Optional[list] = None,
        metadata: Optional[dict] = None,
    ):
        """Record a single message — persists to SQLite + indexes in ChromaDB."""
        msg_id = str(uuid4())

        # 1. Save to SQLite
        await self.store.save_message(
            message_id=msg_id,
            session_id=session_id,
            role=role,
            content=content,
            channel=channel,
            channel_id=channel_id,
            thinking=thinking,
            tool_calls=tool_calls,
            metadata=metadata,
        )

        # 2. Index in ChromaDB for semantic search
        if content.strip() and role in ("user", "assistant"):
            self.vectors.add_conversation(
                doc_id=msg_id,
                content=content,
                metadata={
                    "session_id": session_id,
                    "role": role,
                    "channel": channel or "",
                    "timestamp": str(time.time()),
                },
            )

    async def search_past(self, query: str, n_results: int = 10) -> list[dict]:
        """Search past conversations semantically."""
        return self.vectors.search_conversations(query, n_results=n_results)

    async def search_memories(self, query: str, n_results: int = 10) -> list[dict]:
        """Search extracted memories semantically."""
        return self.vectors.search_memories(query, n_results=n_results)

    async def extract_memories(self, session_messages: list[dict]) -> list[dict]:
        """
        Extract memories from a conversation.
        Returns the extraction prompt + messages for the LLM to process.
        This is called by the agent after a conversation ends or periodically.
        """
        if len(session_messages) < 4:  # Skip trivial conversations
            return []

        # Build conversation text
        conv_text = "\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')}"
            for m in session_messages
            if m.get("content")
        )

        return [{
            "role": "system",
            "content": MEMORY_EXTRACTION_PROMPT,
        }, {
            "role": "user",
            "content": f"Conversation:\n{conv_text}",
        }]

    async def save_extracted_memories(self, memories_json: str, session_id: str):
        """Process and save extracted memories from the LLM."""
        try:
            memories = json.loads(memories_json)
            if not isinstance(memories, list):
                return

            for mem in memories:
                mem_id = str(uuid4())
                content = mem.get("content", "")
                category = mem.get("category", "general")
                importance = float(mem.get("importance", 0.5))

                if not content:
                    continue

                # Save to SQLite
                await self.store.save_memory(
                    memory_id=mem_id,
                    category=category,
                    content=content,
                    importance=importance,
                    source_session=session_id,
                )

                # Index in ChromaDB
                self.vectors.add_memory(
                    doc_id=mem_id,
                    content=content,
                    metadata={"category": category, "importance": str(importance)},
                )

                logger.info(f"Memory saved: [{category}] {content[:80]}...")

                # Dump raw content for Graphify
                await graphify_backend.add_raw_memory(
                    f"Category: {category}\nImportance: {importance}\n{content}",
                    f"memory_{mem_id}.txt"
                )

            # Update MEMORY.md
            await self._update_memory_md()
            
            # Rebuild Knowledge Graph
            await graphify_backend.update_graph()

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse memories: {e}")

    async def save_user_facts(self, facts_json: str, session_id: str):
        """Process and save user facts from the LLM."""
        try:
            facts = json.loads(facts_json)
            if not isinstance(facts, list):
                return

            for fact in facts:
                key = fact.get("key", "")
                value = fact.get("value", "")
                confidence = float(fact.get("confidence", 0.5))

                if not key or not value:
                    continue

                self.user_model.update_fact(key, value, confidence, source=session_id)
                await self.store.save_user_fact(key, value, confidence, source=session_id)

            # Persist to USER.md
            self.user_model.save_to_file()

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse user facts: {e}")

    def get_context_for_agent(self) -> str:
        """Build memory context to inject into the agent's system prompt."""
        parts = []

        # User model summary
        user_summary = self.user_model.get_context_summary()
        if user_summary:
            parts.append(user_summary)
            
        # Graphify Knowledge Graph Index
        wiki_index = graphify_backend.get_wiki_index()
        if wiki_index:
            parts.append("## Knowledge Graph Context (Graphify)\n" + wiki_index)

        return "\n\n".join(parts)

    async def get_relevant_context(self, query: str, n_results: int = 5) -> str:
        """Get relevant past memories/conversations for a given query."""
        parts = []

        # Search memories
        memories = self.vectors.search_memories(query, n_results=n_results)
        if memories:
            parts.append("## Relevant memories:")
            for m in memories:
                parts.append(f"- {m['content']}")

        # Search past conversations
        past = self.vectors.search_conversations(query, n_results=3)
        if past:
            parts.append("\n## Related past conversations:")
            for p in past:
                parts.append(f"- [{p.get('metadata', {}).get('role', '?')}]: {p['content'][:200]}")

        return "\n".join(parts) if parts else ""

    async def _update_memory_md(self):
        """Update MEMORY.md with all memories."""
        memories = await self.store.get_memories(limit=200)
        if not memories:
            return

        # Group by category
        by_cat: dict[str, list] = {}
        for m in memories:
            cat = m.get("category", "general")
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(m)

        entries = []
        for cat, mems in sorted(by_cat.items()):
            entries.append(f"\n## {cat.title()}")
            for m in mems:
                imp = "🔴" if m["importance"] >= 0.8 else "🟡" if m["importance"] >= 0.5 else "⚪"
                entries.append(f"- {imp} {m['content']}")

        content = MEMORY_MD_TEMPLATE.format(
            entries="\n".join(entries),
            count=len(memories),
            updated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._settings.memory_md_path.write_text(content, encoding="utf-8")

    async def get_stats(self) -> dict:
        """Get memory system statistics."""
        store_stats = await self.store.get_stats()
        vector_stats = self.vectors.get_stats()
        return {
            **store_stats,
            **vector_stats,
            "user_facts": len(self.user_model.get_all_facts()),
        }
