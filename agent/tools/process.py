"""
NexAlfa Process Tool
Execute shell commands — unrestricted (dev-mode). No permission gates.
"""

from __future__ import annotations

import asyncio
import os

from agent.tools.base import Tool


class ShellTool(Tool):
    name = "shell"
    description = "Execute a shell command and return stdout/stderr. No restrictions."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "cwd": {"type": "string", "description": "Working directory (optional)"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default: 60)"},
                },
                "required": ["command"],
            },
        }

    async def execute(self, command: str, cwd: str = None, timeout: int = 60) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or os.getcwd(),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = ""
            if stdout:
                output += stdout.decode("utf-8", errors="replace")
            if stderr:
                output += f"\n[stderr]\n{stderr.decode('utf-8', errors='replace')}"
            output += f"\n[exit code: {proc.returncode}]"
            return output.strip()
        except asyncio.TimeoutError:
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"


def get_process_tools() -> list[Tool]:
    return [ShellTool()]
