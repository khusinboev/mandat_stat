"""
filter_fac.py — Yo'nalish bo'yicha qidirish.

Tuzatilgan muammolar:
  1. Til dublikatlari: DISTINCT ON (lan_id) ishlatildi
  2. COUNT(DISTINCT ...) → subquery bilan to'g'rilandi
  3. Inline handler o'z state iga bog'liq
  4. Eski xabarlar tozalanadi
"""
import hashlib
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
fac_router = Router()

BOT_USERNAME = "mandatjavobbot"


class FormFac(StatesGroup):
    fac1 = State()   # Yo'nalish qidirish
    fac2 = State()   # Universitet tanlash
    fac3 = State()   # Ta'lim shakli
    fac4 = State()   # Ta'lim tili → natija


# ─── YORDAMCHI ─────────────────────────────────────────────────────────

async def _delete_old_msgs(state: FSMContext, chat_id: int):
    data = await state.get_data()
    for mid in data.get("_bot_msgs", []):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass
    await state.update_data(_bot_msgs=[])


async def _track_msg(state: FSMContext, msg: Message):
    data = await state.get_data()
    ids  = data.get("_bot_msgs", [])
    ids.append(msg.message_id)
    await state.update_data(_bot_msgs=ids)


async def _safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


def _get_unique_langs_for_fac(cur, un_id, ty_id):
    """
    ✅ DISTINCT ON (lan_id) — bir xil lan_id uchun faqat bitta lan_text.
    """
    cur.execute("""
        SELECT DISTINCT ON (g.lan_id) g.lan_id, g.lan_text
        FROM mandat mn
        JOIN getlangs g ON mn.lan_id = g.lan_id
        WHERE mn.un_id = %s AND mn.ty_id = %s
        ORDER BY g.lan_id, g.lan_text
    """, (un_id, ty_id))
    return cur.fetchall()


# ═══════════════════════════════════════════════════════════════
#  FAC1 — YO'NALISH QIDIRISH
# ═══════════════════════════════════════════════════════════════

