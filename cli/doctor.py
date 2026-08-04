"""
NexAlfa Environment & Health Diagnostic Tool
Command: `nexalfa doctor`
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def run_doctor() -> dict[str, bool]:
    """Run full diagnostic check on NexAlfa environment."""
    console.print(Panel(
        "[bold cyan]🩺 NexAlfa System Doctor[/bold cyan]\n"
        "Diagnosing system dependencies, configuration, and environment health...",
        title="Diagnostic",
        border_style="cyan",
    ))

    results = {}
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="bold")
    table.add_column("Status", width=12)
    table.add_column("Details")

    # 1. Python Check
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    results["python"] = py_ok
    table.add_row(
        "Python Version",
        "[green]✓ OK[/green]" if py_ok else "[red]✗ FAIL[/red]",
        f"v{py_ver} ({sys.executable})"
    )

    # 2. Node.js Check
    node_ok = False
    node_ver = "Not installed"
    try:
        import subprocess
        out = subprocess.check_output(["node", "--version"], text=True).strip()
        node_ver = out
        node_ok = True
    except Exception:
        pass
    results["node"] = node_ok
    table.add_row(
        "Node.js Runtime",
        "[green]✓ OK[/green]" if node_ok else "[yellow]⚠️ Warning[/yellow]",
        f"{node_ver} (required for WhatsApp Web bridge)"
    )

    # 3. Environment File
    env_ok = Path(".env").exists()
    results["env_file"] = env_ok
    table.add_row(
        "Configuration (.env)",
        "[green]✓ OK[/green]" if env_ok else "[yellow]⚠️ Missing[/yellow]",
        ".env file present" if env_ok else "Run 'nexalfa onboard' to create .env"
    )

    # 4. Identity SOUL.md
    soul_path = Path("workspace/SOUL.md")
    soul_ok = soul_path.exists()
    results["soul_file"] = soul_ok
    table.add_row(
        "Agent Persona (SOUL.md)",
        "[green]✓ OK[/green]" if soul_ok else "[yellow]⚠️ Missing[/yellow]",
        str(soul_path) if soul_ok else "Run 'nexalfa onboard' to generate SOUL.md"
    )

    # 5. Storage Directory Permissions
    storage_dir = Path("storage")
    storage_ok = storage_dir.exists() and os.access(storage_dir, os.W_OK)
    results["storage"] = storage_ok
    table.add_row(
        "Storage Directory",
        "[green]✓ OK[/green]" if storage_ok else "[red]✗ FAIL[/red]",
        f"{storage_dir.resolve()} (Writable)" if storage_ok else "Storage path not writable"
    )

    # 6. API Keys Check
    from agent.config.settings import get_settings
    settings = get_settings()
    has_key = bool(
        settings.model.openai_api_key or
        settings.model.google_api_key or
        settings.model.openrouter_api_key or
        settings.model.ollama_base_url
    )
    results["api_keys"] = has_key
    table.add_row(
        "AI Provider Credentials",
        "[green]✓ OK[/green]" if has_key else "[red]✗ Missing[/red]",
        f"Default model: {settings.model.default_model}" if has_key else "No API key configured"
    )

    # 7. System Permissions
    from agent.core.permissions import permissions_manager
    perms = permissions_manager.get_all()
    table.add_row(
        "System Permissions",
        "[green]✓ Active[/green]",
        f"Shell: {perms.get('allow_shell')}, Desktop: {perms.get('allow_desktop')}, Browser: {perms.get('allow_browser')}"
    )

    console.print(table)
    console.print()

    all_passed = all([py_ok, storage_ok, has_key])
    if all_passed:
        console.print(Panel("[bold green]✅ All critical system checks passed! NexAlfa is healthy.[/bold green]", border_style="green"))
    else:
        console.print(Panel("[bold yellow]⚠️ Some checks require attention. Run 'nexalfa onboard' to fix.[/bold yellow]", border_style="yellow"))

    return results
