"""
Token data aggregator service.

Responsible for fetching token data from various providers
and normalizing it into a unified TokenData structure.

This service:
1. Delegates data fetching to TokenDataProvider
2. Can combine data from multiple sources (future)
3. Handles caching (future)
"""

import asyncio
import logging

from bot.core.exceptions import DataFetchError
from bot.core.models import TokenData
from bot.core.protocols import TokenDataProvider

logger = logging.getLogger(__name__)

# Default timeout for provider calls (seconds)
DEFAULT_TIMEOUT = 10.0


class TokenDataAggregator:
    """
    Aggregates token data from one or more providers.

    Currently uses a single provider, but designed to support
    multiple providers in the future (e.g., Helius + Birdeye).

    The aggregator's responsibility is to:
    1. Call the provider(s) to fetch data
    2. Handle errors gracefully
    3. Log operations for debugging
    4. Enforce timeout on provider calls

    It does NOT:
    - Calculate risk (that's RiskService's job)
    - Generate explanations (that's ExplainService's job)
    """

    def __init__(self, provider: TokenDataProvider, timeout: float = DEFAULT_TIMEOUT):
        """
        Initialize aggregator with a data provider.

        Args:
            provider: TokenDataProvider implementation (mock or real)
            timeout: Timeout for provider calls in seconds
        """
        self._provider = provider
        self._timeout = timeout

    async def get_token_data(self, address: str) -> TokenData:
        """
        Fetch and aggregate token data.

        Args:
            address: Validated Solana token address

        Returns:
            TokenData with all available information

        Raises:
            DataFetchError: If fetching fails
        """
        logger.info(f"Fetching token data for: {address[:8]}...")

        try:
            # Enforce timeout on provider call
            token_data = await asyncio.wait_for(
                self._provider.get_token_data(address),
                timeout=self._timeout,
            )
            logger.debug(
                f"Token data received: {token_data.symbol}, "
                f"liquidity=${token_data.liquidity_usd:,.2f}"
            )
            return token_data

        except TimeoutError:
            logger.error(f"Provider timeout after {self._timeout}s for {address[:8]}")
            raise DataFetchError(
                message="Запрос занял слишком много времени. Попробуйте позже.",
                technical_message=f"Provider timeout after {self._timeout}s",
            ) from None

        except DataFetchError:
            # Re-raise our own exceptions
            raise

        except Exception as e:
            # Wrap unexpected errors
            logger.exception(f"Unexpected error fetching token data: {e}")
            raise DataFetchError(
                message="Не удалось получить данные о токене.",
                technical_message=f"Provider error: {type(e).__name__}: {e}",
            ) from e
