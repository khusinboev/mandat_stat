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

reg_router = Router()

class FormReg(StatesGroup):
    reg1 = State()
    reg2 = State()
    reg3 = State()
    reg4 = State()
    reg5 = State()

@reg_router.message(F.text == "📈 Viloyatlar kesimida", F.chat.type == ChatType.PRIVATE)
async def enter_direction(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        cursor.execute("SELECT region_id, region_name FROM regions")
        rows = cursor.fetchall()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        keyboard = []
        for row in rows:
            region_name = row[1]
            keyboard.append([KeyboardButton(text=region_name)])

        # Ortga tugmasini eng pastga qo‘shamiz
        keyboard.append([KeyboardButton(text="🔙 Ortga")])

        btn = ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
        )
        await message.answer(f"<b>📍 Hududni tanlang:</b>",
                             parse_mode="html", reply_markup=btn)
        await message.answer("<b>Tezkor qidiruvdan foydalaning...👇</b>", parse_mode="html", reply_markup=kb)
        await state.set_state(FormReg.reg1)
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))


@reg_router.inline_query(FormReg.reg1)
async def inline_search_region(inline_query: InlineQuery):
    text = inline_query.query.lower()

    if text:
        cursor.execute("SELECT id, region_id, region_name FROM regions WHERE lower(region_name) LIKE %s", (f"%{text}%",))
    else:
        cursor.execute("SELECT id, region_id, region_name FROM regions")
    facs = cursor.fetchall()
    if facs:
        results = [
            InlineQueryResultArticle(
                id=str(id),
                title=region_name,
                input_message_content=InputTextMessageContent(
                    message_text=region_name,
                    parse_mode="HTML"
                )
            ) for id, region_id, region_name in facs
        ]
        await inline_query.answer(results, cache_time=1, is_personal=True)


@reg_router.message(FormReg.reg1)
async def chosen_university(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        region_name = message.text
        cursor.execute("SELECT region_id FROM regions WHERE region_name = %s", (region_name,))
        region_id = cursor.fetchone()[0]
        cursor.execute("SELECT u.un_text FROM regions r JOIN universities u ON r.region_id = u.region_id WHERE r.region_name = %s ORDER BY u.un_text", (region_name,))
        un_id = cursor.fetchall()
        if un_id:
            await state.update_data(region_name=region_name)
            await state.update_data(region_id=region_id)
            await state.update_data(un_number=len(un_id))
            await state.set_state(FormReg.reg2)

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            keyboard = [[KeyboardButton(text=row[0])] for row in un_id]
            keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
            btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
            await message.answer(f"<b>Siz tanlagan hududda {len(un_id)} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>", parse_mode="html", reply_markup=btn)
            await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)


