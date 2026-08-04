"""
NexAlfa CLI
Entry point for the `nexalfa` / `nex` command.
Full command tree for managing the agent, channels, sub-agents, and settings.
"""

from __future__ import annotations

import asyncio
import os
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """NexAlfa — Your personal AI agent. No guardrails."""
    if ctx.invoked_subcommand is None:
        # First run? → onboarding
        from cli.onboarding import is_first_run
        if is_first_run():
            from cli.onboarding import run_onboarding
            run_onboarding()
        else:
            ctx.invoke(chat)


# ═══════════════════════════════════════════════════════════
# Core Commands
# ═══════════════════════════════════════════════════════════

@cli.command()
def chat():
    """Start interactive chat with Nex."""
    from agent.core.agent import NexAgent
    from agent.config.settings import get_settings

    settings = get_settings()
    agent = NexAgent()

    console.print(Panel(
        f"[bold cyan]🤖 {settings.agent_name}[/bold cyan] — Ready to chat\n"
        f"[dim]Model: {settings.model.default_model}[/dim]\n"
        f"[dim]Type /help for commands, Ctrl+C to exit[/dim]",
        border_style="cyan",
    ))

    async def run():
        await agent.initialize()
        try:
            while True:
                try:
                    user_input = console.input("[bold green]You:[/bold green] ")
                    if not user_input.strip():
                        continue

                    if user_input.strip().lower() in ("exit", "quit", "/exit", "/quit"):
                        break

                    if user_input.strip() == "/help":
                        console.print(Markdown(HELP_TEXT))
                        continue

                    console.print(f"[bold cyan]{settings.agent_name}:[/bold cyan] ", end="")
                    response = await agent.process_message(
                        content=user_input,
                        channel="cli",
                        channel_id="local",
                    )
                    console.print(Markdown(response))
                    console.print()

                except KeyboardInterrupt:
                    break

        finally:
            await agent.shutdown()
            console.print("\n[dim]👋 See you later![/dim]")

    asyncio.run(run())


@cli.command()
def gateway():
    """Start the gateway server."""
    from gateway.server import start_gateway
    start_gateway()


@cli.command()
def onboard():
    """Run the interactive setup wizard."""
    from cli.onboarding import run_onboarding
    run_onboarding()


@cli.command()
def setup():
    """Re-run setup (non-destructive)."""
    from cli.onboarding import run_onboarding
    run_onboarding()


@cli.command(name="app")
def app_command():
    """Launch native PC desktop chat window."""
    from cli.desktop_launcher import launch_desktop_app
    launch_desktop_app()


@cli.command(name="desktop")
def desktop_command():
    """Launch native PC desktop chat window."""
    from cli.desktop_launcher import launch_desktop_app
    launch_desktop_app()


@cli.command(name="doctor")
def doctor_command():
    """Run environment health diagnostics."""
    from cli.doctor import run_doctor
    run_doctor()


@cli.group(name="domain")
def domain_group():
    """Manage custom domain setup."""
    pass


@domain_group.command(name="setup")
def domain_setup_command():
    """Configure custom domain & reverse proxy."""
    from cli.domain_setup import run_domain_setup
    run_domain_setup()


# ═══════════════════════════════════════════════════════════
# Status & Diagnostics
# ═══════════════════════════════════════════════════════════

@cli.command()
def status():
    """Show full agent status."""
    from agent.config.settings import get_settings
    settings = get_settings()

    table = Table(title="NexAlfa Status", show_header=False, border_style="cyan")
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Agent", settings.agent_name)
    table.add_row("Model", settings.model.default_model)
    table.add_row("Gateway", f"{settings.gateway.host}:{settings.gateway.port}")
    table.add_row("Dev Mode", "ON" if settings.dev_mode.enabled else "OFF")
    table.add_row("Workspace", str(settings.workspace_path))
    table.add_row("Storage", str(settings.storage_path))
    table.add_row("Fallbacks", ", ".join(settings.model.fallback_models) or "None")

    # Voice
    voice_mode = os.environ.get("NEX_VOICE_MODE", "auto")
    table.add_row("Voice Mode", voice_mode)
    table.add_row("TTS Voice", os.environ.get("NEX_TTS_VOICE", "alloy"))

    console.print(table)


