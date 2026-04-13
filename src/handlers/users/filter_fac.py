"""filter_fac.py — Yo'nalishlar bo'yicha qidirish (Direction-based search).

Flow:
  fac1  -> inline query: yo'nalish tanlash (offset pagination)
  fac2  -> inline query: OTM tanlash (tanlangan yo'nalish bo'yicha)
  fac3  -> reply keyboard: ta'lim shakli (type) tanlash
  fac4  -> inline query: yakuniy yozuv tanlash va natijani ko'rish

Inline xabarlar patak prefiksi bilan kodlanadi va darhol o'chiriladi.
Redis orqali qidiruv natijalari 120 soniya davomida keshlangan bo'ladi.
"""
import json
import os
from _md5 import md5

import redis.asyncio as aioredis
from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    KeyboardButton,
    ReplyKeyboardMarkup,
    FSInputFile,
)

from config import bot, REDIS_URL, cursor, conn
from src.handlers.users.users import create_card
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

fac_router = Router()

# -- Constants -----------------------------------------------------------------
_PAGE = 50    # inline results per page
_TTL  = 120   # Redis cache TTL (seconds)

# Main-menu section buttons — pressing these from any FSM state should clear
# state and return the user to the main menu.
_SECTION_BTNS = frozenset({
    "📊 Ball yetadigan yo'nalishlar",
    "\U0001f4da Yo\u02bbnalishlar bo\u02bbyicha",
    "📈 Viloyatlar kesimida",
})

# -- Redis helpers -------------------------------------------------------------
_redis: "aioredis.Redis | None" = None


async def _get_redis():
    global _redis
    if _redis is None and REDIS_URL:
        try:
            _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        except Exception:
            pass
    return _redis


async def _cget(key: str):
    r = await _get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def _cset(key: str, value) -> None:
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(value, ensure_ascii=False), ex=_TTL)
    except Exception:
        pass


# -- FSM -----------------------------------------------------------------------
class FormFac(StatesGroup):
    fac1 = State()   # direction search
    fac2 = State()   # university search
    fac3 = State()   # education-type selection (reply keyboard)
    fac4 = State()   # final record search & display


# -- Keyboard helpers ----------------------------------------------------------
def _back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="\U0001f519 Ortga"), KeyboardButton(text="\U0001f519 Bosh menu")]],
        resize_keyboard=True,
    )


def _iq_btn(label: str = "\U0001f50d Izlash") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, switch_inline_query_current_chat=" ")]
    ])


# =============================================================================
# STEP 1 -- Entry & direction search
# =============================================================================

@fac_router.message(F.text == "\U0001f4da Yo\u02bbnalishlar bo\u02bbyicha", F.chat.type == ChatType.PRIVATE)
async def enter_direction(message: Message, state: FSMContext) -> None:
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)
    if not check_status:
        await message.answer(
            "!\U0000274c Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn(channels),
        )
        return

    cursor.execute("SELECT COUNT(DISTINCT nomi) FROM mandat")
    total = cursor.fetchone()[0]
    await state.set_state(FormFac.fac1)
    await message.answer(
        f"<b>Jami <u>{total}</u> ta yo'nalish mavjud.\n\n"
        f"\U0001f4da Qidiruv orqali kerakli yo'nalishni toping:</b>",
        parse_mode="html",
        reply_markup=_back_kb(),
    )
    await message.answer(
        "<b>Qidiruvni boshlash uchun tugmani bosing \U0001f447</b>",
        parse_mode="html",
        reply_markup=_iq_btn(),
    )


