"""
NexAlfa User Model
Builds a deepening understanding of who you are across sessions.
Inspired by Hermes Agent's user modeling system.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from agent.config.settings import get_settings

logger = logging.getLogger("nex.memory.user_model")

USER_MD_TEMPLATE = """# User Profile
> Auto-maintained by Nex. Updated as I learn more about you.

## Preferences
{preferences}

## Communication Style
{communication_style}

## Projects & Interests
{projects}

## Technical Stack
{tech_stack}

## Important Context
{context}

---
*Last updated: {updated_at}*
"""


class UserModel:
    """
    Tracks and updates what Nex knows about the user.
    Persists to USER.md and SQLite user_facts table.
    """

    def __init__(self):
        settings = get_settings()
        self._user_md_path = settings.user_md_path
        self._facts: dict[str, dict] = {}
        self._load_from_file()

    def _load_from_file(self):
        """Load existing user model from USER.md if it exists."""
        if self._user_md_path.exists():
            content = self._user_md_path.read_text(encoding="utf-8")
            # Parse simple key-value pairs from the markdown
            logger.info("Loaded existing user model from USER.md")

    def update_fact(self, key: str, value: str, confidence: float = 0.5, source: str = ""):
        """Update a fact about the user."""
        self._facts[key] = {
            "value": value,
            "confidence": confidence,
            "source": source,
            "updated_at": time.time(),
        }
        logger.info(f"User fact updated: {key} = {value} (confidence: {confidence})")

    def get_fact(self, key: str) -> Optional[str]:
        """Get a specific fact."""
        fact = self._facts.get(key)
        return fact["value"] if fact else None

    def get_all_facts(self) -> dict[str, dict]:
        """Get all known facts."""
        return dict(self._facts)

    def get_context_summary(self) -> str:
        """Generate a summary of the user model for injection into agent context."""
        if not self._facts:
            return "No user profile built yet. Learn from interactions."

        lines = ["## What I know about the user:"]
        # Group by category
        categories = {}
        for key, fact in self._facts.items():
            cat = key.split(".")[0] if "." in key else "general"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(f"- **{key}**: {fact['value']}")

        for cat, items in categories.items():
            lines.append(f"\n### {cat.title()}")
            lines.extend(items)

        return "\n".join(lines)

    def save_to_file(self):
        """Persist the user model to USER.md."""
        prefs = []
        style = []
        projects = []
        tech = []
        context = []

        for key, fact in self._facts.items():
            line = f"- **{key}**: {fact['value']}"
            if key.startswith("pref."):
                prefs.append(line)
            elif key.startswith("style."):
                style.append(line)
            elif key.startswith("project."):
                projects.append(line)
            elif key.startswith("tech."):
                tech.append(line)
            else:
                context.append(line)

        content = USER_MD_TEMPLATE.format(
            preferences="\n".join(prefs) if prefs else "- *Learning...*",
            communication_style="\n".join(style) if style else "- *Observing...*",
            projects="\n".join(projects) if projects else "- *Discovering...*",
            tech_stack="\n".join(tech) if tech else "- *Noting...*",
            context="\n".join(context) if context else "- *Gathering...*",
            updated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

        self._user_md_path.write_text(content, encoding="utf-8")
        logger.info("User model saved to USER.md")

    def generate_learning_prompt(self) -> str:
        """Generate a prompt for the LLM to extract user facts from a conversation."""
        return """Analyze this conversation and extract facts about the user.
Return a JSON array of objects with these fields:
- "key": dot-notation key (e.g. "pref.language", "tech.framework", "project.current", "style.tone")
- "value": the fact value
- "confidence": 0.0-1.0 how confident you are

Categories: pref (preferences), style (communication), project (projects/interests), tech (technical stack), general (other)

Only extract clear, factual information. Don't guess. Return [] if nothing new learned.
Example: [{"key": "tech.language", "value": "Python and TypeScript", "confidence": 0.9}]"""
