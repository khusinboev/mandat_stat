import asyncio
import os
import aiofiles
import logging
import time
from collections import defaultdict
from aiogram import Router, F, Bot
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, BufferedInputFile
from aiogram.exceptions import (
    TelegramBadRequest, TelegramForbiddenError, TelegramNotFound, TelegramRetryAfter
)
from config import ADMIN_ID, sql, bot
from src.keyboards.buttons import AdminPanel

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('broadcast.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

msg_router = Router()

# Semaphore to limit concurrent requests
MAX_BROADCAST_CONCURRENCY = int(os.getenv("MAX_BROADCAST_CONCURRENCY", "20"))
DEFAULT_BROADCAST_BATCH_SIZE = int(os.getenv("DEFAULT_BROADCAST_BATCH_SIZE", "100"))
DEFAULT_DB_PAGE_SIZE = int(os.getenv("DEFAULT_DB_PAGE_SIZE", "1000"))
PROGRESS_UPDATE_EVERY_USERS = int(os.getenv("PROGRESS_UPDATE_EVERY_USERS", "500"))
PROGRESS_UPDATE_MIN_SECONDS = float(os.getenv("PROGRESS_UPDATE_MIN_SECONDS", "2"))
semaphore = asyncio.Semaphore(MAX_BROADCAST_CONCURRENCY)

# Files for logging failed users
FAILED_USERS_FILE = "failed_users.txt"
TEST_FAILED_COPY_FILE = "test_failed_copy.txt"
TEST_FAILED_FORWARD_FILE = "test_failed_forward.txt"

# === STATES (FSM) === #
class MsgState(StatesGroup):
    forward_msg = State()
    send_msg = State()
    test_copy_msg = State()
    test_forward_msg = State()

# === BACK BUTTON === #
markup = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]]
)

# === LOGGER: Write unique error messages to file === #
async def log_failed_user(error_message: str, filename: str):
    # Read existing errors to avoid duplicates
    unique_errors = set()
    if os.path.exists(filename):
        async with aiofiles.open(filename, mode="r") as f:
            content = await f.read()
            unique_errors.update(content.splitlines())

    # Add new error if not already present
    if error_message not in unique_errors:
        unique_errors.add(error_message)
        async with aiofiles.open(filename, mode="a") as f:
            await f.write(f"{error_message}\n")
        logger.info(f"Logged unique error to {filename}: {error_message}")

