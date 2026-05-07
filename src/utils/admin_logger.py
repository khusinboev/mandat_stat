"""Admin error logging utility - sends detailed errors only to admins."""

import traceback
from typing import Optional, Dict, Any
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError
from config import ADMIN_ID


async def send_error_to_admin(
    bot: Bot,
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    handler_name: str = "Unknown",
):
    """
    Send detailed error information to admin(s).
    
    Args:
        bot: Aiogram Bot instance
        error: Exception object
        context: Optional dictionary with additional context (region_name, un_id, etc.)
        handler_name: Name of the handler where error occurred
    """
    try:
        if isinstance(error, (TelegramForbiddenError, TelegramNetworkError)):
            return

        # Build error message
        error_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        
        context_str = ""
        if context:
            context_str = "\n\n<b>Context:</b>\n"
            for key, value in context.items():
                context_str += f"• {key}: <code>{value}</code>\n"
        
        admin_message = (
            f"<b>🚨 Error in Handler: {handler_name}</b>\n\n"
            f"<b>Error Type:</b> <code>{type(error).__name__}</code>\n"
            f"<b>Error Message:</b> <code>{str(error)}</code>\n"
            f"{context_str}"
            f"\n<b>Traceback:</b>\n<code>{error_trace[-1500:]}</code>"  # Last 1500 chars
        )
        
        # Send to all admins
        for admin_id in ADMIN_ID:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode="html"
                )
            except Exception as send_error:
                print(f"Failed to send error to admin {admin_id}: {send_error}")
    except Exception as logging_error:
        print(f"Error in admin_logger.send_error_to_admin: {logging_error}")


async def send_info_to_admin(
    bot: Bot,
    title: str,
    message: str,
    info: Optional[Dict[str, Any]] = None,
):
    """
    Send informational message to admin(s).
    
    Args:
        bot: Aiogram Bot instance
        title: Title/subject of the message
        message: Main message content
        info: Optional dictionary with additional info
    """
    try:
        info_str = ""
        if info:
            info_str = "\n\n<b>Info:</b>\n"
            for key, value in info.items():
                info_str += f"• {key}: <code>{value}</code>\n"
        
        admin_message = (
            f"<b>ℹ️ {title}</b>\n\n"
            f"{message}"
            f"{info_str}"
        )
        
        # Send to all admins
        for admin_id in ADMIN_ID:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode="html"
                )
            except Exception as send_error:
                print(f"Failed to send info to admin {admin_id}: {send_error}")
    except Exception as logging_error:
        print(f"Error in admin_logger.send_info_to_admin: {logging_error}")
