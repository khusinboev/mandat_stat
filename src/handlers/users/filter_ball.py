"""
filter_ball.py — Ball bo'yicha yo'nalish qidirish.

Tuzatilgan muammolar:
  1. SQL alias xatosi: "m.con_b" → to'g'ri alias bilan subquery
  2. Inline query handler o'z state iga bog'liq — boshqa stepda ishlamaydi
  3. Har bir stepda eski xabarlar o'chiriladi (msg_id state da saqlanadi)
  4. COUNT(DISTINCT ...) to'g'ri yozildi
"""
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
ball_router = Router()

BOT_USERNAME = "mandatjavobbot"


class FormBall(StatesGroup):
    ball1   = State()   # Grand / Kontrakt tanlash
    s_ball1 = State()   # Ball kiritish
    ball2   = State()   # Hudud tanlash
    ball3   = State()   # Universitet tanlash
    ball4   = State()   # Ta'lim shakli
    ball5   = State()   # Ta'lim tili
    ball6   = State()   # Yo'nalish va natija


# ─── YORDAMCHI FUNKSIYALAR ─────────────────────────────────────────────

def _ball_condition(shakl: str) -> str:
    """
    SQL WHERE sharti — alias ishlatilmaydi, to'g'ridan-to'g'ri ustun nomi.
    """
    if shakl == "gr":
        return "gr_b <= %s AND gr_b != 0 AND ty_id = '1'"
    return "con_b <= %s AND con_b != 0"


async def _delete_old_msgs(state: FSMContext, chat_id: int):
    """State da saqlangan eski bot xabarlarini o'chiradi."""
    data = await state.get_data()
    old_ids: list = data.get("_bot_msgs", [])
    for mid in old_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass
    await state.update_data(_bot_msgs=[])


async def _track_msg(state: FSMContext, msg: Message):
    """Yangi bot xabarini state ga qo'shadi."""
    data = await state.get_data()
    old_ids: list = data.get("_bot_msgs", [])
    old_ids.append(msg.message_id)
    await state.update_data(_bot_msgs=old_ids)


async def _safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
#  KIRISH — Grand / Kontrakt tanlash
# ═══════════════════════════════════════════════════════════════

@ball_router.message(F.text == "📊 Ball yetadigan yo'nalishlar", F.chat.type == ChatType.PRIVATE)
async def enter_ball_menu(message: Message, state: FSMContext):
    await _safe_delete(message)
    ok, channels = await CheckData.check_member(bot, message.from_user.id)
    if not ok:
        m = await message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn(channels),
        )
        return

    await state.clear()
    m = await message.answer(
        "<b>O'quv turini tanlang 👇</b>",
        parse_mode="html",
        reply_markup=await UserPanels.ball_btn(),
    )
    await state.set_state(FormBall.ball1)
    await _track_msg(state, m)


@ball_router.message(F.text.in_({"🏆 Grand", "📄 Kontrakt"}), FormBall.ball1)
async def choose_type(message: Message, state: FSMContext):
    await _safe_delete(message)
    await _delete_old_msgs(state, message.chat.id)

    shakl = "gr" if message.text == "🏆 Grand" else "kn"
    await state.update_data(shakl=shakl)
    await state.set_state(FormBall.s_ball1)

    m = await message.answer(
        "<b>Saralash uchun ballni kiriting:</b>",
        parse_mode="html",
        reply_markup=await UserPanels.to_back(),
    )
    await _track_msg(state, m)


# ═══════════════════════════════════════════════════════════════
#  S_BALL1 — Ball kiritish
# ═══════════════════════════════════════════════════════════════

