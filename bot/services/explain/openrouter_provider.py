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
    TokenData,
)

logger = logging.getLogger(__name__)

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default timeout (SLA: 1.5 sec)
DEFAULT_TIMEOUT = 1.5

# System prompt - rules, format, restrictions
SYSTEM_PROMPT = """Ты — эксперт по анализу криптовалютных токенов.

ПРАВИЛА:
1. Отвечай СТРОГО в JSON формате
2. НЕ придумывай данные
3. Используй только предоставленную информацию
4. Пиши на русском языке
5. Будь кратким и понятным

ФОРМАТ ОТВЕТА (строго JSON):
{
  "risk": "high" | "medium" | "low",
  "summary": "краткое объяснение (1-2 предложения)",
  "why": ["причина 1", "причина 2", "причина 3"],
  "recommendation": "avoid" | "caution" | "ok"
}

ВАЖНО:
- risk должен совпадать с предоставленным уровнем риска
- why должен содержать 1-5 причин
- summary максимум 200 символов"""


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
        risk_level: RiskLevel,
    ) -> AnalysisResult:
        """
        Generate analysis using OpenRouter LLM.

        Args:
            token_data: Normalized token information
            risk_level: Pre-calculated risk level

        Returns:
            AnalysisResult with summary, reasons, and recommendation

        Raises:
            LLMError: If generation fails (after fallback attempt)
        """
        logger.info(
            f"Generating LLM analysis for {token_data.symbol}, "
            f"risk={risk_level.value}"
        )

        try:
            response = await asyncio.wait_for(
                self._call_api(token_data, risk_level),
                timeout=self._timeout,
            )
            return response

        except TimeoutError:
            logger.warning(f"OpenRouter timeout after {self._timeout}s, using fallback")
            return self._generate_fallback(token_data, risk_level)

        except LLMError as e:
            # Use fallback for LLM errors too (API errors, parse errors)
            logger.warning(f"LLM error: {e}, using fallback")
            return self._generate_fallback(token_data, risk_level)

        except Exception as e:
            logger.warning(f"OpenRouter error: {e}, using fallback")
            return self._generate_fallback(token_data, risk_level)

    async def _call_api(
        self,
        token_data: TokenData,
        risk_level: RiskLevel,
    ) -> AnalysisResult:
        """
        Make actual API call to OpenRouter.
        """
        # Build user prompt with token data
        user_prompt = self._build_user_prompt(token_data, risk_level)

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,  # Lower temperature for consistent output
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
        return self._parse_response(content, risk_level)

    def _build_user_prompt(
        self,
        token_data: TokenData,
        risk_level: RiskLevel,
    ) -> str:
        """
        Build user prompt with token data.
        """
        # Prepare token data summary
        data_summary = {
            "name": token_data.name or "Unknown",
            "symbol": token_data.symbol or "UNKNOWN",
            "age_days": token_data.age_days,
            "liquidity_usd": token_data.liquidity_usd,
            "holders": token_data.holders,
            "top10_holders_percent": token_data.top10_holders_percent,
        }

        # Add authority flags if available
        if token_data.mint_authority_exists is not None:
            data_summary["mint_authority_exists"] = token_data.mint_authority_exists

        if token_data.freeze_authority_exists is not None:
            data_summary["freeze_authority_exists"] = token_data.freeze_authority_exists

        if token_data.metadata_mutable is not None:
            data_summary["metadata_mutable"] = token_data.metadata_mutable

        # Add holder concentration if available
        if token_data.top1_holder_percent is not None:
            data_summary["top1_holder_percent"] = token_data.top1_holder_percent

        if token_data.top5_holders_percent is not None:
            data_summary["top5_holders_percent"] = token_data.top5_holders_percent

        # Add rugpull flags
        data_summary["rugpull_flags"] = {
            "new_contract": token_data.rugpull_flags.new_contract,
            "low_liquidity": token_data.rugpull_flags.low_liquidity,
            "centralized_holders": token_data.rugpull_flags.centralized_holders,
        }

        return f"""Проанализируй токен:

Данные: {json.dumps(data_summary, ensure_ascii=False, indent=2)}

Уровень риска (рассчитан системой): {risk_level.value}

Объясни почему токен имеет такой уровень риска. Ответь в JSON формате."""

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
        risk_level: RiskLevel,
    ) -> AnalysisResult:
        """
        Generate fallback response when LLM fails.

        Uses template-based response similar to mock provider.
        """
        logger.info("Using fallback template for analysis")

        # Build reasons from available data
        why = []

        if risk_level == RiskLevel.HIGH:
            if token_data.mint_authority_exists:
                why.append("Присутствует mint authority (можно создавать новые токены)")
            if token_data.freeze_authority_exists:
                why.append("Присутствует freeze authority (можно заморозить переводы)")
            if token_data.top1_holder_percent and token_data.top1_holder_percent > 50:
                why.append(
                    f"Один кошелёк контролирует {token_data.top1_holder_percent:.1f}% токенов"
                )
            if token_data.rugpull_flags.low_liquidity:
                why.append("Низкая ликвидность")
            if token_data.rugpull_flags.new_contract:
                why.append("Очень молодой контракт")
            if token_data.rugpull_flags.centralized_holders:
                why.append("Высокая концентрация у топ-держателей")

        elif risk_level == RiskLevel.MEDIUM:
            why.append("Некоторые показатели требуют внимания")
            if token_data.metadata_mutable:
                why.append("Метаданные токена могут быть изменены")
            if token_data.top5_holders_percent and token_data.top5_holders_percent > 40:
                why.append("Умеренная концентрация у крупных держателей")

        else:  # LOW
            why.append("Основные показатели в норме")
            if not token_data.mint_authority_exists:
                why.append("Mint authority отозван")
            if not token_data.freeze_authority_exists:
                why.append("Freeze authority отозван")

        # Ensure at least one reason
        if not why:
            why = ["Анализ на основе доступных данных"]

        # Build summary
        summaries = {
            RiskLevel.HIGH: f"{token_data.symbol or 'Токен'}: высокий риск. Обнаружены критические проблемы.",
            RiskLevel.MEDIUM: f"{token_data.symbol or 'Токен'}: средний риск. Есть вопросы, требующие внимания.",
            RiskLevel.LOW: f"{token_data.symbol or 'Токен'}: низкий риск. Основные показатели в норме.",
        }

        recommendations = {
            RiskLevel.HIGH: Recommendation.AVOID,
            RiskLevel.MEDIUM: Recommendation.CAUTION,
            RiskLevel.LOW: Recommendation.OK,
        }

        return AnalysisResult(
            risk=risk_level,
            summary=summaries[risk_level],
            why=why[:5],
            recommendation=recommendations[risk_level],
        )
