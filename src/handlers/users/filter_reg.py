import os
import logging

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    KeyboardButton, ReplyKeyboardMarkup, FSInputFile
)

from config import bot, db_connection
from src.handlers.users.users import create_card
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

logger = logging.getLogger(__name__)
reg_router = Router()

BOT_USERNAME = "mandatjavobbot"


class FormReg(StatesGroup):
    reg1 = State()
    reg2 = State()
    reg3 = State()
    reg4 = State()
    reg5 = State()


# ═══════════════════════════════════════════════════════════════
#  REG1 — HUDUD TANLASH
# ═══════════════════════════════════════════════════════════════

@reg_router.message(F.text == "📈 Viloyatlar kesimida", F.chat.type == ChatType.PRIVATE)
async def enter_direction(message: Message, state: FSMContext):
    ok, channels = await CheckData.check_member(bot, message.from_user.id)
    if not ok:
        await message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn(channels),
        )
        return

    with db_connection() as (conn, cur):
        cur.execute("SELECT region_id, region_name FROM regions ORDER BY region_name")
        rows = cur.fetchall()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    keyboard = [[KeyboardButton(text=region_name)] for _, region_name in rows]
    keyboard.append([KeyboardButton(text="🔙 Ortga")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    await message.answer("<b>📍 Hududni tanlang:</b>", parse_mode="html", reply_markup=btn)
    await message.answer("<b>Tezkor qidiruvdan foydalaning...👇</b>", parse_mode="html", reply_markup=kb)
    await state.set_state(FormReg.reg1)


@reg_router.inline_query(FormReg.reg1)
async def inline_reg1(inline_query: InlineQuery):
    text = inline_query.query.lower().strip()
    with db_connection() as (conn, cur):
        if text:
            cur.execute(
                "SELECT id, region_id, region_name FROM regions WHERE lower(region_name) LIKE %s",
                (f"%{text}%",)
            )
        else:
            cur.execute("SELECT id, region_id, region_name FROM regions")
        rows = cur.fetchall()

    results = [
        InlineQueryResultArticle(
            id=str(rid),
            title=region_name,
            input_message_content=InputTextMessageContent(
                message_text=region_name, parse_mode="HTML"
            ),
        )
        for rid, region_id, region_name in rows
    ]
    await inline_query.answer(results, cache_time=300, is_personal=False)


@reg_router.message(FormReg.reg1)
async def chosen_region(message: Message, state: FSMContext):
    if message.text in ("🔙 Ortga", "🔙 Bosh menu"):
        await message.delete()
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang 👇</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    region_name = message.text
    with db_connection() as (conn, cur):
        cur.execute("SELECT region_id FROM regions WHERE region_name = %s", (region_name,))
        row = cur.fetchone()
        if not row:
            return
        region_id = row[0]

        cur.execute("""
            SELECT u.un_text FROM regions r
            JOIN universities u ON r.region_id = u.region_id
            WHERE r.region_name = %s ORDER BY u.un_text
        """, (region_name,))
        universities = cur.fetchall()

    if not universities:
        await message.answer("<b>🤷🏻‍♂️ Bu hududda oliygoh topilmadi</b>", parse_mode="html")
        return

    await state.update_data(region_name=region_name, region_id=region_id)
    await state.set_state(FormReg.reg2)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    keyboard = [[KeyboardButton(text=un_text)] for (un_text,) in universities]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    await message.answer(
        f"<b>Siz tanlagan hududda {len(universities)} ta oliygoh mavjud\n\n🏢 OTMni tanlang:</b>",
        parse_mode="html",
        reply_markup=btn,
    )
    await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)


# ═══════════════════════════════════════════════════════════════
#  REG2 — UNIVERSITET TANLASH
# ═══════════════════════════════════════════════════════════════

@reg_router.inline_query(FormReg.reg2)
async def inline_reg2(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower().strip()
    data = await state.get_data()
    region_name = data.get("region_name")

    with db_connection() as (conn, cur):
        if text:
            cur.execute("""
                SELECT u.id, u.un_text FROM regions r
                JOIN universities u ON r.region_id = u.region_id
                WHERE r.region_name = %s AND lower(u.un_text) LIKE %s
                ORDER BY u.un_text
            """, (region_name, f"%{text}%"))
        else:
            cur.execute("""
                SELECT u.id, u.un_text FROM regions r
                JOIN universities u ON r.region_id = u.region_id
                WHERE r.region_name = %s ORDER BY u.un_text
            """, (region_name,))
        universities = list(dict.fromkeys(cur.fetchall()))[:50]

    results = [
        InlineQueryResultArticle(
            id=str(un_id),
            title=un_text,
            input_message_content=InputTextMessageContent(message_text=un_text),
        )
        for un_id, un_text in universities
    ]
    await inline_query.answer(results, cache_time=60, is_personal=False)


@reg_router.message(FormReg.reg2)
async def chosen_university(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        with db_connection() as (conn, cur):
            cur.execute("SELECT region_id, region_name FROM regions ORDER BY region_name")
            rows = cur.fetchall()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        keyboard = [[KeyboardButton(text=rn)] for _, rn in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>📍 Hududni tanlang:</b>", parse_mode="html", reply_markup=btn)
        await message.answer("<b>Tezkor qidiruvdan foydalaning...👇</b>", parse_mode="html", reply_markup=kb)
        await state.set_state(FormReg.reg1)
        return

    if message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang 👇</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    un_name = message.text
    with db_connection() as (conn, cur):
        cur.execute("SELECT un_id FROM universities WHERE lower(un_text) = %s", (un_name.lower(),))
        row = cur.fetchone()
        if not row:
            return
        un_id = row[0]

        data      = await state.get_data()
        region_id = data.get("region_id")
        cur.execute(
            "SELECT ty_id, ty_text FROM gettypes WHERE region_id = %s AND un_id = %s",
            (region_id, un_id)
        )
        types = cur.fetchall()

    if not types:
        await message.answer("<b>🤷🏻‍♂️ Ta'lim shakllari topilmadi</b>", parse_mode="html")
        return

    await state.update_data(un_id=un_id)
    await state.set_state(FormReg.reg3)

    keyboard = [[KeyboardButton(text=ty_text)] for _, ty_text in types]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)


# ═══════════════════════════════════════════════════════════════
#  REG3 — TA'LIM SHAKLI
# ═══════════════════════════════════════════════════════════════

@reg_router.message(FormReg.reg3)
async def chosen_type(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg2)
        data    = await state.get_data()
        region_name = data.get("region_name")
        with db_connection() as (conn, cur):
            cur.execute("""
                SELECT u.un_text FROM regions r
                JOIN universities u ON r.region_id = u.region_id
                WHERE r.region_name = %s ORDER BY u.un_text
            """, (region_name,))
            universities = cur.fetchall()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        keyboard = [[KeyboardButton(text=un_text)] for (un_text,) in universities]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer(
            f"<b>{len(universities)} ta oliygoh\n\n🏢 OTMni tanlang:</b>",
            parse_mode="html", reply_markup=btn
        )
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
        return

    if message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang 👇</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    name = message.text.lower()
    with db_connection() as (conn, cur):
        cur.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text) = %s", (name,))
        row = cur.fetchone()
        if not row:
            return
        ty_id = row[0]

        data  = await state.get_data()
        un_id = data.get("un_id")
        cur.execute("""
            SELECT DISTINCT g.lan_id, g.lan_text FROM mandat m
            JOIN getlangs g ON m.lan_id = g.lan_id
            WHERE m.un_id = %s AND m.ty_id = %s
        """, (un_id, ty_id))
        langs = cur.fetchall()

    await state.update_data(ty_id=ty_id)
    await state.set_state(FormReg.reg4)

    keyboard = [[KeyboardButton(text=lan_text[:60])] for _, lan_text in langs]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)


# ═══════════════════════════════════════════════════════════════
#  REG4 — TA'LIM TILI
# ═══════════════════════════════════════════════════════════════

@reg_router.message(FormReg.reg4)
async def chosen_lang(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg3)
        data  = await state.get_data()
        un_id = data.get("un_id")
        region_id = data.get("region_id")
        with db_connection() as (conn, cur):
            cur.execute(
                "SELECT ty_id, ty_text FROM gettypes WHERE region_id = %s AND un_id = %s",
                (region_id, un_id)
            )
            types = cur.fetchall()
        keyboard = [[KeyboardButton(text=ty_text)] for _, ty_text in types]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
        return

    if message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang 👇</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    lan_text_input = message.text.lower()
    with db_connection() as (conn, cur):
        cur.execute("SELECT lan_id FROM getlangs WHERE lower(lan_text) = %s", (lan_text_input,))
        row = cur.fetchone()
        if not row:
            return
        lan_id = row[0]

    data      = await state.get_data()
    region_id = data["region_id"]
    un_id     = data["un_id"]
    ty_id     = data["ty_id"]

    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT mvdir, nomi FROM mandat WHERE region_id = %s AND un_id = %s AND ty_id = %s AND lan_id = %s",
            (region_id, un_id, ty_id, lan_id)
        )
        rows = cur.fetchall()

    await state.update_data(lan_id=lan_id)
    await state.set_state(FormReg.reg5)

    keyboard = [[KeyboardButton(text=f"{mvdir} - {nomi}")] for mvdir, nomi in rows]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    await message.answer(
        f"{len(rows)} ta yo'nalish mavjud:\n📚 Ta'lim yo'nalishini tanlang:",
        parse_mode="html",
        reply_markup=btn,
    )
    await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)


