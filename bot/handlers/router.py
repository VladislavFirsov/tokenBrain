"""
Router setup and configuration.

Registers all handlers and middleware with the dispatcher.
Order matters - command handlers are registered before catch-all.
"""

from aiogram import Dispatcher

from bot.handlers import common_handler, token_handler
from bot.middleware import ErrorHandlerMiddleware, LoggingMiddleware
from bot.services.orchestrator import AnalyzerOrchestrator


def setup_routers(
    dp: Dispatcher,
    orchestrator: AnalyzerOrchestrator,
) -> None:
    """
    Configure dispatcher with all routers and middleware.

    Sets up:
    1. Global middleware (error handling, logging)
    2. Command handlers (/start, /help)
    3. Token analysis handler (catch-all)

    Order is important:
    - Middleware is processed for all updates
    - Command handlers are checked first
    - Token handler catches remaining messages

    Args:
        dp: Aiogram dispatcher
        orchestrator: Analyzer service for injection into handlers
    """
    # Register middleware (order: first registered = outermost)
    # Error handler should be outermost to catch all errors
    dp.update.middleware(ErrorHandlerMiddleware())
    dp.update.middleware(LoggingMiddleware())

    # Store orchestrator for dependency injection
    # This makes it available as a handler argument
    dp["orchestrator"] = orchestrator

    # Register routers (order matters!)
    # Commands should be matched before catch-all token handler
    dp.include_router(common_handler.router)
    dp.include_router(token_handler.router)
