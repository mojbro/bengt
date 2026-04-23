from app.config import Settings
from app.llm.openai_provider import OpenAIProvider
from app.llm.types import LLMProvider


class LLMConfigError(Exception):
    """Raised when LLM settings are invalid or incomplete."""


def build_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        if not settings.llm_api_key:
            raise LLMConfigError("LLM_API_KEY is required for the openai provider")
        if not settings.llm_model:
            raise LLMConfigError("LLM_MODEL is required for the openai provider")
        return OpenAIProvider(
            api_key=settings.llm_api_key, model=settings.llm_model
        )
    raise LLMConfigError(
        f"Unknown LLM provider: {settings.llm_provider!r}. "
        "Supported providers: openai."
    )
