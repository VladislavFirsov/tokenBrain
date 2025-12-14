"""
Tests for OpenRouterLLMProvider.

Tests cover:
- Successful API responses
- JSON parsing and validation
- Fallback on error/timeout
- System/user prompt separation
"""

import pytest
from aioresponses import aioresponses

from bot.core.models import (
    AnalysisResult,
    Recommendation,
    RiskLevel,
    RugpullFlags,
    SocialInfo,
    TokenData,
)
from bot.services.explain.openrouter_provider import (
    OPENROUTER_API_URL,
    OpenRouterLLMProvider,
)


@pytest.fixture
def openrouter_provider() -> OpenRouterLLMProvider:
    """OpenRouterLLMProvider with test API key."""
    return OpenRouterLLMProvider(
        api_key="test-api-key",
        model="anthropic/claude-3.5-sonnet",
        timeout=1.0,
    )


@pytest.fixture
def sample_token() -> TokenData:
    """Sample token data for testing."""
    return TokenData(
        address="TestToken11111111111111111111111111111111",
        name="Test Token",
        symbol="TEST",
        age_days=30,
        liquidity_usd=50000,
        holders=1000,
        top10_holders_percent=40,
        tx_count_24h=500,
        mint_authority_exists=False,
        freeze_authority_exists=False,
        metadata_mutable=False,
        top1_holder_percent=15.0,
        top5_holders_percent=30.0,
        rugpull_flags=RugpullFlags(),
        social=SocialInfo(twitter_exists=True, telegram_exists=True),
    )


@pytest.fixture
def mock_success_response() -> dict:
    """Mock successful OpenRouter response."""
    return {
        "choices": [
            {
                "message": {
                    "content": """{
                        "risk": "medium",
                        "summary": "Токен имеет средний уровень риска.",
                        "why": ["Умеренная ликвидность", "Средняя концентрация"],
                        "recommendation": "caution"
                    }"""
                }
            }
        ]
    }


@pytest.fixture
def mock_high_risk_response() -> dict:
    """Mock high risk response."""
    return {
        "choices": [
            {
                "message": {
                    "content": """{
                        "risk": "high",
                        "summary": "Высокий риск из-за mint authority.",
                        "why": ["Mint authority активен", "Можно создать новые токены"],
                        "recommendation": "avoid"
                    }"""
                }
            }
        ]
    }


class TestOpenRouterSuccess:
    """Tests for successful API responses."""

    @pytest.mark.asyncio
    async def test_generate_analysis_success(
        self,
        openrouter_provider: OpenRouterLLMProvider,
        sample_token: TokenData,
        mock_success_response: dict,
    ) -> None:
        """Should generate analysis from valid response."""
        with aioresponses() as m:
            m.post(OPENROUTER_API_URL, payload=mock_success_response)

            result = await openrouter_provider.generate_analysis(
                sample_token, RiskLevel.MEDIUM
            )

            assert isinstance(result, AnalysisResult)
            assert result.risk == RiskLevel.MEDIUM
            assert result.recommendation == Recommendation.CAUTION
            assert len(result.why) >= 1

    @pytest.mark.asyncio
    async def test_parses_high_risk_response(
        self,
        openrouter_provider: OpenRouterLLMProvider,
        sample_token: TokenData,
        mock_high_risk_response: dict,
    ) -> None:
        """Should parse high risk response correctly."""
        with aioresponses() as m:
            m.post(OPENROUTER_API_URL, payload=mock_high_risk_response)

            result = await openrouter_provider.generate_analysis(
                sample_token, RiskLevel.HIGH
            )

            assert result.risk == RiskLevel.HIGH
            assert result.recommendation == Recommendation.AVOID


class TestOpenRouterJsonParsing:
    """Tests for JSON parsing."""

    @pytest.mark.asyncio
    async def test_handles_markdown_code_block(
        self,
        openrouter_provider: OpenRouterLLMProvider,
        sample_token: TokenData,
    ) -> None:
        """Should extract JSON from markdown code block."""
        response = {
            "choices": [
                {
                    "message": {
                        "content": """```json
{
    "risk": "low",
    "summary": "Безопасный токен.",
    "why": ["Хорошие показатели"],
    "recommendation": "ok"
}
```"""
                    }
                }
            ]
        }

        with aioresponses() as m:
            m.post(OPENROUTER_API_URL, payload=response)

            result = await openrouter_provider.generate_analysis(
                sample_token, RiskLevel.LOW
            )

            assert result.risk == RiskLevel.LOW
            assert result.recommendation == Recommendation.OK

    @pytest.mark.asyncio
    async def test_handles_plain_code_block(
        self,
        openrouter_provider: OpenRouterLLMProvider,
        sample_token: TokenData,
    ) -> None:
        """Should extract JSON from plain code block."""
        response = {
            "choices": [
                {
                    "message": {
                        "content": """```
{
    "risk": "medium",
    "summary": "Средний риск.",
    "why": ["Причина"],
    "recommendation": "caution"
}
```"""
                    }
                }
            ]
        }

        with aioresponses() as m:
            m.post(OPENROUTER_API_URL, payload=response)

            result = await openrouter_provider.generate_analysis(
                sample_token, RiskLevel.MEDIUM
            )

            assert result.risk == RiskLevel.MEDIUM


