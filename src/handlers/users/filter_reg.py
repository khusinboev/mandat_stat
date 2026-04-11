"""
filter_reg.py — "Viloyatlar kesimida" bo'limi

Oqim:
  reg1  → Viloyat tanlash
  reg2  → Universitet tanlash
  reg3  → Ta'lim shakli tanlash → yo'nalishlar (qavs ichida til) ko'rsatiladi
  reg4  → Yo'nalish tanlash → natija (rasm + matn)
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

reg_router = Router()


class FormReg(StatesGroup):
    reg1 = State()   # Viloyat tanlash
    reg2 = State()   # Universitet tanlash
    reg3 = State()   # Shakl tanlash
    reg4 = State()   # Yo'nalish + til tanlash → natija


# ── Doimiy klaviaturalar ─────────────────────────────────────────────────────

SEARCH_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
])


def _parse_direction_btn(text: str):
    """
    "123 - Yo'nalish nomi (O'zbek tili)" → (mvdir, nomi, lan_text)
    Qaytadi: (str, str, str) yoki None xato bo'lsa.
    """
    if not text.endswith(")"):
        return None
    last_open = text.rfind(" (")
    if last_open == -1:
        return None
    lan_text = text[last_open + 2:-1]
    rest = text[:last_open]
    dash = rest.find(" - ")
    if dash == -1:
        return None
    mvdir = rest[:dash]
    nomi  = rest[dash + 3:]
    return mvdir, nomi, lan_text


async def _send_result(message: Message, un_id, ty_id, lan_id,
                       un_name, mvdir, nomi, lan_text, ty_text,
                       gr_b, con_b, olimp):
    """Yo'nalish natijasini rasm + matn sifatida yuboradi."""
    msg_text = (
        f"<b>🏛 OLIYGOH:</b> {un_name}\n\n"
        f"<b>📚 TAʼLIM YO'NALISHI</b> — {mvdir} - {nomi}\n\n"
        f"<b>🇺🇿 TAʼLIM TILI</b> — {lan_text}\n\n"
        f"<b>🔰 TAʼLIM SHAKLI</b> — {ty_text}\n\n"
        f"<b>📈 OʻTISH BALLARI:</b>\n"
        f"<b>Grand</b> — {gr_b} ball  |  <b>Kontrakt</b> — {con_b} ball\n\n"
        f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
        f"<b>© <a href='https://t.me/mandatjavobbot?start=share'>"
        f"@Mandatjavobbot</a> — oʻtish ballari va mandat natijalari</b>"
    )
    user_id = message.from_user.id
    cursor.execute(
        "SELECT file_id FROM photos WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s",
        (str(un_id), str(ty_id), str(lan_id), str(mvdir))
    )
    old = cursor.fetchone()
    if old:
        await message.answer_photo(photo=old[0], caption=msg_text, parse_mode="html")
        return

    if create_card(univer=un_name, faculty=f"{mvdir} - {nomi}",
                   lang=lan_text, edu=ty_text,
                   grand=gr_b, kont=con_b, olmp=olimp, name=user_id):
        file_path = f"{os.path.dirname(os.path.abspath(__file__))}/photos/{user_id}.jpg"
        sent = await message.answer_photo(
            photo=FSInputFile(file_path), caption=msg_text, parse_mode="html"
        )
        file_id = sent.photo[-1].file_id
        cursor.execute("""
            INSERT INTO photos (un_id, ty_id, lan_id, mvdir, file_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (un_id, ty_id, lan_id, mvdir) DO NOTHING
        """, (str(un_id), str(ty_id), str(lan_id), str(mvdir), file_id))
        conn.commit()
        if os.path.exists(file_path):
            os.remove(file_path)
    else:
        await message.answer(msg_text, parse_mode="html")


# ── reg1 — Viloyat tanlash ───────────────────────────────────────────────────

