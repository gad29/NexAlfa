"""
NexAlfa n8n MCP Integration
Automatically spins up and connects to the n8n MCP server via stdio
and registers its tools directly into NexAlfa's ToolRegistry.
"""

import asyncio
import json
import logging
import os
from typing import Optional, Any

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.n8n")

class N8nMCPProxyTool(Tool):
    """Dynamically generated tool that proxies to the running n8n MCP server."""
    
    def __init__(self, name: str, description: str, schema: dict, mcp_client: Any):
        self.name = name
        self.description = description
        self._schema = schema
        self.mcp_client = mcp_client

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._schema
        }

    async def execute(self, **kwargs) -> str:
        try:
            result = await self.mcp_client.session.call_tool(self.name, kwargs)
            if result.content:
                parts = []
                for block in result.content:
                    if hasattr(block, "text"):
                        parts.append(block.text)
                return "\n".join(parts) if parts else "Tool returned no content."
            return "Executed successfully."
        except Exception as e:
            logger.error(f"Failed to execute n8n MCP tool {self.name}: {e}")
            return f"Error executing {self.name}: {e}"


class N8nMCPServerManager:
    """Manages the lifecycle of the npx @n8n/mcp-server process."""

    def __init__(self):
        self.server_process = None
        self.session = None
        self.exit_stack = None

    async def start_and_get_tools(self) -> list[Tool]:
        try:
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp import ClientSession
            from contextlib import AsyncExitStack

            # You must have node/npx installed and N8N_API_KEY / N8N_API_URL set in env
            # for full n8n management.
            params = StdioServerParameters(
                command="npx",
                args=["-y", "@n8n/mcp-server"],
                env=os.environ.copy()
            )

            self.exit_stack = AsyncExitStack()
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(params))
            read, write = stdio_transport
            
            self.session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
            
            tools_result = await self.session.list_tools()
            
            proxy_tools = []
            for t in tools_result.tools:
                # Format parameters according to our Tool schema
                proxy_tools.append(N8nMCPProxyTool(
                    name=t.name,
                    description=t.description or "",
                    schema=t.inputSchema,
                    mcp_client=self
                ))
                
            logger.info(f"Successfully connected to n8n MCP and loaded {len(proxy_tools)} tools.")
            return proxy_tools

        except Exception as e:
            logger.warning(f"Failed to start n8n MCP server: {e}")
            if self.exit_stack:
                await self.exit_stack.aclose()
            return []

    async def shutdown(self):
        if self.exit_stack:
            await self.exit_stack.aclose()

n8n_mcp_manager = N8nMCPServerManager()

async def get_n8n_tools_async() -> list[Tool]:
    """Async initializer for n8n tools."""
    return await n8n_mcp_manager.start_and_get_tools()
