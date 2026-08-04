"""
NexAlfa System Permissions Manager
Controls shell execution, desktop GUI automation, web browser control, and file access.
Persists settings in storage/permissions.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("nex.permissions")

PERMISSIONS_FILE = Path(__file__).parent.parent.parent / "storage" / "permissions.json"

DEFAULT_PERMISSIONS = {
    "allow_shell": "ask",         # "ask", "allowed", "disabled"
    "allow_desktop": True,        # Enable screen captures & GUI desktop tools
    "allow_browser": True,        # Enable Playwright headless browser control
    "allow_filesystem": True,     # Enable file operations outside workspace
    "allowed_command_prefixes": [ # Allowed shell command prefixes if shell="ask" or "allowed"
        "git", "npm", "uv", "python", "node", "docker", "pip", "pytest", "curl"
    ]
}


class PermissionsManager:
    """Manages system permissions and security boundaries for NexAlfa tools."""

    def __init__(self, file_path: Path = PERMISSIONS_FILE):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.permissions: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Load permissions from storage/permissions.json."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.permissions = {**DEFAULT_PERMISSIONS, **data}
            except Exception as e:
                logger.error(f"Failed to read permissions file: {e}")
                self.permissions = dict(DEFAULT_PERMISSIONS)
        else:
            self.permissions = dict(DEFAULT_PERMISSIONS)
            self.save()

    def save(self):
        """Persist permissions to disk."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.permissions, f, indent=2)
            logger.info("Updated system permissions")
        except Exception as e:
            logger.error(f"Failed to save permissions: {e}")

    def get_all(self) -> Dict[str, Any]:
        """Get copy of all permissions."""
        return dict(self.permissions)

    def update(self, new_perms: Dict[str, Any]):
        """Update permission keys and persist."""
        for k, v in new_perms.items():
            if k in DEFAULT_PERMISSIONS:
                self.permissions[k] = v
        self.save()

    def is_allowed(self, capability: str) -> bool:
        """Check if a specific capability is allowed."""
        return bool(self.permissions.get(capability, False))


# Singleton instance
permissions_manager = PermissionsManager()
