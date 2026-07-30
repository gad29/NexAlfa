"""
NexAlfa Skills Engine
Loads skills from SKILL.md files (OpenClaw format) and supports auto-creation
from experience (Hermes pattern).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent.config.settings import get_settings

logger = logging.getLogger("nex.skills")


@dataclass
class Skill:
    """A loaded skill definition."""

    name: str
    description: str
    content: str  # full SKILL.md content
    path: Path
    enabled: bool = True
    auto_created: bool = False
    usage_count: int = 0
    last_used: Optional[float] = None
    created_at: float = field(default_factory=time.time)

    def to_context(self) -> str:
        """Convert to context string for injection into the agent prompt."""
        return f"### Skill: {self.name}\n{self.content}"


SKILL_MD_TEMPLATE = """# {name}

## Description
{description}

## When to Use
{when_to_use}

## Steps
{steps}

## Notes
{notes}

---
*Auto-created by Nex on {created_at}*
*Usage count: {usage_count}*
"""


class SkillsEngine:
    """
    Manages agent skills — loadable, invocable, auto-creatable.
    Skills are SKILL.md files in the workspace/skills/ directory.
    """

    def __init__(self):
        self._settings = get_settings()
        self._skills: dict[str, Skill] = {}
        self._skills_dir = self._settings.skills_path

    def load_all(self):
        """Load all skills from the skills directory."""
        self._skills_dir.mkdir(parents=True, exist_ok=True)

        for skill_dir in self._skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    self._load_skill(skill_dir.name, skill_file)

        logger.info(f"Loaded {len(self._skills)} skills")

    def _load_skill(self, name: str, path: Path):
        """Load a single skill from its SKILL.md file."""
        try:
            content = path.read_text(encoding="utf-8")
            # Extract description from first paragraph after the title
            lines = content.strip().split("\n")
            description = ""
            for line in lines[1:]:  # skip title
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line
                    break

            skill = Skill(
                name=name,
                description=description,
                content=content,
                path=path,
            )
            self._skills[name] = skill
            logger.debug(f"Loaded skill: {name}")
        except Exception as e:
            logger.warning(f"Failed to load skill {name}: {e}")

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_all_skills(self) -> list[Skill]:
        """Get all loaded skills."""
        return list(self._skills.values())

    def get_enabled_skills(self) -> list[Skill]:
        """Get all enabled skills."""
        return [s for s in self._skills.values() if s.enabled]

    def get_skills_context(self) -> str:
        """Build skills context for injection into agent prompt."""
        enabled = self.get_enabled_skills()
        if not enabled:
            return ""

        lines = ["## Available Skills"]
        for skill in enabled:
            lines.append(f"- **/{skill.name}**: {skill.description}")

        return "\n".join(lines)

    def invoke_skill(self, name: str) -> Optional[str]:
        """Invoke a skill — returns its content for the agent to follow."""
        skill = self._skills.get(name)
        if not skill or not skill.enabled:
            return None

        skill.usage_count += 1
        skill.last_used = time.time()
        logger.info(f"Skill invoked: {name} (usage #{skill.usage_count})")
        return skill.to_context()

    def create_skill(
        self,
        name: str,
        description: str,
        when_to_use: str,
        steps: str,
        notes: str = "",
    ) -> Skill:
        """Create a new skill from the agent's experience."""
        # Create skill directory
        skill_dir = self._skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Write SKILL.md
        content = SKILL_MD_TEMPLATE.format(
            name=name,
            description=description,
            when_to_use=when_to_use,
            steps=steps,
            notes=notes or "None",
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            usage_count=0,
        )

        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(content, encoding="utf-8")

        # Load the new skill
        skill = Skill(
            name=name,
            description=description,
            content=content,
            path=skill_file,
            auto_created=True,
        )
        self._skills[name] = skill
        logger.info(f"✨ New skill created: {name}")
        return skill

    def list_skills(self) -> list[dict]:
        """List all skills with metadata."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "enabled": s.enabled,
                "auto_created": s.auto_created,
                "usage_count": s.usage_count,
                "last_used": s.last_used,
            }
            for s in self._skills.values()
        ]
