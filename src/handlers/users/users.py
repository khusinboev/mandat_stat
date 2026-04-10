import os
import logging

from PIL import Image, ImageDraw, ImageFont
from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, InlineQuery, InlineQueryResultArticle,
    InputTextMessageContent, WebAppInfo
)

from config import bot, ADMIN_ID
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

logger = logging.getLogger(__name__)
user_router = Router()

CURRENT_YEAR = "2025"
BOT_USERNAME = "mandatjavobbot"


# ═══════════════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════════════

@user_router.message(CommandStart())
async def start_cmd(message: Message):
    await message.answer(
        "Botimizga xush kelibsiz! Kerakli bo'limni tanlang 👇",
        parse_mode="html",
        reply_markup=await UserPanels.asos_manu(),
    )


# ═══════════════════════════════════════════════════════════════
#  KANAL A'ZOLIK TEKSHIRISH CALLBACK
# ═══════════════════════════════════════════════════════════════

@user_router.callback_query(F.data == "check", F.message.chat.type == ChatType.PRIVATE)
async def check_subscription(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        ok, channels = await CheckData.check_member(bot, user_id)
        if ok:
            try:
                await call.message.delete()
            except Exception:
                pass
            await call.answer()
            await bot.send_message(
                chat_id=user_id,
                text="Quyidagi menulardan birini tanlang!",
                parse_mode="html",
                reply_markup=await UserPanels.asos_manu(),
            )
        else:
            await call.answer(
                show_alert=True,
                text="Botimizdan foydalanish uchun barcha kanallarga a'zo bo'ling",
            )
    except Exception as e:
        logger.error(f"check callback xato: {e}")
        try:
            await call.answer()
        except Exception:
            pass


@user_router.callback_query(F.data == "check2", F.message.chat.type == ChatType.PRIVATE)
async def check_subscription2(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        ok, channels = await CheckData.check_member2(bot, user_id)
        if ok:
            try:
                await call.message.delete()
            except Exception:
                pass
            await call.answer()
            await bot.send_message(
                chat_id=user_id,
                text="Quyidagi menulardan birini tanlang!",
                parse_mode="html",
                reply_markup=await UserPanels.asos_manu(),
            )
        else:
            await call.answer(
                show_alert=True,
                text="Botimizdan foydalanish uchun barcha kanallarga a'zo bo'ling",
            )
    except Exception as e:
        logger.error(f"check2 callback xato: {e}")
        try:
            await call.answer()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  BOSH MENYU TUGMALARI
# ═══════════════════════════════════════════════════════════════

@user_router.message(F.text == "📕BAKALAVRIAT 2025")
async def bakalavriat_2025(message: Message):
    """✅ 2024 → 2025 tuzatildi"""
    await message.answer(
        "Quyidagi bo'limlardan birini tanlang 👇",
        parse_mode="html",
        reply_markup=await UserPanels.main_manu(),
    )


@user_router.message(F.text == "◀️ Ortga")
async def back_to_main(message: Message):
    await message.answer(
        "Bosh menyu 👇",
        parse_mode="html",
        reply_markup=await UserPanels.asos_manu(),
    )


@user_router.message(F.text == "📘O'qishni ko'chirish")
async def move_menu(message: Message):
    await message.answer(
        "O'qishni ko'chirish bo'limi 👇",
        parse_mode="html",
        reply_markup=await UserPanels.move_manu(),
    )


# ═══════════════════════════════════════════════════════════════
#  O'QISHNI KO'CHIRISH BO'LIMLARI
# ═══════════════════════════════════════════════════════════════

@user_router.message(F.text == "📝 Baholash mezonlari️")
async def baholash_mezonlari(message: Message):
    ok, channels = await CheckData.check_member2(bot, message.from_user.id)
    if not ok:
        await message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn2(channels),
        )
        return

    # ✅ 2025/2026 yil ma'lumotlari
    await message.answer(
        "<b>⚡️ 2025/2026-o'quv yilida o'qishni ko'chirish imtihonlarida "
        "baholash mezonlari:</b>\n\n"

        "👉 <b>Majburiy 3 ta fan bo'yicha:</b>\n\n"
        "<b>➖ Ona tili</b> (o'zbek, rus yoki qoraqalpoq tili) — 10 ta savol, "
        "har biri 1,1 ball. Maksimal: <b>11 ball</b>\n\n"
        "<b>➖ Matematika</b> — 10 ta savol, har biri 1,1 ball. "
        "Maksimal: <b>11 ball</b>\n\n"
        "<b>➖ O'zbekiston tarixi</b> — 10 ta savol, har biri 1,1 ball. "
        "Maksimal: <b>11 ball</b>\n\n"
        "✅ <b>Majburiy blok jami: 33 ball</b>\n\n"

        "👉 <b>Mutaxassislik 2 ta fan bo'yicha:</b>\n\n"
        "<b>➖ 1-fan</b> — 30 ta savol, har biri 3,1 ball. "
        "Maksimal: <b>93 ball</b>\n\n"
        "<b>➖ 2-fan</b> — 30 ta savol, har biri 2,1 ball. "
        "Maksimal: <b>63 ball</b>\n\n"
        "✅ <b>Mutaxassislik blok jami: 156 ball</b>\n\n"

        "📝 <i>2025/2026-o'quv yilida 5 ta fan bo'yicha 90 ta test topshirig'i beriladi. "
        "Maksimal ball — <b>189 ball</b></i>\n\n"

        f"<i>© <a href='https://t.me/{BOT_USERNAME}?start=share'>@{BOT_USERNAME}</a> "
        "— O'qishni ko'chirishga oid ma'lumotlar bazasi!</i>",
        parse_mode="HTML",
    )


@user_router.message(F.text == "📚 Fanlar majmuasi️")
async def fanlar_majmuasi(message: Message):
    ok, channels = await CheckData.check_member2(bot, message.from_user.id)
    if not ok:
        await message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn2(channels),
        )
        return

    await message.answer_document(
        document="BQACAgIAAxkBAAGQxtNoVAi8RFho9rDGd2uLPCfdPsC5YQACrUwAAtE4SEu0bZFBET334TYE",
        caption=(
            "<b>📕 FANLAR MAJMUASI!\n\n"
            "📝 O'qishni ko'chirish imtihonlarida test topshiriladigan fanlar majmuasi.\n\n"
            "✔️ Yo'nalishlar bo'yicha qaysi fandan imtihon bo'lishi ko'rsatilgan.\n\n"
            "⚠️ O'qishni ko'chirishda aynan mana shu 2025/2026-o'quv yilidagi "
            "fanlar majmuasidan foydalaniladi.\n\n"
            f"© @{BOT_USERNAME} — O'qishni ko'chirishga oid ma'lumotlar bazasi!</b>"
        ),
        parse_mode="html",
    )


