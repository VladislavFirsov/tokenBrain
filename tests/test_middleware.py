"""
Tests for middleware components.

Tests error handling and logging middleware behavior.
Uses mock objects to simulate aiogram updates.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.core.exceptions import (
    TokenBrainError,
    ValidationError,
    DataFetchError,
    LLMError,
)
from bot.middleware.error_handler import ErrorHandlerMiddleware
from bot.middleware.logging import LoggingMiddleware


class MockUpdate:
    """Mock aiogram Update object."""

    def __init__(self, text: str = "test message", user_id: int = 12345):
        self.message = MagicMock()
        self.message.text = text
        self.message.from_user = MagicMock()
        self.message.from_user.id = user_id
        self.message.from_user.username = "testuser"
        self.message.answer = AsyncMock()
        self.callback_query = None


class TestErrorHandlerMiddleware:
    """Tests for ErrorHandlerMiddleware."""

    @pytest.fixture
    def middleware(self) -> ErrorHandlerMiddleware:
        return ErrorHandlerMiddleware()

    @pytest.fixture
    def mock_update(self) -> MockUpdate:
        return MockUpdate()

    @pytest.mark.asyncio
    async def test_passes_through_on_success(
        self,
        middleware: ErrorHandlerMiddleware,
        mock_update: MockUpdate,
    ) -> None:
        """Should pass through when handler succeeds."""
        handler = AsyncMock(return_value="success")

        result = await middleware(handler, mock_update, {})

        assert result == "success"
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_catches_validation_error(
        self,
        middleware: ErrorHandlerMiddleware,
        mock_update: MockUpdate,
    ) -> None:
        """Should catch ValidationError and send message."""
        handler = AsyncMock(side_effect=ValidationError("Invalid address"))

        result = await middleware(handler, mock_update, {})

        assert result is None
        mock_update.message.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_catches_data_fetch_error(
        self,
        middleware: ErrorHandlerMiddleware,
        mock_update: MockUpdate,
    ) -> None:
        """Should catch DataFetchError and send message."""
        handler = AsyncMock(side_effect=DataFetchError())

        result = await middleware(handler, mock_update, {})

        assert result is None
        mock_update.message.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_catches_llm_error(
        self,
        middleware: ErrorHandlerMiddleware,
        mock_update: MockUpdate,
    ) -> None:
        """Should catch LLMError and send message."""
        handler = AsyncMock(side_effect=LLMError())

        result = await middleware(handler, mock_update, {})

        assert result is None
        mock_update.message.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_catches_unknown_error(
        self,
        middleware: ErrorHandlerMiddleware,
        mock_update: MockUpdate,
    ) -> None:
        """Should catch unknown errors and send generic message."""
        handler = AsyncMock(side_effect=RuntimeError("Unknown"))

        result = await middleware(handler, mock_update, {})

        assert result is None
        mock_update.message.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_error_message(
        self,
        middleware: ErrorHandlerMiddleware,
        mock_update: MockUpdate,
    ) -> None:
        """Should use error's message for user."""
        custom_message = "Custom error message"
        handler = AsyncMock(side_effect=ValidationError(custom_message))

        await middleware(handler, mock_update, {})

        # Check that the message contains our custom text
        call_args = mock_update.message.answer.call_args
        assert custom_message in call_args[0][0]


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    @pytest.fixture
    def middleware(self) -> LoggingMiddleware:
        return LoggingMiddleware()

    @pytest.fixture
    def mock_update(self) -> MockUpdate:
        return MockUpdate(text="test token address")

    @pytest.mark.asyncio
    async def test_passes_through_result(
        self,
        middleware: LoggingMiddleware,
        mock_update: MockUpdate,
    ) -> None:
        """Should pass through handler result."""
        handler = AsyncMock(return_value="result")

        result = await middleware(handler, mock_update, {})

        assert result == "result"

    @pytest.mark.asyncio
    async def test_logs_incoming_message(
        self,
        middleware: LoggingMiddleware,
        mock_update: MockUpdate,
    ) -> None:
        """Should log incoming message."""
        handler = AsyncMock(return_value=None)

        with patch("bot.middleware.logging.logger") as mock_logger:
            await middleware(handler, mock_update, {})

            # Check info was called for incoming
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_logs_error_on_exception(
        self,
        middleware: LoggingMiddleware,
        mock_update: MockUpdate,
    ) -> None:
        """Should log error when handler raises."""
        handler = AsyncMock(side_effect=RuntimeError("test error"))

        with patch("bot.middleware.logging.logger") as mock_logger:
            with pytest.raises(RuntimeError):
                await middleware(handler, mock_update, {})

            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_truncates_long_messages(
        self,
        middleware: LoggingMiddleware,
    ) -> None:
        """Should truncate very long messages in logs."""
        long_text = "a" * 200
        mock_update = MockUpdate(text=long_text)
        handler = AsyncMock(return_value=None)

        # Should not raise
        await middleware(handler, mock_update, {})

        # Check truncation happened
        info = middleware._get_message_info(mock_update)
        assert len(info) < len(long_text) + 20  # Some overhead for formatting
