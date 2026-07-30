"""
NexAlfa OAuth Sink
Manages OAuth session tokens and cookies for web-based LLM providers (e.g., ChatGPT Web, Claude Web).
Stores profiles securely in storage/auth-profiles.json.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("nex.auth")

class OAuthSink:
    """Stores and retrieves OAuth session tokens and cookies."""
    
    def __init__(self, storage_dir: str = "storage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.profile_path = self.storage_dir / "auth-profiles.json"
        self.profiles: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r") as f:
                    self.profiles = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load auth profiles: {e}")
                self.profiles = {}

    def _save(self):
        try:
            with open(self.profile_path, "w") as f:
                json.dump(self.profiles, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save auth profiles: {e}")

    def save_token(self, provider: str, token: str, metadata: dict = None):
        """Save a raw access token for a provider."""
        if provider not in self.profiles:
            self.profiles[provider] = {}
        self.profiles[provider]["access_token"] = token
        if metadata:
            self.profiles[provider]["metadata"] = metadata
        self._save()
        logger.info(f"Saved OAuth token for provider: {provider}")

    def get_token(self, provider: str) -> Optional[str]:
        """Retrieve the access token for a provider."""
        return self.profiles.get(provider, {}).get("access_token")

    def has_provider(self, provider: str) -> bool:
        return provider in self.profiles and "access_token" in self.profiles[provider]

    def remove_provider(self, provider: str):
        if provider in self.profiles:
            del self.profiles[provider]
            self._save()
            logger.info(f"Removed OAuth profile for provider: {provider}")

# Singleton instance
auth_sink = OAuthSink()
