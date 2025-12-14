"""
Risk calculation service v2.

Calculates token risk level based on heuristic rules with data completeness tracking.
This is the "brain" of the risk assessment - it decides whether a token is HIGH, MEDIUM, or LOW risk.

Key principles:
1. LOW risk requires ALL critical signals to be known and safe
2. None (unknown data) = disqualifies from LOW risk
3. SafeList override for protocol tokens (wSOL, USDC, USDT)
4. Returns RiskResult with completeness scores for LLM

Decision Matrix:
- HIGH: mint_authority=True OR freeze_authority=True OR top1>50% OR top10>60%
        OR (age<7 AND known) OR (liquidity<20k AND known)
- LOW:  All critical signals known AND safe, no HIGH triggers
- MEDIUM: Default (insufficient data or mixed signals)
"""

import logging
from dataclasses import dataclass
from typing import Any

from bot.core.models import RiskLevel, RiskResult, TokenData

logger = logging.getLogger(__name__)


# UX-исключение для базовых протокольных токенов Solana
# НЕ whitelist проектов! Non-protocol токены ЗАПРЕЩЕНЫ.
SAFE_PROTOCOL_TOKENS = {
    "So11111111111111111111111111111111111111112",  # Wrapped SOL (native)
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC (Circle)
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT (Tether)
}


@dataclass(frozen=True)
class RiskThresholds:
    """
    Threshold values for risk calculation v2.2.

    Frozen dataclass ensures immutability.
    Can be loaded from config in the future.
    """

    # Liquidity thresholds (USD)
    liquidity_high_risk: float = 20_000
    liquidity_low_risk: float = 80_000

    # Age thresholds (days)
    age_high_risk: int = 7
    age_low_risk: int = 30

    # Holder concentration - HIGH risk triggers
    top1_high_risk: float = 50.0       # Single wallet > 50% = HIGH
    top5_high_risk: float = 50.0       # Top 5 > 50% = HIGH (standalone)
    top10_high_risk: float = 65.0      # Top 10 > 65% = HIGH
    top1_top2_high_risk: float = 40.0  # (top1 + top2) > 40% = HIGH

    # Holder concentration - LOW risk requirements (stricter)
    top1_low_risk: float = 25.0    # Top 1 must be ≤ 25% for LOW
    top5_low_risk: float = 40.0    # Top 5 must be ≤ 40% for LOW
    top10_low_risk: float = 55.0   # Top 10 must be ≤ 55% for LOW

    # Holders count - LOW risk requirement
    holders_low_risk: int = 100    # Must have ≥ 100 holders for LOW