@ball_router.message(FormBall.s_ball1)
async def enter_ball(message: Message, state: FSMContext):
    await _safe_delete(message)

    if message.text == "🔙 Ortga":
        await _delete_old_msgs(state, message.chat.id)
        await state.set_state(FormBall.ball1)
        m = await message.answer(
            "<b>O'quv turini tanlang 👇</b>",
            parse_mode="html",
            reply_markup=await UserPanels.ball_btn(),
        )
        await _track_msg(state, m)
        return

    if message.text == "🔙 Bosh menu":
        await _delete_old_msgs(state, message.chat.id)
        await state.clear()
        m = await message.answer(
            "<b>Quyidagi menulardan birini tanlang 👇</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    if not message.text or not message.text.isdigit():
        m = await message.answer(
            "<b>Ball xato kiritildi! Faqat son kiriting:</b>",
            parse_mode="html",
            reply_markup=await UserPanels.to_back(),
        )
        await _track_msg(state, m)
        return

    ball = int(message.text)
    if ball > 200:
        m = await message.answer(
            "<b>Ball 200 dan oshmasligi kerak!</b>",
            parse_mode="html",
            reply_markup=await UserPanels.to_back(),
        )
        await _track_msg(state, m)
        return

    data  = await state.get_data()
    shakl = data["shakl"]
    cond  = _ball_condition(shakl)

    with db_connection() as (conn, cur):
        cur.execute(f"""
            SELECT DISTINCT r.region_name
            FROM mandat mn
            JOIN regions r ON mn.region_id = r.region_id
            WHERE {cond}
        """, (ball,))
        regions = cur.fetchall()

    if not regions:
        m = await message.answer(
            "<b>🤷🏻‍♂️ Bu ball bilan hech qaysi yo'nalish topilmadi</b>",
            parse_mode="html",
        )
        await _track_msg(state, m)
        m2 = await message.answer(
            "<b>Saralash uchun ballni kiriting:</b>",
            parse_mode="html",
            reply_markup=await UserPanels.to_back(),
        )
        await _track_msg(state, m2)
        return

    await _delete_old_msgs(state, message.chat.id)
    await state.update_data(ball=ball)
    await state.set_state(FormBall.ball2)

    keyboard = [[KeyboardButton(text=rn)] for (rn,) in regions]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])

    m1 = await message.answer(
        f"Bu ball bilan <b>{len(regions)}</b> ta hududdagi oliygohga kirish mumkin!\n\n"
        "<b>📍 Hududni tanlang:</b>",
        parse_mode="html",
        reply_markup=btn,
    )
    m2 = await message.answer(
        "<b>Tezkor qidiruvdan foydalaning...</b>",
        parse_mode="html",
        reply_markup=kb,
    )
    await _track_msg(state, m1)
    await _track_msg(state, m2)


# ═══════════════════════════════════════════════════════════════
#  BALL2 — Hudud tanlash  (inline FormBall.ball2 ga bog'liq)
# ═══════════════════════════════════════════════════════════════

@ball_router.inline_query(FormBall.ball2)
async def inline_ball2(inline_query: InlineQuery, state: FSMContext):
    text  = inline_query.query.lower().strip()
    data  = await state.get_data()
    shakl = data.get("shakl", "gr")
    ball  = data.get("ball", 0)
    cond  = _ball_condition(shakl)

    with db_connection() as (conn, cur):
        if text:
            cur.execute(f"""
                SELECT DISTINCT r.id, r.region_name
                FROM mandat mn
                JOIN regions r ON mn.region_id = r.region_id
                WHERE lower(r.region_name) LIKE %s AND {cond}
            """, (f"%{text}%", ball))
        else:
            cur.execute(f"""
                SELECT DISTINCT r.id, r.region_name
                FROM mandat mn
                JOIN regions r ON mn.region_id = r.region_id
                WHERE {cond}
            """, (ball,))
        regions = list(dict.fromkeys(cur.fetchall()))[:50]

    results = [
        InlineQueryResultArticle(
            id=str(rid),
            title=rn,
            input_message_content=InputTextMessageContent(message_text=rn),
        )
        for rid, rn in regions
    ]
    await inline_query.answer(results, cache_time=30, is_personal=True)