@fac_router.inline_query(FormFac.fac1)
async def iq_directions(iq: InlineQuery) -> None:
    text   = iq.query.strip().lower()
    offset = int(iq.offset or 0)
    ckey   = f"fac:d:{md5(text.encode()).hexdigest()}:{offset}"

    rows = await _cget(ckey)
    if rows is None:
        if text:
            cursor.execute(
                "SELECT DISTINCT mvdir, nomi FROM mandat "
                "WHERE lower(nomi) LIKE %s ORDER BY nomi LIMIT %s OFFSET %s",
                (f"%{text}%", _PAGE + 1, offset),
            )
        else:
            cursor.execute(
                "SELECT DISTINCT mvdir, nomi FROM mandat ORDER BY nomi LIMIT %s OFFSET %s",
                (_PAGE + 1, offset),
            )
        rows = [[str(r[0]), r[1]] for r in cursor.fetchall()]
        await _cset(ckey, rows)

    has_more = len(rows) > _PAGE
    page     = rows[:_PAGE]
    results  = [
        InlineQueryResultArticle(
            id=f"d|{mv}",
            title=f"{mv} \u2014 {nm}",
            description="Yo'nalish kodi va nomi",
            input_message_content=InputTextMessageContent(
                message_text=f"\U0001f4ccDIR|{mv}|{nm}",
            ),
        )
        for mv, nm in page
    ]
    if not results:
        results = [InlineQueryResultArticle(
            id="empty_d",
            title="Natija topilmadi \u2014 boshqacha so'z bilan qidiring",
            input_message_content=InputTextMessageContent(message_text="\U0001f4ccEMPTY"),
        )]
    await iq.answer(
        results,
        cache_time=0,
        is_personal=True,
        next_offset=str(offset + _PAGE) if has_more else "",
    )