@reg_router.inline_query(FormReg.reg2)
async def inline_search_university(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    region_name = data.get("region_name")

    if text:
        cursor.execute(
            "SELECT u.id, u.un_text FROM regions r JOIN universities u ON r.region_id = u.region_id WHERE r.region_name = %s AND lower(u.un_text) LIKE %s ORDER BY u.un_text",
            (region_name, f"%{text}%"))
    else:
        cursor.execute("SELECT u.id, u.un_text FROM regions r JOIN universities u ON r.region_id = u.region_id WHERE r.region_name = %s ORDER BY u.un_text", (region_name,))
    universities = cursor.fetchall()
    if universities:
        universities = list(dict.fromkeys(universities))[:50]
        results = [
            InlineQueryResultArticle(
                id=str(un_id),
                title=un_text,
                input_message_content=InputTextMessageContent(message_text=un_text)
            ) for un_id, un_text in universities
        ]
        await inline_query.answer(results, cache_time=1, is_personal=True)


@reg_router.message(FormReg.reg2)
async def chosen_university(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        try:
            cursor.execute("SELECT region_id, region_name FROM regions")
            rows = cursor.fetchall()
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            keyboard = [[KeyboardButton(text=row[1])] for row in rows]
            keyboard.append([KeyboardButton(text="🔙 Ortga")])
            btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
            await message.answer(f"<b>📍 Hududni tanlang:</b>", parse_mode="html", reply_markup=btn)
            await message.answer("<b>Tezkor qidiruvdan foydalaning...👇</b>", parse_mode="html", reply_markup=kb)
            await state.set_state(FormReg.reg1)
        except:
            await message.delete()
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html", reply_markup=await UserPanels.main_manu())
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html", reply_markup=await UserPanels.main_manu())
    else:
        un_name = message.text
        cursor.execute("SELECT un_id FROM universities WHERE lower(un_text)=%s", (un_name.lower(),))
        un_id = cursor.fetchone()
        if un_id:
            un_id = un_id[0]
            await state.update_data(un_id=un_id)
            await state.set_state(FormReg.reg3)
            data = await state.get_data()
            region_id = data.get("region_id")
            cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE region_id=%s AND un_id=%s", (region_id, un_id))
            rows = cursor.fetchall()
            if rows:
                keyboard = [[KeyboardButton(text=row[1])] for row in rows]
                keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
                btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
                await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)

@reg_router.message(FormReg.reg3)
async def chosen_type(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg2)
        data = await state.get_data()
        un_id = data.get("un_id")
        cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE un_id=%s", (un_id,))
        rows = cursor.fetchall()
        keyboard = []
        for row in rows:
            region_name = row[1]
            keyboard.append([KeyboardButton(text=region_name)])

        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

        btn = ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
        )
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        name = message.text.lower()
        cursor.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text)=%s", (name,))
        ty_id = cursor.fetchone()
        if ty_id:
            ty_id = ty_id[0]
            await state.update_data(ty_id=ty_id)
            await state.set_state(FormReg.reg4)
            data = await state.get_data()
            un_id = data.get("un_id")
            cursor.execute('''
                SELECT DISTINCT g.lan_id, g.lan_text
                FROM mandat m
                JOIN getlangs g ON m.lan_id = g.lan_id
                WHERE m.un_id = %s AND m.ty_id = %s
            ''', (un_id, ty_id))
            rows = cursor.fetchall()
            keyboard = []
            for row1, row2 in rows:
                keyboard.append([KeyboardButton(text=row2[:60])])

            keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

            btn = ReplyKeyboardMarkup(
                keyboard=keyboard,
                resize_keyboard=True,
            )
            await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)


@reg_router.message(FormReg.reg4)
async def chosen_lang(message: Message, state: FSMContext):
    lan_text = message.text.lower()
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg3)
        data = await state.get_data()
        ty_id = data.get("ty_id")
        un_id = data.get("un_id")
        cursor.execute('''
            SELECT DISTINCT g.lan_id, g.lan_text
            FROM mandat m
            JOIN getlangs g ON m.lan_id = g.lan_id
            WHERE m.un_id = %s AND m.ty_id = %s
        ''', (un_id, ty_id))
        rows = cursor.fetchall()
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
        cursor.execute("SELECT lan_id FROM getlangs WHERE lower(lan_text)=%s", (lan_text,))
        lan_id = cursor.fetchone()
        if lan_id:
            lan_id = lan_id[0]
            await state.update_data(lan_id=lan_id)
            data = await state.get_data()
            region_id = data["region_id"]
            un_id = data["un_id"]
            ty_id = data["ty_id"]
            lan_id = data["lan_id"]
            cursor.execute("""SELECT mvdir, nomi FROM mandat WHERE region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s""",
                           (region_id, un_id, ty_id, lan_id))
            rows = cursor.fetchall()
            keyboard = []
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
            message_text = f"{len(rows)} ta yo'nalish mavjud:\n📚 Ta'lim yo'nalishini tanlang:"
            await message.answer(message_text, parse_mode="html", reply_markup=btn)
            await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
            await state.set_state(FormReg.reg5)

