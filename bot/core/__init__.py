"""
Core module - models, protocols, and exceptions.

This module contains the fundamental building blocks of the application:
- Data models (Pydantic)
- Protocol definitions (interfaces)
- Custom exceptions
"""

from bot.core.exceptions import (
    DataFetchError,
    LLMError,
    TokenBrainError,
    ValidationError,
)
from bot.core.models import (
    AnalysisResult,
    Recommendation,
    RiskLevel,
    RugpullFlags,
    SocialInfo,
    TokenData,
)
from bot.core.protocols import LLMProvider, TokenDataProvider

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
