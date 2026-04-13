import os

from aiogram import Router, F
# removed  # <-- faqat bu qo‘shildi

from aiogram.enums import ChatType
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, \
    InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult, KeyboardButton, ReplyKeyboardMarkup, \
    FSInputFile

from config import sql, bot, ADMIN_ID, cursor, conn
from src.handlers.users.users import create_card
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

ball_router = Router()

# Main-menu section buttons — pressing these from any FSM state should clear
# state and return the user to the main menu.
_SECTION_BTNS = frozenset({
    "📊 Ball yetadigan yo'nalishlar",
    "\U0001f4da Yo\u02bbnalishlar bo\u02bbyicha",
    "📈 Viloyatlar kesimida",
})

_SCORE_YEAR = 2025
_CAPTION_YEARS = (2025, 2024, 2023)

class FormBall(StatesGroup):
    ball1 = State()
    s_ball1 = State()
    ball2 = State()
    ball3 = State()
    ball4 = State()
    ball5 = State()
    ball6 = State()


@ball_router.message(F.text == "📊 Ball yetadigan yo'nalishlar", F.chat.type == ChatType.PRIVATE)
async def enter_direction(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        await message.answer("<b>O'quv turini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.ball_btn())
        await state.set_state(FormBall.ball1)
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))


@ball_router.message(F.text == "🔙 Ortga", FormBall.ball1)
async def handle_hello(message: Message, state: FSMContext):
    await message.delete()
    await state.clear()
    await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                         reply_markup=await UserPanels.main_manu())


@ball_router.message(F.text == "🏆 Grand", FormBall.ball1)
async def enter_direction(message: Message, state: FSMContext):
    await message.answer("<b>Saralash uchun ballni kiriting:</b>", parse_mode="html",
                         reply_markup=await UserPanels.to_back())
    await state.set_state(FormBall.s_ball1)
    await state.update_data(shakl="gr")


@ball_router.message(F.text == "📄 Kontrakt", FormBall.ball1)
async def enter_direction(message: Message, state: FSMContext):
    await message.answer("<b>Saralash uchun ballni kiriting:</b>", parse_mode="html",
                         reply_markup=await UserPanels.to_back())
    await state.set_state(FormBall.s_ball1)
    await state.update_data(shakl="kn")


@ball_router.message(FormBall.s_ball1)
async def enter_direction(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await message.answer("<b>O'quv turini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.ball_btn())
        await state.set_state(FormBall.ball1)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        if message.text.isdigit():
            if int(message.text) > 200:
                await message.answer("<b>Ball xato kiritildi!\nSaralash uchun ballni kiriting:</b>", parse_mode="html",
                                     reply_markup=await UserPanels.to_back())
            else:
                data = await state.get_data()
                shakl = data["shakl"]
                if shakl == "gr":
                    cursor.execute("""
                        SELECT DISTINCT r.region_name 
                        FROM mandat m 
                        JOIN regions r ON m.region_id = r.region_id 
                        WHERE m.year = 2025 AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'
                        ORDER BY r.region_name
                    """, (message.text,))
                elif shakl == "kn":
                    cursor.execute("""
                        SELECT DISTINCT r.region_name 
                        FROM mandat m 
                        JOIN regions r ON m.region_id = r.region_id 
                        WHERE m.year = 2025 AND m.con_b <= %s AND m.con_b != 0
                        ORDER BY r.region_name
                    """, (message.text,))
                regions = cursor.fetchall()
                if regions:
                    keyboard = []
                    for row in regions:
                        keyboard.append([KeyboardButton(text=row[0])])
                    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

                    btn = ReplyKeyboardMarkup(
                        keyboard=keyboard,
                        resize_keyboard=True,
                    )
                    await message.answer(f"Bu ball bilan <b>{len(regions)}</b> ta hududdagi oliygohga kirish mumkin!\n\n<b>📍 Hududni tanlang:</b>", parse_mode="html",
                                         reply_markup=btn)

                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
                    ])
                    await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
                    await state.set_state(FormBall.ball2)
                    await state.update_data(ball=message.text)
                else:
                    await message.answer("<b>🤷🏻‍♂️ Bunday ma'lumot yo'q</b>", parse_mode="html")
                    await message.answer("<b>Saralash uchun ballni kiriting:</b>", parse_mode="html", reply_markup=await UserPanels.to_back())

