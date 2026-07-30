"""
NexAlfa Browser Automation System
Full Playwright-based browser control — persistent session, multi-tab,
screenshots, clicking, typing, scrolling, JS execution, form filling, and more.
Gives Nex the same browser powers as a human operator.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from pathlib import Path
from typing import Optional

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.browser")

# ── Persistent Browser Session ──────────────────────────────

class BrowserSession:
    """Singleton persistent browser session shared across all browser tools."""

    _instance: Optional["BrowserSession"] = None

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._pages: dict[str, any] = {}  # tab_id -> page
        self._active_tab: Optional[str] = None
        self._screenshot_dir = Path("storage/screenshots")
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get(cls) -> "BrowserSession":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def ensure_browser(self):
        if self._browser is None:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                ),
                java_script_enabled=True,
                accept_downloads=True,
            )
            logger.info("🌐 Browser launched (Playwright/Chromium, persistent session)")

    @property
    def active_page(self):
        if self._active_tab and self._active_tab in self._pages:
            return self._pages[self._active_tab]
        return None

    async def new_tab(self, url: str = "about:blank") -> str:
        await self.ensure_browser()
        page = await self._context.new_page()
        tab_id = f"tab_{len(self._pages) + 1}_{int(time.time()) % 10000}"
        self._pages[tab_id] = page
        self._active_tab = tab_id
        if url != "about:blank":
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(1)
        return tab_id

    async def close_tab(self, tab_id: str = None):
        tid = tab_id or self._active_tab
        if tid and tid in self._pages:
            await self._pages[tid].close()
            del self._pages[tid]
            self._active_tab = next(iter(self._pages), None) if self._pages else None

    async def close_all(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
            self._pages.clear()
            self._active_tab = None
        if self._pw:
            await self._pw.stop()
            self._pw = None

    def list_tabs(self) -> list[dict]:
        result = []
        for tid, page in self._pages.items():
            result.append({
                "tab_id": tid,
                "url": page.url,
                "active": tid == self._active_tab,
            })
        return result


# ── Helper to get page or error ─────────────────────────────

def _session() -> BrowserSession:
    return BrowserSession.get()

async def _get_page(tab_id: str = None):
    s = _session()
    await s.ensure_browser()
    if tab_id and tab_id in s._pages:
        s._active_tab = tab_id
        return s._pages[tab_id]
    if s.active_page:
        return s.active_page
    # Auto-open a blank tab if none exists
    tid = await s.new_tab()
    return s._pages[tid]


# ── Tool Implementations ────────────────────────────────────

class BrowserOpenTool(Tool):
    name = "browser_open"
    description = "Open a URL in the browser. Creates a new tab or navigates the current one."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open"},
                    "new_tab": {"type": "boolean", "description": "Open in new tab (default: false)"},
                    "wait_until": {"type": "string", "enum": ["load", "domcontentloaded", "networkidle"],
                                   "description": "Wait condition (default: domcontentloaded)"},
                },
                "required": ["url"],
            },
        }

    async def execute(self, url: str, new_tab: bool = False, wait_until: str = "domcontentloaded") -> str:
        try:
            s = _session()
            if new_tab or not s.active_page:
                tab_id = await s.new_tab(url)
                page = s._pages[tab_id]
            else:
                page = await _get_page()
                await page.goto(url, wait_until=wait_until, timeout=20000)
                await asyncio.sleep(1)
            title = await page.title()
            return f"✅ Opened: {url}\nTitle: {title}\nTab: {s._active_tab}"
        except Exception as e:
            return f"❌ Browser open failed: {e}"


class BrowserScreenshotTool(Tool):
    name = "browser_screenshot"
    description = "Take a screenshot of the current page. Can capture full page or a specific element."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector to screenshot a specific element (optional)"},
                    "full_page": {"type": "boolean", "description": "Capture full scrollable page (default: false)"},
                    "filename": {"type": "string", "description": "Save filename (optional, auto-generated if omitted)"},
                },
            },
        }

    async def execute(self, selector: str = None, full_page: bool = False, filename: str = None) -> str:
        try:
            page = await _get_page()
            s = _session()
            fname = filename or f"screenshot_{int(time.time())}.png"
            fpath = s._screenshot_dir / fname

            if selector:
                elem = await page.query_selector(selector)
                if not elem:
                    return f"❌ Element not found: {selector}"
                data = await elem.screenshot(type="png")
            else:
                data = await page.screenshot(type="png", full_page=full_page)

            fpath.write_bytes(data)
            b64 = base64.b64encode(data).decode("utf-8")
            return (
                f"📸 Screenshot saved: {fpath} ({len(data)} bytes)\n"
                f"Page: {page.url}\n"
                f"Base64 preview: {b64[:200]}..."
            )
        except Exception as e:
            return f"❌ Screenshot failed: {e}"


class BrowserClickTool(Tool):
    name = "browser_click"
    description = "Click an element on the page by CSS selector or text content."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or text content (e.g. 'text=Login')"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "Mouse button (default: left)"},
                    "double_click": {"type": "boolean", "description": "Double-click instead of single click"},
                    "wait_after": {"type": "number", "description": "Seconds to wait after click (default: 1)"},
                },
                "required": ["selector"],
            },
        }

    async def execute(self, selector: str, button: str = "left", double_click: bool = False, wait_after: float = 1) -> str:
        try:
            page = await _get_page()
            if double_click:
                await page.dblclick(selector, button=button, timeout=5000)
            else:
                await page.click(selector, button=button, timeout=5000)
            await asyncio.sleep(wait_after)
            new_url = page.url
            return f"✅ Clicked '{selector}' (button={button}). Current URL: {new_url}"
        except Exception as e:
            return f"❌ Click failed on '{selector}': {e}"


class BrowserTypeTool(Tool):
    name = "browser_type"
    description = "Type text into an input field. Can clear existing text first."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the input field"},
                    "text": {"type": "string", "description": "Text to type"},
                    "clear_first": {"type": "boolean", "description": "Clear the field before typing (default: true)"},
                    "press_enter": {"type": "boolean", "description": "Press Enter after typing (default: false)"},
                    "delay_ms": {"type": "integer", "description": "Delay between keystrokes in ms (default: 0, instant)"},
                },
                "required": ["selector", "text"],
            },
        }

    async def execute(self, selector: str, text: str, clear_first: bool = True, press_enter: bool = False, delay_ms: int = 0) -> str:
        try:
            page = await _get_page()
            if clear_first:
                await page.fill(selector, "", timeout=5000)
            if delay_ms > 0:
                await page.type(selector, text, delay=delay_ms, timeout=5000)
            else:
                await page.fill(selector, text, timeout=5000)
            if press_enter:
                await page.press(selector, "Enter")
                await asyncio.sleep(1)
            return f"✅ Typed '{text[:50]}{'...' if len(text) > 50 else ''}' into '{selector}'" + (" + Enter" if press_enter else "")
        except Exception as e:
            return f"❌ Type failed on '{selector}': {e}"


class BrowserGetTextTool(Tool):
    name = "browser_get_text"
    description = "Extract visible text content from the page or a specific element."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector (default: body = full page text)"},
                    "max_length": {"type": "integer", "description": "Max characters to return (default: 5000)"},
                },
            },
        }

    async def execute(self, selector: str = "body", max_length: int = 5000) -> str:
        try:
            page = await _get_page()
            title = await page.title()
            text = await page.inner_text(selector, timeout=5000)
            url = page.url
            text = text[:max_length]
            return f"URL: {url}\nTitle: {title}\n\n{text}"
        except Exception as e:
            return f"❌ Get text failed: {e}"


class BrowserScrollTool(Tool):
    name = "browser_scroll"
    description = "Scroll the page up, down, or to a specific element."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down", "top", "bottom"], "description": "Scroll direction"},
                    "pixels": {"type": "integer", "description": "Pixels to scroll (default: 500)"},
                    "selector": {"type": "string", "description": "Scroll to this element instead"},
                },
            },
        }

    async def execute(self, direction: str = "down", pixels: int = 500, selector: str = None) -> str:
        try:
            page = await _get_page()
            if selector:
                await page.locator(selector).scroll_into_view_if_needed(timeout=5000)
                return f"✅ Scrolled to element: {selector}"
            scroll_map = {"up": -pixels, "down": pixels, "top": -99999, "bottom": 99999}
            delta = scroll_map.get(direction, pixels)
            await page.evaluate(f"window.scrollBy(0, {delta})")
            pos = await page.evaluate("window.scrollY")
            return f"✅ Scrolled {direction} by {abs(delta)}px. Current Y position: {int(pos)}"
        except Exception as e:
            return f"❌ Scroll failed: {e}"


class BrowserKeyPressTool(Tool):
    name = "browser_keypress"
    description = "Press a keyboard key or key combination (e.g. Enter, Tab, Ctrl+A, Escape)."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key to press: Enter, Tab, Escape, Backspace, ArrowDown, Control+a, etc."},
                    "selector": {"type": "string", "description": "Focus this element first (optional)"},
                },
                "required": ["key"],
            },
        }

    async def execute(self, key: str, selector: str = None) -> str:
        try:
            page = await _get_page()
            if selector:
                await page.press(selector, key, timeout=5000)
            else:
                await page.keyboard.press(key)
            return f"✅ Pressed key: {key}"
        except Exception as e:
            return f"❌ Keypress failed: {e}"


class BrowserJSTool(Tool):
    name = "browser_js"
    description = "Execute JavaScript code in the browser page and return the result."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "JavaScript code to execute. Use 'return' for a value."},
                },
                "required": ["code"],
            },
        }

    async def execute(self, code: str) -> str:
        try:
            page = await _get_page()
            # Wrap in an async IIFE if it doesn't start with return
            if not code.strip().startswith("return") and not code.strip().startswith("("):
                expr = code
            else:
                expr = code
            result = await page.evaluate(expr)
            return f"✅ JS result: {str(result)[:3000]}"
        except Exception as e:
            return f"❌ JS error: {e}"


class BrowserWaitTool(Tool):
    name = "browser_wait"
    description = "Wait for an element to appear, for navigation, or for a fixed duration."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector to wait for"},
                    "state": {"type": "string", "enum": ["visible", "hidden", "attached", "detached"],
                              "description": "State to wait for (default: visible)"},
                    "timeout_ms": {"type": "integer", "description": "Max wait time in ms (default: 10000)"},
                    "seconds": {"type": "number", "description": "Just wait this many seconds (ignores selector)"},
                },
            },
        }

    async def execute(self, selector: str = None, state: str = "visible", timeout_ms: int = 10000, seconds: float = None) -> str:
        try:
            if seconds:
                await asyncio.sleep(seconds)
                return f"✅ Waited {seconds}s"
            page = await _get_page()
            if selector:
                await page.wait_for_selector(selector, state=state, timeout=timeout_ms)
                return f"✅ Element '{selector}' is now {state}"
            return "Nothing to wait for — provide selector or seconds."
        except Exception as e:
            return f"❌ Wait failed: {e}"


class BrowserSelectTool(Tool):
    name = "browser_select"
    description = "Select an option from a dropdown (select element)."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the <select> element"},
                    "value": {"type": "string", "description": "Option value to select"},
                    "label": {"type": "string", "description": "Option visible text to select (alternative to value)"},
                },
                "required": ["selector"],
            },
        }

    async def execute(self, selector: str, value: str = None, label: str = None) -> str:
        try:
            page = await _get_page()
            if label:
                await page.select_option(selector, label=label, timeout=5000)
                return f"✅ Selected option with label '{label}' in '{selector}'"
            elif value:
                await page.select_option(selector, value=value, timeout=5000)
                return f"✅ Selected option with value '{value}' in '{selector}'"
            return "❌ Provide either value or label to select."
        except Exception as e:
            return f"❌ Select failed: {e}"


class BrowserTabsTool(Tool):
    name = "browser_tabs"
    description = "Manage browser tabs: list, switch, close, or open new tabs."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "switch", "close", "close_all"],
                               "description": "Tab action to perform"},
                    "tab_id": {"type": "string", "description": "Tab ID for switch/close actions"},
                },
                "required": ["action"],
            },
        }

    async def execute(self, action: str, tab_id: str = None) -> str:
        try:
            s = _session()
            if action == "list":
                tabs = s.list_tabs()
                if not tabs:
                    return "No tabs open."
                lines = ["**Open Tabs:**"]
                for t in tabs:
                    marker = "→ " if t["active"] else "  "
                    lines.append(f"{marker}**{t['tab_id']}**: {t['url']}")
                return "\n".join(lines)
            elif action == "switch" and tab_id:
                if tab_id in s._pages:
                    s._active_tab = tab_id
                    return f"✅ Switched to tab: {tab_id} ({s._pages[tab_id].url})"
                return f"❌ Tab not found: {tab_id}"
            elif action == "close":
                await s.close_tab(tab_id)
                return f"✅ Tab closed. Active: {s._active_tab or 'none'}"
            elif action == "close_all":
                await s.close_all()
                return "✅ All tabs and browser closed."
            return f"❌ Unknown action: {action}"
        except Exception as e:
            return f"❌ Tab action failed: {e}"


class BrowserHoverTool(Tool):
    name = "browser_hover"
    description = "Hover the mouse over an element to trigger hover effects or tooltips."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the element to hover"},
                },
                "required": ["selector"],
            },
        }

    async def execute(self, selector: str) -> str:
        try:
            page = await _get_page()
            await page.hover(selector, timeout=5000)
            return f"✅ Hovering over '{selector}'"
        except Exception as e:
            return f"❌ Hover failed: {e}"


class SearchWebTool(Tool):
    name = "search_web"
    description = "Search the web using DuckDuckGo and return results."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Maximum results (default: 5)"},
                },
                "required": ["query"],
            },
        }

    async def execute(self, query: str, max_results: int = 5) -> str:
        try:
            import re
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0"},
                    timeout=10,
                )
                text = resp.text
                results = []
                links = re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', text)
                snippets = re.findall(r'<a class="result__snippet".*?>(.*?)</a>', text, re.DOTALL)

                for i, (url, title) in enumerate(links[:max_results]):
                    title_clean = re.sub(r'<.*?>', '', title).strip()
                    snippet = re.sub(r'<.*?>', '', snippets[i]).strip() if i < len(snippets) else ""
                    results.append(f"{i+1}. **{title_clean}**\n   {url}\n   {snippet}")

                return "\n\n".join(results) if results else "No results found."
        except Exception as e:
            return f"Search error: {str(e)}"


# ── Export all browser tools ────────────────────────────────

def get_browser_tools() -> list[Tool]:
    return [
        BrowserOpenTool(),
        BrowserScreenshotTool(),
        BrowserClickTool(),
        BrowserTypeTool(),
        BrowserGetTextTool(),
        BrowserScrollTool(),
        BrowserKeyPressTool(),
        BrowserJSTool(),
        BrowserWaitTool(),
        BrowserSelectTool(),
        BrowserTabsTool(),
        BrowserHoverTool(),
        SearchWebTool(),
    ]