@ball_router.message(FormBall.ball2)
async def chosen_region(message: Message, state: FSMContext):
    await _safe_delete(message)

    if message.text == "🔙 Ortga":
        await _delete_old_msgs(state, message.chat.id)
        data  = await state.get_data()
        shakl = data["shakl"]
        ball  = data["ball"]
        cond  = _ball_condition(shakl)
        await state.set_state(FormBall.s_ball1)
        m = await message.answer(
            "<b>Saralash uchun ballni kiriting:</b>",
            parse_mode="html",
            reply_markup=await UserPanels.to_back(),
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

    reg_name = message.text
    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT region_id FROM regions WHERE lower(region_name) = %s",
            (reg_name.lower(),)
        )
        row = cur.fetchone()
        if not row:
            return
        reg_id = row[0]

    data  = await state.get_data()
    shakl = data["shakl"]
    ball  = data["ball"]
    cond  = _ball_condition(shakl)

    with db_connection() as (conn, cur):
        cur.execute(f"""
            SELECT COUNT(DISTINCT u.un_id)
            FROM universities u
            JOIN mandat mn ON u.un_id = mn.un_id AND u.region_id = mn.region_id
            WHERE mn.region_id = %s AND {cond}
        """, (reg_id, ball))
        count = cur.fetchone()[0]

    await _delete_old_msgs(state, message.chat.id)
    await state.update_data(reg_id=reg_id)
    await state.set_state(FormBall.ball3)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    m1 = await message.answer(
        f"<b>Siz tanlagan hududda {count} ta oliygoh mavjud:\n🏢 OTMni tanlang:</b>",
        parse_mode="html",
        reply_markup=await UserPanels.to_back(),
    )
    m2 = await message.answer(
        "<b>Tezkor qidiruvdan foydalaning... 👇</b>",
        parse_mode="html",
        reply_markup=kb,
    )
    await _track_msg(state, m1)
    await _track_msg(state, m2)


# ═══════════════════════════════════════════════════════════════
#  BALL3 — Universitet tanlash  (inline FormBall.ball3 ga bog'liq)
# ═══════════════════════════════════════════════════════════════

@ball_router.inline_query(FormBall.ball3)
async def inline_ball3(inline_query: InlineQuery, state: FSMContext):
    text   = inline_query.query.lower().strip()
    data   = await state.get_data()
    reg_id = data.get("reg_id")
    shakl  = data.get("shakl", "gr")
    ball   = data.get("ball", 0)
    cond   = _ball_condition(shakl)

    with db_connection() as (conn, cur):
        if text:
            cur.execute(f"""
                SELECT DISTINCT u.un_id, u.un_text
                FROM universities u
                JOIN mandat mn ON u.un_id = mn.un_id AND u.region_id = mn.region_id
                WHERE lower(u.un_text) LIKE %s AND mn.region_id = %s AND {cond}
            """, (f"%{text}%", reg_id, ball))
        else:
            cur.execute(f"""
                SELECT DISTINCT u.un_id, u.un_text
                FROM universities u
                JOIN mandat mn ON u.un_id = mn.un_id AND u.region_id = mn.region_id
                WHERE mn.region_id = %s AND {cond}
            """, (reg_id, ball))
        universities = list(dict.fromkeys(cur.fetchall()))[:50]

    results = [
        InlineQueryResultArticle(
            id=str(uid),
            title=utext,
            input_message_content=InputTextMessageContent(message_text=utext),
        )
        for uid, utext in universities
    ]
    await inline_query.answer(results, cache_time=30, is_personal=True)


