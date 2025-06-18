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

fac_router = Router()

class FormFac(StatesGroup):
    fac1 = State()
    fac2 = State()
    fac3 = State()
    fac4 = State()
    fac5 = State()

@fac_router.message(F.text == "📚 Yoʻnalishlar boʻyicha", F.chat.type == ChatType.PRIVATE)
async def enter_direction(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        cursor.execute("SELECT region_id, un_id, ty_id, lan_id, mvdir, nomi FROM mandat")
        row = len(set(cursor.fetchall()))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        await message.answer(f"<b>{row} ta yo'nalish mavjud \n\n📚 Ta'lim yo'nalishini tanlang:</b>",
                             parse_mode="html", reply_markup=await UserPanels.to_back())
        await message.answer("<b>Tezkor qidiruvdan foydalaning...👇</b>", parse_mode="html", reply_markup=kb)
        await state.set_state(FormFac.fac1)
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))

@fac_router.callback_query(F.data == "to_back", FormFac.fac1)
async def handle_hello(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.clear()
    await callback.message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                         reply_markup=await UserPanels.main_manu())

# Region izlash
@fac_router.inline_query(FormFac.fac1)
async def inline_search_region(inline_query: InlineQuery):
    text = inline_query.query.lower()

    if text:
        cursor.execute("SELECT id, region_id, un_id, ty_id, lan_id, mvdir, nomi FROM mandat WHERE lower(nomi) LIKE ?", (f"%{text}%",))
    else:
        cursor.execute("SELECT id, region_id, un_id, ty_id, lan_id, mvdir, nomi FROM mandat")
    facs = cursor.fetchall()
    if facs:
        facs = list(dict.fromkeys(facs))[:50]
        results = [
            InlineQueryResultArticle(
                id=str(id),  # Ensure ID is string
                title=f"{mvdir} - {nomi}",
                input_message_content=InputTextMessageContent(
                    message_text=f'{mvdir} - {nomi}',
                    parse_mode="HTML"
                )
            ) for id, region_id, un_id, ty_id, lan_id, mvdir, nomi in facs
        ]
        await inline_query.answer(results, cache_time=1, is_personal=True)


@fac_router.message(FormFac.fac1)
async def chosen_university(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                                      reply_markup=await UserPanels.main_manu())
    else:
        mvdir = int(message.text.split(" - ")[0])
        cursor.execute('''
                    SELECT u.un_id, u.un_text
                    FROM mandat m
                    JOIN universities u ON m.un_id = u.un_id
                    WHERE m.mvdir = ?
                    GROUP BY u.un_id, u.un_text
                    ORDER BY u.un_text
                ''', (mvdir,))
        un_id = cursor.fetchall()
        if un_id:
            un_id = len(un_id)
            await state.update_data(mvdir=mvdir)
            await state.set_state(FormFac.fac2)

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            await message.answer(f"<b>Siz tanlagan yo'nalish {un_id} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>", parse_mode="html", reply_markup=await UserPanels.to_back())
            await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)

