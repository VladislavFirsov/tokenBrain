"""
Mock LLM provider for development.

Generates realistic analysis responses without calling real LLM API.
Uses Anti-Hallucination Contract: only uses factors from RiskResult.

Output format (must match exactly):
{
    "risk": "high | medium | low",
    "summary": "string (1-2 sentences)",
    "why": ["reason1", "reason2", "reason3"],
    "recommendation": "avoid | caution | ok"
}
"""

from bot.core.models import (
    AnalysisResult,
    Recommendation,
    RiskLevel,
    RiskResult,
    TokenData,
)


class MockLLMProvider:
    """
    Mock LLM provider that returns template-based responses.

    Anti-Hallucination Contract:
    - Uses ONLY factors[] from RiskResult for "why" field
    - Does not add new reasons
    - Risk level comes from RiskResult.level

    Usage:
        provider = MockLLMProvider()
        result = await provider.generate_analysis(token_data, risk_result)
    """

    async def generate_analysis(
        self,
        token_data: TokenData,
        risk_result: RiskResult,
    ) -> AnalysisResult:
        """
        Generate mock analysis based on RiskResult.

        Anti-Hallucination: uses ONLY factors from risk_result.

        Args:
            token_data: Token information
            risk_result: Pre-calculated risk with factors and completeness

        Returns:
            AnalysisResult matching exact Claude API format
        """
        risk_level = risk_result.level

        # Anti-Hallucination: use ONLY factors from risk_result
        why = risk_result.factors[:5] if risk_result.factors else []

        # Ensure at least one reason
        if not why:
            why = self._default_reasons(risk_level)

        # Build summary based on risk level and completeness
        summary = self._build_summary(token_data, risk_result)

        # Recommendation based on risk level
        recommendations = {
            RiskLevel.HIGH: Recommendation.AVOID,
            RiskLevel.MEDIUM: Recommendation.CAUTION,
            RiskLevel.LOW: Recommendation.OK,
        }

        return AnalysisResult(
            risk=risk_level,
            summary=summary,
            why=why,
            recommendation=recommendations[risk_level],
        )

    def _default_reasons(self, risk_level: RiskLevel) -> list[str]:
        """Default reasons when factors are empty."""
        defaults = {
            RiskLevel.HIGH: ["Обнаружены критические проблемы"],
            RiskLevel.MEDIUM: ["Недостаточно данных для полного анализа"],
            RiskLevel.LOW: ["Основные показатели в норме"],
        }
        return defaults[risk_level]

    def _build_summary(self, token_data: TokenData, risk_result: RiskResult) -> str:
        """Build summary based on risk level and completeness."""
        symbol = token_data.name or token_data.symbol or "Токен"
        risk_level = risk_result.level

        # Note about data completeness
        completeness_note = ""
        if risk_result.safety_completeness < 1.0:
            completeness_note = " Часть данных недоступна."

        summaries = {
            RiskLevel.HIGH: (
                f"{symbol}: высокий риск. Обнаружены критические проблемы.{completeness_note}"
            ),
            RiskLevel.MEDIUM: (
                f"{symbol}: средний риск. "
                f"Требуется осторожность.{completeness_note}"
            ),
            RiskLevel.LOW: (
                f"{symbol}: низкий риск. Основные показатели в норме.{completeness_note}"
            ),
        }

        return summaries[risk_level]
