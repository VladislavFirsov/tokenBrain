"""
Risk calculation service.

Calculates token risk level based on heuristic rules.
This is the "brain" of the risk assessment - it decides
whether a token is HIGH, MEDIUM, or LOW risk.

Risk Rules (MVP):
- HIGH: liquidity < $20k OR age < 7 days OR top10 > 60%
- MEDIUM: liquidity 20k-80k OR age 7-30 days
- LOW: liquidity > 80k AND age > 30 days AND top10 <= 60%
"""

import logging
from dataclasses import dataclass

from bot.core.models import RiskLevel, TokenData

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskThresholds:
    """
    Threshold values for risk calculation.

    Frozen dataclass ensures immutability.
    Can be loaded from config in the future.
    """

    # Liquidity thresholds (USD)
    liquidity_high_risk: float = 20_000
    liquidity_low_risk: float = 80_000

    # Age thresholds (days)
    age_high_risk: int = 7
    age_low_risk: int = 30

    # Holder concentration thresholds (%)
    top10_high_risk: float = 60.0
    top1_high_risk: float = 50.0  # Single wallet controlling majority
    top5_warning: float = 40.0  # Warning level for top 5


class RiskService:
    """
    Service for calculating token risk level.

    Applies heuristic rules to token data to determine risk.
    Does NOT generate explanations - that's ExplainService's job.

    The service is stateless - all data needed for calculation
    is passed to the method.

    Usage:
        service = RiskService()
        risk_level = service.calculate_risk(token_data)
    """

    def __init__(self, thresholds: RiskThresholds | None = None):
        """
        Initialize with optional custom thresholds.

        Args:
            thresholds: Custom risk thresholds (uses defaults if None)
        """
        self._thresholds = thresholds or RiskThresholds()

    def calculate_risk(self, token_data: TokenData) -> RiskLevel:
        """
        Calculate risk level for a token.

        Applies the following rules in order:
        1. Check HIGH risk conditions (any match = HIGH)
        2. Check LOW risk conditions (all must match = LOW)
        3. Otherwise = MEDIUM

        Args:
            token_data: Normalized token information

        Returns:
            RiskLevel (HIGH, MEDIUM, or LOW)
        """
        # Format optional values for logging
        liq_str = (
            f"${token_data.liquidity_usd:,.0f}"
            if token_data.liquidity_usd is not None
            else "N/A"
        )
        age_str = (
            f"{token_data.age_days}d" if token_data.age_days is not None else "N/A"
        )
        logger.debug(
            f"Calculating risk for {token_data.symbol}: "
            f"liquidity={liq_str}, "
            f"age={age_str}, "
            f"top10={token_data.top10_holders_percent:.1f}%"
        )

        # Check HIGH risk conditions first
        if self._is_high_risk(token_data):
            logger.info(f"Token {token_data.symbol}: HIGH risk")
            return RiskLevel.HIGH

        # Check LOW risk conditions
        if self._is_low_risk(token_data):
            logger.info(f"Token {token_data.symbol}: LOW risk")
            return RiskLevel.LOW

        # Default to MEDIUM
        logger.info(f"Token {token_data.symbol}: MEDIUM risk")
        return RiskLevel.MEDIUM

    def _is_high_risk(self, data: TokenData) -> bool:
        """
        Check if token meets ANY high risk condition.

        High risk if:
        - Liquidity < $20k (too little to exit)
        - Age < 7 days (too new, unproven)
        - Top 10 holders > 60% (centralized, dump risk)
        - Mint authority exists (can print more tokens)
        - Freeze authority exists (can freeze transfers)
        - Top 1 holder > 50% (single wallet controls majority)

        Args:
            data: Token data to check

        Returns:
            True if any high risk condition is met
        """
        t = self._thresholds

        # Low liquidity = can't exit position
        # None means unknown, don't trigger high risk for unknown data
        if (
            data.liquidity_usd is not None
            and data.liquidity_usd < t.liquidity_high_risk
        ):
            logger.debug(
                f"HIGH risk: liquidity {data.liquidity_usd} < {t.liquidity_high_risk}"
            )
            return True

        # Too new = unproven, could be rugpull
        # None means unknown, don't trigger high risk for unknown data
        if data.age_days is not None and data.age_days < t.age_high_risk:
            logger.debug(f"HIGH risk: age {data.age_days} < {t.age_high_risk}")
            return True

        # Concentrated holdings = dump risk
        if data.top10_holders_percent > t.top10_high_risk:
            logger.debug(
                f"HIGH risk: top10 {data.top10_holders_percent}% > {t.top10_high_risk}%"
            )
            return True

        # Mint authority exists = can inflate supply
        if data.mint_authority_exists is True:
            logger.debug("HIGH risk: mint authority exists")
            return True

        # Freeze authority exists = can freeze transfers
        if data.freeze_authority_exists is True:
            logger.debug("HIGH risk: freeze authority exists")
            return True

        # Single wallet controls majority
        if (
            data.top1_holder_percent is not None
            and data.top1_holder_percent > t.top1_high_risk
        ):
            logger.debug(
                f"HIGH risk: top1 {data.top1_holder_percent}% > {t.top1_high_risk}%"
            )
            return True

        return False

    def _is_low_risk(self, data: TokenData) -> bool:
        """
        Check if token meets ALL low risk conditions.

        Low risk only if:
        - Liquidity > $80k (sufficient to exit) OR unknown
        - Age > 30 days (established) OR unknown
        - Top 10 holders <= 60% (decentralized)
        - No dangerous authorities

        Args:
            data: Token data to check

        Returns:
            True only if ALL low risk conditions are met
        """
        t = self._thresholds

        # Must have good liquidity (if known)
        # Unknown liquidity doesn't disqualify from low risk
        if (
            data.liquidity_usd is not None
            and data.liquidity_usd <= t.liquidity_low_risk
        ):
            return False

        # Must be established (if known)
        # Unknown age doesn't disqualify from low risk
        if data.age_days is not None and data.age_days <= t.age_low_risk:
            return False

        # Must be decentralized
        if data.top10_holders_percent > t.top10_high_risk:
            return False

        # Must not have dangerous authorities
        if data.mint_authority_exists is True:
            return False
        if data.freeze_authority_exists is True:
            return False

        return True

    def get_risk_factors(self, data: TokenData) -> list[str]:
        """
        Get list of risk factors for a token.

        Useful for understanding why a token received its risk level.
        Returns human-readable descriptions of risk factors.

        Args:
            data: Token data to analyze

        Returns:
            List of risk factor descriptions
        """
        t = self._thresholds
        factors = []

        # Authority factors (critical)
        if data.mint_authority_exists is True:
            factors.append("Mint authority активен (можно создавать новые токены)")

        if data.freeze_authority_exists is True:
            factors.append("Freeze authority активен (можно заморозить переводы)")

        # Top 1 holder (critical)
        if (
            data.top1_holder_percent is not None
            and data.top1_holder_percent > t.top1_high_risk
        ):
            factors.append(
                f"Один кошелёк контролирует {data.top1_holder_percent:.0f}% токенов"
            )

        # Liquidity factors (None-safe)
        if data.liquidity_usd is not None:
            if data.liquidity_usd < t.liquidity_high_risk:
                factors.append(f"Очень низкая ликвидность (${data.liquidity_usd:,.0f})")
            elif data.liquidity_usd < t.liquidity_low_risk:
                factors.append(f"Умеренная ликвидность (${data.liquidity_usd:,.0f})")

        # Age factors (None-safe)
        if data.age_days is not None:
            if data.age_days < t.age_high_risk:
                factors.append(f"Очень новый токен ({data.age_days} дней)")
            elif data.age_days < t.age_low_risk:
                factors.append(f"Относительно новый токен ({data.age_days} дней)")

        # Concentration factors
        if data.top10_holders_percent > t.top10_high_risk:
            factors.append(
                f"Высокая концентрация держателей "
                f"(топ-10 = {data.top10_holders_percent:.0f}%)"
            )

        # Top 5 warning (not critical, but notable)
        if (
            data.top5_holders_percent is not None
            and data.top5_holders_percent > t.top5_warning
            and data.top10_holders_percent <= t.top10_high_risk  # Don't duplicate
        ):
            factors.append(
                f"Умеренная концентрация у топ-5 ({data.top5_holders_percent:.0f}%)"
            )

        # Metadata mutable (warning, not critical)
        if data.metadata_mutable is True:
            factors.append("Метаданные токена могут быть изменены")

        # Rugpull flags
        if data.rugpull_flags.developer_wallet_moves:
            factors.append("Подозрительная активность кошелька разработчика")

        # Social factors (absence is a risk)
        missing_social = []
        if not data.social.twitter_exists:
            missing_social.append("Twitter")
        if not data.social.telegram_exists:
            missing_social.append("Telegram")
        if not data.social.website_valid:
            missing_social.append("сайт")

        if len(missing_social) >= 2:
            factors.append(f"Отсутствуют: {', '.join(missing_social)}")

        return factors