@reg_router.message(F.text == "📈 Viloyatlar kesimida", F.chat.type == ChatType.PRIVATE)
async def enter_region(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)
    if not check_status:
        await message.answer("❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
                             reply_markup=await CheckData.channels_btn(channels))
        return

    cursor.execute("SELECT region_id, region_name FROM regions ORDER BY region_name")
    rows = cursor.fetchall()
    keyboard = [[KeyboardButton(text=r[1])] for r in rows]
    keyboard.append([KeyboardButton(text="🔙 Ortga")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer("<b>📍 Hududni tanlang:</b>", parse_mode="html", reply_markup=btn)
    await message.answer("<b>Tezkor qidiruvdan foydalaning...👇</b>",
                         parse_mode="html", reply_markup=SEARCH_KB)
    await state.set_state(FormReg.reg1)


@reg_router.inline_query(FormReg.reg1)
async def inline_reg1(inline_query: InlineQuery):
    text = inline_query.query.lower()
    if text:
        cursor.execute(
            "SELECT id, region_id, region_name FROM regions WHERE lower(region_name) LIKE %s",
            (f"%{text}%",)
        )
    else:
        cursor.execute("SELECT id, region_id, region_name FROM regions ORDER BY region_name")
    results = [
        InlineQueryResultArticle(
            id=str(i),
            title=rname,
            input_message_content=InputTextMessageContent(message_text=rname)
        ) for i, (rid, _region_id, rname) in enumerate(cursor.fetchall())
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@reg_router.message(FormReg.reg1)
async def chosen_reg1(message: Message, state: FSMContext):
    if message.text in ("🔙 Ortga", "🔙 Bosh menu"):
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.main_manu())
        return

    cursor.execute("SELECT region_id FROM regions WHERE region_name = %s", (message.text,))
    row = cursor.fetchone()
    if not row:
        return
    region_id = row[0]

    cursor.execute("""
        SELECT u.un_text FROM regions r
        JOIN universities u ON r.region_id = u.region_id
        WHERE r.region_name = %s ORDER BY u.un_text
    """, (message.text,))
    unis = cursor.fetchall()
    if not unis:
        await message.answer("<b>🤷🏻‍♂️ Bu hududda universitet topilmadi</b>", parse_mode="html")
        return

    await state.update_data(region_name=message.text, region_id=region_id)
    await state.set_state(FormReg.reg2)

    keyboard = [[KeyboardButton(text=u[0])] for u in unis]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer(
        f"<b>Siz tanlagan hududda {len(unis)} ta oliygoh mavjud\n\n🏢 OTMni tanlang:</b>",
        parse_mode="html", reply_markup=btn
    )
    await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>",
                         parse_mode="html", reply_markup=SEARCH_KB)


# ── reg2 — Universitet tanlash ───────────────────────────────────────────────

@reg_router.inline_query(FormReg.reg2)
async def inline_reg2(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    region_name = data.get("region_name")
    if text:
        cursor.execute("""
            SELECT u.id, u.un_text FROM regions r
            JOIN universities u ON r.region_id = u.region_id
            WHERE r.region_name = %s AND lower(u.un_text) LIKE %s
            ORDER BY u.un_text LIMIT 50
        """, (region_name, f"%{text}%"))
    else:
        cursor.execute("""
            SELECT u.id, u.un_text FROM regions r
            JOIN universities u ON r.region_id = u.region_id
            WHERE r.region_name = %s ORDER BY u.un_text LIMIT 50
        """, (region_name,))
    results = [
        InlineQueryResultArticle(
            id=str(i),
            title=un_text,
            input_message_content=InputTextMessageContent(message_text=un_text)
        ) for i, (uid, un_text) in enumerate(cursor.fetchall())
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@reg_router.message(FormReg.reg2)
async def chosen_reg2(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        # Viloyat tanlash ekraniga qaytamiz
        cursor.execute("SELECT region_id, region_name FROM regions ORDER BY region_name")
        rows = cursor.fetchall()
        keyboard = [[KeyboardButton(text=r[1])] for r in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>📍 Hududni tanlang:</b>", parse_mode="html", reply_markup=btn)
        await message.answer("<b>Tezkor qidiruvdan foydalaning...👇</b>",
                             parse_mode="html", reply_markup=SEARCH_KB)
        await state.set_state(FormReg.reg1)
        return
    if message.text == "🔙 Bosh menu":
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
    await state.set_state(FormReg.reg3)

    data = await state.get_data()
    # Faqat bazada haqiqiy mandat ma'lumoti mavjud ta'lim shakllarini ko'rsatamiz
    cursor.execute("""
        SELECT DISTINCT g.ty_id, g.ty_text
        FROM gettypes g
        WHERE g.un_id = %s
          AND EXISTS (SELECT 1 FROM mandat m WHERE m.un_id = %s AND m.ty_id = g.ty_id)
        ORDER BY g.ty_text
    """, (un_id, un_id))
    rows = cursor.fetchall()
    if not rows:
        await message.answer("<b>🤷🏻‍♂️ Ta'lim shakli topilmadi</b>", parse_mode="html")
        return

    keyboard = [[KeyboardButton(text=ty_text)] for _, ty_text in rows]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)


# ── reg3 — Shakl tanlash → yo'nalishlar (til qavs ichida) ───────────────────

@reg_router.message(FormReg.reg3)
async def chosen_reg3(message: Message, state: FSMContext):
    data = await state.get_data()
    un_id     = data.get("un_id")
    region_id = data.get("region_id")

    if message.text == "🔙 Ortga":
        # Universitet tanlash ekraniga qaytamiz
        region_name = data.get("region_name")
        cursor.execute("""
            SELECT u.un_text FROM regions r
            JOIN universities u ON r.region_id = u.region_id
            WHERE r.region_name = %s ORDER BY u.un_text
        """, (region_name,))
        unis = cursor.fetchall()
        keyboard = [[KeyboardButton(text=u[0])] for u in unis]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer(
            f"<b>Siz tanlagan hududda {len(unis)} ta oliygoh mavjud\n\n🏢 OTMni tanlang:</b>",
            parse_mode="html", reply_markup=btn
        )
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>",
                             parse_mode="html", reply_markup=SEARCH_KB)
        await state.set_state(FormReg.reg2)
        return
    if message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.main_manu())
        return

    # ty_id ni mandat dan olamiz — faqat bu university uchun haqiqiy kombinatsiyalar
    cursor.execute("""
        SELECT DISTINCT m.ty_id FROM mandat m
        JOIN gettypes g ON m.ty_id = g.ty_id
        WHERE m.un_id = %s AND lower(g.ty_text) = %s
        LIMIT 1
    """, (un_id, message.text.lower()))
    row = cursor.fetchone()
    if not row:
        return
    ty_id = row[0]
    await state.update_data(ty_id=ty_id)

    # Yo'nalishlarni barcha tillar bilan birga ko'rsatamiz
    cursor.execute("""
        SELECT DISTINCT m.mvdir, m.nomi, g.lan_text
        FROM mandat m
        JOIN getlangs g ON m.lan_id = g.lan_id
        WHERE m.un_id = %s AND m.ty_id = %s
        ORDER BY m.nomi, g.lan_text
    """, (un_id, ty_id))
    rows = cursor.fetchall()

    if not rows:
        await message.answer("<b>🤷🏻‍♂️ Bu kombinatsiya bo'yicha yo'nalish topilmadi</b>",
                             parse_mode="html")
        return

    # Yo'nalishlar keyboard limitidan (100) oshib ketishi mumkin —
    # faqat inline qidiruv ishlatiladi, navigatsiya tugmalari saqlanadi
    nav_btn = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")]]
    )
    await message.answer(
        f"<b>{len(rows)} ta yo'nalish mavjud.\n"
        f"📚 Qidiruv orqali yo'nalishni tanlang 👇</b>",
        parse_mode="html", reply_markup=nav_btn
    )
    await message.answer("<b>🔍 Yo'nalish nomini yozing:</b>",
                         parse_mode="html", reply_markup=SEARCH_KB)
    await state.set_state(FormReg.reg4)


# ── reg4 — Yo'nalish tanlash → natija ───────────────────────────────────────

PAGE_SIZE = 50


@reg_router.inline_query(FormReg.reg4)
async def inline_reg4(inline_query: InlineQuery, state: FSMContext):
    text   = inline_query.query.lower()
    offset = int(inline_query.offset or 0)
    data   = await state.get_data()
    un_id  = data["un_id"]
    ty_id  = data["ty_id"]
    base = """
        SELECT DISTINCT m.mvdir, m.nomi, g.lan_text
        FROM mandat m JOIN getlangs g ON m.lan_id = g.lan_id
        WHERE m.un_id = %s AND m.ty_id = %s {f}
        ORDER BY m.nomi, g.lan_text LIMIT %s OFFSET %s
    """
    if text:
        cursor.execute(base.format(f="AND lower(m.nomi) LIKE %s"),
                       (un_id, ty_id, f"%{text}%", PAGE_SIZE, offset))
    else:
        cursor.execute(base.format(f=""), (un_id, ty_id, PAGE_SIZE, offset))
    rows = cursor.fetchall()
    results = [
        InlineQueryResultArticle(
            id=str(offset + i),
            title=f"{mvdir} - {nomi} ({lan_text})",
            input_message_content=InputTextMessageContent(
                message_text=f"{mvdir} - {nomi} ({lan_text})"
            )
        ) for i, (mvdir, nomi, lan_text) in enumerate(rows)
    ]
    next_offset = str(offset + PAGE_SIZE) if len(rows) == PAGE_SIZE else ""
    await inline_query.answer(results, cache_time=1, is_personal=True, next_offset=next_offset)


@reg_router.message(FormReg.reg4)
async def chosen_reg4(message: Message, state: FSMContext):
    data = await state.get_data()
    region_id = data["region_id"]
    un_id     = data["un_id"]
    ty_id     = data["ty_id"]

    if message.text == "🔙 Ortga":
        # Shakl tanlash ekraniga qaytamiz — faqat mandat da mavjud shakllar
        cursor.execute("""
            SELECT DISTINCT g.ty_id, g.ty_text
            FROM gettypes g
            WHERE g.un_id = %s
              AND EXISTS (SELECT 1 FROM mandat m WHERE m.un_id = %s AND m.ty_id = g.ty_id)
            ORDER BY g.ty_text
        """, (un_id, un_id))
        rows = cursor.fetchall()
        keyboard = [[KeyboardButton(text=ty_text)] for _, ty_text in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>",
                             parse_mode="html", reply_markup=btn)
        await state.set_state(FormReg.reg3)
        return
    if message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.main_manu())
        return

    parsed = _parse_direction_btn(message.text)
    if not parsed:
        return
    mvdir, nomi, lan_text = parsed

    # Mandat ma'lumotlarini olamiz
    cursor.execute("""
        SELECT m.lan_id, m.gr_b, m.con_b, m.olimp
        FROM mandat m JOIN getlangs g ON m.lan_id = g.lan_id
        WHERE m.un_id = %s AND m.ty_id = %s
          AND m.mvdir = %s AND m.nomi = %s AND lower(g.lan_text) = %s
        LIMIT 1
    """, (un_id, ty_id, mvdir, nomi, lan_text.lower()))
    row = cursor.fetchone()
    if not row:
        await message.answer("<b>🤷🏻‍♂️ Ma'lumot topilmadi</b>", parse_mode="html")
        return
    lan_id, gr_b, con_b, olimp = row

    cursor.execute("SELECT un_text FROM universities WHERE un_id = %s", (un_id,))
    un_name_row = cursor.fetchone()
    cursor.execute("SELECT ty_text FROM gettypes WHERE ty_id = %s", (ty_id,))
    ty_text_row = cursor.fetchone()

    await _send_result(
        message=message,
        un_id=un_id, ty_id=ty_id, lan_id=lan_id,
        un_name=un_name_row[0] if un_name_row else "—",
        mvdir=mvdir, nomi=nomi, lan_text=lan_text,
        ty_text=ty_text_row[0] if ty_text_row else "—",
        gr_b=gr_b, con_b=con_b, olimp=olimp,
    )
