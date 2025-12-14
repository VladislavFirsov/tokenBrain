"""
Core module - models, protocols, and exceptions.

This module contains the fundamental building blocks of the application:
- Data models (Pydantic)
- Protocol definitions (interfaces)
- Custom exceptions
"""

from bot.core.exceptions import (
    TokenBrainError,
    ValidationError,
    DataFetchError,
    LLMError,
)
from bot.core.models import (
    RiskLevel,
    Recommendation,
    RugpullFlags,
    SocialInfo,
    TokenData,
    AnalysisResult,
)
from bot.core.protocols import TokenDataProvider, LLMProvider

__all__ = [
    # Exceptions
    "TokenBrainError",
    "ValidationError",
    "DataFetchError",
    "LLMError",
    # Models
    "RiskLevel",
    "Recommendation",
    "RugpullFlags",
    "SocialInfo",
    "TokenData",
    "AnalysisResult",
    # Protocols
    "TokenDataProvider",
    "LLMProvider",
]
