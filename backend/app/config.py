from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    daily_budget_usd: float = 5.0
    auth_password: str = ""
    vault_path: str = "/app/vault"
    inbox_scan_interval_minutes: int = 15


settings = Settings()
