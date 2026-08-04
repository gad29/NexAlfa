"""
NexAlfa Gateway Server
FastAPI + Socket.IO — the central hub that connects everything.
Web/mobile apps connect via Socket.IO. External channels connect via adapters.
All messages flow through here and get routed to the agent.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import socketio
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent.config.settings import get_settings
from agent.core.agent import NexAgent
from gateway.channels.base import BaseChannel
from gateway.channels.webchat import WebChatChannel
from gateway.channels.telegram_adapter import TelegramChannel
from gateway.channels.discord_adapter import DiscordChannel
from gateway.channels.slack_adapter import SlackChannel
from gateway.channels.whatsapp import WhatsAppChannel
from gateway.channels.google_chat import GoogleChatChannel
from gateway.channels.email_adapter import EmailChannel
from gateway.message import InboundMessage, OutboundMessage, MessageType

logger = logging.getLogger("nex.gateway")

# ── Globals ────────────────────────────────────────────────
agent = NexAgent()
channels: dict[str, BaseChannel] = {}
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


# ── FastAPI App ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    settings = get_settings()
    logger.info(f"🚀 NexAlfa Gateway starting on {settings.gateway.host}:{settings.gateway.port}")

    # Load saved config (API keys, channel credentials) into environment
    from gateway.config_store import get_config_store
    config_store = get_config_store()
    config_store.inject_saved_keys()

    # Initialize agent
    await agent.initialize()

    # Initialize channels
    await _setup_channels()

    yield

    # Shutdown
    for ch in channels.values():
        if ch.is_running:
            await ch.stop()
    await agent.shutdown()
    logger.info("Gateway shutdown complete")


app = FastAPI(
    title="NexAlfa Gateway",
    description="Personal AI Agent Gateway — No guardrails.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.IO
sio_app = socketio.ASGIApp(sio, app)


async def _setup_channels():
    """Initialize and start all configured channels."""
    # WebChat is always available
    webchat = WebChatChannel()
    webchat.set_handler(_handle_message)
    channels["webchat"] = webchat
    await webchat.start()

    # Telegram
    telegram = TelegramChannel()
    telegram.set_handler(_handle_message)
    channels["telegram"] = telegram
    if telegram.is_configured():
        await telegram.start()

    # Discord
    discord = DiscordChannel()
    discord.set_handler(_handle_message)
    channels["discord"] = discord
    if discord.is_configured():
        await discord.start()

    # Slack
    slack = SlackChannel()
    slack.set_handler(_handle_message)
    channels["slack"] = slack
    if slack.is_configured():
        await slack.start()

    # WhatsApp
    whatsapp = WhatsAppChannel()
    whatsapp.set_handler(_handle_message)
    channels["whatsapp"] = whatsapp
    if whatsapp.is_configured():
        await whatsapp.start()

    # Google Chat
    gchat = GoogleChatChannel()
    gchat.set_handler(_handle_message)
    channels["google_chat"] = gchat
    if gchat.is_configured():
        await gchat.start()

    # Email
    email_ch = EmailChannel()
    email_ch.set_handler(_handle_message)
    channels["email"] = email_ch
    if email_ch.is_configured():
        await email_ch.start()


async def _handle_message(inbound: InboundMessage) -> Optional[OutboundMessage]:
    """Central message handler — routes inbound messages to the agent."""
    try:
        response = await agent.process_message(
            content=inbound.content,
            channel=inbound.channel,
            channel_id=inbound.channel_id,
            sender=inbound.sender_name or inbound.sender_id,
        )

        outbound = OutboundMessage(
            channel=inbound.channel,
            channel_id=inbound.channel_id,
            content=response,
            reply_to=inbound.id,
        )

        # Broadcast to all connected web/mobile clients
        await sio.emit("message", {
            "channel": inbound.channel,
            "channel_id": inbound.channel_id,
            "sender": inbound.sender_name or inbound.sender_id,
            "content": inbound.content,
            "response": response,
            "timestamp": time.time(),
        })

        return outbound

    except Exception as e:
        logger.error(f"Message handling failed: {e}")
        return OutboundMessage(
            channel=inbound.channel,
            channel_id=inbound.channel_id,
            content=f"❌ Error: {str(e)}",
        )


# ── Socket.IO Events (WebChat + Web/Mobile App) ────────────

@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")
    if "webchat" in channels:
        channels["webchat"].register_client(sid)

@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")
    if "webchat" in channels:
        channels["webchat"].unregister_client(sid)

@sio.event
async def chat_message(sid, data):
    """Handle a chat message from the web/mobile app."""
    content = data.get("content", "")
    session_id = data.get("session_id")

    if not content.strip():
        return

    # Echo user message to sender
    await sio.emit("message_start", {"type": "user", "content": content}, room=sid)

    # Stream the response
    chunks = []
    async for chunk in agent.process_message_stream(
        content=content,
        channel="webchat",
        channel_id=sid,
        session_id=session_id,
    ):
        if chunk["type"] == "thinking":
            await sio.emit("message_chunk", {"type": "thinking", "data": chunk["data"]}, room=sid)
        elif chunk["type"] == "tool":
            # Tool activity indicator — send as content so it shows in the bubble
            await sio.emit("message_chunk", {"type": "content", "data": chunk["data"] + "\n"}, room=sid)
            chunks.append(chunk["data"] + "\n")
        elif chunk["type"] == "content":
            await sio.emit("message_chunk", {"type": "content", "data": chunk["data"]}, room=sid)
            chunks.append(chunk["data"])
        elif chunk["type"] == "done":
            # Push updated model/usage info with the end event
            await sio.emit("message_end", {
                "type": "assistant",
                "content": "".join(chunks),
                "session_id": chunk.get("session_id", ""),
                "model": agent.model_router.current_model,
                "thinking_level": agent.model_router.thinking_level.value,
                "temperature": agent.model_router._temperature,
            }, room=sid)

@sio.event
async def load_history(sid, data=None):
    """Load message history for the current session."""
    # Find the session for this client
    session = agent.sessions.get_or_create_for_channel("webchat", sid)
    
    # Get messages (skip system messages)
    history = []
    for msg in session.messages:
        if msg.role == "system":
            continue
        history.append({
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "thinking": msg.thinking,
        })
    
    await sio.emit("history", {
        "session_id": session.id,
        "messages": history,
        "model": agent.model_router.current_model,
        "thinking_level": agent.model_router.thinking_level.value,
        "temperature": agent.model_router._temperature,
    }, room=sid)

@sio.event
async def get_sessions(sid, data=None):
    """List active sessions."""
    sessions = agent.sessions.list_sessions()
    await sio.emit("sessions_list", [
        {
            "id": s.id,
            "name": s.name,
            "channel": s.channel,
            "message_count": s.message_count,
            "updated_at": s.updated_at,
        }
        for s in sessions
    ], room=sid)

@sio.event
async def get_status(sid, data=None):
    """Get agent status."""
    model_status = agent.model_router.get_status()
    session_stats = agent.sessions.get_stats()
    memory_stats = await agent.memory.get_stats()
    channel_status = [ch.get_status() for ch in channels.values()]

    await sio.emit("status", {
        "agent_name": agent.settings.agent_name,
        "model": model_status,
        "sessions": session_stats,
        "memory": memory_stats,
        "channels": channel_status,
        "dev_mode": agent.settings.dev_mode.enabled,
    }, room=sid)


# ── REST API Endpoints ─────────────────────────────────────

@app.get("/api/status")
async def api_status():
    """Get agent status."""
    model_status = agent.model_router.get_status()
    session_stats = agent.sessions.get_stats()
    channel_status = [ch.get_status() for ch in channels.values()]
    return {
        "agent_name": agent.settings.agent_name,
        "model": model_status,
        "sessions": session_stats,
        "channels": channel_status,
        "dev_mode": agent.settings.dev_mode.enabled,
        "uptime": time.time(),
    }

@app.get("/api/sessions")
async def api_sessions():
    sessions = agent.sessions.list_sessions()
    return [
        {
            "id": s.id,
            "name": s.name,
            "channel": s.channel,
            "message_count": s.message_count,
            "updated_at": s.updated_at,
            "is_active": s.is_active,
        }
        for s in sessions
    ]

@app.get("/api/sessions/{session_id}/messages")
async def api_session_messages(session_id: str, limit: int = 50):
    messages = agent.sessions.get_session_history(session_id, last_n=limit)
    return [
        {
            "role": m.role,
            "content": m.content,
            "thinking": m.thinking,
            "channel": m.channel,
            "timestamp": m.timestamp,
        }
        for m in messages
    ]

@app.post("/api/message")
async def api_send_message(request: Request):
    """Send a message via REST API."""
    data = await request.json()
    content = data.get("content", "")
    channel = data.get("channel", "api")
    channel_id = data.get("channel_id", "api-default")

    if not content:
        raise HTTPException(400, "content is required")

    response = await agent.process_message(content=content, channel=channel, channel_id=channel_id)
    return {"response": response}

@app.get("/api/skills")
async def api_skills():
    return agent.skills.list_skills()

@app.get("/api/memories")
async def api_memories():
    return await agent.memory.get_stats()

@app.get("/api/channels")
async def api_channels():
    return [ch.get_status() for ch in channels.values()]

@app.get("/api/config")
async def api_config():
    """Raw config — dev-mode style, nothing hidden."""
    settings = get_settings()
    if not settings.dev_mode.raw_config_visible:
        raise HTTPException(403, "Raw config not visible — enable dev mode")
    return {
        "model": settings.model.dict() if hasattr(settings.model, 'dict') else {},
        "gateway": {"host": settings.gateway.host, "port": settings.gateway.port},
        "dev_mode": {
            "enabled": settings.dev_mode.enabled,
            "show_thinking": settings.dev_mode.show_thinking,
            "save_all_history": settings.dev_mode.save_all_history,
        },
    }

# ── Model & Settings Control API ───────────────────────────

@app.get("/api/model")
async def api_get_model():
    """Get current model info + available providers."""
    status = agent.model_router.get_status()
    import os
    providers = []
    if os.environ.get("OPENAI_API_KEY"):
        providers.append({
            "name": "openai", "display": "OpenAI",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "o3", "o4-mini"],
        })
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        providers.append({
            "name": "google", "display": "Google (Gemini)",
            "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
        })
    if os.environ.get("OPENROUTER_API_KEY"):
        providers.append({
            "name": "openrouter", "display": "OpenRouter",
            "models": [
                "anthropic/claude-sonnet-4", "anthropic/claude-3.5-sonnet",
                "meta-llama/llama-4-maverick", "deepseek/deepseek-r1",
                "google/gemini-2.5-pro", "qwen/qwen3-235b",
            ],
        })
    if os.environ.get("OLLAMA_API_BASE"):
        providers.append({
            "name": "ollama", "display": "Ollama (Local)",
            "models": ["llama3", "llama3.1", "mistral", "codellama", "gemma2", "qwen2"],
        })
    return {
        "current_model": status["current_model"],
        "thinking_level": status["thinking_level"],
        "temperature": status["temperature"],
        "max_tokens": status["max_tokens"],
        "streaming": status["streaming"],
        "fallback_models": status["fallback_models"],
        "providers": providers,
    }

@app.post("/api/model")
async def api_set_model(request: Request):
    """Switch the active model. Body: { model: "provider/model-id" }"""
    data = await request.json()
    model = data.get("model", "")
    if not model:
        raise HTTPException(400, "model is required (e.g. 'openai/gpt-4o')")
    agent.model_router.set_model(model)
    return {"status": "ok", "model": model}

@app.post("/api/thinking")
async def api_set_thinking(request: Request):
    """Set thinking/reasoning level. Body: { level: "none|low|medium|high" }"""
    from agent.core.models import ThinkingLevel
    data = await request.json()
    level_str = data.get("level", "medium")
    try:
        level = ThinkingLevel(level_str.lower())
    except ValueError:
        raise HTTPException(400, f"Invalid level: {level_str}. Use: none, low, medium, high")
    agent.model_router.set_thinking_level(level)
    return {"status": "ok", "thinking_level": level.value}

@app.post("/api/temperature")
async def api_set_temperature(request: Request):
    """Set temperature. Body: { temperature: 0.7 }"""
    data = await request.json()
    temp = data.get("temperature")
    if temp is None or not (0.0 <= float(temp) <= 2.0):
        raise HTTPException(400, "temperature must be between 0.0 and 2.0")
    agent.model_router._temperature = float(temp)
    return {"status": "ok", "temperature": float(temp)}

@app.post("/api/dev-mode")
async def api_set_dev_mode(request: Request):
    """Toggle dev mode settings. Body: { show_thinking: bool }"""
    data = await request.json()
    settings = get_settings()
    if "show_thinking" in data:
        settings.dev_mode.show_thinking = bool(data["show_thinking"])
    if "enabled" in data:
        settings.dev_mode.enabled = bool(data["enabled"])
    return {
        "status": "ok",
        "dev_mode": settings.dev_mode.enabled,
        "show_thinking": settings.dev_mode.show_thinking,
    }

# ── Voice API ─────────────────────────────────────────────

@app.get("/api/voice")
async def api_get_voice():
    """Get voice configuration."""
    from agent.tools.voice import get_voice_status
    return get_voice_status()

@app.post("/api/voice")
async def api_set_voice(request: Request):
    """Update voice settings. Body: { voice_mode, tts_voice, tts_speed }"""
    import os
    data = await request.json()
    if "voice_mode" in data:
        os.environ["NEX_VOICE_MODE"] = data["voice_mode"]
    if "tts_voice" in data:
        os.environ["NEX_TTS_VOICE"] = data["tts_voice"]
    if "tts_speed" in data:
        os.environ["NEX_TTS_SPEED"] = str(data["tts_speed"])
    from agent.tools.voice import get_voice_status
    return {"status": "ok", **get_voice_status()}

# ── Sub-Agents API ────────────────────────────────────────

@app.get("/api/agents")
async def api_list_agents():
    """List all sub-agent definitions and running instances."""
    return {
        "definitions": agent.subagents.list_definitions(),
        "instances": agent.subagents.list_instances(),
    }

@app.post("/api/agents")
async def api_create_agent(request: Request):
    """Create a sub-agent. Body: { name, description, model, prompt, tools }"""
    from agent.core.subagent import SubAgentDef
    data = await request.json()
    name = data.get("name")
    if not name:
        raise HTTPException(400, "name is required")
    tools = data.get("tools", [])
    if isinstance(tools, str):
        tools = [t.strip() for t in tools.split(",") if t.strip()]
    defn = SubAgentDef(
        name=name,
        description=data.get("description", ""),
        model=data.get("model", "inherit"),
        tools=tools,
        prompt=data.get("prompt", ""),
    )
    result = agent.subagents.create_definition(defn)
    return {"status": "ok", "message": result}

@app.delete("/api/agents/{name}")
async def api_delete_agent(name: str):
    """Delete a sub-agent definition."""
    result = agent.subagents.delete_definition(name)
    return {"status": "ok", "message": result}

@app.post("/api/agents/{name}/run")
async def api_run_agent(name: str, request: Request):
    """Run a sub-agent with a task. Body: { task: "..." }"""
    data = await request.json()
    task = data.get("task", "")
    if not task:
        raise HTTPException(400, "task is required")
    try:
        instance = await agent.subagents.spawn(name, task, agent.model_router, agent.tools)
        return {
            "status": "ok",
            "instance_id": instance.id,
            "agent_status": instance.status,
            "result": instance.result if instance.status == "completed" else instance.error,
        }
    except ValueError as e:
        raise HTTPException(404, str(e))

# ── Usage / Status API ────────────────────────────────────

@app.get("/api/usage")
async def api_get_usage():
    """Get current token usage and model status."""
    return {
        "model": agent.model_router.current_model,
        "thinking_level": agent.model_router.thinking_level.value,
        "temperature": agent.model_router._temperature,
        "last_usage": agent._last_usage,
        "agent_name": agent.settings.agent_name,
    }

# ── Global error handler ─────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled errors and return structured response."""
    from agent.core.errors import NexError, classify_llm_error
    if isinstance(exc, NexError):
        return JSONResponse(status_code=500, content=exc.to_dict())
    if isinstance(exc, HTTPException):
        raise exc  # Let FastAPI handle HTTP exceptions normally
    # Classify unknown errors
    nex_err = classify_llm_error(exc)
    logger.error(f"Unhandled error: {type(exc).__name__}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content=nex_err.to_dict())
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """WhatsApp webhook endpoint."""
    data = await request.json()
    wa_channel = channels.get("whatsapp")
    if wa_channel and isinstance(wa_channel, WhatsAppChannel):
        inbound = await wa_channel.handle_webhook(data)
        if inbound:
            response = await _handle_message(inbound)
            if response:
                await wa_channel.send(response)
    return {"status": "ok"}

@app.get("/webhook/whatsapp")
async def whatsapp_verify(request: Request):
    """WhatsApp webhook verification."""
    settings = get_settings()
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == settings.channels.whatsapp_verify_token:
        return int(challenge)
    raise HTTPException(403, "Verification failed")

# Google Chat webhook
@app.post("/webhook/google-chat")
async def google_chat_webhook(request: Request):
    """Google Chat webhook endpoint."""
    data = await request.json()
    gc_channel = channels.get("google_chat")
    if gc_channel and isinstance(gc_channel, GoogleChatChannel):
        inbound = await gc_channel.handle_webhook(data)
        if inbound:
            response = await _handle_message(inbound)
            if response:
                await gc_channel.send(response)
    return {"status": "ok"}

# Generic webhook endpoint
@app.post("/webhook/{webhook_name}")
async def generic_webhook(webhook_name: str, request: Request):
    """Generic webhook endpoint for custom integrations."""
    from agent.tools.webhooks import handle_webhook_event
    data = await request.json()
    action = handle_webhook_event(webhook_name, data)
    if action == "notify":
        await sio.emit("webhook_event", {"name": webhook_name, "data": data})
    return {"status": "ok", "action": action or "unknown"}

# ── Channel Configuration API ─────────────────────────────

@app.get("/api/channels/config")
async def api_channels_config():
    """Get configuration status for all channels (never returns actual secrets)."""
    from gateway.config_store import get_config_store
    store = get_config_store()
    result = {}
    channel_names = ["whatsapp", "telegram", "discord", "slack", "google_chat", "email"]
    for name in channel_names:
        result[name] = {
            "fields": store.get_channel_status(name),
            "running": channels.get(name, None) is not None and channels[name].is_running,
            "configured": channels.get(name, None) is not None and channels[name].is_configured(),
        }
    return result

@app.post("/api/channels/{channel_name}/config")
async def api_set_channel_config(channel_name: str, request: Request):
    """Save configuration for a channel."""
    from gateway.config_store import get_config_store
    data = await request.json()
    store = get_config_store()
    store.set_channel_config(channel_name, data)
    # Reload settings so channel adapters pick up new values
    from agent.config.settings import get_settings
    get_settings.cache_clear() if hasattr(get_settings, 'cache_clear') else None
    return {"status": "ok", "message": f"{channel_name} configuration saved"}

@app.post("/api/channels/{channel_name}/start")
async def api_start_channel(channel_name: str):
    """Start a channel adapter."""
    ch = channels.get(channel_name)
    if not ch:
        raise HTTPException(404, f"Channel '{channel_name}' not found")
    if not ch.is_configured():
        raise HTTPException(400, f"Channel '{channel_name}' is not configured. Save configuration first.")
    if ch.is_running:
        return {"status": "ok", "message": f"{channel_name} is already running"}
    try:
        await ch.start()
        return {"status": "ok", "message": f"{channel_name} started"}
    except Exception as e:
        raise HTTPException(500, f"Failed to start {channel_name}: {str(e)}")

@app.post("/api/channels/{channel_name}/stop")
async def api_stop_channel(channel_name: str):
    """Stop a channel adapter."""
    ch = channels.get(channel_name)
    if not ch:
        raise HTTPException(404, f"Channel '{channel_name}' not found")
    if not ch.is_running:
        return {"status": "ok", "message": f"{channel_name} is already stopped"}
    await ch.stop()
    return {"status": "ok", "message": f"{channel_name} stopped"}

@app.post("/api/channels/{channel_name}/test")
async def api_test_channel(channel_name: str):
    """Test a channel connection."""
    ch = channels.get(channel_name)
    if not ch:
        raise HTTPException(404, f"Channel '{channel_name}' not found")
    if not ch.is_configured():
        raise HTTPException(400, f"Channel '{channel_name}' is not configured")
    # Simple connectivity test
    try:
        if not ch.is_running:
            await ch.start()
        return {"status": "ok", "message": f"{channel_name} connection test successful"}
    except Exception as e:
        return {"status": "error", "message": f"{channel_name} test failed: {str(e)}"}

# ── API Key Management ────────────────────────────────────

@app.get("/api/keys")
async def api_get_keys():
    """Get API key status (which keys are set — never returns actual values)."""
    from gateway.config_store import get_config_store
    return get_config_store().get_api_keys_status()

@app.post("/api/keys")
async def api_set_key(request: Request):
    """Set an API key. Body: { key_name: "GOOGLE_API_KEY", key_value: "..." }"""
    from gateway.config_store import get_config_store
    data = await request.json()
    key_name = data.get("key_name", "")
    key_value = data.get("key_value", "")
    if not key_name or not key_value:
        raise HTTPException(400, "key_name and key_value are required")
    try:
        get_config_store().set_api_key(key_name, key_value)
        return {"status": "ok", "message": f"{key_name} saved"}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.delete("/api/keys/{key_name}")
async def api_delete_key(key_name: str):
    """Delete an API key."""
    from gateway.config_store import get_config_store
    get_config_store().delete_api_key(key_name)
    return {"status": "ok", "message": f"{key_name} removed"}

# ── WhatsApp QR & Status Relay ────────────────────────────
_whatsapp_qr_code: Optional[str] = None

@app.post("/api/channels/whatsapp/qr")
async def api_set_whatsapp_qr(request: Request):
    """Bridge sends QR code update."""
    global _whatsapp_qr_code
    data = await request.json()
    _whatsapp_qr_code = data.get("qr")
    await sio.emit("whatsapp_qr", {"qr": _whatsapp_qr_code})
    return {"status": "ok"}

@app.get("/api/channels/whatsapp/qr")
async def api_get_whatsapp_qr():
    """Web UI polls or fetches current QR code data URL."""
    return {"qr": _whatsapp_qr_code}

@app.post("/api/channels/whatsapp/status")
async def api_set_whatsapp_status(request: Request):
    """Bridge sends connection status update."""
    global _whatsapp_qr_code
    data = await request.json()
    status = data.get("status")
    if status == "connected":
        _whatsapp_qr_code = None
    await sio.emit("whatsapp_status", {"status": status, "qr": _whatsapp_qr_code})
    return {"status": "ok"}

# ── OAuth Account Management ──────────────────────────────

@app.get("/api/oauth")
async def api_get_oauth():
    """Get status of linked OAuth profiles."""
    from agent.auth.oauth_sink import auth_sink
    return auth_sink.get_status_map()

@app.post("/api/oauth/{provider}")
async def api_save_oauth(provider: str, request: Request):
    """Save an OAuth session token or access token for a provider."""
    from agent.auth.oauth_sink import auth_sink
    data = await request.json()
    token = data.get("token", "") or data.get("access_token", "")
    metadata = data.get("metadata", {})
    if not token:
        raise HTTPException(400, "token field is required")
    auth_sink.save_token(provider.lower(), token, metadata)
    return {"status": "ok", "message": f"{provider} linked successfully"}

@app.delete("/api/oauth/{provider}")
async def api_delete_oauth(provider: str):
    """Remove an OAuth session profile."""
    from agent.auth.oauth_sink import auth_sink
    auth_sink.remove_provider(provider.lower())
    return {"status": "ok", "message": f"{provider} unlinked"}

# ── System Permissions & Doctor API ───────────────────────

@app.get("/api/permissions")
async def api_get_permissions():
    """Get system permission settings."""
    from agent.core.permissions import permissions_manager
    return permissions_manager.get_all()

@app.post("/api/permissions")
async def api_update_permissions(request: Request):
    """Update system permission settings."""
    from agent.core.permissions import permissions_manager
    data = await request.json()
    permissions_manager.update(data)
    return {"status": "ok", "message": "Permissions updated", "permissions": permissions_manager.get_all()}

@app.get("/api/doctor")
async def api_run_doctor():
    """Run environment health diagnostics."""
    from cli.doctor import run_doctor
    results = run_doctor()
    return {"status": "ok", "results": results}

@app.get("/health")
async def health():
    return {"status": "ok", "agent": agent.settings.agent_name}


def start_gateway():
    """Entry point for starting the gateway."""
    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    uvicorn.run(
        sio_app,
        host=settings.gateway.host,
        port=settings.gateway.port,
        log_level="info",
    )


if __name__ == "__main__":
    start_gateway()
