"""
Tests for AnalyzerOrchestrator.

Integration tests that verify the full analysis flow:
- Data fetching
- Risk calculation
- Explanation generation
- Result structure
"""

import pytest

from bot.core.models import RiskLevel, Recommendation, AnalysisResult
from bot.services.orchestrator import AnalyzerOrchestrator


class TestOrchestratorAnalysis:
    """Integration tests for analyze method."""

    @pytest.mark.asyncio
    async def test_analyze_returns_result(
        self,
        orchestrator: AnalyzerOrchestrator,
        valid_solana_address: str,
    ) -> None:
        """Analyze should return AnalysisResult."""
        result = await orchestrator.analyze(valid_solana_address)
        assert isinstance(result, AnalysisResult)

    @pytest.mark.asyncio
    async def test_result_has_risk_level(
        self,
        orchestrator: AnalyzerOrchestrator,
        valid_solana_address: str,
    ) -> None:
        """Result should have valid risk level."""
        result = await orchestrator.analyze(valid_solana_address)
        assert result.risk in [RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]

    @pytest.mark.asyncio
    async def test_result_has_summary(
        self,
        orchestrator: AnalyzerOrchestrator,
        valid_solana_address: str,
    ) -> None:
        """Result should have non-empty summary."""
        result = await orchestrator.analyze(valid_solana_address)
        assert result.summary
        assert len(result.summary) > 10

    @pytest.mark.asyncio
    async def test_result_has_reasons(
        self,
        orchestrator: AnalyzerOrchestrator,
        valid_solana_address: str,
    ) -> None:
        """Result should have list of reasons."""
        result = await orchestrator.analyze(valid_solana_address)
        assert result.why
        assert len(result.why) >= 1
        assert all(isinstance(reason, str) for reason in result.why)

    @pytest.mark.asyncio
    async def test_result_has_recommendation(
        self,
        orchestrator: AnalyzerOrchestrator,
        valid_solana_address: str,
    ) -> None:
        """Result should have valid recommendation."""
        result = await orchestrator.analyze(valid_solana_address)
        assert result.recommendation in [
            Recommendation.AVOID,
            Recommendation.CAUTION,
            Recommendation.OK,
        ]


class TestOrchestratorConsistency:
    """Tests for consistency of results."""

    @pytest.mark.asyncio
    async def test_same_address_same_result(
        self,
        orchestrator: AnalyzerOrchestrator,
        valid_solana_address: str,
    ) -> None:
        """Same address should produce consistent results."""
        result1 = await orchestrator.analyze(valid_solana_address)
        result2 = await orchestrator.analyze(valid_solana_address)

        # Mock providers are deterministic
        assert result1.risk == result2.risk
        assert result1.recommendation == result2.recommendation

    @pytest.mark.asyncio
    async def test_different_addresses_may_differ(
        self,
        orchestrator: AnalyzerOrchestrator,
        valid_solana_address: str,
        another_valid_address: str,
    ) -> None:
        """Different addresses should produce valid but possibly different results."""
        result1 = await orchestrator.analyze(valid_solana_address)
        result2 = await orchestrator.analyze(another_valid_address)

        # Both should be valid
        assert isinstance(result1, AnalysisResult)
        assert isinstance(result2, AnalysisResult)


class TestOrchestratorResultFormat:
    """Tests for result format compliance."""

    @pytest.mark.asyncio
    async def test_result_serializable_to_json(
        self,
        orchestrator: AnalyzerOrchestrator,
        valid_solana_address: str,
    ) -> None:
        """Result should be serializable to JSON."""
        result = await orchestrator.analyze(valid_solana_address)
        json_str = result.model_dump_json()

        assert '"risk"' in json_str
        assert '"summary"' in json_str
        assert '"why"' in json_str
        assert '"recommendation"' in json_str

    @pytest.mark.asyncio
    async def test_result_matches_spec_format(
        self,
        orchestrator: AnalyzerOrchestrator,
        valid_solana_address: str,
    ) -> None:
        """Result should match the spec format exactly."""
        result = await orchestrator.analyze(valid_solana_address)
        data = result.model_dump()

        # Check all required fields
        assert "risk" in data
        assert "summary" in data
        assert "why" in data
        assert "recommendation" in data

        # Check types
        assert isinstance(data["risk"], str)
        assert isinstance(data["summary"], str)
        assert isinstance(data["why"], list)
        assert isinstance(data["recommendation"], str)

        # Check values are from enums
        assert data["risk"] in ["high", "medium", "low"]
        assert data["recommendation"] in ["avoid", "caution", "ok"]