@fac_router.message(FormFac.fac1)
async def on_direction_chosen(message: Message, state: FSMContext) -> None:
    txt = message.text or ""

    if txt in ("\U0001f519 Ortga", "\U0001f519 Bosh menu"):
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang \U0001f447</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    if txt == "\U0001f4ccEMPTY":
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer("Hech narsa topilmadi. Boshqacha so'z bilan qidiring.")
        return

    if txt in _SECTION_BTNS:
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang \U0001f447</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    if not txt.startswith("\U0001f4ccDIR|"):
        await message.answer("Yo'nalishni qidiruvdan tanlang. \U0001f446")
        return

    try:
        await message.delete()
    except Exception:
        pass

    parts = txt.split("|", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Format xato, qayta tanlang.")
        return

    _, mvdir_s, nomi = parts
    mvdir = int(mvdir_s)

    ckey = f"fac:ucnt:{mvdir}:{md5(nomi.encode()).hexdigest()}"
    unis = await _cget(ckey)
    if unis is None:
        cursor.execute(
            """
            SELECT u.un_id, u.un_text
            FROM mandat m
            JOIN universities u ON m.un_id = u.un_id
            WHERE m.mvdir = %s AND m.nomi = %s
            GROUP BY u.un_id, u.un_text
            ORDER BY u.un_text
            """,
            (mvdir, nomi),
        )
        unis = [[r[0], r[1]] for r in cursor.fetchall()]
        await _cset(ckey, unis)

    if not unis:
        await message.answer("Bu yo'nalish hech bir OTMda topilmadi.")
        return

    await state.update_data(mvdir=mvdir, fac_name=nomi)
    await state.set_state(FormFac.fac2)
    await message.answer(
        f"<b>\u2705 Tanlangan yo'nalish: <u>{mvdir} \u2014 {nomi}</u>\n\n"
        f"Bu yo'nalish <u>{len(unis)}</u> ta OTMda mavjud.\n\n"
        f"\U0001f3e2 OTMni qidiring va tanlang:</b>",
        parse_mode="html",
        reply_markup=_back_kb(),
    )
    await message.answer(
        "<b>Qidiruvni boshlash uchun tugmani bosing \U0001f447</b>",
        parse_mode="html",
        reply_markup=_iq_btn(),
    )


# =============================================================================
# STEP 2 -- University search
# =============================================================================

@fac_router.inline_query(FormFac.fac2)
async def iq_universities(iq: InlineQuery, state: FSMContext) -> None:
    text   = iq.query.strip().lower()
    offset = int(iq.offset or 0)
    data   = await state.get_data()
    mvdir  = data.get("mvdir")
    nomi   = data.get("fac_name", "")

    if mvdir is None:
        await iq.answer([], cache_time=1, is_personal=True)
        return

    ckey = f"fac:u:{mvdir}:{md5((nomi + text).encode()).hexdigest()}:{offset}"
    rows = await _cget(ckey)
    if rows is None:
        extra  = "AND lower(u.un_text) LIKE %s" if text else ""
        params = [mvdir, nomi]
        if text:
            params.append(f"%{text}%")
        params += [_PAGE + 1, offset]
        cursor.execute(
            f"""
            SELECT u.un_id, u.un_text
            FROM mandat m
            JOIN universities u ON m.un_id = u.un_id
            WHERE m.mvdir = %s AND m.nomi = %s {extra}
            GROUP BY u.un_id, u.un_text
            ORDER BY u.un_text
            LIMIT %s OFFSET %s
            """,
            params,
        )
        rows = [[r[0], r[1]] for r in cursor.fetchall()]
        await _cset(ckey, rows)

    has_more = len(rows) > _PAGE
    page     = rows[:_PAGE]
    results  = [
        InlineQueryResultArticle(
            id=f"u|{un_id}",
            title=un_text,
            description="OTM nomi",
            input_message_content=InputTextMessageContent(
                message_text=f"\U0001f4ccUNI|{un_id}|{un_text}",
            ),
        )
        for un_id, un_text in page
    ]
    if not results:
        results = [InlineQueryResultArticle(
            id="empty_u",
            title="OTM topilmadi \u2014 boshqacha so'z bilan qidiring",
            input_message_content=InputTextMessageContent(message_text="\U0001f4ccEMPTY"),
        )]
    await iq.answer(
        results,
        cache_time=0,
        is_personal=True,
        next_offset=str(offset + _PAGE) if has_more else "",
    )


@fac_router.message(FormFac.fac2)
async def on_university_chosen(message: Message, state: FSMContext) -> None:
    txt = message.text or ""

    if txt == "\U0001f519 Ortga":
        await state.set_state(FormFac.fac1)
        cursor.execute("SELECT COUNT(DISTINCT nomi) FROM mandat")
        total = cursor.fetchone()[0]
        await message.answer(
            f"<b>Jami <u>{total}</u> ta yo'nalish mavjud.\n\n"
            f"\U0001f4da Qidiruv orqali kerakli yo'nalishni toping:</b>",
            parse_mode="html",
            reply_markup=_back_kb(),
        )
        await message.answer(
            "<b>Qidiruvni boshlash uchun tugmani bosing \U0001f447</b>",
            parse_mode="html",
            reply_markup=_iq_btn(),
        )
        return

    if txt == "\U0001f519 Bosh menu":
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang \U0001f447</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    if txt == "\U0001f4ccEMPTY":
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer("OTM topilmadi. Boshqacha so'z bilan qidiring.")
        return

    if txt in _SECTION_BTNS:
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang \U0001f447</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    if not txt.startswith("\U0001f4ccUNI|"):
        await message.answer("OTMni qidiruvdan tanlang. \U0001f446")
        return

    try:
        await message.delete()
    except Exception:
        pass

    parts = txt.split("|", 2)
    if len(parts) != 3:
        await message.answer("Format xato, qayta tanlang.")
        return

    _, un_id_s, un_text = parts
    data  = await state.get_data()
    mvdir = data["mvdir"]

    ckey  = f"fac:t:{un_id_s}:{mvdir}"
    types = await _cget(ckey)
    if types is None:
        cursor.execute(
            """
            SELECT DISTINCT g.ty_id, g.ty_text
            FROM mandat m
            JOIN gettypes g ON m.ty_id::text = g.ty_id::text AND m.un_id::text = g.un_id::text
            WHERE m.un_id = %s AND m.mvdir = %s
            ORDER BY g.ty_text
            """,
            (un_id_s, mvdir),
        )
        types = [[r[0], r[1]] for r in cursor.fetchall()]
        await _cset(ckey, types)

    if not types:
        await message.answer("Bu OTMda ushbu yo'nalish uchun ta'lim shakli topilmadi.")
        return

    await state.update_data(un_id=un_id_s, un_text=un_text)
    await state.set_state(FormFac.fac3)

    keyboard = [[KeyboardButton(text=ty_text)] for _, ty_text in types]
    keyboard.append([KeyboardButton(text="\U0001f519 Ortga"), KeyboardButton(text="\U0001f519 Bosh menu")])
    await message.answer(
        f"<b>\u2705 OTM: <u>{un_text}</u>\n\n\U0001f530 Ta'lim shaklini tanlang:</b>",
        parse_mode="html",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True),
    )