# Universitet izlash
@fac_router.inline_query(FormFac.fac2)
async def inline_search_university(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    mvdir = data.get("mvdir")

    # So‘rovni shartli tuzamiz
    if text:
        cursor.execute('''
            SELECT u.un_id, u.un_text
            FROM mandat m
            JOIN universities u ON m.un_id = u.un_id
            WHERE m.mvdir = ?
              AND lower(u.un_text) LIKE ?
            GROUP BY u.un_id, u.un_text
            ORDER BY u.un_text
        ''', (mvdir, f"%{text.lower()}%"))
    else:
        cursor.execute('''
            SELECT u.un_id, u.un_text
            FROM mandat m
            JOIN universities u ON m.un_id = u.un_id
            WHERE m.mvdir = ?
            GROUP BY u.un_id, u.un_text
            ORDER BY u.un_text
        ''', (mvdir,))
    universities = cursor.fetchall()
    if universities:
        universities = list(dict.fromkeys(universities))[:50]

        results = [
            InlineQueryResultArticle(
                id=un_id,
                title=un_text,
                input_message_content=InputTextMessageContent(message_text=un_text)
            ) for un_id, un_text in universities
        ]

        await inline_query.answer(results, cache_time=1, is_personal=True)

@fac_router.message(FormFac.fac2)
async def chosen_university(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        name = message.text.lower()
        cursor.execute("SELECT un_id FROM universities WHERE lower(un_text)=?", (name,))
        un_id = cursor.fetchall()[0][0]
        await state.update_data(un_id=un_id)
        await state.set_state(FormFac.fac3)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        rows = cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE un_id=?", (un_id, )).fetchall()
        if rows:
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
            await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
            await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)

@fac_router.callback_query(F.data == "to_back", FormFac.fac2)
async def handle_hello(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.delete()
    except: pass
    await state.clear()
    await callback.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                         reply_markup=await UserPanels.main_manu())

# Ta'lim turi
@fac_router.inline_query(FormFac.fac3)
async def inline_search_type(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    mvdir = data.get("mvdir")
    un_id = data.get("un_id")
    if text:
        cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE lower(ty_text) LIKE ? AND un_id=?", (f"%{text}%", un_id))
    else:
        cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE un_id=?", (un_id, ))
    types = cursor.fetchall()
    if types:
        types = list(dict.fromkeys(types))[:50]
        results = [
            InlineQueryResultArticle(
                id=ty_id,
                title=ty_text,
                input_message_content=InputTextMessageContent(message_text=ty_text)
            ) for ty_id, ty_text in types
        ]
        await inline_query.answer(results, cache_time=1, is_personal=True)

@fac_router.message(FormFac.fac3)
async def chosen_type(message: Message, state: FSMContext):
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormFac.fac2)
        data = await state.get_data()
        mvdir = data.get("mvdir")
        cursor.execute('''
                                    SELECT u.un_id, u.un_text
                                    FROM mandat m
                                    JOIN universities u ON m.un_id = u.un_id
                                    WHERE m.mvdir = ?
                                    GROUP BY u.un_id, u.un_text
                                    ORDER BY u.un_text
                                ''', (mvdir,))
        un_id = len(cursor.fetchall())
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        await message.answer(f"<b>Siz tanlagan yo'nalish {un_id} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>",
                             parse_mode="html", reply_markup=await UserPanels.to_back())
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
    else:
        name = message.text.lower()
        cursor.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text)=?", (name,))
        ty_id = cursor.fetchall()
        if ty_id:
            ty_id = ty_id[0][0]
            await state.update_data(ty_id=ty_id)
            await state.set_state(FormFac.fac4)
            data = await state.get_data()
            un_id = data.get("un_id")
            rows = cursor.execute('''
                SELECT DISTINCT g.lan_id, g.lan_text
                FROM mandat m
                JOIN getlangs g ON m.lan_id = g.lan_id
                WHERE m.un_id = ? AND m.ty_id = ?
            ''', (un_id, ty_id)).fetchall()
            if rows:
                keyboard = []
                for row1, row2 in rows:
                    keyboard.append([KeyboardButton(text=row2[:60])])

                # Ortga tugmasini eng pastga qo‘shamiz
                keyboard.append([KeyboardButton(text="🔙 Ortga")])

                btn = ReplyKeyboardMarkup(
                    keyboard=keyboard,
                    resize_keyboard=True,
                )
                await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)


@fac_router.message(FormFac.fac4)
async def chosen_lang(message: Message, state: FSMContext):
    lan_text = message.text.lower()
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormFac.fac3)
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
        keyboard.append([KeyboardButton(text="🔙 Ortga")])

        btn = ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
        )
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
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

            un_name = (cursor.execute("""SELECT un_text FROM universities WHERE un_id=? """, (un_id,))).fetchone()
            lan_text = (cursor.execute("""SELECT lan_text FROM getlangs WHERE lan_id=? """, (lan_id,))).fetchone()
            ty_text = (cursor.execute("""SELECT ty_text FROM gettypes WHERE ty_id=? """, (ty_id,))).fetchone()
            cursor.execute("""
                                            SELECT mvdir, nomi, gr_b, con_b, olimp
                                            FROM mandat
                                            WHERE un_id=? AND ty_id=? AND lan_id=?
                                        """, (un_id, ty_id, lan_id))
            mvdir, nomi, gr_b, con_b, olimp = cursor.fetchone()

            message_text = (f"<b>🏛 OLIYGOH:</b> {un_name[0]}\n\n<b>📚 TAʼLIM YO‘NALISHI</b> - {str(mvdir) + ' - ' + nomi}\n\n<b>🇺🇿 TAʼLIM TILI</b> - {lan_text[0]}\n\n"
                           f"<b>🔰 TAʼLIM SHAKLI</b> - {ty_text[0]}\n\n<b>📈 OʻTISH BALLARI:</b>\n<b>Grand</b> - {gr_b} ball | <b>Kontrakt</b> - {con_b} ball\n\n"
                           f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
                           f"<b>© <a href='https://t.me/xabardor_bol_bot?start=share'>@xabardor_bol_bot</a> - oʻtish ballari va mandat natijalari</b>")
            await message.answer(message_text, parse_mode="html")