@ball_router.message(FormBall.ball3)
async def chosen_university(message: Message, state: FSMContext):
    await _safe_delete(message)

    if message.text == "🔙 Ortga":
        await _delete_old_msgs(state, message.chat.id)
        data  = await state.get_data()
        shakl = data["shakl"]
        ball  = data["ball"]
        cond  = _ball_condition(shakl)

        with db_connection() as (conn, cur):
            cur.execute(f"""
                SELECT DISTINCT r.region_name
                FROM mandat mn
                JOIN regions r ON mn.region_id = r.region_id
                WHERE {cond}
            """, (ball,))
            regions = cur.fetchall()

        keyboard = [[KeyboardButton(text=rn)] for (rn,) in regions]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        await state.set_state(FormBall.ball2)
        m1 = await message.answer(
            f"<b>{len(regions)} ta hudud\n\n📍 Hududni tanlang:</b>",
            parse_mode="html",
            reply_markup=btn,
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

    un_name = message.text
    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT un_id FROM universities WHERE lower(un_text) = %s",
            (un_name.lower(),)
        )
        row = cur.fetchone()
        if not row:
            return
        un_id = row[0]

    data   = await state.get_data()
    reg_id = data["reg_id"]
    shakl  = data["shakl"]
    ball   = data["ball"]
    cond   = _ball_condition(shakl)

    with db_connection() as (conn, cur):
        if shakl == "gr":
            types = [("1", "Kunduzgi")]
        else:
            cur.execute(f"""
                SELECT DISTINCT g.ty_id, g.ty_text
                FROM gettypes g
                JOIN mandat mn ON g.un_id = mn.un_id AND g.region_id = mn.region_id
                WHERE mn.region_id = %s AND mn.un_id = %s AND {cond}
            """, (reg_id, str(un_id), ball))
            types = cur.fetchall()

    await _delete_old_msgs(state, message.chat.id)
    await state.update_data(un_id=un_id)
    await state.set_state(FormBall.ball4)

    keyboard = [
        [KeyboardButton(text=ty_text if isinstance(ty_text, str) else ty_text)]
        for _, ty_text in types
    ]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    m = await message.answer(
        "<b>🔰 Ta'lim shaklini tanlang: 👇</b>",
        parse_mode="html",
        reply_markup=btn,
    )
    await _track_msg(state, m)


# ═══════════════════════════════════════════════════════════════
#  BALL4 — Ta'lim shakli
# ═══════════════════════════════════════════════════════════════

@ball_router.message(FormBall.ball4)
async def chosen_type(message: Message, state: FSMContext):
    await _safe_delete(message)

    if message.text == "🔙 Ortga":
        await _delete_old_msgs(state, message.chat.id)
        data   = await state.get_data()
        reg_id = data["reg_id"]
        shakl  = data["shakl"]
        ball   = data["ball"]
        cond   = _ball_condition(shakl)

        with db_connection() as (conn, cur):
            cur.execute(f"""
                SELECT COUNT(DISTINCT u.un_id)
                FROM universities u
                JOIN mandat mn ON u.un_id = mn.un_id AND u.region_id = mn.region_id
                WHERE mn.region_id = %s AND {cond}
            """, (reg_id, ball))
            count = cur.fetchone()[0]

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        await state.set_state(FormBall.ball3)
        m1 = await message.answer(
            f"<b>{count} ta oliygoh\n\n🏢 OTMni tanlang:</b>",
            parse_mode="html",
            reply_markup=await UserPanels.to_back(),
        )
        m2 = await message.answer(
            "<b>Tezkor qidiruvdan foydalaning... 👇</b>",
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
    with db_connection() as (conn, cur):
        cur.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text) = %s", (name,))
        row = cur.fetchone()
        if not row:
            ty_id = "1" if name == "kunduzgi" else None
            if not ty_id:
                return
        else:
            ty_id = row[0]

    data   = await state.get_data()
    un_id  = data["un_id"]
    reg_id = data["reg_id"]
    shakl  = data["shakl"]
    ball   = data["ball"]
    cond   = _ball_condition(shakl)

    with db_connection() as (conn, cur):
        cur.execute(f"""
            SELECT DISTINCT g.lan_id, g.lan_text
            FROM mandat mn
            JOIN getlangs g ON mn.lan_id = g.lan_id
            WHERE mn.un_id = %s AND mn.ty_id = %s AND mn.region_id = %s AND {cond}
        """, (un_id, ty_id, reg_id, ball))
        langs = cur.fetchall()

    await _delete_old_msgs(state, message.chat.id)
    await state.update_data(ty_id=ty_id)
    await state.set_state(FormBall.ball5)

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
#  BALL5 — Ta'lim tili
# ═══════════════════════════════════════════════════════════════

