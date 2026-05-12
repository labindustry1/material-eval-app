"""Tavily web-search adapter, restored from legacy.

Pulls top-N web search results for a query. Used as an optional supplement
to the internal-document evidence retrieval pipeline — when the user
wants industry-wide context beyond the local knowledge base.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass(frozen=True)
class WebSearchHit:
    title: str
    url: str
    content_snippet: str
    score: float = 0.0


@dataclass(frozen=True)
class WebSearchResult:
    ok: bool
    answer: str = ""
    hits: tuple[WebSearchHit, ...] = field(default_factory=tuple)
    error: str = ""


def search_web(query: str, *, max_results: int = 5, depth: str = "advanced") -> WebSearchResult:
    """Search the public web via Tavily for industry-wide context.

    Reads TAVILY_API_KEY from env. Returns WebSearchResult; never raises.
    """
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return WebSearchResult(ok=False, error="未配置 TAVILY_API_KEY，全网检索不可用。")
    if not query.strip():
        return WebSearchResult(ok=False, error="检索 query 为空。")

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": depth,
                "include_answer": True,
                "max_results": max_results,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
    except Exception as exc:
        return WebSearchResult(ok=False, error=f"Tavily 调用失败：{exc}")

    hits = tuple(
        WebSearchHit(
            title=str(item.get("title", "")),
            url=str(item.get("url", "")),
            content_snippet=str(item.get("content", ""))[:600],
            score=float(item.get("score", 0.0) or 0.0),
        )
        for item in payload.get("results", [])
    )
    return WebSearchResult(
        ok=True,
        answer=str(payload.get("answer", "") or ""),
        hits=hits,
    )