@user_router.message(F.text == "📊 O'tish ballari️")
async def otish_ballari(message: Message):
    ok, channels = await CheckData.check_member2(bot, message.from_user.id)
    if not ok:
        await message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn2(channels),
        )
        return

    await message.answer_photo(
        photo="AgACAgIAAxkBAAHxJvRofhQTCwdIp6X_ZwJrQ9eIPMDENAACNvIxG0SS-EtT5x82hi17mgEAAwIAA3kAAzYE",
        caption=(
            "<b>⚡️ O'qishni ko'chirishda qancha ball to'plash kerak?</b>\n\n"
            "2025/2026-o'quv yili uchun xorijiy va nodavlat oliy ta'lim muassasalaridan "
            "talabalar o'qishini respublika <b>davlat oliy ta'lim muassasalariga ko'chirish "
            "bo'yicha o'tkaziladigan maxsus sinovlar bo'yicha o'tish ballari</b> tasdiqlangan.\n\n"
            "<b>Yuqoridagi o'tish ballari quyidagilarga taalluqli:</b>\n\n"
            "1️⃣ Xorijdagi OTMlardan yurtimizdagi davlat OTMlariga o'qishini ko'chirmoqchi "
            "bo'lganlarga;\n"
            "2️⃣ Yurtimizdagi nodavlat OTMlar hamda xorijiy OTMlarning filiallaridan "
            "davlat OTMlariga o'qishini ko'chirmoqchi bo'lganlarga.\n\n"
            "Eslatma: o'qishni ko'chirish bo'yicha arizalar "
            "<b>15-iyuldan 5-avgustgacha</b> qabul qilinadi.\n\n"
            f"<b>© @{BOT_USERNAME} — O'qishni ko'chirishga oid ma'lumotlar bazasi!</b>"
        ),
        parse_mode="html",
    )


