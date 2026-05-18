from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl, Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "prod"
    DATABASE_URL: str

    ADMIN_API_KEY: str = Field(default="change_me")
    BOT_API_KEY: str = Field(default="change_me_bot")

    TOKENPAY_API_BASE: AnyUrl = "http://tokenpay:5001"
    TOKENPAY_API_TOKEN: str

    PUBLIC_BASE_URL: AnyUrl = "http://token_shop_backend:8000"

    RETENTION_DAYS: int = 60

settings = Settings()
