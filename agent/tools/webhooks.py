"""
NexAlfa Webhook Tool
Register and manage inbound webhook endpoints for event-driven automation.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.webhooks")

# In-memory webhook registry
_webhooks: dict[str, dict] = {}
_webhook_events: list[dict] = []


class WebhookRegisterTool(Tool):
    name = "webhook_register"
    description = "Register a new webhook endpoint. The gateway will expose /webhook/<name> for external services to POST to."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Webhook name (becomes the URL path)"},
                    "description": {"type": "string", "description": "What this webhook is for"},
                    "response_action": {
                        "type": "string",
                        "description": "What to do when triggered: 'log' (just log), 'notify' (send to current session), 'run' (execute a command)",
                    },
                    "command": {"type": "string", "description": "Command to run (for response_action=run)"},
                },
                "required": ["name", "description"],
            },
        }

    async def execute(
        self, name: str, description: str, response_action: str = "log", command: str = None
    ) -> str:
        _webhooks[name] = {
            "name": name,
            "description": description,
            "response_action": response_action,
            "command": command,
            "created_at": time.time(),
        }
        return (
            f"✅ Webhook registered: **{name}**\n"
            f"URL: `/webhook/{name}`\n"
            f"Action: {response_action}\n"
            f"Description: {description}"
        )


class WebhookListTool(Tool):
    name = "webhook_list"
    description = "List all registered webhooks and recent events."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }

    async def execute(self) -> str:
        if not _webhooks:
            return "No webhooks registered."

        lines = ["**Registered Webhooks:**"]
        for wh in _webhooks.values():
            lines.append(f"- **{wh['name']}**: {wh['description']} (action: {wh['response_action']})")

        if _webhook_events:
            lines.append(f"\n**Recent Events:** ({len(_webhook_events)} total)")
            for ev in _webhook_events[-5:]:
                lines.append(f"- [{ev['webhook']}] {ev['timestamp']}: {json.dumps(ev['data'])[:100]}")

        return "\n".join(lines)


def handle_webhook_event(name: str, data: dict) -> Optional[str]:
    """Process an inbound webhook event. Called by the gateway."""
    webhook = _webhooks.get(name)
    if not webhook:
        return None

    event = {
        "webhook": name,
        "data": data,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _webhook_events.append(event)
    logger.info(f"Webhook event: {name} — {json.dumps(data)[:200]}")

    return webhook.get("response_action", "log")


def get_webhook_tools() -> list[Tool]:
    return [WebhookRegisterTool(), WebhookListTool()]