# =============================================================================
# STEP 3 -- Education-type selection (reply keyboard)
# =============================================================================

@fac_router.message(FormFac.fac3)
async def on_type_chosen(message: Message, state: FSMContext) -> None:
    txt  = message.text or ""
    data = await state.get_data()

    if txt == "\U0001f519 Ortga":
        await state.set_state(FormFac.fac2)
        mvdir    = data["mvdir"]
        fac_name = data["fac_name"]
        cursor.execute(
            """
            SELECT COUNT(DISTINCT u.un_id)
            FROM mandat m
            JOIN universities u ON m.un_id = u.un_id
            WHERE m.mvdir = %s AND m.nomi = %s
            """,
            (mvdir, fac_name),
        )
        count = cursor.fetchone()[0]
        await message.answer(
            f"<b>Bu yo'nalish <u>{count}</u> ta OTMda mavjud.\n\n"
            f"\U0001f3e2 OTMni qidiring va tanlang:</b>",
            parse_mode="html",
            reply_markup=_back_kb(),
        )
        await message.answer(
            "<b>Qidiruvni boshlash uchun tugmani bosing \U0001f447</b>",
            parse_mode="html",
            reply_markup=_iq_btn(),
        )
        return

    if txt == "\U0001f519 Bosh menu":
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang \U0001f447</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    un_id    = data["un_id"]
    mvdir    = data["mvdir"]
    fac_name = data["fac_name"]

    if txt in _SECTION_BTNS:
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang \U0001f447</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    cursor.execute(
        "SELECT ty_id, ty_text FROM gettypes WHERE lower(ty_text) = %s AND un_id = %s",
        (txt.lower(), un_id),
    )
    row = cursor.fetchone()
    if not row:
        await message.answer("Ta'lim shakli topilmadi. Ro'yxatdan tanlang.")
        return

    ty_id, ty_text = row
    await state.update_data(ty_id=str(ty_id), ty_text=ty_text)
    await state.set_state(FormFac.fac4)

    cursor.execute(
        "SELECT COUNT(*) FROM mandat WHERE un_id=%s AND ty_id=%s AND mvdir=%s AND nomi=%s",
        (un_id, str(ty_id), str(mvdir), fac_name),
    )
    count = cursor.fetchone()[0]

    await message.answer(
        f"<b>\u2705 Ta'lim shakli: <u>{ty_text}</u>\n\n"
        f"<u>{count}</u> ta natija topildi.\n\n"
        f"\U0001f4cb Quyidan kerakli yo'nalishni tanlang:</b>",
        parse_mode="html",
        reply_markup=_back_kb(),
    )
    await message.answer(
        "<b>Natijalarni ko'rish uchun qidiruvni oching \U0001f447</b>",
        parse_mode="html",
        reply_markup=_iq_btn("\U0001f4cb Natijalarni ko'rish"),
    )


# =============================================================================
# STEP 4 -- Final record search & display
# =============================================================================

