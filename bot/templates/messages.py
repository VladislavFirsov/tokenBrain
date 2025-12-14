"""
Message templates for Telegram bot.

All user-facing messages are defined here for easy localization
and consistent messaging. Uses HTML formatting for Telegram.

Template naming convention:
- WELCOME, HELP - informational messages
- ERROR_* - error messages
- INVALID_* - validation error messages
"""

# =============================================================================
# Informational Messages
# =============================================================================

WELCOME = """
Привет! Я <b>TokenBrain</b>

Отправь мне адрес Solana токена, и я проанализирую его за 3 секунды.

Просто вставь адрес токена в чат.

<i>Пример:</i>
<code>EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v</code>
""".strip()

HELP = """
<b>Как пользоваться TokenBrain:</b>

1. Скопируй адрес Solana токена
2. Отправь его мне
3. Получи анализ риска

<b>Что я анализирую:</b>
• Ликвидность токена
• Возраст контракта
• Распределение держателей
• Социальные показатели

<b>Уровни риска:</b>
• HIGH - высокий риск, лучше избегать
• MEDIUM - средний риск, будь осторожен
• LOW - низкий риск, относительно безопасно

<i>Отказ от ответственности: TokenBrain не даёт финансовых советов.
Всегда проводи собственное исследование перед инвестициями.</i>
""".strip()

ANALYZING = """
Анализирую токен...
""".strip()

# =============================================================================
# Validation Error Messages
# =============================================================================

INVALID_ADDRESS = """
Это не похоже на адрес Solana токена.

Пожалуйста, отправь корректный адрес.
<i>Пример:</i> <code>EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v</code>
""".strip()

WRONG_CHAIN = """
Этот токен не в сети Solana.

Пока TokenBrain анализирует только Solana-токены.
Ethereum и другие сети — скоро
""".strip()

# =============================================================================
# Error Messages
# =============================================================================

ERROR_GENERIC = """
Произошла ошибка. Попробуй позже.
""".strip()

ERROR_TRY_LATER = """
Не удалось получить данные о токене.

Попробуй через несколько минут.
""".strip()

ERROR_SERVICE_UNAVAILABLE = """
Сервис анализа временно недоступен.

Мы работаем над решением проблемы.
Попробуй позже.
""".strip()
