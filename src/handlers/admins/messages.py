import asyncio
import os
import aiofiles
import logging

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, BufferedInputFile
from aiogram.exceptions import (
    TelegramBadRequest, TelegramForbiddenError,
    TelegramNotFound, TelegramRetryAfter
)

from config import ADMIN_ID, bot, db_connection
from src.keyboards.buttons import AdminPanel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("broadcast.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

msg_router = Router()

# 50k+ user: 30 parallel so'rov (Telegram limit ~30 msg/s)
semaphore = asyncio.Semaphore(30)

FAILED_USERS_FILE      = "failed_users.txt"
TEST_FAILED_COPY_FILE  = "test_failed_copy.txt"
TEST_FAILED_FORWARD_FILE = "test_failed_forward.txt"


class MsgState(StatesGroup):
    forward_msg      = State()
    send_msg         = State()
    test_copy_msg    = State()
    test_forward_msg = State()


markup = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]],
)


# ─── XATO LOGGA YOZISH ─────────────────────────────────────────────────

async def log_failed_user(error_message: str, filename: str):
    """Takrorlanmaydigan xatolarni faylga yozadi."""
    unique_errors: set = set()
    if os.path.exists(filename):
        async with aiofiles.open(filename, mode="r") as f:
            unique_errors = set((await f.read()).splitlines())
    if error_message not in unique_errors:
        async with aiofiles.open(filename, mode="a") as f:
            await f.write(f"{error_message}\n")


# ─── XAVFSIZ YUBORISH ──────────────────────────────────────────────────

async def send_copy_safe(
    user_id: int, message: Message,
    sem: asyncio.Semaphore,
    is_test: bool = False,
    test_filename: str = None,
) -> bool:
    async with sem:
        for attempt in range(5):
            try:
                sent = await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
                if is_test:
                    await bot.delete_message(chat_id=user_id, message_id=sent.message_id)
                await asyncio.sleep(0.034)   # ~30 msg/s
                return True

            except TelegramRetryAfter as e:
                wait = e.retry_after + 2 ** attempt
                logger.warning(f"RetryAfter {user_id}: {wait:.1f}s")
                await asyncio.sleep(wait)

            except (TelegramForbiddenError, TelegramNotFound) as e:
                await log_failed_user(str(e), test_filename or FAILED_USERS_FILE)
                return False

            except TelegramBadRequest as e:
                if "message to copy not found" in str(e).lower():
                    await log_failed_user(str(e), test_filename or FAILED_USERS_FILE)
                    return False
                if attempt < 4:
                    await asyncio.sleep(2 ** attempt)
                else:
                    await log_failed_user(str(e), test_filename or FAILED_USERS_FILE)
                    return False

            except Exception as e:
                if attempt < 4:
                    await asyncio.sleep(2 ** attempt)
                else:
                    await log_failed_user(str(e), test_filename or FAILED_USERS_FILE)
                    return False

        await log_failed_user("Max retries exceeded", test_filename or FAILED_USERS_FILE)
        return False


async def send_forward_safe(
    user_id: int, message: Message,
    sem: asyncio.Semaphore,
    is_test: bool = False,
    test_filename: str = None,
) -> bool:
    async with sem:
        for attempt in range(5):
            try:
                sent = await bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
                if is_test:
                    await bot.delete_message(chat_id=user_id, message_id=sent.message_id)
                await asyncio.sleep(0.034)
                return True

            except TelegramRetryAfter as e:
                wait = e.retry_after + 2 ** attempt
                logger.warning(f"RetryAfter {user_id}: {wait:.1f}s")
                await asyncio.sleep(wait)

            except (TelegramForbiddenError, TelegramNotFound) as e:
                await log_failed_user(str(e), test_filename or FAILED_USERS_FILE)
                return False

            except TelegramBadRequest as e:
                if attempt < 4:
                    await asyncio.sleep(2 ** attempt)
                else:
                    await log_failed_user(str(e), test_filename or FAILED_USERS_FILE)
                    return False

            except Exception as e:
                if attempt < 4:
                    await asyncio.sleep(2 ** attempt)
                else:
                    await log_failed_user(str(e), test_filename or FAILED_USERS_FILE)
                    return False

        await log_failed_user("Max retries exceeded", test_filename or FAILED_USERS_FILE)
        return False


# ─── BROADCAST ─────────────────────────────────────────────────────────

