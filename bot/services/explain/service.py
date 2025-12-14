"""
Explanation service.

Generates human-readable analysis explanations using LLM.
This service is the bridge between raw data and user-friendly output.

Responsibilities:
1. Take token data and risk level
2. Call LLM provider to generate explanation
3. Return structured AnalysisResult
"""

import logging

from bot.core.models import TokenData, RiskLevel, AnalysisResult
from bot.core.protocols import LLMProvider
from bot.core.exceptions import LLMError

logger = logging.getLogger(__name__)


class ExplainService:
    """
    Service for generating analysis explanations.

    Uses an LLMProvider to generate human-readable explanations
    of token risk. The service handles errors and logging.

    It does NOT:
    - Fetch token data (that's TokenDataAggregator's job)
    - Calculate risk (that's RiskService's job)

    Usage:
        service = ExplainService(llm_provider)
        result = await service.explain(token_data, risk_level)
    """

    def __init__(self, llm_provider: LLMProvider):
        """
        Initialize with an LLM provider.

        Args:
            llm_provider: LLMProvider implementation (mock or Claude)
        """
        self._llm_provider = llm_provider

    async def explain(
        self,
        token_data: TokenData,
        risk_level: RiskLevel,
    ) -> AnalysisResult:
        """
        Generate explanation for token analysis.

        Calls the LLM to produce a human-readable summary
        of why the token has its risk level.

        Args:
            token_data: Normalized token information
            risk_level: Pre-calculated risk level

        Returns:
            AnalysisResult with summary, reasons, and recommendation

        Raises:
            LLMError: If explanation generation fails
        """
        logger.info(
            f"Generating explanation for {token_data.symbol}, "
            f"risk={risk_level.value}"
        )

        try:
            result = await self._llm_provider.generate_analysis(
                token_data,
                risk_level,
            )

            logger.debug(
                f"Explanation generated: {len(result.summary)} chars, "
                f"{len(result.why)} reasons"
            )

            return result

        except LLMError:
            # Re-raise our own exceptions
            raise

        except Exception as e:
            # Wrap unexpected errors
            logger.exception(f"Unexpected error generating explanation: {e}")
            raise LLMError(
                message="Не удалось сгенерировать анализ.",
                technical_message=f"LLM error: {type(e).__name__}: {e}",
            )
