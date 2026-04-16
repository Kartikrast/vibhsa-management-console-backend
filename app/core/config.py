from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Vibhsa Management Console"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_URL: str = "http://localhost:8000"  # Frontend URL for invite links

    # Database
    DATABASE_URL: str

    # Security
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Google
    GOOGLE_CLIENT_ID: str

    # Email
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    EMAIL_FROM_NAME: str = "Vibhsa Management Console"

    WALMART_ENV: str = "sandbox"
    WALMART_SANDBOX_URL: str
    WALMART_PRODUCTION_URL: str

    AMAZON_ENV: str = "sandbox"
    AMAZON_SANDBOX_US_URL: str
    AMAZON_PRODUCTION_US_URL: str
    AMAZON_LWA_ENDPOINT: str = "https://api.amazon.com/auth/o2/token"

    ORDER_SYNC_INTERVAL_MINUTES: int = 15

    # Walmart Webhooks
    WALMART_WEBHOOK_BASE_URL: str = ""  # Public base URL Walmart POSTs to
    WALMART_WEBHOOK_USERNAME: str = ""  # BASIC_AUTH username for incoming webhooks
    WALMART_WEBHOOK_PASSWORD: str = ""  # BASIC_AUTH password for incoming webhooks
    WALMART_WEBHOOK_AUTH_HEADER: str = "Authorization"  # Header name for auth

    BRAVE_BROWSER_PATH: str = ""


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