@cli.command()
def doctor():
    """Diagnose issues with the setup."""
    from agent.config.settings import get_settings
    import shutil

    settings = get_settings()
    console.print("[bold]🩺 NexAlfa Doctor[/bold]\n")

    checks = []

    # Workspace
    if settings.workspace_path.exists():
        checks.append(("Workspace", "✅", str(settings.workspace_path)))
    else:
        checks.append(("Workspace", "❌", f"Not found: {settings.workspace_path}"))

    # SOUL.md
    if settings.soul_path.exists():
        checks.append(("SOUL.md", "✅", "Loaded"))
    else:
        checks.append(("SOUL.md", "⚠️", "Not found — using default personality"))

    # API Keys
    if settings.model.openai_api_key or os.environ.get("OPENAI_API_KEY"):
        checks.append(("OpenAI API", "✅", "Key configured"))
    else:
        checks.append(("OpenAI API", "⚠️", "Not configured"))

    if settings.model.google_api_key or os.environ.get("GOOGLE_API_KEY"):
        checks.append(("Google API", "✅", "Key configured"))
    else:
        checks.append(("Google API", "⚠️", "Not configured"))

    if settings.model.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY"):
        checks.append(("OpenRouter API", "✅", "Key configured"))
    else:
        checks.append(("OpenRouter API", "⚠️", "Not configured"))

    if settings.model.ollama_base_url or os.environ.get("OLLAMA_API_BASE"):
        checks.append(("Ollama", "✅", f"URL: {settings.model.ollama_base_url or os.environ.get('OLLAMA_API_BASE')}"))
    else:
        checks.append(("Ollama", "⚪", "Not configured"))

    # Channels
    if settings.channels.telegram_bot_token:
        checks.append(("Telegram", "✅", "Token configured"))
    else:
        checks.append(("Telegram", "⚪", "Not configured"))

    if settings.channels.discord_bot_token:
        checks.append(("Discord", "✅", "Token configured"))
    else:
        checks.append(("Discord", "⚪", "Not configured"))

    # FFmpeg
    if shutil.which("ffmpeg"):
        checks.append(("FFmpeg", "✅", "Found"))
    else:
        checks.append(("FFmpeg", "⚠️", "Not found — voice features won't work"))

    # Python version
    import platform
    checks.append(("Python", "✅", platform.python_version()))

    # Node.js
    if shutil.which("node"):
        checks.append(("Node.js", "✅", "Found"))
    else:
        checks.append(("Node.js", "⚠️", "Not found — web UI and WhatsApp bridge won't work"))

    for name, status_icon, detail in checks:
        console.print(f"  {status_icon} [bold]{name}[/bold]: {detail}")


# ═══════════════════════════════════════════════════════════
# Set Command Group (model, thinking, provider, soul)
# ═══════════════════════════════════════════════════════════

@cli.group()
def set():
    """Change agent settings."""
    pass


@set.command("model")
@click.argument("model_id")
def set_model(model_id):
    """Set the default model. Example: nexalfa set model openai/gpt-4o"""
    import httpx
    try:
        r = httpx.post("http://localhost:18789/api/model", json={"model": model_id}, timeout=5)
        if r.status_code == 200:
            console.print(f"✅ Model set to: [bold]{model_id}[/bold]")
        else:
            console.print(f"❌ Failed: {r.text}")
    except httpx.ConnectError:
        console.print("❌ Gateway not running. Start it first: [bold cyan]nexalfa gateway[/bold cyan]")


@set.command("thinking")
@click.argument("level", type=click.Choice(["none", "low", "medium", "high"]))
def set_thinking(level):
    """Set thinking level. Example: nexalfa set thinking high"""
    import httpx
    try:
        r = httpx.post("http://localhost:18789/api/thinking", json={"level": level}, timeout=5)
        if r.status_code == 200:
            console.print(f"✅ Thinking level: [bold]{level}[/bold]")
        else:
            console.print(f"❌ Failed: {r.text}")
    except httpx.ConnectError:
        console.print("❌ Gateway not running.")