@fac_router.message(F.text == "📚 Yoʻnalishlar boʻyicha", F.chat.type == ChatType.PRIVATE)
async def enter_direction(message: Message, state: FSMContext):
    await _safe_delete(message)
    ok, channels = await CheckData.check_member(bot, message.from_user.id)
    if not ok:
        await message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn(channels),
        )
        return

    await state.clear()

    with db_connection() as (conn, cur):
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT region_id, un_id, ty_id, lan_id, mvdir, nomi
                FROM mandat
            ) sub
        """)
        row_count = cur.fetchone()[0]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    m1 = await message.answer(
        f"<b>{row_count} ta yo'nalish mavjud\n\n📚 Ta'lim yo'nalishini tanlang:</b>",
        parse_mode="html",
        reply_markup=await UserPanels.to_back(),
    )
    m2 = await message.answer(
        "<b>Tezkor qidiruvdan foydalaning...👇</b>",
        parse_mode="html",
        reply_markup=kb,
    )
    await state.set_state(FormFac.fac1)
    await _track_msg(state, m1)
    await _track_msg(state, m2)


@fac_router.inline_query(FormFac.fac1)
async def inline_fac1(inline_query: InlineQuery):
    text = inline_query.query.lower().strip()
    with db_connection() as (conn, cur):
        if text:
            cur.execute(
                "SELECT DISTINCT mvdir, nomi FROM mandat WHERE lower(nomi) LIKE %s ORDER BY nomi",
                (f"%{text}%",)
            )
        else:
            cur.execute("SELECT DISTINCT mvdir, nomi FROM mandat ORDER BY nomi")
        facs = cur.fetchall()[:50]

    results = [
        InlineQueryResultArticle(
            id=hashlib.md5(f"{mvdir}___{nomi}".encode()).hexdigest(),  # ← SHU
            title=f"{mvdir} - {nomi}",
            input_message_content=InputTextMessageContent(
                message_text=f"{mvdir} - {nomi}", parse_mode="HTML"
            ),
        )
        for mvdir, nomi in facs
    ]
    await inline_query.answer(results, cache_time=60, is_personal=False)


@fac_router.message(FormFac.fac1)
async def chosen_fac(message: Message, state: FSMContext):
    await _safe_delete(message)

    if message.text in ("🔙 Ortga", "🔙 Bosh menu"):
        await _delete_old_msgs(state, message.chat.id)
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
    mvdir_str, fac_name = parts[0].strip(), parts[1].strip()

    try:
        mvdir = int(mvdir_str)
    except ValueError:
        return

    with db_connection() as (conn, cur):
        cur.execute("""
            SELECT u.un_id, u.un_text
            FROM mandat mn
            JOIN universities u ON mn.un_id = u.un_id
            WHERE mn.mvdir = %s AND mn.nomi = %s
            GROUP BY u.un_id, u.un_text
            ORDER BY u.un_text
        """, (mvdir, fac_name))
        universities = cur.fetchall()

    if not universities:
        m = await message.answer("<b>🤷🏻‍♂️ Bunday ma'lumot yo'q</b>", parse_mode="html")
        await _track_msg(state, m)
        return

    await _delete_old_msgs(state, message.chat.id)
    await state.update_data(mvdir=mvdir, fac_name=fac_name)
    await state.set_state(FormFac.fac2)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    m1 = await message.answer(
        f"<b>Siz tanlagan yo'nalish {len(universities)} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>",
        parse_mode="html",
        reply_markup=await UserPanels.to_back(),
    )
    m2 = await message.answer(
        "<b>Tezkor qidiruvdan foydalaning...</b>",
        parse_mode="html",
        reply_markup=kb,
    )
    await _track_msg(state, m1)
    await _track_msg(state, m2)


# ═══════════════════════════════════════════════════════════════
#  FAC2 — UNIVERSITET TANLASH  (inline FormFac.fac2 ga bog'liq)
# ═══════════════════════════════════════════════════════════════

@fac_router.inline_query(FormFac.fac2)
async def inline_fac2(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower().strip()
    data = await state.get_data()
    mvdir    = data.get("mvdir")
    fac_name = data.get("fac_name")

    with db_connection() as (conn, cur):
        if text:
            cur.execute("""
                SELECT u.un_id, u.un_text
                FROM mandat mn JOIN universities u ON mn.un_id = u.un_id
                WHERE mn.mvdir = %s AND mn.nomi = %s AND lower(u.un_text) LIKE %s
                GROUP BY u.un_id, u.un_text ORDER BY u.un_text
            """, (mvdir, fac_name, f"%{text}%"))
        else:
            cur.execute("""
                SELECT u.un_id, u.un_text
                FROM mandat mn JOIN universities u ON mn.un_id = u.un_id
                WHERE mn.mvdir = %s AND mn.nomi = %s
                GROUP BY u.un_id, u.un_text ORDER BY u.un_text
            """, (mvdir, fac_name))
        universities = cur.fetchall()[:50]

    results = [
        InlineQueryResultArticle(
            id=str(un_id),
            title=un_text,
            input_message_content=InputTextMessageContent(message_text=un_text),
        )
        for un_id, un_text in universities
    ]
    await inline_query.answer(results, cache_time=60, is_personal=False)


@fac_router.message(FormFac.fac2)
async def chosen_university(message: Message, state: FSMContext):
    await _safe_delete(message)

    if message.text in ("🔙 Ortga", "🔙 Bosh menu"):
        await _delete_old_msgs(state, message.chat.id)
        await state.set_state(FormFac.fac1)

        with db_connection() as (conn, cur):
            cur.execute("""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT region_id, un_id, ty_id, lan_id, mvdir, nomi
                    FROM mandat
                ) sub
            """)
            row_count = cur.fetchone()[0]

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        m1 = await message.answer(
            f"<b>{row_count} ta yo'nalish\n\n📚 Ta'lim yo'nalishini tanlang:</b>",
            parse_mode="html",
            reply_markup=await UserPanels.to_back(),
        )
        m2 = await message.answer(
            "<b>Tezkor qidiruvdan foydalaning...👇</b>",
            parse_mode="html",
            reply_markup=kb,
        )
        await _track_msg(state, m1)
        await _track_msg(state, m2)
        return

    name = message.text.lower()
    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT un_id FROM universities WHERE lower(un_text) = %s",
            (name,)
        )
        row = cur.fetchone()
        if not row:
            return
        un_id = row[0]

        cur.execute(
            "SELECT DISTINCT ty_id, ty_text FROM gettypes WHERE un_id = %s ORDER BY ty_text",
            (un_id,)
        )
        types = cur.fetchall()

    await _delete_old_msgs(state, message.chat.id)
    await state.update_data(un_id=un_id)
    await state.set_state(FormFac.fac3)

    keyboard = [[KeyboardButton(text=ty_text)] for _, ty_text in types]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    m = await message.answer(
        "<b>🔰 Ta'lim shaklini tanlang: 👇</b>",
        parse_mode="html",
        reply_markup=btn,
    )
    await _track_msg(state, m)


# ═══════════════════════════════════════════════════════════════
#  FAC3 — TA'LIM SHAKLI  (inline FormFac.fac3 ga bog'liq)
# ═══════════════════════════════════════════════════════════════

@fac_router.inline_query(FormFac.fac3)
async def inline_fac3(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower().strip()
    data = await state.get_data()
    un_id = data.get("un_id")

    with db_connection() as (conn, cur):
        if text:
            cur.execute(
                "SELECT ty_id, ty_text FROM gettypes WHERE lower(ty_text) LIKE %s AND un_id = %s",
                (f"%{text}%", un_id)
            )
        else:
            cur.execute(
                "SELECT DISTINCT ty_id, ty_text FROM gettypes WHERE un_id = %s ORDER BY ty_text",
                (un_id,)
            )
        types = cur.fetchall()[:50]

    results = [
        InlineQueryResultArticle(
            id=str(ty_id),
            title=ty_text,
            input_message_content=InputTextMessageContent(message_text=ty_text),
        )
        for ty_id, ty_text in types
    ]
    await inline_query.answer(results, cache_time=60, is_personal=False)


@fac_router.message(FormFac.fac3)
async def chosen_type(message: Message, state: FSMContext):
    await _safe_delete(message)

    if message.text == "🔙 Ortga":
        await _delete_old_msgs(state, message.chat.id)
        data     = await state.get_data()
        mvdir    = data.get("mvdir")
        fac_name = data.get("fac_name")

        with db_connection() as (conn, cur):
            cur.execute("""
                SELECT COUNT(DISTINCT u.un_id)
                FROM mandat mn
                JOIN universities u ON mn.un_id = u.un_id
                WHERE mn.mvdir = %s AND mn.nomi = %s
            """, (mvdir, fac_name))
            count = cur.fetchone()[0]

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        await state.set_state(FormFac.fac2)
        m1 = await message.answer(
            f"<b>{count} ta oliygoh mavjud\n\n🏢 OTMni tanlang:</b>",
            parse_mode="html",
            reply_markup=await UserPanels.to_back(),
        )
        m2 = await message.answer(
            "<b>Tezkor qidiruvdan foydalaning...</b>",
            parse_mode="html",
            reply_markup=kb,
        )
        await _track_msg(state, m1)
        await _track_msg(state, m2)
        return

    if message.text == "🔙 Bosh menu":
        await _delete_old_msgs(state, message.chat.id)
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang 👇</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    name = message.text.lower()
    data  = await state.get_data()
    un_id = data["un_id"]

    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT ty_id FROM gettypes WHERE lower(ty_text) = %s AND un_id = %s LIMIT 1",
            (name, un_id)
        )
        row = cur.fetchone()
        if not row:
            return
        ty_id = row[0]

        # ✅ TUZATILDI: DISTINCT ON (lan_id)
        langs = _get_unique_langs_for_fac(cur, un_id, ty_id)

    await _delete_old_msgs(state, message.chat.id)
    await state.update_data(ty_id=ty_id)
    await state.set_state(FormFac.fac4)

    keyboard = [[KeyboardButton(text=lan_text[:60])] for _, lan_text in langs]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    m = await message.answer(
        "<b>🇺🇿 Ta'lim tilini tanlang:</b>",
        parse_mode="html",
        reply_markup=btn,
    )
    await _track_msg(state, m)


# ═══════════════════════════════════════════════════════════════
#  FAC4 — TA'LIM TILI → NATIJA
# ═══════════════════════════════════════════════════════════════

@fac_router.message(FormFac.fac4)
async def chosen_lang(message: Message, state: FSMContext):
    await _safe_delete(message)

    if message.text == "🔙 Ortga":
        await _delete_old_msgs(state, message.chat.id)
        data  = await state.get_data()
        un_id = data["un_id"]
        ty_id = data["ty_id"]

        with db_connection() as (conn, cur):
            langs = _get_unique_langs_for_fac(cur, un_id, ty_id)

        keyboard = [[KeyboardButton(text=lan_text[:60])] for _, lan_text in langs]

        with db_connection() as (conn, cur):
            cur.execute(
                "SELECT DISTINCT ty_id, ty_text FROM gettypes WHERE un_id = %s ORDER BY ty_text",
                (un_id,)
            )
            types = cur.fetchall()

        keyboard_types = [[KeyboardButton(text=ty_text)] for _, ty_text in types]
        keyboard_types.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard_types, resize_keyboard=True)
        await state.set_state(FormFac.fac3)
        m = await message.answer(
            "<b>🔰 Ta'lim shaklini tanlang: 👇</b>",
            parse_mode="html",
            reply_markup=btn,
        )
        await _track_msg(state, m)
        return

    if message.text == "🔙 Bosh menu":
        await _delete_old_msgs(state, message.chat.id)
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang 👇</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    lan_text_input = message.text.lower()
    # ✅ TUZATILDI: DISTINCT ON (lan_id)
    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT DISTINCT ON (lan_id) lan_id FROM getlangs WHERE lower(lan_text) = %s ORDER BY lan_id",
            (lan_text_input,)
        )
        row = cur.fetchone()
        if not row:
            return
        lan_id = row[0]

    data     = await state.get_data()
    un_id    = str(data["un_id"])
    ty_id    = str(data["ty_id"])
    mvdir    = str(data["mvdir"])
    fac_name = str(data["fac_name"])

    with db_connection() as (conn, cur):
        cur.execute("SELECT un_text FROM universities WHERE un_id = %s", (un_id,))
        un_name_row  = cur.fetchone()
        # ✅ TUZATILDI
        cur.execute(
            "SELECT DISTINCT ON (lan_id) lan_text FROM getlangs WHERE lan_id = %s ORDER BY lan_id",
            (lan_id,)
        )
        lan_text_row = cur.fetchone()
        cur.execute("SELECT ty_text FROM gettypes WHERE ty_id = %s LIMIT 1", (ty_id,))
        ty_text_row  = cur.fetchone()
        cur.execute("""
            SELECT mvdir, nomi, gr_b, con_b, olimp FROM mandat
            WHERE un_id = %s AND ty_id = %s AND lan_id = %s AND mvdir = %s AND nomi = %s
        """, (un_id, ty_id, lan_id, mvdir, fac_name))
        kayp = cur.fetchone()

    if not kayp:
        m = await message.answer("<b>🤷🏻‍♂️ Bunday ma'lumot yo'q</b>", parse_mode="html")
        await _track_msg(state, m)
        return

    mv, nomi, gr_b, con_b, olimp = kayp
    un_name  = un_name_row[0]  if un_name_row  else "—"
    lan_text = lan_text_row[0] if lan_text_row else "—"
    ty_text  = ty_text_row[0]  if ty_text_row  else "—"

    msg_text = (
        f"<b>🏛 OLIYGOH:</b> {un_name}\n\n"
        f"<b>📚 TAʼLIM YO'NALISHI</b> — {mv} - {nomi}\n\n"
        f"<b>🇺🇿 TAʼLIM TILI</b> — {lan_text}\n\n"
        f"<b>🔰 TAʼLIM SHAKLI</b> — {ty_text}\n\n"
        f"<b>📈 OʻTISH BALLARI:</b>\n"
        f"<b>Grand</b> — {gr_b} ball | <b>Kontrakt</b> — {con_b} ball\n\n"
        f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
        f"<b>© <a href='https://t.me/{BOT_USERNAME}?start=share'>@{BOT_USERNAME}</a> "
        "— oʻtish ballari va mandat natijalari</b>"
    )

    await _delete_old_msgs(state, message.chat.id)

    user_id = message.from_user.id
    await _send_card(
        message, msg_text,
        un_id, ty_id, lan_id, str(mv), user_id,
        un_name, f"{mv} - {nomi}", lan_text, ty_text, gr_b, con_b, olimp
    )


async def _send_card(
    message: Message, msg_text: str,
    un_id, ty_id, lan_id, mvdir,
    user_id, univer, faculty, lang, edu, grand, kont, olmp,
):
    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT file_id FROM photos WHERE un_id = %s AND ty_id = %s AND lan_id = %s AND mvdir = %s",
            (un_id, ty_id, lan_id, str(mvdir))
        )
        old = cur.fetchone()

    if old:
        await message.answer_photo(photo=old[0], caption=msg_text, parse_mode="html")
        return

    if create_card(
        univer=univer, faculty=faculty, lang=lang, edu=edu,
        grand=grand, kont=kont, olmp=olmp, name=user_id
    ):
        CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(CURRENT_DIR, "photos", f"{user_id}.jpg")
        try:
            sent = await message.answer_photo(
                photo=FSInputFile(path), caption=msg_text, parse_mode="html"
            )
            file_id = sent.photo[-1].file_id
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO photos (un_id, ty_id, lan_id, mvdir, file_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (un_id, ty_id, lan_id, mvdir) DO NOTHING
                """, (un_id, ty_id, lan_id, str(mvdir), file_id))
        finally:
            if os.path.exists(path):
                os.remove(path)
    else:
        await message.answer(msg_text, parse_mode="html")