@ball_router.inline_query(FormBall.ball2)
async def inline_search_ball(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    shakl = data["shakl"]
    ball = data["ball"]
    if shakl == "gr":
        if text:
            cursor.execute("""
                        SELECT DISTINCT r.region_id, r.region_name 
                FROM mandat m 
                JOIN regions r ON m.region_id = r.region_id 
                WHERE lower(r.region_name) LIKE %s 
                AND m.year = 2025 AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'
                ORDER BY r.region_name
                LIMIT 50
            """, (f"%{text}%", ball))
        else:
            cursor.execute("""
                SELECT DISTINCT r.region_id, r.region_name 
                FROM mandat m 
                JOIN regions r ON m.region_id = r.region_id 
                WHERE m.year = 2025 AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'
                ORDER BY r.region_name
                LIMIT 50
            """, (ball,))
        regions = cursor.fetchall()
        results = [
            InlineQueryResultArticle(
                id=str(reg_id),
                title=reg_text,
                input_message_content=InputTextMessageContent(message_text=reg_text)
            ) for reg_id, reg_text in regions
        ]
        await inline_query.answer(results, cache_time=1, is_personal=True)

    elif shakl == "kn":
        if text:
            cursor.execute("""
                SELECT DISTINCT r.region_id, r.region_name 
                FROM mandat m 
                JOIN regions r ON m.region_id = r.region_id 
                WHERE lower(r.region_name) LIKE %s 
                AND m.year = 2025 AND m.con_b <= %s AND m.con_b != 0
                ORDER BY r.region_name
                LIMIT 50
            """, (f"%{text}%", ball))
        else:
            cursor.execute("""
                SELECT DISTINCT r.region_id, r.region_name 
                FROM mandat m 
                JOIN regions r ON m.region_id = r.region_id 
                WHERE m.year = 2025 AND m.con_b <= %s AND m.con_b != 0
                ORDER BY r.region_name
                LIMIT 50
            """, (ball,))
        regions = cursor.fetchall()
        results = [
            InlineQueryResultArticle(
                id=str(reg_id),
                title=reg_text,
                input_message_content=InputTextMessageContent(message_text=reg_text)
            ) for reg_id, reg_text in regions
        ]
        await inline_query.answer(results, cache_time=1, is_personal=True)


@ball_router.message(FormBall.ball2)
async def chosen_university(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await message.answer("<b>Saralash uchun ballni kiriting:</b>", parse_mode="html",
                             reply_markup=await UserPanels.to_back())
        await state.set_state(FormBall.s_ball1)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        if message.text in _SECTION_BTNS:
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                                 reply_markup=await UserPanels.main_manu())
            return
        reg_name = message.text.lower()
        cursor.execute("SELECT region_id FROM regions WHERE lower(region_name)=%s", (reg_name,))
        reg_id_data = cursor.fetchall()
        if reg_id_data:
            reg_id = reg_id_data[0][0]
            await state.update_data(reg_id=reg_id)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            data = await state.get_data()
            shakl = data["shakl"]
            ball = data["ball"]
            if shakl == "gr":
                cursor.execute("""
                    SELECT u.id 
                    FROM universities u 
                    JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id 
                    WHERE m.region_id = %s 
                    AND m.year = 2025 AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'
                """, (reg_id, ball))
                rows = cursor.fetchall()
                await message.answer(f"<b>Siz tanlagan hududda {len(set(rows))} ta oliygoh mavjud:\n🏢 OTMni tanlang:</b>",
                                     parse_mode="html", reply_markup=await UserPanels.to_back())
                await message.answer("<b>Tezkor qidiruvdan foydalaning... 👇</b>", parse_mode="html", reply_markup=kb)
                await state.set_state(FormBall.ball3)
            elif shakl == "kn":
                cursor.execute("""
                    SELECT u.id, u.un_text 
                    FROM universities u 
                    JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id 
                    WHERE m.region_id = %s 
                    AND m.year = 2025 AND m.con_b <= %s AND m.con_b != 0
                """, (reg_id, ball))
                rows = cursor.fetchall()
                await message.answer(f"<b>Siz tanlagan hududda {len(set(rows))} ta oliygoh mavjud:\n🏢 OTMni tanlang:</b>",
                                     parse_mode="html", reply_markup=await UserPanels.to_back())
                await message.answer("<b>Tezkor qidiruvdan foydalaning... 👇</b>", parse_mode="html", reply_markup=kb)
                await state.set_state(FormBall.ball3)
# Universitet izlash
@ball_router.inline_query(FormBall.ball3)
async def inline_search_university(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    reg_id = data.get("reg_id")
    shakl = data["shakl"]
    ball = data["ball"]
    if shakl == "gr":
        if text:
            cursor.execute(
                "SELECT DISTINCT u.un_id, u.un_text FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE lower(un_text) LIKE %s AND m.region_id = %s AND m.year = 2025 AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'",
                (f"%{text}%", reg_id, ball))
        else:
            cursor.execute(
                "SELECT DISTINCT u.un_id, u.un_text FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE m.region_id = %s AND m.year = 2025 AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'",
                (reg_id, ball))
    elif shakl == "kn":
        if text:
            cursor.execute(
                "SELECT DISTINCT u.un_id, u.un_text FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE lower(un_text) LIKE %s AND m.region_id = %s AND m.year = 2025 AND m.con_b <= %s AND m.con_b != 0",
                (f"%{text}%", reg_id, ball))
        else:
            cursor.execute(
                "SELECT DISTINCT u.un_id, u.un_text FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE m.region_id = %s AND m.year = 2025 AND m.con_b <= %s AND m.con_b != 0",
                (reg_id, ball))
    res_data = cursor.fetchall()
    if res_data:
        universities = res_data[:50]
        results = [InlineQueryResultArticle(
                id=str(un_id),
                title=un_text,
                input_message_content=InputTextMessageContent(message_text=un_text)
            ) for un_id, un_text in universities]
        await inline_query.answer(results, cache_time=1, is_personal=True)


@ball_router.message(FormBall.ball3)
async def chosen_university(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        data = await state.get_data()
        shakl = data["shakl"]
        ball = data["ball"]
        if shakl == "gr":
            cursor.execute(
                "SELECT DISTINCT r.region_name FROM mandat m JOIN regions r ON m.region_id = r.region_id "
                "WHERE m.year = 2025 AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'",
                (ball,))
        elif shakl == "kn":
            cursor.execute(
                "SELECT DISTINCT r.region_name FROM mandat m JOIN regions r ON m.region_id = r.region_id "
                "WHERE m.year = 2025 AND m.con_b <= %s AND m.con_b != 0",
                (ball,))
        regions = cursor.fetchall()
        if regions:
            keyboard = [[KeyboardButton(text=row[0])] for row in regions]
            keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
            btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
            await message.answer(
                f"Bu ball bilan <b>{len(regions)}</b> ta hududdagi oliygohga kirish mumkin!\n\n<b>📍 Hududni tanlang:</b>",
                parse_mode="html", reply_markup=btn)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
            await state.set_state(FormBall.ball2)
            await state.update_data(ball=ball)
        else:
            await message.answer("<b>🤷🏻‍♂️ Bunday ma'lumot yo'q</b>", parse_mode="html")
            await message.answer("<b>Saralash uchun ballni kiriting:</b>", parse_mode="html",
                                 reply_markup=await UserPanels.to_back())
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        if message.text in _SECTION_BTNS:
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                                 reply_markup=await UserPanels.main_manu())
            return
        un_name = message.text
        cursor.execute("SELECT un_id FROM universities WHERE lower(un_text) = %s", (un_name.lower(),))
        result = cursor.fetchone()
        if result:
            un_id = result[0]
            await state.update_data(un_id=un_id)
            await state.set_state(FormBall.ball4)
            data = await state.get_data()
            reg_id = data["reg_id"]
            shakl = data["shakl"]
            ball = data["ball"]
            if shakl == "gr":
                ress = [["Kunduzgi"]]
            elif shakl == "kn":
                cursor.execute(
                    "SELECT DISTINCT g.ty_text FROM gettypes g JOIN mandat m ON g.un_id::text = m.un_id::text AND g.region_id::text = m.region_id::text "
                    "WHERE m.region_id = %s AND m.un_id = %s AND m.year = 2025 AND m.con_b <= %s AND m.con_b != 0",
                    (reg_id, str(un_id), ball))
                ress = cursor.fetchall()
            keyboard = [[KeyboardButton(text=row[0])] for row in ress]
            keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
            btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
            await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)


@ball_router.message(FormBall.ball4)
async def chosen_type(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        try:
            await message.delete()
        except:
            pass
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        data = await state.get_data()
        shakl = data["shakl"]
        reg_id = data["reg_id"]
        ball = data["ball"]
        if shakl == "gr":
            cursor.execute(
                "SELECT DISTINCT u.id FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE m.region_id = %s AND m.year = 2025 AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'",
                (reg_id, ball))
        elif shakl == "kn":
            cursor.execute(
                "SELECT DISTINCT u.id FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE m.region_id = %s AND m.year = 2025 AND m.con_b <= %s AND m.con_b != 0",
                (reg_id, ball))
        rows = cursor.fetchall()
        await message.answer(f"<b>Siz tanlagan hududda {len(rows)} ta oliygoh mavjud:\n🏢 OTMni tanlang:</b>",
                             parse_mode="html", reply_markup=await UserPanels.to_back())
        await message.answer("<b>Tezkor qidiruvdan foydalaning... 👇</b>", parse_mode="html", reply_markup=kb)
        await state.set_state(FormBall.ball3)
    elif message.text == "🔙 Bosh menu":
        try:
            await message.delete()
            await state.clear()
        except: pass
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        if message.text in _SECTION_BTNS:
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                                 reply_markup=await UserPanels.main_manu())
            return
        name = message.text.lower()
        data = await state.get_data()
        un_id = data.get("un_id")
        cursor.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text) = %s AND un_id = %s", (name, un_id))
        ty = cursor.fetchone()
        if ty:
            ty_id = ty[0]
            await state.update_data(ty_id=ty_id)
            await state.set_state(FormBall.ball5)
            data = await state.get_data()
            un_id = data["un_id"]
            reg_id = data["reg_id"]
            shakl = data["shakl"]
            ball = data["ball"]
            if shakl == "gr":
                cursor.execute("""
                    SELECT DISTINCT g.lan_id, g.lan_text FROM mandat m
                    JOIN getlangs g ON m.lan_id::text = g.lan_id::text AND m.un_id::text = g.un_id::text AND m.ty_id::text = g.ty_id::text AND m.region_id::text = g.region_id::text
                    WHERE m.un_id = %s AND m.ty_id = %s AND m.region_id = %s 
                    AND m.year = 2025 AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1'
                """, (un_id, ty_id, reg_id, ball))
            elif shakl == "kn":
                cursor.execute("""
                    SELECT DISTINCT g.lan_id, g.lan_text FROM mandat m
                    JOIN getlangs g ON m.lan_id::text = g.lan_id::text AND m.un_id::text = g.un_id::text AND m.ty_id::text = g.ty_id::text AND m.region_id::text = g.region_id::text
                    WHERE m.un_id = %s AND m.ty_id = %s AND m.region_id = %s 
                    AND m.year = 2025 AND m.con_b <= %s AND m.con_b != 0
                """, (un_id, ty_id, reg_id, ball))
            rows = cursor.fetchall()
            keyboard = [[KeyboardButton(text=row[1][:60])] for row in rows]
            keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
            btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
            await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)

