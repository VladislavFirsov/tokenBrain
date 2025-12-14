"""
Mock LLM provider for development.

Generates realistic analysis responses without calling real LLM API.
The output format is EXACTLY the same as what Claude would return,
ensuring UI/UX testing accuracy.

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
    TokenData,
)


class MockLLMProvider:
    """
    Mock LLM provider that returns template-based responses.

    Designed to produce output identical in structure to real Claude API.
    Responses are based on the pre-calculated risk level and token data.

    Usage:
        provider = MockLLMProvider()
        result = await provider.generate_analysis(token_data, RiskLevel.HIGH)
    """

    # Response templates by risk level
    # These are designed to be realistic and match expected LLM output
    TEMPLATES = {
        RiskLevel.HIGH: {
            "summary_templates": [
                "Токен выглядит очень рискованным: низкая ликвидность, "
                "маленький возраст, высокая концентрация держателей.",
                "Этот токен несёт высокие риски. Основные проблемы: "
                "недостаточная ликвидность и централизованное владение.",
                "Крайне рискованный токен. Множество красных флагов "
                "указывают на возможный скам.",
            ],
            "why_templates": [
                [
                    "Ликвидность ниже безопасного порога",
                    "Контракт создан недавно",
                    "Топ-10 держателей контролируют большую часть предложения",
                ],
                [
                    "Недостаточная ликвидность для безопасного выхода",
                    "Слишком новый проект без истории",
                    "Высокий риск dump от крупных держателей",
                ],
                [
                    "Низкий объём торгов",
                    "Нет подтверждённой команды",
                    "Централизованное распределение токенов",
                ],
            ],
            "recommendation": Recommendation.AVOID,
        },
        RiskLevel.MEDIUM: {
            "summary_templates": [
                "Есть ряд вопросов: умеренная ликвидность, "
                "средняя концентрация держателей. Требуется осторожность.",
                "Токен имеет смешанные показатели. Некоторые метрики "
                "вызывают вопросы, но критических рисков не обнаружено.",
                "Средний уровень риска. Токен не идеален, но и не "
                "выглядит откровенным скамом.",
            ],
            "why_templates": [
                [
                    "Ликвидность в среднем диапазоне",
                    "Токен относительно новый",
                    "Распределение держателей требует внимания",
                ],
                [
                    "Умеренный объём торгов",
                    "Проект ещё развивается",
                    "Есть пространство для улучшения метрик",
                ],
                [
                    "Средняя ликвидность",
                    "История проекта пока короткая",
                    "Социальные показатели средние",
                ],
            ],
            "recommendation": Recommendation.CAUTION,
        },
        RiskLevel.LOW: {
            "summary_templates": [
                "Структура токена выглядит стабильной. "
                "Хорошая ликвидность и распределение.",
                "Токен демонстрирует здоровые показатели. "
                "Достаточная ликвидность и децентрализованное владение.",
                "Относительно безопасный токен с хорошими метриками. "
                "Основные риски минимизированы.",
            ],
            "why_templates": [
                [
                    "Высокая ликвидность",
                    "Токен существует достаточно долго",
                    "Равномерное распределение между держателями",
                ],
                [
                    "Достаточный объём для безопасной торговли",
                    "Проверенная история проекта",
                    "Децентрализованное владение",
                ],
                [
                    "Стабильная ликвидность",
                    "Зрелый проект",
                    "Активное сообщество",
                ],
            ],
            "recommendation": Recommendation.OK,
        },
    }

    async def generate_analysis(
        self,
        token_data: TokenData,
        risk_level: RiskLevel,
    ) -> AnalysisResult:
        """
        Generate mock analysis based on risk level.

        Uses template responses to simulate LLM output.
        Selects template variation based on token address hash
        for deterministic but varied responses.

        Args:
            token_data: Token information (used for variation selection)
            risk_level: Pre-calculated risk level

        Returns:
            AnalysisResult matching exact Claude API format
        """
        template = self.TEMPLATES[risk_level]

        # Use token address to select variation (deterministic)
        variation_index = sum(ord(c) for c in token_data.address) % 3

        summary = template["summary_templates"][variation_index]
        why = template["why_templates"][variation_index]
        recommendation = template["recommendation"]

        # Customize summary with token name if available
        if token_data.name:
            summary = f"{token_data.name}: {summary}"

        return AnalysisResult(
            risk=risk_level,
            summary=summary,
            why=why,
            recommendation=recommendation,
        )
