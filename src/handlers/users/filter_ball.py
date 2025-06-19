import os

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
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
            if int(message.text)>200:
                await message.answer("<b>Ball xato kiritildi!\nSaralash uchun ballni kiriting:</b>", parse_mode="html",
                                     reply_markup=await UserPanels.to_back())
            else:
                data = await state.get_data()
                shakl = data["shakl"]
                if shakl == "gr":
                    cursor.execute("SELECT r.region_name FROM mandat m JOIN regions r ON m.region_id = r.region_id WHERE m.gr_b <= ? AND m.gr_b != 0 AND m.ty_id = 1", (message.text,))
                elif shakl == "kn":
                    cursor.execute(
                        "SELECT r.region_name FROM mandat m JOIN regions r ON m.region_id = r.region_id WHERE m.con_b <= ? AND m.con_b != 0",
                        (message.text,))
                regions = set(cursor.fetchall())
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
            cursor.execute("SELECT r.id, r.region_name FROM mandat m JOIN regions r ON m.region_id = r.region_id WHERE lower(r.region_name) LIKE ? and m.gr_b <= ? AND m.gr_b != 0 AND m.ty_id = 1", (f"%{text}%", ball))
        else:
            cursor.execute(
                "SELECT r.id, r.region_name FROM mandat m JOIN regions r ON m.region_id = r.region_id WHERE m.gr_b <= ? AND m.gr_b != 0 AND m.ty_id = 1",
                (ball,))
        regions = list(dict.fromkeys(cursor.fetchall()))[:50]
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
            cursor.execute("SELECT r.id, r.region_name FROM mandat m JOIN regions r ON m.region_id = r.region_id WHERE lower(r.region_name) LIKE ? and m.con_b <= ? AND m.con_b != 0", (f"%{text}%", ball))
        else:
            cursor.execute(
                "SELECT r.id, r.region_name FROM mandat m JOIN regions r ON m.region_id = r.region_id WHERE m.con_b <= ? AND m.con_b != 0",
                (ball,))
        regions = list(dict.fromkeys(cursor.fetchall()))[:50]
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
        reg_name = message.text.lower()
        cursor.execute("SELECT region_id FROM regions WHERE lower(region_name)=?", (reg_name, ))
        reg_id = cursor.fetchall()
        if reg_id:
            reg_id = reg_id[0][0]
            await state.update_data(reg_id=reg_id)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            data = await state.get_data()
            shakl = data["shakl"]
            if shakl == "gr":
                ball = data["ball"]
                reg_id = data["reg_id"]
                rows = cursor.execute(
                    "SELECT u.id FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                    "WHERE m.region_id = ? AND m.gr_b <= ? AND m.gr_b != 0 AND m.ty_id = 1", (reg_id, ball)).fetchall()
                await message.answer(f"<b>Siz tanlagan hududda {len(set(rows))} ta oliygoh mavjud:\n🏢 OTMni tanlang:</b>", parse_mode="html", reply_markup=await UserPanels.to_back())
                await message.answer("<b>Tezkor qidiruvdan foydalaning... 👇</b>", parse_mode="html", reply_markup=kb)
                await state.set_state(FormBall.ball3)
            elif shakl == "kn":
                ball = data["ball"]
                reg_id = data["reg_id"]
                rows = cursor.execute("SELECT u.id, u.un_text FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                                      "WHERE m.region_id = ? AND m.con_b <= ? AND m.con_b != 0", (reg_id, ball)).fetchall()
                await message.answer(f"<b>Siz tanlagan hududda {len(set(rows))} ta oliygoh mavjud:\n🏢 OTMni tanlang:</b>", parse_mode="html",
                                     reply_markup=await UserPanels.to_back())
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
                "SELECT u.id, u.un_text FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE lower(un_text) LIKE ? and m.region_id = ? AND m.gr_b <= ? AND m.gr_b != 0 AND m.ty_id = 1", (f"%{text}%", reg_id, ball))
        else:
            cursor.execute("SELECT u.id, u.un_text FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                           "WHERE m.region_id = ? AND m.gr_b <= ? AND m.gr_b != 0 AND m.ty_id = 1", (reg_id, ball))
    elif shakl == "kn":
        if text:
            cursor.execute(
                "SELECT u.id, u.un_text FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE lower(un_text) LIKE ? and m.region_id = ? AND m.con_b <= ? AND m.con_b != 0",
                (f"%{text}%", reg_id, ball))
        else:
            cursor.execute(
                "SELECT u.id, u.un_text FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE m.region_id = ? AND m.con_b <= ? AND m.con_b != 0", (reg_id, ball))
    res_data = cursor.fetchall()
    if res_data:
        universities = list(dict.fromkeys(res_data))[:50]
        results = [InlineQueryResultArticle(
                id=str(un_id),
                title=un_text,
                input_message_content=InputTextMessageContent(message_text=un_text)
            ) for un_id, un_text in universities
        ]
        await inline_query.answer(results, cache_time=1, is_personal=True)


@ball_router.message(FormBall.ball3)
async def chosen_university(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        data = await state.get_data()
        shakl = data["shakl"]
        if shakl == "gr":
            cursor.execute(
                "SELECT r.region_name FROM mandat m JOIN regions r ON m.region_id = r.region_id WHERE m.gr_b <= ? AND m.gr_b != 0 AND m.ty_id = 1",
                (message.text,))
        elif shakl == "kn":
            cursor.execute(
                "SELECT r.region_name FROM mandat m JOIN regions r ON m.region_id = r.region_id WHERE m.con_b <= ? AND m.con_b != 0",
                (message.text,))
        regions = set(cursor.fetchall())
        if regions:
            keyboard = []
            for row in regions:
                keyboard.append([KeyboardButton(text=row[0])])
            keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

            btn = ReplyKeyboardMarkup(
                keyboard=keyboard,
                resize_keyboard=True,
            )
            await message.answer(
                f"Bu ball bilan <b>{len(regions)}</b> ta hududdagi oliygohga kirish mumkin!\n\n<b>📍 Hududni tanlang:</b>",
                parse_mode="html",
                reply_markup=btn)

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
            await state.set_state(FormBall.ball2)
            await state.update_data(ball=message.text)
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
        un_name = message.text
        cursor.execute("SELECT un_id FROM universities WHERE lower(un_text)=?", (un_name.lower(),))
        un_id = cursor.fetchall()
        if un_id:
            un_id = un_id[0][0]
            await state.update_data(un_id=un_id)
            await state.set_state(FormBall.ball4)
            data = await state.get_data()
            reg_id = data.get("reg_id")
            un_id = data.get("un_id")
            shakl = data["shakl"]
            ball = data["ball"]
            if shakl == "gr":
                ress = [["Kunduzgi"]]
            elif shakl == "kn":
                rows = cursor.execute(
                    "SELECT g.ty_text FROM gettypes g JOIN mandat m ON g.un_id = m.un_id AND g.region_id = m.region_id "
                    "WHERE m.region_id = ? AND m.un_id = ? AND m.con_b <= ?  AND m.con_b != 0 ", (reg_id, un_id, ball))
                ress = set(rows.fetchall())
            keyboard = []
            for row in ress:
                keyboard.append([KeyboardButton(text=row[0])])

            keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

            btn = ReplyKeyboardMarkup(
                keyboard=keyboard,
                resize_keyboard=True,
            )
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
        if shakl == "gr":
            ball = data["ball"]
            reg_id = data["reg_id"]
            rows = cursor.execute(
                "SELECT u.id FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE m.region_id = ? AND m.gr_b <= ? AND m.gr_b != 0 AND m.ty_id = 1", (reg_id, ball)).fetchall()
            await message.answer(f"<b>Siz tanlagan hududda {len(set(rows))} ta oliygoh mavjud:\n🏢 OTMni tanlang:</b>",
                                 parse_mode="html", reply_markup=await UserPanels.to_back())
            await message.answer("<b>Tezkor qidiruvdan foydalaning... 👇</b>", parse_mode="html", reply_markup=kb)
            await state.set_state(FormBall.ball3)
        elif shakl == "kn":
            ball = data["ball"]
            reg_id = data["reg_id"]
            rows = cursor.execute(
                "SELECT u.id, u.un_text FROM universities u JOIN mandat m ON u.un_id = m.un_id AND u.region_id = m.region_id "
                "WHERE m.region_id = ? AND m.con_b <= ? AND m.con_b != 0", (reg_id, ball)).fetchall()
            await message.answer(f"<b>Siz tanlagan hududda {len(set(rows))} ta oliygoh mavjud:\n🏢 OTMni tanlang:</b>",
                                 parse_mode="html",
                                 reply_markup=await UserPanels.to_back())
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
        name = message.text.lower()
        cursor.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text)=?", (name,))
        ty_id = cursor.fetchall()
        if ty_id:
            ty_id = ty_id[0][0]
            await state.update_data(ty_id=ty_id)
            await state.set_state(FormBall.ball5)
            data = await state.get_data()
            un_id = data.get("un_id")
            reg_id = data.get("reg_id")
            shakl = data["shakl"]
            ball = data["ball"]
            if shakl == "gr":
                rows = cursor.execute('''
                    SELECT DISTINCT g.lan_id, g.lan_text
                    FROM mandat m
                    JOIN getlangs g ON m.lan_id = g.lan_id
                    WHERE m.un_id = ? AND m.ty_id = ? AND m.region_id = ? AND m.gr_b <= ? AND m.gr_b != 0 AND m.ty_id = 1
                ''', (un_id, ty_id, reg_id, ball)).fetchall()
            elif shakl == "kn":
                rows = cursor.execute('''
                                        SELECT DISTINCT g.lan_id, g.lan_text
                                        FROM mandat m
                                        JOIN getlangs g ON m.lan_id = g.lan_id
                                        WHERE m.un_id = ? AND m.ty_id = ? AND m.region_id = ? AND m.con_b <= ? AND m.con_b != 0
                                    ''', (un_id, ty_id, reg_id, ball)).fetchall()
            keyboard = []
            for row1, row2 in rows:
                keyboard.append([KeyboardButton(text=row2[:60])])

            keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

            btn = ReplyKeyboardMarkup(
                keyboard=keyboard,
                resize_keyboard=True,
            )
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
            rows = cursor.execute(
                "SELECT g.ty_text FROM gettypes g JOIN mandat m ON g.un_id = m.un_id AND g.region_id = m.region_id "
                "WHERE m.region_id = ? AND m.un_id = ? AND m.con_b <= ?  AND m.con_b != 0 ", (reg_id, un_id, ball))
            ress = set(rows.fetchall())
        keyboard = []
        for row in ress:
            keyboard.append([KeyboardButton(text=row[0])])

        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

        btn = ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
        )
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
        await state.set_state(FormBall.ball4)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                                      reply_markup=await UserPanels.main_manu())
    else:
        cursor.execute("SELECT lan_id FROM getlangs WHERE lower(lan_text)=?", (lan_text,))
        lan_id = cursor.fetchall()
        if lan_id:
            lan_id = list(dict.fromkeys(lan_id))[0][0]
            print(lan_id)
            await state.update_data(lan_id=lan_id)
            data = await state.get_data()
            un_id = data["un_id"]
            ty_id = data["ty_id"]
            lan_id = data["lan_id"]
            reg_id = data.get("reg_id")
            shakl = data["shakl"]
            ball = data["ball"]

            if shakl == "gr":
                cursor.execute("""SELECT mvdir, nomi FROM mandat WHERE region_id=? and un_id=? AND ty_id=? AND lan_id=? and gr_b<=?""",
                               (reg_id, un_id, ty_id, lan_id, ball))
            elif shakl == "kn":
                cursor.execute(
                    """SELECT mvdir, nomi FROM mandat WHERE region_id=? and un_id=? AND ty_id=? AND lan_id=? and con_b<=?""",
                    (reg_id, un_id, ty_id, lan_id, ball))
            keyboard = []
            rows = cursor.fetchall()
            for mvdir, nomi in rows:
                keyboard.append([KeyboardButton(text=f"{mvdir} - {nomi}")])
            keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
            btn = ReplyKeyboardMarkup(
                keyboard=keyboard,
                resize_keyboard=True,
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            message_text = f"{len(list(dict.fromkeys(rows)))} ta yo'nalish mavjud:\n📚 Ta'lim yo'nalishini tanlang:"
            await message.answer(message_text, parse_mode="html", reply_markup=btn)
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
            cursor.execute("SELECT id, mvdir, nomi FROM mandat WHERE lower(nomi) LIKE ? and region_id=? and un_id=? and ty_id=? and lan_id=? and gr_b<=?", (f"%{text}%", reg_id, un_id, ty_id, lan_id, ball))
        else:
            cursor.execute("SELECT id, mvdir, nomi FROM mandat where region_id=? and un_id=? and ty_id=? and lan_id=? and gr_b<=?", (reg_id, un_id, ty_id, lan_id, ball))
    elif shakl == "kn":
        if text:
            cursor.execute(
                "SELECT id, mvdir, nomi FROM mandat WHERE lower(nomi) LIKE ? and region_id=? and un_id=? and ty_id=? and lan_id=? and con_b<=?",
                (f"%{text}%", reg_id, un_id, ty_id, lan_id, ball))
        else:
            cursor.execute(
                "SELECT id, mvdir, nomi FROM mandat where region_id=? and un_id=? and ty_id=? and lan_id=? and con_b<=?",
                (reg_id, un_id, ty_id, lan_id, ball))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    facs = list(dict.fromkeys(cursor.fetchall()))[:50]
    results = [
        InlineQueryResultArticle(
            id=str(id),  # Ensure ID is string
            title=f"{mvdir} - {nomi}",
            input_message_content=InputTextMessageContent(
                message_text=f'{mvdir} - {nomi}',
                parse_mode="HTML"
            ),
            reply_markup=kb
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
            rows = cursor.execute('''
                                    SELECT DISTINCT g.lan_id, g.lan_text
                                    FROM mandat m
                                    JOIN getlangs g ON m.lan_id = g.lan_id
                                    WHERE m.un_id = ? AND m.ty_id = ? AND m.region_id = ? AND m.gr_b <= ? AND m.gr_b != 0 AND m.ty_id = 1
                                ''', (un_id, ty_id, reg_id, ball)).fetchall()
        elif shakl == "kn":
            rows = cursor.execute('''
                                                        SELECT DISTINCT g.lan_id, g.lan_text
                                                        FROM mandat m
                                                        JOIN getlangs g ON m.lan_id = g.lan_id
                                                        WHERE m.un_id = ? AND m.ty_id = ? AND m.region_id = ? AND m.con_b <= ? AND m.con_b != 0
                                                    ''', (un_id, ty_id, reg_id, ball)).fetchall()
        keyboard = []
        for row1, row2 in rows:
            keyboard.append([KeyboardButton(text=row2[:60])])

        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

        btn = ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
        )
        await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                                      reply_markup=await UserPanels.main_manu())
    else:
        galyan = message.text.split(" - ")
        mvdir = galyan[0]
        nomi = galyan[1]
        data = await state.get_data()
        un_id = data["un_id"]
        ty_id = data["ty_id"]
        lan_id = data["lan_id"]
        reg_id = data.get("reg_id")
        shakl = data["shakl"]
        ball = data["ball"]
        if lan_id:
            if shakl == "gr":
                cursor.execute("""SELECT gr_b, con_b, olimp FROM mandat WHERE un_id=? AND ty_id=? AND lan_id=? AND mvdir=? AND nomi=? and region_id=? and gr_b<=?""",
                               (un_id, ty_id, lan_id, mvdir, nomi, reg_id, ball))
                ress = cursor.fetchall()
            elif shakl == "kn":
                cursor.execute(
                    """SELECT gr_b, con_b, olimp FROM mandat WHERE un_id=? AND ty_id=? AND lan_id=? AND mvdir=? AND nomi=? and region_id=? and con_b<=?""",
                    (un_id, ty_id, lan_id, mvdir, nomi, reg_id, ball))
                ress = cursor.fetchall()
            gr_b, con_b, olimp = ress[0]
            if con_b:
                un_name = (cursor.execute("""SELECT un_text FROM universities WHERE un_id=? """, (un_id,))).fetchone()
                lan_text = (cursor.execute("""SELECT lan_text FROM getlangs WHERE lan_id=? """, (lan_id,))).fetchone()
                ty_text = (cursor.execute("""SELECT ty_text FROM gettypes WHERE ty_id=? """, (ty_id,))).fetchone()

                message_text = (
                    f"<b>🏛 OLIYGOH:</b> {un_name[0]}\n\n<b>📚 TAʼLIM YO‘NALISHI</b> - {str(mvdir) + ' - ' + nomi}\n\n<b>🇺🇿 TAʼLIM TILI</b> - {lan_text[0]}\n\n"
                    f"<b>🔰 TAʼLIM SHAKLI</b> - {ty_text[0]}\n\n<b>📈 OʻTISH BALLARI:</b>\n<b>Grand</b> - {gr_b} ball | <b>Kontrakt</b> - {con_b} ball\n\n"
                    f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
                    f"<b>© <a href='https://t.me/mandatjavobbot?start=share'>@Mandatjavobbot</a> - oʻtish ballari va mandat natijalari</b>")
                # await message.answer(message_text, parse_mode="html")

                user_id = message.from_user.id
                old = cursor.execute(
                    """ SELECT file_id FROM photos WHERE un_id = ? AND ty_id = ? AND lan_id = ? AND mvdir = ? """,
                    (un_id, ty_id, lan_id, mvdir)).fetchone()
                if old:
                    await message.answer_photo(photo=old[0], caption=message_text, parse_mode="html")
                else:
                    if create_card(univer=un_name[0], faculty=str(mvdir) + ' - ' + nomi, lang=lan_text[0],
                                   edu=ty_text[0],
                                   grand=gr_b, kont=con_b, olmp=olimp, name=user_id):
                        sent_message = await message.answer_photo(
                            photo=FSInputFile(f"{os.path.dirname(os.path.abspath(__file__))}/photos/{user_id}.jpg"),
                            caption=message_text, parse_mode="html")
                        file_id = sent_message.photo[-1].file_id
                        cursor.execute("""
                                                INSERT OR IGNORE INTO photos (un_id, ty_id, lan_id, mvdir, file_id)
                                                VALUES (?, ?, ?, ?, ?)
                                            """, (un_id, ty_id, lan_id, mvdir, file_id))
                        conn.commit()
                        if os.path.exists(f"{os.path.dirname(os.path.abspath(__file__))}/photos/{user_id}.jpg"):
                            os.remove(f"{os.path.dirname(os.path.abspath(__file__))}/photos/{user_id}.jpg")
                    else:
                        await message.answer(message_text, parse_mode="html")
