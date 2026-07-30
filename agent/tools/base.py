"""
NexAlfa Tool Base
Base class for all agent tools. Dev-mode: everything allowed by default.
Inspired by OpenClaw's tool system with dev-mode philosophy.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger("nex.tools")

# ── Tool categories and their trigger keywords ──────────────
TOOL_CATEGORIES = {
    "core": {
        "always_include": True,
        "keywords": [],  # Always sent
    },
    "desktop": {
        "always_include": False,
        "keywords": [
            "screen", "screenshot", "click", "type", "window", "open app",
            "close app", "desktop", "mouse", "keyboard", "hotkey", "drag",
            "scroll", "focus", "minimize", "maximize", "notepad", "word",
            "excel", "chrome", "browser", "clipboard", "copy", "paste",
        ],
    },
    "pc_control": {
        "always_include": False,
        "keywords": [
            "wallpaper", "dark mode", "light mode", "volume", "brightness",
            "wifi", "bluetooth", "battery", "shutdown", "restart", "sleep",
            "lock", "camera", "microphone", "speakers", "audio", "webcam",
            "system info", "specs", "cpu", "ram", "gpu", "disk", "process",
            "network", "ip address", "permission", "display",
        ],
    },
    "system": {
        "always_include": False,
        "keywords": [
            "model", "switch model", "change model", "thinking", "temperature",
            "status", "health", "config", "restart", "logs", "tools",
            "set model", "what model", "system", "diagnose",
        ],
    },
    "browser": {
        "always_include": False,
        "keywords": [
            "browse", "website", "url", "navigate", "web page", "tab",
            "browser", "html", "javascript", "scrape",
        ],
    },
    "documents": {
        "always_include": False,
        "keywords": [
            "pdf", "word", "docx", "excel", "xlsx", "csv", "document",
            "read file", "write file", "convert", "extract table",
        ],
    },
    "web": {
        "always_include": False,
        "keywords": [
            "search", "google", "internet", "web", "scrape", "extract",
            "find online", "look up",
        ],
    },
    "voice": {
        "always_include": False,
        "keywords": [
            "voice", "speak", "transcribe", "audio", "speech", "tts",
            "stt", "whisper", "say", "listen",
        ],
    },
    "google_api": {
        "always_include": False,
        "keywords": [
            "gmail", "email", "google", "drive", "calendar", "inbox",
            "send email", "upload drive", "events", "schedule",
        ],
    },
    "devtools": {
        "always_include": False,
        "keywords": [
            "vscode", "code", "project", "scaffold", "create project",
            "git", "commit", "push", "pull", "build", "npm", "dev server",
            "monitor process", "ide", "antigravity",
        ],
    },
    "subagents": {
        "always_include": False,
        "keywords": [
            "sub-agent", "subagent", "agent", "spawn", "parallel",
            "researcher", "coder", "worker",
        ],
    },
    "cron": {
        "always_include": False,
        "keywords": [
            "schedule", "cron", "timer", "repeat", "every hour",
            "every day", "periodic", "recurring",
        ],
    },
    "webhooks": {
        "always_include": False,
        "keywords": ["webhook", "callback", "http hook", "endpoint"],
    },
    "mcp": {
        "always_include": False,
        "keywords": ["mcp", "protocol", "connect tool"],
    },
}


class Tool(ABC):
    """Base class for all NexAlfa tools."""

    name: str = ""
    description: str = ""
    enabled: bool = True
    category: str = "core"  # Tool category for smart loading

    @abstractmethod
    def get_schema(self) -> dict:
        """Return OpenAI-compatible function schema for this tool."""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """Execute the tool and return result as string."""
        ...

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI tools format."""
        return {
            "type": "function",
            "function": self.get_schema(),
        }


class ToolRegistry:
    """Registry of all available tools with smart relevance loading."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info(f"Tool registered: {tool.name}")

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        return [t for t in self._tools.values() if t.enabled]

    def get_openai_tools(self) -> list[dict]:
        """Get all enabled tools in OpenAI format."""
        return [t.to_openai_tool() for t in self._tools.values() if t.enabled]

    def get_relevant_tools(self, message: str) -> list[dict]:
        """Get only the tools relevant to the user's message.
        
        Instead of sending all 89 tool schemas (~15K tokens), this sends
        only the matching categories (~3-5K tokens). Core tools always included.
        """
        msg_lower = message.lower()

        # Find which categories are relevant
        relevant_categories = set()
        for cat_name, cat_info in TOOL_CATEGORIES.items():
            if cat_info["always_include"]:
                relevant_categories.add(cat_name)
                continue
            for keyword in cat_info["keywords"]:
                if keyword in msg_lower:
                    relevant_categories.add(cat_name)
                    break

        # If no specific categories matched, include system tools as default
        if relevant_categories == {"core"}:
            relevant_categories.add("system")

        # Collect tools from matched categories
        result = []
        for tool in self._tools.values():
            if not tool.enabled:
                continue
            if tool.category in relevant_categories:
                result.append(tool.to_openai_tool())

        logger.debug(f"Smart tools: {len(result)}/{len(self._tools)} tools for categories: {relevant_categories}")
        return result

    async def execute_tool(self, name: str, arguments: str) -> str:
        """Execute a tool by name with JSON arguments."""
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"
        if not tool.enabled:
            return f"Error: Tool '{name}' is disabled"
        try:
            kwargs = json.loads(arguments) if isinstance(arguments, str) else arguments
            result = await tool.execute(**kwargs)
            return result
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return f"Error executing {name}: {str(e)}"

    def list_tools(self) -> list[dict]:
        """List all tools with their status."""
        return [
            {"name": t.name, "description": t.description, "enabled": t.enabled, "category": t.category}
            for t in self._tools.values()
        ]

