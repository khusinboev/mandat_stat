from aiogram.fsm.state import StatesGroup, State

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, Filter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, \
    InlineQueryResultArticle, InputTextMessageContent

from config import sql, bot, ADMIN_ID, cursor, conn
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

user_router = Router()

class StatesBall(StatesGroup):
    ch_add = State()
    for_username = State()
    ch_delete = State()

    anons_forward = State()
    anons_simple = State()

    clear_base = State()

@user_router.message(CommandStart())
async def enter_add_cinema(msg: Message):
    await msg.answer("Quyidagi menulardan birini tanlang!", parse_mode="html", reply_markup=await UserPanels.main_manu())


@user_router.callback_query(F.data == "check", F.message.chat.type == ChatType.PRIVATE)
async def check(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        check_status, channels = await CheckData.check_member(bot, user_id)
        if check_status:
            await call.message.delete()
            await bot.send_message(chat_id=user_id,
                                   text="Quyidagi menulardan birini tanlang!",
                                   parse_mode="html")
            try: await call.answer()
            except: pass
        else:
            try:
                await call.answer(show_alert=True, text="Botimizdan foydalanish uchun hamma kanallargaga azo bo'ling")
            except Exception as e:
                try:
                    await call.answer()
                except:
                    pass
    except Exception as e:
        try: await call.answer()
        except: pass
        await bot.forward_message(chat_id=ADMIN_ID[0], from_chat_id=call.message.chat.id, message_id=call.message.message_id)
        await bot.send_message(chat_id=ADMIN_ID[0], text=f"Error in check: \n\n{e}")


# Ball yetadigan yo'nalishlar
@user_router.message(F.text == "📊 Ball yetadigan yo'nalishlar", F.chat.type == ChatType.PRIVATE)
async def enter_add_cinema(message: Message):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Regionni izlash", switch_inline_query_current_chat="region ")],
            [InlineKeyboardButton(text="🎓 Universitetni izlash", switch_inline_query_current_chat="univer ")],
            [InlineKeyboardButton(text="🌐 Tilni izlash", switch_inline_query_current_chat="til ")]
        ])
        await message.answer("<b>O'quv turini tanlang 👇</b>", parse_mode="html", reply_markup=kb)
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))



@user_router.inline_query(F.query.startswith("region"))
async def inline_search_region(inline_query: InlineQuery):
    text = inline_query.query.replace("region", "").strip().lower()

    if text:
        cursor.execute("SELECT region_name FROM regions WHERE lower(region_name) LIKE ?", (f"%{text}%",))
    else:
        cursor.execute("SELECT region_name FROM regions LIMIT 20")  # Default holat

    regions = cursor.fetchall()
    conn.close()

    results = [
        InlineQueryResultArticle(
            id=str(i),
            title=row[0],
            input_message_content=InputTextMessageContent(message_text=f"Tanlangan region: {row[0]}")
        ) for i, row in enumerate(regions)
    ]

    await inline_query.answer(results, cache_time=1, is_personal=True)
