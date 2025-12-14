"""
Custom exceptions for TokenBrain application.

Exception hierarchy:
    TokenBrainError (base)
    ├── ValidationError - Invalid input data
    ├── DataFetchError - Failed to fetch token data from external APIs
    └── LLMError - Failed to get response from LLM

Each exception carries a user-friendly message that can be shown to users,
and optionally a technical message for logging.
"""


class TokenBrainError(Exception):
    """
    Base exception for all TokenBrain errors.

    Attributes:
        message: User-friendly error message (can be shown to users)
        technical_message: Detailed message for logs (optional)
    """

    def __init__(
        self,
        message: str = "Произошла ошибка. Попробуйте позже.",
        technical_message: str | None = None,
    ):
        self.message = message
        self.technical_message = technical_message or message
        super().__init__(self.technical_message)

    def __str__(self) -> str:
        return self.technical_message


class ValidationError(TokenBrainError):
    """
    Raised when input validation fails.

    Examples:
        - Invalid Solana address format
        - Empty input
        - Wrong chain address
    """

    def __init__(
        self,
        message: str = "Некорректный адрес токена.",
        technical_message: str | None = None,
    ):
        super().__init__(message, technical_message)


class DataFetchError(TokenBrainError):
    """
    Raised when fetching token data from external APIs fails.

    Examples:
        - Helius API timeout
        - Birdeye API error
        - Token not found
        - Network issues
    """

    def __init__(
        self,
        message: str = "Не удалось получить данные о токене. Попробуйте позже.",
        technical_message: str | None = None,
    ):
        super().__init__(message, technical_message)


class LLMError(TokenBrainError):
    """
    Raised when LLM (Claude) request fails.

    Examples:
        - Claude API timeout
        - Rate limiting
        - Invalid response format
        - Service unavailable
    """

    def __init__(
        self,
        message: str = "Сервис анализа временно недоступен. Попробуйте позже.",
        technical_message: str | None = None,
    ):
        super().__init__(message, technical_message)
