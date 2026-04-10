import logging

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup

from config import ADMIN_ID, bot, db_connection
from src.keyboards.buttons import AdminPanel
from src.keyboards.keyboard_func import PanelFunc

logger = logging.getLogger(__name__)
add_router = Router()


class AdminAdd(StatesGroup):
    admin_add    = State()
    admin_delete = State()


markup = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]],
)


@add_router.message(F.text == "🔧Adminlar👨‍💻", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def adminlar_menu(message: Message):
    await message.answer("Tanlang", reply_markup=await AdminPanel.admin_add())


@add_router.message(F.text == "🔙Orqaga qaytish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Orqaga qaytildi", reply_markup=await AdminPanel.admin_add())


@add_router.message(F.text == "➕Admin qo'shish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def admin_qoshish(message: Message, state: FSMContext):
    await bot.send_message(
        message.chat.id,
        text="Qo'shish kerak bo'lgan admin ID sini yuboring. ID ni @ShowJsonBot orqali bilishingiz mumkin.",
        reply_markup=markup,
        parse_mode="html",
    )
    await state.set_state(AdminAdd.admin_add)


@add_router.message(AdminAdd.admin_add, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def admin_qoshish_2(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.isdigit():
        await message.answer(
            "Admin ID xato kiritildi. ID faqat sonlardan iborat bo'lishi kerak.",
            reply_markup=markup,
        )
        return

    admin_id = int(text)
    with db_connection() as (conn, cur):
        cur.execute("SELECT 1 FROM public.admins WHERE user_id = %s", (admin_id,))
        exists = cur.fetchone()

    if exists:
        await message.answer("Bu admin avvaldan bor", reply_markup=await AdminPanel.admin_add())
    else:
        await PanelFunc.admin_add(admin_id)
        await message.answer("Admin qo'shildi 🎉", reply_markup=await AdminPanel.admin_add())

    await state.clear()


@add_router.message(F.text == "❌Admin o'chirish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def admin_ochirish(message: Message, state: FSMContext):
    await message.answer("O'chiriladigan adminning ID sini yuboring.", reply_markup=markup)
    await state.set_state(AdminAdd.admin_delete)


@add_router.message(AdminAdd.admin_delete, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def admin_ochirish_2(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.isdigit():
        await message.answer(
            "Admin ID xato kiritildi. ID faqat sonlardan iborat bo'lishi kerak.",
            reply_markup=markup,
        )
        return

    admin_id = int(text)
    with db_connection() as (conn, cur):
        cur.execute("SELECT 1 FROM public.admins WHERE user_id = %s", (admin_id,))
        exists = cur.fetchone()

    if not exists:
        await message.answer("Bunday admin yo'q", reply_markup=await AdminPanel.admin_add())
    else:
        await PanelFunc.admin_delete(admin_id)
        await message.answer("Admin muvaffaqiyatli o'chirildi", reply_markup=await AdminPanel.admin_add())

    await state.clear()


@add_router.message(F.text == "📋 Adminlar ro'yxati", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def adminlar_royxati(message: Message):
    result = await PanelFunc.admin_list()
    if len(result) > 3:
        await message.answer(result, parse_mode="html")
    else:
        await message.answer("Hozircha adminlar yo'q")
