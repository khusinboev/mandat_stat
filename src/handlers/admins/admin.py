from datetime import datetime, timedelta

import psycopg2
import pytz
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatType
from aiogram.fsm.state import StatesGroup, State
from dateutil.relativedelta import relativedelta

from src.keyboards.buttons import AdminPanel
from config import sql, ADMIN_ID, DB_CONFIG, bot
from src.keyboards.keyboard_func import PanelFunc

admin_router = Router()

class Form(StatesGroup):
    ch_add = State()
    for_username = State()
    ch_delete = State()
    ch_add2 = State()
    for_username2 = State()
    ch_delete2 = State()
    anons_forward = State()
    anons_simple = State()
    clear_base = State()

# Kanal boshqaruv uchun konfiguratsiyalar
_CHANNEL_CONFIGS = {
    "1": {
        "table": "mandatorys",
        "states": {"add": "ch_add", "username": "for_username", "delete": "ch_delete"},
        "panel": "admin_channel",
        "back_text": "🔙Orqaga qaytish",
    },
    "2": {
        "table": "kanallar2",
        "states": {"add": "ch_add2", "username": "for_username2", "delete": "ch_delete2"},
        "panel": "admin_channel2",
        "back_text": "🔙Orqaga qaytish2",
    },
}


async def _get_panel(config):
    return await getattr(AdminPanel, config["panel"])()


async def _handle_channel_input(message: Message, state: FSMContext, config):
    """Umumiy kanal qo'shish logikasi (link/username qabul qilish)."""
    table = config["table"]
    panel = await _get_panel(config)
    back_markup = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton(text=config["back_text"])]]
    )

    if message.chat_shared:
        return

    text = message.text or ""
    chat_link = None

    if "https://t.me/" in text:
        chat_link = "@" + text.split("https://t.me/", 1)[1]
    elif text.startswith("@"):
        chat_link = "@" + text[1:]
    else:
        await message.answer("Kanal <b>username</b> yuboring", reply_markup=back_markup, parse_mode="html")
        return

    try:
        chat = await bot.get_chat(chat_link)
    except Exception as e:
        print(e)
        await state.clear()
        await bot.send_message(
            chat_id=message.chat.id,
            text="Bot kanalga <b>admin emas!</b> yoki havolani qayta ishlashda muammolar bo'lyapti. "
                 "Iltimos havolani va adminlikni tekshirib qaytadan urining",
            reply_markup=panel,
            parse_mode="html",
        )
        return

    channel_id = chat.id
    sql.execute(f"SELECT chat_id FROM public.{table} WHERE chat_id = %s", (channel_id,))
    data = sql.fetchone()
    if data is None:
        await message.reply(
            "Kanal username qabul qilindi, endi taklif havolasini yuboring. "
            "U https://t.me/+ deb boshlanadi. Buni kanal havolalari bo'limida yaratasiz.",
            reply_markup=back_markup,
        )
        await state.update_data(channel_id=str(channel_id))
        username_state = getattr(Form, config["states"]["username"])
        await state.set_state(username_state)
    else:
        await message.reply("Bu kanal avvaldan bor, qaytadan yuboring", reply_markup=back_markup)


async def _handle_invite_link(message: Message, state: FSMContext, config):
    """Umumiy taklif havolasi qabul qilish logikasi."""
    link = message.text
    panel = await _get_panel(config)
    back_markup = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton(text=config["back_text"])]]
    )

    if "https://t.me/" in link:
        data = await state.get_data()
        channel_id = data["channel_id"]
        add_func = getattr(PanelFunc, f"channel_add{'2' if config['table'] == 'kanallar2' else ''}")
        await add_func(channel_id, link)
        await state.clear()
        await message.reply("Kanal qo'shildi🎉🎉", reply_markup=panel)
    else:
        await message.answer(
            "Kanal taklif havolasini yuboring. U https://t.me/+ deb boshlanadi. "
            "Buni kanal havolalari bo'limida yaratasiz.",
            reply_markup=back_markup,
        )


async def _handle_channel_delete(message: Message, state: FSMContext, config):
    """Umumiy kanal o'chirish logikasi."""
    table = config["table"]
    panel = await _get_panel(config)

    all_details = await bot.get_chat(message.text)
    channel_id = all_details.id
    sql.execute(f"SELECT chat_id FROM public.{table} WHERE chat_id = %s", (channel_id,))
    data = sql.fetchone()

    if data is None:
        await message.reply("Bunday kanal yo'q", reply_markup=panel)
    else:
        if message.text[0] == '@':
            delete_func = getattr(PanelFunc, f"channel_delete{'2' if table == 'kanallar2' else ''}")
            await delete_func(channel_id)
            await state.clear()
            await message.reply("Kanal muvaffaqiyatli o'chirildi", reply_markup=panel)
        else:
            await message.reply(
                "Kanal useri xato kiritildi\nIltimos userni @coder_admin ko'rinishida kiriting",
                reply_markup=panel,
            )
    await state.clear()


# ─── Admin panelga kirish ───
@admin_router.message(Command("panel", "admin"), F.from_user.id.in_(ADMIN_ID), F.chat.type == ChatType.PRIVATE)
async def panel_handler(message: Message) -> None:
    await message.answer("panel", reply_markup=await AdminPanel.admin_menu())


