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
