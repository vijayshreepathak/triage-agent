"""MCP search adapter tests — payload parsing and factory gating, no network."""

from __future__ import annotations

import json

import pytest

from app.config.settings import Settings
from app.tools.errors import ToolConfigurationError
from app.tools.mcp_search import parse_mcp_content, parse_mcp_rows
from app.tools.search_providers import create_search_tool


def test_factory_requires_mcp_url() -> None:
    with pytest.raises(ToolConfigurationError):
        create_search_tool(Settings(search_provider="mcp", mcp_server_url=""))


def test_factory_builds_mcp_tool_when_configured() -> None:
    tool = create_search_tool(
        Settings(
            search_provider="mcp",
            mcp_server_url="http://localhost:9000/mcp",
            mcp_search_tool_name="web_search",
        )
    )
    assert tool.provider_name == "mcp:web_search"


def test_rows_map_flexible_field_names() -> None:
    rows = [
        {"title": "NHS", "url": "https://nhs.uk/a", "summary": "text", "score": 0.8},
        {"title": "Mayo", "href": "https://mayo.example/b", "content": "text2", "relevance": "0.6"},
        {"title": "no url row", "summary": "dropped"},
        {"link": "https://c.example", "body": "text3", "score": "not-a-number"},
    ]
    results = parse_mcp_rows(rows)
    assert [r.url for r in results] == ["https://nhs.uk/a", "https://mayo.example/b", "https://c.example"]
    assert results[0].relevance == pytest.approx(0.8)
    assert results[1].relevance == pytest.approx(0.6)
    assert results[2].relevance == pytest.approx(0.7)  # unparseable score -> default


def test_content_parsing_handles_results_key_and_bare_lists() -> None:
    wrapped = json.dumps({"results": [{"title": "A", "url": "https://a.example", "summary": "s"}]})
    bare = json.dumps([{"title": "B", "url": "https://b.example", "summary": "s"}])
    not_json = "plain prose, no data"
    results = parse_mcp_content([wrapped, bare, not_json])
    assert {r.url for r in results} == {"https://a.example", "https://b.example"}


def test_scores_are_clamped_to_unit_interval() -> None:
    results = parse_mcp_rows([{"url": "https://x.example", "score": 7.5}])
    assert results[0].relevance == 1.0
