import asyncio
from aiogram import Router, F, Bot
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramForbiddenError, TelegramNotFound

from config import ADMIN_ID, sql, bot
from src.keyboards.buttons import AdminPanel

msg_router = Router()

class MsgState(StatesGroup):
    forward_msg = State()
    send_msg = State()

markup = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]]
)

# Admin panelga kirish
@msg_router.message(F.text == "✍Xabarlar", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def panel_handler(message: Message) -> None:
    await message.answer("Xabarlar bo'limi!", reply_markup=await AdminPanel.admin_msg())

# --- FORWARD xabar yuborish --- #
@msg_router.message(F.text == "📨Forward xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_forward(message: Message, state: FSMContext):
    await message.answer("Forward yuboriladigan xabarni yuboring", reply_markup=markup)
    await state.set_state(MsgState.forward_msg)

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

# --- ODDIY (copy) xabar yuborish --- #
@msg_router.message(F.text == "📬Oddiy xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_text_send(message: Message, state: FSMContext):
    await message.answer("Yuborilishi kerak bo'lgan xabarni yuboring", reply_markup=markup)
    await state.set_state(MsgState.send_msg)

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

# --- ORQAGA QAYTISH --- #
@msg_router.message(F.text == "🔙Orqaga qaytish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Orqaga qaytildi", reply_markup=await AdminPanel.admin_msg())

# === ASOSİY BROADCAST FUNKSIYALARI === #

semaphore = asyncio.Semaphore(30)  # Parallel yuborish limiti (Telegram uchun xavfsiz)

async def broadcast_copy(user_ids: list[int], message: Message) -> tuple[int, int]:
    tasks = [send_copy_safe(uid, message) for uid in user_ids]
    results = await asyncio.gather(*tasks)
    return sum(results), len(user_ids) - sum(results)

async def broadcast_forward(user_ids: list[int], message: Message) -> tuple[int, int]:
    tasks = [send_forward_safe(uid, message) for uid in user_ids]
    results = await asyncio.gather(*tasks)
    return sum(results), len(user_ids) - sum(results)

async def send_copy_safe(user_id: int, message: Message) -> int:
    try:
        async with semaphore:
            await bot.copy_message(chat_id=user_id,
                                   from_chat_id=message.chat.id,
                                   message_id=message.message_id)
            return 1
    except (TelegramForbiddenError, TelegramNotFound, TelegramAPIError, TelegramBadRequest):
        return 0
    except Exception as e:
        print(f"❌ Copy error user_id={user_id}: {e}")
        return 0

async def send_forward_safe(user_id: int, message: Message) -> int:
    try:
        async with semaphore:
            await bot.forward_message(chat_id=user_id,
                                      from_chat_id=message.chat.id,
                                      message_id=message.message_id)
            return 1
    except (TelegramForbiddenError, TelegramNotFound, TelegramAPIError, TelegramBadRequest):
        return 0
    except Exception as e:
        print(f"❌ Forward error user_id={user_id}: {e}")
        return 0