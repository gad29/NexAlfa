"""
NexAlfa Agent — The Main Brain
The central agent loop that receives messages, builds context from personality +
memory + skills, calls the LLM, executes tools, learns, and responds.

Pulls patterns from:
- Hermes Agent's run_agent.py (learning loop, skill creation)
- OpenClaw's agent (session management, tool execution)
- Dev Mode (no guardrails, thinking messages)
"""

from __future__ import annotations

import json
import logging
import time
from typing import AsyncIterator, Optional
from uuid import uuid4

from agent.config.settings import get_settings
from agent.core.models import ModelRouter, ModelResponse, StreamChunk, ThinkingLevel
from agent.core.sessions import Session, SessionManager, Message
from agent.core.errors import NexError, classify_llm_error, ToolError
from agent.core.subagent import SubAgentManager, get_subagent_tools
from agent.memory.manager import MemoryManager
from agent.personality.soul import PersonalityManager
from agent.skills.engine import SkillsEngine
from agent.tools.base import ToolRegistry
from agent.tools.filesystem import get_filesystem_tools
from agent.tools.process import get_process_tools
from agent.tools.browser import get_browser_tools
from agent.tools.cron import get_cron_tools
from agent.tools.mcp_client import get_mcp_tools
from agent.tools.webhooks import get_webhook_tools
from agent.tools.mcp_n8n import get_n8n_tools_async, n8n_mcp_manager
from agent.tools.documents import get_document_tools
from agent.tools.web import get_web_tools
from agent.tools.voice import get_voice_tools, stt_transcribe, tts_generate, should_respond_with_voice
from agent.tools.system import get_system_tools, _set_agent_ref
from agent.tools.desktop import get_desktop_tools
from agent.tools.pc_control import get_pc_control_tools
from agent.tools.devtools import get_devtools
from agent.tools.google_api import get_google_tools

logger = logging.getLogger("nex.agent")


