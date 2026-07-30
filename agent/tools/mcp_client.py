"""
NexAlfa MCP Client Tool
Connects to external MCP (Model Context Protocol) servers to extend tool capabilities.
Inspired by Hermes Agent's MCP integration.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.mcp")


class MCPConnectTool(Tool):
    name = "mcp_connect"
    description = "Connect to an MCP (Model Context Protocol) server and list its available tools."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "server_url": {"type": "string", "description": "MCP server URL (e.g. http://localhost:3000)"},
                    "server_name": {"type": "string", "description": "Friendly name for this server"},
                },
                "required": ["server_url"],
            },
        }

    async def execute(self, server_url: str, server_name: str = "mcp-server") -> str:
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            async with sse_client(server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    tools = tools_result.tools

                    if not tools:
                        return f"Connected to {server_name} but no tools available."

                    lines = [f"✅ Connected to **{server_name}** ({server_url}):", ""]
                    for tool in tools:
                        lines.append(f"- **{tool.name}**: {tool.description or 'No description'}")

                    return "\n".join(lines)
        except ImportError:
            return "MCP client not installed. Install with: pip install mcp"
        except Exception as e:
            return f"MCP connection error: {str(e)}"


class MCPCallTool(Tool):
    name = "mcp_call"
    description = "Call a tool on a connected MCP server."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "server_url": {"type": "string", "description": "MCP server URL"},
                    "tool_name": {"type": "string", "description": "Name of the tool to call"},
                    "arguments": {"type": "object", "description": "Tool arguments as key-value pairs"},
                },
                "required": ["server_url", "tool_name"],
            },
        }

    async def execute(self, server_url: str, tool_name: str, arguments: dict = None) -> str:
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            async with sse_client(server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments or {})

                    if result.content:
                        parts = []
                        for block in result.content:
                            if hasattr(block, "text"):
                                parts.append(block.text)
                        return "\n".join(parts) if parts else "Tool returned no text content."
                    return "Tool executed but returned no content."
        except ImportError:
            return "MCP client not installed. Install with: pip install mcp"
        except Exception as e:
            return f"MCP call error: {str(e)}"


def get_mcp_tools() -> list[Tool]:
    return [MCPConnectTool(), MCPCallTool()]
