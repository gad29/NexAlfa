"""
NexAlfa Desktop Control Tools
Full computer-use agent capabilities — see the screen, click, type, manage windows,
launch apps, and control the clipboard.  Powered by pyautogui + mss + pygetwindow.

Vision loop pattern:
  1. desktop_screenshot  → Nex sees the screen
  2. desktop_click / desktop_type / desktop_hotkey → Nex acts
  3. desktop_screenshot  → Nex verifies
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.desktop")

# ── Lazy imports (only when used) ────────────────────────────

def _get_pyautogui():
    import pyautogui
    pyautogui.FAILSAFE = True   # Move mouse to corner to abort
    pyautogui.PAUSE = 0.1       # Small pause between actions
    return pyautogui

def _get_mss():
    import mss
    return mss.mss()

def _get_pygetwindow():
    import pygetwindow as gw
    return gw

def _get_pyperclip():
    import pyperclip
    return pyperclip


# ═══════════════════════════════════════════════════════════════
#  SCREEN & VISION
# ═══════════════════════════════════════════════════════════════

class DesktopScreenshotTool(Tool):
    name = "desktop_screenshot"
    description = (
        "Take a screenshot of the entire screen or a specific region. "
        "Returns a base64-encoded PNG image that you can analyze to see what's on screen. "
        "ALWAYS call this before interacting with the desktop so you know what you're clicking on."
    )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "object",
                        "description": "Optional region to capture: {x, y, width, height}. Omit for full screen.",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"},
                        },
                    },
                    "save_path": {
                        "type": "string",
                        "description": "Optional path to save the screenshot file.",
                    },
                },
                "required": [],
            },
        }

    async def execute(self, region: dict = None, save_path: str = None) -> str:
        try:
            sct = _get_mss()
            if region:
                monitor = {"left": region["x"], "top": region["y"],
                           "width": region["width"], "height": region["height"]}
            else:
                monitor = sct.monitors[0]  # Full screen (all monitors)

            img = sct.grab(monitor)

            # Convert to PIL Image
            from PIL import Image
            pil_img = Image.frombytes("RGB", (img.width, img.height), img.rgb)

            # Resize for token efficiency (max 1280px wide)
            max_w = 1280
            if pil_img.width > max_w:
                ratio = max_w / pil_img.width
                new_size = (max_w, int(pil_img.height * ratio))
                pil_img = pil_img.resize(new_size, Image.LANCZOS)

            # Save if requested
            if save_path:
                p = Path(save_path).expanduser()
                p.parent.mkdir(parents=True, exist_ok=True)
                pil_img.save(str(p))

            # Encode to base64
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG", optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            return (
                f"Screenshot captured ({pil_img.width}x{pil_img.height}). "
                f"[IMAGE:data:image/png;base64,{b64}]"
            )
        except Exception as e:
            return f"Error taking screenshot: {e}"


class DesktopFindOnScreenTool(Tool):
    name = "desktop_find_on_screen"
    description = "Find an image/icon on screen using template matching. Returns coordinates if found."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Path to the image to find on screen."},
                    "confidence": {"type": "number", "description": "Match confidence 0-1 (default 0.8)."},
                },
                "required": ["image_path"],
            },
        }

    async def execute(self, image_path: str, confidence: float = 0.8) -> str:
        try:
            gui = _get_pyautogui()
            loc = gui.locateOnScreen(image_path, confidence=confidence)
            if loc:
                center = gui.center(loc)
                return f"Found at ({center.x}, {center.y}). Region: left={loc.left}, top={loc.top}, width={loc.width}, height={loc.height}"
            return "Image not found on screen."
        except Exception as e:
            return f"Error: {e}"


class DesktopWaitForTool(Tool):
    name = "desktop_wait_for"
    description = "Wait until a specific window title appears or a timeout is reached. Useful for waiting for apps to open."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "window_title": {"type": "string", "description": "Window title to wait for (partial match)."},
                    "timeout": {"type": "integer", "description": "Max seconds to wait (default 15)."},
                },
                "required": ["window_title"],
            },
        }

    async def execute(self, window_title: str, timeout: int = 15) -> str:
        try:
            gw = _get_pygetwindow()
            start = time.time()
            while time.time() - start < timeout:
                windows = gw.getWindowsWithTitle(window_title)
                if windows:
                    return f"Window '{windows[0].title}' appeared after {time.time()-start:.1f}s."
                await asyncio.sleep(0.5)
            return f"Timeout: Window '{window_title}' did not appear within {timeout}s."
        except Exception as e:
            return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  MOUSE & KEYBOARD
# ═══════════════════════════════════════════════════════════════

class DesktopClickTool(Tool):
    name = "desktop_click"
    description = (
        "Click at specific screen coordinates (x, y). Supports left, right, and double click. "
        "Use desktop_screenshot first to identify where to click."
    )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate to click."},
                    "y": {"type": "integer", "description": "Y coordinate to click."},
                    "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "Mouse button (default: left)."},
                    "clicks": {"type": "integer", "description": "Number of clicks (default: 1, use 2 for double-click)."},
                },
                "required": ["x", "y"],
            },
        }

    async def execute(self, x: int, y: int, button: str = "left", clicks: int = 1) -> str:
        try:
            gui = _get_pyautogui()
            gui.click(x, y, clicks=clicks, button=button)
            return f"Clicked ({x}, {y}) — {button} button, {clicks}x"
        except Exception as e:
            return f"Error clicking: {e}"


class DesktopTypeTool(Tool):
    name = "desktop_type"
    description = "Type text into the currently focused application. For special keys, use desktop_hotkey instead."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type."},
                    "interval": {"type": "number", "description": "Seconds between keystrokes (default: 0.02)."},
                },
                "required": ["text"],
            },
        }

    async def execute(self, text: str, interval: float = 0.02) -> str:
        try:
            gui = _get_pyautogui()
            gui.typewrite(text, interval=interval) if text.isascii() else gui.write(text)
            return f"Typed {len(text)} characters."
        except Exception as e:
            # Fallback: use pyperclip + Ctrl+V for non-ASCII
            try:
                clip = _get_pyperclip()
                clip.copy(text)
                gui = _get_pyautogui()
                gui.hotkey("ctrl", "v")
                return f"Typed {len(text)} characters (via clipboard paste)."
            except Exception as e2:
                return f"Error typing: {e2}"


class DesktopHotkeyTool(Tool):
    name = "desktop_hotkey"
    description = (
        "Press a keyboard shortcut or special key. Examples: 'ctrl+c', 'alt+tab', 'win+d', "
        "'enter', 'escape', 'tab', 'backspace', 'delete', 'ctrl+shift+esc', 'win+i' (settings), "
        "'ctrl+a' (select all), 'f5' (refresh), 'printscreen'."
    )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "string",
                        "description": "Keys to press, joined by '+'. E.g. 'ctrl+c', 'alt+f4', 'enter', 'win+d'.",
                    },
                },
                "required": ["keys"],
            },
        }

    async def execute(self, keys: str) -> str:
        try:
            gui = _get_pyautogui()
            key_list = [k.strip().lower() for k in keys.split("+")]
            # Map common aliases
            alias = {"ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift",
                     "win": "win", "windows": "win", "cmd": "win", "super": "win",
                     "esc": "escape", "del": "delete", "bs": "backspace",
                     "return": "enter", "space": "space", "printscreen": "printscreen"}
            mapped = [alias.get(k, k) for k in key_list]
            gui.hotkey(*mapped)
            return f"Pressed: {' + '.join(mapped)}"
        except Exception as e:
            return f"Error pressing keys: {e}"


class DesktopMouseMoveTool(Tool):
    name = "desktop_mouse_move"
    description = "Move the mouse cursor to specific coordinates."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate."},
                    "y": {"type": "integer", "description": "Y coordinate."},
                    "duration": {"type": "number", "description": "Movement duration in seconds (default: 0.3)."},
                },
                "required": ["x", "y"],
            },
        }

    async def execute(self, x: int, y: int, duration: float = 0.3) -> str:
        try:
            gui = _get_pyautogui()
            gui.moveTo(x, y, duration=duration)
            return f"Mouse moved to ({x}, {y})."
        except Exception as e:
            return f"Error: {e}"


class DesktopScrollTool(Tool):
    name = "desktop_scroll"
    description = "Scroll up or down at the current mouse position or at specific coordinates."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "clicks": {"type": "integer", "description": "Scroll amount. Positive = up, negative = down."},
                    "x": {"type": "integer", "description": "X coordinate (optional)."},
                    "y": {"type": "integer", "description": "Y coordinate (optional)."},
                },
                "required": ["clicks"],
            },
        }

    async def execute(self, clicks: int, x: int = None, y: int = None) -> str:
        try:
            gui = _get_pyautogui()
            gui.scroll(clicks, x=x, y=y)
            direction = "up" if clicks > 0 else "down"
            return f"Scrolled {direction} {abs(clicks)} clicks."
        except Exception as e:
            return f"Error: {e}"


class DesktopDragTool(Tool):
    name = "desktop_drag"
    description = "Drag the mouse from one point to another. Useful for moving files, resizing windows, selecting text."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "start_x": {"type": "integer"}, "start_y": {"type": "integer"},
                    "end_x": {"type": "integer"}, "end_y": {"type": "integer"},
                    "duration": {"type": "number", "description": "Drag duration in seconds (default: 0.5)."},
                    "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "Mouse button."},
                },
                "required": ["start_x", "start_y", "end_x", "end_y"],
            },
        }

    async def execute(self, start_x: int, start_y: int, end_x: int, end_y: int,
                      duration: float = 0.5, button: str = "left") -> str:
        try:
            gui = _get_pyautogui()
            gui.moveTo(start_x, start_y, duration=0.1)
            gui.drag(end_x - start_x, end_y - start_y, duration=duration, button=button)
            return f"Dragged from ({start_x},{start_y}) to ({end_x},{end_y})."
        except Exception as e:
            return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  WINDOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════

class DesktopListWindowsTool(Tool):
    name = "desktop_list_windows"
    description = "List all open windows with their titles, positions, and sizes."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self) -> str:
        try:
            gw = _get_pygetwindow()
            windows = gw.getAllWindows()
            visible = [w for w in windows if w.title.strip() and w.visible]
            if not visible:
                return "No visible windows found."
            lines = []
            for w in visible:
                try:
                    lines.append(
                        f"• {w.title}  — pos:({w.left},{w.top}) size:{w.width}x{w.height}"
                        f"{'  [ACTIVE]' if w.isActive else ''}"
                    )
                except Exception:
                    continue
            return f"{len(lines)} open windows:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"


class DesktopFocusWindowTool(Tool):
    name = "desktop_focus_window"
    description = "Bring a window to the front by its title (partial match). E.g. 'Chrome', 'Word', 'Notepad'."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Window title to find (partial match)."},
                },
                "required": ["title"],
            },
        }

    async def execute(self, title: str) -> str:
        try:
            gw = _get_pygetwindow()
            windows = gw.getWindowsWithTitle(title)
            if not windows:
                return f"No window found matching '{title}'."
            w = windows[0]
            if w.isMinimized:
                w.restore()
            w.activate()
            return f"Focused window: '{w.title}'"
        except Exception as e:
            return f"Error: {e}"


class DesktopCloseWindowTool(Tool):
    name = "desktop_close_window"
    description = "Close a window by its title (partial match)."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Window title to close."},
                    "all_matching": {"type": "boolean", "description": "Close ALL matching windows (default: false)."},
                },
                "required": ["title"],
            },
        }

    async def execute(self, title: str, all_matching: bool = False) -> str:
        try:
            gw = _get_pygetwindow()
            windows = gw.getWindowsWithTitle(title)
            if not windows:
                return f"No window found matching '{title}'."
            targets = windows if all_matching else [windows[0]]
            closed = []
            for w in targets:
                try:
                    w.close()
                    closed.append(w.title)
                except Exception:
                    pass
            return f"Closed {len(closed)} window(s): {', '.join(closed)}"
        except Exception as e:
            return f"Error: {e}"


class DesktopResizeWindowTool(Tool):
    name = "desktop_resize_window"
    description = "Move and/or resize a window by title."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Window title (partial match)."},
                    "x": {"type": "integer", "description": "New X position."},
                    "y": {"type": "integer", "description": "New Y position."},
                    "width": {"type": "integer", "description": "New width."},
                    "height": {"type": "integer", "description": "New height."},
                    "maximize": {"type": "boolean", "description": "Maximize the window."},
                    "minimize": {"type": "boolean", "description": "Minimize the window."},
                },
                "required": ["title"],
            },
        }

    async def execute(self, title: str, x: int = None, y: int = None,
                      width: int = None, height: int = None,
                      maximize: bool = False, minimize: bool = False) -> str:
        try:
            gw = _get_pygetwindow()
            windows = gw.getWindowsWithTitle(title)
            if not windows:
                return f"No window found matching '{title}'."
            w = windows[0]
            if maximize:
                w.maximize()
                return f"Maximized: '{w.title}'"
            if minimize:
                w.minimize()
                return f"Minimized: '{w.title}'"
            if x is not None and y is not None:
                w.moveTo(x, y)
            if width and height:
                w.resizeTo(width, height)
            return f"Resized '{w.title}' — pos:({w.left},{w.top}) size:{w.width}x{w.height}"
        except Exception as e:
            return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  APP LAUNCHING & CLIPBOARD
# ═══════════════════════════════════════════════════════════════

# Smart app name → executable mapping for Windows
APP_MAP = {
    # Microsoft Office
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "outlook": "outlook", "onenote": "onenote", "teams": "msteams",
    "access": "msaccess", "publisher": "mspub",
    # Browsers
    "chrome": "chrome", "firefox": "firefox", "edge": "msedge",
    "brave": "brave", "opera": "opera", "vivaldi": "vivaldi",
    # Dev tools
    "vscode": "code", "vs code": "code", "code": "code",
    "antigravity": "code",  # Opens VS Code
    "terminal": "wt", "windows terminal": "wt",
    "cmd": "cmd", "powershell": "powershell",
    "git bash": "git-bash",
    # System
    "notepad": "notepad", "calculator": "calc", "paint": "mspaint",
    "explorer": "explorer", "file explorer": "explorer",
    "task manager": "taskmgr", "settings": "ms-settings:",
    "control panel": "control",
    "snipping tool": "snippingtool", "snip": "snippingtool",
    # Media
    "spotify": "spotify", "vlc": "vlc",
    "photos": "ms-photos:", "camera": "microsoft.windows.camera:",
    # Communication
    "discord": "discord", "slack": "slack", "zoom": "zoom",
    "whatsapp": "whatsapp", "telegram": "telegram",
    # Misc
    "steam": "steam", "obs": "obs64",
}


class DesktopOpenAppTool(Tool):
    name = "desktop_open_app"
    description = (
        "Launch an application by name or path. Smart mapping: 'word' → Microsoft Word, "
        "'chrome' → Chrome, 'vscode' → VS Code, 'settings' → Windows Settings, etc. "
        "Can also open URLs and files directly."
    )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "App name (e.g. 'chrome', 'word', 'notepad') or full path to executable.",
                    },
                    "args": {
                        "type": "string",
                        "description": "Optional arguments (e.g. URL for browser, file path for editor).",
                    },
                },
                "required": ["app"],
            },
        }

    async def execute(self, app: str, args: str = "") -> str:
        try:
            app_lower = app.lower().strip()
            exe = APP_MAP.get(app_lower, app)

            # ms-settings: and ms-photos: are URI protocols
            if exe.startswith("ms-") or exe.startswith("microsoft."):
                cmd = f'start "" "{exe}"'
            elif args:
                cmd = f'start "" "{exe}" {args}'
            else:
                cmd = f'start "" "{exe}"'

            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                shell=True,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            return f"Launched: {app}" + (f" with args: {args}" if args else "")
        except Exception as e:
            return f"Error launching {app}: {e}"


class DesktopClipboardTool(Tool):
    name = "desktop_clipboard"
    description = "Read from or write to the system clipboard."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["read", "write"], "description": "Read or write."},
                    "text": {"type": "string", "description": "Text to copy to clipboard (only for 'write')."},
                },
                "required": ["action"],
            },
        }

    async def execute(self, action: str, text: str = "") -> str:
        try:
            clip = _get_pyperclip()
            if action == "write":
                clip.copy(text)
                return f"Copied {len(text)} chars to clipboard."
            else:
                content = clip.paste()
                return f"Clipboard content ({len(content)} chars):\n{content[:2000]}"
        except Exception as e:
            return f"Error: {e}"


# ── Export ────────────────────────────────────────────────────

def get_desktop_tools() -> list[Tool]:
    """Get all desktop control tools."""
    tools = [
        # Screen & Vision
        DesktopScreenshotTool(),
        DesktopFindOnScreenTool(),
        DesktopWaitForTool(),
        # Mouse & Keyboard
        DesktopClickTool(),
        DesktopTypeTool(),
        DesktopHotkeyTool(),
        DesktopMouseMoveTool(),
        DesktopScrollTool(),
        DesktopDragTool(),
        # Window Management
        DesktopListWindowsTool(),
        DesktopFocusWindowTool(),
        DesktopCloseWindowTool(),
        DesktopResizeWindowTool(),
        # Apps & Clipboard
        DesktopOpenAppTool(),
        DesktopClipboardTool(),
    ]
    for t in tools:
        t.category = "desktop"
    return tools
