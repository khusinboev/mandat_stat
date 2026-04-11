"""
filter_fac.py — "Yo'nalishlar bo'yicha" bo'limi

Oqim:
  fac1  → Yo'nalish tanlash (mvdir + nomi)
  fac2  → Universitet tanlash
  fac3  → Ta'lim shakli tanlash → barcha tillar bo'yicha natija ko'rsatiladi
  fac4  → Faqat orqaga navigatsiya (natijadan keyin)
"""

import os
from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, InlineQuery,
    InlineQueryResultArticle, InputTextMessageContent,
    KeyboardButton, ReplyKeyboardMarkup, FSInputFile,
)

from config import cursor, conn, bot
from src.handlers.users.users import create_card
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

fac_router = Router()


class FormFac(StatesGroup):
    fac1 = State()   # Yo'nalish tanlash
    fac2 = State()   # Universitet tanlash
    fac3 = State()   # Shakl tanlash → natija
    fac4 = State()   # Orqaga navigatsiya


# ── Doimiy klaviaturalar ─────────────────────────────────────────────────────

SEARCH_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
])

BACK_KB = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[[KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")]]
)


def _main_menu_kb():
    """Asosiy menyuga qaytish."""
    return UserPanels.main_manu()


# ── fac1 — Yo'nalish tanlash ─────────────────────────────────────────────────

@fac_router.message(F.text == "📚 Yoʻnalishlar boʻyicha", F.chat.type == ChatType.PRIVATE)
async def enter_direction(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)
    if not check_status:
        await message.answer("❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
                             reply_markup=await CheckData.channels_btn(channels))
        return

    cursor.execute("SELECT COUNT(*) FROM (SELECT DISTINCT mvdir, nomi FROM mandat) t")
    total = cursor.fetchone()[0]
    await message.answer(
        f"<b>{total} ta yo'nalish mavjud\n\n📚 Ta'lim yo'nalishini tanlang:</b>",
        parse_mode="html", reply_markup=await UserPanels.to_back()
    )
    await message.answer("<b>Tezkor qidiruvdan foydalaning...👇</b>",
                         parse_mode="html", reply_markup=SEARCH_KB)
    await state.set_state(FormFac.fac1)


@fac_router.inline_query(FormFac.fac1)
async def inline_fac1(inline_query: InlineQuery):
    text = inline_query.query.lower()
    if text:
        cursor.execute(
            "SELECT DISTINCT mvdir, nomi FROM mandat WHERE lower(nomi) LIKE %s ORDER BY nomi LIMIT 50",
            (f"%{text}%",)
        )
    else:
        cursor.execute("SELECT DISTINCT mvdir, nomi FROM mandat ORDER BY nomi LIMIT 50")
    results = [
        InlineQueryResultArticle(
            id=f"{mvdir}_{i}",
            title=f"{mvdir} - {nomi}",
            input_message_content=InputTextMessageContent(message_text=f"{mvdir} - {nomi}")
        ) for i, (mvdir, nomi) in enumerate(cursor.fetchall())
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@fac_router.message(FormFac.fac1)
async def chosen_fac1(message: Message, state: FSMContext):
    if message.text in ("🔙 Ortga", "🔙 Bosh menu"):
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.main_manu())
        return

    parts = message.text.split(" - ", 1)
    if len(parts) < 2:
        return
    try:
        mvdir = int(parts[0])
    except ValueError:
        return
    fac_name = parts[1]

    cursor.execute("""
        SELECT COUNT(DISTINCT u.un_id)
        FROM mandat m JOIN universities u ON m.un_id = u.un_id
        WHERE m.mvdir = %s AND m.nomi = %s
    """, (mvdir, fac_name))
    total = cursor.fetchone()[0]
    if not total:
        await message.answer("<b>🤷🏻‍♂️ Bunday yo'nalish topilmadi</b>", parse_mode="html")
        return

    await state.update_data(mvdir=mvdir, fac_name=fac_name)
    await state.set_state(FormFac.fac2)
    await message.answer(
        f"<b>Siz tanlagan yo'nalish {total} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>",
        parse_mode="html", reply_markup=await UserPanels.to_back()
    )
    await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>",
                         parse_mode="html", reply_markup=SEARCH_KB)


# ── fac2 — Universitet tanlash ───────────────────────────────────────────────

@fac_router.inline_query(FormFac.fac2)
async def inline_fac2(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    mvdir, fac_name = data.get("mvdir"), data.get("fac_name")
    base = """
        SELECT u.un_id, u.un_text
        FROM mandat m JOIN universities u ON m.un_id = u.un_id
        WHERE m.mvdir = %s AND m.nomi = %s {f}
        GROUP BY u.un_id, u.un_text ORDER BY u.un_text LIMIT 50
    """
    if text:
        cursor.execute(base.format(f="AND lower(u.un_text) LIKE %s"),
                       (mvdir, fac_name, f"%{text}%"))
    else:
        cursor.execute(base.format(f=""), (mvdir, fac_name))
    results = [
        InlineQueryResultArticle(
            id=str(i),
            title=un_text,
            input_message_content=InputTextMessageContent(message_text=un_text)
        ) for i, (un_id, un_text) in enumerate(cursor.fetchall())
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@fac_router.message(FormFac.fac2)
async def chosen_fac2(message: Message, state: FSMContext):
    if message.text in ("🔙 Ortga", "🔙 Bosh menu"):
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.main_manu())
        return

    cursor.execute("SELECT un_id FROM universities WHERE lower(un_text) = %s",
                   (message.text.lower(),))
    row = cursor.fetchone()
    if not row:
        return
    un_id = row[0]
    await state.update_data(un_id=un_id)
    await state.set_state(FormFac.fac3)

    cursor.execute("SELECT DISTINCT ty_id, ty_text FROM gettypes WHERE un_id = %s ORDER BY ty_text",
                   (un_id,))
    rows = cursor.fetchall()
    if not rows:
        await message.answer("<b>🤷🏻‍♂️ Ta'lim shakli topilmadi</b>", parse_mode="html")
        return

    keyboard = [[KeyboardButton(text=ty_text)] for _, ty_text in rows]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
    await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>",
                         parse_mode="html", reply_markup=SEARCH_KB)


