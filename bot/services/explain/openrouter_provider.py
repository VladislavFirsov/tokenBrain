"""
OpenRouter LLM provider.

Calls OpenRouter API to get Claude-based analysis of token risk.
This is the real implementation used in production.

Responsibilities:
1. Format prompt with token data and risk level
2. Call OpenRouter API
3. Parse and validate JSON response
4. Fallback to safe template on error

NO risk calculation (that's RiskService's job).
"""

import asyncio
import json
import logging

import aiohttp

from bot.core.exceptions import LLMError
from bot.core.models import (
    AnalysisResult,
    Recommendation,
    RiskLevel,
    RiskResult,
    TokenData,
)

logger = logging.getLogger(__name__)

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default timeout (SLA: 1.5 sec)
DEFAULT_TIMEOUT = 1.5

# System prompt - Anti-Hallucination Contract
SYSTEM_PROMPT = """Ты — аналитик рисков криптовалютных токенов.

ANTI-HALLUCINATION CONTRACT:
1. Используй ТОЛЬКО переданные данные и factors[]
2. НЕ добавляй НОВЫЕ причины — используй ТОЛЬКО factors[]
3. Если значение = null — считай неизвестным и укажи это
4. НЕ делай предположений о данных, которых нет
5. Risk level УЖЕ рассчитан системой — НЕ меняй его
6. Ответ СТРОГО в JSON формате

ФОРМАТ ОТВЕТА:
{
  "risk": "high" | "medium" | "low",
  "summary": "краткое объяснение на основе factors (1-2 предложения)",
  "why": ["причина из factors 1", "причина из factors 2", ...],
  "recommendation": "avoid" | "caution" | "ok"
}

ПРАВИЛА:
- risk ДОЛЖЕН совпадать с предоставленным уровнем
- why берётся ТОЛЬКО из переданного factors[] (переформулируй если нужно)
- Если данных недостаточно — объясни это в summary
- summary максимум 200 символов
- Пиши на русском языке, будь кратким"""


