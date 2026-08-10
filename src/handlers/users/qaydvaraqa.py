"""'🔍 Mandat tahlili' bo'limi.

Hammasi REPLY-klaviatura asosida (inline/callback ISHLATILMAYDI) — har bir
bosqichda "🔙 Ortga" (bir qadam orqaga) + "🔙 Bosh menu" (butunlay chiqish)
tugmalari bor (birinchi qadam — PDF kutish — bundan mustasno, u yerda
"Ortga" qiladigan oldingi bosqich yo'q).

Oqim:
  tugma -> qaydvaraqa PDF so'raladi
  PDF kelgach -> tahlil qilinadi (matn qatlami sifatida, OCR/AI SHART EMAS —
    `src/utils/qaydvaraqa.py` docstringiga qarang), tanlovlar ko'rsatiladi,
    ID orqali ball saytdan AVTOMATIK olishga urinib ko'riladi (topilmasa —
    qo'lda so'raladi)
  ball aniqlangach -> yakuniy hisobot yuboriladi, keyin POST_REPORT menyusi:
    - "🎓 Universitet tavsiyasi" (bitta umumiy matn, admin tomonidan tayyorlangan)
    - "📊 Raqobatchilar tahlil qilinsinmi?" (huddi "Mandat saytdagi o'rni"
      bo'limidagi kabi, orin.py funksiyalari qayta ishlatiladi)
    - "🧮 Super-kontrakt kalkulyatori" (tanlov tanlanadi -> soha aniqlanadi
      -> ball farqi so'raladi -> tabaqalashtirilgan to'lov taxmini)

Bu bo'lim `asos_manu()` oilasiga tegishli (orin.py/yonalish.py bilan bir
xil uslub: rate_limit, CheckData.check_member, answer_safe, HTML format).
"""
import logging
import re
import time

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from config import bot, BOT_USERNAME
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData
from src.utils import rate_limit
from src.utils.safe_send import answer_safe
from src.utils.qaydvaraqa import (
    MatchedChoice, parse_pdf, match_choices, format_report, format_som,
    soha_info, super_kontrakt_amount_for_gap, QaydvaraqaParseError,
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
BTN_UNI_RECO = "🎓 Universitet tavsiyasi"
BTN_COMPETITORS = "📊 Raqobatchilar tahlil qilinsinmi?"
BTN_CALCULATOR = "🧮 Super-kontrakt kalkulyatori"

# Bitta umumiy matn, barcha foydalanuvchilarga bir xil ko'rsatiladi (admin
# tomonidan qo'lda tayyorlangan tavsiyalar ro'yxati).
UNIVERSITY_RECOMMENDATION_TEXT = '<b>1️⃣-TAVSIYA</b>\n🎓 Universitet nomi:<b> </b><a href="https://qabul.tdxu.uz/register"><b>Turkiy davlatlar xalqaro universiteti</b></a>\n📍 <b>Shahar:</b> Toshkent shahri \n📚 <b>Yo\'nalishlar soni:</b>  5 ta\n📖 <b>Asosiy yo\'nalishlar: </b>Davolash ishi, Kompyuter injiniringi)\n🕒 <b>Ta\'lim shakli:</b> kunduzgi\n💰 <b>Kontrakt narxi:</b> (<b>11 mln</b>dan <b>25 mln</b> so\'mgacha)\n🔗<b> Bog\'lanish uchun havola:</b> https://qabul.tdxu.uz/register\n<i>______________________</i><b>\n\n2️⃣-TAVSIYA</b>\n🎓<b> Universitet nomi: </b><a href="https://forms.amocrm.ru/rztwtdc"><b>Perfect universiteti</b></a>\n📍<b> Shahar: </b>Toshkent shahri\n📚 <b>Yo\'nalishlar soni:</b> Bakalavr: 16 ta, Ikkinchi mutaxasislik: 16 ta.\n📖<b> Asosiy yo\'nalishlar:</b> Jahon iqtisodiyoti va xalqaro iqtisodiy munosabatlar, Iqtisodiyot, Dasturiy injiniring.\n🕒 <b>Ta\'lim shakli:</b> (kunduzgi / kechki)\n💰 <b>Kontrakt narxi: </b>(<b>10 mln</b>dan boshlab)\n🔗 <b>Bog\'lanish havolasi uchun havola: </b>https://forms.amocrm.ru/rztwtdc\n<i>______________________</i><b>\n\n3️⃣-TAVSIYA\n</b>🎓 <b>Universitet nomi:</b> <a href="https://forms.amocrm.ru/rztwtwd"><b>Afrasiab university</b></a>\n📍<b> Shahar: </b>Toshkent shahri\n📚<b> Yo\'nalishlar soni: </b> Bakalavr: 18 ta, Magistratura: 7 ta, Ikkinchi mutahasislik: 4 ta.\n📖 <b>Asosiy yo\'nalishlar</b>: Yurisprudensiya, kiberxavsizlik injiniringi, sun`iy intellekt.\n🕒 <b>Ta\'lim shakli:</b> (kunduzgi)\n💰<b> Kontrakt narxi: </b>(<b>18 mln</b>dan boshlab)\n🔗 <b>Bog\'lanish havolasi uchun havola:</b> https://forms.amocrm.ru/rztwtwd<b>\n</b><i>______________________</i><b>\n\n4️⃣-TAVSIYA\n</b>🎓<b> Universitet nomi: </b><a href="https://forms.amocrm.ru/rztwtwl"><b>Xalqaro ijtimoiy innovatsiyalar universiteti</b></a>\n📍 <b>Shahar: </b>Toshkent shahri\n📚 <b>Yo\'nalishlar soni: </b>Bakalavr: 20 ta\n📖 <b>Asosiy yo\'nalishlar: </b> Yurisprudensiya, Arab tili, Sun`iy intellekt\n🕒 <b>Ta\'lim shakli:</b> (kunduzgi / kechki)\n💰 <b>Kontrakt narxi: </b>(<b>15 mln</b>dan boshlab)\n🔗<b> Bog\'lanish havolasi uchun havola: </b>https://forms.amocrm.ru/rztwtwl<b>\n</b><i>______________________</i><b>\n\n5️⃣-TAVSIYA</b>\n🎓 Universitet nomi:<b> </b><a href="https://forms.amocrm.ru/rzttdrl"><b>Sarbon universiteti</b></a>\n📍 <b>Shahar:</b> Toshkent shahri \n📚 <b>Yo\'nalishlar soni:</b>  34 ta\n📖 <b>Asosiy yo\'nalishlar: </b>Yurisprudensiya, davlat va jamiyat boshqaruvi, kosmetalogiya)\n🕒 <b>Ta\'lim shakli:</b> (kunduzgi / kechki / masofaviy)\n💰 <b>Kontrakt narxi:</b> (<b>14 mln</b>dan <b>25 mln</b> so\'mgacha)\n🔗<b> Bog\'lanish uchun havola:</b> https://forms.amocrm.ru/rzttdrl<i>\n______________________\n</i>\n6️⃣<b>-TAVSIYA</b>\n🎓<b> </b>Universitet nomi: <a href="https://forms.amocrm.ru/rzttdrd"><b>Toshkent Gumanitar Fanlar Universiteti </b></a><b>(TGFU)</b>\n📍 <b>Shahar: </b>Toshkent shahri, Samarqand shahri, Qoraqalpog\'iston Respublikasi \n📚 <b>Yo\'nalishlar soni: </b>bakalavr: 24 ta, Magistratura: 3 ta.\n📖 <b>Asosiy yo\'nalishlar</b>: (Xalqaro munosabatlar, Iqtisodiyot, Maktabgacha ta\'lim, Sport faoliyati): \n🕒 <b>Ta\'lim shakli:</b> (kunduzgi / kechki / part time)\n💰 <b>Kontrakt narxi: </b>(<b>8 mln</b>dan <b>17 mln</b> so\'mgacha)\n🔗<b> Bog\'lanish uchun havola:</b> https://forms.amocrm.ru/rzttdrd'

# "Ortga" va "Bosh menu" turlicha ma'noga ega: "Ortga" — bir bosqich orqaga,
# "Bosh menu" — butunlay chiqish. PDF kutish bosqichida ORTGA qilinadigan
# bosqich yo'q (bu birinchi qadam), shu sabab o'sha yerda faqat "Bosh menu"
# ko'rsatiladi — ikkalasi bir xil natija berib, chalkashtirmasin (production'da
# aniqlangan bug). Qolgan BARCHA bosqichlarda ikkalasi ham bor (`UserPanels.
# to_back()` yoki shu ikki tugmani o'zida saqlagan maxsus klaviatura orqali).
_BACK_TEXTS = {"🔙 Ortga", "◀️ Ortga"}
_MAIN_MENU_TEXTS = {"🔙 Bosh menu"}

# `asos_manu()`dagi barcha bo'lim tugmalari. Mid-flow'da (PDF, ball, yoki
# hisobotdan keyingi istalgan bosqichda) foydalanuvchi BOSHQA bo'limga
# o'tmoqchi bo'lsa, buni "noto'g'ri kiritish" deb emas, bo'lim almashtirish
# deb tushunish kerak — aks holda foydalanuvchi tugma bosib ham hech narsa
# bo'lmay qolib ketadi (boshqa loyihada aynan shu turdagi bug production'da
# aniqlangan va tuzatilgan — mantiqni shu yerda oldindan qo'llaymiz).
_ASOS_MENU_BTNS = {
    "📊 Mandat saytdagi o'rni", "🎯 Balingizga mos yo'nalish",
    "📊 O'tish ballari", "🎓 Perevod-2026", "😎 Test ishlash", QV_BTN,
}

# Real qaydvaraqa PDF ~60-70KB — ancha keng xavfsizlik chegarasi.
MAX_PDF_SIZE = 5 * 1024 * 1024

_CALC_CHOICE_RE = re.compile(r"^(\d+)-tanlov$")


class QVState(StatesGroup):
    waiting_pdf = State()
    waiting_ball = State()
    post_report = State()
    calc_choose_direction = State()
    calc_waiting_gap = State()


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


def _post_report_keyboard(abt_id: str | None) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=BTN_UNI_RECO)]]
    if abt_id:
        rows.append([KeyboardButton(text=BTN_COMPETITORS)])
    rows.append([KeyboardButton(text=BTN_CALCULATOR)])
    rows.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def _calculable_choices(matched: list[MatchedChoice]) -> list[MatchedChoice]:
    """Kalkulyator faqat BAZADA aniqlangan (nomi/ty_text tasdiqlangan)
    tanlovlar bilan ishlay oladi — soha aniqlash shu ikkalasiga bog'liq."""
    return [m for m in matched if m.matched and m.nomi]