class RiskService:
    """
    Service for calculating token risk level with data completeness tracking.

    Returns RiskResult containing:
    - level: HIGH/MEDIUM/LOW
    - safety_completeness: 0.0-1.0 (critical signals)
    - context_completeness: 0.0-1.0 (contextual signals)
    - risk_signals: dict for LLM
    - factors: human-readable reasons

    Usage:
        service = RiskService()
        result = service.calculate_risk(token_data)
    """

    def __init__(self, thresholds: RiskThresholds | None = None):
        """
        Initialize with optional custom thresholds.

        Args:
            thresholds: Custom risk thresholds (uses defaults if None)
        """
        self._thresholds = thresholds or RiskThresholds()

    def calculate_risk(self, token_data: TokenData) -> RiskResult:
        """
        Calculate risk level for a token.

        Order of evaluation:
        1. SafeList override (protocol tokens)
        2. HIGH risk conditions (any match = HIGH)
        3. LOW risk conditions (all must match = LOW)
        4. Default = MEDIUM

        Args:
            token_data: Normalized token information

        Returns:
            RiskResult with level, completeness scores, signals, and factors
        """
        # SafeList override — ТОЛЬКО протокольные токены, до risk-engine
        # data.address = mint address токена (проверено в models.py)
        if token_data.address in SAFE_PROTOCOL_TOKENS:
            logger.info(
                f"Token {token_data.symbol}: LOW risk (SafeList protocol token)"
            )
            return RiskResult(
                level=RiskLevel.LOW,
                safety_completeness=1.0,
                context_completeness=1.0,
                risk_signals={"safelist": True},
                factors=["Базовый протокольный токен Solana"],
            )

        # Extract signals and calculate completeness
        signals = self._extract_signals(token_data)
        safety_score = self._calculate_safety_completeness(signals)
        context_score = self._calculate_context_completeness(signals)
        factors = self.get_risk_factors(token_data)

        # Log for debugging
        self._log_risk_check(token_data, safety_score, context_score)

        # Determine risk level
        if self._is_high_risk(token_data):
            level = RiskLevel.HIGH
            logger.info(f"Token {token_data.symbol}: HIGH risk")
        elif self._is_low_risk(token_data):
            level = RiskLevel.LOW
            logger.info(f"Token {token_data.symbol}: LOW risk")
        else:
            level = RiskLevel.MEDIUM
            logger.info(
                f"Token {token_data.symbol}: MEDIUM risk "
                f"(safety={safety_score:.0%}, context={context_score:.0%})"
            )

        return RiskResult(
            level=level,
            safety_completeness=safety_score,
            context_completeness=context_score,
            risk_signals=signals,
            factors=factors,
        )

    def _extract_signals(self, data: TokenData) -> dict[str, Any]:
        """
        Extract all risk signals from token data (v2.2).

        Returns dict with None for unknown values (for LLM Anti-Hallucination).
        """
        return {
            # Critical signals (6) — affect LOW-gate
            "mint_authority_exists": data.mint_authority_exists,
            "freeze_authority_exists": data.freeze_authority_exists,
            "top1_holder_percent": data.top1_holder_percent,
            "top2_holder_percent": data.top2_holder_percent,
            "top5_holders_percent": data.top5_holders_percent,
            "top10_holders_percent": data.top10_holders_percent,
            # Contextual signals (4) — for explanation quality
            "age_days": data.age_days,
            "liquidity_usd": data.liquidity_usd,
            "metadata_mutable": data.metadata_mutable,
            "holders": data.holders,
        }

    def _calculate_safety_completeness(self, signals: dict[str, Any]) -> float:
        """
        Calculate completeness of critical signals (affects LOW-gate).

        Critical signals (6): mint, freeze, top1, top2, top5, top10
        """
        critical_signals = [
            "mint_authority_exists",
            "freeze_authority_exists",
            "top1_holder_percent",
            "top2_holder_percent",
            "top5_holders_percent",
            "top10_holders_percent",
        ]
        known = sum(1 for s in critical_signals if signals.get(s) is not None)
        return known / len(critical_signals)

    def _calculate_context_completeness(self, signals: dict[str, Any]) -> float:
        """
        Calculate completeness of contextual signals (affects explanation quality).

        Contextual signals (4): age, liquidity, metadata_mutable, holders
        """
        context_signals = ["age_days", "liquidity_usd", "metadata_mutable", "holders"]
        # holders is always known (has default 0), so check if it's > 0 for "known"
        known = sum(
            1
            for s in context_signals
            if (signals.get(s) is not None and (s != "holders" or signals.get(s) > 0))
        )
        return known / len(context_signals)

    def _log_risk_check(
        self, data: TokenData, safety_score: float, context_score: float
    ) -> None:
        """Log token data for debugging."""
        liq_str = (
            f"${data.liquidity_usd:,.0f}"
            if data.liquidity_usd is not None
            else "N/A"
        )
        age_str = f"{data.age_days}d" if data.age_days is not None else "N/A"
        top10_str = (
            f"{data.top10_holders_percent:.1f}%"
            if data.top10_holders_percent is not None
            else "N/A"
        )
        logger.debug(
            f"Calculating risk for {data.symbol}: "
            f"liquidity={liq_str}, age={age_str}, top10={top10_str}, "
            f"safety={safety_score:.0%}, context={context_score:.0%}"
        )

    def _is_high_risk(self, data: TokenData) -> bool:
        """
        Check if token meets ANY high risk condition (v2.2).

        HIGH risk triggers (immediate):
        - mint_authority_exists == True
        - freeze_authority_exists == True
        - top1_holder_percent > 50%
        - top5_holders_percent > 50% (standalone)
        - top10_holders_percent > 65%
        - (top1 + top2) > 40%
        - age_days is None AND liquidity_usd is None (full opacity)

        Contextual signals (HIGH only if known):
        - age_days < 7
        - liquidity_usd < 20k

        Args:
            data: Token data to check

        Returns:
            True if any high risk condition is met
        """
        t = self._thresholds

        # Critical signals — immediate HIGH
        if data.mint_authority_exists is True:
            logger.debug("HIGH risk: mint authority exists")
            return True

        if data.freeze_authority_exists is True:
            logger.debug("HIGH risk: freeze authority exists")
            return True

        if (
            data.top1_holder_percent is not None
            and data.top1_holder_percent > t.top1_high_risk
        ):
            logger.debug(
                f"HIGH risk: top1 {data.top1_holder_percent}% > {t.top1_high_risk}%"
            )
            return True

        # top5 > 50% standalone (no combo with age)
        if (
            data.top5_holders_percent is not None
            and data.top5_holders_percent > t.top5_high_risk
        ):
            logger.debug(
                f"HIGH risk: top5 {data.top5_holders_percent}% > {t.top5_high_risk}%"
            )
            return True

        if (
            data.top10_holders_percent is not None
            and data.top10_holders_percent > t.top10_high_risk
        ):
            logger.debug(
                f"HIGH risk: top10 {data.top10_holders_percent}% > {t.top10_high_risk}%"
            )
            return True

        # (top1 + top2) > 40% — two whales control too much
        if (
            data.top1_holder_percent is not None
            and data.top2_holder_percent is not None
        ):
            top1_top2_sum = data.top1_holder_percent + data.top2_holder_percent
            if top1_top2_sum > t.top1_top2_high_risk:
                logger.debug(
                    f"HIGH risk: (top1 + top2) = {top1_top2_sum}% > {t.top1_top2_high_risk}%"
                )
                return True

        # Full opacity: both age AND liquidity unknown = HIGH
        if data.age_days is None and data.liquidity_usd is None:
            logger.debug("HIGH risk: both age and liquidity unknown (full opacity)")
            return True

        # Contextual signals — HIGH only if known and dangerous
        if (
            data.liquidity_usd is not None
            and data.liquidity_usd < t.liquidity_high_risk
        ):
            logger.debug(
                f"HIGH risk: liquidity {data.liquidity_usd} < {t.liquidity_high_risk}"
            )
            return True

        if data.age_days is not None and data.age_days < t.age_high_risk:
            logger.debug(f"HIGH risk: age {data.age_days} < {t.age_high_risk}")
            return True

        return False

    def _is_low_risk(self, data: TokenData) -> bool:
        """
        Check if token meets ALL low risk conditions (v2.2).

        LOW is ALLOWED only if ALL conditions are met:
        1. mint_authority_exists == False (known)
        2. freeze_authority_exists == False (known)
        3. top1_holder_percent ≤ 25% (known)
        4. top2_holder_percent (known) — for safety completeness
        5. top5_holders_percent ≤ 40% (known)
        6. top10_holders_percent ≤ 55% (known)
        7. liquidity_usd ≥ 80k (known)
        8. age_days ≥ 30 (known)
        9. holders ≥ 100 (if known)

        If ANY critical data is None or above threshold → LOW is FORBIDDEN.

        Args:
            data: Token data to check

        Returns:
            True only if ALL low risk conditions are met
        """
        t = self._thresholds

        # LOW ЗАПРЕЩЁН если любой критический сигнал = None
        if data.mint_authority_exists is None:
            logger.debug("LOW forbidden: mint_authority_exists is None")
            return False
        if data.freeze_authority_exists is None:
            logger.debug("LOW forbidden: freeze_authority_exists is None")
            return False
        if data.top1_holder_percent is None:
            logger.debug("LOW forbidden: top1_holder_percent is None")
            return False
        if data.top2_holder_percent is None:
            logger.debug("LOW forbidden: top2_holder_percent is None")
            return False
        if data.top5_holders_percent is None:
            logger.debug("LOW forbidden: top5_holders_percent is None")
            return False
        if data.top10_holders_percent is None:
            logger.debug("LOW forbidden: top10_holders_percent is None")
            return False

        # LOW ЗАПРЕЩЁН если authority активны
        if data.mint_authority_exists is True:
            return False
        if data.freeze_authority_exists is True:
            return False

        # LOW ЗАПРЕЩЁН если концентрация выше строгих порогов
        if data.top1_holder_percent > t.top1_low_risk:
            logger.debug(f"LOW forbidden: top1 {data.top1_holder_percent}% > {t.top1_low_risk}%")
            return False
        if data.top5_holders_percent > t.top5_low_risk:
            logger.debug(f"LOW forbidden: top5 {data.top5_holders_percent}% > {t.top5_low_risk}%")
            return False
        if data.top10_holders_percent > t.top10_low_risk:
            logger.debug(f"LOW forbidden: top10 {data.top10_holders_percent}% > {t.top10_low_risk}%")
            return False

        # LOW ЗАПРЕЩЁН если liquidity/age неизвестны или недостаточны
        if data.liquidity_usd is None:
            logger.debug("LOW forbidden: liquidity_usd is None")
            return False
        if data.liquidity_usd < t.liquidity_low_risk:
            logger.debug(f"LOW forbidden: liquidity {data.liquidity_usd} < {t.liquidity_low_risk}")
            return False

        if data.age_days is None:
            logger.debug("LOW forbidden: age_days is None")
            return False
        if data.age_days < t.age_low_risk:
            logger.debug(f"LOW forbidden: age {data.age_days} < {t.age_low_risk}")
            return False

        # LOW ЗАПРЕЩЁН если мало холдеров (если известно)
        if data.holders < t.holders_low_risk:
            logger.debug(f"LOW forbidden: holders {data.holders} < {t.holders_low_risk}")
            return False

        return True

    def get_risk_factors(self, data: TokenData) -> list[str]:
        """
        Get list of risk factors for a token (v2.2).

        Returns human-readable descriptions for LLM.
        LLM must use ONLY these factors, not add new ones.

        Includes UX Confidence Gate: if total_completeness < 0.5,
        adds warning about insufficient data.

        Args:
            data: Token data to analyze

        Returns:
            List of risk factor descriptions in Russian
        """
        t = self._thresholds
        factors: list[str] = []

        # Calculate completeness for UX Confidence Gate
        signals = self._extract_signals(data)
        safety_score = self._calculate_safety_completeness(signals)
        context_score = self._calculate_context_completeness(signals)
        total_completeness = (safety_score * 0.7) + (context_score * 0.3)

        # UX Confidence Gate: if total completeness < 50%, warn user
        if total_completeness < 0.5:
            factors.append("⚠️ Недостаточно данных для уверенной оценки")

        # Full opacity: both age AND liquidity unknown = HIGH risk factor
        if data.age_days is None and data.liquidity_usd is None:
            factors.append("Полная непрозрачность: возраст и ликвидность неизвестны")

        # Unknown critical signals (for transparency)
        if data.mint_authority_exists is None:
            factors.append("Данные о mint authority недоступны")
        if data.freeze_authority_exists is None:
            factors.append("Данные о freeze authority недоступны")
        if data.top1_holder_percent is None:
            factors.append("Данные о крупнейшем держателе недоступны")
        if data.top2_holder_percent is None:
            factors.append("Данные о втором крупнейшем держателе недоступны")
        if data.top10_holders_percent is None:
            factors.append("Данные о распределении токенов недоступны")

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

        # (top1 + top2) > 40% — two whales control too much (v2.2)
        if (
            data.top1_holder_percent is not None
            and data.top2_holder_percent is not None
        ):
            top1_top2_sum = data.top1_holder_percent + data.top2_holder_percent
            if top1_top2_sum > t.top1_top2_high_risk:
                factors.append(
                    f"Два крупнейших кошелька контролируют {top1_top2_sum:.0f}% токенов"
                )

        # Top 5 > 50% standalone HIGH (v2.2)
        if (
            data.top5_holders_percent is not None
            and data.top5_holders_percent > t.top5_high_risk
        ):
            factors.append(
                f"Топ-5 держателей контролируют {data.top5_holders_percent:.0f}% токенов"
            )

        # Top 10 concentration > 65%
        if (
            data.top10_holders_percent is not None
            and data.top10_holders_percent > t.top10_high_risk
        ):
            factors.append(
                f"Высокая концентрация держателей "
                f"(топ-10 = {data.top10_holders_percent:.0f}%)"
            )

        # Top 5 moderate (40-50%) — warning, not HIGH
        if (
            data.top5_holders_percent is not None
            and t.top5_low_risk < data.top5_holders_percent <= t.top5_high_risk
        ):
            factors.append(
                f"Умеренная концентрация у топ-5 ({data.top5_holders_percent:.0f}%)"
            )

        # Liquidity factors (contextual)
        if data.liquidity_usd is None:
            # Skip if already covered by "full opacity"
            if data.age_days is not None:
                factors.append("Ликвидность неизвестна")
        elif data.liquidity_usd < t.liquidity_high_risk:
            factors.append(f"Очень низкая ликвидность (${data.liquidity_usd:,.0f})")
        elif data.liquidity_usd < t.liquidity_low_risk:
            factors.append(f"Умеренная ликвидность (${data.liquidity_usd:,.0f})")

        # Age factors (contextual)
        if data.age_days is None:
            # Skip if already covered by "full opacity"
            if data.liquidity_usd is not None:
                factors.append("Возраст токена неизвестен")
        elif data.age_days < t.age_high_risk:
            factors.append(f"Очень новый токен ({data.age_days} дней)")
        elif data.age_days < t.age_low_risk:
            factors.append(f"Относительно новый токен ({data.age_days} дней)")

        # Low holders count — blocks LOW risk
        if data.holders > 0 and data.holders < t.holders_low_risk:
            factors.append(f"Мало держателей ({data.holders})")

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
