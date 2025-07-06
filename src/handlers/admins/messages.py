import asyncio
import time
from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramForbiddenError, TelegramNotFound

from config import ADMIN_ID, sql, bot
from src.keyboards.buttons import AdminPanel

import aiofiles
import os

msg_router = Router()
semaphore = asyncio.Semaphore(100)

# Xatoliklarni faylga yozish uchun log fayl nomini aniqlaymiz
timestamp = time.strftime("%Y%m%d_%H%M%S")
ERROR_LOG_FILE = f"errors_{timestamp}.txt"

# === Xatoliklarni faylga yozish === #
async def log_error(user_id, error_msg):
    async with aiofiles.open(ERROR_LOG_FILE, mode='a') as f:
        await f.write(f"user_id: {user_id}, error: {error_msg}\n")


# --- COPY xavfsiz --- #
async def send_copy_safe(user_id: int, message: Message, retries=3) -> int:
    for attempt in range(retries):
        try:
            async with semaphore:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                return 1
        except (TelegramForbiddenError, TelegramNotFound, TelegramBadRequest, TelegramAPIError) as e:
            await log_error(user_id, f"{type(e).__name__}: {e}")
            return 0
        except Exception as e:
            await log_error(user_id, f"OtherError(attempt {attempt+1}): {e}")
            await asyncio.sleep(1)
    return 0


# --- FORWARD xavfsiz --- #
async def send_forward_safe(user_id: int, message: Message, retries=3) -> int:
    for attempt in range(retries):
        try:
            async with semaphore:
                await bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                return 1
        except (TelegramForbiddenError, TelegramNotFound, TelegramBadRequest, TelegramAPIError) as e:
            await log_error(user_id, f"{type(e).__name__}: {e}")
            return 0
        except Exception as e:
            await log_error(user_id, f"OtherError(attempt {attempt+1}): {e}")
            await asyncio.sleep(1)
    return 0


# --- Broadcast tugagach log yuborish --- #
async def send_log_file_if_exists(chat_id: int):
    if os.path.exists(ERROR_LOG_FILE):
        async with aiofiles.open(ERROR_LOG_FILE, "rb") as f:
            await bot.send_document(chat_id=chat_id, document=(ERROR_LOG_FILE, await f.read()))
        os.remove(ERROR_LOG_FILE)


# --- Oddiy xabar broadcast --- #
async def broadcast_copy(user_ids: list[int], message: Message) -> tuple[int, int]:
    success, failed = 0, 0
    status_msg = await message.answer("📤 Yuborish boshlandi...")

    for i, user_id in enumerate(user_ids, 1):
        result = await send_copy_safe(user_id, message)
        success += result
        failed += not result

        if i % 100 == 0 or i == len(user_ids):
            try:
                await status_msg.edit_text(
                    f"📬 Oddiy xabar yuborilmoqda...\n\n"
                    f"✅ Yuborilgan: {success} ta\n"
                    f"❌ Yuborilmagan: {failed} ta\n"
                    f"📦 Jami: {len(user_ids)} ta\n"
                    f"📊 Progres: {i}/{len(user_ids)}"
                )
            except Exception:
                pass

    await send_log_file_if_exists(message.chat.id)
    return success, failed


# --- Forward xabar broadcast --- #
async def broadcast_forward(user_ids: list[int], message: Message) -> tuple[int, int]:
    success, failed = 0, 0
    status_msg = await message.answer("📨 Forward yuborish boshlandi...")

    for i, user_id in enumerate(user_ids, 1):
        result = await send_forward_safe(user_id, message)
        success += result
        failed += not result

        if i % 100 == 0 or i == len(user_ids):
            try:
                await status_msg.edit_text(
                    f"📨 Forward yuborilmoqda...\n\n"
                    f"✅ Yuborilgan: {success} ta\n"
                    f"❌ Yuborilmagan: {failed} ta\n"
                    f"📦 Jami: {len(user_ids)} ta\n"
                    f"📊 Progres: {i}/{len(user_ids)}"
                )
            except Exception:
                pass

    await send_log_file_if_exists(message.chat.id)
    return success, failed