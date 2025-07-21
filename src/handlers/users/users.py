import os

from PIL import Image, ImageDraw, ImageFont
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
async def start_cmd1(message: Message):
    await message.answer("Botimizga xush kelibsiz, kerakli bo'limni tanlab va davom eting!", parse_mode="html", reply_markup=await UserPanels.asos_manu())

@user_router.callback_query(F.data == "check", F.message.chat.type == ChatType.PRIVATE)
async def check(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        check_status, channels = await CheckData.check_member(bot, user_id)
        if check_status:
            try:
                await call.message.delete()
                await call.answer()
            except:
                pass
            await bot.send_message(chat_id=user_id,
                                   text="Quyidagi menulardan birini tanlang!",
                                   parse_mode="html", reply_markup=await UserPanels.asos_manu())
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


@user_router.message(F.text == "📕BAKALAVRIAT 2024")
async def start_cmd2(message: Message):
    await message.answer("Quyidagi menulardan birini tanlang!", parse_mode="html", reply_markup=await UserPanels.main_manu())

@user_router.message(F.text == "◀️ Ortga")
async def start_cmd3(message: Message):
    await message.answer("Quyidagi menulardan birini tanlang!", parse_mode="html", reply_markup=await UserPanels.asos_manu())


@user_router.message(F.text == "📘O'qishni ko'chirish")
async def start_cmd4(message: Message):
    await message.answer("Quyidagi menulardan birini tanlang!", parse_mode="html", reply_markup=await UserPanels.move_manu())

@user_router.message(F.text == "📝 Baholash mezonlari️")
async def start_cmd5(message: Message):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        await message.answer(
        "<b>⚡️Bu yilgi o‘qishni ko‘chirish imtihonlarida baholash mezonlari quyidagicha bo‘ladi:</b>\n\n"

        "👉 <b>Barcha test topshiruvchilar uchun majburiy bo‘lgan 3 ta fan bo‘yicha:</b>\n\n"

        "<b>➖ Ona tili</b> (o‘zbek, rus yoki qoraqalpoq tili) – 10 ta savol.\n"
        "Har biri uchun 1,1 balldan.\n"
        "Maksimal ball – 11 ball.\n\n"

        "<b>➖ Matematika</b> – 10 ta savol.\n"
        "Har biri uchun 1,1 balldan.\n"
        "Maksimal ball – 11 ball.\n\n"

        "<b>➖ O‘zbekiston tarixi</b> – 10 ta savol.\n"
        "Har biri uchun 1,1 balldan.\n"
        "Maksimal ball – 11 ball.\n\n"

        "✅ <b>Jami to‘plash mumkin bo‘lgan ball – 33 ball.</b>\n\n"

        "👉 <b>Bakalavriat taʼlim yoʻnalishiga mos boʻlgan 2 ta mutaxassislik fan bo‘yicha:</b>\n\n"

        "<b>➖ 1-fan</b> – 30 ta savol.\n"
        "Har biri uchun 3,1 balldan.\n"
        "Maksimal ball – 93 ball.\n\n"

        "<b>➖ 2-fan</b> – 30 ta savol.\n"
        "Har biri uchun 2,1 balldan.\n"
        "Maksimal ball – 63 ball.\n\n"

        "✅ <b>Jami to‘plash mumkin bo‘lgan ball – 156 ball.</b>\n\n"

        "📝 <i>Umumiy holda, 2025/2026-o‘quv yilida o‘qishni ko‘chirish talabida bo‘lganlar uchun "
        "5 ta fan bo‘yicha jami 90 ta test topshirig‘i beriladi. "
        "Bunda to‘plash mumkin bo‘lgan maksimal ball – <b>189 ball</b>ni tashkil etadi.</i>\n\n"

        "<i>© <a href='https://t.me/mandatjavobbot?start=share'>@mandatjavobbot</a> — O‘qishni ko‘chirishga oid ma’lumotlar bazasi!</i>",
        parse_mode="HTML"
    )
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))

