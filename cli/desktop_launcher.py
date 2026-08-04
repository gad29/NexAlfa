"""
NexAlfa Desktop App Launcher
Launches a native PC desktop chat window pointing to the local NexAlfa Web UI.
Uses pywebview if available, or falls back to system browser in app-mode.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import webbrowser
import httpx
from rich.console import Console

console = Console()
logger = logging.getLogger("nex.desktop")


def launch_desktop_app(port: int = 18789):
    """Launch the PC desktop chat app."""
    url = f"http://localhost:3000"  # Next.js web UI
    gateway_url = f"http://localhost:{port}"

    console.print("[cyan]🖥️ Starting NexAlfa Desktop Chat Window...[/cyan]")

    # Check if web UI / gateway is running
    try:
        httpx.get(f"{gateway_url}/health", timeout=1.0)
    except Exception:
        console.print("⚠️ Gateway server is not running. Starting gateway in background...")
        import subprocess
        subprocess.Popen([sys.executable, "-m", "gateway.server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.0)

    # Try PyWebView for native window
    try:
        import webview
        console.print("[green]✅ Opening native desktop window...[/green]")
        webview.create_window(
            title="NexAlfa — Personal AI Agent",
            url=url,
            width=1200,
            height=800,
            resizable=True,
            text_select=True,
            confirm_close=False,
        )
        webview.start()
    except ImportError:
        console.print("ℹ️  pywebview not installed. Opening browser app window...")
        # Open browser in app mode
        if sys.platform == "win32":
            os.system(f'start msedge --app="{url}"')
        elif sys.platform == "darwin":
            os.system(f'open -n -a "Google Chrome" --args --app="{url}"')
        else:
            webbrowser.open(url)
