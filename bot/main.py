"""
TokenBrain Bot entry point.

Initializes all components and starts the bot.
This is the main module that ties everything together.

Run with: python -m bot.main
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_settings
from bot.handlers import setup_routers
from bot.services.factory import ServiceFactory


def setup_logging(level: str) -> None:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    # Reduce noise from external libraries
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def validate_production_config(settings) -> None:
    """
    Validate that required API keys are present in production mode.

    Raises:
        RuntimeError: If required env vars are missing.
    """
    if settings.use_mock_services:
        return  # Mock mode doesn't need real API keys

    missing = []
    if not settings.helius_api_key:
        missing.append("HELIUS_API_KEY")
    if not settings.openrouter_api_key:
        missing.append("OPENROUTER_API_KEY")

    if missing:
        raise RuntimeError(
            f"Missing required env vars for production mode: {', '.join(missing)}. "
            f"Set USE_MOCK_SERVICES=true for development without API keys."
        )


async def main() -> None:
    """
    Main application entry point.

    Initializes:
    1. Configuration from environment
    2. Logging
    3. Services via factory
    4. Bot and dispatcher
    5. Handlers and middleware

    Then starts polling for updates.
    """
    # Load configuration
    settings = get_settings()

    # Setup logging first (so validation errors are logged)
    setup_logging(settings.log_level)

    # Validate production config
    validate_production_config(settings)
    logger = logging.getLogger(__name__)

    logger.info("=" * 50)
    logger.info("TokenBrain Bot starting...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Mock mode: {settings.use_mock_services}")
    logger.info("=" * 50)

    # Create services
    factory = ServiceFactory(settings)
    orchestrator = factory.create_orchestrator()

    # Initialize bot
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    # Initialize dispatcher
    dp = Dispatcher()

    # Setup handlers and middleware
    setup_routers(dp, orchestrator)

    # Graceful shutdown handler
    async def on_shutdown() -> None:
        logger.info("Shutting down...")
        await bot.session.close()

    dp.shutdown.register(on_shutdown)

    # Start polling
    logger.info("Bot is ready. Starting polling...")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    except Exception as e:
        logger.exception(f"Bot stopped with error: {e}")
        raise
    finally:
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