@user_router.message(F.text == "💰 Super kontrakt miqdori️")
async def super_kontrakt(message: Message):
    ok, channels = await CheckData.check_member2(bot, message.from_user.id)
    if not ok:
        await message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn2(channels),
        )
        return

    await message.answer(
        "<b>⚡️ O'QISHNI KO'CHIRISHDA SUPER KONTRAKT MIQDORI QANCHA❓</b>\n\n"
        "<u>Super-kontrakt miqdori quyidagicha:</u>\n\n"
        "👉 0.1 balldan — <b>1.0 ballgacha</b> yetmasa: oddiy kontraktning <b>1.5 barobari</b>\n"
        "👉 1.1 balldan — <b>2.0 ballgacha</b> yetmasa: oddiy kontraktning <b>2 barobari</b>\n"
        "👉 2.1 balldan — <b>3.0 ballgacha</b> yetmasa: oddiy kontraktning <b>2.5 barobari</b>\n"
        "👉 3.1 balldan — <b>4.0 ballgacha</b> yetmasa: oddiy kontraktning <b>3 barobari</b>\n\n"
        "☝️ Agar <b>4.0 balldan ortiq</b> yetmasa — tabaqalashtirilgan to'lov-kontraktning "
        "minimal miqdori to'lanadi. Bu miqdor bazaviy kontraktning "
        "<b>8 barobardan 25 barobargacha</b> belgilanishi mumkin.\n\n"
        f"<b>© @{BOT_USERNAME} — O'qishni ko'chirishga oid ma'lumotlar bazasi!</b>",
        parse_mode="html",
    )


@user_router.message(F.text == "🧮 Tabaqalashtirilgan kontrakt miqdori")
async def tabaqalashtirilgan(message: Message):
    ok, channels = await CheckData.check_member2(bot, message.from_user.id)
    if not ok:
        await message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn2(channels),
        )
        return

    await message.answer_document(
        document="BQACAgIAAxkBAAGQx5toVAkCAX8b_5xpiuOVqfwWAdGstAACvEkAAs5EgUps3NE-tIIBSDYE",
        caption=(
            "<b>Tabaqalashtirilgan to'lov-kontrakt miqdorlari</b>\n\n"
            "2025/2026-o'quv yilida o'qishni ko'chirish sinovlarida o'tish baliga "
            "<b>4,05 balldan ortiq yetmagan, 56,7 balldan kam bo'lmaganlar</b> uchun "
            "tabaqalashtirilgan kontrakt miqdorlari yo'nalishlar kesimida.\n\n"
            "Shuningdek, har yili tabaqalashtirilgan to'lov-kontrakt qiymatini "
            "<u>15-oktyabrga qadar to'liq to'lagan abituriyentlarga 10% chegirma beriladi.</u>\n\n"
            f"<b>© @{BOT_USERNAME} — O'qishni ko'chirishga oid ma'lumotlar bazasi!</b>"
        ),
        parse_mode="html",
    )


@user_router.message(F.text == "📄 Transkript yuklash")
async def transkript(message: Message):
    ok, channels = await CheckData.check_member2(bot, message.from_user.id)
    if not ok:
        await message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn2(channels),
        )
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Transkript yuklash 🗂",
            web_app=WebAppInfo(url="https://my.hemis.uz/")
        )]
    ])
    await message.answer(
        "<b>O'qishni ko'chirishda asosiy hujjat — transkript. "
        "Transkriptni yuklash uchun pastdagi havolani bosing 👇</b>",
        reply_markup=keyboard,
        parse_mode="html",
    )


