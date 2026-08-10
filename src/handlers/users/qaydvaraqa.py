"""'🔍 Mandat tahlili' bo'limi.

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
import time

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
    Message, ReplyKeyboardMarkup,
)

from config import bot
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData
from src.utils import rate_limit
from src.utils.safe_send import answer_safe
from src.utils.qaydvaraqa import (
    MatchedChoice, parse_pdf, match_choices, format_report, QaydvaraqaParseError,
)
# "Raqobatchilarni tahlil qilish" -- '🎯 Balingizga mos yo'nalish'dagi bilan
# AYNAN BIR XIL mantiq (get_rank + get_stats + format_main/format_details),
# faqat 7 xonali ID qayta so'ralmaydi -- u qaydvaraqadan allaqachon olingan.
# `src/handlers/users/orin.py`ga (jonli, ishlab turgan handler) tegilmaydi --
# faqat uning ochiq (underscore'siz) `src/utils/orin.py` funksiyalari qayta
# ishlatiladi.
from src.utils import orin as orin_utils
from src.utils.mandat_parser import MandatBusy, MandatUnavailable

qv_router = Router()

QV_BTN = "🔍 Mandat tahlili"

# "Ortga" va "Bosh menu" turlicha ma'noga ega: "Ortga" — bir bosqich orqaga
# (masalan PDF qayta yuborish), "Bosh menu" — butunlay chiqish. PDF kutish
# bosqichida ORTGA qilinadigan bosqich yo'q (bu birinchi qadam), shu sabab
# o'sha yerda faqat "Bosh menu" ko'rsatiladi — ikkalasi bir xil natija
# berib, chalkashtirmasin (production'da aniqlangan bug).
_BACK_TEXTS = {"🔙 Ortga", "◀️ Ortga"}
_MAIN_MENU_TEXTS = {"🔙 Bosh menu"}

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


def _main_menu_only_keyboard() -> ReplyKeyboardMarkup:
    """PDF kutish bosqichida — bu birinchi qadam, "Ortga" qaytadigan
    boshqa bosqich yo'q, shu sabab faqat "Bosh menu" ko'rsatiladi."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Bosh menu")]], resize_keyboard=True,
    )


# abt_id -> (info, stats, olingan_vaqt). Qaydvaraqa qayta ishlanganda
# saytdan bir marta olingan (get_rank/get_stats) ma'lumot shu yerda
# saqlanadi — "Raqobatchilar tahlil qilinsinmi?" bosilganda ENDI QAYTA
# SO'ROV YUBORILMAYDI, mana shu keshdan o'qiladi. Redis emas: bu faqat
# BITTA suhbat sessiyasi davomida (bir necha daqiqa) kerak bo'ladigan
# vaqtinchalik ma'lumot — loyihaning "middleware/qo'shimcha infratuzilma
# yo'q" konvensiyasiga mos, xotiradagi oddiy dict yetarli.
_competitor_cache: dict[str, tuple[dict, dict | None, float]] = {}
_COMPETITOR_CACHE_TTL_S = 15 * 60


def _cache_competitor_data(abt_id: str, info: dict, stats: dict | None) -> None:
    _competitor_cache[abt_id] = (info, stats, time.monotonic())


def _get_cached_competitor_data(abt_id: str) -> tuple[dict, dict | None] | None:
    entry = _competitor_cache.get(abt_id)
    if not entry:
        return None
    info, stats, fetched_at = entry
    if time.monotonic() - fetched_at > _COMPETITOR_CACHE_TTL_S:
        return None
    return info, stats


