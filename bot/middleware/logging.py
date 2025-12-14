"""
Logging middleware for aiogram.

Logs all incoming updates for debugging and monitoring.
Captures user info, message content, and processing time.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Update

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware that logs all incoming updates.

    Logs:
    - User ID and username
    - Message text (truncated for long messages)
    - Processing time

    Usage:
        dp.update.middleware(LoggingMiddleware())
    """

    MAX_TEXT_LENGTH = 100  # Truncate long messages in logs

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        """
        Process update and log information.

        Args:
            handler: Next handler in chain
            event: Incoming update
            data: Handler data

        Returns:
            Handler result
        """
        start_time = time.monotonic()

        # Extract user info
        user_info = self._get_user_info(event)
        message_info = self._get_message_info(event)

        logger.info(f"Incoming: {user_info} | {message_info}")

        try:
            result = await handler(event, data)

            # Calculate processing time
            elapsed = (time.monotonic() - start_time) * 1000  # ms
            logger.debug(f"Processed in {elapsed:.2f}ms")

            return result

        except Exception as e:
            elapsed = (time.monotonic() - start_time) * 1000
            logger.error(f"Error after {elapsed:.2f}ms: {type(e).__name__}: {e}")
            raise

    def _get_user_info(self, event: Update) -> str:
        """Extract user info from update."""
        user = None

        if event.message:
            user = event.message.from_user
        elif event.callback_query:
            user = event.callback_query.from_user

        if user:
            username = f"@{user.username}" if user.username else "no_username"
            return f"user={user.id} ({username})"

        return "user=unknown"

    def _get_message_info(self, event: Update) -> str:
        """Extract message info from update."""
        if event.message and event.message.text:
            text = event.message.text
            if len(text) > self.MAX_TEXT_LENGTH:
                text = text[: self.MAX_TEXT_LENGTH] + "..."
            return f'text="{text}"'

        if event.callback_query:
            return f"callback={event.callback_query.data}"

        return "type=other"