@user_router.message(F.text == "📚 Namunaviy test topshiriqlari")
async def namunaviy_testlar(message: Message):
    ok, channels = await CheckData.check_member(bot, message.from_user.id)
    if not ok:
        await message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn(channels),
        )
        return

    await message.answer(
        "<b>⚡️ Bilimni baholash agentligi tomonidan olinadigan imtihonlarning "
        "<u>majburiy va mutaxassislik</u> fanlaridan "
        "<u>namunaviy test topshiriqlari</u></b>\n\n"

        "<b>Majburiy bloklar:</b>\n"
        "👉 <a href='https://t.me/nodavlattalim/1393'>Ona tili</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1394'>Rus tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1395'>Qoraqalpoq tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1396'>Matematika</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1397'>Matematika (rus)</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1398'>O'zbekiston tarixi</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1399'>O'zbekiston tarixi (rus)</a>\n\n"

        "<b>Mutaxassislik fanlari:</b>\n"
        "👉 <a href='https://t.me/nodavlattalim/1400'>Huquqshunoslik</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1401'>Tarix</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1402'>Biologiya</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1403'>Fizika</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1404'>Kimyo</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1405'>Matematika</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1406'>Geografiya</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1407'>Ingliz tili</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1408'>Nemis tili</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1409'>Fransuz tili</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1410'>Ona tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1412'>Rus tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1411'>Qoraqalpoq tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1413'>Ona tili va adabiyoti (o'zga tilli)</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1414'>Rus tili va adabiyoti (o'zga tilli)</a>\n\n"

        f"<b>© <a href='https://t.me/{BOT_USERNAME}?start=share'>@{BOT_USERNAME}</a> "
        "- o'tish ballari va mandat natijalari</b>",
        parse_mode="HTML",
    )


# ═══════════════════════════════════════════════════════════════
#  KARTA YARATISH YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════

def split_text_by_words(text: str, max_len: int = 45) -> str:
    """Matnni so'z chegarasida qatorlarga bo'ladi."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_len:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current)
    return "\n".join(lines)


def create_card(
    univer: str, faculty: str, lang: str, edu: str,
    grand, kont, olmp, name
) -> bool:
    """
    Mandat kartasini yaratadi va photos/ papkaga saqlaydi.
    ✅ 2024 → 2025 tuzatildi.
    Qaytaradi: True — muvaffaqiyatli, False — xato.
    """
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(CURRENT_DIR, "edu.png")
    photos_dir = os.path.join(CURRENT_DIR, "photos")
    output_path = os.path.join(photos_dir, f"{name}.jpg")

    os.makedirs(photos_dir, exist_ok=True)

    try:
        if not os.path.exists(template_path):
            logger.error(f"Shablon topilmadi: {template_path}")
            return False

        image = Image.open(template_path)
        draw = ImageDraw.Draw(image)

        font_path = os.path.join(CURRENT_DIR, "Quicksand-Bold.otf")
        try:
            title_font = ImageFont.truetype(font_path, 100)
            main_font  = ImageFont.truetype(font_path, 90)
        except Exception:
            logger.warning("Shrift topilmadi, standart shrift ishlatiladi")
            title_font = ImageFont.load_default()
            main_font  = ImageFont.load_default()

        draw.text((500,  200),  split_text_by_words(univer),  font=title_font, fill="black")
        draw.text((300,  800),  split_text_by_words(faculty), font=main_font,  fill="black")
        draw.text((550,  1600), str(lang),  font=main_font, fill="white")
        draw.text((1500, 1600), str(edu),   font=main_font, fill="white")
        # ✅ "2024" → CURRENT_YEAR ("2025") tuzatildi
        draw.text((2450, 1600), CURRENT_YEAR, font=main_font, fill="white")
        draw.text((650,  2120), str(grand), font=main_font, fill="black")
        draw.text((1420, 2120), str(kont),  font=main_font, fill="black")
        draw.text((2550, 2170), str(olmp),  font=main_font, fill="black")

        image.save(output_path, quality=85, optimize=True)
        logger.info(f"Karta yaratildi: {output_path}")
        return True

    except Exception as e:
        logger.error(f"create_card xato: {e}")
        return False