class NexAgent:
    """
    The Nex agent — self-improving personal AI assistant.

    Flow per message:
    1. Receive user message
    2. Get/create session for the channel
    3. Build system prompt (personality + memory + skills + user model)
    4. Retrieve relevant context from past conversations
    5. Call LLM (with tools available)
    6. If tool calls → execute tools → send results back to LLM → repeat
    7. Return final response
    8. Post-processing: record to memory, learn, extract facts, maybe create skill
    """

    def __init__(self):
        self.settings = get_settings()
        self.model_router = ModelRouter()
        self.sessions = SessionManager()
        self.memory = MemoryManager()
        self.personality = PersonalityManager()
        self.skills = SkillsEngine()
        self.tools = ToolRegistry()
        self.subagents = SubAgentManager()
        self._initialized = False
        self._last_usage: dict = {}  # Track last response usage for status bar
        self._pending_cron_messages: list[str] = []  # Queue for cron-triggered agent tasks

    async def initialize(self):
        """Initialize all subsystems."""
        if self._initialized:
            return

        # Initialize memory system
        await self.memory.initialize()

        # Load skills
        self.skills.load_all()

        # Register tools — core (always included in context)
        for tool in get_filesystem_tools():
            tool.category = "core"
            self.tools.register(tool)
        for tool in get_process_tools():
            tool.category = "core"
            self.tools.register(tool)
        # Register tools — browser
        for tool in get_browser_tools():
            tool.category = "browser"
            self.tools.register(tool)
        # Register tools — scheduling / automation
        for tool in get_cron_tools():
            tool.category = "cron"
            self.tools.register(tool)
        for tool in get_mcp_tools():
            tool.category = "mcp"
            self.tools.register(tool)
            
        # Register n8n MCP tools natively
        try:
            n8n_tools = await get_n8n_tools_async()
            for tool in n8n_tools:
                tool.category = "automation"
                self.tools.register(tool)
        except Exception as e:
            logger.warning(f"Failed to load n8n MCP tools: {e}")

        for tool in get_webhook_tools():
            tool.category = "webhooks"
            self.tools.register(tool)
        # Register tools — documents, web, voice
        for tool in get_document_tools():
            tool.category = "documents"
            self.tools.register(tool)
        for tool in get_web_tools():
            tool.category = "web"
            self.tools.register(tool)
        for tool in get_voice_tools():
            tool.category = "voice"
            self.tools.register(tool)
        # Register tools — sub-agents
        for tool in get_subagent_tools(self.subagents, self.model_router, self.tools):
            tool.category = "subagents"
            self.tools.register(tool)
        # Register tools — system self-management
        for tool in get_system_tools():
            tool.category = "system"
            self.tools.register(tool)
        # Register tools — desktop control, PC management, dev tools, Google
        for tool in get_desktop_tools():
            self.tools.register(tool)  # category already set in module
        for tool in get_pc_control_tools():
            self.tools.register(tool)  # category already set in module
        for tool in get_devtools():
            self.tools.register(tool)  # category already set in module
        for tool in get_google_tools():
            self.tools.register(tool)  # category already set in module

        # Set self-reference so system tools can access this agent
        _set_agent_ref(self)

        self._initialized = True
        tool_count = len(self.tools.get_all())
        logger.info(f"🤖 {self.settings.agent_name} initialized — {tool_count} tools ready")

    async def shutdown(self):
        """Clean shutdown."""
        await self.memory.close()
        try:
            await n8n_mcp_manager.shutdown()
        except Exception:
            pass
        logger.info("Agent shutdown complete")

    async def process_message(
        self,
        content: str,
        channel: str = "webchat",
        channel_id: str = "default",
        sender: str = "user",
        session_id: Optional[str] = None,
    ) -> str:
        """
        Process a user message and return the agent's response.
        Non-streaming version.
        """
        await self.initialize()

        # 1. Get or create session
        if session_id:
            session = self.sessions.get_session(session_id)
            if not session:
                session = self.sessions.create_session(channel=channel, channel_id=channel_id)
        else:
            session = self.sessions.get_or_create_for_channel(channel, channel_id)

        # 2. Handle slash commands
        if content.startswith("/"):
            result = await self._handle_command(content, session)
            if result is not None:
                return result

        # 3. Add user message to session
        session.add_message("user", content)

        # 4. Record to memory
        await self.memory.record_message(
            session_id=session.id, role="user", content=content,
            channel=channel, channel_id=channel_id,
        )

        # 5. Auto-summarize if conversation is getting long
        await self._auto_summarize(session)

        # 5b. Drain pending cron messages (e.g. human learning triggers)
        while self._pending_cron_messages:
            cron_msg = self._pending_cron_messages.pop(0)
            session.add_message("system", cron_msg)
            logger.info(f"Injected cron message into session: {cron_msg[:80]}...")

        # 6. Build system prompt with all context
        system_prompt = await self._build_system_prompt(content, session)

        # 7. Use WINDOWED messages (not all messages) to prevent context bloat
        messages = session.get_windowed_messages()
        if not messages or messages[0]["role"] != "system":
            messages.insert(0, {"role": "system", "content": system_prompt})
        else:
            messages[0]["content"] = system_prompt

        # 8. Get RELEVANT tools only (not all 89)
        tools_schema = self.tools.get_relevant_tools(content) or None

        # 9. Agent loop — call LLM, execute tools, repeat
        max_iterations = 10
        final_response = ""
        thinking_output = ""

        for i in range(max_iterations):
            try:
                response = await asyncio.wait_for(
                    self.model_router.complete(messages=messages, tools=tools_schema),
                    timeout=90,  # 90s timeout per LLM call
                )
            except asyncio.TimeoutError:
                return "⏳ The model took too long to respond. Please try again or switch to a faster model."
            except Exception as e:
                nex_err = classify_llm_error(e)
                logger.error(f"LLM error: {nex_err.to_dict()}")
                # Auto-retry on rate limit (once)
                if nex_err.code.value == "rate_limited" and i == 0:
                    retry_msg = "⏳ Rate limited. Waiting 10s and retrying..."
                    logger.info(retry_msg)
                    await asyncio.sleep(10)
                    continue
                return nex_err.to_user_message()

            # Track usage for status bar
            if response.usage:
                self._last_usage = response.usage

            # Collect thinking
            if response.thinking:
                thinking_output += response.thinking

            # Handle tool calls
            if response.tool_calls:
                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls,
                })

                # Execute each tool with timeout
                for tc in response.tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_args = tc["function"]["arguments"]
                    logger.info(f"🔧 Tool call: {tool_name}")

                    try:
                        result = await asyncio.wait_for(
                            self.tools.execute_tool(tool_name, tool_args),
                            timeout=30,  # 30s per tool
                        )
                    except asyncio.TimeoutError:
                        result = f"⏳ Tool '{tool_name}' timed out after 30s."

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
                continue  # Loop back for LLM to process tool results

            # No tool calls — we have the final response
            final_response = response.content
            break

        # 10. Add assistant response to session
        session.add_message(
            "assistant", final_response,
            thinking=thinking_output if thinking_output else None,
        )

        # 11. Record to memory
        await self.memory.record_message(
            session_id=session.id, role="assistant", content=final_response,
            channel=channel, channel_id=channel_id, thinking=thinking_output or None,
        )

        # 12. Post-processing — learning loop (async, non-blocking)
        await self._post_process(session)

        # 13. Format response with thinking if dev-mode
        if thinking_output and self.settings.dev_mode.show_thinking:
            return f"💭 Reasoning:\n{thinking_output}\n\n{final_response}"

        return final_response

    async def process_message_stream(
        self,
        content: str,
        channel: str = "webchat",
        channel_id: str = "default",
        session_id: Optional[str] = None,
    ) -> AsyncIterator[dict]:
        """
        Process a user message with streaming response.
        Yields dicts with keys: type (thinking|content|tool|done|error), data.
        Tool calls are handled via non-streaming complete(), final answer is streamed.
        """
        await self.initialize()

        # Get/create session
        if session_id:
            session = self.sessions.get_session(session_id) or \
                      self.sessions.create_session(channel=channel, channel_id=channel_id)
        else:
            session = self.sessions.get_or_create_for_channel(channel, channel_id)

        # Handle slash commands
        if content.startswith("/"):
            result = await self._handle_command(content, session)
            if result is not None:
                yield {"type": "content", "data": result}
                yield {"type": "done", "data": ""}
                return

        # Add user message
        session.add_message("user", content)
        await self.memory.record_message(
            session_id=session.id, role="user", content=content,
            channel=channel, channel_id=channel_id,
        )

        # Auto-summarize if conversation is getting long
        await self._auto_summarize(session)

        # Build context
        system_prompt = await self._build_system_prompt(content, session)

        # Use WINDOWED messages (not all) to prevent context bloat
        messages = session.get_windowed_messages()
        if not messages or messages[0]["role"] != "system":
            messages.insert(0, {"role": "system", "content": system_prompt})
        else:
            messages[0]["content"] = system_prompt

        # ── Tool loop (non-streaming) ──────────────────────────
        # Get RELEVANT tools only (not all 89)
        tools_schema = self.tools.get_relevant_tools(content) or None
        max_iterations = 10
        import json as _json

        for i in range(max_iterations):
            try:
                response = await asyncio.wait_for(
                    self.model_router.complete(messages=messages, tools=tools_schema),
                    timeout=90,  # 90s timeout per LLM call
                )
            except asyncio.TimeoutError:
                yield {"type": "error", "data": "⏳ The model took too long to respond. Please try again or switch to a faster model."}
                yield {"type": "done", "data": "", "session_id": session.id}
                return
            except Exception as e:
                nex_err = classify_llm_error(e)
                logger.error(f"LLM error (stream): {nex_err.to_dict()}")
                # Auto-retry on rate limit (once)
                if nex_err.code.value == "rate_limited" and i == 0:
                    yield {"type": "tool", "data": "⏳ Rate limited by provider. Waiting 10s and retrying..."}
                    await asyncio.sleep(10)
                    continue
                # Context exceeded — auto-compact and retry
                if nex_err.code.value == "context_exceeded" and i == 0:
                    yield {"type": "tool", "data": "📦 Context too large. Compacting conversation..."}
                    session.compact(keep_last=10)
                    messages = session.get_windowed_messages()
                    if not messages or messages[0]["role"] != "system":
                        messages.insert(0, {"role": "system", "content": system_prompt})
                    else:
                        messages[0]["content"] = system_prompt
                    continue
                yield {"type": "error", "data": nex_err.to_user_message()}
                yield {"type": "done", "data": "", "session_id": session.id}
                return

            # Track usage
            if response.usage:
                self._last_usage = response.usage

            if response.tool_calls:
                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls,
                })

                # Execute each tool and notify frontend
                for tc in response.tool_calls:
                    tool_name = tc["function"]["name"]
                    tool = self.tools.get(tool_name)

                    # Emit tool activity to frontend
                    yield {"type": "tool", "data": f"⚙️ Running `{tool_name}`..."}

                    if tool:
                        try:
                            args = _json.loads(tc["function"]["arguments"])
                            result = await asyncio.wait_for(
                                tool.execute(**args),
                                timeout=30,  # 30s per tool
                            )
                        except asyncio.TimeoutError:
                            result = f"⏳ Tool '{tool_name}' timed out after 30s."
                        except Exception as e:
                            result = f"Tool error: {type(e).__name__}: {e}"
                    else:
                        result = f"Tool '{tool_name}' not found."

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": str(result),
                    })

                # Continue the loop — model will process tool results
                continue

            # ── No tool calls → this is the final response ─────
            # Stream the final text if we have it
            if response.content:
                # Emit thinking if present
                if response.thinking and self.settings.dev_mode.show_thinking:
                    yield {"type": "thinking", "data": response.thinking}

                # Yield content in small chunks for streaming feel
                text = response.content
                chunk_size = 12  # chars per chunk for smooth streaming
                for j in range(0, len(text), chunk_size):
                    yield {"type": "content", "data": text[j:j+chunk_size]}
                    await asyncio.sleep(0.015)  # slight delay for visual streaming

                # Save to session and memory
                session.add_message("assistant", text, thinking=response.thinking or None)
                await self.memory.record_message(
                    session_id=session.id, role="assistant", content=text,
                    channel=channel, channel_id=channel_id,
                    thinking=response.thinking or None,
                )
            break

        # Post-process (non-blocking)
        try:
            await self._post_process(session)
        except Exception as e:
            logger.warning(f"Post-processing failed: {e}")

        yield {"type": "done", "data": "", "session_id": session.id}

    async def _build_system_prompt(self, current_message: str, session: Session) -> str:
        """Build the full system prompt with all context layers."""
        # Get user model context
        user_context = self.memory.get_context_for_agent()

        # Get skills context (names only, not full content)
        skills_context = self.skills.get_skills_context()

        # Get relevant memories for this message (limited to top 5)
        memory_context = await self.memory.get_relevant_context(current_message, n_results=3)

        # Build full prompt
        return self.personality.get_system_prompt(
            user_context=user_context,
            skills_context=skills_context,
            memory_context=memory_context,
        )

    SUMMARIZE_PROMPT = (
        "Summarize the following conversation between a user and an AI assistant in 2-3 sentences. "
        "Focus on: what the user asked for, what was accomplished, and the current state. "
        "Be specific about technical details, names, and decisions. "
        "Do NOT include greetings or filler."
    )

    async def _auto_summarize(self, session: Session):
        """Auto-summarize older messages when conversation gets too long.
        This prevents context from growing unbounded during long sessions."""
        if not session.needs_summarization():
            return

        old_messages = session.get_messages_for_summarization()
        if not old_messages:
            return

        # Build a compact conversation text from the overflow
        conv_lines = []
        for m in old_messages[:30]:  # Cap at 30 messages for summarization
            role = "User" if m["role"] == "user" else "Nex"
            conv_lines.append(f"{role}: {m['content'][:200]}")
        conv_text = "\n".join(conv_lines)

        # Use a lightweight LLM call to summarize
        try:
            summary_messages = [
                {"role": "system", "content": self.SUMMARIZE_PROMPT},
                {"role": "user", "content": f"Conversation to summarize:\n\n{conv_text}"},
            ]
            # Use a fast, cheap call (no tools)
            response = await asyncio.wait_for(
                self.model_router.complete(messages=summary_messages, tools=None),
                timeout=30,
            )
            if response.content:
                # Merge with existing summary
                if session.summary:
                    new_summary = f"{session.summary}\n\nUpdate: {response.content}"
                    # Keep summary under ~500 chars
                    if len(new_summary) > 600:
                        new_summary = response.content
                else:
                    new_summary = response.content

                session.apply_summary_and_compact(new_summary)
                logger.info(f"Auto-summarized session {session.id}: {len(new_summary)} chars")
        except Exception as e:
            logger.warning(f"Auto-summarize failed: {e}")
            # Fallback: just compact without summary
            session.compact(keep_last=20)

    async def _handle_command(self, content: str, session: Session) -> Optional[str]:
        """Handle slash commands. Returns response or None if not a command."""
        parts = content.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/new": lambda: self._cmd_new(session),
            "/reset": lambda: self._cmd_new(session),
            "/model": lambda: self._cmd_model(args),
            "/think": lambda: self._cmd_think(args),
            "/personality": lambda: self._cmd_personality(args),
            "/skills": lambda: self._cmd_skills(),
            "/status": lambda: self._cmd_status(session),
            "/usage": lambda: self._cmd_usage(session),
            "/compact": lambda: self._cmd_compact(session),
            "/search": lambda: self._cmd_search(args),
            "/memories": lambda: self._cmd_memories(),
            "/connect": lambda: self._cmd_connect(args),
            "/human-learning": lambda: self._cmd_human_learning(args),
        }

        handler = handlers.get(cmd)
        if handler:
            return await handler() if asyncio.iscoroutinefunction(handler) else handler()

        # Check if it's a skill invocation
        skill_name = cmd[1:]  # remove /
        skill_content = self.skills.invoke_skill(skill_name)
        if skill_content:
            return f"Skill **{skill_name}** activated:\n{skill_content}"

        return None  # Not a command, process as regular message

    def _cmd_new(self, session: Session) -> str:
        session.messages.clear()
        return "🔄 Session cleared. Fresh start."

    def _cmd_model(self, args: str) -> str:
        if not args:
            status = self.model_router.get_status()
            return f"**Current model**: `{status['current_model']}`\n**Fallbacks**: {', '.join(status['fallback_models'])}"
        self.model_router.set_model(args.strip())
        return f"✅ Model switched to: `{args.strip()}`"

    def _cmd_connect(self, args: str) -> str:
        if not args:
            return "Usage: /connect <provider> <token>\nExample: /connect openai eyJhbG..."
        parts = args.strip().split(maxsplit=1)
        provider = parts[0].lower()
        token = parts[1] if len(parts) > 1 else ""
        if not token:
            return f"Please provide an OAuth token for {provider}."
        
        from agent.auth.oauth_sink import auth_sink
        auth_sink.save_token(provider, token)
        return f"✅ Linked **{provider}** account successfully via OAuth token."

    def _cmd_human_learning(self, args: str) -> str:
        from agent.tools.cron import get_scheduler, _job_actions
        scheduler = get_scheduler()
        sub = args.strip().lower() if args else "status"

        JOB_ID = "human_interaction_learning"

        if sub == "on":
            # Schedule daily at 04:00 local time
            from apscheduler.triggers.cron import CronTrigger
            async def _learning_job():
                logger.info("🧠 CRON: Human interaction learning job fired.")
                # Inject a system message into the next agent loop via the pending_cron_messages queue
                self._pending_cron_messages.append(
                    "SYSTEM CRON TRIGGER: Your daily human_interaction_learning skill is due. "
                    "Invoke the skill now: study Twitter/X and YouTube via Agent Reach, "
                    "extract human interaction patterns, filter AI content, stay neutral, "
                    "and write a brief daily summary of what you learned."
                )

            scheduler.add_job(_learning_job, CronTrigger(hour=4, minute=0), id=JOB_ID, replace_existing=True)
            _job_actions[JOB_ID] = {
                "action": "Invoke human_interaction_learning skill via Agent Reach",
                "description": "Daily human behavior study (04:00)"
            }
            return "✅ **Human Learning** enabled — daily at 04:00 AM.\nNex will study human interaction patterns on Twitter/X and YouTube, and write a brief summary of what was learned."

        elif sub == "off":
            try:
                scheduler.remove_job(JOB_ID)
                _job_actions.pop(JOB_ID, None)
            except Exception:
                pass
            return "⏹️ **Human Learning** disabled. No more daily studies."

        elif sub == "run":
            self._pending_cron_messages.append(
                "SYSTEM MANUAL TRIGGER: The user asked you to run the human_interaction_learning skill NOW. "
                "Invoke the skill: study Twitter/X and YouTube via Agent Reach, "
                "extract human interaction patterns, filter AI content, stay neutral, "
                "and write a brief daily summary of what you learned."
            )
            return "🚀 **Human Learning** manually triggered — will run on next message cycle."

        else:  # status
            jobs = scheduler.get_jobs()
            active = any(j.id == JOB_ID for j in jobs)
            if active:
                job = next(j for j in jobs if j.id == JOB_ID)
                return f"🧠 **Human Learning**: Active\n⏰ Next run: {job.next_run_time}\nUse `/human-learning off` to disable."
            else:
                return "💤 **Human Learning**: Inactive\nUse `/human-learning on` to enable daily studies."

    def _cmd_think(self, args: str) -> str:
        try:
            level = ThinkingLevel(args.strip().lower()) if args else ThinkingLevel.MEDIUM
            self.model_router.set_thinking_level(level)
            return f"🧠 Thinking level: **{level.value}**"
        except ValueError:
            return f"Invalid level. Use: none, low, medium, high"

    def _cmd_personality(self, args: str) -> str:
        if not args:
            available = self.personality.list_personalities()
            return f"**Current**: {self.personality.current_name}\n**Available**: {', '.join(available)}"
        if self.personality.switch_personality(args.strip()):
            return f"🎭 Personality switched to: **{args.strip()}**"
        return f"Personality '{args}' not found."

    def _cmd_skills(self) -> str:
        skills = self.skills.list_skills()
        if not skills:
            return "No skills installed. I'll create them as I learn!"
        lines = ["**Available Skills:**"]
        for s in skills:
            status = "✅" if s["enabled"] else "❌"
            auto = " (auto-created)" if s["auto_created"] else ""
            lines.append(f"- {status} **/{s['name']}** — {s['description']}{auto} (used {s['usage_count']}x)")
        return "\n".join(lines)

    def _cmd_status(self, session: Session) -> str:
        model_status = self.model_router.get_status()
        session_stats = self.sessions.get_stats()
        return (
            f"🤖 **{self.settings.agent_name}** Status\n"
            f"**Model**: `{model_status['current_model']}`\n"
            f"**Thinking**: {model_status['thinking_level']}\n"
            f"**Sessions**: {session_stats['active_sessions']} active\n"
            f"**Messages**: {session_stats['total_messages']} total\n"
            f"**This session**: {session.message_count} messages\n"
            f"**Dev mode**: {'ON' if self.settings.dev_mode.enabled else 'OFF'}"
        )

    def _cmd_usage(self, session: Session) -> str:
        return (
            f"**Session**: {session.message_count} messages, ~{session.token_estimate} tokens\n"
            f"**Model**: `{self.model_router.current_model}`"
        )

    def _cmd_compact(self, session: Session) -> str:
        removed = session.compact(keep_last=10)
        return f"📦 Compacted: removed {len(removed)} old messages, kept last 10."

    async def _cmd_search(self, args: str) -> str:
        if not args:
            return "Usage: /search <query>"
        results = await self.memory.search_past(args.strip())
        if not results:
            return "No results found."
        lines = [f"**Search results for** '{args.strip()}':"]
        for r in results[:5]:
            lines.append(f"- {r['content'][:150]}...")
        return "\n".join(lines)

    async def _cmd_memories(self) -> str:
        stats = await self.memory.get_stats()
        return (
            f"🧠 **Memory Stats**\n"
            f"Messages stored: {stats.get('total_messages', 0)}\n"
            f"Memories extracted: {stats.get('total_memories', 0)}\n"
            f"User facts: {stats.get('user_facts', 0)}\n"
            f"Vectors indexed: conversations={stats.get('conversations_indexed', 0)}, "
            f"memories={stats.get('memories_indexed', 0)}"
        )

    async def _post_process(self, session: Session):
        """Post-conversation learning loop. Extracts memories and user facts."""
        if not self.settings.memory.auto_learn:
            return

        # Only learn every N messages to avoid overhead
        if session.message_count % 6 != 0:
            return

        try:
            # Get recent messages for analysis
            recent = session.get_last_n_messages(10)
            msg_dicts = [{"role": m.role, "content": m.content} for m in recent]

            # Extract memories
            extraction_prompt = await self.memory.extract_memories(msg_dicts)
            if extraction_prompt:
                response = await self.model_router.complete(
                    messages=extraction_prompt,
                    stream=False,
                    temperature=0.3,
                    max_tokens=1000,
                )
                await self.memory.save_extracted_memories(response.content, session.id)

            # Extract user facts
            user_prompt = [{
                "role": "system",
                "content": self.memory.user_model.generate_learning_prompt(),
            }, {
                "role": "user",
                "content": "\n".join(f"[{m.role}]: {m.content}" for m in recent if m.content),
            }]
            response = await self.model_router.complete(
                messages=user_prompt,
                stream=False,
                temperature=0.3,
                max_tokens=500,
            )
            await self.memory.save_user_facts(response.content, session.id)

        except Exception as e:
            logger.warning(f"Post-processing failed: {e}")


# Need this import for _handle_command
import asyncio