@ball_router.message(FormBall.ball5)
async def chosen_lang(message: Message, state: FSMContext):
    lan_text = message.text.lower()
    if message.text == "🔙 Ortga":
        await message.delete()
        data = await state.get_data()
        reg_id = data.get("reg_id")
        un_id = data.get("un_id")
        shakl = data["shakl"]
        ball = data["ball"]
        if shakl == "gr":
            ress = [["Kunduzgi"]]
        elif shakl == "kn":
            cursor.execute(
                "SELECT DISTINCT g.ty_text FROM gettypes g JOIN mandat m ON g.un_id::text = m.un_id::text AND g.region_id::text = m.region_id::text "
                "WHERE m.region_id = %s AND m.un_id = %s AND m.year = 2025 AND m.con_b <= %s AND m.con_b != 0 ", (reg_id, un_id, ball))
            ress = cursor.fetchall()
        keyboard = [[KeyboardButton(text=row[0])] for row in ress]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
        await state.set_state(FormBall.ball4)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        if message.text in _SECTION_BTNS:
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                                 reply_markup=await UserPanels.main_manu())
            return
        data = await state.get_data()
        un_id = data.get("un_id")
        ty_id = data.get("ty_id")
        reg_id = data.get("reg_id")
        cursor.execute(
            "SELECT lan_id FROM getlangs WHERE lower(lan_text) = %s AND un_id = %s AND ty_id = %s AND region_id = %s",
            (lan_text, un_id, ty_id, reg_id),
        )
        lan = cursor.fetchone()
        if lan:
            lan_id = lan[0]
            await state.update_data(lan_id=lan_id)
            data = await state.get_data()
            un_id = data["un_id"]
            ty_id = data["ty_id"]
            lan_id = data["lan_id"]
            reg_id = data.get("reg_id")
            shakl = data["shakl"]
            ball = data["ball"]
            if shakl == "gr":
                cursor.execute("""SELECT mvdir, nomi FROM mandat WHERE year=2025 AND region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s AND gr_b<=%s""",
                               (reg_id, un_id, ty_id, lan_id, ball))
            elif shakl == "kn":
                cursor.execute("""SELECT mvdir, nomi FROM mandat WHERE year=2025 AND region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s AND con_b<=%s""",
                               (reg_id, un_id, ty_id, lan_id, ball))
            rows = cursor.fetchall()
            keyboard = [[KeyboardButton(text=f"{mvdir} - {nomi}")] for mvdir, nomi in rows]
            keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
            btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            await message.answer(f"{len(rows)} ta yo'nalish mavjud:\n📚 Ta'lim yo'nalishini tanlang:", parse_mode="html", reply_markup=btn)
            await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
            await state.set_state(FormBall.ball6)


