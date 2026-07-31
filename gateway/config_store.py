"""
NexAlfa Config Store — Persistent JSON-based configuration.
Stores channel credentials, API keys, and runtime config.
Lives at /app/storage/channel_config.json inside the Docker volume.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger("nex.config_store")

# Default path — inside the Docker persistent volume
CONFIG_PATH = os.environ.get(
    "NEX_CONFIG_PATH",
    os.path.join(os.path.dirname(__file__), "..", "storage", "config.json"),
)


class ConfigStore:
    """Thread-safe JSON config store that merges with environment variables."""

    def __init__(self, path: str = CONFIG_PATH):
        self._path = Path(path).resolve()
        self._lock = Lock()
        self._data: dict[str, Any] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────

    def _load(self):
        """Load config from disk. Create file if missing."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists():
                with open(self._path, "r") as f:
                    self._data = json.load(f)
                logger.info(f"Loaded config from {self._path}")
            else:
                self._data = {}
                self._save()
                logger.info(f"Created new config at {self._path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._data = {}

    def _save(self):
        """Persist config to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    # ── Channel Config ────────────────────────────────────────

    def get_channel_config(self, channel: str) -> dict[str, Any]:
        """Get config for a specific channel."""
        with self._lock:
            return dict(self._data.get("channels", {}).get(channel, {}))

    def set_channel_config(self, channel: str, config: dict[str, str]):
        """Save config for a channel and inject into os.environ."""
        with self._lock:
            if "channels" not in self._data:
                self._data["channels"] = {}
            self._data["channels"][channel] = config
            self._save()

        # Inject into environment so the channel adapters pick them up
        env_mapping = self._get_env_mapping(channel)
        for field, env_var in env_mapping.items():
            if field in config and config[field]:
                os.environ[env_var] = config[field]
                logger.info(f"Set {env_var} from config store")

    def get_channel_status(self, channel: str) -> dict[str, bool]:
        """Return which fields are configured (True/False), never actual values."""
        config = self.get_channel_config(channel)
        env_mapping = self._get_env_mapping(channel)
        result = {}
        for field, env_var in env_mapping.items():
            # Check both config store and environment
            has_value = bool(config.get(field)) or bool(os.environ.get(env_var))
            result[field] = has_value
        return result

    # ── API Key Config ────────────────────────────────────────

    def get_api_keys_status(self) -> dict[str, bool]:
        """Return which API keys are set (True/False), never actual values."""
        keys = [
            "GOOGLE_API_KEY",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "GEMINI_API_KEY",
            "OLLAMA_API_BASE",
        ]
        return {k: bool(os.environ.get(k) or self._data.get("api_keys", {}).get(k)) for k in keys}

    def set_api_key(self, key_name: str, key_value: str):
        """Save an API key and inject into os.environ."""
        allowed = {
            "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY",
            "GEMINI_API_KEY", "OLLAMA_API_BASE",
        }
        if key_name not in allowed:
            raise ValueError(f"Unknown API key: {key_name}")

        with self._lock:
            if "api_keys" not in self._data:
                self._data["api_keys"] = {}
            self._data["api_keys"][key_name] = key_value
            self._save()

        os.environ[key_name] = key_value
        # Also set GEMINI_API_KEY when GOOGLE_API_KEY is set (for LiteLLM)
        if key_name == "GOOGLE_API_KEY":
            os.environ["GEMINI_API_KEY"] = key_value
        logger.info(f"Set API key: {key_name}")

    def delete_api_key(self, key_name: str):
        """Remove an API key."""
        with self._lock:
            if "api_keys" in self._data and key_name in self._data["api_keys"]:
                del self._data["api_keys"][key_name]
                self._save()
        os.environ.pop(key_name, None)
        logger.info(f"Removed API key: {key_name}")

    # ── Boot: Load saved keys into environment ────────────────

    def inject_saved_keys(self):
        """On boot, load any saved API keys & channel configs into os.environ."""
        # API keys
        for key, value in self._data.get("api_keys", {}).items():
            if value and not os.environ.get(key):
                os.environ[key] = value
                logger.info(f"Injected saved API key: {key}")
                if key == "GOOGLE_API_KEY":
                    os.environ["GEMINI_API_KEY"] = value

        # Channel configs
        for channel, config in self._data.get("channels", {}).items():
            env_mapping = self._get_env_mapping(channel)
            for field, env_var in env_mapping.items():
                if field in config and config[field] and not os.environ.get(env_var):
                    os.environ[env_var] = config[field]
                    logger.info(f"Injected saved channel config: {env_var}")

    # ── Env var mapping per channel ───────────────────────────

    @staticmethod
    def _get_env_mapping(channel: str) -> dict[str, str]:
        """Map config field names to environment variable names."""
        mappings = {
            "whatsapp": {
                "bridge": "NEX_WHATSAPP_BRIDGE",
                "phone_number_id": "WHATSAPP_PHONE_NUMBER_ID",
                "business_account_id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "access_token": "WHATSAPP_ACCESS_TOKEN",
                "verify_token": "WHATSAPP_VERIFY_TOKEN",
            },
            "telegram": {
                "bot_token": "TELEGRAM_BOT_TOKEN",
            },
            "discord": {
                "bot_token": "DISCORD_BOT_TOKEN",
            },
            "slack": {
                "bot_token": "SLACK_BOT_TOKEN",
                "app_token": "SLACK_APP_TOKEN",
            },
            "google_chat": {
                "credentials_file": "GOOGLE_CHAT_CREDENTIALS_FILE",
                "project_id": "GOOGLE_CHAT_PROJECT_ID",
            },
            "email": {
                "smtp_host": "EMAIL_SMTP_HOST",
                "smtp_port": "EMAIL_SMTP_PORT",
                "imap_host": "EMAIL_IMAP_HOST",
                "imap_port": "EMAIL_IMAP_PORT",
                "address": "EMAIL_ADDRESS",
                "password": "EMAIL_PASSWORD",
            },
        }
        return mappings.get(channel, {})


# Singleton
_store: Optional[ConfigStore] = None


def get_config_store() -> ConfigStore:
    """Get or create the singleton config store."""
    global _store
    if _store is None:
        _store = ConfigStore()
    return _store