@ball_router.message(FormBall.ball5)
async def chosen_lang(message: Message, state: FSMContext):
    await _safe_delete(message)

    if message.text == "🔙 Ortga":
        await _delete_old_msgs(state, message.chat.id)
        data   = await state.get_data()
        reg_id = data.get("reg_id")
        un_id  = data.get("un_id")
        shakl  = data["shakl"]
        ball   = data["ball"]
        cond   = _ball_condition(shakl)

        with db_connection() as (conn, cur):
            if shakl == "gr":
                types = [("1", "Kunduzgi")]
            else:
                cur.execute(f"""
                    SELECT DISTINCT g.ty_id, g.ty_text
                    FROM gettypes g
                    JOIN mandat mn ON g.un_id = mn.un_id AND g.region_id = mn.region_id
                    WHERE mn.region_id = %s AND mn.un_id = %s AND {cond}
                """, (reg_id, str(un_id), ball))
                types = cur.fetchall()

        keyboard = [[KeyboardButton(text=t[1] if len(t) > 1 else t[0])] for t in types]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await state.set_state(FormBall.ball4)
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
    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT lan_id FROM getlangs WHERE lower(lan_text) = %s",
            (lan_text_input,)
        )
        row = cur.fetchone()
        if not row:
            return
        lan_id = row[0]

    data   = await state.get_data()
    un_id  = data["un_id"]
    ty_id  = data["ty_id"]
    reg_id = data.get("reg_id")
    shakl  = data["shakl"]
    ball   = data["ball"]
    cond   = _ball_condition(shakl)

    # ✅ TUZATILDI: SQL da alias "m." yo'q, to'g'ri ustun nomlari ishlatiladi
    with db_connection() as (conn, cur):
        cur.execute(f"""
            SELECT mvdir, nomi
            FROM mandat
            WHERE region_id = %s
              AND un_id = %s
              AND ty_id = %s
              AND lan_id = %s
              AND {cond}
            ORDER BY nomi
        """, (reg_id, un_id, ty_id, lan_id, ball))
        rows = cur.fetchall()

    await _delete_old_msgs(state, message.chat.id)
    await state.update_data(lan_id=lan_id)
    await state.set_state(FormBall.ball6)

    keyboard = [[KeyboardButton(text=f"{mvdir} - {nomi}")] for mvdir, nomi in rows]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    m1 = await message.answer(
        f"<b>{len(rows)} ta yo'nalish mavjud:\n📚 Ta'lim yo'nalishini tanlang:</b>",
        parse_mode="html",
        reply_markup=btn,
    )
    m2 = await message.answer(
        "<b>Tezkor qidiruvdan foydalaning...</b>",
        parse_mode="html",
        reply_markup=kb,
    )
    await _track_msg(state, m1)
    await _track_msg(state, m2)


# ═══════════════════════════════════════════════════════════════
#  BALL6 — Yo'nalish inline + natija  (inline FormBall.ball6 ga bog'liq)
# ═══════════════════════════════════════════════════════════════

@ball_router.inline_query(FormBall.ball6)
async def inline_ball6(inline_query: InlineQuery, state: FSMContext):
    text   = inline_query.query.lower().strip()
    data   = await state.get_data()
    un_id  = data.get("un_id")
    ty_id  = data.get("ty_id")
    lan_id = data.get("lan_id")
    reg_id = data.get("reg_id")
    shakl  = data.get("shakl", "gr")
    ball   = data.get("ball", 0)
    cond   = _ball_condition(shakl)

    with db_connection() as (conn, cur):
        if text:
            cur.execute(f"""
                SELECT id, mvdir, nomi FROM mandat
                WHERE lower(nomi) LIKE %s
                  AND region_id = %s AND un_id = %s
                  AND ty_id = %s AND lan_id = %s AND {cond}
                ORDER BY nomi
            """, (f"%{text}%", reg_id, un_id, ty_id, lan_id, ball))
        else:
            cur.execute(f"""
                SELECT id, mvdir, nomi FROM mandat
                WHERE region_id = %s AND un_id = %s
                  AND ty_id = %s AND lan_id = %s AND {cond}
                ORDER BY nomi
            """, (reg_id, un_id, ty_id, lan_id, ball))
        facs = cur.fetchall()[:50]

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
    await inline_query.answer(results, cache_time=30, is_personal=True)