@ball_router.inline_query(FormBall.ball6)
async def inline_search_region(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    un_id = data["un_id"]
    ty_id = data["ty_id"]
    lan_id = data["lan_id"]
    reg_id = data.get("reg_id")
    shakl = data["shakl"]
    ball = data["ball"]
    if shakl == "gr":
        if text:
                cursor.execute("""SELECT DISTINCT id, mvdir, nomi FROM mandat 
                                        WHERE year=2025 AND lower(nomi) LIKE %s AND region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s AND gr_b<=%s""",
                           (f"%{text}%", reg_id, un_id, ty_id, lan_id, ball))
        else:
            cursor.execute("""SELECT DISTINCT id, mvdir, nomi FROM mandat 
                                        WHERE year=2025 AND region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s AND gr_b<=%s""",
                           (reg_id, un_id, ty_id, lan_id, ball))
    elif shakl == "kn":
        if text:
                cursor.execute("""SELECT DISTINCT id, mvdir, nomi FROM mandat 
                                        WHERE year=2025 AND lower(nomi) LIKE %s AND region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s AND con_b<=%s""",
                           (f"%{text}%", reg_id, un_id, ty_id, lan_id, ball))
        else:
            cursor.execute("""SELECT DISTINCT id, mvdir, nomi FROM mandat 
                                        WHERE year=2025 AND region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s AND con_b<=%s""",
                           (reg_id, un_id, ty_id, lan_id, ball))
    facs = cursor.fetchall()[:50]
    results = [
        InlineQueryResultArticle(
            id=str(id),
            title=f"{mvdir} - {nomi}",
            input_message_content=InputTextMessageContent(message_text=f'{mvdir} - {nomi}', parse_mode="HTML"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
        ) for id, mvdir, nomi in facs
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@ball_router.message(FormBall.ball6)
async def chosen_lang(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await state.set_state(FormBall.ball5)
        try:
            await message.delete()
        except:
            pass
        data = await state.get_data()
        un_id = data.get("un_id")
        reg_id = data.get("reg_id")
        shakl = data["shakl"]
        ball = data["ball"]
        ty_id = data["ty_id"]
        if shakl == "gr":
            cursor.execute('''SELECT DISTINCT g.lan_id, g.lan_text FROM mandat m 
                              JOIN getlangs g ON m.lan_id::text = g.lan_id::text AND m.un_id::text = g.un_id::text AND m.ty_id::text = g.ty_id::text AND m.region_id::text = g.region_id::text
                                        WHERE m.un_id = %s AND m.ty_id = %s AND m.region_id = %s AND m.year = 2025 AND m.gr_b <= %s AND m.gr_b != 0 AND m.ty_id = '1' ''',
                           (un_id, ty_id, reg_id, ball))
        elif shakl == "kn":
            cursor.execute('''SELECT DISTINCT g.lan_id, g.lan_text FROM mandat m 
                              JOIN getlangs g ON m.lan_id::text = g.lan_id::text AND m.un_id::text = g.un_id::text AND m.ty_id::text = g.ty_id::text AND m.region_id::text = g.region_id::text
                                        WHERE m.un_id = %s AND m.ty_id = %s AND m.region_id = %s AND m.year = 2025 AND m.con_b <= %s AND m.con_b != 0''',
                           (un_id, ty_id, reg_id, ball))
        rows = cursor.fetchall()
        keyboard = [[KeyboardButton(text=row[1][:60])] for row in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        if message.text in _SECTION_BTNS:
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                                 reply_markup=await UserPanels.main_manu())
            return
        if " - " not in message.text:
            await message.answer("Yo'nalishni ro'yxatdan tanlang yoki inline qidiruvdan foydalaning.")
            return
        mvdir, nomi = message.text.split(" - ", 1)
        data = await state.get_data()
        un_id = data["un_id"]
        ty_id = data["ty_id"]
        lan_id = data["lan_id"]
        reg_id = data.get("reg_id")
        shakl = data["shakl"]
        ball = data["ball"]
        if shakl == "gr":
                cursor.execute("""SELECT gr_b, con_b, olimp FROM mandat 
                                        WHERE year=2025 AND un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s AND nomi=%s AND region_id=%s AND gr_b<=%s""",
                           (un_id, ty_id, lan_id, mvdir, nomi, reg_id, ball))
        elif shakl == "kn":
                cursor.execute("""SELECT gr_b, con_b, olimp FROM mandat 
                                        WHERE year=2025 AND un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s AND nomi=%s AND region_id=%s AND con_b<=%s""",
                           (un_id, ty_id, lan_id, mvdir, nomi, reg_id, ball))
        kaup = cursor.fetchone()
        if kaup:
            gr_b, con_b, olimp = kaup
            cursor.execute(
                """
                SELECT year, gr_b, con_b
                FROM mandat
                WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s AND nomi=%s AND region_id=%s
                  AND year IN (2025, 2024, 2023)
                ORDER BY year DESC
                """,
                (un_id, ty_id, lan_id, mvdir, nomi, reg_id),
            )
            year_rows = cursor.fetchall()
            year_scores = {int(y): (float(gb or 0), float(cb or 0)) for y, gb, cb in year_rows}
            score_lines = []
            for y in _CAPTION_YEARS:
                if y in year_scores:
                    y_gr, y_con = year_scores[y]
                    score_lines.append(f"<b>{y}</b>: Grand {y_gr} | Kontrakt {y_con}")
            score_block = "\n".join(score_lines) if score_lines else f"<b>{_SCORE_YEAR}</b>: Grand {gr_b} | Kontrakt {con_b}"

            cursor.execute("SELECT un_text FROM universities WHERE un_id=%s", (un_id,))
            un_row = cursor.fetchone()
            cursor.execute("SELECT lan_text FROM getlangs WHERE lan_id=%s", (lan_id,))
            lan_row = cursor.fetchone()
            cursor.execute("SELECT ty_text FROM gettypes WHERE ty_id=%s", (ty_id,))
            ty_row = cursor.fetchone()
            if not un_row or not lan_row or not ty_row:
                await message.answer("Ma'lumot to'liq topilmadi. Iltimos, qaytadan urinib ko'ring.")
                return

            un_name = un_row[0]
            lan_text = lan_row[0]
            ty_text = ty_row[0]
            message_text = (
                f"<b>🏛 OLIYGOH:</b> {un_name}\n\n<b>📚 TAʼLIM YO‘NALISHI</b> - {mvdir} - {nomi}\n\n<b>🇺🇿 TAʼLIM TILI</b> - {lan_text}\n\n"
                f"<b>🔰 TAʼLIM SHAKLI</b> - {ty_text}\n\n<b>📈 OʻTISH BALLARI (yillar kesimida):</b>\n{score_block}\n\n"
                f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
                f"<b>© <a href='https://t.me/mandatjavobbot?start=share'>@Mandatjavobbot</a> - oʻtish ballari va mandat natijalari</b>")
            user_id = message.from_user.id
            cursor.execute("""SELECT file_id FROM photos 
                              WHERE un_id = %s AND ty_id = %s AND lan_id = %s AND mvdir = %s""",
                           (un_id, ty_id, lan_id, mvdir))
            old = cursor.fetchone()
            if old:
                await message.answer_photo(photo=old[0], caption=message_text, parse_mode="html")
            else:
                if create_card(univer=un_name, faculty=f"{mvdir} - {nomi}", lang=lan_text, edu=ty_text,
                               grand=gr_b, kont=con_b, olmp=olimp, name=user_id):
                    path = f"{os.path.dirname(os.path.abspath(__file__))}/photos/{user_id}.jpg"
                    sent_message = await message.answer_photo(photo=FSInputFile(path), caption=message_text, parse_mode="html")
                    file_id = sent_message.photo[-1].file_id
                    cursor.execute("""
                        INSERT INTO photos (un_id, ty_id, lan_id, mvdir, file_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (un_id, ty_id, lan_id, mvdir, file_id))
                    conn.commit()
                    if os.path.exists(path):
                        os.remove(path)
                else:
                    await message.answer(message_text, parse_mode="html")