@fac_router.inline_query(FormFac.fac4)
async def iq_records(iq: InlineQuery, state: FSMContext) -> None:
    text   = iq.query.strip().lower()
    offset = int(iq.offset or 0)
    data   = await state.get_data()
    un_id  = data.get("un_id", "")
    ty_id  = str(data.get("ty_id", ""))
    mvdir  = str(data.get("mvdir", ""))
    nomi   = data.get("fac_name", "")

    if not un_id or not ty_id or not mvdir:
        await iq.answer([], cache_time=1, is_personal=True)
        return

    ckey = f"fac:r:{un_id}:{ty_id}:{mvdir}:{md5((nomi + text).encode()).hexdigest()}:{offset}"
    rows = await _cget(ckey)
    if rows is None:
        extra  = "AND lower(g.lan_text) LIKE %s" if text else ""
        params = [un_id, ty_id, mvdir, nomi]
        if text:
            params.append(f"%{text}%")
        params += [_PAGE + 1, offset]
        cursor.execute(
            f"""
            SELECT m.mvdir, m.nomi, g.lan_text, m.lan_id
            FROM mandat m
            JOIN getlangs g ON m.lan_id::text    = g.lan_id::text
                           AND m.un_id::text     = g.un_id::text
                           AND m.ty_id::text     = g.ty_id::text
                           AND m.region_id::text = g.region_id::text
            WHERE m.un_id = %s AND m.ty_id = %s AND m.mvdir = %s AND m.nomi = %s
            {extra}
            ORDER BY g.lan_text
            LIMIT %s OFFSET %s
            """,
            params,
        )
        rows = [[str(r[0]), r[1], r[2], str(r[3])] for r in cursor.fetchall()]
        await _cset(ckey, rows)

    has_more = len(rows) > _PAGE
    page     = rows[:_PAGE]
    results  = [
        InlineQueryResultArticle(
            id=f"r|{mv}|{lid}",
            title=f"{mv} \u2014 {nm}",
            description=lan,
            input_message_content=InputTextMessageContent(
                message_text=f"\U0001f4ccREC|{mv}|{lid}",
            ),
        )
        for mv, nm, lan, lid in page
    ]
    if not results:
        results = [InlineQueryResultArticle(
            id="empty_r",
            title="Natija topilmadi",
            input_message_content=InputTextMessageContent(message_text="\U0001f4ccEMPTY"),
        )]
    await iq.answer(
        results,
        cache_time=0,
        is_personal=True,
        next_offset=str(offset + _PAGE) if has_more else "",
    )