# ── fac3 — Shakl tanlash → natija to'g'ridan-to'g'ri ───────────────────────

@fac_router.inline_query(FormFac.fac3)
async def inline_fac3(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    un_id = data.get("un_id")
    if text:
        cursor.execute(
            "SELECT DISTINCT ty_id, ty_text FROM gettypes WHERE lower(ty_text) LIKE %s AND un_id = %s LIMIT 50",
            (f"%{text}%", un_id)
        )
    else:
        cursor.execute(
            "SELECT DISTINCT ty_id, ty_text FROM gettypes WHERE un_id = %s LIMIT 50", (un_id,)
        )
    results = [
        InlineQueryResultArticle(
            id=str(i),
            title=ty_text,
            input_message_content=InputTextMessageContent(message_text=ty_text)
        ) for i, (ty_id, ty_text) in enumerate(cursor.fetchall())
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@fac_router.message(FormFac.fac3)
async def chosen_fac3(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormFac.fac2)
        data = await state.get_data()
        mvdir, fac_name = data.get("mvdir"), data.get("fac_name")
        cursor.execute("""
            SELECT COUNT(DISTINCT u.un_id)
            FROM mandat m JOIN universities u ON m.un_id = u.un_id
            WHERE m.mvdir = %s AND m.nomi = %s
        """, (mvdir, fac_name))
        total = cursor.fetchone()[0]
        await message.answer(
            f"<b>Siz tanlagan yo'nalish {total} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>",
            parse_mode="html", reply_markup=await UserPanels.to_back()
        )
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>",
                             parse_mode="html", reply_markup=SEARCH_KB)
        return
    if message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.main_manu())
        return

    # Shakl tanlandi — ty_id ni aniqlaymiz
    cursor.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text) = %s", (message.text.lower(),))
    row = cursor.fetchone()
    if not row:
        return
    ty_id = row[0]
    await state.update_data(ty_id=ty_id)
    data = await state.get_data()
    un_id  = str(data["un_id"])
    mvdir  = str(data["mvdir"])
    fac_name = str(data["fac_name"])
    ty_id  = str(ty_id)

    # Barcha tillar bo'yicha natijalarni olamiz (har bir til uchun bitta qator)
    cursor.execute("""
        SELECT DISTINCT ON (m.lan_id)
            m.lan_id, m.gr_b, m.con_b, m.olimp, g.lan_text
        FROM mandat m
        JOIN getlangs g ON m.lan_id = g.lan_id
        WHERE m.un_id = %s AND m.ty_id = %s AND m.mvdir = %s AND m.nomi = %s
        ORDER BY m.lan_id, g.lan_text
    """, (un_id, ty_id, mvdir, fac_name))
    results = cursor.fetchall()

    if not results:
        await message.answer("<b>🤷🏻‍♂️ Bu kombinatsiya bo'yicha ma'lumot topilmadi</b>",
                             parse_mode="html")
        return

    cursor.execute("SELECT un_text FROM universities WHERE un_id = %s", (un_id,))
    un_name_row = cursor.fetchone()
    cursor.execute("SELECT ty_text FROM gettypes WHERE ty_id = %s", (ty_id,))
    ty_text_row = cursor.fetchone()
    un_name = un_name_row[0] if un_name_row else "—"
    ty_text = ty_text_row[0] if ty_text_row else "—"

    # Barcha tillar bo'yicha natijani bitta xabarda ko'rsatamiz
    langs_block = ""
    for _lan_id, gr_b, con_b, olimp, lan_text in results:
        langs_block += (
            f"\n🌐 <b>{lan_text}:</b>\n"
            f"   📈 Grand: <b>{gr_b} ball</b>  |  "
            f"💰 Kontrakt: <b>{con_b} ball</b>  |  "
            f"🏆 Olimp: <b>{olimp}</b>\n"
        )

    message_text = (
        f"<b>🏛 OLIYGOH:</b> {un_name}\n\n"
        f"<b>📚 TAʼLIM YO'NALISHI:</b> {mvdir} - {fac_name}\n\n"
        f"<b>🔰 TAʼLIM SHAKLI:</b> {ty_text}\n\n"
        f"<b>📊 OʻTISH BALLARI (tiller bo'yicha):</b>{langs_block}\n"
        f"<b>© <a href='https://t.me/mandatjavobbot?start=share'>"
        f"@Mandatjavobbot</a> - oʻtish ballari va mandat natijalari</b>"
    )
    await message.answer(message_text, parse_mode="html", reply_markup=BACK_KB)
    await state.set_state(FormFac.fac4)


# ── fac4 — Orqaga navigatsiya ────────────────────────────────────────────────

@fac_router.message(FormFac.fac4)
async def chosen_fac4(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await state.set_state(FormFac.fac3)
        data = await state.get_data()
        un_id = data.get("un_id")
        cursor.execute(
            "SELECT DISTINCT ty_id, ty_text FROM gettypes WHERE un_id = %s ORDER BY ty_text", (un_id,)
        )
        rows = cursor.fetchall()
        keyboard = [[KeyboardButton(text=ty_text)] for _, ty_text in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>",
                             parse_mode="html", reply_markup=btn)
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>",
                             parse_mode="html", reply_markup=SEARCH_KB)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.main_manu())