class OpenRouterLLMProvider:
    """
    Real LLM provider using OpenRouter API.

    Sends token data to Claude via OpenRouter and parses response.
    Has mandatory fallback on error/timeout.

    Timeout: 1.5 seconds (Telegram UX requirement)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-3.5-sonnet",
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            model: Model to use (default: claude-3.5-sonnet)
            timeout: Request timeout in seconds (default 1.5s)
        """
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate_analysis(
        self,
        token_data: TokenData,
        risk_result: RiskResult,
    ) -> AnalysisResult:
        """
        Generate analysis using OpenRouter LLM.

        Anti-Hallucination Contract:
        - LLM receives risk_result.factors[] and must use ONLY these
        - LLM must not change the risk level

        Args:
            token_data: Normalized token information
            risk_result: Pre-calculated risk with factors and completeness scores

        Returns:
            AnalysisResult with summary, reasons, and recommendation

        Raises:
            LLMError: If generation fails (after fallback attempt)
        """
        logger.info(
            f"Generating LLM analysis for {token_data.symbol}, "
            f"risk={risk_result.level.value}, "
            f"factors={len(risk_result.factors)}"
        )

        try:
            response = await asyncio.wait_for(
                self._call_api(token_data, risk_result),
                timeout=self._timeout,
            )
            return response

        except TimeoutError:
            logger.warning(f"OpenRouter timeout after {self._timeout}s, using fallback")
            return self._generate_fallback(token_data, risk_result)

        except LLMError as e:
            # Use fallback for LLM errors too (API errors, parse errors)
            logger.warning(f"LLM error: {e}, using fallback")
            return self._generate_fallback(token_data, risk_result)

        except Exception as e:
            logger.warning(f"OpenRouter error: {e}, using fallback")
            return self._generate_fallback(token_data, risk_result)

    async def _call_api(
        self,
        token_data: TokenData,
        risk_result: RiskResult,
    ) -> AnalysisResult:
        """
        Make actual API call to OpenRouter.
        """
        # Build user prompt with token data and factors (Anti-Hallucination)
        user_prompt = self._build_user_prompt(token_data, risk_result)

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,  # Lower temperature for consistent output
            "max_tokens": 500,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        timeout = aiohttp.ClientTimeout(total=self._timeout)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                OPENROUTER_API_URL,
                json=payload,
                headers=headers,
                timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"OpenRouter API error {resp.status}: {error_text}")
                    raise LLMError(
                        message="Сервис анализа временно недоступен.",
                        technical_message=f"OpenRouter {resp.status}: {error_text}",
                    )

                data = await resp.json()

        # Extract content from response
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error(f"Invalid OpenRouter response structure: {e}")
            raise LLMError(
                message="Ошибка формата ответа.",
                technical_message=f"Invalid response: {e}",
            ) from e

        # Parse and validate JSON response
        return self._parse_response(content, risk_result.level)

    def _build_user_prompt(
        self,
        token_data: TokenData,
        risk_result: RiskResult,
    ) -> str:
        """
        Build user prompt with token data and factors (Anti-Hallucination Contract).

        LLM receives:
        - risk_signals: raw data (with null for unknown)
        - factors: pre-calculated reasons (LLM must use ONLY these)
        - completeness scores: data quality indicators
        """
        # Build structured data for LLM (Anti-Hallucination)
        prompt_data = {
            "token": {
                "name": token_data.name or "Unknown",
                "symbol": token_data.symbol or "UNKNOWN",
            },
            "risk_level": risk_result.level.value,
            "safety_completeness": f"{risk_result.safety_completeness:.0%}",
            "context_completeness": f"{risk_result.context_completeness:.0%}",
            "risk_signals": risk_result.risk_signals,
            "factors": risk_result.factors,
        }

        return f"""Проанализируй токен.

ДАННЫЕ (Anti-Hallucination Contract):
{json.dumps(prompt_data, ensure_ascii=False, indent=2)}

ВАЖНО:
- Уровень риска УЖЕ рассчитан: {risk_result.level.value}
- Используй ТОЛЬКО factors[] для поля "why"
- НЕ добавляй новые причины
- null в risk_signals = данные неизвестны

Ответь в JSON формате."""

    def _parse_response(
        self,
        content: str,
        expected_risk: RiskLevel,
    ) -> AnalysisResult:
        """
        Parse and validate LLM response.
        """
        # Try to extract JSON from response
        try:
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON: {e}")
            logger.debug(f"Raw content: {content}")
            raise LLMError(
                message="Ошибка формата ответа.",
                technical_message=f"JSON parse error: {e}",
            ) from e

        # Validate and extract fields
        try:
            # Risk level
            risk_str = data.get("risk", expected_risk.value).lower()
            try:
                risk = RiskLevel(risk_str)
            except ValueError:
                risk = expected_risk

            # Summary
            summary = str(data.get("summary", "Анализ недоступен."))[:500]

            # Why (reasons)
            why_raw = data.get("why", [])
            if isinstance(why_raw, list):
                why = [str(r)[:200] for r in why_raw[:5]]
            else:
                why = [str(why_raw)[:200]]

            if not why:
                why = ["Причины не указаны"]

            # Recommendation
            rec_str = data.get("recommendation", "caution").lower()
            try:
                recommendation = Recommendation(rec_str)
            except ValueError:
                # Map risk to recommendation as fallback
                recommendation = {
                    RiskLevel.HIGH: Recommendation.AVOID,
                    RiskLevel.MEDIUM: Recommendation.CAUTION,
                    RiskLevel.LOW: Recommendation.OK,
                }.get(risk, Recommendation.CAUTION)

            return AnalysisResult(
                risk=risk,
                summary=summary,
                why=why,
                recommendation=recommendation,
            )

        except Exception as e:
            logger.error(f"Failed to validate LLM response: {e}")
            raise LLMError(
                message="Ошибка формата ответа.",
                technical_message=f"Validation error: {e}",
            ) from e

    def _generate_fallback(
        self,
        token_data: TokenData,
        risk_result: RiskResult,
    ) -> AnalysisResult:
        """
        Generate fallback response when LLM fails.

        Uses factors from risk_result (Anti-Hallucination Contract).
        """
        logger.info("Using fallback template for analysis")

        risk_level = risk_result.level

        # Use pre-calculated factors (Anti-Hallucination)
        why = risk_result.factors[:5] if risk_result.factors else []

        # Ensure at least one reason
        if not why:
            if risk_level == RiskLevel.HIGH:
                why = ["Обнаружены критические проблемы"]
            elif risk_level == RiskLevel.MEDIUM:
                why = ["Недостаточно данных для полного анализа"]
            else:
                why = ["Основные показатели в норме"]

        # Build summary based on completeness
        symbol = token_data.symbol or "Токен"
        if risk_result.safety_completeness < 1.0:
            completeness_note = " Часть данных недоступна."
        else:
            completeness_note = ""

        summaries = {
            RiskLevel.HIGH: f"{symbol}: высокий риск.{completeness_note}",
            RiskLevel.MEDIUM: f"{symbol}: средний риск.{completeness_note}",
            RiskLevel.LOW: f"{symbol}: низкий риск.{completeness_note}",
        }

        recommendations = {
            RiskLevel.HIGH: Recommendation.AVOID,
            RiskLevel.MEDIUM: Recommendation.CAUTION,
            RiskLevel.LOW: Recommendation.OK,
        }

        return AnalysisResult(
            risk=risk_level,
            summary=summaries[risk_level],
            why=why,
            recommendation=recommendations[risk_level],
        )
