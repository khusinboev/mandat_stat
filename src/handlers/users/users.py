from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, \
    InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult

from config import sql, bot, ADMIN_ID, cursor, conn
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

user_router = Router()

class FormFac(StatesGroup):
    fac1 = State()
    fac2 = State()
    fac3 = State()
    fac4 = State()
    fac5 = State()

@user_router.message(CommandStart())
async def start_cmd(msg: Message):
    await msg.answer("Quyidagi menulardan birini tanlang!", parse_mode="html", reply_markup=await UserPanels.main_manu())

@user_router.callback_query(F.data == "check", F.message.chat.type == ChatType.PRIVATE)
async def check(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        check_status, channels = await CheckData.check_member(bot, user_id)
        if check_status:
            await call.message.delete()
            await bot.send_message(chat_id=user_id,
                                   text="Quyidagi menulardan birini tanlang!",
                                   parse_mode="html", reply_markup=await UserPanels.to_back())
            try:
                await call.answer()
            except:
                pass
        else:
            try:
                await call.answer(show_alert=True, text="Botimizdan foydalanish uchun barcha kanallarga a'zo bo'ling")
            except:
                try:
                    await call.answer()
                except:
                    pass
    except Exception as e:
        await bot.forward_message(chat_id=ADMIN_ID[0], from_chat_id=call.message.chat.id, message_id=call.message.message_id)
        await bot.send_message(chat_id=ADMIN_ID[0], text=f"Error in check:\n{e}")

@user_router.message(F.text == "📚 Yoʻnalishlar boʻyicha", F.chat.type == ChatType.PRIVATE)
async def enter_direction(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")],
                [InlineKeyboardButton(text="🔙 Ortga", callback_data="to_back")]
            ])
            await message.answer("<b>Viloyat yoki respublikani tanlang 👇</b>", parse_mode="html", reply_markup=kb)
            await state.set_state(FormFac.fac1)
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))

@user_router.callback_query(F.data == "to_back", FormFac.fac1)
async def handle_hello(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.clear()
    await callback.message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                         reply_markup=await UserPanels.main_manu())

# Region izlash
@user_router.inline_query(FormFac.fac1)
async def inline_search_region(inline_query: InlineQuery):
    text = inline_query.query.lower()

    if text:
        cursor.execute("SELECT region_id, region_name FROM regions WHERE lower(region_name) LIKE ?", (f"%{text}%",))
    else:
        cursor.execute("SELECT region_id, region_name FROM regions")

    regions = cursor.fetchall()

    results = [
        InlineQueryResultArticle(
            id=str(region_id),  # Ensure ID is string
            title=region_name,
            input_message_content=InputTextMessageContent(
                message_text=f"Tanlangan region: {region_name}",
                parse_mode="HTML"
            ),
            description=f"Region ID: {region_id}"  # Optional description
        ) for region_id, region_name in regions
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@user_router.message(FormFac.fac1)
async def chosen_university(message: Message, state: FSMContext):
        name = message.text.lower()[18:]
        cursor.execute("SELECT region_id FROM regions WHERE lower(region_name)=?", (name, ))
        reg_id = cursor.fetchall()[0][0]
        await state.update_data(reg_id=reg_id)
        await state.set_state(FormFac.fac2)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")],
                [InlineKeyboardButton(text="🔙 Ortga", callback_data="to_back")]
        ])
        await message.answer("<b>Oliy o'quv yurtini tanlang 👇</b>", parse_mode="html", reply_markup=kb)

# Universitet izlash
@user_router.inline_query(FormFac.fac2)
async def inline_search_university(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    reg_id = data.get("reg_id")

    if text:
        cursor.execute("SELECT un_id, un_text FROM universities WHERE lower(un_text) LIKE ? AND region_id=?", (f"%{text}%", reg_id))
    else:
        cursor.execute("SELECT un_id, un_text FROM universities WHERE region_id=?", (reg_id,))

    universities = cursor.fetchall()

    results = [
        InlineQueryResultArticle(
            id=un_id,
            title=un_text,
            input_message_content=InputTextMessageContent(message_text=f"Tanlangan oliygoh: {un_text}")
        ) for un_id, un_text in universities
    ]

    await inline_query.answer(results, cache_time=1, is_personal=True)

@user_router.message(FormFac.fac2)
async def chosen_university(message: Message, state: FSMContext):
        name = message.text.lower()[19:]
        cursor.execute("SELECT un_id FROM universities WHERE lower(un_text)=?", (name,))
        un_id = cursor.fetchall()[0][0]
        await state.update_data(un_id=un_id)
        await state.set_state(FormFac.fac3)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")],
                [InlineKeyboardButton(text="🔙 Ortga", callback_data="to_back")]
        ])
        await message.answer("<b>Ta'lim shaklini tanlang 👇</b>", parse_mode="html", reply_markup=kb)

