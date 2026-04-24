import json

from app.config import Settings
from app.llm.openai_provider import OpenAIProvider
from app.llm.types import LLMProvider


class LLMConfigError(Exception):
    """Raised when LLM settings are invalid or incomplete."""


def _single_provider(
    settings: Settings, model_id: str
) -> LLMProvider:
    provider_name = settings.llm_provider.lower()
    if provider_name == "openai":
        if not settings.llm_api_key:
            raise LLMConfigError("LLM_API_KEY is required for the openai provider")
        if not model_id:
            raise LLMConfigError("model id is required")
        return OpenAIProvider(api_key=settings.llm_api_key, model=model_id)
    raise LLMConfigError(
        f"Unknown LLM provider: {settings.llm_provider!r}. "
        "Supported providers: openai."
    )


def _parse_models_map(raw: str) -> dict[str, str]:
    """Parse the LLM_MODELS env value.

    Accepts JSON mapping display-name → model-id, e.g.
        {"fast": "gpt-4o-mini", "smart": "gpt-5"}
    Empty / unset returns an empty dict (signals single-model mode).
    """
    raw = raw.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMConfigError(
            f"LLM_MODELS is not valid JSON: {exc.msg}"
        ) from exc
    if not isinstance(parsed, dict):
        raise LLMConfigError(
            "LLM_MODELS must be a JSON object mapping names → model IDs"
        )
    cleaned: dict[str, str] = {}
    for k, v in parsed.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise LLMConfigError(
                "LLM_MODELS keys and values must both be strings"
            )
        key = k.strip()
        val = v.strip()
        if not key or not val:
            raise LLMConfigError("LLM_MODELS entries can't be blank")
        cleaned[key] = val
    if not cleaned:
        raise LLMConfigError("LLM_MODELS is empty")
    return cleaned


def build_providers(settings: Settings) -> tuple[dict[str, LLMProvider], str]:
    """Build one provider per configured model and return them with the
    default key.

    Single-model mode: if LLM_MODELS is empty, returns a dict with one
    entry keyed by LLM_MODEL (the literal model id).
    """
    models_map = _parse_models_map(settings.llm_models)
    if not models_map:
        # Single-model fallback — preserves pre-multi-model behaviour.
        if not settings.llm_model:
            raise LLMConfigError("LLM_MODEL is required in single-model mode")
        models_map = {settings.llm_model: settings.llm_model}

    default = settings.llm_default_model.strip() or next(iter(models_map.keys()))
    if default not in models_map:
        raise LLMConfigError(
            f"LLM_DEFAULT_MODEL={default!r} isn't one of the configured "
            f"LLM_MODELS keys: {sorted(models_map)}"
        )

    providers: dict[str, LLMProvider] = {}
    for name, model_id in models_map.items():
        providers[name] = _single_provider(settings, model_id)
    return providers, default


def build_provider(settings: Settings) -> LLMProvider:
    """Backward-compat shim — returns the default provider.

    Callers that want to support multi-model switching should use
    build_providers() and pick per-request.
    """
    providers, default = build_providers(settings)
    return providers[default]