@set.command("provider")
@click.argument("name", type=click.Choice(["openai", "google", "openrouter", "ollama"]))
@click.option("--key", prompt=True, hide_input=True, help="API key")
def set_provider(name, key):
    """Set a provider API key. Example: nexalfa set provider openai --key sk-..."""
    env_map = {
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "ollama": "OLLAMA_API_BASE",
    }
    env_key = env_map[name]

    # Update .env file
    env_path = Path(".env")
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{env_key}="):
            lines[i] = f"{env_key}={key}"
            found = True
            break
    if not found:
        lines.append(f"{env_key}={key}")
    env_path.write_text("\n".join(lines), encoding="utf-8")
    os.environ[env_key] = key
    console.print(f"✅ {name.title()} key saved to .env")


@set.command("soul")
def set_soul():
    """Edit the SOUL.md personality file."""
    soul_path = Path("workspace/SOUL.md")
    if not soul_path.exists():
        console.print("⚠️ SOUL.md not found. Run: nexalfa onboard")
        return
    editor = os.environ.get("EDITOR", "notepad" if sys.platform == "win32" else "nano")
    os.system(f"{editor} {soul_path}")
    console.print(f"✅ SOUL.md saved. Changes take effect on next message.")


# ═══════════════════════════════════════════════════════════
# Connect Command (channels)
# ═══════════════════════════════════════════════════════════

@cli.command()
@click.argument("channel", type=click.Choice(["whatsapp", "telegram", "discord", "email", "slack", "google-chat"]))
def connect(channel):
    """Connect a channel. Example: nexalfa connect whatsapp"""
    if channel == "whatsapp":
        console.print(Panel(
            "[bold]📱 WhatsApp Connection[/bold]\n\n"
            "1. Make sure the gateway is running: [cyan]nexalfa gateway[/cyan]\n"
            "2. The WhatsApp bridge will generate a QR code\n"
            "3. Scan it with WhatsApp on your phone\n\n"
            "Starting WhatsApp bridge...",
            border_style="green",
        ))
        # Start the bridge process
        bridge_path = Path("gateway/channels/whatsapp_bridge.js")
        if bridge_path.exists():
            os.system(f"node {bridge_path}")
        else:
            console.print("⚠️ WhatsApp bridge not found. The bridge is being set up...")
            console.print("   For now, use the Meta Business API method:")
            console.print("   1. Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID in .env")
            console.print("   2. Set up webhook URL: https://your-domain/webhook/whatsapp")

    elif channel == "telegram":
        from agent.config.settings import get_settings
        settings = get_settings()
        if not settings.channels.telegram_bot_token:
            token = click.prompt("Telegram Bot Token (from @BotFather)")
            # Save to .env
            _append_env("TELEGRAM_BOT_TOKEN", token)
            console.print("✅ Token saved. Restart the gateway to activate.")
        else:
            console.print("✅ Telegram already configured. Restart gateway to reconnect.")

    elif channel == "discord":
        from agent.config.settings import get_settings
        settings = get_settings()
        if not settings.channels.discord_bot_token:
            token = click.prompt("Discord Bot Token")
            _append_env("DISCORD_BOT_TOKEN", token)
            console.print("✅ Token saved. Restart the gateway to activate.")
        else:
            console.print("✅ Discord already configured. Restart gateway to reconnect.")

    elif channel == "email":
        server = click.prompt("IMAP Server", default="imap.gmail.com")
        address = click.prompt("Email Address")
        password = click.prompt("Password (app password)", hide_input=True)
        _append_env("EMAIL_IMAP_SERVER", server)
        _append_env("EMAIL_ADDRESS", address)
        _append_env("EMAIL_PASSWORD", password)
        console.print("✅ Email configured. Restart the gateway to activate.")

    else:
        console.print(f"⚠️ {channel} connection not yet automated. Configure in .env and restart gateway.")


