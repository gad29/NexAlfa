"""
NexAlfa Dev Tools
Open IDEs, scaffold projects, run builds, monitor processes, git operations.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.devtools")


class DevOpenProjectTool(Tool):
    name = "dev_open_project"
    description = (
        "Open a project folder in VS Code, Antigravity, or another IDE. "
        "Example: dev_open_project(ide='vscode', path='C:/Users/G.H/Coding/MyApp')"
    )

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "ide": {"type": "string", "enum": ["vscode", "antigravity", "cursor", "windsurf"], "description": "IDE to open."},
                    "path": {"type": "string", "description": "Project directory path."},
                },
                "required": ["path"],
            },
        }

    async def execute(self, path: str, ide: str = "vscode") -> str:
        try:
            p = str(Path(path).expanduser().resolve())
            exe_map = {"vscode": "code", "antigravity": "code", "cursor": "cursor", "windsurf": "windsurf"}
            exe = exe_map.get(ide, "code")
            proc = await asyncio.create_subprocess_shell(
                f'"{exe}" "{p}"',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            return f"Opened {p} in {ide}."
        except Exception as e:
            return f"Error: {e}"


class DevCreateProjectTool(Tool):
    name = "dev_create_project"
    description = (
        "Scaffold a new project. Supported: vite, nextjs, python, html. "
        "Creates the directory, initializes the project, and optionally opens it."
    )

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "template": {"type": "string", "enum": ["vite", "nextjs", "python", "html"], "description": "Project template."},
                    "path": {"type": "string", "description": "Directory for the new project."},
                    "name": {"type": "string", "description": "Project name."},
                    "open_in_ide": {"type": "boolean", "description": "Open in VS Code after creation (default: true)."},
                },
                "required": ["template", "path"],
            },
        }

    async def execute(self, template: str, path: str, name: str = "my-project", open_in_ide: bool = True) -> str:
        try:
            p = Path(path).expanduser().resolve()
            p.mkdir(parents=True, exist_ok=True)

            cmds = {
                "vite": f'npx -y create-vite@latest "{name}" --template vanilla',
                "nextjs": f'npx -y create-next-app@latest "{name}" --ts --tailwind --eslint --app --no-src-dir --import-alias "@/*"',
                "python": f'mkdir "{name}" && cd "{name}" && python -m venv venv && echo # {name} > README.md',
                "html": None,  # Manual creation
            }

            if template == "html":
                proj_dir = p / name
                proj_dir.mkdir(exist_ok=True)
                (proj_dir / "index.html").write_text(f'<!DOCTYPE html>\n<html><head><title>{name}</title><link rel="stylesheet" href="style.css"></head>\n<body><h1>{name}</h1><script src="main.js"></script></body></html>')
                (proj_dir / "style.css").write_text("* { margin:0; padding:0; box-sizing:border-box; }\nbody { font-family: system-ui; }")
                (proj_dir / "main.js").write_text(f'console.log("{name} loaded");')
                result = f"HTML project created at {proj_dir}"
            else:
                cmd = cmds[template]
                proc = await asyncio.create_subprocess_shell(
                    cmd, cwd=str(p),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                result = stdout.decode("utf-8", errors="replace")

            proj_path = str(p / name)
            if open_in_ide:
                await asyncio.create_subprocess_shell(f'code "{proj_path}"')

            return f"✅ {template} project '{name}' created at {proj_path}\n{result[:500]}"
        except Exception as e:
            return f"Error: {e}"


class DevRunCommandTool(Tool):
    name = "dev_run_command"
    description = "Run a dev command (npm run dev, python manage.py, etc.) in a project directory. Returns output."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to run."},
                    "cwd": {"type": "string", "description": "Working directory."},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30)."},
                    "background": {"type": "boolean", "description": "Run in background (don't wait for completion)."},
                },
                "required": ["command", "cwd"],
            },
        }

    async def execute(self, command: str, cwd: str, timeout: int = 30, background: bool = False) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                command, cwd=cwd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            if background:
                return f"Process started in background (PID: {proc.pid}). Use pc_running_processes to monitor."
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = stdout.decode("utf-8", errors="replace")
            if stderr:
                out += f"\n[stderr] {stderr.decode('utf-8', errors='replace')}"
            out += f"\n[exit: {proc.returncode}]"
            return out[:3000]
        except asyncio.TimeoutError:
            return f"Command still running after {timeout}s (PID: {proc.pid}). It may be a long-running server."
        except Exception as e:
            return f"Error: {e}"


class DevMonitorProcessTool(Tool):
    name = "dev_monitor_process"
    description = "Check if a process is still running by PID or name. Useful for monitoring builds and servers."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "Process ID to check."},
                    "name": {"type": "string", "description": "Process name to check."},
                },
                "required": [],
            },
        }

    async def execute(self, pid: int = None, name: str = None) -> str:
        try:
            if pid:
                cmd = f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object ProcessName,Id,CPU,WorkingSet64,StartTime | Format-List | Out-String"
            elif name:
                cmd = f"Get-Process -Name '{name}' -ErrorAction SilentlyContinue | Select-Object ProcessName,Id,CPU,@{{N='RAM_MB';E={{[math]::Round($_.WorkingSet64/1MB)}}}} | Format-Table | Out-String"
            else:
                return "Provide pid or name."
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-NoProfile", "-Command", cmd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            result = stdout.decode("utf-8", errors="replace").strip()
            return result if result else f"Process {'PID ' + str(pid) if pid else name} not found (may have exited)."
        except Exception as e:
            return f"Error: {e}"


class DevGitTool(Tool):
    name = "dev_git"
    description = "Git operations: status, log, commit, push, pull, branch, diff. Runs git commands in a project directory."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Git subcommand (e.g. 'status', 'log -5', 'commit -m \"msg\"', 'push', 'diff')."},
                    "cwd": {"type": "string", "description": "Project directory with .git folder."},
                },
                "required": ["command", "cwd"],
            },
        }

    async def execute(self, command: str, cwd: str) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                f"git {command}", cwd=cwd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            out = stdout.decode("utf-8", errors="replace")
            if stderr:
                out += stderr.decode("utf-8", errors="replace")
            return out[:3000] or "(no output)"
        except Exception as e:
            return f"Error: {e}"


def get_devtools() -> list[Tool]:
    tools = [
        DevOpenProjectTool(),
        DevCreateProjectTool(),
        DevRunCommandTool(),
        DevMonitorProcessTool(),
        DevGitTool(),
    ]
    for t in tools:
        t.category = "devtools"
    return tools
