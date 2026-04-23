"""Two tools that give the agent the rest of the internet:

- `web_search(query, limit?)` — DuckDuckGo results. No API key, free.
- `fetch_url(url)` — reader-mode-ish content extraction via trafilatura.
  Strips boilerplate (nav, ads, footers), returns plain text, truncated
  to ~8000 chars so a single fetch can't blow up the context window.

Both tools handle network failures by returning the error as the tool
result — the agent sees it and can recover, rather than crashing the
turn.
"""

import asyncio
from typing import Any

import trafilatura
from ddgs import DDGS

from app.agent.tools import Tool, ToolRegistry

_SEARCH_TIMEOUT_S = 10
_MAX_FETCH_CHARS = 8000


def _sync_search(query: str, limit: int) -> list[dict[str, Any]]:
    with DDGS(timeout=_SEARCH_TIMEOUT_S) as ddgs:
        return list(ddgs.text(query, max_results=limit))


async def _web_search(args: dict[str, Any]) -> str:
    query = str(args["query"]).strip()
    if not query:
        return "web_search requires a non-empty query."
    limit = int(args.get("limit", 5))
    limit = max(1, min(limit, 10))

    try:
        results = await asyncio.to_thread(_sync_search, query, limit)
    except Exception as exc:
        return f"web_search failed: {exc}"

    if not results:
        return "(no results)"

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title") or "(no title)"
        url = r.get("href") or ""
        snippet = (r.get("body") or "")[:200]
        lines.append(f"{i}. {title}\n   {url}\n   {snippet}")
    return "\n\n".join(lines)


def _sync_fetch(url: str) -> str | None:
    return trafilatura.fetch_url(url)


async def _fetch_url(args: dict[str, Any]) -> str:
    url = str(args["url"]).strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return f"fetch_url requires an absolute http(s) URL, got: {url!r}"

    try:
        downloaded = await asyncio.to_thread(_sync_fetch, url)
    except Exception as exc:
        return f"fetch_url network error: {exc}"

    if not downloaded:
        return f"fetch_url could not retrieve {url}"

    text = trafilatura.extract(downloaded, include_comments=False) or ""
    if not text:
        return f"fetch_url: no readable content extracted from {url}"

    if len(text) > _MAX_FETCH_CHARS:
        text = (
            text[:_MAX_FETCH_CHARS]
            + f"\n\n[... truncated, {len(text)} chars total]"
        )
    return text


def register_web_tools(registry: ToolRegistry) -> None:
    registry.register(
        Tool(
            name="web_search",
            description=(
                "Search the public web via DuckDuckGo. Returns up to 10 "
                "results, each with a title, URL, and short snippet. Use "
                "this for current events, facts outside the user's vault, "
                "or to find URLs the user might want to read."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in natural language.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Max number of results (default 5).",
                    },
                },
                "required": ["query"],
            },
            fn=_web_search,
        )
    )
    registry.register(
        Tool(
            name="fetch_url",
            description=(
                "Fetch and extract the main readable text of a web page. "
                "Strips navigation, ads, and boilerplate. Use this to read "
                "articles the user links to, or URLs you found via "
                "web_search. Output is truncated at ~8000 chars; for very "
                "long pages, ask a follow-up question with a more specific "
                "URL or target section."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Absolute http:// or https:// URL.",
                    },
                },
                "required": ["url"],
            },
            fn=_fetch_url,
        )
    )
