"""
NexAlfa Personality System
Loads SOUL.md and supports personality switching.
Inspired by OpenClaw (SOUL.md) + Hermes (/personality).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from agent.config.settings import get_settings

logger = logging.getLogger("nex.personality")


class PersonalityManager:
    """Manages agent personality via SOUL.md files."""

    def __init__(self):
        self._settings = get_settings()
        self._current_name = "default"
        self._soul_content: str = ""
        self._agents_md: str = ""
        self._load_default()

    def _load_default(self):
        """Load the default SOUL.md and AGENTS.md."""
        soul_path = self._settings.soul_path
        agents_path = self._settings.agents_md_path

        if soul_path.exists():
            self._soul_content = soul_path.read_text(encoding="utf-8")
            logger.info("Loaded SOUL.md")
        else:
            self._soul_content = f"You are {self._settings.agent_name}, a helpful personal AI assistant."

        if agents_path.exists():
            self._agents_md = agents_path.read_text(encoding="utf-8")
            logger.info("Loaded AGENTS.md")

    def get_system_prompt(self, user_context: str = "", skills_context: str = "", memory_context: str = "") -> str:
        """Build the full system prompt for the agent."""
        parts = [self._soul_content]

        if self._agents_md:
            parts.append(self._agents_md)

        if memory_context:
            parts.append(memory_context)

        if user_context:
            parts.append(user_context)

        if skills_context:
            parts.append(skills_context)

        return "\n\n---\n\n".join(parts)

    def switch_personality(self, name: str) -> bool:
        """Switch to a different personality file."""
        personality_dir = self._settings.workspace_path / "personalities"
        personality_file = personality_dir / f"{name}.md"

        if personality_file.exists():
            self._soul_content = personality_file.read_text(encoding="utf-8")
            self._current_name = name
            logger.info(f"Personality switched to: {name}")
            return True

        # Also check if it's the default
        if name == "default":
            self._load_default()
            self._current_name = "default"
            return True

        logger.warning(f"Personality not found: {name}")
        return False

    def list_personalities(self) -> list[str]:
        """List available personality files."""
        personalities = ["default"]
        personality_dir = self._settings.workspace_path / "personalities"
        if personality_dir.exists():
            for f in personality_dir.glob("*.md"):
                personalities.append(f.stem)
        return personalities

    @property
    def current_name(self) -> str:
        return self._current_name

    @property
    def soul_content(self) -> str:
        return self._soul_content
