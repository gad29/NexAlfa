"""
NexAlfa Error System
Every error returns: code, message, and a fix suggestion so the user always knows what to do.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    # Auth / Provider
    AUTH_FAILED = "AUTH_FAILED"
    API_KEY_MISSING = "API_KEY_MISSING"
    API_KEY_INVALID = "API_KEY_INVALID"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"

    # Model
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    MODEL_OVERLOADED = "MODEL_OVERLOADED"
    RATE_LIMITED = "RATE_LIMITED"
    CONTEXT_EXCEEDED = "CONTEXT_EXCEEDED"
    ALL_MODELS_FAILED = "ALL_MODELS_FAILED"

    # Tools
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    BROWSER_FAILED = "BROWSER_FAILED"

    # Channels
    CHANNEL_DISCONNECTED = "CHANNEL_DISCONNECTED"
    CHANNEL_AUTH_FAILED = "CHANNEL_AUTH_FAILED"
    CHANNEL_NOT_CONFIGURED = "CHANNEL_NOT_CONFIGURED"
    WHATSAPP_QR_EXPIRED = "WHATSAPP_QR_EXPIRED"

    # Files / Documents
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_READ_ERROR = "FILE_READ_ERROR"
    FILE_WRITE_ERROR = "FILE_WRITE_ERROR"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"

    # Voice
    STT_FAILED = "STT_FAILED"
    TTS_FAILED = "TTS_FAILED"
    FFMPEG_NOT_FOUND = "FFMPEG_NOT_FOUND"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"

    # Sub-agents
    SUBAGENT_NOT_FOUND = "SUBAGENT_NOT_FOUND"
    SUBAGENT_FAILED = "SUBAGENT_FAILED"
    SUBAGENT_LIMIT_REACHED = "SUBAGENT_LIMIT_REACHED"

    # System
    GATEWAY_ERROR = "GATEWAY_ERROR"
    MEMORY_ERROR = "MEMORY_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"
    UNKNOWN = "UNKNOWN"


# Human-readable fix suggestions for each error code
ERROR_FIXES: dict[ErrorCode, str] = {
    ErrorCode.AUTH_FAILED: "Check your API key. Run: nexalfa set provider <name> --key <YOUR_KEY>",
    ErrorCode.API_KEY_MISSING: "No API key found. Add it to .env or run: nexalfa set provider <name> --key <KEY>",
    ErrorCode.API_KEY_INVALID: "The API key was rejected. Get a new key from your provider's dashboard.",
    ErrorCode.PROVIDER_UNAVAILABLE: "Provider is down or unreachable. Check your internet or try a different provider.",
    ErrorCode.MODEL_NOT_FOUND: "Model not found. Check the model name or use Settings → Model to pick one.",
    ErrorCode.MODEL_OVERLOADED: "Model is overloaded. Wait a moment or switch to a different model.",
    ErrorCode.RATE_LIMITED: "Rate limit hit. Wait 30 seconds, or switch to a fallback model.",
    ErrorCode.CONTEXT_EXCEEDED: "Context window full. Use /compact to compress history, or start a /new session.",
    ErrorCode.ALL_MODELS_FAILED: "All configured models failed. Check your API keys and internet connection.",
    ErrorCode.TOOL_NOT_FOUND: "Tool not found. Available tools are listed in /status.",
    ErrorCode.TOOL_EXECUTION_FAILED: "A tool failed to execute. Check the error details below.",
    ErrorCode.TOOL_TIMEOUT: "Tool timed out. Try again or check if the target is responding.",
    ErrorCode.BROWSER_FAILED: "Browser automation failed. Run: playwright install chromium",
    ErrorCode.CHANNEL_DISCONNECTED: "Channel disconnected. Run: nexalfa connect <channel>",
    ErrorCode.CHANNEL_AUTH_FAILED: "Channel auth failed. Check the token/credentials in .env",
    ErrorCode.CHANNEL_NOT_CONFIGURED: "Channel not configured. Add credentials to .env, then: nexalfa connect <channel>",
    ErrorCode.WHATSAPP_QR_EXPIRED: "WhatsApp QR expired. Run: nexalfa connect whatsapp (to get a new QR)",
    ErrorCode.FILE_NOT_FOUND: "File not found. Check the path and try again.",
    ErrorCode.FILE_READ_ERROR: "Cannot read file. Check permissions and file format.",
    ErrorCode.FILE_WRITE_ERROR: "Cannot write file. Check permissions and disk space.",
    ErrorCode.UNSUPPORTED_FORMAT: "File format not supported. Supported: PDF, DOCX, TXT, CSV, XLSX, JSON, YAML, MD, HTML",
    ErrorCode.STT_FAILED: "Speech-to-text failed. Check your STT provider key and audio format.",
    ErrorCode.TTS_FAILED: "Text-to-speech failed. Check your TTS provider key.",
    ErrorCode.FFMPEG_NOT_FOUND: "FFmpeg not found. Install it: apt install ffmpeg (Linux) or choco install ffmpeg (Windows)",
    ErrorCode.AUDIO_TOO_LONG: "Audio too long (max 25 minutes). Split into smaller clips.",
    ErrorCode.SUBAGENT_NOT_FOUND: "Sub-agent not found. List available agents with /agents or nexalfa agents list",
    ErrorCode.SUBAGENT_FAILED: "Sub-agent failed. Check its workspace logs.",
    ErrorCode.SUBAGENT_LIMIT_REACHED: "Too many sub-agents running. Stop one first: nexalfa agents stop <name>",
    ErrorCode.GATEWAY_ERROR: "Gateway error. Restart the gateway: nexalfa gateway",
    ErrorCode.MEMORY_ERROR: "Memory system error. Try: nexalfa doctor",
    ErrorCode.CONFIG_ERROR: "Configuration error. Check your .env file or run: nexalfa doctor",
    ErrorCode.UNKNOWN: "An unknown error occurred. Check logs for details.",
}


class NexError(Exception):
    """Base NexAlfa error with structured info."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.UNKNOWN,
        message: str = "",
        fix: Optional[str] = None,
        details: Optional[dict] = None,
        cause: Optional[Exception] = None,
    ):
        self.code = code
        self.message = message or f"Error: {code.value}"
        self.fix = fix or ERROR_FIXES.get(code, "Check logs for details.")
        self.details = details or {}
        self.cause = cause
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Serialize for API/Socket.IO responses."""
        d = {
            "error": True,
            "code": self.code.value,
            "message": self.message,
            "fix": self.fix,
        }
        if self.details:
            d["details"] = self.details
        if self.cause:
            d["cause"] = f"{type(self.cause).__name__}: {self.cause}"
        return d

    def to_user_message(self) -> str:
        """Format for display in chat."""
        parts = [f"❌ **{self.code.value}**: {self.message}"]
        if self.fix:
            parts.append(f"💡 **Fix**: {self.fix}")
        if self.cause:
            parts.append(f"🔍 **Cause**: `{type(self.cause).__name__}: {self.cause}`")
        return "\n".join(parts)


# ── Convenience subclasses ─────────────────────────────────

class AuthError(NexError):
    def __init__(self, message: str = "Authentication failed", **kw):
        super().__init__(ErrorCode.AUTH_FAILED, message, **kw)

class ModelError(NexError):
    def __init__(self, code: ErrorCode = ErrorCode.MODEL_NOT_FOUND, message: str = "", **kw):
        super().__init__(code, message, **kw)

class ToolError(NexError):
    def __init__(self, tool_name: str = "", message: str = "", **kw):
        details = kw.pop("details", {})
        details["tool"] = tool_name
        super().__init__(ErrorCode.TOOL_EXECUTION_FAILED, message or f"Tool '{tool_name}' failed", details=details, **kw)

class ChannelError(NexError):
    def __init__(self, channel: str = "", code: ErrorCode = ErrorCode.CHANNEL_DISCONNECTED, message: str = "", **kw):
        details = kw.pop("details", {})
        details["channel"] = channel
        super().__init__(code, message or f"Channel '{channel}' error", details=details, **kw)

class FileError(NexError):
    def __init__(self, path: str = "", code: ErrorCode = ErrorCode.FILE_NOT_FOUND, message: str = "", **kw):
        details = kw.pop("details", {})
        details["path"] = path
        super().__init__(code, message or f"File error: {path}", details=details, **kw)

class VoiceError(NexError):
    def __init__(self, code: ErrorCode = ErrorCode.STT_FAILED, message: str = "", **kw):
        super().__init__(code, message, **kw)


def classify_llm_error(error: Exception) -> NexError:
    """Classify a raw LLM/LiteLLM exception into a structured NexError."""
    msg = str(error).lower()

    # Auto-revert from model router — model was bad, reverted to working one
    if "auto-reverted" in msg:
        return NexError(
            ErrorCode.MODEL_NOT_FOUND,
            str(error),
            fix="The model you switched to doesn't work. I've reverted to the last working model. Try your request again.",
            cause=error,
        )

    if "all models failed" in msg:
        return NexError(ErrorCode.ALL_MODELS_FAILED, str(error), cause=error)
    if "authentication" in msg or "api key" in msg or "invalid api" in msg or "401" in msg:
        return NexError(ErrorCode.API_KEY_INVALID, str(error), cause=error)
    if "rate limit" in msg or "429" in msg or "too many requests" in msg:
        return NexError(ErrorCode.RATE_LIMITED, str(error), cause=error)
    if "model not found" in msg or "does not exist" in msg or "404" in msg:
        return NexError(ErrorCode.MODEL_NOT_FOUND, str(error), cause=error)
    if "context" in msg and ("length" in msg or "exceed" in msg or "too long" in msg):
        return NexError(ErrorCode.CONTEXT_EXCEEDED, str(error), cause=error)
    if "overloaded" in msg or "503" in msg or "capacity" in msg:
        return NexError(ErrorCode.MODEL_OVERLOADED, str(error), cause=error)
    if "timeout" in msg:
        return NexError(ErrorCode.PROVIDER_UNAVAILABLE, f"Provider timed out: {error}", cause=error)
    return NexError(ErrorCode.UNKNOWN, str(error), cause=error)
