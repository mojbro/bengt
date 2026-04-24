import json
from dataclasses import dataclass

from app.config import Settings
from app.llm.openai_provider import OpenAIProvider
from app.llm.types import LLMProvider


class LLMConfigError(Exception):
    """Raised when LLM settings are invalid or incomplete."""


_VALID_EFFORTS = {"low", "medium", "high"}


@dataclass(frozen=True)
class ModelSpec:
    """Configured model variant.

    `model` is the underlying provider model id (e.g. "gpt-5.4"). `effort`
    applies to reasoning-capable models (gpt-5, o-series) and maps to
    OpenAI's `reasoning_effort` — None leaves it off the wire.
    """

    model: str
    effort: str | None = None


def _single_provider(settings: Settings, spec: ModelSpec) -> LLMProvider:
    provider_name = settings.llm_provider.lower()
    if provider_name == "openai":
        if not settings.llm_api_key:
            raise LLMConfigError("LLM_API_KEY is required for the openai provider")
        if not spec.model:
            raise LLMConfigError("model id is required")
        return OpenAIProvider(
            api_key=settings.llm_api_key,
            model=spec.model,
            reasoning_effort=spec.effort,
        )
    raise LLMConfigError(
        f"Unknown LLM provider: {settings.llm_provider!r}. "
        "Supported providers: openai."
    )


def _parse_models_map(raw: str) -> dict[str, ModelSpec]:
    """Parse the LLM_MODELS env value.

    Accepts two forms per entry:

      {"fast": "gpt-4o-mini"}                          # legacy string form
      {"Smart": {"model": "gpt-5.4", "effort": "high"}}  # explicit effort

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
            "LLM_MODELS must be a JSON object mapping names → model specs"
        )
    cleaned: dict[str, ModelSpec] = {}
    for raw_key, value in parsed.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise LLMConfigError("LLM_MODELS keys must be non-empty strings")
        key = raw_key.strip()

        if isinstance(value, str):
            model_id = value.strip()
            if not model_id:
                raise LLMConfigError(f"LLM_MODELS[{key!r}] can't be blank")
            cleaned[key] = ModelSpec(model=model_id)
            continue

        if isinstance(value, dict):
            raw_model = value.get("model")
            if not isinstance(raw_model, str) or not raw_model.strip():
                raise LLMConfigError(
                    f"LLM_MODELS[{key!r}] needs a non-empty 'model' field"
                )
            model_id = raw_model.strip()
            raw_effort = value.get("effort")
            effort: str | None
            if raw_effort is None:
                effort = None
            elif isinstance(raw_effort, str) and raw_effort.strip().lower() in _VALID_EFFORTS:
                effort = raw_effort.strip().lower()
            else:
                raise LLMConfigError(
                    f"LLM_MODELS[{key!r}].effort must be one of "
                    f"{sorted(_VALID_EFFORTS)} or omitted; got {raw_effort!r}"
                )
            cleaned[key] = ModelSpec(model=model_id, effort=effort)
            continue

        raise LLMConfigError(
            f"LLM_MODELS[{key!r}] must be a string or object; got {type(value).__name__}"
        )

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
        if not settings.llm_model:
            raise LLMConfigError("LLM_MODEL is required in single-model mode")
        models_map = {settings.llm_model: ModelSpec(model=settings.llm_model)}

    default = settings.llm_default_model.strip() or next(iter(models_map.keys()))
    if default not in models_map:
        raise LLMConfigError(
            f"LLM_DEFAULT_MODEL={default!r} isn't one of the configured "
            f"LLM_MODELS keys: {sorted(models_map)}"
        )

    providers: dict[str, LLMProvider] = {}
    for name, spec in models_map.items():
        providers[name] = _single_provider(settings, spec)
    return providers, default


def build_provider(settings: Settings) -> LLMProvider:
    """Backward-compat shim — returns the default provider.

    Callers that want to support multi-model switching should use
    build_providers() and pick per-request.
    """
    providers, default = build_providers(settings)
    return providers[default]