@cli.command()
@click.argument("channel", type=click.Choice(["whatsapp", "telegram", "discord", "email", "slack", "google-chat"]))
def disconnect(channel):
    """Disconnect a channel."""
    console.print(f"⚠️ To disconnect {channel}, remove its credentials from .env and restart the gateway.")


# ═══════════════════════════════════════════════════════════
# Agents Command (sub-agents)
# ═══════════════════════════════════════════════════════════

@cli.group()
def agents():
    """Manage sub-agents."""
    pass


@agents.command("list")
def agents_list():
    """List all sub-agents."""
    import httpx
    try:
        r = httpx.get("http://localhost:18789/api/agents", timeout=5)
        data = r.json()
        if data.get("definitions"):
            table = Table(title="Sub-Agents")
            table.add_column("Name", style="cyan")
            table.add_column("Model")
            table.add_column("Description")
            for d in data["definitions"]:
                table.add_row(d["name"], d["model"], d.get("description", ""))
            console.print(table)
        else:
            console.print("No sub-agents defined. Create one with: nexalfa agents create")
    except httpx.ConnectError:
        # Read from filesystem
        from pathlib import Path
        agents_dir = Path("workspace/agents")
        if agents_dir.exists():
            files = list(agents_dir.glob("*.md"))
            if files:
                for f in files:
                    console.print(f"  📋 {f.stem}")
            else:
                console.print("No sub-agents found in workspace/agents/")
        else:
            console.print("No sub-agents directory. Create one with: nexalfa agents create")


@agents.command("create")
@click.option("--name", prompt=True, help="Agent name")
@click.option("--description", prompt=True, help="What this agent does")
@click.option("--model", default="inherit", help="Model to use (default: inherit from main)")
def agents_create(name, description, model):
    """Create a new sub-agent."""
    from pathlib import Path
    agents_dir = Path("workspace/agents")
    agents_dir.mkdir(parents=True, exist_ok=True)

    prompt = click.prompt("System prompt for this agent", default=f"You are {name}, a specialized assistant.")

    content = f"""---
name: {name}
description: {description}
model: {model}
thinking: medium
maxTurns: 50
---

{prompt}
"""
    path = agents_dir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    console.print(f"✅ Sub-agent '{name}' created at {path}")


@agents.command("delete")
@click.argument("name")
def agents_delete(name):
    """Delete a sub-agent."""
    from pathlib import Path
    path = Path("workspace/agents") / f"{name}.md"
    if path.exists():
        path.unlink()
        console.print(f"✅ Sub-agent '{name}' deleted.")
    else:
        console.print(f"❌ Sub-agent '{name}' not found.")


# ═══════════════════════════════════════════════════════════
# Logs
# ═══════════════════════════════════════════════════════════

@cli.command()
@click.option("--lines", "-n", default=50, help="Number of lines to show")
def logs(lines):
    """Tail gateway logs."""
    import subprocess
    log_path = Path("storage/nexalfa.log")
    if log_path.exists():
        subprocess.run(["tail", "-n", str(lines), "-f", str(log_path)])
    else:
        console.print("No log file found. Gateway writes to stdout by default.")
        console.print("Tip: redirect output: nexalfa gateway 2>&1 | tee storage/nexalfa.log")


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

from pathlib import Path

def _append_env(key: str, value: str):
    """Add or update a key in .env."""
    env_path = Path(".env")
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines), encoding="utf-8")


HELP_TEXT = """
## Commands
- `/new` / `/reset` — Clear session
- `/model [provider/model]` — Switch or show model
- `/think [none|low|medium|high]` — Set thinking level
- `/personality [name]` — Switch personality
- `/skills` — List skills
- `/agents` — List sub-agents
- `/status` — Agent status
- `/usage` — Token usage
- `/compact` — Compress context
- `/search <query>` — Search past conversations
- `/memories` — Memory stats
- `exit` / `quit` — Exit chat
"""

if __name__ == "__main__":
    cli()
