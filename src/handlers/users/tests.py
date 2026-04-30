import asyncio
import os
import random
from pathlib import Path
from urllib.parse import quote

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    ReplyKeyboardRemove,
)

from config import MSG_LIMIT, REQUIRED_REFERRALS, bot, cursor, sql
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData
from src.utils.quiz_helpers import format_results, insert_result


test_router = Router()
ROOT_DIR = Path(__file__).resolve().parents[3]
SUBJECT_NAME_TO_CODE = {
    "Ona tili": "literature",
    "Matematika": "math",
    "O'zbekiston tarixi": "history",
}
SUBJECT_MENU_BTNS = frozenset({
    "📝 Matematika",
    "📚 Ona tili",
    "📚 Tarix",
    "🧮 Hammasidan",
    "📊 Natijalarim",
})


class FormQues(StatesGroup):
    ques_list = State()
    current_index = State()
    score = State()
    end_time = State()
    subject_stats = State()
    start_time = State()


def _limit_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    share_url = f"https://t.me/share/url?url={quote(ref_link, safe='')}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=share_url)],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_referral")],
    ])


async def _is_limited(user_id: int) -> tuple[bool, int]:
    sql.execute(
        "SELECT msg_count, referral_count FROM public.accounts WHERE user_id=%s LIMIT 1",
        (user_id,),
    )
    row = sql.fetchone()
    if not row:
        return False, 0

    msg_count, referral_count = row
    limited = msg_count > MSG_LIMIT and referral_count < REQUIRED_REFERRALS
    return limited, referral_count


def _active_status_sql(table_name: str) -> str:
    return (
        f"SELECT DISTINCT varyant FROM public.{table_name} "
        "WHERE COALESCE(status::text, '') ILIKE 'true'"
    )


def _question_sql(table_name: str) -> str:
    return (
        f"SELECT file_id, answer, photo FROM public.{table_name} "
        "WHERE varyant=%s AND COALESCE(status::text, '') ILIKE 'true'"
    )


def _quiz_start_kb(subject_code: str, subject_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Boshlash", callback_data=f"test_confirm_start:{subject_code}:{subject_name}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="test_back_to_menu")],
    ])


