"""Tool layer tests: factories fail fast, strategies behave, no network."""

from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.tools.errors import ToolConfigurationError
from app.tools.llm_providers import create_llm_client
from app.tools.search_providers import DuckDuckGoSearchTool, NullSearchTool, create_search_tool
from app.utils.retry import RetryExhaustedError


class _FakeDDGS:
    """Stands in for ddgs.DDGS — context manager with a .text() method."""

    def __init__(self, rows: list[dict[str, str]]) -> None:
        self._rows = rows

    def __enter__(self) -> _FakeDDGS:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def text(self, query: str, max_results: int) -> list[dict[str, str]]:
        return self._rows[:max_results]


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"max_retries": 0, "retry_base_delay_seconds": 0.01}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


# --- Factories fail fast on misconfiguration ---


def test_llm_factory_requires_anthropic_key() -> None:
    with pytest.raises(ToolConfigurationError):
        create_llm_client(_settings(llm_provider="anthropic", anthropic_api_key=""))


def test_llm_factory_requires_groq_key() -> None:
    with pytest.raises(ToolConfigurationError):
        create_llm_client(_settings(llm_provider="groq", groq_api_key=""))


def test_llm_factory_requires_openrouter_key() -> None:
    with pytest.raises(ToolConfigurationError):
        create_llm_client(_settings(llm_provider="openrouter", openrouter_api_key=""))


def test_search_factory_requires_tavily_key() -> None:
    with pytest.raises(ToolConfigurationError):
        create_search_tool(_settings(search_provider="tavily", tavily_api_key=""))


def test_search_factory_none_returns_null_tool() -> None:
    tool = create_search_tool(_settings(search_provider="none"))
    assert isinstance(tool, NullSearchTool)


# --- Strategy behavior ---


@pytest.mark.asyncio
async def test_null_search_returns_empty() -> None:
    assert await NullSearchTool().search("anything", max_results=5) == []


@pytest.mark.asyncio
async def test_duckduckgo_maps_rows_and_assigns_rank_relevance() -> None:
    rows = [
        {"title": "NHS - Tremor", "body": "Causes of tremor.", "href": "https://nhs.uk/tremor"},
        {"title": "Mayo Clinic", "body": "Tremor overview.", "href": "https://mayo.example/tremor"},
        {"title": "No URL row", "body": "should be skipped", "href": ""},
    ]
    tool = DuckDuckGoSearchTool(_settings(), ddgs_factory=lambda: _FakeDDGS(rows))
    results = await tool.search("tremor causes", max_results=5)

    assert [r.url for r in results] == ["https://nhs.uk/tremor", "https://mayo.example/tremor"]
    assert results[0].relevance == pytest.approx(0.9)
    assert results[1].relevance == pytest.approx(0.8)


def test_rank_relevance_has_floor() -> None:
    assert DuckDuckGoSearchTool.rank_relevance(0) == pytest.approx(0.9)
    assert DuckDuckGoSearchTool.rank_relevance(50) == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_duckduckgo_failure_propagates_for_node_to_contain() -> None:
    class _Exploding:
        def __enter__(self) -> _Exploding:
            raise ConnectionError("ddg down")

        def __exit__(self, *args: object) -> bool:
            return False

    tool = DuckDuckGoSearchTool(_settings(), ddgs_factory=_Exploding)
    with pytest.raises(RetryExhaustedError):
        await tool.search("q", max_results=3)
