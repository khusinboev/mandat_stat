import asyncio from pathlib import Path from datetime import datetime from aiogram import Router, F, Bot from aiogram.enums import ChatType from aiogram.fsm.context import FSMContext from aiogram.fsm.state import StatesGroup, State from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, InputFile from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramForbiddenError, TelegramNotFound

from config import ADMIN_ID, sql, bot from src.keyboards.buttons import AdminPanel

msg_router = Router()

=== HOLAT (FSM) ===

class MsgState(StatesGroup): forward_msg = State() send_msg = State()

=== QAYTISH TUGMASI ===

markup = ReplyKeyboardMarkup( resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]] )

=== ERROR LOG ===

ERROR_LOG_PATH = Path("/mnt/data/broadcast_errors.txt")

def log_error(user_id: int, error: Exception): with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f: f.write(f"{datetime.now().isoformat()} | user_id={user_id} | error={error}\n")

=== ADMIN PANEL ===

@msg_router.message(F.text == "✍Xabarlar", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID)) async def panel_handler(message: Message) -> None: await message.answer("Xabarlar bo'limi!", reply_markup=await AdminPanel.admin_msg())

=== FORWARD XABAR BOSHLASH ===

@msg_router.message(F.text == "📨Forward xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID)) async def start_forward(message: Message, state: FSMContext): await message.answer("Forward yuboriladigan xabarni yuboring", reply_markup=markup) await state.set_state(MsgState.forward_msg)

=== FORWARD XABARNI YUBORISH ===

@msg_router.message(MsgState.forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID)) async def send_forward_to_all(message: Message, state: FSMContext): await state.clear() sql.execute("SELECT user_id FROM public.accounts") user_ids = [row[0] for row in sql.fetchall()]

success, failed = await broadcast_forward(user_ids, message)

files = []
if ERROR_LOG_PATH.exists():
    files.append(InputFile(ERROR_LOG_PATH))

await bot.send_message(
    chat_id=message.chat.id,
    text=f"✅ Forward xabar yuborildi\n\n"
         f"📤 Yuborilgan: {success} ta\n"
         f"❌ Yuborilmagan: {failed} ta",
    reply_markup=await AdminPanel.admin_msg()
)

if files:
    await bot.send_document(message.chat.id, files[0])

=== ODDIY XABAR BOSHLASH ===

@msg_router.message(F.text == "📬Oddiy xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID)) async def start_text_send(message: Message, state: FSMContext): await message.answer("Yuborilishi kerak bo'lgan xabarni yuboring", reply_markup=markup) await state.set_state(MsgState.send_msg)

=== ODDIY XABARNI YUBORISH ===

@msg_router.message(MsgState.send_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID)) async def send_text_to_all(message: Message, state: FSMContext): await state.clear() sql.execute("SELECT user_id FROM public.accounts") user_ids = [row[0] for row in sql.fetchall()]

success, failed = await broadcast_copy(user_ids, message)

files = []
if ERROR_LOG_PATH.exists():
    files.append(InputFile(ERROR_LOG_PATH))

await message.answer(
    f"✅ Oddiy xabar yuborildi\n\n"
    f"📤 Yuborilgan: {success} ta\n"
    f"❌ Yuborilmagan: {failed} ta",
    reply_markup=await AdminPanel.admin_msg()
)

if files:
    await message.answer_document(files[0])

=== ORQAGA QAYTISH ===

@msg_router.message(F.text == "🔙Orqaga qaytish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID)) async def back_to_menu(message: Message, state: FSMContext): await state.clear() await message.answer("Orqaga qaytildi", reply_markup=await AdminPanel.admin_msg())

=======================

BROADCAST

=======================

semaphore = asyncio.Semaphore(30)  # 30 ta parallel yuborishga ruxsat

--- ODDIY XABAR BROADCAST ---

async def broadcast_copy(user_ids: list[int], message: Message) -> tuple[int, int]: success = 0 failed = 0 status_msg = await message.answer("\ud83d\udce4 Yuborish boshlandi...")

for i, user_id in enumerate(user_ids, 1):
    result = await send_copy_safe(user_id, message)
    success += result
    failed += (1 - result)

    if i % 100 == 0 or i == len(user_ids):
        try:
            await status_msg.edit_text(
                f"📬 Oddiy xabar yuborilmoqda...\n\n"
                f"✅ Yuborilgan: {success} ta\n"
                f"❌ Yuborilmagan: {failed} ta\n"
                f"📦 Jami: {len(user_ids)} ta\n"
                f"📊 Progres: {i}/{len(user_ids)}"
            )
        except Exception as e:
            log_error(0, e)

return success, failed

--- FORWARD XABAR BROADCAST ---

async def broadcast_forward(user_ids: list[int], message: Message) -> tuple[int, int]: success = 0 failed = 0 status_msg = await message.answer("📨 Forward yuborish boshlandi...")

for i, user_id in enumerate(user_ids, 1):
    result = await send_forward_safe(user_id, message)
    success += result
    failed += (1 - result)

    if i % 100 == 0 or i == len(user_ids):
        try:
            await status_msg.edit_text(
                f"📨 Forward yuborilmoqda...\n\n"
                f"✅ Yuborilgan: {success} ta\n"
                f"❌ Yuborilmagan: {failed} ta\n"
                f"📦 Jami: {len(user_ids)} ta\n"
                f"📊 Progres: {i}/{len(user_ids)}"
            )
        except Exception as e:
            log_error(0, e)

return success, failed

--- XAVFSIZ COPY ---

async def send_copy_safe(user_id: int, message: Message, retries=3) -> int: for attempt in range(retries): try: async with semaphore: await bot.copy_message( chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id ) return 1 except (TelegramForbiddenError, TelegramNotFound, TelegramBadRequest, TelegramAPIError): return 0 except Exception as e: log_error(user_id, e) await asyncio.sleep(1) return 0

--- XAVFSIZ FORWARD ---

async def send_forward_safe(user_id: int, message: Message, retries=3) -> int: for attempt in range(retries): try: async with semaphore: await bot.forward_message( chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id ) return 1 except (TelegramForbiddenError, TelegramNotFound, TelegramBadRequest, TelegramAPIError): return 0 except Exception as e: log_error(user_id, e) await asyncio.sleep(1) return 0

