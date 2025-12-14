"""
Token analysis handler.

Handles messages containing Solana token addresses.
Main workflow:
1. Validate address format
2. Call orchestrator for analysis
3. Format and send result
"""

import logging

from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ChatAction

from bot.utils.validators import validate_solana_address
from bot.utils.formatters import format_analysis_result
from bot.templates.messages import INVALID_ADDRESS
from bot.services.orchestrator import AnalyzerOrchestrator

logger = logging.getLogger(__name__)

router = Router(name="token")


@router.message()
async def handle_message(
    message: Message,
    orchestrator: AnalyzerOrchestrator,
) -> None:
    """
    Handle any text message as potential token address.

    This is a catch-all handler for messages that don't match
    any commands. It tries to interpret the message as a
    Solana token address.

    Args:
        message: Incoming Telegram message
        orchestrator: Injected analyzer orchestrator
    """
    # Ignore non-text messages
    if not message.text:
        await message.answer(INVALID_ADDRESS)
        return

    # Extract and clean the address
    address = message.text.strip()

    # Validate Solana address format
    is_valid, error = validate_solana_address(address)

    if not is_valid:
        logger.debug(f"Invalid address: {error}")
        await message.answer(INVALID_ADDRESS)
        return

    # Show typing indicator while analyzing
    await message.bot.send_chat_action(
        chat_id=message.chat.id,
        action=ChatAction.TYPING,
    )

    # Perform analysis
    # Errors are caught by ErrorHandlerMiddleware
    result = await orchestrator.analyze(address)

    # Format and send result
    formatted = format_analysis_result(result)
    await message.answer(formatted)
