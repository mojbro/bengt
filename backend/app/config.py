from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    # JSON object mapping display names → model IDs, e.g.
    #   LLM_MODELS={"fast":"gpt-4o-mini","standard":"gpt-5.4-mini","smart":"gpt-5"}
    # If unset/empty, we run in single-model mode using llm_model.
    llm_models: str = ""
    # Key into llm_models (or ignored in single-model mode). If empty in
    # multi-model mode, falls back to the first entry.
    llm_default_model: str = ""
    daily_budget_usd: float = 5.0
    auth_password: str = ""
    vault_path: str = "/app/vault"
    data_path: str = "/app/data"
    # The assistant's name. Appears in the system prompt so the agent
    # knows how to refer to itself. Replaceable via env.
    assistant_name: str = "Bengt"
    # IANA timezone name used when the prompt tells the agent what "today"
    # means to the user. Override via TIMEZONE env (e.g. Europe/Stockholm).
    timezone: str = "UTC"
    inbox_scan_interval_minutes: int = 15
    # Tests flip this off so APScheduler doesn't fire jobs during pytest.
    scheduler_autostart: bool = True
    # After a fresh conversation's first assistant turn, auto-generate a
    # short title via a tiny extra LLM call. Disabled in tests.
    auto_title: bool = True


settings = Settings()
