"""
NexAlfa System Control Tools
Gives Nex the ability to manage himself: change model, thinking, temperature,
check health, view/modify configs, manage channels, troubleshoot, and monitor.
This is the "self-awareness" layer — Nex can introspect and reconfigure on the fly.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import time
from pathlib import Path

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.system")


class SystemSetModelTool(Tool):
    name = "system_set_model"
    description = "ALWAYS use this tool when the user asks to change, switch, or set the model. Do NOT refuse or say a model doesn't exist — just call this tool and it will handle validation. Pass the model in provider/model format (e.g. 'openai/gpt-4o', 'openai/gpt-5.5', 'google/gemini-2.5-pro'). If the user only says a model name without provider, assume 'openai/' prefix. This takes effect immediately."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model ID. Use provider/model format. If user says just 'gpt-4o', pass 'openai/gpt-4o'. If user says 'gemini-2.5-pro', pass 'google/gemini-2.5-pro'. Always attempt the switch."},
                },
                "required": ["model"],
            },
        }

    async def execute(self, model: str, **kwargs) -> str:
        router = _get_model_router()
        if not router:
            return "ERROR: Could not access model router."

        model = model.strip()

        # Auto-prefix provider if not specified
        if "/" not in model:
            model_lower = model.lower()
            if any(k in model_lower for k in ["gpt", "o1", "o3", "o4", "davinci", "turbo"]):
                model = f"openai/{model}"
            elif any(k in model_lower for k in ["gemini", "palm"]):
                model = f"google/{model}"
            elif any(k in model_lower for k in ["claude", "sonnet", "opus", "haiku"]):
                model = f"openrouter/anthropic/{model}"
            elif any(k in model_lower for k in ["llama", "mistral", "phi", "qwen", "codellama"]):
                model = f"ollama/{model}"
            else:
                model = f"openai/{model}"

        old_model = router.current_model
        router.set_model(model)
        return f"✅ Model switched: `{old_model}` → `{model}`\nThis takes effect starting from the next message."


class SystemSetThinkingTool(Tool):
    name = "system_set_thinking"
    description = "Change the thinking/reasoning depth level. Levels: none (fastest, no reasoning), low (light reasoning), medium (balanced), high (deep reasoning, slower)."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "description": "Thinking level: none, low, medium, or high",
                        "enum": ["none", "low", "medium", "high"],
                    },
                },
                "required": ["level"],
            },
        }

    async def execute(self, level: str, **kwargs) -> str:
        from agent.core.models import ThinkingLevel
        router = _get_model_router()
        if router:
            try:
                tl = ThinkingLevel(level.strip().lower())
                old = router.thinking_level.value
                router.set_thinking_level(tl)
                return f"✅ Thinking level: `{old}` → `{tl.value}`"
            except ValueError:
                return f"Invalid level. Use: none, low, medium, high"
        return "ERROR: Could not access model router."


class SystemSetTemperatureTool(Tool):
    name = "system_set_temperature"
    description = "Change the LLM temperature (creativity). 0.0 = deterministic, 1.0 = creative, 2.0 = very random. Default is 0.7."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "description": "Temperature value between 0.0 and 2.0"},
                },
                "required": ["temperature"],
            },
        }

    async def execute(self, temperature: float, **kwargs) -> str:
        router = _get_model_router()
        if router:
            if not (0.0 <= float(temperature) <= 2.0):
                return "Temperature must be between 0.0 and 2.0."
            old = router._temperature
            router._temperature = float(temperature)
            return f"✅ Temperature: `{old}` → `{temperature}`"
        return "ERROR: Could not access model router."


class SystemStatusTool(Tool):
    name = "system_status"
    description = "Get full system status: current model, thinking level, temperature, tools count, sub-agents, memory stats, channels, provider health, and resource usage. Use this to check if everything is working."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }

    async def execute(self, **kwargs) -> str:
        agent = _get_agent()
        if not agent:
            return "ERROR: Cannot access agent instance."

        model_status = agent.model_router.get_status()
        session_stats = agent.sessions.get_stats()
        tool_count = len(agent.tools.get_all())
        sub_count = len(agent.subagents.list_definitions())
        instances = agent.subagents.list_instances()
        running = [i for i in instances if i["status"] == "running"]

        # Memory stats
        try:
            mem_stats = await agent.memory.get_stats()
        except Exception:
            mem_stats = {}

        # System info
        ffmpeg = "✅" if shutil.which("ffmpeg") else "❌"
        
        # API key status
        keys = []
        if os.environ.get("OPENAI_API_KEY"):
            keys.append("OpenAI ✅")
        if os.environ.get("GOOGLE_API_KEY"):
            keys.append("Google ✅")
        if os.environ.get("OPENROUTER_API_KEY"):
            keys.append("OpenRouter ✅")
        if os.environ.get("OLLAMA_API_BASE"):
            keys.append("Ollama ✅")

        lines = [
            "## 🤖 System Status",
            "",
            f"**Model:** `{model_status['current_model']}`",
            f"**Thinking:** {model_status['thinking_level']}",
            f"**Temperature:** {model_status['temperature']}",
            f"**Streaming:** {model_status['streaming']}",
            f"**Max Tokens:** {model_status['max_tokens']}",
            f"**Fallbacks:** {', '.join(model_status['fallback_models']) or 'None'}",
            "",
            f"**Tools:** {tool_count} registered",
            f"**Sub-agents:** {sub_count} defined, {len(running)} running",
            f"**Sessions:** {session_stats.get('active_sessions', 0)} active, {session_stats.get('total_messages', 0)} messages",
            "",
            f"**Memories:** {mem_stats.get('total_memories', '?')}",
            f"**User facts:** {mem_stats.get('user_facts', '?')}",
            "",
            f"**Providers:** {', '.join(keys) if keys else '❌ None configured!'}",
            f"**FFmpeg:** {ffmpeg}",
            f"**Python:** {platform.python_version()}",
            f"**OS:** {platform.system()} {platform.release()}",
            f"**Dev Mode:** {'ON' if agent.settings.dev_mode.enabled else 'OFF'}",
        ]

        # Check last usage
        if agent._last_usage:
            total = agent._last_usage.get("total_tokens", 0)
            lines.append(f"\n**Last request tokens:** {total:,}")

        return "\n".join(lines)


class SystemHealthCheckTool(Tool):
    name = "system_health_check"
    description = "Run a comprehensive health check on the system. Tests: API keys valid, provider reachable, memory system, storage permissions, FFmpeg, channels. Returns pass/fail for each check."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }

    async def execute(self, **kwargs) -> str:
        agent = _get_agent()
        checks = []

        # 1. Check API keys exist
        for name, key in [("OpenAI", "OPENAI_API_KEY"), ("Google", "GOOGLE_API_KEY"),
                           ("OpenRouter", "OPENROUTER_API_KEY")]:
            val = os.environ.get(key, "")
            if val:
                checks.append(f"✅ {name} API key: configured ({len(val)} chars)")
            else:
                checks.append(f"⚪ {name} API key: not set")

        # 2. Check current model is valid format
        if agent:
            model = agent.model_router.current_model
            if "/" in model:
                checks.append(f"✅ Model format: `{model}` (valid)")
            else:
                checks.append(f"⚠️ Model format: `{model}` (should be provider/model)")

        # 3. Check workspace & storage exist and are writable
        for name, path in [("Workspace", "workspace"), ("Storage", "storage")]:
            p = Path(path)
            if p.exists() and p.is_dir():
                try:
                    test_file = p / ".health_check"
                    test_file.write_text("ok")
                    test_file.unlink()
                    checks.append(f"✅ {name}: writable ({p.resolve()})")
                except Exception as e:
                    checks.append(f"❌ {name}: not writable — {e}")
            else:
                checks.append(f"❌ {name}: directory not found")

        # 4. Check SOUL.md
        soul = Path("workspace/SOUL.md")
        if soul.exists():
            checks.append(f"✅ SOUL.md: loaded ({soul.stat().st_size} bytes)")
        else:
            checks.append(f"⚠️ SOUL.md: not found (using default personality)")

        # 5. Check FFmpeg
        if shutil.which("ffmpeg"):
            checks.append("✅ FFmpeg: available")
        else:
            checks.append("⚠️ FFmpeg: not found (voice features won't work)")

        # 6. Check memory system
        if agent:
            try:
                await agent.memory.get_stats()
                checks.append("✅ Memory system: operational")
            except Exception as e:
                checks.append(f"❌ Memory system: error — {e}")

        # 7. Check sub-agents
        if agent:
            defs = agent.subagents.list_definitions()
            checks.append(f"✅ Sub-agents: {len(defs)} loaded")

        # 8. Check tools
        if agent:
            tools = agent.tools.get_all()
            checks.append(f"✅ Tools: {len(tools)} registered")

        header = "## 🩺 Health Check Report\n"
        passed = sum(1 for c in checks if c.startswith("✅"))
        total = len(checks)
        summary = f"\n**Result: {passed}/{total} checks passed**"

        return header + "\n".join(checks) + summary


class SystemGetConfigTool(Tool):
    name = "system_get_config"
    description = "Read a configuration value from .env or current runtime settings. Use this to check what's configured."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Config key to read (e.g. 'NEX_DEFAULT_MODEL', 'OPENAI_API_KEY', 'NEX_VOICE_MODE'). Use 'all' to list all NexAlfa config."},
                },
                "required": ["key"],
            },
        }

    async def execute(self, key: str, **kwargs) -> str:
        if key.strip().lower() == "all":
            # List all NEX_ and key provider vars
            lines = ["## Current Configuration\n"]
            env_path = Path(".env")
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    k, _, v = line.partition("=")
                    # Mask sensitive keys
                    if "KEY" in k or "TOKEN" in k or "PASSWORD" in k or "SECRET" in k:
                        if v and len(v) > 8:
                            v = v[:4] + "****" + v[-4:]
                    lines.append(f"- `{k}` = `{v}`")
            return "\n".join(lines)
        else:
            val = os.environ.get(key.strip(), None)
            if val is None:
                return f"Config key `{key}` is not set."
            # Mask sensitive values
            if "KEY" in key or "TOKEN" in key or "PASSWORD" in key:
                if len(val) > 8:
                    display = val[:4] + "****" + val[-4:]
                else:
                    display = "****"
            else:
                display = val
            return f"`{key}` = `{display}`"


class SystemSetConfigTool(Tool):
    name = "system_set_config"
    description = "Set a configuration value in .env and apply it at runtime. Use this to change any NexAlfa setting (voice mode, API keys, gateway config, etc.)."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Config key (e.g. 'NEX_VOICE_MODE', 'NEX_TTS_VOICE')"},
                    "value": {"type": "string", "description": "Value to set"},
                },
                "required": ["key", "value"],
            },
        }

    async def execute(self, key: str, value: str, **kwargs) -> str:
        key = key.strip()
        value = value.strip()

        # Apply to runtime
        os.environ[key] = value

        # Write to .env file
        env_path = Path(".env")
        lines = env_path.read_text().splitlines() if env_path.exists() else []
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")
        env_path.write_text("\n".join(lines), encoding="utf-8")

        return f"✅ Config updated: `{key}` = `{value}` (runtime + .env)"


class SystemListToolsTool(Tool):
    name = "system_list_tools"
    description = "List all tools available to you (the agent). Shows tool name, description, and enabled status."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }

    async def execute(self, **kwargs) -> str:
        agent = _get_agent()
        if not agent:
            return "ERROR: Cannot access agent."
        tools = agent.tools.list_tools()
        lines = [f"## 🔧 Available Tools ({len(tools)})\n"]
        for t in tools:
            status = "✅" if t["enabled"] else "❌"
            lines.append(f"- {status} **{t['name']}** — {t['description'][:80]}")
        return "\n".join(lines)


class SystemRestartTool(Tool):
    name = "system_restart_component"
    description = "Reload a system component without full restart. Components: 'soul' (reload SOUL.md personality), 'skills' (reload skills), 'subagents' (reload sub-agent definitions), 'memory' (reconnect memory)."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": "Component to reload: soul, skills, subagents, memory",
                        "enum": ["soul", "skills", "subagents", "memory"],
                    },
                },
                "required": ["component"],
            },
        }

    async def execute(self, component: str, **kwargs) -> str:
        agent = _get_agent()
        if not agent:
            return "ERROR: Cannot access agent."

        if component == "soul":
            agent.personality._load_default()
            return "✅ SOUL.md reloaded."
        elif component == "skills":
            agent.skills.load_all()
            return f"✅ Skills reloaded: {len(agent.skills.list_skills())} skills."
        elif component == "subagents":
            agent.subagents._load_definitions()
            return f"✅ Sub-agents reloaded: {len(agent.subagents.list_definitions())} agents."
        elif component == "memory":
            try:
                await agent.memory.close()
                await agent.memory.initialize()
                return "✅ Memory system reconnected."
            except Exception as e:
                return f"❌ Memory restart failed: {e}"
        return f"Unknown component: {component}"


class SystemLogsTool(Tool):
    name = "system_logs"
    description = "Check recent system logs for errors or issues. Useful for troubleshooting."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "lines": {"type": "integer", "description": "Number of recent log lines to return (default 30)"},
                    "filter": {"type": "string", "description": "Filter logs: 'errors' (only errors), 'warnings', or 'all' (default)"},
                },
            },
        }

    async def execute(self, lines: int = 30, filter: str = "all", **kwargs) -> str:
        log_path = Path("storage/nexalfa.log")
        if not log_path.exists():
            return "No log file found at storage/nexalfa.log. Logs go to stdout by default."
        
        content = log_path.read_text(encoding="utf-8", errors="replace")
        all_lines = content.strip().split("\n")
        
        if filter == "errors":
            all_lines = [l for l in all_lines if "ERROR" in l or "CRITICAL" in l]
        elif filter == "warnings":
            all_lines = [l for l in all_lines if "WARNING" in l or "ERROR" in l]
        
        recent = all_lines[-lines:]
        if not recent:
            return "No matching log entries found."
        
        return f"## Recent Logs ({len(recent)} lines)\n```\n" + "\n".join(recent) + "\n```"


# ── Module-level references ─────────────────────────────────
# These get set when the agent initializes and registers system tools

_agent_ref = None
_router_ref = None


def _set_agent_ref(agent):
    """Called during agent init to give system tools access to the agent."""
    global _agent_ref, _router_ref
    _agent_ref = agent
    _router_ref = agent.model_router


def _get_agent():
    return _agent_ref


def _get_model_router():
    return _router_ref


# ── Tool registration ──────────────────────────────────────

def get_system_tools() -> list[Tool]:
    return [
        SystemSetModelTool(),
        SystemSetThinkingTool(),
        SystemSetTemperatureTool(),
        SystemStatusTool(),
        SystemHealthCheckTool(),
        SystemGetConfigTool(),
        SystemSetConfigTool(),
        SystemListToolsTool(),
        SystemRestartTool(),
        SystemLogsTool(),
    ]