# ═══════════════════════════════════════════════════════════════
#  REG5 — YO'NALISH TANLASH VA NATIJA
# ═══════════════════════════════════════════════════════════════

@reg_router.inline_query(FormReg.reg5)
async def inline_reg5(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower().strip()
    data = await state.get_data()
    region_id = data["region_id"]
    un_id     = data["un_id"]
    ty_id     = data["ty_id"]
    lan_id    = data["lan_id"]

    with db_connection() as (conn, cur):
        if text:
            cur.execute("""
                SELECT id, mvdir, nomi FROM mandat
                WHERE lower(nomi) LIKE %s AND region_id = %s AND un_id = %s
                AND ty_id = %s AND lan_id = %s
            """, (f"%{text}%", region_id, un_id, ty_id, lan_id))
        else:
            cur.execute("""
                SELECT id, mvdir, nomi FROM mandat
                WHERE region_id = %s AND un_id = %s AND ty_id = %s AND lan_id = %s
            """, (region_id, un_id, ty_id, lan_id))
        facs = list(dict.fromkeys(cur.fetchall()))[:50]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    results = [
        InlineQueryResultArticle(
            id=str(fac_id),
            title=f"{mvdir} - {nomi}",
            input_message_content=InputTextMessageContent(
                message_text=f"{mvdir} - {nomi}", parse_mode="HTML"
            ),
            reply_markup=kb,
        )
        for fac_id, mvdir, nomi in facs
    ]
    await inline_query.answer(results, cache_time=60, is_personal=False)


@reg_router.message(FormReg.reg5)
async def chosen_direction(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg4)
        data  = await state.get_data()
        un_id = data.get("un_id")
        ty_id = data.get("ty_id")
        with db_connection() as (conn, cur):
            cur.execute("""
                SELECT DISTINCT g.lan_id, g.lan_text FROM mandat m
                JOIN getlangs g ON m.lan_id = g.lan_id
                WHERE m.un_id = %s AND m.ty_id = %s
            """, (un_id, ty_id))
            langs = cur.fetchall()
        keyboard = [[KeyboardButton(text=lan_text[:60])] for _, lan_text in langs]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)
        return

    if message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang 👇</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    parts = message.text.split(" - ", 1)
    if len(parts) < 2:
        return
    mvdir, nomi = parts[0].strip(), parts[1].strip()

    data      = await state.get_data()
    un_id     = data["un_id"]
    ty_id     = data["ty_id"]
    lan_id    = data["lan_id"]

    with db_connection() as (conn, cur):
        cur.execute("SELECT un_text  FROM universities WHERE un_id = %s", (un_id,))
        un_name_row  = cur.fetchone()
        cur.execute("SELECT lan_text FROM getlangs    WHERE lan_id = %s", (lan_id,))
        lan_text_row = cur.fetchone()
        cur.execute("SELECT ty_text  FROM gettypes    WHERE ty_id  = %s", (ty_id,))
        ty_text_row  = cur.fetchone()
        cur.execute("""
            SELECT gr_b, con_b, olimp FROM mandat
            WHERE un_id = %s AND ty_id = %s AND lan_id = %s AND mvdir = %s AND nomi = %s
        """, (un_id, ty_id, lan_id, mvdir, nomi))
        result = cur.fetchone()

    if not result:
        await message.answer("<b>🤷🏻‍♂️ Ma'lumot topilmadi</b>", parse_mode="html")
        return

    gr_b, con_b, olimp = result
    un_name  = un_name_row[0]  if un_name_row  else "—"
    lan_text = lan_text_row[0] if lan_text_row else "—"
    ty_text  = ty_text_row[0]  if ty_text_row  else "—"

    msg_text = (
        f"<b>🏛 OLIYGOH:</b> {un_name}\n\n"
        f"<b>📚 TAʼLIM YO'NALISHI</b> — {mvdir} - {nomi}\n\n"
        f"<b>🇺🇿 TAʼLIM TILI</b> — {lan_text}\n\n"
        f"<b>🔰 TAʼLIM SHAKLI</b> — {ty_text}\n\n"
        f"<b>📈 OʻTISH BALLARI:</b>\n"
        f"<b>Grand</b> — {gr_b} ball | <b>Kontrakt</b> — {con_b} ball\n\n"
        f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
        f"<b>© <a href='https://t.me/{BOT_USERNAME}?start=share'>@{BOT_USERNAME}</a> "
        "— oʻtish ballari va mandat natijalari</b>"
    )

    user_id = message.from_user.id
    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT file_id FROM photos WHERE un_id = %s AND ty_id = %s AND lan_id = %s AND mvdir = %s",
            (un_id, ty_id, lan_id, mvdir)
        )
        old = cur.fetchone()

    if old:
        await message.answer_photo(photo=old[0], caption=msg_text, parse_mode="html")
        return

    if create_card(univer=un_name, faculty=f"{mvdir} - {nomi}", lang=lan_text, edu=ty_text,
                   grand=gr_b, kont=con_b, olmp=olimp, name=user_id):
        CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
        file_path   = os.path.join(CURRENT_DIR, "photos", f"{user_id}.jpg")
        try:
            sent    = await message.answer_photo(photo=FSInputFile(file_path), caption=msg_text, parse_mode="html")
            file_id = sent.photo[-1].file_id
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO photos (un_id, ty_id, lan_id, mvdir, file_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (un_id, ty_id, lan_id, mvdir) DO NOTHING
                """, (un_id, ty_id, lan_id, mvdir, file_id))
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    else:
        await message.answer(msg_text, parse_mode="html")
