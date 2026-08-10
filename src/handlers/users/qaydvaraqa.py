"""'📋 Qaydvaraqa bo'yicha tekshirish' bo'limi.

Oqim:
  tugma -> qaydvaraqa PDF so'raladi
  PDF kelgach -> tahlil qilinadi (matn qatlami sifatida, OCR/AI SHART EMAS —
    `src/utils/qaydvaraqa.py` docstringiga qarang), tanlovlar ko'rsatiladi,
    ball so'raladi
  ball kelgach -> har bir tanlov 2025-yil kontrakt balli bilan solishtirilib,
    yakuniy hisobot yuboriladi (+ milliy kontrakt/grant chegaralari bilan
    taqqoslash)

Bu bo'lim `asos_manu()` oilasiga tegishli (orin.py/yonalish.py bilan bir
xil uslub: rate_limit, CheckData.check_member, answer_safe, HTML format).
"""
import logging

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message

from config import bot
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData
from src.utils import rate_limit
from src.utils.safe_send import answer_safe
from src.utils.qaydvaraqa import (
    MatchedChoice, parse_pdf, match_choices, format_report, QaydvaraqaParseError,
)

qv_router = Router()

QV_BTN = "📋 Qaydvaraqa bo'yicha tekshirish"

# `UserPanels.to_back()` shu ikki tugmani beradi — ikkalasi ham bosh menyuga qaytaradi.
BACK_BUTTONS = {"🔙 Ortga", "🔙 Bosh menu", "◀️ Ortga"}

# `asos_manu()`dagi barcha bo'lim tugmalari. Mid-flow'da (PDF yoki ball
# kutilayotganda) foydalanuvchi BOSHQA bo'limga o'tmoqchi bo'lsa, buni
# "noto'g'ri fayl/ball" deb emas, bo'lim almashtirish deb tushunish kerak —
# aks holda foydalanuvchi tugma bosib ham hech narsa bo'lmay qolib ketadi
# (boshqa loyihada aynan shu turdagi bug production'da aniqlangan va
# tuzatilgan — mantiqni shu yerda oldindan qo'llaymiz).
_ASOS_MENU_BTNS = {
    "📊 Mandat saytdagi o'rni", "🎯 Balingizga mos yo'nalish",
    "📊 O'tish ballari", "🎓 Perevod-2026", "😎 Test ishlash", QV_BTN,
}

# Real qaydvaraqa PDF ~60-70KB — ancha keng xavfsizlik chegarasi.
MAX_PDF_SIZE = 5 * 1024 * 1024


class QVState(StatesGroup):
    waiting_pdf = State()
    waiting_ball = State()


def _choices_preview(matched: list[MatchedChoice]) -> str:
    lines = ["📋 <b>Qaydvaraqangizdan aniqlangan tanlovlar:</b>\n"]
    for m in matched:
        if m.matched:
            lines.append(
                f"{m.rank}. {m.un_text}\n"
                f"    {m.nomi} ({m.ty_text}, {m.lan_text})"
            )
        else:
            lines.append(f"{m.rank}. {m.university_raw} — ⚠️ {m.unmatch_reason}")
    return "\n".join(lines)


async def _to_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bosh menyu:", reply_markup=await UserPanels.asos_manu())


@qv_router.message(F.text == QV_BTN, F.chat.type == ChatType.PRIVATE)
async def qv_start(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)
    if not check_status:
        await message.answer("❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
                             reply_markup=await CheckData.channels_btn(channels))
        return
    await state.set_state(QVState.waiting_pdf)
    await message.answer(
        "📋 <b>Qaydvaraqa bo'yicha tekshirish</b>\n\n"
        "Bilim va malakalarni baholash agentligi saytidan yuklab olgan "
        "<b>Abituriyent qayd varaqasi</b> PDF faylini shu yerga <b>hujjat "
        "(📎)</b> sifatida yuboring:",
        parse_mode="HTML",
        reply_markup=await UserPanels.to_back(),
    )


