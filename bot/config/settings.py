"""
Application settings loaded from environment variables.

Uses pydantic-settings for automatic loading from .env file.
All settings have sensible defaults for development mode.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration.

    All values are loaded from environment variables.
    Copy .env.example to .env and fill in your values.

    Attributes:
        telegram_bot_token: Bot token from @BotFather (required)
        environment: Runtime environment (development/production)
        use_mock_services: Use mock providers instead of real APIs
        log_level: Logging verbosity
        api_timeout_seconds: Timeout for external API calls
        helius_api_key: Helius API key (optional in mock mode)
        birdeye_api_key: Birdeye API key (optional in mock mode)
        claude_api_key: Claude API key (optional in mock mode)
        openrouter_api_key: OpenRouter API key for LLM (optional in mock mode)
        llm_model: LLM model to use via OpenRouter
    """

    # Required
    telegram_bot_token: str

    # Environment
    environment: Literal["development", "production"] = "development"
    use_mock_services: bool = True

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Timeouts
    api_timeout_seconds: int = 10

    # API Keys (optional when use_mock_services=True)
    helius_api_key: str = ""
    birdeye_api_key: str = ""
    claude_api_key: str = ""

    # OpenRouter LLM settings
    openrouter_api_key: str = ""
    llm_model: str = "anthropic/claude-3.5-sonnet"

    # Pydantic settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Case-insensitive env var names
        case_sensitive=False,
        # Don't fail if .env doesn't exist
        env_ignore_empty=True,
    )

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Uses lru_cache to avoid re-reading .env file on every call.
    Settings are loaded once and reused throughout the application.

    Returns:
        Settings instance with all configuration values.
    """
    return Settings()
