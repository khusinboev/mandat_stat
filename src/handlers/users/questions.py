import os
import random
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile, InputMediaPhoto, ReplyKeyboardRemove

from config import cursor
from src.keyboards.buttons import UserPanels

ques_router = Router()

class FormQues(StatesGroup):
    ques_list = State()
    current_index = State()
    score = State()

@ques_router.message(F.text == "📚 Majburiydan testlar")
async def start_cmd1(message: Message):
    await message.answer(
        "Majburiy bloklardan test ishlash bo'limiga xush kelibsiz, kerakli fanni tanlang va davom eting!",
        parse_mode="html",
        reply_markup=await UserPanels.ques_manu()
    )

@ques_router.message(F.text == "📝 Matematika️")
async def start_math(message: Message, state: FSMContext):
    await start_subject(message, state, "math", "Matematika")

@ques_router.message(F.text == "📚 Ona tili")
async def start_literature(message: Message, state: FSMContext):
    await start_subject(message, state, "literature", "Ona tili")

@ques_router.message(F.text == "📚 Tarix")
async def start_history(message: Message, state: FSMContext):
    await start_subject(message, state, "history", "Tarix")

@ques_router.message(F.text == "🧮 Hamasidan")
async def start_all_subjects(message: Message, state: FSMContext):
    try:
        await message.delete()
    except:
        pass

    subjects = [("math", "Matematika"), ("literature", "Ona tili"), ("history", "Tarix")]
    selected_all = []

    for table_name, subject_name in subjects:
        cursor.execute(f"SELECT photo, answer FROM {table_name}")
        questions = cursor.fetchall()
        if len(questions) < 10:
            await message.answer(f"{subject_name} fani uchun yetarlicha test mavjud emas.")
            return
        selected_all.extend([(q[0], q[1], subject_name) for q in random.sample(questions, 10)])

    await state.set_data({
        "ques_list": selected_all,
        "current_index": 0,
        "score": 0.0,
        "total_questions": len(selected_all)
    })

    await message.answer("📚 3 ta fandan umumiy test boshlandi", reply_markup=ReplyKeyboardRemove())
    await show_question(message, selected_all[0], 0, 0.0, state)


async def start_subject(message: Message, state: FSMContext, table_name: str, subject_name: str):
    try:
        await message.delete()
    except:
        pass

    cursor.execute(f"SELECT photo, answer FROM {table_name}")
    all_questions = cursor.fetchall()
    if len(all_questions) < 10:
        await message.answer("Yetarlicha test mavjud emas.")
        return

    selected = [(q[0], q[1], subject_name) for q in random.sample(all_questions, 10)]

    await state.set_data({
        "ques_list": selected,
        "current_index": 0,
        "score": 0.0,
        "total_questions": len(selected)
    })

    await message.answer("Test boshlandi", reply_markup=ReplyKeyboardRemove())
    await show_question(message, selected[0], 0, 0.0, state)


async def show_question(message_or_callback, question, index, score, state: FSMContext):
    data = await state.get_data()
    total_questions = data.get("total_questions", 10)

    photo_path, correct_answer, *subject = question
    subject_name = subject[0] if subject else "Fan"

    current_dir = os.path.dirname(os.path.abspath(__file__))
    photo_path = os.path.join(current_dir, photo_path)

    variants = ["A", "B", "C", "D"]
    keyboard = []
    for i in range(0, 4, 2):
        row = []
        for option in variants[i:i + 2]:
            suffix = "+" if option == correct_answer else "-"
            row.append(
                InlineKeyboardButton(
                    text=option,
                    callback_data=f"answer:{option}:{suffix}:{index}:{score}"
                )
            )
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⛔ To‘xtatish", callback_data="stop-quest")])
    btn = InlineKeyboardMarkup(inline_keyboard=keyboard)

    with open(photo_path, "rb") as image_file:
        photo = BufferedInputFile(image_file.read(), filename=os.path.basename(photo_path))

    caption = (
        f"📖 FAN: <b>{subject_name}</b>\n"
        f"🧮 <b>Savol: {index + 1} / {total_questions}</b>\n"
        "Quyidagilar orqali javob berasi!"
    )

    if isinstance(message_or_callback, Message):
        await message_or_callback.answer_photo(photo=photo, caption=caption, reply_markup=btn, parse_mode="HTML")
    else:
        try:
            await message_or_callback.message.edit_media(
                InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"))
            await message_or_callback.message.edit_reply_markup(reply_markup=btn)
        except:
            pass
        await message_or_callback.answer()


@ques_router.callback_query(F.data.startswith("answer:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    javob = callback.data.split(":")
    is_correct = javob[2]
    index = int(javob[3])
    score = float(javob[4])

    if is_correct == "+":
        score += 1.1

    data = await state.get_data()
    questions = data.get("ques_list")
    next_index = index + 1

    if next_index < len(questions):
        await state.update_data(current_index=next_index, score=score)
        await show_question(callback, questions[next_index], next_index, score, state)
    else:
        await callback.message.answer(
            f"Siz {len(questions)} ta savoldan {int((score + 0.01) // 1.1)} tasiga to'g'ri javob berib {round(score,1)} ball to‘pladingiz!",
            reply_markup=await UserPanels.ques_manu())
        await callback.message.delete()
        await state.clear()


@ques_router.callback_query(F.data == "stop-quest")
async def stop_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Majburiy bloklardan test ishlash bo'limiga xush kelibsiz, kerakli fanni tanlang va davom eting!",
        parse_mode="html",
        reply_markup=await UserPanels.ques_manu()
    )
    await callback.message.delete()