@fac_router.message(FormFac.fac4)
async def on_record_chosen(message: Message, state: FSMContext) -> None:
    txt  = message.text or ""
    data = await state.get_data()

    # -- Back navigation -------------------------------------------------------
    if txt == "\U0001f519 Ortga":
        await state.set_state(FormFac.fac3)
        un_id = data["un_id"]
        mvdir = data["mvdir"]
        ckey  = f"fac:t:{un_id}:{mvdir}"
        types = await _cget(ckey)
        if types is None:
            cursor.execute(
                """
                SELECT DISTINCT g.ty_id, g.ty_text
                FROM mandat m
                JOIN gettypes g ON m.ty_id::text = g.ty_id::text AND m.un_id::text = g.un_id::text
                WHERE m.un_id = %s AND m.mvdir = %s
                ORDER BY g.ty_text
                """,
                (un_id, mvdir),
            )
            types = [[r[0], r[1]] for r in cursor.fetchall()]
        keyboard = [[KeyboardButton(text=ty_text)] for _, ty_text in types]
        keyboard.append([KeyboardButton(text="\U0001f519 Ortga"), KeyboardButton(text="\U0001f519 Bosh menu")])
        await message.answer(
            "<b>\U0001f530 Ta'lim shaklini tanlang:</b>",
            parse_mode="html",
            reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True),
        )
        return

    if txt == "\U0001f519 Bosh menu":
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang \U0001f447</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    # -- Empty inline result ---------------------------------------------------
    if txt == "\U0001f4ccEMPTY":
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer("Natija topilmadi.")
        return

    if txt in _SECTION_BTNS:
        await state.clear()
        await message.answer(
            "<b>Quyidagi menulardan birini tanlang \U0001f447</b>",
            parse_mode="html",
            reply_markup=await UserPanels.main_manu(),
        )
        return

    if not txt.startswith("\U0001f4ccREC|"):
        await message.answer("Natijani qidiruvdan tanlang. \U0001f446")
        return

    try:
        await message.delete()
    except Exception:
        pass

    parts = txt.split("|", 2)
    if len(parts) != 3:
        await message.answer("Format xato.")
        return

    _, mv_s, lan_id_s = parts
    un_id    = data["un_id"]
    ty_id    = str(data["ty_id"])
    fac_name = data["fac_name"]

    # -- Fetch full record -----------------------------------------------------
    cursor.execute(
        """
        SELECT m.mvdir, m.nomi, m.gr_b, m.con_b, m.olimp,
               u.un_text, g.lan_text, t.ty_text
        FROM mandat m
        JOIN universities u ON m.un_id = u.un_id
        JOIN getlangs g ON m.lan_id::text    = g.lan_id::text
                       AND m.un_id::text     = g.un_id::text
                       AND m.ty_id::text     = g.ty_id::text
                       AND m.region_id::text = g.region_id::text
        JOIN gettypes  t ON m.ty_id::text = t.ty_id::text AND m.un_id::text = t.un_id::text
        WHERE m.un_id = %s AND m.ty_id = %s AND m.mvdir = %s
          AND m.nomi  = %s AND m.lan_id = %s
        LIMIT 1
        """,
        (un_id, ty_id, mv_s, fac_name, lan_id_s),
    )
    row = cursor.fetchone()
    if not row:
        await message.answer("Ma'lumot topilmadi.")
        return

    mv_val, nomi, gr_b, con_b, olimp, un_text, lan_text, ty_text = row

    caption = (
        f"<b>\U0001f3db OLIYGOH:</b> {un_text}\n\n"
        f"<b>\U0001f4da TA'LIM YO'NALISHI</b> \u2014 {mv_val} \u2014 {nomi}\n\n"
        f"<b>\U0001f1fa\U0001f1ff TA'LIM TILI</b> \u2014 {lan_text}\n\n"
        f"<b>\U0001f530 TA'LIM SHAKLI</b> \u2014 {ty_text}\n\n"
        f"<b>\U0001f4c8 O'TISH BALLARI:</b>\n"
        f"<b>Grand</b> \u2014 {gr_b} ball | <b>Kontrakt</b> \u2014 {con_b} ball\n\n"
        f"<b>\U0001f3c6 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
        f"<b>\u00a9 <a href='https://t.me/mandatjavobbot?start=share'>@Mandatjavobbot</a>"
        f" \u2014 o'tish ballari va mandat natijalari</b>"
    )

    # Inline button on the card so user can search again without navigating back
    again_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="\U0001f50d Yana natija ko'rish",
            switch_inline_query_current_chat=" ",
        )]
    ])

    # -- Send photo card -------------------------------------------------------
    user_id = message.from_user.id
    cursor.execute(
        "SELECT file_id FROM photos WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s",
        (un_id, ty_id, lan_id_s, str(mv_val)),
    )
    cached_photo = cursor.fetchone()

    if cached_photo:
        await message.answer_photo(
            photo=cached_photo[0],
            caption=caption,
            parse_mode="html",
            reply_markup=again_kb,
        )
    else:
        photo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "photos", f"{user_id}.jpg"
        )
        if create_card(
            univer=un_text,
            faculty=f"{mv_val} \u2014 {nomi}",
            lang=lan_text,
            edu=ty_text,
            grand=gr_b,
            kont=con_b,
            olmp=olimp,
            name=user_id,
        ):
            try:
                sent = await message.answer_photo(
                    photo=FSInputFile(photo_path),
                    caption=caption,
                    parse_mode="html",
                    reply_markup=again_kb,
                )
                file_id = sent.photo[-1].file_id
                cursor.execute(
                    """
                    INSERT INTO photos (un_id, ty_id, lan_id, mvdir, file_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (un_id, ty_id, lan_id_s, str(mv_val), file_id),
                )
                conn.commit()
            finally:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
        else:
            await message.answer(caption, parse_mode="html", reply_markup=again_kb)

    # Restore reply keyboard for back navigation (state stays at fac4)
    await message.answer(
        "<b>\U00002b07\U0000fe0f Boshqa natijani ko'rish yoki ortga qaytish:</b>",
        parse_mode="html",
        reply_markup=_back_kb(),
    )
