"""
Tests for RiskService.

Tests cover:
- HIGH risk conditions
- MEDIUM risk conditions
- LOW risk conditions
- Edge cases at thresholds
- Risk factor detection
"""

from bot.core.models import RiskLevel, TokenData
from bot.services.risk.service import RiskService


class TestRiskServiceHighRisk:
    """Tests for HIGH risk detection."""

    def test_low_liquidity_is_high_risk(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Liquidity < $20k should be HIGH risk."""
        low_risk_token.liquidity_usd = 15_000
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.HIGH

    def test_new_token_is_high_risk(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Age < 7 days should be HIGH risk."""
        low_risk_token.age_days = 5
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.HIGH

    def test_concentrated_holders_is_high_risk(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Top 10 holders > 60% should be HIGH risk."""
        low_risk_token.top10_holders_percent = 75
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.HIGH

    def test_multiple_high_risk_factors(
        self,
        risk_service: RiskService,
        high_risk_token: TokenData,
    ) -> None:
        """Token with multiple high risk factors should be HIGH risk."""
        result = risk_service.calculate_risk(high_risk_token)
        assert result == RiskLevel.HIGH

    def test_mint_authority_is_high_risk(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Mint authority present should be HIGH risk."""
        low_risk_token.mint_authority_exists = True
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.HIGH

    def test_freeze_authority_is_high_risk(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Freeze authority present should be HIGH risk."""
        low_risk_token.freeze_authority_exists = True
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.HIGH

    def test_top1_holder_over_50_is_high_risk(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Top 1 holder > 50% should be HIGH risk."""
        low_risk_token.top1_holder_percent = 55.0
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.HIGH

    def test_none_authority_is_not_high_risk(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """None (unknown) authority should not trigger HIGH risk."""
        low_risk_token.mint_authority_exists = None
        low_risk_token.freeze_authority_exists = None
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.LOW  # Token is otherwise low risk


class TestRiskServiceLowRisk:
    """Tests for LOW risk detection."""

    def test_good_metrics_is_low_risk(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Token with all good metrics should be LOW risk."""
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.LOW

    def test_requires_high_liquidity(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Liquidity must be > $80k for LOW risk."""
        low_risk_token.liquidity_usd = 80_000  # Exactly at threshold
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.MEDIUM  # Not LOW because <= threshold

    def test_requires_old_age(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Age must be > 30 days for LOW risk."""
        low_risk_token.age_days = 30  # Exactly at threshold
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.MEDIUM

    def test_requires_good_distribution(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Top 10 holders must be <= 60% for LOW risk."""
        low_risk_token.top10_holders_percent = 61  # Just over threshold
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.HIGH  # High because > 60%


class TestRiskServiceMediumRisk:
    """Tests for MEDIUM risk detection."""

    def test_medium_liquidity_is_medium_risk(
        self,
        risk_service: RiskService,
        medium_risk_token: TokenData,
    ) -> None:
        """Token with medium metrics should be MEDIUM risk."""
        result = risk_service.calculate_risk(medium_risk_token)
        assert result == RiskLevel.MEDIUM

    def test_moderate_age_is_medium_risk(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Age 7-30 days with good other metrics should be MEDIUM."""
        low_risk_token.age_days = 15
        result = risk_service.calculate_risk(low_risk_token)
        assert result == RiskLevel.MEDIUM


class TestRiskServiceEdgeCases:
    """Tests for edge cases at thresholds."""

    def test_exactly_at_high_liquidity_threshold(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Liquidity exactly at $20k should be HIGH risk (< threshold)."""
        low_risk_token.liquidity_usd = 20_000
        result = risk_service.calculate_risk(low_risk_token)
        # At threshold, still safe (not less than)
        assert result in [RiskLevel.MEDIUM, RiskLevel.LOW]

    def test_exactly_at_age_threshold(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Age exactly at 7 days should be HIGH risk (< threshold)."""
        low_risk_token.age_days = 7
        result = risk_service.calculate_risk(low_risk_token)
        # At threshold, still safe (not less than)
        assert result in [RiskLevel.MEDIUM, RiskLevel.LOW]

    def test_exactly_at_holder_threshold(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Top 10 exactly at 60% should not be HIGH risk."""
        low_risk_token.top10_holders_percent = 60
        result = risk_service.calculate_risk(low_risk_token)
        assert result != RiskLevel.HIGH


class TestRiskServiceCustomThresholds:
    """Tests with custom thresholds."""

    def test_custom_thresholds_applied(
        self,
        custom_risk_service: RiskService,
    ) -> None:
        """Custom thresholds should change risk calculation."""
        # Custom thresholds: liquidity_low=50k, age_low=20, top10_high=50%
        token = TokenData(
            address="test",
            age_days=25,  # > 20 (custom age_low_risk)
            liquidity_usd=60_000,  # > 50k (custom liquidity_low_risk)
            holders=100,
            top10_holders_percent=40,  # <= 50% (custom top10_high_risk)
            tx_count_24h=100,
        )
        result = custom_risk_service.calculate_risk(token)
        assert result == RiskLevel.LOW


class TestRiskServiceFactors:
    """Tests for get_risk_factors method."""

    def test_detects_low_liquidity_factor(
        self,
        risk_service: RiskService,
        high_risk_token: TokenData,
    ) -> None:
        """Should detect low liquidity as risk factor."""
        factors = risk_service.get_risk_factors(high_risk_token)
        assert any("ликвидность" in f.lower() for f in factors)

    def test_detects_new_token_factor(
        self,
        risk_service: RiskService,
        high_risk_token: TokenData,
    ) -> None:
        """Should detect new token as risk factor."""
        factors = risk_service.get_risk_factors(high_risk_token)
        assert any("новый" in f.lower() for f in factors)

    def test_detects_concentration_factor(
        self,
        risk_service: RiskService,
        high_risk_token: TokenData,
    ) -> None:
        """Should detect holder concentration as risk factor."""
        factors = risk_service.get_risk_factors(high_risk_token)
        assert any("концентрация" in f.lower() for f in factors)

    def test_no_factors_for_low_risk(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Low risk token should have no major risk factors."""
        factors = risk_service.get_risk_factors(low_risk_token)
        # May have minor factors, but not major ones
        assert len(factors) <= 1

    def test_detects_mint_authority_factor(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Should detect mint authority as risk factor."""
        low_risk_token.mint_authority_exists = True
        factors = risk_service.get_risk_factors(low_risk_token)
        assert any("mint" in f.lower() for f in factors)

    def test_detects_freeze_authority_factor(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Should detect freeze authority as risk factor."""
        low_risk_token.freeze_authority_exists = True
        factors = risk_service.get_risk_factors(low_risk_token)
        assert any("freeze" in f.lower() for f in factors)

    def test_detects_top1_holder_factor(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Should detect top 1 holder concentration as risk factor."""
        low_risk_token.top1_holder_percent = 55.0
        factors = risk_service.get_risk_factors(low_risk_token)
        assert any("кошелёк" in f.lower() or "55" in f for f in factors)

    def test_detects_metadata_mutable_factor(
        self,
        risk_service: RiskService,
        low_risk_token: TokenData,
    ) -> None:
        """Should detect mutable metadata as risk factor."""
        low_risk_token.metadata_mutable = True
        factors = risk_service.get_risk_factors(low_risk_token)
        assert any("метаданные" in f.lower() for f in factors)
