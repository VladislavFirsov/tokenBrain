"""
Analyzer orchestrator.

Coordinates the analysis workflow without containing business logic.
This is the entry point for token analysis - it calls the services
in the correct order and returns the final result.

Workflow:
1. TokenDataAggregator → get token data
2. RiskService → calculate risk level
3. ExplainService → generate explanation
4. Return AnalysisResult
"""

import logging

from bot.core.models import AnalysisResult
from bot.services.explain.service import ExplainService
from bot.services.risk.service import RiskService
from bot.services.token_data.aggregator import TokenDataAggregator

logger = logging.getLogger(__name__)


class AnalyzerOrchestrator:
    """
    Orchestrates the token analysis workflow.

    This class coordinates between services but contains NO business logic.
    Each step is delegated to a specialized service:
    - Data fetching → TokenDataAggregator
    - Risk calculation → RiskService
    - Explanation generation → ExplainService

    The orchestrator's responsibility is purely coordination:
    1. Call services in correct order
    2. Pass data between services
    3. Handle logging
    4. Return final result

    Usage:
        orchestrator = AnalyzerOrchestrator(aggregator, risk_service, explain_service)
        result = await orchestrator.analyze("So111...")
    """

    def __init__(
        self,
        aggregator: TokenDataAggregator,
        risk_service: RiskService,
        explain_service: ExplainService,
    ):
        """
        Initialize orchestrator with all required services.

        Args:
            aggregator: Service for fetching token data
            risk_service: Service for calculating risk level
            explain_service: Service for generating explanations
        """
        self._aggregator = aggregator
        self._risk_service = risk_service
        self._explain_service = explain_service

    async def analyze(self, token_address: str) -> AnalysisResult:
        """
        Perform full token analysis.

        Orchestrates the complete analysis workflow:
        1. Fetch token data from providers
        2. Calculate risk level using heuristics
        3. Generate human-readable explanation
        4. Return structured result

        Args:
            token_address: Validated Solana token address

        Returns:
            AnalysisResult with risk level, summary, reasons, and recommendation

        Raises:
            DataFetchError: If token data cannot be fetched
            LLMError: If explanation cannot be generated
        """
        logger.info(f"Starting analysis for token: {token_address[:8]}...")

        # Step 1: Fetch token data
        token_data = await self._aggregator.get_token_data(token_address)
        logger.debug(
            f"Token data: {token_data.symbol}, ${token_data.liquidity_usd:,.0f}"
        )

        # Step 2: Calculate risk level
        risk_level = self._risk_service.calculate_risk(token_data)
        logger.debug(f"Risk level: {risk_level.value}")

        # Step 3: Generate explanation
        result = await self._explain_service.explain(token_data, risk_level)
        logger.info(
            f"Analysis complete for {token_data.symbol}: "
            f"{risk_level.value} risk, {result.recommendation.value}"
        )

        return result