@user_router.message(F.text == "📚 Fanlar majmuasi️")
async def start_cmd6(message: Message):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        await message.answer_document(document="BQACAgIAAxkBAAGQxtNoVAi8RFho9rDGd2uLPCfdPsC5YQACrUwAAtE4SEu0bZFBET334TYE",
        caption="<b>📕 FANLAR MAJMUASI! \n\n"
"📝 O'qishni ko'chirish imtihonlarida test topshiriladigan fanlar majmuasi.\n\n"
"✔️ Yo'nalishlar bo'yicha qaysi fandan imtihon bo'lishi ko'rsatilgan.\n\n"
"⚠️ Oʻqishni koʻchirishda aynan mana shu 2024/2025-o'quv yilidagi fanlar majmuasidan foydalaniladi. \n\n"
"© @mandatjavobbot — O'qishni ko'chirishga oid ma'lumotlar bazasi!</b>"
    , parse_mode="html")
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))

@user_router.message(F.text == "📊 O'tish ballari️")
async def start_cmd7(message: Message):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        await message.answer_photo(photo="AgACAgIAAxkBAAHxJvRofhQTCwdIp6X_ZwJrQ9eIPMDENAACNvIxG0SS-EtT5x82hi17mgEAAwIAA3kAAzYE", caption="<b>⚡️O‘qishni ko‘chirishda qancha ball to'plash kerak?</b>\n\n"
"2025/2026-oʻquv yili uchun xorijiy va nodavlat oliy taʼlim muassasalaridan talabalar oʻqishini respublika <b>davlat oliy taʼlim muassasalariga koʻchirish boʻyicha oʻtkaziladigan maxsus sinovlar boʻyicha oʻtish ballari</b> tasdiqlangan.\n\n"
"<b>Yuqoridagi o’tish ballari quyidagilarga taalluqli:</b>\n\n"
"1️⃣ xorijdagi OTMlardan yurtimizdagi davlat OTMlariga o’qishini ko’chirmoqchi bo’lganlarga;\n"
"2️⃣ yurtimizdagi nodavlat OTMlar hamda xorijiy OTMlarning filiallaridan davlat OTMlariga o’qishini ko’chirmoqchi bo’lganlarga.\n\n"
"Eslatma: o’qishni ko’chirish bo’yicha arizalar <b>15-iyuldan 5-avgustgacha</b> qabul qilinadi.\n\n"
"<b>© @mandatjavobbot — O'qishni ko'chirishga oid ma'lumotlar bazasi!!</b>", parse_mode="html")
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))

@user_router.message(F.text == "💰 Super kontrakt miqdori️")
async def start_cmd8(message: Message):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        await message.answer("<b>⚡️O'QISHNI KO'CHIRISHDA SUPER KONTRAKT MIQDORI QANCHA❓</b>\n\n"
"<u>Super-kontrakt miqdori quyidagicha:</u>\n\n"
"👉 Agar 0.1 balldan — <b>1.0 ballgacha</b> yetmasa oddiy kontraktning <b>1.5 barobarini</b> to'laydi;\n"
"👉 Agar 1,1 baldan — <b>2,0  ballgacha</b> yetmasa oddiy kontraktning <b>2 barobarini</b> to'laydi;\n"
"👉 Agar 2,1 baldan — <b>3.0 ballgacha</b> yetmasa oddiy kontraktning <b>2.5 barobarini</b> to'laydi;\n"
"👉 Agar 3,1 balldan — <b>4.0 ballgacha</b> yetmasa oddiy kontraktning <b>3 barobarini</b> to'laydi;\n\n"
"☝️ Agar <b>4,0 balldan ortiq ball yetmasa</b> tabaqalashtirilgan to'lov-kontraktning minimal miqdorini to'laydi. Bu miqdor yo'nalishlarga qarab bazaviy kontraktning <b>8 barobardan 25 barobargacha</b> belgilanishi mumkin.\n\n"
"<b>© @mandatjavobbot — O'qishni ko'chirishga oid ma'lumotlar bazasi!</b>", parse_mode="html")
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))


@user_router.message(F.text == "🧮 Tabaqalashtirilgan kontrakt miqdori")
async def start_cmd9(message: Message):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        await message.answer_document(document="BQACAgIAAxkBAAGQx5toVAkCAX8b_5xpiuOVqfwWAdGstAACvEkAAs5EgUps3NE-tIIBSDYE",
                                  caption="<b>Tabaqalashtirilgan to‘lov-kontrakt miqdorlari</b>\n\n"
"2025/2026-oʻquv yilida o'qishni ko'chirish sinovlarida o'tish baliga <b>4,05 balldan ortiq yetmagan, 56,7 balldan kam boʻlmaganlar</b> uchun tabaqalashtirilgan kontrakt miqdorlari yo'nalishlar kesimida.\n\n"
"Shuningdek, har yili tabaqalashtirilgan toʻlov-kontrakt qiymatini <u>15-oktyabrga qadar to‘liq toʻlagan abituriyentlarga 10%lik chegirma beriladi.</u>\n\n"
"<b>© @mandatjavobbot — O'qishni ko'chirishga oid ma'lumotlar bazasi!</b>", parse_mode="html")
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))