# === SAFE SEND FUNCTIONS === #
async def send_copy_safe(user_id: int, message: Message, semaphore: asyncio.Semaphore, is_test: bool = False, test_filename: str = None):
    async with semaphore:
        for attempt in range(5):
            try:
                sent_msg = await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                if is_test:
                    await bot.delete_message(chat_id=user_id, message_id=sent_msg.message_id)
                logger.info(f"Successfully sent copy to user {user_id}")
                await asyncio.sleep(0.2)  # Minimum delay for copy
                return True, "ok"
            except TelegramRetryAfter as e:
                logger.warning(f"RetryAfter for user {user_id}: waiting {e.retry_after}s")
                await asyncio.sleep(e.retry_after + (2 ** attempt))
            except TelegramForbiddenError as e:
                logger.error(f"User {user_id} blocked: {str(e)}")
                await log_failed_user(str(e), test_filename if is_test else FAILED_USERS_FILE)
                await asyncio.sleep(0.2)
                return False, "forbidden"
            except TelegramNotFound as e:
                logger.error(f"User {user_id} not found: {str(e)}")
                await log_failed_user(str(e), test_filename if is_test else FAILED_USERS_FILE)
                await asyncio.sleep(0.2)
                return False, "not_found"
            except TelegramBadRequest as e:
                if "message to copy not found" in str(e).lower():
                    logger.error(f"Message to copy not found for user {user_id}: {str(e)}")
                    await log_failed_user(str(e), test_filename if is_test else FAILED_USERS_FILE)
                    await asyncio.sleep(0.2)
                    return False, "bad_request"
                if attempt < 4:
                    logger.warning(f"BadRequest for user {user_id}, attempt {attempt + 1}: {str(e)}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(f"Failed to send copy to user {user_id}: {str(e)}")
                    await log_failed_user(str(e), test_filename if is_test else FAILED_USERS_FILE)
                    await asyncio.sleep(0.2)
                    return False, "bad_request"
            except Exception as e:
                logger.error(f"Unexpected error sending copy to {user_id} (attempt {attempt + 1}): {str(e)}")
                if attempt < 4:
                    await asyncio.sleep(2 ** attempt)
                else:
                    await log_failed_user(str(e), test_filename if is_test else FAILED_USERS_FILE)
                    await asyncio.sleep(0.2)
                    return False, "unknown"
        logger.error(f"Failed to send copy to user {user_id} after 5 attempts")
        await log_failed_user("Max retries exceeded", test_filename if is_test else FAILED_USERS_FILE)
        await asyncio.sleep(0.2)
        return False, "retries_exceeded"

async def send_forward_safe(user_id: int, message: Message, semaphore: asyncio.Semaphore, is_test: bool = False, test_filename: str = None):
    async with semaphore:
        for attempt in range(5):
            try:
                sent_msg = await bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                if is_test:
                    await bot.delete_message(chat_id=user_id, message_id=sent_msg.message_id)
                logger.info(f"Successfully sent forward to user {user_id}")
                await asyncio.sleep(0.5)  # Minimum delay for forward
                return True, "ok"
            except TelegramRetryAfter as e:
                logger.warning(f"RetryAfter for user {user_id}: waiting {e.retry_after}s")
                await asyncio.sleep(e.retry_after + (2 ** attempt))
            except TelegramForbiddenError as e:
                logger.error(f"User {user_id} blocked: {str(e)}")
                await log_failed_user(str(e), test_filename if is_test else FAILED_USERS_FILE)
                await asyncio.sleep(0.5)
                return False, "forbidden"
            except TelegramNotFound as e:
                logger.error(f"User {user_id} not found: {str(e)}")
                await log_failed_user(str(e), test_filename if is_test else FAILED_USERS_FILE)
                await asyncio.sleep(0.5)
                return False, "not_found"
            except TelegramBadRequest as e:
                if attempt < 4:
                    logger.warning(f"BadRequest for user {user_id}, attempt {attempt + 1}: {str(e)}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(f"Failed to send forward to user {user_id}: {str(e)}")
                    await log_failed_user(str(e), test_filename if is_test else FAILED_USERS_FILE)
                    await asyncio.sleep(0.5)
                    return False, "bad_request"
            except Exception as e:
                logger.error(f"Unexpected error sending forward to {user_id} (attempt {attempt + 1}): {str(e)}")
                if attempt < 4:
                    await asyncio.sleep(2 ** attempt)
                else:
                    await log_failed_user(str(e), test_filename if is_test else FAILED_USERS_FILE)
                    await asyncio.sleep(0.5)
                    return False, "unknown"
        logger.error(f"Failed to send forward to user {user_id} after 5 attempts")
        await log_failed_user("Max retries exceeded", test_filename if is_test else FAILED_USERS_FILE)
        await asyncio.sleep(0.5)
        return False, "retries_exceeded"


def format_eta(seconds: float) -> str:
    if seconds <= 0:
        return "0s"
    mins, sec = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs}h {mins}m {sec}s"
    if mins:
        return f"{mins}m {sec}s"
    return f"{sec}s"


def build_progress_text(is_test: bool, success: int, failed: int, total: int, processed: int, started_at: float) -> str:
    elapsed = max(time.perf_counter() - started_at, 0.001)
    speed = processed / elapsed
    remaining = max(total - processed, 0)
    eta = remaining / speed if speed > 0 else 0
    return (
        f"📬 {'Sinov' if is_test else 'Xabar'} yuborilmoqda...\n\n"
        f"✅ Yuborilgan: {success} ta\n"
        f"❌ Yuborilmagan: {failed} ta\n"
        f"📦 Jami: {total} ta\n"
        f"📊 Progres: {processed}/{total}\n"
        f"⚡ Tezlik: {speed:.2f} user/s\n"
        f"⏳ ETA: {format_eta(eta)}"
    )

# === BROADCAST FUNCTION === #
async def broadcast(
    user_ids: list[int],
    message: Message,
    send_func,
    is_test: bool = False,
    test_filename: str = None,
    send_summary: bool = True,
    reset_failed_log: bool = True,
    show_status: bool = True,
):
    total = len(user_ids)
    success = 0
    failed = 0
    reasons = defaultdict(int)
    status_msg = await message.answer("📤 Yuborish boshlandi...") if show_status else None
    batch_size = DEFAULT_BROADCAST_BATCH_SIZE
    started_at = time.perf_counter()
    processed = 0
    last_update_at = started_at

    # Clear the log file at the start if it exists
    filename = test_filename if is_test else FAILED_USERS_FILE
    if reset_failed_log and os.path.exists(filename):
        os.remove(filename)
        logger.info(f"Cleared log file: {filename}")

    for i in range(0, total, batch_size):
        batch = user_ids[i:i + batch_size]
        tasks = [send_func(uid, message, semaphore, is_test, test_filename) for uid in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                failed += 1
                reasons["gather_exception"] += 1
            elif isinstance(result, tuple) and len(result) == 2 and result[0] is True:
                success += 1
            else:
                failed += 1
                reason = result[1] if isinstance(result, tuple) and len(result) > 1 else "unknown"
                reasons[reason] += 1
        processed += len(batch)

        # Update progress
        now = time.perf_counter()
        should_update = (
            status_msg
            and (
                processed >= total
                or (processed % PROGRESS_UPDATE_EVERY_USERS == 0)
                or (now - last_update_at) >= PROGRESS_UPDATE_MIN_SECONDS
            )
        )
        if should_update:
            try:
                await status_msg.edit_text(build_progress_text(is_test, success, failed, total, processed, started_at))
                last_update_at = now
            except Exception as e:
                logger.error(f"Failed to update status message: {str(e)}")

        # Sleep between batches (optional, as per-user delays are handled in send functions)
        await asyncio.sleep(0.1)
        logger.info(f"Processed batch {i//batch_size + 1}/{total//batch_size + 1}")

    if send_summary:
        reason_text = "\n".join([f"- {k}: {v}" for k, v in sorted(reasons.items())]) if reasons else "- no-failures"
        await message.answer(
            f"✅ {'Sinov' if is_test else 'Xabar'} yuborildi\n\n"
            f"📤 Yuborilgan: {success} ta\n"
            f"❌ Yuborilmagan: {failed} ta\n\n"
            f"📉 Xatolik turlari:\n{reason_text}",
            reply_markup=await AdminPanel.admin_msg()
        )
        logger.info(f"Broadcast completed: {success} successful, {failed} failed, total: {total}")

        if os.path.exists(filename):
            async with aiofiles.open(filename, "rb") as f:
                data = await f.read()
                file = BufferedInputFile(data, filename)
                await message.answer_document(
                    file,
                    caption=f"❌ {'Sinov' if is_test else 'Xabar'} yuborishda yuzaga kelgan xatolar"
                )
                logger.info(f"Sent failed errors file: {filename}")

    return success, failed, dict(reasons)

# === DATABASE PAGINATION (KEYSET) === #
async def iter_user_id_batches(batch_size: int = DEFAULT_DB_PAGE_SIZE):
    last_id = 0
    while True:
        sql.execute(
            "SELECT id, user_id FROM public.accounts WHERE id > %s ORDER BY id ASC LIMIT %s",
            (last_id, batch_size),
        )
        rows = sql.fetchall()
        if not rows:
            break
        last_id = rows[-1][0]
        yield [row[1] for row in rows]


async def broadcast_all_users(message: Message, send_func, is_test: bool = False, test_filename: str = None):
    sql.execute("SELECT COUNT(*) FROM public.accounts")
    total = sql.fetchone()[0]
    processed = 0
    success_total = 0
    failed_total = 0
    reason_totals = defaultdict(int)
    started_at = time.perf_counter()
    status_msg = await message.answer("📤 Yuborish boshlandi...")

    reset_failed_log = True
    filename = test_filename if is_test else FAILED_USERS_FILE

    async for user_ids in iter_user_id_batches():
        success, failed, reasons = await broadcast(
            user_ids,
            message,
            send_func,
            is_test=is_test,
            test_filename=test_filename,
            send_summary=False,
            reset_failed_log=reset_failed_log,
            show_status=False,
        )
        reset_failed_log = False
        success_total += success
        failed_total += failed
        for key, value in reasons.items():
            reason_totals[key] += value
        processed += len(user_ids)
        try:
            await status_msg.edit_text(build_progress_text(is_test, success_total, failed_total, total, processed, started_at))
        except Exception as e:
            logger.error(f"Failed to update global status message: {str(e)}")

    reason_text = "\n".join([f"- {k}: {v}" for k, v in sorted(reason_totals.items())]) if reason_totals else "- no-failures"
    await message.answer(
        f"✅ {'Sinov' if is_test else 'Xabar'} yuborildi\n\n"
        f"📤 Yuborilgan: {success_total} ta\n"
        f"❌ Yuborilmagan: {failed_total} ta\n\n"
        f"📉 Xatolik turlari:\n{reason_text}",
        reply_markup=await AdminPanel.admin_msg()
    )

    if os.path.exists(filename):
        async with aiofiles.open(filename, "rb") as f:
            data = await f.read()
            file = BufferedInputFile(data, filename)
            await message.answer_document(
                file,
                caption=f"❌ {'Sinov' if is_test else 'Xabar'} yuborishda yuzaga kelgan xatolar"
            )

    return success_total, failed_total

# === HANDLERS === #
@msg_router.message(F.text == "✍Xabarlar", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def panel_handler(message: Message) -> None:
    await message.answer("Xabarlar bo'limi!", reply_markup=await AdminPanel.admin_msg())
    logger.info(f"Admin {message.from_user.id} accessed messages panel")

@msg_router.message(F.text == "📨Forward xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_forward(message: Message, state: FSMContext):
    await message.answer("Forward yuboriladigan xabarni yuboring", reply_markup=markup)
    await state.set_state(MsgState.forward_msg)
    logger.info(f"Admin {message.from_user.id} started forward message")

@msg_router.message(MsgState.forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_forward_to_all(message: Message, state: FSMContext):
    await state.clear()
    await broadcast_all_users(message, send_forward_safe)
    logger.info(f"Admin {message.from_user.id} completed forward broadcast")

@msg_router.message(F.text == "📬Oddiy xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_text_send(message: Message, state: FSMContext):
    await message.answer("Yuborilishi kerak bo'lgan xabarni yuboring", reply_markup=markup)
    await state.set_state(MsgState.send_msg)
    logger.info(f"Admin {message.from_user.id} started copy message")

@msg_router.message(MsgState.send_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_text_to_all(message: Message, state: FSMContext):
    await state.clear()
    await broadcast_all_users(message, send_copy_safe)
    logger.info(f"Admin {message.from_user.id} completed copy broadcast")

@msg_router.message(F.text == "🧪Sinov: Copy yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def test_copy_broadcast(message: Message, state: FSMContext):
    await message.answer("🧪 Sinov: Oddiy xabarni yuboring (copy), yuboriladi va darhol o‘chiriladi:")
    await state.set_state(MsgState.test_copy_msg)
    logger.info(f"Admin {message.from_user.id} started test copy broadcast")

@msg_router.message(MsgState.test_copy_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def handle_test_copy(message: Message, state: FSMContext):
    await state.clear()
    await broadcast_all_users(message, send_copy_safe, is_test=True, test_filename=TEST_FAILED_COPY_FILE)
    logger.info(f"Admin {message.from_user.id} completed test copy broadcast")

@msg_router.message(F.text == "🧪Sinov: Forward yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def test_forward_broadcast(message: Message, state: FSMContext):
    await message.answer("🧪 Sinov: Forward xabar yuboring, darhol o‘chiriladi:")
    await state.set_state(MsgState.test_forward_msg)
    logger.info(f"Admin {message.from_user.id} started test forward broadcast")

@msg_router.message(MsgState.test_forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def handle_test_forward(message: Message, state: FSMContext):
    await state.clear()
    await broadcast_all_users(message, send_forward_safe, is_test=True, test_filename=TEST_FAILED_FORWARD_FILE)
    logger.info(f"Admin {message.from_user.id} completed test forward broadcast")

@msg_router.message(F.text == "🔙Orqaga qaytish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Orqaga qaytildi", reply_markup=await AdminPanel.admin_msg())
    logger.info(f"Admin {message.from_user.id} returned to menu")