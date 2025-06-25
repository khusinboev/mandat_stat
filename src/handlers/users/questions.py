import os

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, \
    InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult, BufferedInputFile, InputMediaPhoto, \
    ReplyKeyboardRemove

from config import cursor
from src.keyboards.buttons import UserPanels

ques_router = Router()

class FormQues(StatesGroup):
    ques1 = State()
    ques2 = State()
    ques3 = State()
    ques4 = State()
    ques5 = State()

@ques_router.message(F.text == "📚 Majburiydan testlar")
async def start_cmd1(message: Message):
    await message.answer("Botimizga xush kelibsiz, kerakli bo'limni tanlab va davom eting!", parse_mode="html", reply_markup=await UserPanels.ques_manu())


@ques_router.message(F.text == "📝 Matematika️")
async def start_cmd1(message: Message, state: FSMContext):
    try: await message.delete()
    except: pass
    basa = cursor.execute("SELECT photo, answer FROM math").fetchall()
    photo, answer = basa[0]
    current_dir = os.path.dirname(os.path.abspath(__file__))
    photo = os.path.join(current_dir, photo)
    variants = ["A", "B", "C", "D"]
    keyboard = []
    for i in range(0, 4, 2):  # 2 ta tugmali qatordan hosil qilish
        row = []
        for option in variants[i:i + 2]:
            suffix = "+" if option == answer else "-"
            row.append(
                InlineKeyboardButton(
                    text=option,
                    callback_data=f"answer:{option}:{suffix}:0:0"
                )
            )
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⛔ To‘xtatish", callback_data="stop")])
    btn = InlineKeyboardMarkup(inline_keyboard=keyboard)
    with open(photo, "rb") as image_file:
        photo = BufferedInputFile(image_file.read(), filename=os.path.basename(photo))
    await message.answer(text="Test boshlandi", reply_markup=ReplyKeyboardRemove())
    await message.answer_photo(photo=photo, caption="Quyidagilar orqali javob berasi!", parse_mode="html", reply_markup=btn)
    await state.set_state(FormQues.ques1)


# Callback tugmalarni ushlovchi
@ques_router.callback_query(F.data.startswith("answer:"), FormQues.ques1)
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    javob = callback.data.split(":")
    is_correct = javob[2]
    number = int(javob[3])+1
    ball = round(float(javob[4]), 1)
    if is_correct == "+":
        ball = float(ball) + 1.1
    if number < 10:

        basa = cursor.execute("SELECT photo, answer FROM math").fetchall()
        photo, answer = basa[number]
        current_dir = os.path.dirname(os.path.abspath(__file__))
        photo = os.path.join(current_dir, photo)
        variants = ["A", "B", "C", "D"]
        keyboard = []
        for i in range(0, 4, 2):  # 2 ta tugmali qatordan hosil qilish
            row = []
            for option in variants[i:i + 2]:
                suffix = "+" if option == answer else "-"
                row.append(
                    InlineKeyboardButton(
                        text=option,
                        callback_data=f"answer:{option}:{suffix}:{number}:{ball}"
                    )
                )
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(text="⛔ To‘xtatish",callback_data="stop")])
        btn = InlineKeyboardMarkup(inline_keyboard=keyboard)
        with open(photo, "rb") as image_file:
            photo = BufferedInputFile(image_file.read(), filename=os.path.basename(photo))

        await callback.message.edit_media(media=InputMediaPhoto(media=photo, caption="Quyidagilar orqali javob berasi!"))
        try:
            await callback.message.edit_reply_markup(reply_markup=btn)
        except: pass
        await callback.answer()  # loadingni yopish
    else:
        print(ball)
        await callback.message.answer(f"Siz {number} ta savoldan {int((ball+0.01)//1.1)} tasiga to'g'ri javob berib {ball} ball to'pladingiz!", reply_markup=await UserPanels.ques_manu())
        await callback.message.delete()
        await state.clear()


@ques_router.callback_query(F.data == "stop", FormQues.ques1)
async def stop_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Test to‘xtatildi. ✅")
    await callback.message.delete()