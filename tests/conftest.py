"""
Pytest configuration and fixtures.

Provides reusable test fixtures for:
- Mock services
- Sample token data
- Test orchestrator
"""

import pytest

from bot.core.models import (
    RugpullFlags,
    SocialInfo,
    TokenData,
)
from bot.services.explain.mock_llm import MockLLMProvider
from bot.services.explain.service import ExplainService
from bot.services.orchestrator import AnalyzerOrchestrator
from bot.services.risk.service import RiskService, RiskThresholds
from bot.services.token_data.aggregator import TokenDataAggregator
from bot.services.token_data.mock_provider import MockTokenDataProvider

# =============================================================================
# Token Data Fixtures
# =============================================================================


@pytest.fixture
def high_risk_token() -> TokenData:
    """Token with HIGH risk indicators."""
    return TokenData(
        address="HighRiskToken11111111111111111111111111111",
        name="ScamCoin",
        symbol="SCAM",
        age_days=2,
        liquidity_usd=5_000,
        holders=50,
        top10_holders_percent=85,
        tx_count_24h=20,
        rugpull_flags=RugpullFlags(
            new_contract=True,
            low_liquidity=True,
            centralized_holders=True,
        ),
        social=SocialInfo(),
    )


@pytest.fixture
def medium_risk_token() -> TokenData:
    """Token with MEDIUM risk indicators."""
    return TokenData(
        address="MediumRiskToken111111111111111111111111111",
        name="MidCoin",
        symbol="MID",
        age_days=20,
        liquidity_usd=50_000,
        holders=500,
        top10_holders_percent=45,
        tx_count_24h=200,
        rugpull_flags=RugpullFlags(),
        social=SocialInfo(
            twitter_exists=True,
            telegram_exists=True,
        ),
    )


@pytest.fixture
def low_risk_token() -> TokenData:
    """Token with LOW risk indicators."""
    return TokenData(
        address="LowRiskToken1111111111111111111111111111111",
        name="SafeCoin",
        symbol="SAFE",
        age_days=180,
        liquidity_usd=500_000,
        holders=10_000,
        top10_holders_percent=25,
        tx_count_24h=5_000,
        rugpull_flags=RugpullFlags(),
        social=SocialInfo(
            twitter_exists=True,
            telegram_exists=True,
            website_valid=True,
        ),
    )


# =============================================================================
# Service Fixtures
# =============================================================================


@pytest.fixture
def risk_service() -> RiskService:
    """RiskService with default thresholds."""
    return RiskService()


@pytest.fixture
def custom_risk_service() -> RiskService:
    """RiskService with custom thresholds for testing edge cases."""
    return RiskService(
        thresholds=RiskThresholds(
            liquidity_high_risk=10_000,
            liquidity_low_risk=50_000,
            age_high_risk=5,
            age_low_risk=20,
            top10_high_risk=50.0,
        )
    )


@pytest.fixture
def mock_token_provider() -> MockTokenDataProvider:
    """Mock token data provider."""
    return MockTokenDataProvider()


@pytest.fixture
def mock_llm_provider() -> MockLLMProvider:
    """Mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def token_aggregator(mock_token_provider: MockTokenDataProvider) -> TokenDataAggregator:
    """Token data aggregator with mock provider."""
    return TokenDataAggregator(mock_token_provider)


@pytest.fixture
def explain_service(mock_llm_provider: MockLLMProvider) -> ExplainService:
    """Explain service with mock LLM."""
    return ExplainService(mock_llm_provider)


@pytest.fixture
def orchestrator(
    token_aggregator: TokenDataAggregator,
    risk_service: RiskService,
    explain_service: ExplainService,
) -> AnalyzerOrchestrator:
    """Fully configured orchestrator with mock services."""
    return AnalyzerOrchestrator(
        aggregator=token_aggregator,
        risk_service=risk_service,
        explain_service=explain_service,
    )


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def valid_solana_address() -> str:
    """Valid Solana token address (USDC)."""
    return "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


@pytest.fixture
def another_valid_address() -> str:
    """Another valid Solana address (wrapped SOL)."""
    return "So11111111111111111111111111111111111111112"


@pytest.fixture
def invalid_addresses() -> list[str]:
    """List of invalid addresses for testing."""
    return [
        "",  # Empty
        "   ",  # Whitespace
        "abc",  # Too short
        "0x742d35Cc6634C0532925a3b844Bc9e7595f5bEb2",  # Ethereum
        "So11111111111111111111111111111111111111112!",  # Invalid char
        "O0Il" * 11,  # Invalid base58 chars
    ]