@user_router.message(F.text == "📚 Namunaviy test topshiriqlari")
async def start_cmd(message: Message):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        await message.answer(
        "<b>⚡️Bilimni baholash agentligi tomonidan olinadigan imtihonlarning "
        "<u>majburiy va mutaxassislik</u> fanlaridan <u>namunaviy test topshiriqlari</u></b>\n\n"

        "<b>Majburiy bloklar:</b>\n"
        "👉 <a href='https://t.me/nodavlattalim/1393'>Ona tili</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1394'>Rus tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1395'>Qoraqalpoq tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1396'>Matematika</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1397'>Matematika (rus)</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1398'>O‘zbekiston tarixi</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1399'>O‘zbekiston tarixi (rus)</a>\n\n"

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
        "👉 <a href='https://t.me/nodavlattalim/1413'>Ona tili va adabiyoti (o‘zga tilli guruhlar uchun)</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1414'>Rus tili va adabiyoti (o‘zga tilli guruhlar uchun)</a>\n\n"

        "<b>© <a href='https://t.me/mandatjavobbot?start=share'>@mandatjavobbot</a> - oʻtish ballari va mandat natijalari</b>",
        parse_mode="HTML"
    )
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))


def split_text_by_words(text, max_len=45):
    words = text.split()
    result = ''
    line = ''

    for word in words:
        # Agar yangi so‘zni qo‘shganda line uzunligi max_len'dan oshmasa
        if len(line) + len(word) + 1 <= max_len:
            if line:
                line += ' ' + word
            else:
                line = word
        else:
            # Yangi qatorga o'tamiz
            result += line + '\n'
            line = word

    # Oxirgi qatorni ham qo‘shamiz
    if line:
        result += line

    return result

def create_card(univer, faculty, lang, edu, grand, kont, olmp, name):
    univer = split_text_by_words(univer)
    faculty = split_text_by_words(faculty)
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    template_path = CURRENT_DIR+"/edu.png"
    output_path = f"{CURRENT_DIR}/photos/{name}.jpg"
    try:
        # Rasmni ochish
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template image '{template_path}' not found!")

        image = Image.open(template_path)
        draw = ImageDraw.Draw(image)

        # Shriftlarni yuklash (o'zingizga mos fayllarni ko'rsating)
        try:
            title_font = ImageFont.truetype(CURRENT_DIR+"/Quicksand-Bold.otf", 100)
            main_font = ImageFont.truetype(CURRENT_DIR+"/Quicksand-Bold.otf", 90)
        except:
            # Agar shriftlar topilmasa, standart shriftlardan foydalanish
            title_font = ImageFont.load_default()
            main_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # 1. Universitet nomi (binoning ustidagi ochiq maydonga)
        draw.text((500, 200), str(univer), font=title_font, fill="black")

        # 2. Ta'lim yo'nalishi ("AJ" yozuvi o'rniga)
        # "AJ" ni o'chirish uchun uning joyiga oq rangda to'rtburchak chizamiz
        draw.text((300, 800), str(faculty), font=main_font, fill="black")

        # 3. Ta'lim tili (oldingi yozuv ostida)
        draw.text((550, 1600), str(lang), font=main_font, fill="white")

        # 4. Ta'lim shakli
        draw.text((1500, 1600), str(edu), font=main_font, fill="white")

        # 5. Mandat yili
        draw.text((2450, 1600), "2024", font=main_font, fill="white")

        # 6. Grantlar
        draw.text((650, 2120), str(grand), font=main_font, fill="black")

        # 7. Kontraktlar
        draw.text((1420, 2120), str(kont), font=main_font, fill="black")

        # 8. Olimpiada g'oliblari soni
        draw.text((2550, 2170), str(olmp), font=main_font, fill="black")

        # Natijani saqlash
        image.save(output_path)
        print(f"Karta muvaffaqiyatli yaratildi: {output_path}")
        return True

    except Exception as e:
        print(f"Xatolik yuz berdi: {str(e)}")
        return False