async def _fetch_and_cache_competitor_data(abt_id: str) -> tuple[dict, dict | None] | None:
    """`get_rank` + `get_stats`ni chaqirib, natijani keshlaydi. Topilmasa
    (yoki xato bo'lsa) `None` — chaqiruvchi buni "avtomatik aniqlab
    bo'lmadi" deb talqin qiladi."""
    try:
        res = await orin_utils.get_rank(abt_id)
    except (MandatBusy, MandatUnavailable):
        return None
    except Exception:
        logging.exception("get_rank chaqiruvida xato (ID=%s)", abt_id)
        return None
    if "info" not in res:
        return None
    info = res["info"]
    stats = None
    try:
        stats = await orin_utils.get_stats(info["s4subject"], info["s5subject"], info["ed_lang_id"])
    except (MandatBusy, MandatUnavailable):
        pass
    except Exception:
        logging.exception("get_stats chaqiruvida xato (ID=%s)", abt_id)
    _cache_competitor_data(abt_id, info, stats)
    return info, stats


@qv_router.message(F.text == QV_BTN, F.chat.type == ChatType.PRIVATE)
async def qv_start(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)
    if not check_status:
        await message.answer("❗ Iltimos, quyidagi kanallarga a'zo bo'ling:",
                             reply_markup=await CheckData.channels_btn(channels))
        return
    await state.set_state(QVState.waiting_pdf)
    await message.answer(
        "🔍 <b>Mandat tahlili</b>\n\n"
        "Bilim va malakalarni baholash agentligi saytidan yuklab olgan "
        "<b>Abituriyent qayd varaqasi</b> PDF faylini shu yerga <b>hujjat "
        "(📎)</b> sifatida yuboring:",
        parse_mode="HTML",
        reply_markup=_main_menu_only_keyboard(),
    )


async def _process_new_pdf(message: Message, state: FSMContext) -> None:
    """PDF hujjatini qabul qilib tahlil qiladi. Ikki joydan chaqiriladi:
    birinchi marta yuborilganda VA foydalanuvchi ball kutish bosqichida
    (masalan noto'g'ri ball kiritganidan keyin) qaydvaraqani QAYTA
    yuborganda — ikkalasida ham bir xil, oxirgi yuborilgan PDF asosiy
    hisoblanadi (eski tanlovlar/shaxsiy ma'lumot almashtiriladi)."""
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

    personal = {
        "fio": parsed.fio, "abt_id": parsed.abt_id, "passport": parsed.passport,
        "jshshir": parsed.jshshir, "birth_date": parsed.birth_date, "gender": parsed.gender,
    }
    await state.update_data(matched=[vars(m) for m in matched], personal=personal)
    await answer_safe(message, _choices_preview(matched), parse_mode="HTML")

    # ⚡ ID qaydvaraqadan allaqachon ma'lum — mandat.uzbmb.uz saytidan
    # ballni AVTOMATIK olishga urinamiz, shunda foydalanuvchidan qo'lda
    # so'rash shart bo'lmaydi (u yerda "Mandat saytdagi o'rni" bo'limi
    # allaqachon aynan shu ID orqali ballni topa oladi). Natija bir yo'la
    # keshlanadi — "Raqobatchilar tahlil qilinsinmi?" bosilganda bu SAYTGA
    # QAYTA SO'ROV YUBORMAYDI, shu yerda olingan ma'lumotdan foydalanadi.
    ball = None
    if parsed.abt_id:
        status = await message.answer(
            "🔍 Siz haqingizda ma'lumot yig'ilmoqda (saytdan balingiz aniqlanmoqda)..."
        )
        result = await _fetch_and_cache_competitor_data(parsed.abt_id)
        await _safe_delete(status)
        if result:
            info, _stats = result
            raw_ball = info.get("ball")
            if raw_ball is not None and float(raw_ball) > 0:
                ball = float(raw_ball)

    if ball is not None:
        await message.answer(
            f"✅ Balingiz saytdan avtomatik aniqlandi: <b>{ball:g}</b>", parse_mode="HTML",
        )
        await _finalize_report(message, state, ball)
        return

    # Saytdan avtomatik aniqlab bo'lmadi (ID topilmadi, sayt band/ishlamayapti
    # yoki ball hali e'lon qilinmagan) — zaxira yo'l: qo'lda so'raymiz.
    await state.set_state(QVState.waiting_ball)
    await message.answer(
        "🎯 Endi to'plagan (umumiy) ballingizni kiriting:",
        reply_markup=await UserPanels.to_back(),
    )


