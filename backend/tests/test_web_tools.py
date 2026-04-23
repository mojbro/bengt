"""Unit tests for web_search / fetch_url.

Mocks the external packages so tests stay offline. There's a pytest.mark.
integration test at the bottom that hits the real network — skipped by
default.
"""

from typing import Any

import pytest

from app.agent import ToolRegistry
from app.agent.web_tools import register_web_tools


def _registry() -> ToolRegistry:
    reg = ToolRegistry()
    register_web_tools(reg)
    return reg


def test_both_tools_registered():
    reg = _registry()
    assert set(reg.names()) == {"web_search", "fetch_url"}


async def test_web_search_formats_results(monkeypatch):
    class FakeDDGS:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def text(self, query: str, max_results: int | None = None):
            return [
                {
                    "title": "Volvo",
                    "href": "https://volvo.com",
                    "body": "Swedish car manufacturer.",
                },
                {
                    "title": "Volvo Cars",
                    "href": "https://www.volvocars.com",
                    "body": "Official Volvo Cars global website.",
                },
            ]

    monkeypatch.setattr("app.agent.web_tools.DDGS", FakeDDGS)

    reg = _registry()
    out = await reg.invoke("web_search", {"query": "volvo"})
    assert "Volvo" in out
    assert "https://volvo.com" in out
    assert "Swedish car manufacturer" in out


async def test_web_search_empty_results(monkeypatch):
    class FakeDDGS:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def text(self, *a, **kw):
            return []

    monkeypatch.setattr("app.agent.web_tools.DDGS", FakeDDGS)

    reg = _registry()
    out = await reg.invoke("web_search", {"query": "asdfghjkl"})
    assert out == "(no results)"


async def test_web_search_handles_exceptions(monkeypatch):
    class FakeDDGS:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            raise RuntimeError("rate limited")

        def __exit__(self, *a):
            pass

    monkeypatch.setattr("app.agent.web_tools.DDGS", FakeDDGS)

    reg = _registry()
    out = await reg.invoke("web_search", {"query": "hi"})
    assert "failed" in out
    assert "rate limited" in out


async def test_web_search_requires_query():
    reg = _registry()
    out = await reg.invoke("web_search", {"query": "   "})
    assert "non-empty" in out


async def test_fetch_url_rejects_non_http():
    reg = _registry()
    out = await reg.invoke("fetch_url", {"url": "file:///etc/passwd"})
    assert "absolute http(s)" in out


async def test_fetch_url_returns_extracted_text(monkeypatch):
    import app.agent.web_tools as web_tools

    monkeypatch.setattr(
        web_tools.trafilatura,
        "fetch_url",
        lambda url, **kw: "<html><body>content</body></html>",
    )
    monkeypatch.setattr(
        web_tools.trafilatura,
        "extract",
        lambda html, **kw: "Main article content.",
    )

    reg = _registry()
    out = await reg.invoke("fetch_url", {"url": "https://example.com"})
    assert out == "Main article content."


async def test_fetch_url_truncates_long_content(monkeypatch):
    import app.agent.web_tools as web_tools

    long_text = "x" * 20_000
    monkeypatch.setattr(
        web_tools.trafilatura, "fetch_url", lambda url, **kw: "<html/>"
    )
    monkeypatch.setattr(
        web_tools.trafilatura, "extract", lambda html, **kw: long_text
    )

    reg = _registry()
    out = await reg.invoke("fetch_url", {"url": "https://example.com"})
    assert len(out) < 20_000
    assert "truncated" in out
    assert "20000 chars total" in out


async def test_fetch_url_handles_network_error(monkeypatch):
    import app.agent.web_tools as web_tools

    def raise_network(*a, **kw):
        raise OSError("dns failure")

    monkeypatch.setattr(web_tools.trafilatura, "fetch_url", raise_network)

    reg = _registry()
    out = await reg.invoke("fetch_url", {"url": "https://example.com"})
    assert "network error" in out
    assert "dns failure" in out


async def test_fetch_url_empty_download(monkeypatch):
    import app.agent.web_tools as web_tools

    monkeypatch.setattr(
        web_tools.trafilatura, "fetch_url", lambda url, **kw: None
    )

    reg = _registry()
    out = await reg.invoke("fetch_url", {"url": "https://example.com"})
    assert "could not retrieve" in out


# -------------------- Optional real-network integration


@pytest.mark.integration
async def test_fetch_url_real_network():
    """Hits example.com for real. Skipped by default."""
    reg = _registry()
    out = await reg.invoke("fetch_url", {"url": "https://example.com"})
    # Should produce some text (or at least not an error).
    assert not out.startswith("fetch_url ")