def _calc_choice_keyboard(calculable: list[MatchedChoice]) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=f"{m.rank}-tanlov")] for m in calculable]
    rows.append([KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def _calc_choice_list_text(calculable: list[MatchedChoice]) -> str:
    lines = [
        "🧮 <b>Super-kontrakt kalkulyatori</b>\n",
        "Qaysi tanlov bo'yicha hisoblab ko'rmoqchisiz? Pastdagi tugmalardan "
        "birini bosing:\n",
    ]
    for m in calculable:
        lines.append(f"<b>{m.rank}-tanlov</b> — {m.un_text}\n    {m.nomi} ({m.ty_text})")
    return "\n".join(lines)


async def _return_to_post_report(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    abt_id = (data.get("personal") or {}).get("abt_id")
    await state.set_state(QVState.post_report)
    await message.answer(
        "Quyidagi bo'limlardan birini tanlang👇",
        reply_markup=_post_report_keyboard(abt_id),
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


# `src/keyboards/buttons.py`dagi `_bot_username()` bilan bir xil mantiq —
# BOT_USERNAME .envda berilmagan bo'lsa, tokendan (bot.get_me) avtomatik
# aniqlaydi va keshlaydi. Shu tufayli hisobot ostidagi havola ORIGINAL va
# KLON botda har doim TO'G'RI o'zining username'ini ko'rsatadi (boshqa
# bot havolasi bilan aralashib qolmaydi).
_resolved_bot_username: str | None = None


async def _own_bot_username() -> str:
    global _resolved_bot_username
    if BOT_USERNAME:
        return BOT_USERNAME
    if _resolved_bot_username is None:
        me = await bot.get_me()
        _resolved_bot_username = me.username
    return _resolved_bot_username


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
    kiritgach) yakuniy hisobotni yaratib yuboradi va POST_REPORT menyusiga
    o'tadi (state TOZALANMAYDI — keyingi bo'limlar (raqobatchilar,
    kalkulyator) xuddi shu `matched`/`personal` ma'lumotidan foydalanadi)."""
    data = await state.get_data()
    matched = [MatchedChoice(**m) for m in data.get("matched", [])]
    personal = data.get("personal") or {}
    bot_username = await _own_bot_username()
    report = format_report(matched, ball, personal=personal, bot_username=bot_username)

    await answer_safe(message, report, parse_mode="HTML")
    abt_id = personal.get("abt_id")
    await state.set_state(QVState.post_report)
    await message.answer(
        "Quyidagi bo'limlardan birini tanlang👇",
        reply_markup=_post_report_keyboard(abt_id),
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


# -- Hisobotdan keyingi menyu -------------------------------------------
@qv_router.message(QVState.post_report, F.chat.type == ChatType.PRIVATE)
async def qv_post_report_menu(message: Message, state: FSMContext):
    text = message.text or ""
    if text in _MAIN_MENU_TEXTS or text in _ASOS_MENU_BTNS:
        await _to_main_menu(message, state)
        return
    if text in _BACK_TEXTS:
        await state.set_state(QVState.waiting_pdf)
        await message.answer(
            "📋 Qaydvaraqa PDF faylini qayta yuboring:",
            reply_markup=_main_menu_only_keyboard(),
        )
        return

    data = await state.get_data()
    personal = data.get("personal") or {}
    abt_id = personal.get("abt_id")

    if text == BTN_UNI_RECO:
        await answer_safe(message, UNIVERSITY_RECOMMENDATION_TEXT, parse_mode="HTML")
        return
    if text == BTN_COMPETITORS and abt_id:
        await _show_competitors(message, abt_id)
        return
    if text == BTN_CALCULATOR:
        matched = [MatchedChoice(**m) for m in data.get("matched", [])]
        calculable = _calculable_choices(matched)
        if not calculable:
            await message.answer(
                "⚠️ Qaydvaraqangizdagi hech bir tanlov bazamizda aniqlanmagani "
                "uchun kalkulyator ishlay olmaydi."
            )
            return
        await state.set_state(QVState.calc_choose_direction)
        await answer_safe(
            message, _calc_choice_list_text(calculable), parse_mode="HTML",
            reply_markup=_calc_choice_keyboard(calculable),
        )
        return

    await message.answer(
        "Quyidagi bo'limlardan birini tanlang👇",
        reply_markup=_post_report_keyboard(abt_id),
    )


# -- Raqobatchilar tahlili -------------------------------------------------
async def _build_competitor_text(abt_id: str) -> str:
    """`src/handlers/users/orin.py`dagi `_build()` bilan bir xil mantiq —
    'Mandat saytdagi o'rni' bo'limi allaqachon sinovdan o'tgan, shuni
    qayta ishlatamiz (nusxa ko'chirilgan, chunki asl funksiya o'sha
    handler faylida underscore bilan "shaxsiy" deb belgilangan).

    QAYDVARAQA PDF qayta ishlanganda bu ma'lumot ALLAQACHON bir marta
    olib, keshlangan bo'lishi mumkin (`_fetch_and_cache_competitor_data`) —
    shu holatda saytga QAYTA SO'ROV YUBORILMAYDI, kesh ishlatiladi.

    Xulosa + batafsil statistika ALOHIDA tugma/bosqichsiz, BITTA xabarda
    birlashtirilib qaytariladi (foydalanuvchi so'roviga ko'ra)."""
    cached = _get_cached_competitor_data(abt_id)
    if cached:
        info, stats = cached
        stale = False
    else:
        res = await orin_utils.get_rank(abt_id)
        if "info" not in res:
            return res["text"]
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

    main_text = orin_utils.format_main(info, stats, stale=stale)
    details_text = orin_utils.format_details(info, stats)
    return main_text + "\n\n" + details_text


async def _show_competitors(message: Message, abt_id: str) -> None:
    """Natijani yuboradi va pastdagi (post_report) klaviaturani O'ZGARTIRMAYDI
    — na state, na reply_markup almashtiriladi, faqat xabar yuboriladi."""
    if not rate_limit.allow(message.from_user.id):
        await message.answer("⏳ Juda tez-tez so'rov yubordingiz. Bir necha soniya kutib qayta urining.")
        return
    status = await message.answer("🔍 Raqobatchilar ma'lumoti aniqlanmoqda, iltimos kuting...")

    try:
        text = await _build_competitor_text(abt_id)
    except MandatBusy:
        text = ("🚨 Hozir so'rovlar juda ko'p, navbat to'la.\n"
                "Iltimos, 1-2 daqiqadan so'ng qayta urinib ko'ring.")
    except MandatUnavailable:
        text = "🚨 mandat.uzbmb.uz sayti hozir javob bermayapti. Iltimos, birozdan so'ng qayta urinib ko'ring."
    except Exception:
        logging.exception("Raqobatchilar tahlilida ichki xatolik (ID=%s)", abt_id)
        text = "🚨 Ichki xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."

    await _safe_delete(status)
    await answer_safe(message, text, parse_mode="HTML")


# -- Super-kontrakt kalkulyatori --------------------------------------------
@qv_router.message(QVState.calc_choose_direction, F.chat.type == ChatType.PRIVATE)
async def qv_calc_choose_direction(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text in _MAIN_MENU_TEXTS or text in _ASOS_MENU_BTNS:
        await _to_main_menu(message, state)
        return
    if text in _BACK_TEXTS:
        await _return_to_post_report(message, state)
        return

    data = await state.get_data()
    matched = [MatchedChoice(**m) for m in data.get("matched", [])]
    calculable = _calculable_choices(matched)

    rank_match = _CALC_CHOICE_RE.match(text)
    chosen = None
    if rank_match:
        rank = int(rank_match.group(1))
        chosen = next((c for c in calculable if c.rank == rank), None)
    if not chosen:
        await message.answer(
            "Quyidagi tanlovlardan birini tugma orqali tanlang 👇",
            reply_markup=_calc_choice_keyboard(calculable),
        )
        return

    info = soha_info(chosen.nomi, chosen.ty_text)
    if info is None:
        await message.answer(
            f"⚠️ <b>{chosen.rank}-tanlov</b> ({chosen.nomi}) sohasi aniqlanmadi, "
            "shu sabab kalkulyator bu tanlov uchun ishlay olmaydi.\n\n"
            "Boshqa tanlovni tanlang yoki ortga qayting.",
            parse_mode="HTML",
            reply_markup=_calc_choice_keyboard(calculable),
        )
        return

    await state.update_data(calc_rank=chosen.rank)
    await state.set_state(QVState.calc_waiting_gap)
    ty_label = "kunduzgi" if info["is_kunduzgi"] else "sirtqi/kechki/masofaviy"
    await message.answer(
        f"📚 <b>{chosen.rank}-tanlov:</b> {chosen.nomi}\n"
        f"🏷 Soha: <b>{info['category_label']}</b>\n"
        f"💵 Bazaviy kontrakt narxi ({ty_label}): <b>{format_som(info['base_amount'])}</b>\n\n"
        "Necha ball yetishmayotganini kiriting (masalan: 2.5):",
        parse_mode="HTML",
        reply_markup=await UserPanels.to_back(),
    )


@qv_router.message(QVState.calc_waiting_gap, F.chat.type == ChatType.PRIVATE)
async def qv_calc_waiting_gap(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text in _MAIN_MENU_TEXTS or text in _ASOS_MENU_BTNS:
        await _to_main_menu(message, state)
        return

    data = await state.get_data()
    matched = [MatchedChoice(**m) for m in data.get("matched", [])]
    calculable = _calculable_choices(matched)

    if text in _BACK_TEXTS:
        await state.set_state(QVState.calc_choose_direction)
        await answer_safe(
            message, _calc_choice_list_text(calculable), parse_mode="HTML",
            reply_markup=_calc_choice_keyboard(calculable),
        )
        return

    raw = text.replace(",", ".")
    try:
        gap = float(raw)
    except ValueError:
        await message.answer("⚠️ Iltimos, ball farqini raqam sifatida kiriting (masalan: 2.5):")
        return
    if gap < 0:
        await message.answer("⚠️ Ball farqi manfiy bo'lishi mumkin emas. Qayta kiriting:")
        return

    rank = data.get("calc_rank")
    chosen = next((c for c in calculable if c.rank == rank), None)
    if not chosen:
        await state.set_state(QVState.calc_choose_direction)
        await answer_safe(
            message, _calc_choice_list_text(calculable), parse_mode="HTML",
            reply_markup=_calc_choice_keyboard(calculable),
        )
        return

    info = soha_info(chosen.nomi, chosen.ty_text)
    if info is None:
        result_text = "⚠️ Bu tanlov sohasi aniqlanmadi, hisoblab bo'lmadi."
    elif gap == 0:
        result_text = (
            "✅ Ball farqi 0 — tabaqalashtirilgan to'lov kerak emas, "
            "oddiy kontrakt narxi qo'llanadi."
        )
    elif gap > 4.0:
        result_text = (
            f"👉 Ball farqi ({gap:g}) 4 dan katta — bu holatda to'lov-kontrakt "
            "miqdorini OTM 2025-yildan beri mustaqil belgilaydi, biz hisoblay olmaymiz "
            "(<a href='https://t.me/nodavlattalim/4271'>manba</a>)."
        )
    else:
        calc = super_kontrakt_amount_for_gap(info["base_amount"], gap)
        result_text = (
            f"💰 <b>{chosen.rank}-tanlov</b> uchun taxminiy super-kontrakt:\n"
            f"Bazaviy narx: {format_som(info['base_amount'])}\n"
            f"Ko'paytiruvchi: ×{calc['multiplier']:g}\n"
            f"<b>Jami: {format_som(calc['amount'])}</b>\n\n"
            "<i>Bu — taxminiy hisob-kitob, aniq raqamni OTM'ning o'zidan tasdiqlang.</i>"
        )

    await answer_safe(message, result_text, parse_mode="HTML")
    await state.set_state(QVState.calc_choose_direction)
    await message.answer(
        "Boshqa tanlov uchun ham hisoblab ko'rishingiz mumkin, yoki ortga qayting 👇",
        reply_markup=_calc_choice_keyboard(calculable),
    )


async def _safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass
