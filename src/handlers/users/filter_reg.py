import logging
import os
import unicodedata

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, \
    InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult, KeyboardButton, ReplyKeyboardMarkup, \
    FSInputFile

from config import sql, bot, ADMIN_ID, cursor, conn
from src.handlers.users.users import create_card
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData
from src.utils.admin_logger import send_error_to_admin


logger = logging.getLogger(__name__)


def normalize_input(text: str | None) -> str:
    """Normalize user input: trim whitespace and normalize unicode."""
    return unicodedata.normalize('NFKD', (text or "").strip())


def extract_message_text(message: Message) -> str | None:
    if message.text is None:
        return None
    return message.text.strip()


async def prompt_selection_from_keyboard(message: Message) -> None:
    await message.answer("Iltimos, tugmalardan birini tanlang yoki qidiruvdan foydalaning.")

reg_router = Router()
_SCORE_YEAR = 2025
_CAPTION_YEARS = (2025, 2024, 2023)

# Main-menu section buttons — pressing these from any FSM state should clear
# state and return the user to the main menu.
_SECTION_BTNS = frozenset({
    "📊 Ball yetadigan yo'nalishlar",
    "\U0001f4da Yo\u02bbnalishlar bo\u02bbyicha",
    "📈 Viloyatlar kesimida",
})

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
        cursor.execute(
            "SELECT id, region_id, region_name FROM regions WHERE lower(region_name) LIKE %s ORDER BY region_name LIMIT 50",
            (f"%{text}%",),
        )
    else:
        cursor.execute("SELECT id, region_id, region_name FROM regions ORDER BY region_name LIMIT 50")
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
    text = extract_message_text(message)
    if text is None:
        await prompt_selection_from_keyboard(message)
        return

    if text == "🔙 Ortga":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    elif text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        if text in _SECTION_BTNS:
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                                 reply_markup=await UserPanels.main_manu())
            return
        region_name = text
        cursor.execute("SELECT region_id FROM regions WHERE region_name = %s", (region_name,))
        region_id = cursor.fetchone()
        if region_id:
            region_id = region_id[0]
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
            "SELECT DISTINCT u.un_id, u.un_text FROM regions r JOIN universities u ON r.region_id = u.region_id WHERE r.region_name = %s AND lower(u.un_text) LIKE %s ORDER BY u.un_text LIMIT 50",
            (region_name, f"%{text}%"))
    else:
        cursor.execute(
            "SELECT DISTINCT u.un_id, u.un_text FROM regions r JOIN universities u ON r.region_id = u.region_id WHERE r.region_name = %s ORDER BY u.un_text LIMIT 50",
            (region_name,),
        )
    universities = cursor.fetchall()
    if universities:
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
    text = extract_message_text(message)
    if text is None:
        await prompt_selection_from_keyboard(message)
        return

    if text == "🔙 Ortga":
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
        except Exception:
            await message.delete()
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html", reply_markup=await UserPanels.main_manu())
    elif text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html", reply_markup=await UserPanels.main_manu())
    else:
        if text in _SECTION_BTNS:
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang</b>", parse_mode="html", reply_markup=await UserPanels.main_manu())
            return
        try:
            un_name = normalize_input(text)
            cursor.execute("SELECT un_id FROM universities WHERE TRIM(LOWER(un_text))=%s", (un_name.lower(),))
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
                else:
                    await message.answer("❌ Bu OTM uchun ta'lim turi mavjud emas. Iltimos, boshqa OTMni tanlang.")
                    await state.set_state(FormReg.reg2)
            else:
                await message.answer("❌ OTM topilmadi. Iltimos, ro'yxatdan tanlang yoki tezkor qidiruvdan foydalaning.")
        except TelegramForbiddenError:
            return
        except TelegramNetworkError as error:
            logger.warning("Transient Telegram network error in reg2 for user_id=%s: %s", message.from_user.id, error)
            return
        except Exception as e:
            await send_error_to_admin(
                bot=bot,
                error=e,
                context={"user_id": message.from_user.id, "handler": "FormReg.reg2 (university selection)"},
                handler_name="chosen_university (reg2)"
            )
            await message.answer("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")

@reg_router.message(FormReg.reg3)
async def chosen_type(message: Message, state: FSMContext):
    text = extract_message_text(message)
    if text is None:
        await prompt_selection_from_keyboard(message)
        return

    if text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg2)
        data = await state.get_data()
        region_name = data.get("region_name")
        cursor.execute(
            "SELECT u.un_text FROM regions r JOIN universities u ON r.region_id = u.region_id WHERE r.region_name = %s ORDER BY u.un_text",
            (region_name,),
        )
        rows = cursor.fetchall()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
        ])
        keyboard = [[KeyboardButton(text=row[0])] for row in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer(f"<b>Siz tanlagan hududda {len(rows)} ta oliygohda mavjud\n\n🏢 OTMni tanlang:</b>", parse_mode="html", reply_markup=btn)
        await message.answer("<b>Tezkor qidiruvdan foydalaning...</b>", parse_mode="html", reply_markup=kb)
    elif text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        if text in _SECTION_BTNS:
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang</b>", parse_mode="html",
                                 reply_markup=await UserPanels.main_manu())
            return
        try:
            name = normalize_input(text)
            data = await state.get_data()
            un_id = data.get("un_id")
            region_id = data.get("region_id")
            cursor.execute("SELECT ty_id FROM gettypes WHERE TRIM(LOWER(ty_text))=%s AND un_id=%s AND region_id=%s", (name.lower(), un_id, region_id))
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
                    JOIN getlangs g ON m.lan_id::text = g.lan_id::text AND m.un_id::text = g.un_id::text AND m.ty_id::text = g.ty_id::text AND m.region_id::text = g.region_id::text
                    WHERE m.un_id = %s AND m.ty_id = %s AND m.year = 2025
                ''', (un_id, ty_id))
                rows = cursor.fetchall()
                if rows:
                    keyboard = []
                    for row1, row2 in rows:
                        keyboard.append([KeyboardButton(text=row2[:60])])

                    keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])

                    btn = ReplyKeyboardMarkup(
                        keyboard=keyboard,
                        resize_keyboard=True,
                    )
                    await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)
                else:
                    await message.answer("❌ Bu ta'lim shakli uchun til mavjud emas. Iltimos, boshqa shakl tanlang.")
                    await state.set_state(FormReg.reg3)
            else:
                await message.answer("❌ Ta'lim shakli topilmadi. Iltimos, ro'yxatdan tanlang.")
        except TelegramForbiddenError:
            return
        except TelegramNetworkError as error:
            logger.warning("Transient Telegram network error in reg3 for user_id=%s: %s", message.from_user.id, error)
            return
        except Exception as e:
            await send_error_to_admin(
                bot=bot,
                error=e,
                context={"user_id": message.from_user.id, "handler": "FormReg.reg3 (education type selection)"},
                handler_name="chosen_type (reg3)"
            )
            await message.answer("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")


@reg_router.message(FormReg.reg4)
async def chosen_lang(message: Message, state: FSMContext):
    text = extract_message_text(message)
    if text is None:
        await prompt_selection_from_keyboard(message)
        return

    lan_text = text.lower()
    if text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg3)
        data = await state.get_data()
        un_id = data.get("un_id")
        region_id = data.get("region_id")
        cursor.execute("SELECT ty_id, ty_text FROM gettypes WHERE region_id=%s AND un_id=%s", (region_id, un_id))
        rows = cursor.fetchall()
        keyboard = [[KeyboardButton(text=row[1])] for row in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🔰 Ta'lim shaklini tanlang: 👇</b>", parse_mode="html", reply_markup=btn)
    elif text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        if text in _SECTION_BTNS:
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang</b>", parse_mode="html",
                                 reply_markup=await UserPanels.main_manu())
            return
        try:
            data = await state.get_data()
            un_id = data["un_id"]
            ty_id = data["ty_id"]
            region_id = data["region_id"]
            cursor.execute(
                "SELECT lan_id FROM getlangs WHERE TRIM(LOWER(lan_text))=%s AND un_id=%s AND ty_id=%s AND region_id=%s",
                (lan_text.strip().lower(), un_id, ty_id, region_id),
            )
            lan_id = cursor.fetchone()
            if lan_id:
                lan_id = lan_id[0]
                await state.update_data(lan_id=lan_id)
                data = await state.get_data()
                region_id = data["region_id"]
                un_id = data["un_id"]
                ty_id = data["ty_id"]
                lan_id = data["lan_id"]
                cursor.execute("""SELECT mvdir, nomi FROM mandat WHERE year=2025 AND region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s""",
                               (region_id, un_id, ty_id, lan_id))
                rows = cursor.fetchall()
                if rows:
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
                else:
                    await message.answer("❌ Bu til uchun yo'nalish mavjud emas. Iltimos, boshqa til tanlang.")
                    await state.set_state(FormReg.reg4)
            else:
                await message.answer("❌ Ta'lim tili topilmadi. Iltimos, ro'yxatdan tanlang.")
        except TelegramForbiddenError:
            return
        except TelegramNetworkError as error:
            logger.warning("Transient Telegram network error in reg4 for user_id=%s: %s", message.from_user.id, error)
            return
        except Exception as e:
            await send_error_to_admin(
                bot=bot,
                error=e,
                context={"user_id": message.from_user.id, "handler": "FormReg.reg4 (language selection)"},
                handler_name="chosen_lang (reg4)"
            )
            await message.answer("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")

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
            "SELECT DISTINCT id, mvdir, nomi FROM mandat WHERE year=2025 AND lower(nomi) LIKE %s AND region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s ORDER BY nomi LIMIT 50",
            (f"%{text}%", region_id, un_id, ty_id, lan_id))
    else:
        cursor.execute(
            "SELECT DISTINCT id, mvdir, nomi FROM mandat WHERE year=2025 AND region_id=%s AND un_id=%s AND ty_id=%s AND lan_id=%s ORDER BY nomi LIMIT 50",
            (region_id, un_id, ty_id, lan_id))
    facs = cursor.fetchall()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Izlash", switch_inline_query_current_chat=" ")]
    ])
    if facs:
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
    text = extract_message_text(message)
    if text is None:
        await prompt_selection_from_keyboard(message)
        return

    if text == "🔙 Ortga":
        await message.delete()
        await state.set_state(FormReg.reg4)
        data = await state.get_data()
        ty_id = data.get("ty_id")
        un_id = data.get("un_id")
        cursor.execute("""
            SELECT DISTINCT g.lan_id, g.lan_text
            FROM mandat m
            JOIN getlangs g ON m.lan_id::text = g.lan_id::text AND m.un_id::text = g.un_id::text AND m.ty_id::text = g.ty_id::text AND m.region_id::text = g.region_id::text
            WHERE m.un_id = %s AND m.ty_id = %s AND m.year = 2025
        """, (un_id, ty_id))
        rows = cursor.fetchall()
        keyboard = [[KeyboardButton(text=row2[:60])] for row1, row2 in rows]
        keyboard.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer("<b>🇺🇿 Ta'lim tilini tanlang:</b>", parse_mode="html", reply_markup=btn)
    elif text == "🔙 Bosh menu":
        await message.delete()
        await state.clear()
        await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                             reply_markup=await UserPanels.main_manu())
    else:
        if text in _SECTION_BTNS:
            await state.clear()
            await message.answer("<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                                 reply_markup=await UserPanels.main_manu())
            return
        try:
            if " - " not in text:
                await message.answer("Yo'nalishni ro'yxatdan tanlang yoki inline qidiruvdan foydalaning.")
                return
            mvdir, nomi = text.split(" - ", 1)
            data = await state.get_data()
            un_id = data.get("un_id")
            ty_id = data.get("ty_id")
            lan_id = data.get("lan_id")
            if not un_id or not ty_id or not lan_id:
                await state.clear()
                await message.answer(
                    "❌ Sessiya muddati tugagan. Iltimos, /start bosing.",
                    reply_markup=await UserPanels.main_manu()
                )
                return
            cursor.execute("SELECT un_text FROM universities WHERE un_id=%s", (un_id,))
            un_name = cursor.fetchone()
            cursor.execute("SELECT lan_text FROM getlangs WHERE lan_id=%s", (lan_id,))
            lan_text = cursor.fetchone()
            cursor.execute("SELECT ty_text FROM gettypes WHERE ty_id=%s", (ty_id,))
            ty_text = cursor.fetchone()
            cursor.execute("""
                SELECT gr_b, con_b, olimp FROM mandat
                WHERE year=2025 AND un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s AND nomi=%s
            """, (un_id, ty_id, lan_id, mvdir, nomi))
            ball_row = cursor.fetchone()
            if not un_name or not lan_text or not ty_text or not ball_row:
                await message.answer("Ma'lumot topilmadi yoki to'liq emas. Iltimos, qaytadan tanlang.")
                return
            gr_b, con_b, olimp = ball_row

            cursor.execute(
                """
                SELECT year, gr_b, con_b
                FROM mandat
                WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s AND nomi=%s
                  AND year IN (2025, 2024, 2023)
                ORDER BY year DESC
                """,
                (un_id, ty_id, lan_id, mvdir, nomi),
            )
            year_rows = cursor.fetchall()
            year_scores = {int(y): (float(gb or 0), float(cb or 0)) for y, gb, cb in year_rows}
            score_lines = []
            for y in _CAPTION_YEARS:
                if y in year_scores:
                    y_gr, y_con = year_scores[y]
                    score_lines.append(f"<b>{y}</b>: Grand {y_gr} | Kontrakt {y_con}")
            score_block = "\n".join(score_lines) if score_lines else f"<b>{_SCORE_YEAR}</b>: Grand {gr_b} | Kontrakt {con_b}"

            message_text = (
                f"<b>🏛 OLIYGOH:</b> {un_name[0]}\n\n<b>📚 TAʼLIM YO'NALISHI</b> - {mvdir} - {nomi}\n\n<b>🇺🇿 TAʼLIM TILI</b> - {lan_text[0]}\n\n"
                f"<b>🔰 TAʼLIM SHAKLI</b> - {ty_text[0]}\n\n<b>📈 OʻTISH BALLARI (yillar kesimida):</b>\n{score_block}\n\n"
                f"<b>🏆 OLIMPIADA G'OLIBLARI:</b> {olimp}\n\n"
                f"<b>© <a href='https://t.me/mandatjavobbot%sstart=share'>@Mandatjavobbot</a> - oʻtish ballari va mandat natijalari</b>")

            user_id = message.from_user.id
            cursor.execute("""
                SELECT file_id FROM photos
                WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s
            """, (un_id, ty_id, lan_id, mvdir))
            old = cursor.fetchone()
            if old:
                try:
                    await message.answer_photo(photo=old[0], caption=message_text, parse_mode="html")
                    return
                except TelegramBadRequest:
                    # Eski file_id ishlamasa keshdan o'chirib qayta yaratamiz.
                    cursor.execute(
                        "DELETE FROM photos WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND mvdir=%s",
                        (un_id, ty_id, lan_id, mvdir),
                    )
                    conn.commit()

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
        except TelegramForbiddenError:
            # Foydalanuvchi botni bloklagan — admin ga xabar yubormaslik
            return
        except TelegramNetworkError as error:
            logger.warning("Transient Telegram network error in reg5 for user_id=%s direction=%s: %s", message.from_user.id, text, error)
            return
        except Exception as e:
            await send_error_to_admin(
                bot=bot,
                error=e,
                context={
                    "user_id": message.from_user.id,
                    "handler": "FormReg.reg5 (direction selection)",
                    "selected_direction": text
                },
                handler_name="chosen_lang (reg5)"
            )
            await message.answer("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
            return