@user_router.callback_query(F.data == "to_back", FormFac.fac2)
async def handle_hello(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.set_state(FormFac.fac1)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")],
                [InlineKeyboardButton(text="🔙 Ortga", callback_data="to_back")]
    ])
    await callback.message.answer("<b>Oliy o'quv yurtini tanlang 👇</b>", parse_mode="html", reply_markup=kb)

# Ta'lim turi
@user_router.inline_query(FormFac.fac3)
async def inline_search_type(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    reg_id = data.get("reg_id")
    un_id = data.get("un_id")
    if text:
        cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE lower(ty_text) LIKE ? AND region_id=? AND un_id=?", (f"%{text}%", reg_id, un_id))
    else:
        cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE region_id=? and un_id=?", (reg_id, un_id))

    types = set(cursor.fetchall())
    results = [
        InlineQueryResultArticle(
            id=ty_id,
            title=ty_text,
            input_message_content=InputTextMessageContent(message_text=f"Tanlangan ta'lim shakli: {ty_text}")
        ) for ty_id, ty_text in types
    ]

    await inline_query.answer(results, cache_time=1, is_personal=True)

@user_router.message(FormFac.fac3)
async def chosen_type(message: Message, state: FSMContext):
    name = message.text.lower()[25:]
    cursor.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text)=?", (name,))
    ty_id = cursor.fetchall()[0][0]
    await state.update_data(ty_id=ty_id)
    await state.set_state(FormFac.fac4)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")],
        [InlineKeyboardButton(text="🔙 Ortga", callback_data="to_back")]
    ])
    await message.answer("<b>Ta'lim tilini tanlang tanlang 👇</b>", parse_mode="html", reply_markup=kb)

@user_router.callback_query(F.data == "to_back", FormFac.fac3)
async def handle_hello(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.set_state(FormFac.fac2)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")],
                [InlineKeyboardButton(text="🔙 Ortga", callback_data="to_back")]
    ])
    await callback.message.answer("<b>Ta'lim shaklini tanlang 👇</b>", parse_mode="html", reply_markup=kb)

# Tilni tanlash
@user_router.inline_query(FormFac.fac4)
async def inline_search_lang(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    reg_id = data.get("reg_id")
    un_id = data.get("un_id")
    ty_id = data.get("ty_id")

    if text:
        cursor.execute("SELECT lan_id, lan_text FROM getlangs WHERE lower(lan_text) LIKE ? AND region_id=? and un_id=? and ty_id=?", (f"%{text}%", reg_id, un_id, ty_id))
    else:
        cursor.execute("SELECT lan_id, lan_text FROM getlangs WHERE region_id=? and un_id=? and ty_id=?", (reg_id, un_id, ty_id))

    langs = set(cursor.fetchall())

    results = [
        InlineQueryResultArticle(
            id=lan_id,
            title=lan_text,
            input_message_content=InputTextMessageContent(message_text=f"Tanlangan til: {lan_text}")
        ) for lan_id, lan_text in langs
    ]

    await inline_query.answer(results, cache_time=1, is_personal=True)

@user_router.message(FormFac.fac4)
async def chosen_lang(message: Message, state: FSMContext):
    name = message.text.lower()[15:]
    cursor.execute("SELECT lan_id FROM getlangs WHERE lower(lan_text)=?", (name,))
    lan_id = cursor.fetchall()[0][0]
    await state.update_data(lan_id=lan_id)
    await state.set_state(FormFac.fac4)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")],
        [InlineKeyboardButton(text="🔙 Ortga", callback_data="to_back")]
    ])
    data = await state.get_data()
    reg_id = data["reg_id"]
    un_id = data["un_id"]
    ty_id = data["ty_id"]
    lan_id = data["lan_id"]

    cursor.execute("""
                SELECT nomi
                FROM mandat
                WHERE region_id=? AND un_id=? AND ty_id=? AND lan_id=?
            """, (reg_id, un_id, ty_id, lan_id))

    result = cursor.fetchall()
    await message.answer(f"<b>{len(result)} ta yo'nalish mavjud:</b> \n📚 Ta'lim yo'nalishini tanlang:", parse_mode="html")
    await message.answer("<b>Tezkor qidiruvdan foydalaning... 👇</b>", parse_mode="html", reply_markup=kb)
    await state.set_state(FormFac.fac5)


