"""
Error handling middleware for aiogram.

Catches all exceptions and returns user-friendly error messages.
Logs technical details for debugging while hiding them from users.

Exception handling priority:
1. ValidationError → show validation message
2. DataFetchError → show "try later" message
3. LLMError → show "service unavailable" message
4. Unknown errors → show generic error message
"""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update, Message

from bot.core.exceptions import (
    TokenBrainError,
    ValidationError,
    DataFetchError,
    LLMError,
)
from bot.templates.messages import (
    ERROR_GENERIC,
    ERROR_SERVICE_UNAVAILABLE,
    ERROR_TRY_LATER,
)

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Global error handling middleware.

    Catches exceptions from handlers and:
    1. Logs technical details for debugging
    2. Sends user-friendly message to the user
    3. Prevents exception from crashing the bot

    All TokenBrainError subclasses have predefined user messages.
    Unknown errors get a generic "something went wrong" message.

    Usage:
        dp.update.middleware(ErrorHandlerMiddleware())
    """

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        """
        Process update with error handling.

        Args:
            handler: Next handler in chain
            event: Incoming update
            data: Handler data

        Returns:
            Handler result or None if error occurred
        """
        try:
            return await handler(event, data)

        except ValidationError as e:
            await self._handle_error(event, e, log_level="warning")

        except DataFetchError as e:
            await self._handle_error(
                event, e,
                fallback_message=ERROR_TRY_LATER,
                log_level="error",
            )

        except LLMError as e:
            await self._handle_error(
                event, e,
                fallback_message=ERROR_SERVICE_UNAVAILABLE,
                log_level="error",
            )

        except TokenBrainError as e:
            # Catch-all for our custom exceptions
            await self._handle_error(event, e, log_level="error")

        except Exception as e:
            # Unknown errors - log full traceback
            logger.exception(f"Unexpected error: {type(e).__name__}: {e}")
            await self._send_error_message(event, ERROR_GENERIC)

        return None

    async def _handle_error(
        self,
        event: Update,
        error: TokenBrainError,
        fallback_message: str | None = None,
        log_level: str = "error",
    ) -> None:
        """
        Handle a known error type.

        Args:
            event: The update that caused the error
            error: The exception that was raised
            fallback_message: Message to use if error.message is empty
            log_level: Logging level (warning, error)
        """
        # Log technical details
        log_func = getattr(logger, log_level)
        log_func(f"{type(error).__name__}: {error.technical_message}")

        # Send user-friendly message
        message = error.message or fallback_message or ERROR_GENERIC
        await self._send_error_message(event, message)

    async def _send_error_message(
        self,
        event: Update,
        message: str,
    ) -> None:
        """
        Send error message to user.

        Extracts the message object from update and sends the error.

        Args:
            event: The update to respond to
            message: Error message to send
        """
        # Get the message object to reply to
        msg: Message | None = None

        if event.message:
            msg = event.message
        elif event.callback_query and event.callback_query.message:
            msg = event.callback_query.message

        if msg:
            try:
                await msg.answer(message)
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")