@ball_router.message(FormBall.ball6)
async def chosen_direction(message: Message, state: FSMContext):
    await _safe_delete(message)

    if message.text == "🔙 Ortga":
        await _delete_old_msgs(state, message.chat.id)
        data   = await state.get_data()
        un_id  = data["un_id"]
        ty_id  = data["ty_id"]
        reg_id = data.get("reg_id")
        shakl  = data["shakl"]
        ball   = data["ball"]
        cond   = _ball_condition(shakl)

        with db_connection() as (conn, cur):
            cur.execute(f"""
                SELECT DISTINCT g.lan_id, g.lan_text
                FROM mandat mn
                JOIN getlangs g ON mn.lan_id = g.lan_id
                WHERE mn.un_id = %s AND mn.ty_id = %s AND mn.region_id = %s AND {cond}
            """, (un_id, ty_id, reg_id, ball))
            langs = cur.fetchall()

        keyboard = [[KeyboardButton(text=lan_text[:60])] for _, lan_text in langs]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await state.set_state(FormBall.ball5)
        m = await message.answer(
            "<b>🇺🇿 Ta'lim tilini tanlang:</b>",
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

    parts = message.text.split(" - ", 1)
    if len(parts) < 2:
        return
    mvdir_str, nomi = parts[0].strip(), parts[1].strip()

    data   = await state.get_data()
    un_id  = data["un_id"]
    ty_id  = data["ty_id"]
    lan_id = data["lan_id"]
    reg_id = data.get("reg_id")

    with db_connection() as (conn, cur):
        cur.execute("""
            SELECT gr_b, con_b, olimp FROM mandat
            WHERE un_id = %s AND ty_id = %s AND lan_id = %s
              AND mvdir = %s AND nomi = %s AND region_id = %s
        """, (un_id, ty_id, lan_id, mvdir_str, nomi, reg_id))
        kaup = cur.fetchone()

        if not kaup:
            m = await message.answer(
                "<b>🤷🏻‍♂️ Bunday ma'lumot yo'q</b>",
                parse_mode="html",
            )
            await _track_msg(state, m)
            return

        gr_b, con_b, olimp = kaup

        cur.execute("SELECT un_text  FROM universities WHERE un_id  = %s", (un_id,))
        un_name_row  = cur.fetchone()
        cur.execute("SELECT lan_text FROM getlangs    WHERE lan_id = %s", (lan_id,))
        lan_text_row = cur.fetchone()
        cur.execute("SELECT ty_text  FROM gettypes    WHERE ty_id  = %s", (ty_id,))
        ty_text_row  = cur.fetchone()

    un_name  = un_name_row[0]  if un_name_row  else "—"
    lan_text = lan_text_row[0] if lan_text_row else "—"
    ty_text  = ty_text_row[0]  if ty_text_row  else "—"

    msg_text = (
        f"<b>🏛 OLIYGOH:</b> {un_name}\n\n"
        f"<b>📚 TAʼLIM YO'NALISHI</b> — {mvdir_str} - {nomi}\n\n"
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
    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT file_id FROM photos WHERE un_id = %s AND ty_id = %s AND lan_id = %s AND mvdir = %s",
            (un_id, ty_id, lan_id, mvdir_str)
        )
        old = cur.fetchone()

    if old:
        await message.answer_photo(photo=old[0], caption=msg_text, parse_mode="html")
        return

    if create_card(
        univer=un_name, faculty=f"{mvdir_str} - {nomi}",
        lang=lan_text, edu=ty_text,
        grand=gr_b, kont=con_b, olmp=olimp, name=user_id
    ):
        CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(CURRENT_DIR, "photos", f"{user_id}.jpg")
        try:
            sent    = await message.answer_photo(
                photo=FSInputFile(path), caption=msg_text, parse_mode="html"
            )
            file_id = sent.photo[-1].file_id
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO photos (un_id, ty_id, lan_id, mvdir, file_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (un_id, ty_id, lan_id, mvdir) DO NOTHING
                """, (un_id, ty_id, lan_id, mvdir_str, file_id))
        finally:
            if os.path.exists(path):
                os.remove(path)
    else:
        await message.answer(msg_text, parse_mode="html")