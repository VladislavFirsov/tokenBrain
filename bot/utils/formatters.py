"""
Output formatters for Telegram messages.

Converts AnalysisResult into user-friendly Telegram messages.
Uses HTML formatting for better readability.
"""

from bot.core.models import AnalysisResult, RiskLevel, Recommendation


# Emoji mappings for risk levels
RISK_EMOJI = {
    RiskLevel.HIGH: "🔴",
    RiskLevel.MEDIUM: "🟡",
    RiskLevel.LOW: "🟢",
}

# Emoji mappings for recommendations
RECOMMENDATION_EMOJI = {
    Recommendation.AVOID: "🚫",
    Recommendation.CAUTION: "⚠️",
    Recommendation.OK: "👍",
}

# Russian labels for recommendations
RECOMMENDATION_LABEL = {
    Recommendation.AVOID: "Avoid",
    Recommendation.CAUTION: "Caution",
    Recommendation.OK: "OK",
}


def format_analysis_result(result: AnalysisResult) -> str:
    """
    Format analysis result as Telegram message.

    Creates a structured, readable message with:
    - Risk level indicator with emoji
    - Summary explanation
    - List of reasons
    - Final recommendation

    Uses HTML formatting (bold, italic, bullet points).

    Args:
        result: Analysis result from orchestrator

    Returns:
        Formatted HTML string for Telegram
    """
    risk_emoji = RISK_EMOJI[result.risk]
    risk_label = result.risk.value.upper()

    rec_emoji = RECOMMENDATION_EMOJI[result.recommendation]
    rec_label = RECOMMENDATION_LABEL[result.recommendation]

    # Format reasons as bullet list
    reasons_list = "\n".join(f"• {reason}" for reason in result.why)

    message = f"""
{risk_emoji} <b>Risk: {risk_label}</b>

{result.summary}

<b>Почему:</b>
{reasons_list}

<b>Рекомендация:</b> {rec_emoji} {rec_label}
""".strip()

    return message


def format_risk_badge(risk: RiskLevel) -> str:
    """
    Format a compact risk badge.

    Useful for inline displays or summaries.

    Args:
        risk: Risk level

    Returns:
        Formatted badge like "🔴 HIGH"
    """
    emoji = RISK_EMOJI[risk]
    label = risk.value.upper()
    return f"{emoji} {label}"


def format_recommendation_badge(recommendation: Recommendation) -> str:
    """
    Format a compact recommendation badge.

    Args:
        recommendation: Recommendation value

    Returns:
        Formatted badge like "🚫 Avoid"
    """
    emoji = RECOMMENDATION_EMOJI[recommendation]
    label = RECOMMENDATION_LABEL[recommendation]
    return f"{emoji} {label}"