async def broadcast(
    user_ids: list,
    message: Message,
    send_func,
    is_test: bool = False,
    test_filename: str = None,
):
    total   = len(user_ids)
    success = 0
    failed  = 0

    filename = test_filename if is_test else FAILED_USERS_FILE
    if os.path.exists(filename):
        os.remove(filename)

    status_msg = await message.answer(
        f"📤 Yuborish boshlandi... Jami: {total} ta foydalanuvchi"
    )

    BATCH = 200          # Har bir batch hajmi
    UPDATE_EVERY = 1000  # Har necha userni statusni yangilaymiz

    for i in range(0, total, BATCH):
        batch = user_ids[i : i + BATCH]
        tasks = [
            send_func(uid, message, semaphore, is_test, test_filename)
            for uid in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if r is True:
                success += 1
            else:
                failed += 1

        processed = min(i + BATCH, total)
        if processed % UPDATE_EVERY == 0 or processed >= total:
            try:
                await status_msg.edit_text(
                    f"📬 {'Sinov' if is_test else 'Xabar'} yuborilmoqda...\n\n"
                    f"✅ Yuborilgan:    {success}\n"
                    f"❌ Yuborilmagan: {failed}\n"
                    f"📦 Jami:         {total}\n"
                    f"📊 Progres:      {processed}/{total}"
                )
            except Exception:
                pass

    await message.answer(
        f"✅ {'Sinov' if is_test else 'Xabar'} yuborish tugadi\n\n"
        f"📤 Yuborilgan:    {success}\n"
        f"❌ Yuborilmagan: {failed}",
        reply_markup=await AdminPanel.admin_msg(),
    )
    logger.info(f"Broadcast: {success} ok, {failed} fail, total {total}")

    if os.path.exists(filename):
        async with aiofiles.open(filename, "rb") as f:
            data = await f.read()
        file_obj = BufferedInputFile(data, filename)
        await message.answer_document(
            file_obj,
            caption=f"❌ Xatolar ro'yxati",
        )

    return success, failed


# ─── FOYDALANUVCHI ID LARI ─────────────────────────────────────────────

async def get_user_ids_paginated(batch_size: int = 5000) -> list:
    """
    Barcha user_id larni DB dan oladi.
    ✅ Global cursor o'rniga connection pool ishlatadi.
    """
    user_ids = []
    offset   = 0
    while True:
        with db_connection() as (conn, cur):
            cur.execute(
                "SELECT user_id FROM public.accounts LIMIT %s OFFSET %s",
                (batch_size, offset),
            )
            rows = cur.fetchall()

        if not rows:
            break
        user_ids.extend(row[0] for row in rows)
        offset += batch_size
        logger.info(f"Fetched {len(rows)} user IDs (offset={offset})")

    return user_ids


# ─── HANDLERLAR ────────────────────────────────────────────────────────

@msg_router.message(F.text == "✍Xabarlar", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def xabarlar_panel(message: Message):
    await message.answer("Xabarlar bo'limi!", reply_markup=await AdminPanel.admin_msg())


@msg_router.message(F.text == "📨Forward xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_forward(message: Message, state: FSMContext):
    await message.answer("Forward yuboriladigan xabarni yuboring:", reply_markup=markup)
    await state.set_state(MsgState.forward_msg)


@msg_router.message(MsgState.forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_forward_all(message: Message, state: FSMContext):
    await state.clear()
    user_ids = await get_user_ids_paginated()
    await broadcast(user_ids, message, send_forward_safe)


@msg_router.message(F.text == "📬Oddiy xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_copy(message: Message, state: FSMContext):
    await message.answer("Yuborilishi kerak bo'lgan xabarni yuboring:", reply_markup=markup)
    await state.set_state(MsgState.send_msg)


@msg_router.message(MsgState.send_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_copy_all(message: Message, state: FSMContext):
    await state.clear()
    user_ids = await get_user_ids_paginated()
    await broadcast(user_ids, message, send_copy_safe)


@msg_router.message(F.text == "🧪Sinov: Copy yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def test_copy_start(message: Message, state: FSMContext):
    await message.answer("🧪 Sinov (copy): xabarni yuboring, darhol o'chiriladi:")
    await state.set_state(MsgState.test_copy_msg)


@msg_router.message(MsgState.test_copy_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def test_copy_handle(message: Message, state: FSMContext):
    await state.clear()
    user_ids = await get_user_ids_paginated()
    await broadcast(user_ids, message, send_copy_safe, is_test=True, test_filename=TEST_FAILED_COPY_FILE)


@msg_router.message(F.text == "🧪Sinov: Forward yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def test_forward_start(message: Message, state: FSMContext):
    await message.answer("🧪 Sinov (forward): xabarni yuboring, darhol o'chiriladi:")
    await state.set_state(MsgState.test_forward_msg)


@msg_router.message(MsgState.test_forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def test_forward_handle(message: Message, state: FSMContext):
    await state.clear()
    user_ids = await get_user_ids_paginated()
    await broadcast(user_ids, message, send_forward_safe, is_test=True, test_filename=TEST_FAILED_FORWARD_FILE)


@msg_router.message(F.text == "🔙Orqaga qaytish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back_to_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Orqaga qaytildi", reply_markup=await AdminPanel.admin_msg())
