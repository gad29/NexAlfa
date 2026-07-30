"""
NexAlfa Model Router
Multi-provider LLM routing via LiteLLM — OpenAI, Google, OpenRouter, Ollama.
Supports streaming, thinking levels, and automatic failover.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional

import litellm
from litellm import acompletion

from agent.config.settings import get_settings
from agent.auth.oauth_sink import auth_sink

logger = logging.getLogger("nex.models")

# Suppress litellm noise
litellm.suppress_debug_info = True
litellm.drop_params = True


class ThinkingLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ModelResponse:
    """Normalized model response."""

    content: str
    thinking: Optional[str] = None
    model: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    raw: Any = None


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""

    content: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: Optional[str] = None
    is_thinking: bool = False


class ModelRouter:
    """
    Routes LLM calls to the right provider via LiteLLM.
    Supports failover, streaming, tool calling, and thinking levels.
    Inspired by Hermes Agent's provider-agnostic approach.
    """

    def __init__(self):
        settings = get_settings()
        self._current_model = settings.model.default_model
        self._fallback_models = settings.model.fallback_models
        self._temperature = settings.model.temperature
        self._max_tokens = settings.model.max_tokens
        self._streaming = settings.model.streaming
        self._thinking_level = ThinkingLevel.MEDIUM
        self._last_working_model = self._current_model  # Track last known good model
        self._setup_keys()

    def _setup_keys(self):
        """Set API keys in environment for LiteLLM."""
        import os
        from dotenv import load_dotenv

        # Ensure .env is loaded (pydantic-settings may not push nested values to os.environ)
        load_dotenv(override=False)

        settings = get_settings()

        # Set keys from settings (which reads .env via pydantic-settings)
        # AND fallback to reading .env directly (for nested model fields)
        if settings.model.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.model.openai_api_key
        elif os.environ.get("OPENAI_API_KEY"):
            pass  # Already set from .env
        
        if settings.model.google_api_key:
            os.environ["GOOGLE_API_KEY"] = settings.model.google_api_key
            os.environ["GEMINI_API_KEY"] = settings.model.google_api_key
        elif os.environ.get("GOOGLE_API_KEY"):
            os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

        if settings.model.openrouter_api_key:
            os.environ["OPENROUTER_API_KEY"] = settings.model.openrouter_api_key

        if settings.model.ollama_base_url:
            os.environ["OLLAMA_API_BASE"] = settings.model.ollama_base_url

        # Log what's configured
        configured = []
        if os.environ.get("OPENAI_API_KEY"):
            configured.append("OpenAI")
        if os.environ.get("GOOGLE_API_KEY"):
            configured.append("Google")
        if os.environ.get("OPENROUTER_API_KEY"):
            configured.append("OpenRouter")
        if os.environ.get("OLLAMA_API_BASE"):
            configured.append("Ollama")
        logger.info(f"Model providers configured: {', '.join(configured) or 'None!'}")

    @property
    def current_model(self) -> str:
        return self._current_model

    @property
    def thinking_level(self) -> ThinkingLevel:
        return self._thinking_level

    def set_model(self, model: str):
        """Switch the active model. Format: provider/model-id"""
        old = self._current_model
        logger.info(f"Model switched: {old} → {model}")
        self._current_model = model

    def revert_model(self):
        """Revert to the last known working model."""
        if self._last_working_model and self._last_working_model != self._current_model:
            logger.warning(f"Reverting model: {self._current_model} → {self._last_working_model}")
            self._current_model = self._last_working_model
            return self._current_model
        return None

    def set_thinking_level(self, level: ThinkingLevel):
        """Set the reasoning/thinking depth."""
        self._thinking_level = level
        logger.info(f"Thinking level: {level.value}")

    def _build_params(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        stream: Optional[bool] = None,
        **kwargs,
    ) -> dict:
        """Build the LiteLLM completion params."""
        params = {
            "model": self._current_model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self._temperature),
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "stream": stream if stream is not None else self._streaming,
        }

        if tools:
            params["tools"] = tools
            params["tool_choice"] = kwargs.get("tool_choice", "auto")

        # Thinking/reasoning params (provider-specific)
        if self._thinking_level != ThinkingLevel.NONE:
            model_lower = self._current_model.lower()
            if "claude" in model_lower or "anthropic" in model_lower:
                # Anthropic extended thinking
                budget_map = {
                    ThinkingLevel.LOW: 2048,
                    ThinkingLevel.MEDIUM: 8192,
                    ThinkingLevel.HIGH: 32768,
                }
                params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": budget_map.get(self._thinking_level, 8192),
                }
            elif "ollama" in model_lower:
                # Ollama think parameter
                params["think"] = True

        return params

    async def _g4f_complete(self, model: str, messages: list[dict], tools: Optional[list[dict]] = None, **kwargs) -> ModelResponse:
        import g4f
        from g4f.client import AsyncClient
        
        provider_name = model.split("/", 1)[1] if "/" in model else model
        # Try to match provider name
        provider = getattr(g4f.Provider, provider_name, None)
        
        access_token = auth_sink.get_token(provider_name)
        
        client = AsyncClient(
            provider=provider
        )
        
        response = await client.chat.completions.create(
            model="", # The provider determines the model or we can pass it
            messages=messages,
            api_key=access_token # pass token if available
        )
        
        content = response.choices[0].message.content or ""
        return ModelResponse(
            content=content,
            model=model,
            finish_reason="stop",
            raw=response
        )

    async def _g4f_stream(self, model: str, messages: list[dict], tools: Optional[list[dict]] = None, **kwargs) -> AsyncIterator[StreamChunk]:
        import g4f
        from g4f.client import AsyncClient
        
        provider_name = model.split("/", 1)[1] if "/" in model else model
        provider = getattr(g4f.Provider, provider_name, None)
        
        access_token = auth_sink.get_token(provider_name)
        
        client = AsyncClient(
            provider=provider
        )
        
        response = await client.chat.completions.create(
            model="",
            messages=messages,
            api_key=access_token,
            stream=True
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield StreamChunk(
                    content=chunk.choices[0].delta.content,
                    finish_reason=chunk.choices[0].finish_reason
                )

    async def complete(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Non-streaming completion with automatic failover."""
        models_to_try = [self._current_model] + self._fallback_models
        last_error = None

        # Extract stream from kwargs to avoid duplicate keyword in _build_params
        kwargs.pop("stream", None)

        for model in models_to_try:
            try:
                if model.startswith("oauth/"):
                    response = await self._g4f_complete(model, messages, tools, **kwargs)
                    self._last_working_model = model
                    return response

                params = self._build_params(messages, tools, stream=False, **kwargs)
                params["model"] = model
                try:
                    response = await acompletion(**params)
                except Exception as e:
                    err_msg = str(e).lower()
                    # Retry without custom temperature if model doesn't support it
                    if "temperature" in err_msg and ("not support" in err_msg or "unsupported" in err_msg):
                        logger.info(f"Retrying {model} with default temperature...")
                        params.pop("temperature", None)
                        response = await acompletion(**params)
                    else:
                        raise  # Re-raise to outer except

                choice = response.choices[0]
                content = choice.message.content or ""
                thinking = None
                tool_calls_data = []

                # Extract thinking content if present
                if hasattr(choice.message, "thinking") and choice.message.thinking:
                    thinking = choice.message.thinking

                # Extract tool calls
                if choice.message.tool_calls:
                    for tc in choice.message.tool_calls:
                        tool_calls_data.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        })

                # Mark this model as working
                self._last_working_model = model

                return ModelResponse(
                    content=content,
                    thinking=thinking,
                    model=model,
                    usage=dict(response.usage) if response.usage else {},
                    finish_reason=choice.finish_reason or "",
                    tool_calls=tool_calls_data,
                    raw=response,
                )
            except Exception as e:
                last_error = e
                logger.warning(f"Model {model} failed: {type(e).__name__}: {e}")
                continue

        # All models failed — try to auto-revert to last known working model
        reverted = self.revert_model()
        if reverted:
            logger.warning(f"Auto-reverted to working model: {reverted}")
            raise RuntimeError(
                f"Model `{models_to_try[0]}` failed. Auto-reverted to `{reverted}`. "
                f"Try your request again. (Error: {last_error})"
            )

        logger.error(f"All {len(models_to_try)} models failed. Last error: {last_error}")
        raise RuntimeError(f"All models failed. Last error: {last_error}")

    async def stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming completion with automatic failover."""
        models_to_try = [self._current_model] + self._fallback_models
        last_error = None

        # Extract stream from kwargs to avoid duplicate keyword in _build_params
        kwargs.pop("stream", None)

        for model in models_to_try:
            try:
                if model.startswith("oauth/"):
                    async for chunk in self._g4f_stream(model, messages, tools, **kwargs):
                        yield chunk
                    return

                params = self._build_params(messages, tools, stream=True, **kwargs)
                params["model"] = model
                response = await acompletion(**params)

                async for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    finish = chunk.choices[0].finish_reason

                    sc = StreamChunk(finish_reason=finish)

                    if hasattr(delta, "content") and delta.content:
                        sc.content = delta.content
                    if hasattr(delta, "thinking") and delta.thinking:
                        sc.thinking = delta.thinking
                        sc.is_thinking = True
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc in delta.tool_calls:
                            sc.tool_calls.append({
                                "index": tc.index,
                                "id": getattr(tc, "id", None),
                                "function": {
                                    "name": getattr(tc.function, "name", ""),
                                    "arguments": getattr(tc.function, "arguments", ""),
                                },
                            })
                    yield sc

                return  # Success, don't try fallbacks
            except Exception as e:
                last_error = e
                logger.warning(f"Stream from {model} failed: {e}, trying next...")
                continue

        raise RuntimeError(f"All models failed for streaming. Last error: {last_error}")

    def get_available_models(self) -> list[str]:
        """List configured model identifiers."""
        models = [self._current_model] + self._fallback_models
        return list(dict.fromkeys(models))  # dedupe preserving order

    def get_status(self) -> dict:
        """Current model router status."""
        return {
            "current_model": self._current_model,
            "thinking_level": self._thinking_level.value,
            "fallback_models": self._fallback_models,
            "streaming": self._streaming,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
