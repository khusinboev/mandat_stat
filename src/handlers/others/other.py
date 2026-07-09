from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.keyboards.buttons import UserPanels

other_router = Router()

@other_router.message()
async def chosen_lang(message: Message, state: FSMContext):
    try:
        await message.delete()
        await state.clear()
    except: pass
    await message.answer(f"`{message.photo[-1].file_id}`<b>Quyidagi menulardan birini tanlang 👇</b>", parse_mode="html",
                         reply_markup=await UserPanels.asos_manu())


# Shu yerda keyingi bosqichni (fac5 va hokazo) davom ettirishingiz mumkin.
@other_router.callback_query()
async def handle_stale_callback(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    try:
        await callback.answer()
    except Exception:
        pass