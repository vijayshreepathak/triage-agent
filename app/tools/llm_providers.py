"""LLM provider adapters + factory (Factory pattern).

One thin adapter wraps ANY langchain chat model into our ``LLMClient``
Protocol — Groq and OpenRouter differ only in how the chat model is
constructed, so the factory owns that difference and nothing else does.

Retry policy lives HERE (transport level, exponential backoff, from
settings) with the provider SDK's internal retries disabled — exactly one
retry ladder, fully logged, owned by us.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.config.settings import Settings
from app.models.enums import LLMProvider
from app.services.metrics import MetricsRegistry
from app.tools.errors import ToolConfigurationError
from app.tools.interfaces import LLMClient, LLMResult
from app.utils.logging import get_logger
from app.utils.retry import retry_async

logger = get_logger(__name__)


class ChatModelLLMClient:
    """Adapter: langchain BaseChatModel -> LLMClient Protocol."""

    def __init__(
        self,
        chat_model: BaseChatModel,
        *,
        model_name: str,
        settings: Settings,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._chat = chat_model
        self._model_name = model_name
        self._settings = settings
        self._metrics = metrics

    async def complete(self, *, system: str, user: str) -> LLMResult:
        """Run one completion with transport-level retry + usage tracking."""
        messages = [SystemMessage(content=system), HumanMessage(content=user)]

        async def _invoke() -> object:
            return await self._chat.ainvoke(messages)

        message, retries = await retry_async(
            _invoke,
            operation_name=f"llm:{self._model_name}",
            max_retries=self._settings.max_retries,
            base_delay_seconds=self._settings.retry_base_delay_seconds,
        )
        usage: dict[str, int] = getattr(message, "usage_metadata", None) or {}
        result = LLMResult(
            content=str(getattr(message, "content", "")),
            model=self._model_name,
            prompt_tokens=int(usage.get("input_tokens", 0)),
            completion_tokens=int(usage.get("output_tokens", 0)),
        )
        if retries:
            logger.info(
                "llm call succeeded after retries", extra={"model": self._model_name, "retries": retries}
            )
        if self._metrics is not None:
            self._metrics.record_llm_usage(result)
        return result


def create_llm_client(settings: Settings, metrics: MetricsRegistry | None = None) -> LLMClient:
    """Factory: build the configured provider's client. Fails fast on bad config.

    temperature comes from settings (0.0) for determinism; the SDK's own
    retries are disabled (max_retries=0) so our retry ladder is the only one.
    """
    if settings.llm_provider == LLMProvider.ANTHROPIC:
        if not settings.anthropic_api_key:
            raise ToolConfigurationError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        from langchain_anthropic import ChatAnthropic  # local import: only pay for what you use

        chat = ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
        return ChatModelLLMClient(
            chat, model_name=settings.anthropic_model, settings=settings, metrics=metrics
        )

    if settings.llm_provider == LLMProvider.GROQ:
        if not settings.groq_api_key:
            raise ToolConfigurationError("LLM_PROVIDER=groq but GROQ_API_KEY is not set")
        from langchain_groq import ChatGroq  # local import: only pay for what you use

        chat = ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
        return ChatModelLLMClient(chat, model_name=settings.groq_model, settings=settings, metrics=metrics)

    if settings.llm_provider == LLMProvider.OPENROUTER:
        if not settings.openrouter_api_key:
            raise ToolConfigurationError("LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set")
        from langchain_openai import ChatOpenAI

        chat = ChatOpenAI(
            model=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
        return ChatModelLLMClient(
            chat, model_name=settings.openrouter_model, settings=settings, metrics=metrics
        )

    raise ToolConfigurationError(f"Unknown LLM provider: {settings.llm_provider}")