async def _finalize_report(message: Message, state: FSMContext, ball: float) -> None:
    """Ball aniqlangach (avtomatik saytdan yoki foydalanuvchi qo'lda
    kiritgach) yakuniy hisobotni yaratib yuboradi va undan keyingi
    tugmalarni ko'rsatadi."""
    data = await state.get_data()
    matched = [MatchedChoice(**m) for m in data.get("matched", [])]
    personal = data.get("personal") or {}
    report = format_report(matched, ball, personal=personal)
    await state.clear()

    await answer_safe(message, report, parse_mode="HTML", reply_markup=await UserPanels.asos_manu())
    abt_id = personal.get("abt_id")
    await message.answer(
        "Quyidagilardan birini tanlashingiz mumkin 👇",
        reply_markup=_post_report_markup(abt_id),
    )


@qv_router.message(QVState.waiting_pdf, F.document, F.chat.type == ChatType.PRIVATE)
async def qv_pdf_received(message: Message, state: FSMContext):
    await _process_new_pdf(message, state)


@qv_router.message(QVState.waiting_pdf, F.chat.type == ChatType.PRIVATE)
async def qv_pdf_fallback(message: Message, state: FSMContext):
    if message.text in _BACK_TEXTS or message.text in _MAIN_MENU_TEXTS:
        await _to_main_menu(message, state)
        return
    if message.text in _ASOS_MENU_BTNS:
        await _to_main_menu(message, state)
        return
    await message.answer(
        "⚠️ Iltimos, qaydvaraqa PDF faylini <b>hujjat (📎)</b> sifatida yuboring.",
        parse_mode="HTML",
    )


# Ball kutilayotganda foydalanuvchi PDF'ni QAYTA yuborishi mumkin (masalan
# birinchi safar balini xato kiritib, "Ortga" bosmasdan to'g'ridan-to'g'ri
# qaytadan fayl tashlashi) — buni ball sifatida talqin qilish o'rniga,
# qaydvaraqani qaytadan tahlil qilish kerak. Shu handler matn-handlerdan
# OLDIN ro'yxatdan o'tgani uchun hujjatni ushlab qoladi.
@qv_router.message(QVState.waiting_ball, F.document, F.chat.type == ChatType.PRIVATE)
async def qv_pdf_resent_during_ball(message: Message, state: FSMContext):
    await _process_new_pdf(message, state)


