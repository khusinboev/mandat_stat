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


@fac_router.inline_query(FormFac.fac1)
async def inline_search_region(inline_query: InlineQuery):
    text = inline_query.query.lower()
    if text:
        cursor.execute("SELECT mvdir, nomi FROM mandat WHERE lower(nomi) LIKE %s", (f"%{text}%",))
    else:
        cursor.execute("SELECT mvdir, nomi FROM mandat")
    facs = cursor.fetchall()
    facs = list(dict.fromkeys(facs))[:50]
    results = [
        InlineQueryResultArticle(
            id=str(mvdir),
            title=f"{mvdir} - {nomi}",
            input_message_content=InputTextMessageContent(
                message_text=f'{mvdir} - {nomi}',
                parse_mode="HTML"
            )
        ) for mvdir, nomi in facs
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@fac_router.message(FormFac.fac1)
async def chosen_university(message: Message, state: FSMContext):
    if message.text in ["🔙 Ortga", "🔙 Bosh menu"]:
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        mvdir, fac_name = message.text.split(" - ", 1)
        mvdir = int(mvdir)
        cursor.execute("""
            SELECT u.un_id, u.un_text
            FROM mandat m
            JOIN universities u ON m.un_id = u.un_id
            WHERE m.mvdir = %s AND m.nomi = %s
            GROUP BY u.un_id, u.un_text
            ORDER BY u.un_text
        """, (mvdir, fac_name))
        universities = cursor.fetchall()
        if universities:
            await state.update_data(mvdir=mvdir, fac_name=fac_name)
            await state.set_state(FormFac.fac2)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
            ])
            await message.answer(f"<b>Siz tanlagan yo'nalish {len(universities)} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>", parse_mode="html", reply_markup=await UserPanels.to_back())
            await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)


