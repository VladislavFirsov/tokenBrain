"""
Protocol definitions (interfaces) for external services.

Using typing.Protocol instead of ABC because:
1. Supports duck typing (no inheritance required)
2. Lighter weight
3. Better for dependency injection
4. Easier to mock in tests

Each protocol defines the contract that implementations must follow.
"""

from typing import Protocol, runtime_checkable

from bot.core.models import AnalysisResult, RiskResult, TokenData


@runtime_checkable
class TokenDataProvider(Protocol):
    """
    Protocol for token data providers.

    Implementations fetch token data from external sources like:
    - Helius (on-chain data)
    - Birdeye (market data)
    - pump.fun (meme coin data)

    For development, MockTokenDataProvider returns fake data.
    """

    async def get_token_data(self, address: str) -> TokenData:
        """
        Fetch token data by address.

        Args:
            address: Solana token address (validated)

        Returns:
            TokenData with all available information

        Raises:
            DataFetchError: If fetching fails
        """
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """
    Protocol for LLM providers.

    Implementations generate human-readable analysis from token data.
    Currently supports:
    - Claude (Anthropic) - production
    - MockLLMProvider - development

    The provider must return AnalysisResult in the exact format
    expected by the frontend.

    Anti-Hallucination Contract:
    - LLM receives RiskResult with pre-calculated factors[]
    - LLM must use ONLY these factors, not add new ones
    - LLM must not change the risk level
    """

    async def generate_analysis(
        self,
        token_data: TokenData,
        risk_result: RiskResult,
    ) -> AnalysisResult:
        """
        Generate analysis explanation from token data.

        The LLM should:
        1. NOT calculate risk (already provided in risk_result)
        2. Use ONLY factors[] from risk_result
        3. Explain in simple terms
        4. Return strictly formatted JSON

        Args:
            token_data: Normalized token information
            risk_result: Pre-calculated risk with factors and completeness

        Returns:
            AnalysisResult with summary, reasons, and recommendation

        Raises:
            LLMError: If generation fails
        """
        ...
