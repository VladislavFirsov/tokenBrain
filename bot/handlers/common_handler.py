"""
Common handlers for basic bot commands.

Handles:
- /start - Welcome message
- /help - Usage instructions
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.templates.messages import HELP, WELCOME

router = Router(name="common")


@router.message(Command("start"))
async def handle_start(message: Message) -> None:
    """
    Handle /start command.

    Sends welcome message with usage instructions.
    This is the first message users see when they start the bot.
    """
    await message.answer(WELCOME)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """
    Handle /help command.

    Sends detailed usage instructions and feature description.
    """
    await message.answer(HELP)
