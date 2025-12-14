"""
Pydantic models for TokenBrain application.

All data structures used throughout the application are defined here.
Models provide:
- Type safety
- Automatic validation
- JSON serialization/deserialization
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """
    Token risk level.

    Values match the LLM output format exactly.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Recommendation(str, Enum):
    """
    Trading recommendation based on risk analysis.

    Values match the LLM output format exactly.
    """

    AVOID = "avoid"
    CAUTION = "caution"
    OK = "ok"


class RugpullFlags(BaseModel):
    """
    Flags indicating potential rugpull risks.

    Each flag represents a specific risk factor that could indicate
    the token is a scam or high-risk investment.
    """

    new_contract: bool = False
    """Contract deployed recently (high risk indicator)"""

    low_liquidity: bool = False
    """Liquidity below safe threshold"""

    centralized_holders: bool = False
    """Top holders control majority of supply"""

    developer_wallet_moves: bool = False
    """Suspicious activity from developer wallets"""


class SocialInfo(BaseModel):
    """
    Token's social media presence.

    Legitimate projects usually have active social media presence.
    Missing social links can be a red flag.
    """

    twitter_exists: bool = False
    """Has a Twitter/X account"""

    telegram_exists: bool = False
    """Has a Telegram group"""

    website_valid: bool = False
    """Has a working website"""


class TokenData(BaseModel):
    """
    Normalized token data from various sources.

    This is the unified data structure that aggregates information
    from Helius, Birdeye, and other data providers.
    """

    # Basic info
    chain: str = "solana"
    """Blockchain network (always 'solana' for MVP)"""

    address: str
    """Token contract address"""

    name: str | None = None
    """Token name (e.g., 'Bonk')"""

    symbol: str | None = None
    """Token symbol (e.g., 'BONK')"""

    # Key metrics (None = data unavailable)
    age_days: int | None = None
    """Days since contract deployment (None if unknown)"""

    liquidity_usd: float | None = None
    """Total liquidity in USD (None if unknown)"""

    holders: int = Field(ge=0)
    """Number of token holders"""

    top10_holders_percent: float | None = Field(default=None, ge=0, le=100)
    """Percentage of supply held by top 10 wallets (None if unknown)"""

    tx_count_24h: int = Field(ge=0)
    """Transaction count in last 24 hours"""

    # Authority flags (None = data unavailable)
    mint_authority_exists: bool | None = None
    """Whether mint authority is still present (can mint more tokens)"""

    freeze_authority_exists: bool | None = None
    """Whether freeze authority is still present (can freeze transfers)"""

    metadata_mutable: bool | None = None
    """Whether token metadata can be changed"""

    # Holder concentration (None = data unavailable)
    top1_holder_percent: float | None = None
    """Percentage of supply held by largest wallet"""

    top5_holders_percent: float | None = None
    """Percentage of supply held by top 5 wallets"""

    # Risk indicators
    rugpull_flags: RugpullFlags = Field(default_factory=RugpullFlags)
    """Rugpull risk indicators"""

    social: SocialInfo = Field(default_factory=SocialInfo)
    """Social media presence"""

    model_config = {"from_attributes": True}


class AnalysisResult(BaseModel):
    """
    Final analysis result from LLM.

    This is the EXACT format that Claude must return.
    Mock provider must also return data in this exact format.

    JSON example:
    {
        "risk": "high",
        "summary": "Токен выглядит очень рискованным...",
        "why": ["Низкая ликвидность", "Новый контракт", "..."],
        "recommendation": "avoid"
    }
    """

    risk: RiskLevel
    """Risk level: high | medium | low"""

    summary: str = Field(min_length=1, max_length=500)
    """Brief explanation of the token (1-2 sentences)"""

    why: list[str] = Field(min_length=1, max_length=5)
    """List of reasons for the risk assessment (1-5 items)"""

    recommendation: Recommendation
    """Action recommendation: avoid | caution | ok"""

    model_config = {
        "json_schema_extra": {
            "example": {
                "risk": "high",
                "summary": "Токен выглядит очень рискованным: "
                "низкая ликвидность, маленький возраст, "
                "высокая концентрация держателей.",
                "why": [
                    "Ликвидность ниже безопасного порога",
                    "Контракт создан недавно",
                    "Топ-10 держателей контролируют большую часть предложения",
                ],
                "recommendation": "avoid",
            }
        }
    }


class RiskResult(BaseModel):
    """
    Result of risk calculation with completeness metrics.

    This model is returned by RiskService.calculate_risk() and contains:
    - Risk level decision
    - Data completeness scores (safety + context)
    - Raw risk signals for LLM
    - Human-readable factors for explanation

    Used for Anti-Hallucination Contract: LLM receives structured data
    and must not add new factors beyond those provided.
    """

    level: RiskLevel
    """Calculated risk level: HIGH, MEDIUM, or LOW"""

    safety_completeness: float = Field(ge=0.0, le=1.0)
    """Completeness of critical signals (mint, freeze, top1, top10). 1.0 = all known."""

    context_completeness: float = Field(ge=0.0, le=1.0)
    """Completeness of contextual signals (age, liquidity, metadata). 1.0 = all known."""

    risk_signals: dict[str, Any]
    """Raw risk signals for LLM (null = unknown)"""

    factors: list[str]
    """Human-readable risk factors. LLM must use ONLY these, not add new ones."""

    @property
    def total_completeness(self) -> float:
        """
        Combined completeness score.

        Safety is weighted 70%, context 30%.
        """
        return (self.safety_completeness * 0.7) + (self.context_completeness * 0.3)

    model_config = {"from_attributes": True}