async def _resolve_photo_source(file_id: str | None, photo_path: str | None) -> str | FSInputFile | None:
    if file_id:
        return file_id

    if not photo_path:
        return None

    candidates = [
        ROOT_DIR / photo_path,
        ROOT_DIR / "ques-bot" / photo_path,
        ROOT_DIR / "ques-bot" / "src" / "handlers" / "users" / photo_path,
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return FSInputFile(path)
    return None


async def _send_or_edit_question(
    message_or_callback: Message | CallbackQuery,
    photo_source: str | FSInputFile,
    caption: str,
    reply_markup: InlineKeyboardMarkup,
) -> tuple[bool, str | None]:
    if isinstance(message_or_callback, Message):
        sent = await message_or_callback.answer_photo(
            photo=photo_source,
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
        if isinstance(photo_source, FSInputFile):
            return True, sent.photo[-1].file_id
        return True, None

    try:
        if isinstance(photo_source, str):
            media = InputMediaPhoto(media=photo_source, caption=caption, parse_mode="HTML")
            await message_or_callback.message.edit_media(media=media, reply_markup=reply_markup)
            await message_or_callback.answer()
            return True, None

        sent = await message_or_callback.message.answer_photo(
            photo=photo_source,
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
        try:
            await message_or_callback.message.delete()
        except Exception:
            pass
        await message_or_callback.answer()
        return True, sent.photo[-1].file_id
    except Exception:
        return False, None


@test_router.message(F.text == "📝 Matematika")
async def choose_math(message: Message):
    await message.answer(
        "📝 Matematika fanidan testni boshlashni xohlaysizmi?",
        reply_markup=_quiz_start_kb("math", "Matematika"),
    )


@test_router.message(F.text == "📚 Ona tili")
async def choose_literature(message: Message):
    await message.answer(
        "📚 Ona tili fanidan testni boshlashni xohlaysizmi?",
        reply_markup=_quiz_start_kb("literature", "Ona tili"),
    )


@test_router.message(F.text == "📚 Tarix")
async def choose_history(message: Message):
    await message.answer(
        "📚 O'zbekiston tarixi fanidan testni boshlashni xohlaysizmi?",
        reply_markup=_quiz_start_kb("history", "O'zbekiston tarixi"),
    )


@test_router.message(F.text == "🧮 Hammasidan")
async def choose_all_subjects(message: Message):
    await message.answer(
        "🧮 3 ta fandan umumiy testni boshlashni xohlaysizmi?",
        reply_markup=_quiz_start_kb("all", "all"),
    )


@test_router.message(F.text == "📊 Natijalarim")
async def my_results_handler(message: Message):
    await message.answer(format_results(message.from_user.id), parse_mode="html")


@test_router.callback_query(F.data == "test_back_to_menu")
async def back_to_quiz_menu(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "📚 Test bo'limiga qaytdingiz, kerakli fanni tanlang.",
        reply_markup=await UserPanels.quiz_menu(),
    )
    await callback.answer()


@test_router.callback_query(F.data.startswith("test_confirm_start:"))
async def confirm_start_test(callback: CallbackQuery, state: FSMContext):
    limited, referral_count = await _is_limited(callback.from_user.id)
    if limited:
        remaining = REQUIRED_REFERRALS - referral_count
        me = await bot.get_me()
        ref_link = f"https://t.me/{me.username}?start=ref_{callback.from_user.id}"
        await callback.message.answer(
            f"⛔ <b>Siz {MSG_LIMIT} ta xabar limitini tugatdingiz!</b>\n\n"
            f"Davom etish uchun <b>{REQUIRED_REFERRALS}</b> ta do'st taklif qiling.\n"
            f"👥 Taklif qilganlar: <b>{referral_count}/{REQUIRED_REFERRALS}</b>\n"
            f"➡️ Yana <b>{remaining}</b> ta kishi kerak.",
            parse_mode="html",
            reply_markup=_limit_keyboard(ref_link),
        )
        await callback.answer()
        return

    check_status, channels = await CheckData.check_member(bot, callback.from_user.id)
    if not check_status:
        await callback.message.delete()
        await callback.message.answer(
            "❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
            reply_markup=await CheckData.channels_btn(channels),
        )
        await callback.answer()
        return

    _, subject_code, subject_name = callback.data.split(":", 2)
    if subject_code == "all":
        await start_all_subjects(callback.message, state)
    else:
        await start_subject(callback.message, state, subject_code, subject_name, duration=20 * 60)

    await callback.answer()


async def start_all_subjects(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass

    subjects = [
        ("literature", "Ona tili"),
        ("math", "Matematika"),
        ("history", "O'zbekiston tarixi"),
    ]

    selected_all = []
    stats = {}

    for table_name, subject_name in subjects:
        cursor.execute(_active_status_sql(table_name))
        variants = cursor.fetchall()
        if not variants:
            await message.answer(f"{subject_name} fanida variant topilmadi.")
            return

        selected_variant = random.choice([v[0] for v in variants])
        cursor.execute(_question_sql(table_name), (selected_variant,))
        questions = cursor.fetchall()
        if len(questions) < 10:
            await message.answer(f"{subject_name} fanida {selected_variant}-variantdan test yetarli emas.")
            return

        sample = random.sample(questions, 10)
        selected_all.extend([(q[0], q[1], subject_name, q[2]) for q in sample])
        stats[subject_name] = {"correct": 0, "score": 0.0}

    now = asyncio.get_event_loop().time()
    await state.set_data(
        {
            "ques_list": selected_all,
            "current_index": 0,
            "score": 0.0,
            "total_questions": len(selected_all),
            "end_time": now + 60 * 60,
            "subject_stats": stats,
            "start_time": now,
        }
    )

    await message.answer("📚 3 ta fandan umumiy test boshlandi", reply_markup=ReplyKeyboardRemove())
    await show_question(message, selected_all[0], 0, 0.0, state)


async def start_subject(message: Message, state: FSMContext, table_name: str, subject_name: str, duration: int):
    try:
        await message.delete()
    except Exception:
        pass

    cursor.execute(_active_status_sql(table_name))
    variants = cursor.fetchall()
    if not variants:
        await message.answer("Fan uchun variant topilmadi.")
        return

    selected_variant = random.choice([v[0] for v in variants])
    cursor.execute(_question_sql(table_name), (selected_variant,))
    questions = cursor.fetchall()
    if len(questions) < 10:
        await message.answer("Yetarlicha test mavjud emas.")
        return

    selected = [(q[0], q[1], subject_name, q[2]) for q in random.sample(questions, 10)]
    now = asyncio.get_event_loop().time()

    await state.set_data(
        {
            "ques_list": selected,
            "current_index": 0,
            "score": 0.0,
            "total_questions": len(selected),
            "end_time": now + duration,
            "subject_stats": {subject_name: {"correct": 0, "score": 0.0}},
            "start_time": now,
        }
    )

    await message.answer(f"Test boshlandi ({selected_variant}-variant)", reply_markup=ReplyKeyboardRemove())
    await show_question(message, selected[0], 0, 0.0, state)


async def show_question(message_or_callback: Message | CallbackQuery, question, index: int, score: float, state: FSMContext):
    data = await state.get_data()
    total_questions = data.get("total_questions", 10)
    end_time = data.get("end_time")

    now = asyncio.get_event_loop().time()
    if end_time is None or now > end_time:
        await force_finish(message_or_callback, state)
        return

    time_left = int(end_time - now)
    time_elapsed = int(now - data.get("start_time", now))

    photo, correct_answer, subject_name, photo_path = question

    variants = ["A", "B", "C", "D"]
    keyboard = []
    for i in range(0, 4, 2):
        row = []
        for option in variants[i:i + 2]:
            suffix = "+" if option.lower() == str(correct_answer).lower() else "-"
            row.append(
                InlineKeyboardButton(
                    text=option,
                    callback_data=f"test_answer:{option}:{suffix}:{index}:{score}:{subject_name}",
                )
            )
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⛔ To'xtatish", callback_data="test_stop")])
    btn = InlineKeyboardMarkup(inline_keyboard=keyboard)

    caption = (
        f"📖 FAN: <b>{subject_name}</b>\n"
        f"🧮 <b>Savol: {index + 1} / {total_questions}</b>\n"
        f"⏱ O'tgan: {time_elapsed // 60} daq. {time_elapsed % 60} son. | "
        f"Qolgan: {time_left // 60} daq. {time_left % 60} son."
    )

    photo_source = await _resolve_photo_source(photo, photo_path)
    if photo_source is None:
        await _skip_broken_question(message_or_callback, state, index, score, subject_name)
        return

    sent_ok, uploaded_file_id = await _send_or_edit_question(message_or_callback, photo_source, caption, btn)
    if not sent_ok:
        await _skip_broken_question(message_or_callback, state, index, score, subject_name)
        return

    if uploaded_file_id and photo_path:
        cursor.execute(
            f"UPDATE public.{SUBJECT_NAME_TO_CODE[subject_name]} SET file_id=%s WHERE photo=%s",
            (uploaded_file_id, photo_path),
        )


async def _skip_broken_question(message_or_callback: Message | CallbackQuery, state: FSMContext, index: int, score: float, subject_name: str):
    state_data = await state.get_data()
    questions = state_data.get("ques_list", [])
    next_index = index + 1

    if next_index < len(questions):
        await state.update_data(current_index=next_index, score=score)
        await show_question(message_or_callback, questions[next_index], next_index, score, state)
    else:
        await force_finish(message_or_callback, state)


async def force_finish(message_or_callback: Message | CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0.0)
    stats = data.get("subject_stats", {})
    elapsed = int(asyncio.get_event_loop().time() - data.get("start_time", 0))

    result = "⏱ Vaqt tugadi!\n"
    for subject, info in stats.items():
        result += f"\n📘 {subject}: {info['correct']} ta to'g'ri | {round(info['score'], 1)} ball"
    result += f"\n\nUmumiy: {int((score + 0.01) // 1.1)} ta to'g'ri | {round(score, 1)} ball"
    result += f"\n⏳ {elapsed // 60} daqiqa {elapsed % 60} soniyada yakunlandi"

    target = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
    await target.answer(result, reply_markup=await UserPanels.quiz_menu())
    await state.clear()


@test_router.callback_query(F.data.startswith("test_answer:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    is_correct = parts[2]
    index = int(parts[3])
    score = float(parts[4])
    subject = parts[5]

    state_data = await state.get_data()
    end_time = state_data.get("end_time")
    if end_time is None:
        await callback.message.answer("Eski so'rov bo'lishi mumkin.", reply_markup=await UserPanels.quiz_menu())
        await callback.answer()
        return

    if asyncio.get_event_loop().time() > end_time:
        await force_finish(callback, state)
        await callback.answer()
        return

    if is_correct == "+":
        score += 1.1
        state_data["subject_stats"][subject]["correct"] += 1
        state_data["subject_stats"][subject]["score"] += 1.1

    questions = state_data.get("ques_list", [])
    next_index = index + 1

    if next_index < len(questions):
        await state.update_data(
            current_index=next_index,
            score=score,
            subject_stats=state_data["subject_stats"],
        )
        await show_question(callback, questions[next_index], next_index, score, state)
        return

    elapsed = int(asyncio.get_event_loop().time() - state_data.get("start_time", 0))
    result = "✅ Test yakunlandi!\n"

    for subject_name, info in state_data["subject_stats"].items():
        result += f"\n📘 {subject_name}: {info['correct']} ta to'g'ri | {round(info['score'], 1)} ball"
        insert_result(
            user_id=callback.from_user.id,
            subject=SUBJECT_NAME_TO_CODE[subject_name],
            number=info["correct"],
        )

    result += f"\n\nUmumiy: {int((score + 0.01) // 1.1)} ta to'g'ri | {round(score, 1)} ball"
    result += f"\n⏳ {elapsed // 60} daqiqa {elapsed % 60} soniyada yakunlandi"

    await callback.message.answer(result, reply_markup=await UserPanels.quiz_menu())
    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.clear()
    await callback.answer()


@test_router.callback_query(F.data == "test_stop")
async def stop_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Test bo'limiga qaytdingiz, kerakli fanni tanlang.",
        reply_markup=await UserPanels.quiz_menu(),
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()
