"""
Explanation service.

Generates human-readable analysis explanations using LLM.
This service is the bridge between raw data and user-friendly output.

Responsibilities:
1. Take token data and risk level
2. Call LLM provider to generate explanation
3. Return structured AnalysisResult
4. Enforce timeout on LLM calls
"""

import asyncio
import logging

from bot.core.exceptions import LLMError
from bot.core.models import AnalysisResult, RiskResult, TokenData
from bot.core.protocols import LLMProvider

logger = logging.getLogger(__name__)

# Default timeout for LLM calls (seconds)
DEFAULT_LLM_TIMEOUT = 30.0


class ExplainService:
    """
    Service for generating analysis explanations.

    Uses an LLMProvider to generate human-readable explanations
    of token risk. The service handles errors, logging, and timeouts.

    It does NOT:
    - Fetch token data (that's TokenDataAggregator's job)
    - Calculate risk (that's RiskService's job)

    Usage:
        service = ExplainService(llm_provider)
        result = await service.explain(token_data, risk_level)
    """

    def __init__(self, llm_provider: LLMProvider, timeout: float = DEFAULT_LLM_TIMEOUT):
        """
        Initialize with an LLM provider.

        Args:
            llm_provider: LLMProvider implementation (mock or Claude)
            timeout: Timeout for LLM calls in seconds
        """
        self._llm_provider = llm_provider
        self._timeout = timeout

    async def explain(
        self,
        token_data: TokenData,
        risk_result: RiskResult,
    ) -> AnalysisResult:
        """
        Generate explanation for token analysis.

        Calls the LLM to produce a human-readable summary
        of why the token has its risk level.

        Anti-Hallucination Contract:
        - LLM receives risk_result.factors[] and must use ONLY these
        - LLM must not add new factors
        - Risk level is fixed by risk_result.level

        Args:
            token_data: Normalized token information
            risk_result: Pre-calculated risk with factors and completeness scores

        Returns:
            AnalysisResult with summary, reasons, and recommendation

        Raises:
            LLMError: If explanation generation fails
        """
        logger.info(
            f"Generating explanation for {token_data.symbol}, "
            f"risk={risk_result.level.value}, "
            f"safety={risk_result.safety_completeness:.0%}, "
            f"context={risk_result.context_completeness:.0%}"
        )

        try:
            # Enforce timeout on LLM call
            result = await asyncio.wait_for(
                self._llm_provider.generate_analysis(
                    token_data,
                    risk_result,
                ),
                timeout=self._timeout,
            )

            logger.debug(
                f"Explanation generated: {len(result.summary)} chars, "
                f"{len(result.why)} reasons"
            )

            return result

        except TimeoutError:
            logger.error(f"LLM timeout after {self._timeout}s")
            raise LLMError(
                message="Сервис анализа не ответил вовремя. Попробуйте позже.",
                technical_message=f"LLM timeout after {self._timeout}s",
            ) from None

        except LLMError:
            # Re-raise our own exceptions
            raise

        except Exception as e:
            # Wrap unexpected errors
            logger.exception(f"Unexpected error generating explanation: {e}")
            raise LLMError(
                message="Не удалось сгенерировать анализ.",
                technical_message=f"LLM error: {type(e).__name__}: {e}",
            ) from e
