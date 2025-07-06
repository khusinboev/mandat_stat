import asyncio
import aiofiles
from aiogram import Router, F, Bot
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramForbiddenError, TelegramNotFound

from config import ADMIN_ID, sql, bot
from src.keyboards.buttons import AdminPanel

msg_router = Router()

FAILED_USERS_FILE = "failed_users.txt"
semaphore = asyncio.Semaphore(100)  # 100 ta parallel yuborishga ruxsat


# === HOLAT (FSM) === #
class MsgState(StatesGroup):
    forward_msg = State()
    send_msg = State()
    test_copy_msg = State()
    test_forward_msg = State()


# === QAYTISH TUGMASI === #
markup = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]]
)


# === ADMIN PANEL === #
@msg_router.message(F.text == "✍Xabarlar", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def panel_handler(message: Message) -> None:
    await message.answer("Xabarlar bo'limi!", reply_markup=await AdminPanel.admin_msg())


# === FORWARD XABAR BOSHLASH === #
@msg_router.message(F.text == "📨Forward xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_forward(message: Message, state: FSMContext):
    await message.answer("Forward yuboriladigan xabarni yuboring", reply_markup=markup)
    await state.set_state(MsgState.forward_msg)


# === FORWARD YUBORISH === #
@msg_router.message(MsgState.forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_forward_to_all(message: Message, state: FSMContext):
    await state.clear()
    sql.execute("SELECT user_id FROM public.accounts")
    rows = sql.fetchall()
    user_ids = [row[0] for row in rows]

    success, failed = await broadcast_forward(user_ids, message)

    await message.bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Forward xabar yuborildi\n\n"
             f"📤 Yuborilgan: {success} ta\n"
             f"❌ Yuborilmagan: {failed} ta",
        reply_markup=await AdminPanel.admin_msg()
    )


# === ODDIY XABAR BOSHLASH === #
@msg_router.message(F.text == "📬Oddiy xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_text_send(message: Message, state: FSMContext):
    await message.answer("Yuborilishi kerak bo'lgan xabarni yuboring", reply_markup=markup)
    await state.set_state(MsgState.send_msg)


# === ODDIY XABARNI YUBORISH === #
@msg_router.message(MsgState.send_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_text_to_all(message: Message, state: FSMContext):
    await state.clear()
    sql.execute("SELECT user_id FROM public.accounts")
    rows = sql.fetchall()
    user_ids = [row[0] for row in rows]

    success, failed = await broadcast_copy(user_ids, message)

    await message.answer(
        f"✅ Oddiy xabar yuborildi\n\n"
        f"📤 Yuborilgan: {success} ta\n"
        f"❌ Yuborilmagan: {failed} ta",
        reply_markup=await AdminPanel.admin_msg()
    )


# === ORQAGA QAYTISH === #
@msg_router.message(F.text == "🔙Orqaga qaytish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Orqaga qaytildi", reply_markup=await AdminPanel.admin_msg())


# === LOGGER: Xatolik foydalanuvchini faylga yozish === #
async def log_failed_user(user_id: int):
    async with aiofiles.open(FAILED_USERS_FILE, mode="a") as f:
        await f.write(f"{user_id}\n")


# === BROADCAST COPY YUBORISH === #
async def broadcast_copy(user_ids: list[int], message: Message) -> tuple[int, int]:
    success = 0
    failed = 0
    status_msg = await message.answer("📤 Yuborish boshlandi...")

    async def handle_user(user_id):
        nonlocal success, failed
        result = await send_copy_safe(user_id, message)
        if result:
            success += 1
        else:
            failed += 1
            await log_failed_user(user_id)

    tasks = [handle_user(uid) for uid in user_ids]

    for i in range(0, len(tasks), 500):
        await asyncio.gather(*tasks[i:i + 500])
        try:
            await status_msg.edit_text(
                f"📬 Oddiy xabar yuborilmoqda...\n\n"
                f"✅ Yuborilgan: {success} ta\n"
                f"❌ Yuborilmagan: {failed} ta\n"
                f"📦 Jami: {len(user_ids)} ta\n"
                f"📊 Progres: {min(i + 500, len(user_ids))}/{len(user_ids)}"
            )
        except Exception as e:
            print(f"Holatni yangilashda xato: {e}")

    return success, failed


# === BROADCAST FORWARD === #
async def broadcast_forward(user_ids: list[int], message: Message) -> tuple[int, int]:
    success = 0
    failed = 0
    status_msg = await message.answer("📨 Forward yuborish boshlandi...")

    async def handle_user(user_id):
        nonlocal success, failed
        result = await send_forward_safe(user_id, message)
        if result:
            success += 1
        else:
            failed += 1
            await log_failed_user(user_id)

    tasks = [handle_user(uid) for uid in user_ids]

    for i in range(0, len(tasks), 500):
        await asyncio.gather(*tasks[i:i + 500])
        try:
            await status_msg.edit_text(
                f"📨 Forward yuborilmoqda...\n\n"
                f"✅ Yuborilgan: {success} ta\n"
                f"❌ Yuborilmagan: {failed} ta\n"
                f"📦 Jami: {len(user_ids)} ta\n"
                f"📊 Progres: {min(i + 500, len(user_ids))}/{len(user_ids)}"
            )
        except Exception as e:
            print(f"Holatni yangilashda xato: {e}")

    return success, failed


# === FORWARD XAVFSIZ YUBORISH === #
async def send_forward_safe(user_id: int, message: Message, retries=2) -> int:
    for attempt in range(retries):
        try:
            async with semaphore:
                await bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                return 1
        except (TelegramForbiddenError, TelegramNotFound, TelegramBadRequest, TelegramAPIError):
            return 0
        except Exception as e:
            print(f"❌ Forward error user_id={user_id} (attempt {attempt + 1}): {e}")
            await asyncio.sleep(1)
    return 0


# === COPY XAVFSIZ YUBORISH === #
async def send_copy_safe(user_id: int, message: Message, retries=2) -> int:
    for attempt in range(retries):
        try:
            async with semaphore:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                return 1
        except (TelegramForbiddenError, TelegramNotFound, TelegramBadRequest, TelegramAPIError):
            return 0
        except Exception as e:
            print(f"❌ Copy error user_id={user_id} (attempt {attempt + 1}): {e}")
            await asyncio.sleep(1)
    return 0




TEST_FAILED_COPY_FILE = "test_failed_copy.txt"
TEST_FAILED_FORWARD_FILE = "test_failed_forward.txt"

# === LOGGER: Xatolik foydalanuvchini faylga yozish (test copy/forward uchun) === #
async def log_test_failed_user(user_id: int, is_copy=True):
    filename = TEST_FAILED_COPY_FILE if is_copy else TEST_FAILED_FORWARD_FILE
    async with aiofiles.open(filename, mode="a") as f:
        await f.write(f"{user_id}\n")


# === SINOV: ODDIY XABARNI COPY YUBORIB O‘CHIRISH === #
@msg_router.message(F.text == "🧪Sinov: Copy yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def test_copy_broadcast(message: Message, state: FSMContext):
    await message.answer("🧪 Sinov: Oddiy xabarni yuboring (copy), yuboriladi va darhol o‘chiriladi:")
    await state.set_state(MsgState.test_copy_msg)


@msg_router.message(MsgState.test_copy_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def handle_test_copy(message: Message, state: FSMContext):
    await state.clear()
    sql.execute("SELECT user_id FROM public.accounts")
    rows = sql.fetchall()
    user_ids = [row[0] for row in rows]

    success = 0
    failed = 0
    status = await message.answer("📤 Sinov copy yuborish boshlandi...")

    async def send_and_delete(user_id):
        nonlocal success, failed
        try:
            async with semaphore:
                sent = await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                await asyncio.sleep(0.2)
                await bot.delete_message(chat_id=user_id, message_id=sent.message_id)
                success += 1
        except Exception as e:
            failed += 1
            await log_test_failed_user(user_id, is_copy=True)
            print(f"[COPY TEST] ❌ user_id={user_id} | {e}")

    tasks = [send_and_delete(uid) for uid in user_ids]

    for i in range(0, len(tasks), 500):
        await asyncio.gather(*tasks[i:i + 500])
        try:
            await status.edit_text(
                f"🧪 Copy sinovi\n"
                f"✅ Yuborildi: {success}\n"
                f"❌ Xato: {failed}\n"
                f"📊 Progres: {min(i + 500, len(user_ids))}/{len(user_ids)}"
            )
        except:
            pass

    await message.answer(f"✅ Sinov yakunlandi\n\n"
                         f"📤 Copy yuborilgan: {success}\n"
                         f"❌ Xatoliklar: {failed}\n"
                         f"📦 Jami: {len(user_ids)} foydalanuvchi")


# === SINOV: FORWARD XABARNI YUBORIB O‘CHIRISH === #
@msg_router.message(F.text == "🧪Sinov: Forward yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def test_forward_broadcast(message: Message, state: FSMContext):
    await message.answer("🧪 Sinov: Forward xabar yuboring, darhol o‘chiriladi:")
    await state.set_state(MsgState.test_forward_msg)


@msg_router.message(MsgState.test_forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def handle_test_forward(message: Message, state: FSMContext):
    await state.clear()
    sql.execute("SELECT user_id FROM public.accounts")
    rows = sql.fetchall()
    user_ids = [row[0] for row in rows]

    success = 0
    failed = 0
    status = await message.answer("📨 Sinov forward yuborish boshlandi...")

    async def send_and_delete(user_id):
        nonlocal success, failed
        try:
            async with semaphore:
                sent = await bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                await asyncio.sleep(0.2)
                await bot.delete_message(chat_id=user_id, message_id=sent.message_id)
                success += 1
        except Exception as e:
            failed += 1
            await log_test_failed_user(user_id, is_copy=False)
            print(f"[FORWARD TEST] ❌ user_id={user_id} | {e}")

    tasks = [send_and_delete(uid) for uid in user_ids]

    for i in range(0, len(tasks), 500):
        await asyncio.gather(*tasks[i:i + 500])
        try:
            await status.edit_text(
                f"🧪 Forward sinovi\n"
                f"✅ Yuborildi: {success}\n"
                f"❌ Xato: {failed}\n"
                f"📊 Progres: {min(i + 500, len(user_ids))}/{len(user_ids)}"
            )
        except:
            pass

    await message.answer(f"✅ Forward sinov tugadi\n\n"
                         f"📤 Forward yuborilgan: {success}\n"
                         f"❌ Xatoliklar: {failed}\n"
                         f"📦 Jami: {len(user_ids)} foydalanuvchi")