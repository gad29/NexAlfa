"""
NexAlfa Vector Store
ChromaDB-backed semantic memory for past conversations, memories, and skills.
Enables "search your own past" feature from Hermes Agent.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from agent.config.settings import get_settings

logger = logging.getLogger("nex.memory.vector")


class VectorStore:
    """Semantic vector memory using ChromaDB — search conversations by meaning."""

    def __init__(self, persist_path: Optional[Path] = None):
        settings = get_settings()
        self._persist_path = persist_path or Path(settings.memory.vector_store_path)
        self._client: Optional[chromadb.ClientAPI] = None
        self._conversations: Optional[chromadb.Collection] = None
        self._memories: Optional[chromadb.Collection] = None
        self._skills: Optional[chromadb.Collection] = None

    async def initialize(self):
        """Initialize ChromaDB collections."""
        self._persist_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self._persist_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # Collections
        self._conversations = self._client.get_or_create_collection(
            name="conversations",
            metadata={"description": "All conversation messages for semantic search"},
        )
        self._memories = self._client.get_or_create_collection(
            name="memories",
            metadata={"description": "Extracted memories and learnings"},
        )
        self._skills = self._client.get_or_create_collection(
            name="skills",
            metadata={"description": "Skill definitions for similarity matching"},
        )
        logger.info(f"Vector store initialized: {self._persist_path}")

    def add_conversation(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[dict] = None,
    ):
        """Index a conversation message for semantic search."""
        if not content.strip():
            return
        self._conversations.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata or {}],
        )

    def add_memory(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[dict] = None,
    ):
        """Index a memory entry."""
        self._memories.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata or {}],
        )

    def add_skill(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[dict] = None,
    ):
        """Index a skill definition."""
        self._skills.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata or {}],
        )

    def search_conversations(
        self, query: str, n_results: int = 10, where: Optional[dict] = None
    ) -> list[dict]:
        """Semantic search over past conversations."""
        params = {"query_texts": [query], "n_results": n_results}
        if where:
            params["where"] = where
        results = self._conversations.query(**params)
        return self._format_results(results)

    def search_memories(
        self, query: str, n_results: int = 10, where: Optional[dict] = None
    ) -> list[dict]:
        """Semantic search over memories."""
        params = {"query_texts": [query], "n_results": n_results}
        if where:
            params["where"] = where
        results = self._memories.query(**params)
        return self._format_results(results)

    def search_skills(
        self, query: str, n_results: int = 5
    ) -> list[dict]:
        """Find relevant skills for a given query/task."""
        results = self._skills.query(query_texts=[query], n_results=n_results)
        return self._format_results(results)

    def _format_results(self, results: dict) -> list[dict]:
        """Format ChromaDB results into clean dicts."""
        formatted = []
        if not results or not results.get("ids"):
            return formatted

        for i, doc_id in enumerate(results["ids"][0]):
            entry = {
                "id": doc_id,
                "content": results["documents"][0][i] if results.get("documents") else "",
                "distance": results["distances"][0][i] if results.get("distances") else 0,
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            }
            formatted.append(entry)
        return formatted

    def get_stats(self) -> dict:
        """Get vector store statistics."""
        return {
            "conversations_indexed": self._conversations.count() if self._conversations else 0,
            "memories_indexed": self._memories.count() if self._memories else 0,
            "skills_indexed": self._skills.count() if self._skills else 0,
            "persist_path": str(self._persist_path),
        }
