import logging
from datetime import datetime, timedelta

import psycopg2
import pytz
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ChatInviteLink
)
from aiogram.enums import ChatType
from dateutil.relativedelta import relativedelta

from src.keyboards.buttons import AdminPanel
from config import ADMIN_ID, DB_CONFIG, bot, db_connection
from src.keyboards.keyboard_func import PanelFunc

logger = logging.getLogger(__name__)
admin_router = Router()


class Form(StatesGroup):
    ch_add       = State()
    for_username = State()
    ch_delete    = State()

    ch_add2       = State()
    for_username2 = State()
    ch_delete2    = State()


markup  = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]])
markup2 = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙Orqaga qaytish2")]])


# ═══════════════════════════════════════════════════════════════
#  ADMIN PANELGA KIRISH
# ═══════════════════════════════════════════════════════════════

@admin_router.message(
    Command("panel", "admin"),
    F.from_user.id.in_(ADMIN_ID),
    F.chat.type == ChatType.PRIVATE,
)
async def panel_handler(message: Message):
    await message.answer("Admin panel 👇", reply_markup=await AdminPanel.admin_menu())


@admin_router.message(F.text == "🔙Orqaga qaytish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.reply("Orqaga qaytildi", reply_markup=await AdminPanel.admin_menu())


# ═══════════════════════════════════════════════════════════════
#  STATISTIKA
# ═══════════════════════════════════════════════════════════════

@admin_router.message(F.text == "📊Statistika", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def statistika(message: Message):
    now = datetime.now(pytz.timezone("Asia/Tashkent")).date()
    current_month = now.replace(day=1)
    months = [current_month - relativedelta(months=i) for i in range(3)]

    with db_connection() as (conn, cur):
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
            day = now - timedelta(days=i)
            cur.execute(
                "SELECT COUNT(*) FROM accounts WHERE date::date = %s", (day,)
            )
            last_7_days[str(day)] = cur.fetchone()[0] or 0

    text = (
        f"📊 *Foydalanuvchi Statistikasi:*\n\n"
        f"🔹 *Jami foydalanuvchilar:* {all_users}\n\n"
        f"📅 *Oxirgi 3 oy:* (Jami {last_3_months} ta)\n"
    )
    for month, count in month_counts.items():
        text += f" - {month}: {count} ta\n"

    text += f"\n📆 *Oxirgi 7 kun:* (Jami {sum(last_7_days.values())})\n"
    for day, count in last_7_days.items():
        text += f" - {day}: {count} ta\n"

    await message.answer(text, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════
#  KANALLAR 1-GURUH
# ═══════════════════════════════════════════════════════════════

@admin_router.message(F.text == "🔧Kanallar", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanallar_menu(message: Message):
    await message.answer("Tanlang", reply_markup=await AdminPanel.admin_channel())


@admin_router.message(F.text == "➕Kanal qo'shish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanal_qoshish(message: Message, state: FSMContext):
    await bot.send_message(
        message.chat.id,
        text=(
            "Kanal ulash bo'limi.\n"
            "1. <code>https://t.me/kanaluser</code> havolasini yuboring\n"
            "2. <code>@kanaluser</code> username ni yuboring"
        ),
        reply_markup=markup,
        parse_mode="html",
    )
    await state.set_state(Form.ch_add)


@admin_router.message(Form.ch_add, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanal_qoshish_2(message: Message, state: FSMContext):
    raw = message.text or ""
    chat_link = None

    if "https://t.me/" in raw:
        chat_link = "@" + raw.split("https://t.me/", 1)[1].split("/")[0]
    elif raw.startswith("@"):
        chat_link = raw

    if not chat_link:
        await message.answer("Kanal <b>username</b> yoki havolasini yuboring", reply_markup=markup, parse_mode="html")
        return

    try:
        chat = await bot.get_chat(chat_link)
    except Exception as e:
        await state.clear()
        await bot.send_message(
            message.chat.id,
            text="Bot kanalga <b>admin emas!</b> yoki kanal topilmadi. Tekshirib qaytadan urining.",
            reply_markup=await AdminPanel.admin_channel(),
            parse_mode="html",
        )
        return

    with db_connection() as (conn, cur):
        cur.execute("SELECT 1 FROM public.mandatorys WHERE chat_id = %s", (chat.id,))
        exists = cur.fetchone()

    if exists:
        await message.reply("Bu kanal avvaldan bor", reply_markup=await AdminPanel.admin_channel())
        await state.clear()
        return

    await message.reply(
        "Kanal qabul qilindi. Endi taklif havolasini yuboring. "
        "U <code>https://t.me/+</code> deb boshlanadi.",
        reply_markup=markup,
        parse_mode="html",
    )
    await state.update_data(channel_id=str(chat.id))
    await state.set_state(Form.for_username)


@admin_router.message(Form.for_username, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanal_link_saqlash(message: Message, state: FSMContext):
    link = message.text or ""
    if "https://t.me/" not in link:
        await message.answer(
            "Taklif havolasini yuboring. <code>https://t.me/+</code> deb boshlanadi.",
            reply_markup=markup,
            parse_mode="html",
        )
        return
    data = await state.get_data()
    channel_id = data["channel_id"]
    await PanelFunc.channel_add(channel_id, link)
    await state.clear()
    await message.reply("Kanal qo'shildi 🎉", reply_markup=await AdminPanel.admin_channel())


@admin_router.message(F.text == "❌Kanalni olib tashlash", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanal_ochirish(message: Message, state: FSMContext):
    await message.reply("O'chiriladigan kanalning @username ni yuboring.", reply_markup=markup)
    await state.set_state(Form.ch_delete)


@admin_router.message(Form.ch_delete, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanal_ochirish_2(message: Message, state: FSMContext):
    raw = message.text or ""
    try:
        chat = await bot.get_chat(raw)
    except Exception:
        await message.reply("Kanal topilmadi. @username ko'rinishida kiriting.", reply_markup=markup)
        return

    with db_connection() as (conn, cur):
        cur.execute("SELECT 1 FROM public.mandatorys WHERE chat_id = %s", (chat.id,))
        exists = cur.fetchone()

    if not exists:
        await message.reply("Bunday kanal yo'q", reply_markup=await AdminPanel.admin_channel())
    else:
        await PanelFunc.channel_delete(chat.id)
        await message.reply("Kanal muvaffaqiyatli o'chirildi", reply_markup=await AdminPanel.admin_channel())

    await state.clear()


@admin_router.message(F.text == "📋 Kanallar ro'yxati", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanallar_royxati(message: Message):
    result = await PanelFunc.channel_list()
    if len(result) > 3:
        await message.answer(result, parse_mode="html")
    else:
        await message.answer("Hozircha kanallar yo'q")


# ═══════════════════════════════════════════════════════════════
#  KANALLAR 2-GURUH
# ═══════════════════════════════════════════════════════════════

@admin_router.message(F.text == "🔧Kanallar2", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanallar2_menu(message: Message):
    await message.answer("Tanlang", reply_markup=await AdminPanel.admin_channel2())


@admin_router.message(F.text == "🔙Orqaga qaytish2", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back_to_menu2(message: Message, state: FSMContext):
    await state.clear()
    await message.reply("Orqaga qaytildi", reply_markup=await AdminPanel.admin_menu())


@admin_router.message(F.text == "➕Kanal qo'shish2", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanal_qoshish2(message: Message, state: FSMContext):
    await bot.send_message(
        message.chat.id,
        text=(
            "Kanal ulash bo'limi (2-guruh).\n"
            "1. <code>https://t.me/kanaluser</code> havolasini yuboring\n"
            "2. <code>@kanaluser</code> username ni yuboring"
        ),
        reply_markup=markup2,
        parse_mode="html",
    )
    await state.set_state(Form.ch_add2)


@admin_router.message(Form.ch_add2, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanal_qoshish2_2(message: Message, state: FSMContext):
    raw = message.text or ""
    chat_link = None

    if "https://t.me/" in raw:
        chat_link = "@" + raw.split("https://t.me/", 1)[1].split("/")[0]
    elif raw.startswith("@"):
        chat_link = raw

    if not chat_link:
        await message.answer("Kanal <b>username</b> yoki havolasini yuboring", reply_markup=markup2, parse_mode="html")
        return

    try:
        chat = await bot.get_chat(chat_link)
    except Exception:
        await state.clear()
        await bot.send_message(
            message.chat.id,
            text="Bot kanalga <b>admin emas!</b> Tekshirib qaytadan urining.",
            reply_markup=await AdminPanel.admin_channel2(),
            parse_mode="html",
        )
        return

    with db_connection() as (conn, cur):
        cur.execute("SELECT 1 FROM public.kanallar2 WHERE chat_id = %s", (chat.id,))
        exists = cur.fetchone()

    if exists:
        await message.reply("Bu kanal avvaldan bor", reply_markup=markup2)
        return

    await message.reply(
        "Kanal qabul qilindi. Taklif havolasini yuboring (<code>https://t.me/+</code>).",
        reply_markup=markup2,
        parse_mode="html",
    )
    await state.update_data(channel_id=str(chat.id))
    await state.set_state(Form.for_username2)


@admin_router.message(Form.for_username2, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanal_link_saqlash2(message: Message, state: FSMContext):
    link = message.text or ""
    if "https://t.me/" not in link:
        await message.answer(
            "Taklif havolasini yuboring (<code>https://t.me/+</code>).",
            reply_markup=markup2,
            parse_mode="html",
        )
        return
    data = await state.get_data()
    channel_id = data["channel_id"]
    await PanelFunc.channel_add2(channel_id, link)
    await state.clear()
    await message.reply("Kanal qo'shildi 🎉", reply_markup=await AdminPanel.admin_channel2())


@admin_router.message(F.text == "❌Kanalni olib tashlash2", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanal_ochirish2(message: Message, state: FSMContext):
    await message.reply("O'chiriladigan kanalning @username ni yuboring.", reply_markup=markup2)
    await state.set_state(Form.ch_delete2)


@admin_router.message(Form.ch_delete2, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanal_ochirish2_2(message: Message, state: FSMContext):
    raw = message.text or ""
    try:
        chat = await bot.get_chat(raw)
    except Exception:
        await message.reply("Kanal topilmadi.", reply_markup=markup2)
        return

    with db_connection() as (conn, cur):
        cur.execute("SELECT 1 FROM public.kanallar2 WHERE chat_id = %s", (chat.id,))
        exists = cur.fetchone()

    if not exists:
        await message.reply("Bunday kanal yo'q", reply_markup=await AdminPanel.admin_channel2())
    else:
        await PanelFunc.channel_delete2(chat.id)
        await message.reply("Kanal muvaffaqiyatli o'chirildi", reply_markup=await AdminPanel.admin_channel2())

    await state.clear()


@admin_router.message(F.text == "📋 Kanallar ro'yxati2", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def kanallar2_royxati(message: Message):
    result = await PanelFunc.channel_list2()
    if len(result) > 3:
        await message.answer(result, parse_mode="html")
    else:
        await message.answer("Hozircha kanallar yo'q")
