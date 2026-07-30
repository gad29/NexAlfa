"""
NexAlfa Sub-Agent System
Create, manage, and run isolated sub-agents with their own model, tools, workspace, and personality.
Inspired by Claude Code's sub-agents.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger("nex.subagents")


@dataclass
class SubAgentDef:
    """Sub-agent definition (parsed from frontmatter .md files)."""
    name: str
    description: str = ""
    model: str = "inherit"  # "inherit" = use main agent's model
    tools: list[str] = field(default_factory=list)  # Empty = all tools
    disallowed_tools: list[str] = field(default_factory=list)
    thinking: str = "medium"
    workspace: str = ""  # Relative to workspace/agents/
    prompt: str = ""  # System prompt / personality
    max_turns: int = 50
    background: bool = False
    api_key_overrides: dict[str, str] = field(default_factory=dict)
    
    @classmethod
    def from_markdown(cls, path: Path) -> "SubAgentDef":
        """Parse a sub-agent definition from a markdown file with YAML frontmatter."""
        text = path.read_text(encoding="utf-8")
        
        # Parse YAML frontmatter
        fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', text, re.DOTALL)
        if not fm_match:
            return cls(name=path.stem, prompt=text)
        
        fm_text, body = fm_match.groups()
        
        # Simple YAML parsing (avoid pyyaml dependency for agent defs)
        fm: dict[str, Any] = {}
        for line in fm_text.strip().split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                # Handle list values [a, b, c]
                if value.startswith("[") and value.endswith("]"):
                    items = [i.strip().strip("'\"") for i in value[1:-1].split(",") if i.strip()]
                    fm[key] = items
                elif value.lower() in ("true", "false"):
                    fm[key] = value.lower() == "true"
                elif value.isdigit():
                    fm[key] = int(value)
                else:
                    fm[key] = value.strip("'\"")
        
        return cls(
            name=fm.get("name", path.stem),
            description=fm.get("description", ""),
            model=fm.get("model", "inherit"),
            tools=fm.get("tools", []),
            disallowed_tools=fm.get("disallowedTools", fm.get("disallowed_tools", [])),
            thinking=fm.get("thinking", "medium"),
            workspace=fm.get("workspace", ""),
            prompt=body.strip(),
            max_turns=fm.get("max_turns", fm.get("maxTurns", 50)),
            background=fm.get("background", False),
        )
    
    def to_markdown(self) -> str:
        """Serialize back to frontmatter markdown."""
        lines = ["---"]
        lines.append(f"name: {self.name}")
        if self.description:
            lines.append(f"description: {self.description}")
        lines.append(f"model: {self.model}")
        if self.tools:
            lines.append(f"tools: [{', '.join(self.tools)}]")
        if self.disallowed_tools:
            lines.append(f"disallowedTools: [{', '.join(self.disallowed_tools)}]")
        lines.append(f"thinking: {self.thinking}")
        if self.workspace:
            lines.append(f"workspace: {self.workspace}")
        lines.append(f"maxTurns: {self.max_turns}")
        if self.background:
            lines.append(f"background: true")
        lines.append("---")
        lines.append("")
        lines.append(self.prompt)
        return "\n".join(lines)


@dataclass
class SubAgentInstance:
    """A running sub-agent instance."""
    id: str
    definition: SubAgentDef
    status: str = "idle"  # idle, running, completed, failed
    started_at: float = 0
    completed_at: float = 0
    messages: list[dict] = field(default_factory=list)
    result: str = ""
    error: str = ""
    task: str = ""  # What was asked
    turns_used: int = 0


class SubAgentManager:
    """Manages sub-agent definitions and running instances."""
    
    def __init__(self, agents_dir: Optional[Path] = None):
        self.agents_dir = agents_dir or Path("workspace/agents")
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self._definitions: dict[str, SubAgentDef] = {}
        self._instances: dict[str, SubAgentInstance] = {}
        self._load_definitions()
    
    def _load_definitions(self):
        """Load all sub-agent definitions from workspace/agents/*.md"""
        self._definitions.clear()
        for path in self.agents_dir.glob("*.md"):
            if path.name.startswith("_"):
                continue
            try:
                defn = SubAgentDef.from_markdown(path)
                self._definitions[defn.name] = defn
                logger.info(f"Sub-agent loaded: {defn.name} (model: {defn.model})")
            except Exception as e:
                logger.warning(f"Failed to load sub-agent {path}: {e}")
    
    def list_definitions(self) -> list[dict]:
        """List all sub-agent definitions."""
        return [
            {
                "name": d.name,
                "description": d.description,
                "model": d.model,
                "tools": d.tools,
                "thinking": d.thinking,
                "background": d.background,
            }
            for d in self._definitions.values()
        ]
    
    def list_instances(self) -> list[dict]:
        """List all running/completed sub-agent instances."""
        return [
            {
                "id": inst.id,
                "agent": inst.definition.name,
                "status": inst.status,
                "task": inst.task[:100],
                "turns": inst.turns_used,
                "started": inst.started_at,
                "completed": inst.completed_at,
            }
            for inst in self._instances.values()
        ]
    
    def get_definition(self, name: str) -> Optional[SubAgentDef]:
        return self._definitions.get(name)
    
    def create_definition(self, defn: SubAgentDef) -> str:
        """Create a new sub-agent definition file."""
        path = self.agents_dir / f"{defn.name}.md"
        path.write_text(defn.to_markdown(), encoding="utf-8")
        self._definitions[defn.name] = defn
        
        # Create workspace dir
        ws = self.agents_dir / defn.name
        ws.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Sub-agent created: {defn.name}")
        return f"✅ Sub-agent '{defn.name}' created at {path}"
    
    def delete_definition(self, name: str) -> str:
        if name not in self._definitions:
            return f"Sub-agent '{name}' not found."
        
        path = self.agents_dir / f"{name}.md"
        if path.exists():
            path.unlink()
        self._definitions.pop(name, None)
        return f"✅ Sub-agent '{name}' deleted."
    
    async def spawn(
        self,
        name: str,
        task: str,
        model_router,
        tool_registry,
    ) -> SubAgentInstance:
        """Spawn a sub-agent instance to execute a task."""
        defn = self._definitions.get(name)
        if not defn:
            raise ValueError(f"Sub-agent '{name}' not found. Available: {list(self._definitions.keys())}")
        
        instance = SubAgentInstance(
            id=str(uuid4())[:8],
            definition=defn,
            status="running",
            started_at=time.time(),
            task=task,
        )
        self._instances[instance.id] = instance
        
        logger.info(f"🚀 Sub-agent '{name}' spawned (id: {instance.id})")
        
        # Run the sub-agent (use the main model_router but potentially with different model)
        try:
            result = await self._run_agent_loop(instance, model_router, tool_registry)
            instance.status = "completed"
            instance.result = result
            instance.completed_at = time.time()
        except Exception as e:
            instance.status = "failed"
            instance.error = str(e)
            instance.completed_at = time.time()
            logger.error(f"Sub-agent '{name}' failed: {e}")
        
        return instance
    
    async def _run_agent_loop(
        self,
        instance: SubAgentInstance,
        model_router,
        tool_registry,
    ) -> str:
        """Run the sub-agent's message loop."""
        from agent.core.models import ThinkingLevel
        
        defn = instance.definition
        
        # Determine model
        original_model = model_router.current_model
        original_thinking = model_router.thinking_level
        
        if defn.model != "inherit":
            model_router.set_model(defn.model)
        
        # Set thinking level
        try:
            model_router.set_thinking_level(ThinkingLevel(defn.thinking))
        except ValueError:
            pass
        
        # Build messages
        system_prompt = defn.prompt or f"You are {defn.name}, a specialized sub-agent."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": instance.task},
        ]
        
        # Get available tools (filter if specified)
        all_tools = tool_registry.get_all()
        if defn.tools:
            tools = [t for t in all_tools if t.name in defn.tools]
        elif defn.disallowed_tools:
            tools = [t for t in all_tools if t.name not in defn.disallowed_tools]
        else:
            tools = all_tools
        
        tool_schemas = [t.to_openai_tool() for t in tools]
        tool_map = {t.name: t for t in tools}
        
        # Agent loop
        max_turns = defn.max_turns
        for turn in range(max_turns):
            instance.turns_used = turn + 1
            
            response = await model_router.complete(
                messages=messages,
                tools=tool_schemas if tool_schemas else None,
            )
            
            if response.tool_calls:
                # Execute tools
                messages.append({
                    "role": "assistant",
                    "content": response.content or None,
                    "tool_calls": response.tool_calls,
                })
                
                for tc in response.tool_calls:
                    tool_name = tc["function"]["name"]
                    tool = tool_map.get(tool_name)
                    if tool:
                        try:
                            args = json.loads(tc["function"]["arguments"])
                            result = await tool.execute(**args)
                        except Exception as e:
                            result = f"Tool error: {e}"
                    else:
                        result = f"Tool '{tool_name}' not available for this sub-agent."
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": str(result),
                    })
            else:
                # Final response
                model_router.set_model(original_model)
                model_router.set_thinking_level(original_thinking)
                return response.content
        
        # Restore original model
        model_router.set_model(original_model)
        model_router.set_thinking_level(original_thinking)
        return f"(Sub-agent hit max turns: {max_turns})"
    
    def stop_instance(self, instance_id: str) -> str:
        inst = self._instances.get(instance_id)
        if not inst:
            return f"Instance '{instance_id}' not found."
        inst.status = "stopped"
        inst.completed_at = time.time()
        return f"✅ Sub-agent instance '{instance_id}' stopped."


# ── Tool registration ──────────────────────────────────────

from agent.tools.base import Tool


def get_subagent_tools(manager: SubAgentManager, model_router, tool_registry) -> list[Tool]:

    class AgentListTool(Tool):
        name = "agent_list"
        description = "List all available sub-agents and their running instances."

        def get_schema(self) -> dict:
            return {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": {}},
            }

        async def execute(self, **kwargs) -> str:
            defs = manager.list_definitions()
            instances = manager.list_instances()
            parts = ["## Available Sub-Agents"]
            if not defs:
                parts.append("No sub-agents defined. Create one in workspace/agents/*.md")
            for d in defs:
                parts.append(f"- **{d['name']}** — {d['description']} (model: {d['model']})")
            if instances:
                parts.append("\n## Running Instances")
                for inst in instances:
                    parts.append(f"- `{inst['id']}` {inst['agent']}: {inst['status']} ({inst['turns']} turns) — {inst['task']}")
            return "\n".join(parts)

    class AgentSpawnTool(Tool):
        name = "agent_spawn"
        description = "Spawn a sub-agent to perform a task. The sub-agent runs in its own context with its own model and tools, then returns the result."

        def get_schema(self) -> dict:
            return {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the sub-agent to spawn"},
                        "task": {"type": "string", "description": "The task/instruction for the sub-agent"},
                    },
                    "required": ["name", "task"],
                },
            }

        async def execute(self, name: str = "", task: str = "", **kwargs) -> str:
            try:
                instance = await manager.spawn(name, task, model_router, tool_registry)
                if instance.status == "completed":
                    return f"✅ Sub-agent '{name}' completed:\n\n{instance.result}"
                else:
                    return f"❌ Sub-agent '{name}' failed: {instance.error}"
            except Exception as e:
                return f"ERROR: {e}"

    class AgentCreateTool(Tool):
        name = "agent_create"
        description = "Create a new sub-agent definition."

        def get_schema(self) -> dict:
            return {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Unique name for the sub-agent"},
                        "description": {"type": "string", "description": "What this sub-agent does"},
                        "model": {"type": "string", "description": "Model to use or 'inherit'"},
                        "prompt": {"type": "string", "description": "System prompt for the sub-agent"},
                        "tools": {"type": "string", "description": "Comma-separated tool names (empty = all tools)"},
                    },
                    "required": ["name", "description"],
                },
            }

        async def execute(self, name: str = "", description: str = "",
                          model: str = "inherit", prompt: str = "", tools: str = "", **kwargs) -> str:
            tool_list = [t.strip() for t in tools.split(",") if t.strip()] if tools else []
            defn = SubAgentDef(
                name=name,
                description=description,
                model=model,
                tools=tool_list,
                prompt=prompt or f"You are {name}, a specialized assistant.",
            )
            return manager.create_definition(defn)

    class AgentStopTool(Tool):
        name = "agent_stop"
        description = "Stop a running sub-agent instance."

        def get_schema(self) -> dict:
            return {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "instance_id": {"type": "string", "description": "ID of the running instance to stop"},
                    },
                    "required": ["instance_id"],
                },
            }

        async def execute(self, instance_id: str = "", **kwargs) -> str:
            return manager.stop_instance(instance_id)

    return [AgentListTool(), AgentSpawnTool(), AgentCreateTool(), AgentStopTool()]