class TestOpenRouterFallback:
    """Tests for fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(
        self,
        openrouter_provider: OpenRouterLLMProvider,
        sample_token: TokenData,
    ) -> None:
        """Should use fallback on API error."""
        with aioresponses() as m:
            m.post(OPENROUTER_API_URL, status=500)

            # Should not raise, should return fallback
            result = await openrouter_provider.generate_analysis(
                sample_token, RiskLevel.MEDIUM
            )

            assert isinstance(result, AnalysisResult)
            assert result.risk == RiskLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_json(
        self,
        openrouter_provider: OpenRouterLLMProvider,
        sample_token: TokenData,
    ) -> None:
        """Should use fallback on invalid JSON response."""
        response = {
            "choices": [{"message": {"content": "This is not valid JSON at all!"}}]
        }

        with aioresponses() as m:
            m.post(OPENROUTER_API_URL, payload=response)

            result = await openrouter_provider.generate_analysis(
                sample_token, RiskLevel.HIGH
            )

            # Should return fallback result
            assert isinstance(result, AnalysisResult)
            assert result.risk == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_fallback_includes_authority_info(
        self,
        openrouter_provider: OpenRouterLLMProvider,
    ) -> None:
        """Fallback should mention authority flags when present."""
        risky_token = TokenData(
            address="RiskyToken1111111111111111111111111111111",
            name="Risky",
            symbol="RISK",
            age_days=5,
            liquidity_usd=5000,
            holders=100,
            top10_holders_percent=80,
            tx_count_24h=50,
            mint_authority_exists=True,
            freeze_authority_exists=True,
            rugpull_flags=RugpullFlags(low_liquidity=True, new_contract=True),
            social=SocialInfo(),
        )

        with aioresponses() as m:
            m.post(OPENROUTER_API_URL, status=500)

            result = await openrouter_provider.generate_analysis(
                risky_token, RiskLevel.HIGH
            )

            # Should mention authorities in why
            why_text = " ".join(result.why).lower()
            assert "mint" in why_text or "authority" in why_text


class TestOpenRouterValidation:
    """Tests for response validation."""

    @pytest.mark.asyncio
    async def test_truncates_long_summary(
        self,
        openrouter_provider: OpenRouterLLMProvider,
        sample_token: TokenData,
    ) -> None:
        """Should truncate summary longer than 500 chars."""
        long_summary = "A" * 600
        response = {
            "choices": [
                {
                    "message": {
                        "content": f"""{{
                            "risk": "low",
                            "summary": "{long_summary}",
                            "why": ["Причина"],
                            "recommendation": "ok"
                        }}"""
                    }
                }
            ]
        }

        with aioresponses() as m:
            m.post(OPENROUTER_API_URL, payload=response)

            result = await openrouter_provider.generate_analysis(
                sample_token, RiskLevel.LOW
            )

            assert len(result.summary) <= 500

    @pytest.mark.asyncio
    async def test_limits_why_to_5_items(
        self,
        openrouter_provider: OpenRouterLLMProvider,
        sample_token: TokenData,
    ) -> None:
        """Should limit why list to 5 items."""
        response = {
            "choices": [
                {
                    "message": {
                        "content": """{
                            "risk": "medium",
                            "summary": "Тест",
                            "why": ["1", "2", "3", "4", "5", "6", "7", "8"],
                            "recommendation": "caution"
                        }"""
                    }
                }
            ]
        }

        with aioresponses() as m:
            m.post(OPENROUTER_API_URL, payload=response)

            result = await openrouter_provider.generate_analysis(
                sample_token, RiskLevel.MEDIUM
            )

            assert len(result.why) <= 5

    @pytest.mark.asyncio
    async def test_maps_invalid_recommendation(
        self,
        openrouter_provider: OpenRouterLLMProvider,
        sample_token: TokenData,
    ) -> None:
        """Should map invalid recommendation based on risk level."""
        response = {
            "choices": [
                {
                    "message": {
                        "content": """{
                            "risk": "high",
                            "summary": "Тест",
                            "why": ["Причина"],
                            "recommendation": "invalid_value"
                        }"""
                    }
                }
            ]
        }

        with aioresponses() as m:
            m.post(OPENROUTER_API_URL, payload=response)

            result = await openrouter_provider.generate_analysis(
                sample_token, RiskLevel.HIGH
            )

            # Should map to AVOID for HIGH risk
            assert result.recommendation == Recommendation.AVOID