@user_router.inline_query(FormFac.fac5)
async def inline_search_lang(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    reg_id = data["reg_id"]
    un_id = data["un_id"]
    ty_id = data["ty_id"]
    lan_id = data["lan_id"]
    if text:
        cursor.execute("""
                        SELECT mvdir, nomi, gr_b, con_b
                        FROM mandat
                        WHERE region_id=? AND un_id=? AND ty_id=? AND lan_id=? AND lower(nomi) LIKE ?
                    """, (reg_id, un_id, ty_id, lan_id, f"%{text}%"))
    else:
        cursor.execute("""
                                SELECT mvdir, nomi, gr_b, con_b, olimp
                                FROM mandat
                                WHERE region_id=? AND un_id=? AND ty_id=? AND lan_id=?
                            """, (reg_id, un_id, ty_id, lan_id))
    langs = cursor.fetchall()
    un_name = (cursor.execute("""SELECT un_text FROM universities WHERE un_id=? """, (un_id, ))).fetchone()
    lan_text = (cursor.execute("""SELECT lan_text FROM getlangs WHERE lan_id=? """, (lan_id, ))).fetchone()
    ty_text = (cursor.execute("""SELECT ty_text FROM gettypes WHERE ty_id=? """, (ty_id, ))).fetchone()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")],
        [InlineKeyboardButton(text="🔙 Ortga", callback_data="to_back")]
    ])
    results = [
        InlineQueryResultArticle(
            id=str(mvdir),
            title=str(mvdir)+" - "+nomi,
            input_message_content=
            InputTextMessageContent(
                message_text=f"<b>🏛 OLIYGOH:</b> {un_name[0]}\n\n<b>📚 TAʼLIM YO‘NALISHI</b> - {str(mvdir)+' - '+nomi}\n\n<b>🇺🇿 TAʼLIM TILI</b> - {lan_text[0]}\n\n"
                             f"<b>🔰 TAʼLIM SHAKLI</b> - {ty_text[0]}\n\n<b>📈 OʻTISH BALLARI:</b>\n<b>Grand</b> - {gr_b} ball | <b>Kontrakt</b> - {con_b} ball\n\n"
                             f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
                             f"<b>© <a href='https://t.me/xabardor_bol_bot?start=share'>@xabardor_bol_bot</a> - oʻtish ballari va mandat natijalari</b>",
                parse_mode="html"),
            reply_markup=kb
        ) for mvdir, nomi, gr_b, con_b, olimp in langs
    ]

    await inline_query.answer(results, cache_time=1, is_personal=True)


@user_router.callback_query(F.data == "to_back", FormFac.fac5)
async def handle_hello(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FormFac.fac4)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")],
                [InlineKeyboardButton(text="🔙 Ortga", callback_data="to_back")]
    ])
    await callback.message.answer("<b>Tanlang 👇</b>", parse_mode="html", reply_markup=kb)



@user_router.callback_query(F.data == "to_back", FormFac.fac4)
async def handle_hello(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.set_state(FormFac.fac3)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")],
                [InlineKeyboardButton(text="🔙 Ortga", callback_data="to_back")]
    ])
    await callback.message.answer("<b>Ta'lim tilini tanlang tanlang 👇</b>", parse_mode="html", reply_markup=kb)


# Shu yerda keyingi bosqichni (fac5 va hokazo) davom ettirishingiz mumkin.
@user_router.callback_query()
async def handle_hello(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception as e:
        try:
            await bot.delete_message(chat_id=callback.from_user.id, message_id=callback.inline_message_id )
        except:
            pass