# ─── Orqaga qaytish ───
@admin_router.message(F.text == "🔙Orqaga qaytish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back_to_menu(message: Message, state: FSMContext):
    await message.reply("Orqaga qaytildi", reply_markup=await AdminPanel.admin_menu())
    await state.clear()

@admin_router.message(F.text == "🔙Orqaga qaytish2", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back_to_menu2(message: Message, state: FSMContext):
    await message.reply("Orqaga qaytildi", reply_markup=await AdminPanel.admin_menu())
    await state.clear()


# ─── Statistika ───
@admin_router.message(F.text == "📊Statistika", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def statistics(message: Message):
    now = datetime.now(pytz.timezone("Asia/Tashkent")).date()
    current_month = now.replace(day=1)
    months = [current_month - relativedelta(months=i) for i in range(3)]

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM accounts")
    all_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM accounts WHERE date >= %s", (months[-1],))
    last_3_months = cur.fetchone()[0]

    month_counts = {}
    for month in months:
        cur.execute(
            "SELECT COUNT(*) FROM accounts WHERE date >= %s AND date < %s",
            (month, month + relativedelta(months=1)),
        )
        month_counts[month.strftime("%B")] = cur.fetchone()[0] or 0

    last_7_days = {}
    for i in range(7):
        date_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        cur.execute("SELECT COUNT(*) FROM accounts WHERE date = %s", (date_str,))
        last_7_days[date_str] = cur.fetchone()[0] or 0

    cur.close()
    conn.close()

    stats_text = (
        f"📊 *Foydalanuvchi Statistikasi:*\n\n"
        f"🔹 *Jami foydalanuvchilar:* {all_users}\n\n"
        f"📅 *Oxirgi 3 oy:* (Jami {last_3_months} ta)\n"
    )
    for month, count in month_counts.items():
        stats_text += f" - {month}: {count} ta\n"
    stats_text += "\n📆 *Oxirgi 7 kun:* (Jami {})\n".format(sum(last_7_days.values()))
    for day, count in last_7_days.items():
        stats_text += f" - {day}: {count} ta\n"

    await message.answer(stats_text, parse_mode="Markdown")


# ─── Kanallar 1 ───
@admin_router.message(F.text == "🔧Kanallar", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_menu(msg: Message):
    await msg.answer("Tanlang", reply_markup=await AdminPanel.admin_channel())

@admin_router.message(F.text == "➕Kanal qo'shish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_add_start(message: Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]])
    await bot.send_message(
        message.chat.id,
        text="Kanal ulash bo'limi. \nBotga kanal ulashning 3 ta usuli bor:\n"
             "1. https://t.me/coder_admin kanal havolasini shu tartibda yuboring.\n"
             "2. @coder_admin username ni shu tartibda yuboring",
        reply_markup=markup,
        parse_mode="html",
    )
    await state.set_state(Form.ch_add)

@admin_router.message(Form.ch_add, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_add_input(message: Message, state: FSMContext):
    await _handle_channel_input(message, state, _CHANNEL_CONFIGS["1"])

@admin_router.message(Form.for_username, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_add_link(message: Message, state: FSMContext):
    await _handle_invite_link(message, state, _CHANNEL_CONFIGS["1"])

@admin_router.message(F.text == "❌Kanalni olib tashlash", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_delete_start(message: Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]])
    await message.reply("O'chiriladigan kanalning userini yuboring.\nMisol uchun @coder_admin", reply_markup=markup)
    await state.set_state(Form.ch_delete)

@admin_router.message(Form.ch_delete, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_delete_input(message: Message, state: FSMContext):
    await _handle_channel_delete(message, state, _CHANNEL_CONFIGS["1"])

@admin_router.message(F.text == "📋 Kanallar ro'yxati", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_list_show(message: Message):
    result = await PanelFunc.channel_list()
    if len(result) > 3:
        await message.answer(result, parse_mode='html')
    else:
        await message.answer("Hozircha kanallar yo'q")


# ─── Kanallar 2 ───
@admin_router.message(F.text == "🔧Kanallar2", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_menu2(msg: Message):
    await msg.answer("Tanlang", reply_markup=await AdminPanel.admin_channel2())

@admin_router.message(F.text == "➕Kanal qo'shish2", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_add_start2(message: Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙Orqaga qaytish2")]])
    await bot.send_message(
        message.chat.id,
        text="Kanal ulash bo'limi. \nBotga kanal ulashning 3 ta usuli bor:\n"
             "1. https://t.me/coder_admin kanal havolasini shu tartibda yuboring.\n"
             "2. @coder_admin username ni shu tartibda yuboring",
        reply_markup=markup,
        parse_mode="html",
    )
    await state.set_state(Form.ch_add2)

@admin_router.message(Form.ch_add2, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_add_input2(message: Message, state: FSMContext):
    await _handle_channel_input(message, state, _CHANNEL_CONFIGS["2"])

@admin_router.message(Form.for_username2, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_add_link2(message: Message, state: FSMContext):
    await _handle_invite_link(message, state, _CHANNEL_CONFIGS["2"])

@admin_router.message(F.text == "❌Kanalni olib tashlash2", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_delete_start2(message: Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙Orqaga qaytish2")]])
    await message.reply("O'chiriladigan kanalning userini yuboring.\nMisol uchun @coder_admin", reply_markup=markup)
    await state.set_state(Form.ch_delete2)

@admin_router.message(Form.ch_delete2, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_delete_input2(message: Message, state: FSMContext):
    await _handle_channel_delete(message, state, _CHANNEL_CONFIGS["2"])

@admin_router.message(F.text == "📋 Kanallar ro'yxati2", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def channel_list_show2(message: Message):
    result = await PanelFunc.channel_list2()
    if len(result) > 3:
        await message.answer(result, parse_mode='html')
    else:
        await message.answer("Hozircha kanallar yo'q")