@qv_router.message(QVState.waiting_pdf, F.document, F.chat.type == ChatType.PRIVATE)
async def qv_pdf_received(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not rate_limit.allow(user_id, interval=5.0):
        await message.answer("⏳ Juda tez-tez yubordingiz. Bir necha soniya kutib qayta urining.")
        return

    doc = message.document
    is_pdf = doc.mime_type == "application/pdf" or (doc.file_name or "").lower().endswith(".pdf")
    if not is_pdf:
        await message.answer("⚠️ Iltimos, PDF formatidagi qaydvaraqa faylini yuboring.")
        return
    if doc.file_size and doc.file_size > MAX_PDF_SIZE:
        await message.answer("⚠️ Fayl hajmi juda katta. Asl qaydvaraqa PDF faylini yuboring.")
        return

    loading = await message.answer("🔍 Qaydvaraqa tahlil qilinmoqda...")
    matched: list[MatchedChoice]
    try:
        buf = await bot.download(doc)
        data = buf.read() if buf else b""
        parsed = parse_pdf(data)
        matched = match_choices(parsed)
    except QaydvaraqaParseError as e:
        await _safe_delete(loading)
        await message.answer(
            f"⚠️ Faylni tahlil qilib bo'lmadi: {e}\n\n"
            "Iltimos, rasmiy \"Abituriyent qayd varaqasi\" PDF faylini yuboring."
        )
        return
    except Exception:
        logging.exception("Qaydvaraqa tahlilida kutilmagan xato (user=%s)", user_id)
        await _safe_delete(loading)
        await message.answer("🚨 Ichki xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.")
        return

    await _safe_delete(loading)

    await state.update_data(matched=[vars(m) for m in matched])
    await state.set_state(QVState.waiting_ball)
    await answer_safe(message, _choices_preview(matched), parse_mode="HTML")
    await message.answer(
        "🎯 Endi to'plagan (umumiy) ballingizni kiriting:",
        reply_markup=await UserPanels.to_back(),
    )


@qv_router.message(QVState.waiting_pdf, F.chat.type == ChatType.PRIVATE)
async def qv_pdf_fallback(message: Message, state: FSMContext):
    if message.text in BACK_BUTTONS:
        await _to_main_menu(message, state)
        return
    if message.text in _ASOS_MENU_BTNS:
        await _to_main_menu(message, state)
        return
    await message.answer(
        "⚠️ Iltimos, qaydvaraqa PDF faylini <b>hujjat (📎)</b> sifatida yuboring.",
        parse_mode="HTML",
    )


@qv_router.message(QVState.waiting_ball, F.chat.type == ChatType.PRIVATE)
async def qv_ball_received(message: Message, state: FSMContext):
    if message.text in BACK_BUTTONS:
        await state.set_state(QVState.waiting_pdf)
        await message.answer(
            "📋 Qaydvaraqa PDF faylini qayta yuboring:",
            reply_markup=await UserPanels.to_back(),
        )
        return
    if message.text in _ASOS_MENU_BTNS:
        await _to_main_menu(message, state)
        return

    raw = (message.text or "").strip().replace(",", ".")
    try:
        ball = float(raw)
    except ValueError:
        await message.answer("⚠️ Iltimos, ballni raqam sifatida kiriting (masalan: 145.6):")
        return
    if not (0 <= ball <= 250):
        await message.answer(
            "⚠️ Ball noto'g'ri kiritildi (0 dan 250 gacha bo'lishi kerak). Qayta kiriting:"
        )
        return

    data = await state.get_data()
    matched = [MatchedChoice(**m) for m in data.get("matched", [])]
    report = format_report(matched, ball)
    await state.clear()
    await answer_safe(message, report, parse_mode="HTML", reply_markup=await UserPanels.asos_manu())


async def _safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass
