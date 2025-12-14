"""
Service factory for dependency injection.

Creates and configures all services based on application settings.
Switches between mock and real implementations automatically.

This is the single point of service creation - all services
should be created through this factory.
"""

import logging

from bot.config.settings import Settings
from bot.core.protocols import LLMProvider, TokenDataProvider
from bot.services.explain.mock_llm import MockLLMProvider
from bot.services.explain.service import ExplainService
from bot.services.orchestrator import AnalyzerOrchestrator
from bot.services.risk.service import RiskService
from bot.services.token_data.aggregator import TokenDataAggregator
from bot.services.token_data.mock_provider import MockTokenDataProvider

logger = logging.getLogger(__name__)


class ServiceFactory:
    """
    Factory for creating application services.

    Reads configuration and creates appropriate service implementations:
    - Mock implementations for development (USE_MOCK_SERVICES=true)
    - Real implementations for production (USE_MOCK_SERVICES=false)

    All services are created lazily and cached for reuse.

    Usage:
        factory = ServiceFactory(settings)
        orchestrator = factory.create_orchestrator()
    """

    def __init__(self, settings: Settings):
        """
        Initialize factory with application settings.

        Args:
            settings: Application configuration
        """
        self._settings = settings
        self._log_mode()

    def _log_mode(self) -> None:
        """Log the current mode for debugging."""
        mode = "MOCK" if self._settings.use_mock_services else "PRODUCTION"
        logger.info(f"ServiceFactory initialized in {mode} mode")

    def create_token_data_provider(self) -> TokenDataProvider:
        """
        Create token data provider.

        Returns:
            TokenDataProvider implementation based on settings
        """
        if self._settings.use_mock_services:
            logger.debug("Creating MockTokenDataProvider")
            return MockTokenDataProvider()

        # TODO: Implement real provider with Helius/Birdeye
        # return RealTokenDataProvider(
        #     helius_api_key=self._settings.helius_api_key,
        #     birdeye_api_key=self._settings.birdeye_api_key,
        #     timeout=self._settings.api_timeout_seconds,
        # )
        raise NotImplementedError(
            "Real token data provider not implemented. "
            "Set USE_MOCK_SERVICES=true or implement RealTokenDataProvider."
        )

    def create_llm_provider(self) -> LLMProvider:
        """
        Create LLM provider.

        Returns:
            LLMProvider implementation based on settings
        """
        if self._settings.use_mock_services:
            logger.debug("Creating MockLLMProvider")
            return MockLLMProvider()

        # TODO: Implement Claude provider
        # return ClaudeLLMProvider(
        #     api_key=self._settings.claude_api_key,
        #     timeout=self._settings.api_timeout_seconds,
        # )
        raise NotImplementedError(
            "Claude LLM provider not implemented. "
            "Set USE_MOCK_SERVICES=true or implement ClaudeLLMProvider."
        )

    def create_token_data_aggregator(self) -> TokenDataAggregator:
        """
        Create token data aggregator.

        Creates aggregator with the appropriate provider
        based on current settings.

        Returns:
            TokenDataAggregator configured with provider
        """
        provider = self.create_token_data_provider()
        logger.debug("Creating TokenDataAggregator")
        return TokenDataAggregator(provider)

    def create_risk_service(self) -> RiskService:
        """
        Create risk calculation service.

        Risk service uses the same logic for both mock and production.

        Returns:
            RiskService with default thresholds
        """
        logger.debug("Creating RiskService")
        return RiskService()

    def create_explain_service(self) -> ExplainService:
        """
        Create explanation service.

        Creates service with the appropriate LLM provider
        based on current settings.

        Returns:
            ExplainService configured with LLM provider
        """
        llm_provider = self.create_llm_provider()
        logger.debug("Creating ExplainService")
        return ExplainService(llm_provider)

    def create_orchestrator(self) -> AnalyzerOrchestrator:
        """
        Create the main analyzer orchestrator.

        This is the primary service used by handlers.
        Creates all dependencies automatically.

        Returns:
            AnalyzerOrchestrator ready for use
        """
        logger.info("Creating AnalyzerOrchestrator with all dependencies")

        aggregator = self.create_token_data_aggregator()
        risk_service = self.create_risk_service()
        explain_service = self.create_explain_service()

        return AnalyzerOrchestrator(
            aggregator=aggregator,
            risk_service=risk_service,
            explain_service=explain_service,
        )
