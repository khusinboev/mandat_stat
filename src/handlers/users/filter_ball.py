"""
filter_ball.py — "Ball yetadigan yo'nalishlar" bo'limi

Oqim:
  ball1   → Grand / Kontrakt tanlash
  s_ball1 → Ball kiritish
  ball2   → Viloyat tanlash
  ball3   → Universitet tanlash
  ball4   → Ta'lim shakli tanlash → yo'nalishlar (qavs ichida til) ko'rsatiladi
  ball5   → Yo'nalish + til tanlash → natija (rasm + matn)
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

from config import cursor, conn, bot, ADMIN_ID
from src.handlers.users.users import create_card
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

ball_router = Router()


class FormBall(StatesGroup):
    ball1   = State()   # Grand / Kontrakt
    s_ball1 = State()   # Ball kiritish
    ball2   = State()   # Viloyat tanlash
    ball3   = State()   # Universitet tanlash
    ball4   = State()   # Shakl tanlash
    ball5   = State()   # Yo'nalish + til → natija


# ── Doimiy klaviaturalar ─────────────────────────────────────────────────────

SEARCH_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
])

BACK2_KB = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[[KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")]]
)


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
    return rest[:dash], rest[dash + 3:], lan_text


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


# ── ball1 — Grand / Kontrakt ─────────────────────────────────────────────────

@ball_router.message(F.text == "📊 Ball yetadigan yo'nalishlar", F.chat.type == ChatType.PRIVATE)
async def enter_direction(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)
    if not check_status:
        await message.answer("❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
                             reply_markup=await CheckData.channels_btn(channels))
        return
    await message.answer("<b>O'quv turini tanlang 👇</b>",
                         parse_mode="html", reply_markup=await UserPanels.ball_btn())
    await state.set_state(FormBall.ball1)


@ball_router.message(F.text == "🔙 Ortga", FormBall.ball1)
async def back_ball1(message: Message, state: FSMContext):
    await message.delete()
    await state.clear()
    await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                         parse_mode="html", reply_markup=await UserPanels.main_manu())


@ball_router.message(F.text.in_({"🏆 Grand", "📄 Kontrakt"}), FormBall.ball1)
async def chosen_shakl_type(message: Message, state: FSMContext):
    shakl = "gr" if message.text == "🏆 Grand" else "kn"
    await state.update_data(shakl=shakl)
    await state.set_state(FormBall.s_ball1)
    await message.answer("<b>Saralash uchun ballni kiriting:</b>",
                         parse_mode="html", reply_markup=await UserPanels.to_back())


# ── s_ball1 — Ball kiritish ──────────────────────────────────────────────────

@ball_router.message(FormBall.s_ball1)
async def enter_ball(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await message.answer("<b>O'quv turini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.ball_btn())
        await state.set_state(FormBall.ball1)
        return
    if message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.main_manu())
        return

    if not message.text.isdigit() or int(message.text) > 200:
        await message.answer("<b>Ball xato kiritildi!\nSaralash uchun ballni kiriting (0–200):</b>",
                             parse_mode="html", reply_markup=await UserPanels.to_back())
        return

    ball = message.text
    data = await state.get_data()
    shakl = data["shakl"]

    if shakl == "gr":
        cursor.execute("""
            SELECT DISTINCT r.region_name
            FROM mandat m JOIN regions r ON m.region_id = r.region_id
            WHERE m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'
        """, (ball,))
    else:
        cursor.execute("""
            SELECT DISTINCT r.region_name
            FROM mandat m JOIN regions r ON m.region_id = r.region_id
            WHERE m.con_b <= %s AND m.con_b != 0
        """, (ball,))
    regions = cursor.fetchall()

    if not regions:
        await message.answer("<b>🤷🏻‍♂️ Bunday ma'lumot yo'q</b>", parse_mode="html")
        await message.answer("<b>Saralash uchun ballni kiriting:</b>",
                             parse_mode="html", reply_markup=await UserPanels.to_back())
        return

    await state.update_data(ball=ball)
    keyboard = [[KeyboardButton(text=r[0])] for r in regions]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer(
        f"Bu ball bilan <b>{len(regions)}</b> ta hududdagi oliygohga kirish mumkin!\n\n"
        f"<b>📍 Hududni tanlang:</b>",
        parse_mode="html", reply_markup=btn
    )
    await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>",
                         parse_mode="html", reply_markup=SEARCH_KB)
    await state.set_state(FormBall.ball2)


# ── ball2 — Viloyat tanlash ──────────────────────────────────────────────────

@ball_router.inline_query(FormBall.ball2)
async def inline_ball2(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    shakl, ball = data["shakl"], data["ball"]
    if shakl == "gr":
        base = """
            SELECT DISTINCT r.id, r.region_name
            FROM mandat m JOIN regions r ON m.region_id = r.region_id
            WHERE m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1' {f}
            ORDER BY r.region_name LIMIT 50
        """
    else:
        base = """
            SELECT DISTINCT r.id, r.region_name
            FROM mandat m JOIN regions r ON m.region_id = r.region_id
            WHERE m.con_b <= %s AND m.con_b != 0 {f}
            ORDER BY r.region_name LIMIT 50
        """
    if text:
        cursor.execute(base.format(f="AND lower(r.region_name) LIKE %s"), (ball, f"%{text}%"))
    else:
        cursor.execute(base.format(f=""), (ball,))
    results = [
        InlineQueryResultArticle(
            id=str(rid),
            title=rname,
            input_message_content=InputTextMessageContent(message_text=rname)
        ) for rid, rname in cursor.fetchall()
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@ball_router.message(FormBall.ball2)
async def chosen_ball2(message: Message, state: FSMContext):
    data = await state.get_data()
    shakl, ball = data["shakl"], data["ball"]

    if message.text == "🔙 Ortga":
        await message.delete()
        await message.answer("<b>Saralash uchun ballni kiriting:</b>",
                             parse_mode="html", reply_markup=await UserPanels.to_back())
        await state.set_state(FormBall.s_ball1)
        return
    if message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.main_manu())
        return

    cursor.execute("SELECT region_id FROM regions WHERE region_name = %s", (message.text,))
    row = cursor.fetchone()
    if not row:
        return
    reg_id = row[0]
    await state.update_data(reg_id=reg_id)

    if shakl == "gr":
        cursor.execute("""
            SELECT DISTINCT u.un_text
            FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id
            WHERE m.region_id = %s AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'
            ORDER BY u.un_text
        """, (reg_id, ball))
    else:
        cursor.execute("""
            SELECT DISTINCT u.un_text
            FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id
            WHERE m.region_id = %s AND m.con_b <= %s AND m.con_b != 0
            ORDER BY u.un_text
        """, (reg_id, ball))
    unis = cursor.fetchall()

    if not unis:
        await message.answer("<b>🤷🏻‍♂️ Bu hududda mos universitet topilmadi</b>", parse_mode="html")
        return

    keyboard = [[KeyboardButton(text=u[0])] for u in unis]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer(
        f"<b>Siz tanlagan hududda {len(unis)} ta oliygoh mavjud:\n🏢 OTMni tanlang:</b>",
        parse_mode="html", reply_markup=btn
    )
    await message.answer("<b>Tezkor qidiruvdan foydalaning... 👇</b>",
                         parse_mode="html", reply_markup=SEARCH_KB)
    await state.set_state(FormBall.ball3)


# ── ball3 — Universitet tanlash ──────────────────────────────────────────────

@ball_router.inline_query(FormBall.ball3)
async def inline_ball3(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    reg_id, shakl, ball = data["reg_id"], data["shakl"], data["ball"]
    if shakl == "gr":
        base = """
            SELECT DISTINCT u.id, u.un_text
            FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id
            WHERE m.region_id = %s AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1' {f}
            ORDER BY u.un_text LIMIT 50
        """
    else:
        base = """
            SELECT DISTINCT u.id, u.un_text
            FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id
            WHERE m.region_id = %s AND m.con_b <= %s AND m.con_b != 0 {f}
            ORDER BY u.un_text LIMIT 50
        """
    if text:
        cursor.execute(base.format(f="AND lower(u.un_text) LIKE %s"), (reg_id, ball, f"%{text}%"))
    else:
        cursor.execute(base.format(f=""), (reg_id, ball))
    results = [
        InlineQueryResultArticle(
            id=str(uid),
            title=un_text,
            input_message_content=InputTextMessageContent(message_text=un_text)
        ) for uid, un_text in cursor.fetchall()
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@ball_router.message(FormBall.ball3)
async def chosen_ball3(message: Message, state: FSMContext):
    data = await state.get_data()
    shakl, ball, reg_id = data["shakl"], data["ball"], data["reg_id"]

    if message.text == "🔙 Ortga":
        # Viloyatlar ro'yxatiga qaytamiz
        if shakl == "gr":
            cursor.execute("""
                SELECT DISTINCT r.region_name
                FROM mandat m JOIN regions r ON m.region_id = r.region_id
                WHERE m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'
            """, (ball,))
        else:
            cursor.execute("""
                SELECT DISTINCT r.region_name
                FROM mandat m JOIN regions r ON m.region_id = r.region_id
                WHERE m.con_b <= %s AND m.con_b != 0
            """, (ball,))
        regions = cursor.fetchall()
        keyboard = [[KeyboardButton(text=r[0])] for r in regions]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer(
            f"Bu ball bilan <b>{len(regions)}</b> ta hududdagi oliygohga kirish mumkin!\n\n"
            f"<b>📍 Hududni tanlang:</b>",
            parse_mode="html", reply_markup=btn
        )
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>",
                             parse_mode="html", reply_markup=SEARCH_KB)
        await state.set_state(FormBall.ball2)
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
    await state.set_state(FormBall.ball4)

    # Shakl ro'yxatini ko'rsatamiz
    if shakl == "gr":
        ress = [("Kunduzgi",)]
    else:
        cursor.execute("""
            SELECT DISTINCT g.ty_text
            FROM gettypes g JOIN mandat m ON g.un_id = m.un_id AND g.region_id = m.region_id
            WHERE m.region_id = %s AND m.un_id = %s AND m.con_b <= %s AND m.con_b != 0
            ORDER BY g.ty_text
        """, (reg_id, str(un_id), ball))
        ress = cursor.fetchall()

    keyboard = [[KeyboardButton(text=r[0])] for r in ress]
    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>",
                         parse_mode="html", reply_markup=btn)


# ── ball4 — Shakl tanlash → yo'nalishlar (til qavs ichida) ──────────────────

@ball_router.message(FormBall.ball4)
async def chosen_ball4(message: Message, state: FSMContext):
    data = await state.get_data()
    shakl  = data["shakl"]
    ball   = data["ball"]
    reg_id = data["reg_id"]
    un_id  = data["un_id"]

    if message.text == "🔙 Ortga":
        # Universitetlar ro'yxatiga qaytamiz
        if shakl == "gr":
            cursor.execute("""
                SELECT DISTINCT u.un_text
                FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id
                WHERE m.region_id = %s AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'
                ORDER BY u.un_text
            """, (reg_id, ball))
        else:
            cursor.execute("""
                SELECT DISTINCT u.un_text
                FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id
                WHERE m.region_id = %s AND m.con_b <= %s AND m.con_b != 0
                ORDER BY u.un_text
            """, (reg_id, ball))
        unis = cursor.fetchall()
        keyboard = [[KeyboardButton(text=u[0])] for u in unis]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer(
            f"<b>Siz tanlagan hududda {len(unis)} ta oliygoh mavjud:\n🏢 OTMni tanlang:</b>",
            parse_mode="html", reply_markup=btn
        )
        await message.answer("<b>Tezkor qidiruvdan foydalaning... 👇</b>",
                             parse_mode="html", reply_markup=SEARCH_KB)
        await state.set_state(FormBall.ball3)
        return
    if message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>",
                             parse_mode="html", reply_markup=await UserPanels.main_manu())
        return

    # Shakl tanlanganini state ga saqlaymiz
    if shakl == "gr":
        ty_id = "1"   # Grand doim Kunduzgi
    else:
        cursor.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text) = %s",
                       (message.text.lower(),))
        row = cursor.fetchone()
        if not row:
            return
        ty_id = row[0]
    await state.update_data(ty_id=ty_id)

    # Yo'nalishlarni barcha tillar bilan birga ko'rsatamiz
    if shakl == "gr":
        cursor.execute("""
            SELECT m.mvdir, m.nomi, g.lan_text
            FROM mandat m JOIN getlangs g ON m.lan_id = g.lan_id
            WHERE m.region_id = %s AND m.un_id = %s AND m.ty_id = '1'
              AND m.gr_b <= %s AND m.gr_b != 0
            ORDER BY m.nomi, g.lan_text
        """, (reg_id, str(un_id), ball))
    else:
        cursor.execute("""
            SELECT m.mvdir, m.nomi, g.lan_text
            FROM mandat m JOIN getlangs g ON m.lan_id = g.lan_id
            WHERE m.region_id = %s AND m.un_id = %s AND m.ty_id = %s
              AND m.con_b <= %s AND m.con_b != 0
            ORDER BY m.nomi, g.lan_text
        """, (reg_id, str(un_id), ty_id, ball))
    rows = cursor.fetchall()

    if not rows:
        await message.answer("<b>🤷🏻‍♂️ Mos yo'nalish topilmadi</b>", parse_mode="html")
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
    await state.set_state(FormBall.ball5)


# ── ball5 — Yo'nalish tanlash → natija ──────────────────────────────────────

@ball_router.inline_query(FormBall.ball5)
async def inline_ball5(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    shakl  = data["shakl"]
    ball   = data["ball"]
    reg_id = data["reg_id"]
    un_id  = data["un_id"]
    ty_id  = data["ty_id"]

    if shakl == "gr":
        base = """
            SELECT m.id, m.mvdir, m.nomi, g.lan_text
            FROM mandat m JOIN getlangs g ON m.lan_id = g.lan_id
            WHERE m.region_id = %s AND m.un_id = %s AND m.ty_id = '1'
              AND m.gr_b <= %s AND m.gr_b != 0 {f}
            ORDER BY m.nomi, g.lan_text LIMIT 50
        """
        params_base = (reg_id, str(un_id), ball)
    else:
        base = """
            SELECT m.id, m.mvdir, m.nomi, g.lan_text
            FROM mandat m JOIN getlangs g ON m.lan_id = g.lan_id
            WHERE m.region_id = %s AND m.un_id = %s AND m.ty_id = %s
              AND m.con_b <= %s AND m.con_b != 0 {f}
            ORDER BY m.nomi, g.lan_text LIMIT 50
        """
        params_base = (reg_id, str(un_id), ty_id, ball)

    if text:
        cursor.execute(base.format(f="AND lower(m.nomi) LIKE %s"),
                       (*params_base, f"%{text}%"))
    else:
        cursor.execute(base.format(f=""), params_base)

    results = [
        InlineQueryResultArticle(
            id=str(mid),
            title=f"{mvdir} - {nomi} ({lan_text})",
            input_message_content=InputTextMessageContent(
                message_text=f"{mvdir} - {nomi} ({lan_text})"
            )
        ) for mid, mvdir, nomi, lan_text in cursor.fetchall()
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@ball_router.message(FormBall.ball5)
async def chosen_ball5(message: Message, state: FSMContext):
    data = await state.get_data()
    shakl  = data["shakl"]
    ball   = data["ball"]
    reg_id = data["reg_id"]
    un_id  = data["un_id"]
    ty_id  = data["ty_id"]

    if message.text == "🔙 Ortga":
        # Shakl tanlash ekraniga qaytamiz
        if shakl == "gr":
            ress = [("Kunduzgi",)]
        else:
            cursor.execute("""
                SELECT DISTINCT g.ty_text
                FROM gettypes g JOIN mandat m ON g.un_id = m.un_id AND g.region_id = m.region_id
                WHERE m.region_id = %s AND m.un_id = %s AND m.con_b <= %s AND m.con_b != 0
                ORDER BY g.ty_text
            """, (reg_id, str(un_id), ball))
            ress = cursor.fetchall()
        keyboard = [[KeyboardButton(text=r[0])] for r in ress]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>",
                             parse_mode="html", reply_markup=btn)
        await state.set_state(FormBall.ball4)
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
    if shakl == "gr":
        cursor.execute("""
            SELECT m.lan_id, m.gr_b, m.con_b, m.olimp
            FROM mandat m JOIN getlangs g ON m.lan_id = g.lan_id
            WHERE m.region_id = %s AND m.un_id = %s AND m.ty_id = '1'
              AND m.mvdir = %s AND m.nomi = %s AND lower(g.lan_text) = %s
            LIMIT 1
        """, (reg_id, str(un_id), mvdir, nomi, lan_text.lower()))
    else:
        cursor.execute("""
            SELECT m.lan_id, m.gr_b, m.con_b, m.olimp
            FROM mandat m JOIN getlangs g ON m.lan_id = g.lan_id
            WHERE m.region_id = %s AND m.un_id = %s AND m.ty_id = %s
              AND m.mvdir = %s AND m.nomi = %s AND lower(g.lan_text) = %s
            LIMIT 1
        """, (reg_id, str(un_id), ty_id, mvdir, nomi, lan_text.lower()))

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
