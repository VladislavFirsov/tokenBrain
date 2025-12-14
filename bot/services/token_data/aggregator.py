"""
Token data aggregator service.

Responsible for fetching token data from various providers
and normalizing it into a unified TokenData structure.

This service:
1. Delegates data fetching to TokenDataProvider
2. Can combine data from multiple sources (future)
3. Handles caching (future)
"""

import logging

from bot.core.models import TokenData
from bot.core.protocols import TokenDataProvider
from bot.core.exceptions import DataFetchError

logger = logging.getLogger(__name__)


class TokenDataAggregator:
    """
    Aggregates token data from one or more providers.

    Currently uses a single provider, but designed to support
    multiple providers in the future (e.g., Helius + Birdeye).

    The aggregator's responsibility is to:
    1. Call the provider(s) to fetch data
    2. Handle errors gracefully
    3. Log operations for debugging

    It does NOT:
    - Calculate risk (that's RiskService's job)
    - Generate explanations (that's ExplainService's job)
    """

    def __init__(self, provider: TokenDataProvider):
        """
        Initialize aggregator with a data provider.

        Args:
            provider: TokenDataProvider implementation (mock or real)
        """
        self._provider = provider

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
            token_data = await self._provider.get_token_data(address)
            logger.debug(
                f"Token data received: {token_data.symbol}, "
                f"liquidity=${token_data.liquidity_usd:,.2f}"
            )
            return token_data

        except DataFetchError:
            # Re-raise our own exceptions
            raise

        except Exception as e:
            # Wrap unexpected errors
            logger.exception(f"Unexpected error fetching token data: {e}")
            raise DataFetchError(
                message="Не удалось получить данные о токене.",
                technical_message=f"Provider error: {type(e).__name__}: {e}",
            )