@qv_router.message(QVState.waiting_ball, F.chat.type == ChatType.PRIVATE)
async def qv_ball_received(message: Message, state: FSMContext):
    if message.text in _MAIN_MENU_TEXTS:
        await _to_main_menu(message, state)
        return
    if message.text in _BACK_TEXTS:
        await state.set_state(QVState.waiting_pdf)
        await message.answer(
            "📋 Qaydvaraqa PDF faylini qayta yuboring:",
            reply_markup=_main_menu_only_keyboard(),
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

    await _finalize_report(message, state, ball)


def _post_report_markup(abt_id: str | None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🎓 Universitet tavsiyasi", callback_data="qv:reco")]]
    if abt_id:
        rows.append([InlineKeyboardButton(
            text="📊 Raqobatchilar tahlil qilinsinmi?", callback_data=f"qv:comp:{abt_id}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@qv_router.callback_query(F.data == "qv:reco")
async def qv_recommendation_placeholder(call: CallbackQuery):
    await call.answer("🔜 Bu bo'lim tez orada qo'shiladi.", show_alert=True)


def _competitor_markup(abt_id: str, detailed: bool) -> InlineKeyboardMarkup:
    toggle = (
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"qv:comp:{abt_id}")
        if detailed else
        InlineKeyboardButton(text="📊 Batafsil", callback_data=f"qv:compdet:{abt_id}")
    )
    return InlineKeyboardMarkup(inline_keyboard=[[toggle]])


async def _build_competitor_text(abt_id: str, detailed: bool) -> tuple[str, InlineKeyboardMarkup | None]:
    """`src/handlers/users/orin.py`dagi `_build()` bilan bir xil mantiq —
    'Mandat saytdagi o'rni' bo'limi allaqachon sinovdan o'tgan, shuni
    qayta ishlatamiz (nusxa ko'chirilgan, chunki asl funksiya o'sha
    handler faylida underscore bilan "shaxsiy" deb belgilangan).

    QAYDVARAQA PDF qayta ishlanganda bu ma'lumot ALLAQACHON bir marta
    olib, keshlangan bo'lishi mumkin (`_fetch_and_cache_competitor_data`) —
    shu holatda saytga QAYTA SO'ROV YUBORILMAYDI, kesh ishlatiladi."""
    cached = _get_cached_competitor_data(abt_id)
    if cached:
        info, stats = cached
        stale = False
    else:
        res = await orin_utils.get_rank(abt_id)
        if "info" not in res:
            return res["text"], None
        info = res["info"]
        stats = None
        try:
            stats = await orin_utils.get_stats(info["s4subject"], info["s5subject"], info["ed_lang_id"])
        except (MandatBusy, MandatUnavailable):
            pass
        except Exception:
            logging.exception("Raqobatchilar statistikasini olishda xatolik (ID=%s)", abt_id)
        _cache_competitor_data(abt_id, info, stats)
        stale = res.get("stale", False)

    if detailed:
        return orin_utils.format_details(info, stats), _competitor_markup(abt_id, True)
    return (orin_utils.format_main(info, stats, stale=stale),
            _competitor_markup(abt_id, False))


async def _show_competitors(call: CallbackQuery, abt_id: str, detailed: bool) -> None:
    if not rate_limit.allow(call.from_user.id):
        await call.answer("⏳ Juda tez-tez so'rov yubordingiz. Bir necha soniya kutib qayta urining.",
                          show_alert=True)
        return
    await call.answer()
    # Fon prefetch odatda buni allaqachon isitib qo'yadi, lekin isitilmagan
    # bo'lsa (masalan ID qaydvaraqadan topilmagan holatlar) haqiqiy tarmoq
    # so'rovi bir necha soniya cho'zilishi mumkin — foydalanuvchi kutish
    # o'rniga jarayon ketayotganini ko'rishi uchun darhol yangilanadi.
    try:
        await call.message.edit_text("🔍 Raqobatchilar ma'lumoti aniqlanmoqda, iltimos kuting...")
    except Exception:
        pass

    text, markup = None, None
    try:
        text, markup = await _build_competitor_text(abt_id, detailed)
    except MandatBusy:
        text = ("🚨 Hozir so'rovlar juda ko'p, navbat to'la.\n"
                "Iltimos, 1-2 daqiqadan so'ng qayta urinib ko'ring.")
    except MandatUnavailable:
        text = "🚨 mandat.uzbmb.uz sayti hozir javob bermayapti. Iltimos, birozdan so'ng qayta urinib ko'ring."
    except Exception:
        logging.exception("Raqobatchilar tahlilida ichki xatolik (ID=%s)", abt_id)
        text = "🚨 Ichki xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."

    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await call.message.answer(text, parse_mode="HTML", reply_markup=markup)


@qv_router.callback_query(F.data.startswith("qv:comp:"))
async def qv_competitors_main(call: CallbackQuery):
    abt_id = call.data.split(":", 2)[2]
    await _show_competitors(call, abt_id, detailed=False)


@qv_router.callback_query(F.data.startswith("qv:compdet:"))
async def qv_competitors_detailed(call: CallbackQuery):
    abt_id = call.data.split(":", 2)[2]
    await _show_competitors(call, abt_id, detailed=True)


async def _safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass
