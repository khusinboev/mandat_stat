from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, \
    InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult, KeyboardButton, ReplyKeyboardMarkup

from config import sql, bot, ADMIN_ID, cursor, conn
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
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

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
        cursor.execute("SELECT id, region_id, region_name FROM regions WHERE lower(nomi) LIKE ?", (f"%{text}%",))
    else:
        cursor.execute("SELECT id, region_id, region_name FROM regions")
    facs = cursor.fetchall()
    if facs:
        results = [
            InlineQueryResultArticle(
                id=str(id),  # Ensure ID is string
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
        region_id = (cursor.execute("SELECT region_id FROM regions where region_name = ?", (region_name, ))).fetchone()[0]
        cursor.execute("SELECT u.un_text FROM regions r JOIN universities u ON r.region_id = u.region_id WHERE r.region_name = ? ORDER BY u.un_text", (region_name,))
        un_id = cursor.fetchall()
        if un_id:
            await state.update_data(region_name=region_name)
            await state.update_data(region_id=region_id)
            await state.update_data(un_number=len(un_id))
            await state.set_state(FormReg.reg2)

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            keyboard = []
            for row in un_id:
                keyboard.append([KeyboardButton(text=row[0])])

            # Ortga tugmasini eng pastga qo‘shamiz
            keyboard.append([KeyboardButton(text="🔙 Ortga")])
            keyboard.append([KeyboardButton(text="🔙 Bosh menu")])

            btn = ReplyKeyboardMarkup(
                keyboard=keyboard,
                resize_keyboard=True,
            )
            await message.answer(f"<b>Siz tanlagan hududda {len(un_id)} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>", parse_mode="html", reply_markup=btn)
            await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)


@reg_router.inline_query(FormReg.reg2)
async def inline_search_university(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    region_name = data.get("region_name")
    region_id = data.get("region_id")

    # So‘rovni shartli tuzamiz
    if text:
        cursor.execute(
            "SELECT u.id, u.un_text FROM regions r JOIN universities u ON r.region_id = u.region_id WHERE r.region_name = ? and lower(u.un_text) LIKE ? ORDER BY u.un_text",
            (region_name, f"%{text.lower()}%"))
    else:
        cursor.execute("SELECT u.id, u.un_text FROM regions r JOIN universities u ON r.region_id = u.region_id WHERE r.region_name = ? ORDER BY u.un_text", (region_name, ))
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
        data = await state.get_data()
        region_name = data.get("region_name")
        cursor.execute(
            "SELECT u.un_text FROM regions r JOIN universities u ON r.region_id = u.region_id WHERE r.region_name = ? ORDER BY u.un_text",
            (region_name,))
        un_id = cursor.fetchall()
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            keyboard = []
            for row in un_id:
                keyboard.append([KeyboardButton(text=row[0])])

            # Ortga tugmasini eng pastga qo‘shamiz
            keyboard.append([KeyboardButton(text="🔙 Ortga")])
            keyboard.append([KeyboardButton(text="🔙 Bosh menu")])

            btn = ReplyKeyboardMarkup(
                keyboard=keyboard,
                resize_keyboard=True,
            )
            await message.answer(f"<b>Siz tanlagan hududda {len(un_id)} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>",
                                 parse_mode="html", reply_markup=btn)
            await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
        except:
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
        un_name = message.text
        cursor.execute("SELECT un_id FROM universities WHERE lower(un_text)=?", (un_name.lower(),))
        un_id = cursor.fetchall()[0][0]
        await state.update_data(un_id=un_id)
        await state.set_state(FormReg.reg3)
        data = await state.get_data()
        region_id = data.get("region_id")
        rows = cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE region_id=? and un_id=?", (region_id, un_id, )).fetchall()
        if rows:
            keyboard = []
            for row in rows:
                keyboard.append([KeyboardButton(text=row[1])])

            keyboard.append([KeyboardButton(text="🔙 Ortga")])
            keyboard.append([KeyboardButton(text="🔙 Bosh menu")])

            btn = ReplyKeyboardMarkup(
                keyboard=keyboard,
                resize_keyboard=True,
            )
            await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)


@reg_router.message(FormReg.reg3)
async def chosen_type(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg2)
        data = await state.get_data()
        un_id = data.get("un_id")
        rows = cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE un_id=?", (un_id,))
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
        cursor.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text)=?", (name,))
        ty_id = cursor.fetchall()
        if ty_id:
            ty_id = ty_id[0][0]
            await state.update_data(ty_id=ty_id)
            await state.set_state(FormReg.reg4)
            data = await state.get_data()
            un_id = data.get("un_id")
            rows = cursor.execute('''
                SELECT DISTINCT g.lan_id, g.lan_text
                FROM mandat m
                JOIN getlangs g ON m.lan_id = g.lan_id
                WHERE m.un_id = ? AND m.ty_id = ?
            ''', (un_id, ty_id)).fetchall()
            keyboard = []
            for row1, row2 in rows:
                keyboard.append([KeyboardButton(text=row2[:60])])

            keyboard.append([KeyboardButton(text="🔙 Ortga")])
            keyboard.append([KeyboardButton(text="🔙 Bosh menu")])

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
        un_id = data.get("un_id")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        rows = cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE un_id=?", (un_id,))
        keyboard = []
        for row in rows:
            region_name = row[1]
            keyboard.append([KeyboardButton(text=region_name)])

        # Ortga tugmasini eng pastga qo‘shamiz
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

        btn = ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
        )
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
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
            region_id = data["region_id"]
            un_id = data["un_id"]
            ty_id = data["ty_id"]
            lan_id = data["lan_id"]
            cursor.execute("""SELECT mvdir, nomi FROM mandat WHERE region_id=? and un_id=? AND ty_id=? AND lan_id=?""",
                           (region_id, un_id, ty_id, lan_id))
            keyboard = []
            rows = cursor.fetchall()
            for mvdir, nomi in rows:
                keyboard.append([KeyboardButton(text=f"{mvdir} - {nomi}")])

            keyboard.append([KeyboardButton(text="🔙 Ortga")])
            keyboard.append([KeyboardButton(text="🔙 Bosh menu")])
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
        cursor.execute("SELECT id, mvdir, nomi FROM mandat WHERE lower(nomi) LIKE ? and region_id=? and un_id=? and ty_id=? and lan_id=?", (f"%{text}%", region_id, un_id, ty_id, lan_id))
    else:
        cursor.execute("SELECT id, mvdir, nomi FROM mandat where region_id=? and un_id=? and ty_id=? and lan_id=?", (region_id, un_id, ty_id, lan_id))
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


@reg_router.message(FormReg.reg5)
async def chosen_lang(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg4)
        data = await state.get_data()
        un_id = data.get("un_id")
        ty_id = data["ty_id"]
        rows = cursor.execute('''
                        SELECT DISTINCT g.lan_id, g.lan_text
                        FROM mandat m
                        JOIN getlangs g ON m.lan_id = g.lan_id
                        WHERE m.un_id = ? AND m.ty_id = ?
                    ''', (un_id, ty_id)).fetchall()
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
        if lan_id:
            un_name = (cursor.execute("""SELECT un_text FROM universities WHERE un_id=? """, (un_id,))).fetchone()
            lan_text = (cursor.execute("""SELECT lan_text FROM getlangs WHERE lan_id=? """, (lan_id,))).fetchone()
            ty_text = (cursor.execute("""SELECT ty_text FROM gettypes WHERE ty_id=? """, (ty_id,))).fetchone()
            cursor.execute("""SELECT gr_b, con_b, olimp FROM mandat WHERE un_id=? AND ty_id=? AND lan_id=? AND mvdir=? AND nomi=? """,
                           (un_id, ty_id, lan_id, mvdir, nomi))
            gr_b, con_b, olimp = cursor.fetchone()

            message_text = (
                f"<b>🏛 OLIYGOH:</b> {un_name[0]}\n\n<b>📚 TAʼLIM YO‘NALISHI</b> - {str(mvdir) + ' - ' + nomi}\n\n<b>🇺🇿 TAʼLIM TILI</b> - {lan_text[0]}\n\n"
                f"<b>🔰 TAʼLIM SHAKLI</b> - {ty_text[0]}\n\n<b>📈 OʻTISH BALLARI:</b>\n<b>Grand</b> - {gr_b} ball | <b>Kontrakt</b> - {con_b} ball\n\n"
                f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
                f"<b>© <a href='https://t.me/mandatjavobbot?start=share'>@mandatjavobbot</a> - oʻtish ballari va mandat natijalari</b>")
            await message.answer(message_text, parse_mode="html")