@reg_router.inline_query(FormReg.reg5)
async def inline_search_region(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    region_id = data["region_id"]
    un_id = data["un_id"]
    ty_id = data["ty_id"]
    lan_id = data["lan_id"]
    if text:
        cursor.execute(
            "SELECT id, mvdir, nomi FROM mandat WHERE lower(nomi) LIKE %s AND region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s",
            (f"%{text}%", region_id, un_id, ty_id, lan_id))
    else:
        cursor.execute(
            "SELECT id, mvdir, nomi FROM mandat WHERE region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s",
            (region_id, un_id, ty_id, lan_id))
    facs = cursor.fetchall()
    facs = list(dict.fromkeys(facs))[:50]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    results = [
        InlineQueryResultArticle(
            id=str(id),
            title=f"{mvdir} - {nomi}",
            input_message_content=InputTextMessageContent(
                message_text=f"{mvdir} - {nomi}",
                parse_mode="HTML"
            ),
            reply_markup=kb
        ) for id, mvdir, nomi in facs
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@reg_router.message(FormReg.reg5)
async def chosen_lang(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg3)
        data = await state.get_data()
        ty_id = data.get("ty_id")
        un_id = data.get("un_id")
        cursor.execute("""
            SELECT DISTINCT g.lan_id, g.lan_text
            FROM mandat m
            JOIN getlangs g ON m.lan_id = g.lan_id
            WHERE m.un_id = %s AND m.ty_id = %s
        """, (un_id, ty_id))
        rows = cursor.fetchall()
        keyboard = [[KeyboardButton(text=row2[:60])] for row1, row2 in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        galyan = message.text.split(" - ")
        if len(galyan) == 2:
            mvdir = galyan[0]
            nomi = galyan[1]
            data = await state.get_data()
            un_id = data["un_id"]
            ty_id = data["ty_id"]
            lan_id = data["lan_id"]
            cursor.execute("SELECT un_text FROM universities WHERE un_id=%s", (un_id,))
            un_name = cursor.fetchone()
            cursor.execute("SELECT lan_text FROM getlangs WHERE lan_id=%s", (lan_id,))
            lan_text = cursor.fetchone()
            cursor.execute("SELECT ty_text FROM gettypes WHERE ty_id=%s", (ty_id,))
            ty_text = cursor.fetchone()
            cursor.execute("""
                SELECT gr_b, con_b, olimp FROM mandat
                WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s AND nomi=%s
            """, (un_id, ty_id, lan_id, mvdir, nomi))
            gr_b, con_b, olimp = cursor.fetchone()

            message_text = (
                f"<b>🏛 OLIYGOH:</b> {un_name[0]}\n\n<b>📚 TAʼLIM YO‘NALISHI</b> - {mvdir} - {nomi}\n\n<b>🇺🇿 TAʼLIM TILI</b> - {lan_text[0]}\n\n"
                f"<b>🔰 TAʼLIM SHAKLI</b> - {ty_text[0]}\n\n<b>📈 OʻTISH BALLARI:</b>\n<b>Grand</b> - {gr_b} ball | <b>Kontrakt</b> - {con_b} ball\n\n"
                f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
                f"<b>© <a href='https://t.me/mandatjavobbot%sstart=share'>@Mandatjavobbot</a> - oʻtish ballari va mandat natijalari</b>")

            user_id = message.from_user.id
            cursor.execute("""
                SELECT file_id FROM photos
                WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s
            """, (un_id, ty_id, lan_id, mvdir))
            old = cursor.fetchone()
            if old:
                await message.answer_photo(photo=old[0], caption=message_text, parse_mode="html")
            else:
                if create_card(univer=un_name[0], faculty=f"{mvdir} - {nomi}", lang=lan_text[0], edu=ty_text[0],
                               grand=gr_b, kont=con_b, olmp=olimp, name=user_id):
                    file_path = f"{os.path.dirname(os.path.abspath(__file__))}/photos/{user_id}.jpg"
                    sent_message = await message.answer_photo(photo=FSInputFile(file_path), caption=message_text, parse_mode="html")
                    file_id = sent_message.photo[-1].file_id
                    cursor.execute("""
                        INSERT INTO photos (un_id, ty_id, lan_id, mvdir, file_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (un_id, ty_id, lan_id, mvdir) DO NOTHING
                    """, (un_id, ty_id, lan_id, mvdir, file_id))
                    conn.commit()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                else:
                    await message.answer(message_text, parse_mode="html")
