"""
NexAlfa Web Tools
Search, scrape, and extract structured data from the internet.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus, urlparse

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.web")


class SearchWebTool(Tool):
    name = "search_web"
    description = "Search the internet using DuckDuckGo. Returns titles, URLs, and snippets. Use this to find information, research topics, or find URLs to scrape."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "num_results": {"type": "integer", "description": "Number of results (default 8)"},
                },
                "required": ["query"],
            },
        }

    async def execute(self, query: str, num_results: int = 8) -> str:
        results = []
        # Try duckduckgo-search
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", r.get("link", "")),
                        "snippet": r.get("body", r.get("snippet", "")),
                    })
            if results:
                return self._format(query, results, "DuckDuckGo")
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")

        # Fallback: scrape DDG HTML
        if not results:
            try:
                import httpx
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.+?)</a>', resp.text)
                snippets = re.findall(r'class="result__snippet"[^>]*>(.+?)</(?:a|td|div|span)', resp.text, re.DOTALL)
                for i, (u, title) in enumerate(links[:num_results]):
                    title_clean = re.sub(r'<[^>]+>', '', title).strip()
                    snippet_clean = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                    results.append({"title": title_clean, "url": u, "snippet": snippet_clean})
                if results:
                    return self._format(query, results, "DuckDuckGo (HTML)")
            except Exception as e:
                logger.warning(f"DDG HTML fallback failed: {e}")

        return f"No search results found for: {query}"

    @staticmethod
    def _format(query: str, results: list[dict], engine: str) -> str:
        parts = [f"🔍 **Search results for:** \"{query}\" (via {engine})\n"]
        for i, r in enumerate(results, 1):
            parts.append(f"**{i}. [{r['title']}]({r['url']})**")
            if r.get("snippet"):
                parts.append(f"   {r['snippet']}")
            parts.append("")
        return "\n".join(parts)


class WebScrapeTool(Tool):
    name = "web_scrape"
    description = "Fetch a URL and extract clean readable text. Best for articles, docs, and static pages. For JS-rendered pages, use browser tools instead."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to scrape"},
                    "max_chars": {"type": "integer", "description": "Max characters to return (default 30000)"},
                },
                "required": ["url"],
            },
        }

    async def execute(self, url: str, max_chars: int = 30000) -> str:
        try:
            # Try trafilatura first
            try:
                import trafilatura
                import httpx
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                text = trafilatura.extract(resp.text, include_links=True, include_tables=True, include_comments=False)
                if text and len(text.strip()) > 100:
                    if len(text) > max_chars:
                        text = text[:max_chars] + f"\n\n... (truncated)"
                    return f"🌐 **{url}**\n\n{text}"
            except ImportError:
                pass

            # Fallback: BeautifulSoup
            try:
                import httpx
                from bs4 import BeautifulSoup
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                text = "\n".join(lines)
                if len(text) > max_chars:
                    text = text[:max_chars] + f"\n\n... (truncated)"
                title = soup.title.string if soup.title else urlparse(url).hostname
                return f"🌐 **{title}** ({url})\n\n{text}"
            except ImportError:
                pass

            # Last fallback
            import httpx
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            return f"🌐 **{url}**\n\n{text}"
        except Exception as e:
            return f"ERROR: Failed to scrape {url}: {type(e).__name__}: {e}"


class WebExtractTool(Tool):
    name = "web_extract"
    description = "Extract structured data from a web page: links, emails, images, meta tags, or tables."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The page URL to extract from"},
                    "extract": {
                        "type": "string",
                        "description": "What to extract: 'links', 'emails', 'images', 'meta', 'tables', or 'all'",
                        "enum": ["links", "emails", "images", "meta", "tables", "all"],
                    },
                },
                "required": ["url"],
            },
        }

    async def execute(self, url: str, extract: str = "all") -> str:
        try:
            import httpx
            from bs4 import BeautifulSoup
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            soup = BeautifulSoup(resp.text, "html.parser")
            parts = [f"🔗 **Extracted data from:** {url}\n"]

            if extract in ("links", "all"):
                links = []
                for a in soup.find_all("a", href=True)[:50]:
                    href = a["href"]
                    text = a.get_text(strip=True)[:80]
                    if href.startswith(("http", "//")):
                        links.append(f"- [{text or href}]({href})")
                if links:
                    parts.append(f"### Links ({len(links)})")
                    parts.append("\n".join(links[:30]))

            if extract in ("emails", "all"):
                emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text)))
                if emails:
                    parts.append(f"\n### Emails ({len(emails)})")
                    parts.append("\n".join(f"- {e}" for e in emails[:20]))

            if extract in ("images", "all"):
                imgs = []
                for img in soup.find_all("img", src=True)[:20]:
                    src = img["src"]
                    alt = img.get("alt", "")[:50]
                    imgs.append(f"- {alt or 'image'}: {src}")
                if imgs:
                    parts.append(f"\n### Images ({len(imgs)})")
                    parts.append("\n".join(imgs))

            if extract in ("meta", "all"):
                metas = []
                title = soup.title.string if soup.title else "N/A"
                metas.append(f"- **Title**: {title}")
                for meta in soup.find_all("meta"):
                    name = meta.get("name") or meta.get("property", "")
                    content = meta.get("content", "")
                    if name and content:
                        metas.append(f"- **{name}**: {content[:100]}")
                if metas:
                    parts.append(f"\n### Meta Tags ({len(metas)})")
                    parts.append("\n".join(metas[:20]))

            if extract in ("tables", "all"):
                tables = soup.find_all("table")
                for i, table in enumerate(tables[:5]):
                    rows = []
                    for tr in table.find_all("tr"):
                        cells = [td.get_text(strip=True)[:50] for td in tr.find_all(["td", "th"])]
                        rows.append(" | ".join(cells))
                    if rows:
                        parts.append(f"\n### Table {i+1}")
                        parts.append("\n".join(rows[:20]))

            return "\n".join(parts)
        except ImportError:
            return "ERROR: Install beautifulsoup4: pip install beautifulsoup4"
        except Exception as e:
            return f"ERROR: Failed to extract from {url}: {type(e).__name__}: {e}"


def get_web_tools() -> list[Tool]:
    return [SearchWebTool(), WebScrapeTool(), WebExtractTool()]