@fac_router.inline_query(FormFac.fac2)
async def inline_search_university(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    mvdir = data.get("mvdir")
    fac_name = data.get("fac_name")

    query = """
        SELECT u.un_id, u.un_text
        FROM mandat m
        JOIN universities u ON m.un_id = u.un_id
        WHERE m.mvdir = %s AND m.nomi = %s {filter}
        GROUP BY u.un_id, u.un_text
        ORDER BY u.un_text
    """
    if text:
        cursor.execute(query.format(filter="AND lower(u.un_text) LIKE %s"), (mvdir, fac_name, f"%{text}%"))
    else:
        cursor.execute(query.format(filter=""), (mvdir, fac_name))
    universities = list(dict.fromkeys(cursor.fetchall()))[:50]
    results = [
        InlineQueryResultArticle(
            id=str(un_id),
            title=un_text,
            input_message_content=InputTextMessageContent(message_text=un_text)
        ) for un_id, un_text in universities
    ]
    await inline_query.answer(results, cache_time=1, is_personal=True)


@fac_router.message(FormFac.fac2)
async def chosen_university(message: Message, state: FSMContext):
    if message.text in ["🔙 Ortga", "🔙 Bosh menu"]:
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        name = message.text.lower()
        cursor.execute("SELECT un_id FROM universities WHERE lower(un_text)=%s", (name,))
        un_id = cursor.fetchone()[0]
        await state.update_data(un_id=un_id)
        await state.set_state(FormFac.fac3)
        cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE un_id=%s", (un_id,))
        rows = cursor.fetchall()
        keyboard = [[KeyboardButton(text=row[1])] for row in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)


# Ta'lim turi
@fac_router.inline_query(FormFac.fac3)
async def inline_search_type(inline_query: InlineQuery, state: FSMContext):
    text = inline_query.query.lower()
    data = await state.get_data()
    un_id = data.get("un_id")
    if text:
        cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE lower(ty_text) LIKE %s AND un_id=%s", (f"%{text}%", un_id))
    else:
        cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE un_id=%s", (un_id,))
    types = cursor.fetchall()
    if types:
        types = list(dict.fromkeys(types))[:50]
        results = [
            InlineQueryResultArticle(
                id=str(ty_id),
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
        fac_name = data.get("fac_name")
        cursor.execute("""
            SELECT u.un_id, u.un_text
            FROM mandat m
            JOIN universities u ON m.un_id = u.un_id
            WHERE m.mvdir = %s AND m.nomi = %s
            GROUP BY u.un_id, u.un_text
            ORDER BY u.un_text
        """, (mvdir, fac_name))
        un_id = len(cursor.fetchall())
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        await message.answer(f"<b>Siz tanlagan yo'nalish {un_id} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>", parse_mode="html", reply_markup=await UserPanels.to_back())
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html", reply_markup=await UserPanels.main_manu())
    else:
        name = message.text.lower()
        cursor.execute("SELECT ty_id FROM gettypes WHERE lower(ty_text)=%s", (name,))
        ty_id = cursor.fetchone()
        if ty_id:
            ty_id = ty_id[0]
            await state.update_data(ty_id=ty_id)
            await state.set_state(FormFac.fac4)
            data = await state.get_data()
            un_id = data["un_id"]
            cursor.execute("""
                SELECT DISTINCT g.lan_id, g.lan_text
                FROM mandat m
                JOIN getlangs g ON m.lan_id = g.lan_id
                WHERE m.un_id = %s AND m.ty_id = %s
            """, (un_id, ty_id))
            rows = cursor.fetchall()
            if rows:
                keyboard = [[KeyboardButton(text=row2[:60])] for row1, row2 in rows]
                keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
                btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
                await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)


@fac_router.message(FormFac.fac4)
async def chosen_lang(message: Message, state: FSMContext):
    lan_text = message.text.lower()
    if message.text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormFac.fac3)
        data = await state.get_data()
        un_id = data["un_id"]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE un_id=%s", (un_id,))
        rows = cursor.fetchall()
        keyboard = [[KeyboardButton(text=row[1])] for row in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
    elif message.text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html", reply_markup=await UserPanels.main_manu())
    else:
        cursor.execute("SELECT lan_id FROM getlangs WHERE lower(lan_text)=%s", (lan_text,))
        lan_id = cursor.fetchone()
        if lan_id:
            lan_id = lan_id[0]
            await state.update_data(lan_id=lan_id)
            data = await state.get_data()
            un_id = str(data["un_id"])
            ty_id = str(data["ty_id"])
            mvdir = str(data["mvdir"])
            fac_name = str(data["fac_name"])

            cursor.execute("SELECT un_text FROM universities WHERE un_id=%s", (un_id,))
            un_name = cursor.fetchone()

            cursor.execute("SELECT lan_text FROM getlangs WHERE lan_id=%s", (lan_id,))
            lan_text_row = cursor.fetchone()

            cursor.execute("SELECT ty_text FROM gettypes WHERE ty_id=%s", (ty_id,))
            ty_text_row = cursor.fetchone()

            cursor.execute("""
                SELECT mvdir, nomi, gr_b, con_b, olimp
                FROM mandat
                WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s AND nomi=%s
            """, (un_id, ty_id, lan_id, mvdir, fac_name))
            mvdir, nomi, gr_b, con_b, olimp = cursor.fetchone()

            message_text = (
                f"<b>🏛 OLIYGOH:</b> {un_name[0]}\n\n<b>📚 TAʼLIM YO‘NALISHI</b> - {mvdir} - {nomi}\n\n<b>🇺🇿 TAʼLIM TILI</b> - {lan_text_row[0]}\n\n"
                f"<b>🔰 TAʼLIM SHAKLI</b> - {ty_text_row[0]}\n\n<b>📈 OʻTISH BALLARI:</b>\n<b>Grand</b> - {gr_b} ball | <b>Kontrakt</b> - {con_b} ball\n\n"
                f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
                f"<b>© <a href='https://t.me/mandatjavobbot%sstart=share'>@Mandatjavobbot</a> - oʻtish ballari va mandat natijalari</b>"
            )

            user_id = message.from_user.id
            cursor.execute(
                """SELECT file_id FROM photos WHERE un_id = %s AND ty_id = %s AND lan_id = %s AND mvdir = %s""",
                (un_id, ty_id, lan_id, mvdir)
            )
            old = cursor.fetchone()
            if old:
                await message.answer_photo(photo=old[0], caption=message_text, parse_mode="html")
            else:
                if create_card(
                    univer=un_name[0], faculty=f"{mvdir} - {nomi}", lang=lan_text_row[0], edu=ty_text_row[0],
                    grand=gr_b, kont=con_b, olmp=olimp, name=user_id
                ):
                    photo_path = f"{os.path.dirname(os.path.abspath(__file__))}/photos/{user_id}.jpg"
                    sent_message = await message.answer_photo(
                        photo=FSInputFile(photo_path),
                        caption=message_text, parse_mode="html"
                    )
                    file_id = sent_message.photo[-1].file_id
                    cursor.execute("""
                        INSERT INTO photos (un_id, ty_id, lan_id, mvdir, file_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (un_id, ty_id, lan_id, mvdir, file_id))
                    conn.commit()
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                else:
                    await message.answer(message_text, parse_mode="html")
