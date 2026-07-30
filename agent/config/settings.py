"""
NexAlfa Configuration System
Dev-mode first — everything visible, nothing blocked.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    """Walk up from CWD to find the project root (where pyproject.toml lives)."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return current


PROJECT_ROOT = _find_project_root()


class ModelConfig(BaseSettings):
    """LLM model configuration."""

    default_model: str = Field("openai/gpt-4o", alias="NEX_DEFAULT_MODEL")
    fallback_models: list[str] = Field(
        default_factory=lambda: ["openrouter/anthropic/claude-sonnet-4", "ollama/llama3"],
    )
    temperature: float = 0.7
    max_tokens: int = 4096
    streaming: bool = True

    # Provider keys
    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")
    google_api_key: Optional[str] = Field(None, alias="GOOGLE_API_KEY")
    openrouter_api_key: Optional[str] = Field(None, alias="OPENROUTER_API_KEY")
    ollama_base_url: str = Field("http://localhost:11434", alias="OLLAMA_BASE_URL")


class GatewayConfig(BaseSettings):
    """Gateway server configuration."""

    host: str = Field("0.0.0.0", alias="NEX_GATEWAY_HOST")
    port: int = Field(18789, alias="NEX_GATEWAY_PORT")
    secret: str = Field("change-me", alias="NEX_GATEWAY_SECRET")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


class ChannelConfig(BaseSettings):
    """Channel adapter configuration."""

    # Telegram
    telegram_bot_token: Optional[str] = Field(None, alias="TELEGRAM_BOT_TOKEN")
    # Discord
    discord_bot_token: Optional[str] = Field(None, alias="DISCORD_BOT_TOKEN")
    # Slack
    slack_bot_token: Optional[str] = Field(None, alias="SLACK_BOT_TOKEN")
    slack_app_token: Optional[str] = Field(None, alias="SLACK_APP_TOKEN")
    # WhatsApp
    whatsapp_bridge: bool = Field(True, alias="NEX_WHATSAPP_BRIDGE")
    whatsapp_phone_number_id: Optional[str] = Field(None, alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_business_account_id: Optional[str] = Field(None, alias="WHATSAPP_BUSINESS_ACCOUNT_ID")
    whatsapp_access_token: Optional[str] = Field(None, alias="WHATSAPP_ACCESS_TOKEN")
    whatsapp_verify_token: Optional[str] = Field(None, alias="WHATSAPP_VERIFY_TOKEN")
    # Google Chat
    google_chat_credentials_file: Optional[str] = Field(None, alias="GOOGLE_CHAT_CREDENTIALS_FILE")
    google_chat_project_id: Optional[str] = Field(None, alias="GOOGLE_CHAT_PROJECT_ID")
    # Email
    email_smtp_host: Optional[str] = Field(None, alias="EMAIL_SMTP_HOST")
    email_smtp_port: int = Field(587, alias="EMAIL_SMTP_PORT")
    email_imap_host: Optional[str] = Field(None, alias="EMAIL_IMAP_HOST")
    email_imap_port: int = Field(993, alias="EMAIL_IMAP_PORT")
    email_address: Optional[str] = Field(None, alias="EMAIL_ADDRESS")
    email_password: Optional[str] = Field(None, alias="EMAIL_PASSWORD")


class MemoryConfig(BaseSettings):
    """Memory and learning configuration."""

    auto_learn: bool = Field(True, alias="NEX_MEMORY_AUTO_LEARN")
    auto_skills: bool = Field(True, alias="NEX_MEMORY_AUTO_SKILLS")
    vector_store_path: str = Field("./storage/memory", alias="NEX_VECTOR_STORE_PATH")


class DevModeConfig(BaseSettings):
    """Dev mode settings — the NexAlfa way. Everything on by default."""

    enabled: bool = Field(True, alias="NEX_DEV_MODE")
    show_thinking: bool = Field(True, alias="NEX_SHOW_THINKING")
    save_all_history: bool = Field(True, alias="NEX_SAVE_ALL_HISTORY")
    raw_config_visible: bool = Field(True, alias="NEX_RAW_CONFIG_VISIBLE")


class NexSettings(BaseSettings):
    """Master settings for NexAlfa."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Agent identity
    agent_name: str = Field("Nex", alias="NEX_AGENT_NAME")

    # Paths
    workspace_path: Path = Field(PROJECT_ROOT / "workspace", alias="NEX_WORKSPACE_PATH")
    storage_path: Path = Field(PROJECT_ROOT / "storage", alias="NEX_STORAGE_PATH")
    skills_path: Path = Field(PROJECT_ROOT / "workspace" / "skills", alias="NEX_SKILLS_PATH")

    # Sub-configs
    model: ModelConfig = Field(default_factory=ModelConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    channels: ChannelConfig = Field(default_factory=ChannelConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    dev_mode: DevModeConfig = Field(default_factory=DevModeConfig)

    def ensure_dirs(self):
        """Create all required directories."""
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.skills_path.mkdir(parents=True, exist_ok=True)
        (self.storage_path / "memory").mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        return self.storage_path / "nexalfa.db"

    @property
    def soul_path(self) -> Path:
        return self.workspace_path / "SOUL.md"

    @property
    def agents_md_path(self) -> Path:
        return self.workspace_path / "AGENTS.md"

    @property
    def memory_md_path(self) -> Path:
        return self.workspace_path / "MEMORY.md"

    @property
    def user_md_path(self) -> Path:
        return self.workspace_path / "USER.md"


# Singleton
_settings: Optional[NexSettings] = None


def get_settings() -> NexSettings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = NexSettings()
        _settings.ensure_dirs()
    return _settings
