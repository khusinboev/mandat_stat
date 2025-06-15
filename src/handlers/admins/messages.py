from aiogram import Router, F, Bot
from aiogram.enums import ChatType, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from config import ADMIN_ID, sql, bot
from src.keyboards.buttons import AdminPanel

msg_router = Router()

class MsgState(StatesGroup):
    forward_msg = State()
    send_msg = State()

markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]])

# Admin panelga kirish
@msg_router.message(F.text == "✍Xabarlar", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))#,
async def panel_handler(message: Message) -> None:
    await message.answer("Xabarlar bo'limi!", reply_markup=await AdminPanel.admin_msg())


@msg_router.message(F.text == "📨Forward xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_forward(message: Message, state: FSMContext):
    await message.answer("Forward yuboriladigan xabarni yuboring",
                         reply_markup=markup)
    await state.set_state(MsgState.forward_msg)


@msg_router.message(MsgState.forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_forward_to_all(message: Message, state: FSMContext):
    await state.clear()
    sql.execute("SELECT user_id FROM public.accounts")
    rows = sql.fetchall()
    num = 0
    for row in rows:
        num += await forward_send_msg(bot=bot, from_chat_id=message.chat.id, message_id=message.message_id, chat_id=row[0])

    await message.bot.send_message(chat_id=message.chat.id,
                                   text=f"Xabar yuborish yakunlandi, xabaringiz {num} ta odamga yuborildi",
                                   reply_markup=await AdminPanel.admin_msg())


@msg_router.message(F.text == "📬Oddiy xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_text_send(message: Message, state: FSMContext):
    await message.answer("Yuborilishi kerak bo'lgan xabarni yuboring",
                         reply_markup=markup)
    await state.set_state(MsgState.send_msg)


@msg_router.message(MsgState.send_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_text_to_all(message: Message, state: FSMContext):
    await state.clear()
    sql.execute("SELECT user_id FROM public.accounts")
    rows = sql.fetchall()
    num = 0
    for row in rows:
        num += await send_message_chats(bot=bot, from_chat_id=message.chat.id, message_id=message.message_id, chat_id=row[0])

    await message.answer(f"Xabar yuborish yakunlandi, xabaringiz {num} ta odamga yuborildi",
                         reply_markup=await AdminPanel.admin_msg())


@msg_router.message(F.text == "🔙Orqaga qaytish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Orqaga qaytildi", reply_markup=await AdminPanel.admin_msg())


async def forward_send_msg(bot: Bot, chat_id: int, from_chat_id: int, message_id: int) -> int:
    try:
        await bot.forward_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)
        return 1
    except (TelegramAPIError, TelegramBadRequest):
        pass
    except Exception as e:
        print(f"Xatolik (forward): {e}")
    return 0



async def send_message_chats(bot: Bot, chat_id: int, from_chat_id: int, message_id: int) -> int:
    try:
        await bot.copy_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)
        return 1
    except (TelegramAPIError, TelegramBadRequest):
        pass
    except Exception as e:
        print(f"Xatolik (copy): {e}")
    return 0
