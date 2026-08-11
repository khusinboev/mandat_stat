"""Abituriyent qaydvaraqasi (PDF) tahlili va 2025-yil kontrakt ballari bilan
solishtirish.

PDF matn qatlami sifatida saqlangan (rasm/skaner EMAS) — pdfplumber bilan
to'g'ridan-to'g'ri o'qiladi, OCR yoki AI/Vision shart emas. Bu 6 ta real
namunada tekshirilgan (100% mos, `.claude` ishchi eslatmalariga qarang).

Muhim: bazada FAQAT kontrakt balli bor (`mandat.gr_b` barcha qatorlarda 0,
tasdiqlangan) — grant taqqoslash faqat MILLIY minimal chegara (taxminiy)
darajasida, aniq yo'nalish darajasida emas.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber

from config import cursor

# -- Normalizatsiya ----------------------------------------------------------
# O'zbek matnida apostrof bir necha xil belgi bilan yoziladi (o', oʻ, o‘, o`)
# — sertifikat va baza turlicha yozishi mumkin, shu sabab qidiruvdan oldin
# hammasi bitta shaklga keltiriladi.
_APOS = dict.fromkeys(map(ord, "'ʻʼ`‘’´"), "'")
_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _norm(text: Optional[str]) -> str:
    return (text or "").strip().lower().translate(_APOS)


def _tokens(text: Optional[str]) -> set[str]:
    return set(_TOKEN_RE.findall(_norm(text)))


_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def _strip_apos(text: Optional[str]) -> str:
    # BARCHA bo'sh joy turlari (\s, shu jumladan \xa0 — uzilmas bo'sh joy)
    # ham olib tashlanadi — til nomlari hech qachon ICHIDA bo'sh joy
    # bo'lmaydi, shu sabab bu xavfsiz (va ba'zi PDF eksport yo'llarida
    # apostrof o'rniga tasodifiy bo'sh joy tushib qolishini ham qoplaydi —
    # masalan "O\xa0zbekcha" -> "ozbekcha").
    return _WHITESPACE_RE.sub("", _norm(text).replace("'", ""))


# -- PDF parsing ---------------------------------------------------------
@dataclass(frozen=True)
class RawChoice:
    """Qaydvaraqadan XOM (bazaga moslashtirilmagan) o'qilgan bitta tanlov."""
    rank: int
    ty_text_raw: str
    university_raw: str
    direction_raw: str


@dataclass
class QaydvaraqaData:
    fio: Optional[str]
    lang_raw: Optional[str]
    choices: list[RawChoice] = field(default_factory=list)
    abt_id: Optional[str] = None
    passport: Optional[str] = None
    jshshir: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None


class QaydvaraqaParseError(Exception):
    """PDF matni kutilgan qayd varaqa tuzilishiga mos kelmadi."""


_RANK_TY_RE = re.compile(r"^(\d+)\s*(Kunduzgi|Kechki|Masofaviy)\s*$", re.IGNORECASE)
# Label bilan qiymat orasidagi ":" ba'zi PDF eksport yo'llarida (pastga
# qarang — shrift kodlash buzilishi) yo'qolib qolishi mumkin, shu sabab
# "[:\s]+" ishlatiladi (":" ixtiyoriy, kamida bitta bo'sh joy yetarli).
_FIO_RE = re.compile(r"F\.I\.O\.[:\s]+(.+)")
_LANG_RE = re.compile(r"Ta['ʻʼ`‘’]?\s*lim tili[:\s]+(.+)")
# Shaxsiy ma'lumot maydonlari — barchasi qaydvaraqada bitta qatorda (2 ustunli
# blokning ICHIDA emas), shu sabab boshqa maydonlardek aralashib ketmaydi
# (sinovda 6/6 real qaydvaraqada tasdiqlangan).
_ID_RE = re.compile(r"\bID[:\s]+(\d+)")
_PASSPORT_RE = re.compile(r"Pasport\s*\(?ID karta\)?\s*seriya va raqami[:\s]+(.+)")
_JSHSHIR_RE = re.compile(r"JShShIR[:\s]+([\d\s]*\d)")
_BIRTH_RE = re.compile(r"Tug['ʻʼ`‘’]?ilgan sanasi[:\s]+(\S+)")
_GENDER_RE = re.compile(r"Jinsi[:\s]+(\S+)")

# -- Rus tilidagi qaydvaraqa ----------------------------------------------
# t.me/BaholashUz qaydvaraqani rus tilida ham generatsiya qiladi — barcha
# label VA universitet/yo'nalish nomlari kirillda chiqadi (F.I.O., pasport
# seriyasi, ID kabi qiymatlar lotin/raqamlarda qoladi, chunki ular
# tarjima qilinmaydigan xom ma'lumot). 2026-08-11 haqiqiy foydalanuvchi
# xatosida aniqlangan (NURULLAYEVA A.M. namunasi).
_RU_LANDMARK = "регистрационный лист абитуриента"
_RU_FIO_RE = re.compile(r"Ф\.И\.О\.[:\s]+(.+)")
_RU_ID_RE = re.compile(r"\bID[:\s]+(\d+)")
_RU_PASSPORT_RE = re.compile(r"Серия и номер паспорта[^:\n]*:[:\s]*(.+)")
_RU_JSHSHIR_RE = re.compile(r"ПИНФЛ[:\s]+([\d\s]*\d)")
_RU_BIRTH_RE = re.compile(r"Дата рождения[:\s]+(\S+)")
_RU_GENDER_RE = re.compile(r"Пол[:\s]+(\S+)")
_RU_LANG_RE = re.compile(r"Язык обучения[:\s]+(.+)")

_RU_GENDER_MAP = {"мужской": "Erkak", "женский": "Ayol"}
# resolve_lang() "cha" qo'shimchasini kesib DB bilan solishtiradi (mas.
# "Ruscha" -> "rus") — shu sabab tarjima ANIQ shu formatga qilinadi.
_RU_LANG_MAP = {
    "русский": "Ruscha", "узбекский": "O'zbekcha", "каракалпакский": "Qoraqalpoqcha",
    "казахский": "Qozoqcha", "туркменский": "Turkmancha", "киргизский": "Qirg'izcha",
    "таджикский": "Tadjikcha",
}
_RU_FORM_MAP = {
    "очное": "Kunduzgi", "вечернее": "Kechki",
    "заочное": "Sirtqi", "дистанционное": "Masofaviy",
}
_RU_RANK_TY_RE = re.compile(
    r"^(\d+)\s*(Очное|Вечернее|Заочное|Дистанционное)\s*$", re.IGNORECASE
)

# Universitet/yo'nalish nomlaridagi eng ko'p uchraydigan so'zlarning
# rus->o'zbek tarjimasi — TO'LIQ tarjima emas, faqat resolve_university()/
# resolve_direction()ning mavjud (token-qamrov, TARTIBGA BOG'LIQ EMAS)
# moslashtiruvchisi ishlashi uchun yetarli daraja (real DB nomlari bilan
# tekshirilgan — mas. "Tarjima nazariyasi va amaliyoti: ingliz tili").
# Noma'lum so'zlar o'zgarishsiz qoladi — noto'g'ri OTM/yo'nalishga
# moslashtirishdan ko'ra "topilmadi" (0.7 chegaradan pastroq qolsa) afzal.
_RU_UNI_WORD_MAP = {
    "узбекский": "o'zbekiston", "узбекистана": "o'zbekiston", "узбекистан": "o'zbekiston",
    "государственный": "davlat", "национальный": "milliy",
    "университет": "universiteti", "институт": "instituti",
    "мировых": "jahon", "языков": "tillari",
    "технический": "texnika", "педагогический": "pedagogika",
    "медицинский": "tibbiyot", "экономический": "iqtisodiyot",
    "аграрный": "agrar", "юридический": "yuridik", "исламский": "islom",
    "финансов": "moliya", "финансовый": "moliya", "технологический": "texnologiya",
    "и": "va",
    # Yo'nalish nomlarida uchraydigan umumiy akademik so'zlar:
    "теория": "nazariyasi", "практика": "amaliyoti",
    "перевода": "tarjima", "перевод": "tarjima",
    "английский": "ingliz", "немецкий": "nemis", "французский": "fransuz",
    "испанский": "ispan", "китайский": "xitoy", "корейский": "koreys",
    "японский": "yapon", "арабский": "arab", "турецкий": "turk",
    "язык": "tili", "языку": "tili", "иностранный": "xorijiy",
    "литература": "adabiyoti", "филология": "filologiya",
    "обучение": "o'qitish", "языкам": "tillarni",
}


def _translate_ru_words(text: str, word_map: dict[str, str]) -> str:
    """Har bir so'zni (lug'atda bo'lsa) almashtiradi — TO'LIQ tarjima
    EMAS, faqat token-qamrov moslashtiruvchisi uchun yetarli daraja."""
    out_words = []
    for word in text.split():
        key = word.strip(".,;:()").lower()
        out_words.append(word_map.get(key, word))
    return " ".join(out_words)

# -- Buzilgan shrift kodlashini tuzatish --------------------------------
# Ba'zi PDF eksport yo'llari (mas. Safari brauzerining "Print to PDF"i —
# haqiqiy hodisada aniqlangan) qaydvaraqa PDF'ining shriftini noto'g'ri
# subset qiladi: har bir belgi bir xil DOIMIY siljish bilan noto'g'ri
# Unicode kod nuqtasiga tushib qoladi (mas. "Bilim" -> "%LOLP", +29
# siljitilsa asliga qaytadi). Bu www.uzbmb.uz saytidan TO'G'RIDAN-TO'G'RI
# yuklab olingan (6 ta sinov namunasi) qaydvaraqalarda kuzatilmagan — faqat
# muqobil (brauzer orqali qayta eksport qilingan) PDF'larda. Ma'lum
# "landmark" matnni (agentlik nomi, HAR bir qaydvaraqada bor) qidirib,
# TO'G'RI siljish avtomatik aniqlanadi va butun matn/jadvallarga
# qo'llaniladi — noldan shrift xaritasini bilish shart emas.
_ENCODING_LANDMARK = "Bilim va malakalarni"
_MAX_SHIFT_PROBE = 60


def _shift_char(c: str, shift: int) -> str:
    if c in ("\n", " "):
        return c
    cp = ord(c) + shift
    # Haqiqiy (buzilmagan) matnlarda ham siljish "sinab ko'riladi" (shift
    # aniqlanmaguncha) — masalan kirill harflari ancha yuqori kod
    # nuqtalarida, past manfiy siljish bilan 0 dan pastga tushib qolishi
    # mumkin. Bunday holatda chr() ValueError beradi — belgini o'zgarishsiz
    # qoldiramiz (bu shift baribir noto'g'ri bo'lib chiqadi, landmark
    # topilmaydi, lekin CRASH bo'lmasligi kerak).
    return chr(cp) if 0 <= cp <= 0x10FFFF else c


def _apply_char_shift(text: str, shift: int) -> str:
    """Har bir belgini `shift` qadar siljitadi — qator ko'chirish (\\n) va
    ODDIY BO'SH JOY o'zgarishsiz qoladi, chunki ular pdfplumber'ning o'zi
    (glif joylashuviga qarab) qo'shgan STRUKTURAVIY belgilar, shrift
    kodlash oqimidan emas (aralashtirilsa "1 Masofaviy" kabi qiymatlar
    "1=Masofaviy" kabi buzilib qoladi)."""
    if not text or shift == 0:
        return text
    return "".join(_shift_char(c, shift) for c in text)


def _detect_char_shift(text: str) -> int:
    if not text or _ENCODING_LANDMARK in text:
        return 0
    for shift in list(range(1, _MAX_SHIFT_PROBE + 1)) + list(range(-1, -_MAX_SHIFT_PROBE - 1, -1)):
        if _ENCODING_LANDMARK in _apply_char_shift(text, shift):
            return shift
    return 0


def _shift_tables(tables: list, shift: int) -> list:
    if shift == 0:
        return tables
    return [
        [
            [(_apply_char_shift(cell, shift) if cell else cell) for cell in row] if row else row
            for row in table
        ]
        for table in tables
    ]


def _match_rank_ty(line: str, is_russian: bool) -> Optional[tuple[int, str]]:
    """"N Ta'lim_shakli" qatorini moslashtiradi — rus tilidagi qaydvaraqada
    shakl nomlari kirillda (Очное/Вечернее/...) chiqadi, shu sabab topilgach
    darhol o'zbekcha ekvivalentga tarjima qilinadi (keyingi bosqichlar —
    resolve_ty va h.k. — faqat o'zbekcha qiymatlarni biladi)."""
    if is_russian:
        m = _RU_RANK_TY_RE.match(line)
        if not m:
            return None
        return int(m.group(1)), _RU_FORM_MAP[m.group(2).lower()]
    m = _RANK_TY_RE.match(line)
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def _extract_choices_from_text(text: str, is_russian: bool = False) -> list[RawChoice]:
    """`extract_tables()` chegarali jadval topmagan hollar uchun zaxira
    yo'l — "N Ta'lim_shakli" qatorini (`_match_rank_ty`) qidirib, undan
    OLDINGI eng yaqin bo'sh-bo'lmagan qatorni universitet, KEYINGISINI
    yo'nalish sifatida oladi (real "kasbiy (ijodiy) imtihon" qaydvaraqada
    koordinatalar bo'yicha tasdiqlangan — bu uch qator xuddi jadval
    katakchasidagi kabi ketma-ket keladi, faqat pdfplumber ularni jadval
    deb tanimaydi)."""
    lines = [l.strip() for l in text.split("\n")]
    choices: list[RawChoice] = []
    for i, line in enumerate(lines):
        matched = _match_rank_ty(line, is_russian)
        if not matched:
            continue
        rank, ty_text = matched
        university_raw = next((lines[j] for j in range(i - 1, -1, -1) if lines[j]), None)
        direction_raw = next((lines[j] for j in range(i + 1, len(lines)) if lines[j]), None)
        if not university_raw or not direction_raw:
            continue
        choices.append(RawChoice(
            rank=rank, ty_text_raw=ty_text,
            university_raw=university_raw, direction_raw=direction_raw,
        ))
    return choices


def _diagnose_missing_choices(text: str, is_scanned_image: bool) -> str:
    """Tanlovlar topilmasa, sababi aniq bo'lsa moslashtirilgan xabar
    qaytaradi — real foydalanuvchi xatolaridan (2026-08-11, admin'ga
    yuborilgan muvaffaqiyatsiz PDF'lar) aniqlangan naqshlar: (1) skaner/
    skrinshot, (2) "Abituriyent ruxsatnomasi" (imtihon ruxsatnomasi,
    boshqa hujjat), (3) test javoblari varag'i (boshqa hujjat), (4) haqiqiy
    qaydvaraqa, lekin tanlovlar hali BELGILANMAGAN (test natijalaridan
    keyin 15 kun ichida tanlanadi — bu muddatdan oldin yuklab olingan)."""
    if is_scanned_image:
        return (
            "Bu fayl skanerlangan rasm/skrinshot ko'rinishida — matn qatlami "
            "yo'q, shu sabab o'qib bo'lmadi. Iltimos, rasmiy saytdan (yoki "
            "t.me/BaholashUz) TO'G'RIDAN-TO'G'RI yuklab olingan asl PDF "
            "faylni yuboring (skrinshot yoki skaner emas)."
        )
    norm = _norm(text)
    if "ruxsatnomasi" in norm:
        return (
            "Bu fayl \"Abituriyent ruxsatnomasi\" (imtihonga ruxsat varaqasi) "
            "ekan, \"Abituriyent qayd varaqasi\" (tanlovlar ro'yxati) emas. "
            "Iltimos, to'g'ri hujjatni yuklab oling."
        )
    if "umumiy bali" in norm:
        return (
            "Bu fayl test natijalari (javoblar varag'i) ekan, \"Abituriyent "
            "qayd varaqasi\" (tanlovlar ro'yxati) emas. Iltimos, to'g'ri "
            "hujjatni yuklab oling."
        )
    if "yo'nalishlari" in norm:
        return (
            "Qaydvaraqangizda hali tanlovlar ko'rsatilmagan — test "
            "natijalari chiqqach, 15 kun ichida universitet/yo'nalish "
            "tanlashingiz kerak. Tanlovlarni belgilagach, YANGI qaydvaraqani "
            "qayta yuklab oling va shuni yuboring."
        )
    return "Tanlovlar jadvali topilmadi — bu qaydvaraqa fayliga o'xshamaydi"


def parse_pdf(data: bytes) -> QaydvaraqaData:
    """Qaydvaraqa PDF'sini tahlil qiladi.

    Tanlovlar jadvali pdfplumber'ning `extract_tables()` orqali olinadi —
    sahifaning naiv (layout'siz) matn ajratishi ikki ustunli info-blokni
    aralashtirib yuboradi (sinovda tasdiqlangan), lekin real chegarali
    jadval sifatida chiqadigan tanlovlar ro'yxati BUZILMAYDI."""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if not pdf.pages:
                raise QaydvaraqaParseError("PDF sahifasi yo'q")
            page = pdf.pages[0]
            text = page.extract_text() or ""
            tables = page.extract_tables()
            is_scanned_image = not page.chars and bool(page.images)
    except QaydvaraqaParseError:
        raise
    except Exception as exc:
        raise QaydvaraqaParseError(f"PDF ochilmadi: {exc}") from exc

    # Rus tilidagi qaydvaraqada label VA universitet/yo'nalish nomlari
    # kirillda chiqadi (t.me/BaholashUz saytining o'zi shunday generatsiya
    # qiladi — bu BUZILGAN kodlash EMAS). Shrift-siljish tuzatishi bunga
    # daxldor emas, shu sabab avval tekshiriladi (siljishni behuda 120 marta
    # sinab ko'rishning ham hojati yo'q).
    is_russian = _RU_LANDMARK in _norm(text)
    if not is_russian:
        shift = _detect_char_shift(text)
        if shift:
            text = _apply_char_shift(text, shift)
            tables = _shift_tables(tables, shift)

    def _grp(pattern: re.Pattern) -> Optional[str]:
        m = pattern.search(text)
        return m.group(1).strip() if m else None

    if is_russian:
        fio = _grp(_RU_FIO_RE)
        lang_raw = _grp(_RU_LANG_RE)
        abt_id = _grp(_RU_ID_RE)
        passport = _grp(_RU_PASSPORT_RE)
        jshshir = _grp(_RU_JSHSHIR_RE)
        birth_date = _grp(_RU_BIRTH_RE)
        gender = _grp(_RU_GENDER_RE)
        if lang_raw:
            lang_raw = _RU_LANG_MAP.get(lang_raw.strip().lower(), lang_raw)
        if gender:
            gender = _RU_GENDER_MAP.get(gender.strip().lower(), gender)
    else:
        fio = _grp(_FIO_RE)
        lang_raw = _grp(_LANG_RE)
        abt_id = _grp(_ID_RE)
        passport = _grp(_PASSPORT_RE)
        jshshir = _grp(_JSHSHIR_RE)
        birth_date = _grp(_BIRTH_RE)
        gender = _grp(_GENDER_RE)
    # Buzilgan kodlashda (yoki rus PINFL formatida) raqamlar ichiga tasodifiy
    # bo'sh joy tushib qolishi mumkin — bitta yaxlit raqamga birlashtiriladi.
    if jshshir:
        jshshir = jshshir.replace(" ", "")

    def _maybe_translate(value: str) -> str:
        return _translate_ru_words(value, _RU_UNI_WORD_MAP) if is_russian else value

    choices: list[RawChoice] = []
    for table in tables:
        for row in table:
            cell = (row[0] or "") if row else ""
            parts = [p.strip() for p in cell.split("\n") if p.strip()]
            if len(parts) < 3:
                continue
            matched = _match_rank_ty(parts[1], is_russian)
            if not matched:
                continue
            rank, ty_text = matched
            choices.append(RawChoice(
                rank=rank, ty_text_raw=ty_text,
                university_raw=_maybe_translate(parts[0]),
                direction_raw=_maybe_translate(parts[2]),
            ))

    if not choices:
        # Kasbiy (ijodiy) imtihon (mas. sport/san'at yo'nalishlari) orqali
        # kirayotgan abituriyentlar qaydvaraqasida bitta tanlov ODATDAGI
        # chegarali jadval sifatida CHIQMAYDI (pdfplumber uni jadval deb
        # aniqlay olmaydi) — lekin xuddi shu "universitet / rank+shakl /
        # yo'nalish" uch qatorlik ketma-ketlik oddiy matn oqimida ham
        # saqlanib qoladi. Shu sabab jadval topilmasa, xuddi shu naqsh
        # (_RANK_TY_RE) MATN QATORLARI orasidan qidiriladi.
        choices = _extract_choices_from_text(text, is_russian)
        if is_russian:
            choices = [
                RawChoice(
                    rank=c.rank, ty_text_raw=c.ty_text_raw,
                    university_raw=_maybe_translate(c.university_raw),
                    direction_raw=_maybe_translate(c.direction_raw),
                )
                for c in choices
            ]

    if not choices:
        raise QaydvaraqaParseError(_diagnose_missing_choices(text, is_scanned_image))
    choices.sort(key=lambda c: c.rank)
    return QaydvaraqaData(
        fio=fio, lang_raw=lang_raw, choices=choices, abt_id=abt_id,
        passport=passport, jshshir=jshshir, birth_date=birth_date, gender=gender,
    )


# -- Bazaga moslashtirish (entity resolution) --------------------------------
# Aniq (normallashgan) moslik yetarli bo'lmasa shu chegaradan yuqori bo'lgan
# eng yaxshi token-qamrov nomzod qabul qilinadi. 105 ta universitet ustida
# sinovda kalibrlangan — pastroq chegara noto'g'ri (lekin o'xshash nomli)
# muassasani xato moslashtirib qo'yishi mumkin.
_UNI_MATCH_THRESHOLD = 0.7


def resolve_university(raw_name: str, universities: list[tuple[str, str]]) -> Optional[tuple[str, str]]:
    """`universities`: [(un_id, un_text), ...]. Topilmasa None — bu HALOL
    "bazamizda yo'q" javobiga olib keladi, noto'g'ri moslikdan yaxshiroq."""
    target_norm = _norm(raw_name)
    for un_id, un_text in universities:
        if _norm(un_text) == target_norm:
            return un_id, un_text

    target_tokens = _tokens(raw_name)
    if not target_tokens:
        return None
    best: Optional[tuple[str, str]] = None
    best_score = 0.0
    for un_id, un_text in universities:
        db_tokens = _tokens(un_text)
        if not db_tokens:
            continue
        shared = target_tokens & db_tokens
        if not shared:
            continue
        # Ikki tomonlama qamrov (qattiqroq shart): sertifikat nomining
        # QANCHASI bazada bor, VA bazadagi nomning qanchasi sertifikatda
        # bor — aks holda umumiy so'zlar ("davlat", "instituti") bilan
        # noto'g'ri muassasa ham baland ball olib qolishi mumkin edi.
        score = min(len(shared) / len(target_tokens), len(shared) / len(db_tokens))
        if score > best_score:
            best, best_score = (un_id, un_text), score
    return best if best_score >= _UNI_MATCH_THRESHOLD else None


def resolve_ty(raw_ty_text: str, candidates: list[tuple[str, str]]) -> Optional[tuple[str, str]]:
    """`candidates`: [(ty_id, ty_text), ...] shu universitet uchun."""
    key = _norm(raw_ty_text)
    for ty_id, ty_text in candidates:
        if _norm(ty_text) == key:
            return ty_id, ty_text
    return None


def resolve_lang(raw_lang: str, candidates: list[tuple[str, str]]) -> Optional[tuple[str, str]]:
    """`candidates`: [(lan_id, lan_text), ...]. Sertifikatda til SIFAT shaklda
    ("O'zbekcha", "Ruscha"), bazada OT shaklda ("O`zbek", "Rus") — "cha"
    qo'shimchasi kesib, apostrofsiz solishtiriladi (real DB qiymatlariga
    qarab, qattiq kodlangan tarjima jadvalisiz — baza kengaysa ham ishlaydi)."""
    key = _strip_apos(raw_lang)
    if key.endswith("cha"):
        key = key[:-3]
    for lan_id, lan_text in candidates:
        if _strip_apos(lan_text) == key:
            return lan_id, lan_text
    return None


def resolve_direction(raw_direction: str, candidates: list[str]) -> Optional[str]:
    """`candidates`: shu (universitet, ty, til) uchun mavjud `nomi` qiymatlari."""
    target_norm = _norm(raw_direction)
    for nomi in candidates:
        if _norm(nomi) == target_norm:
            return nomi
    target_tokens = _tokens(raw_direction)
    if not target_tokens:
        return None
    best, best_score = None, 0.0
    for nomi in candidates:
        db_tokens = _tokens(nomi)
        if not db_tokens:
            continue
        shared = target_tokens & db_tokens
        if not shared:
            continue
        score = min(len(shared) / len(target_tokens), len(shared) / len(db_tokens))
        if score > best_score:
            best, best_score = nomi, score
    return best if best_score >= _UNI_MATCH_THRESHOLD else None


# -- Baza so'rovlari (sinxron psycopg2 — loyiha konvensiyasiga mos) ----------
_SCORE_YEAR = 2025
NATIONAL_CONTRACT_FLOOR = 56.7
NATIONAL_GRANT_FLOOR = 68.0


@dataclass
class MatchedChoice:
    rank: int
    university_raw: str
    direction_raw: str
    ty_text_raw: str
    matched: bool
    un_text: Optional[str] = None
    ty_text: Optional[str] = None
    lan_text: Optional[str] = None
    nomi: Optional[str] = None
    con_b: Optional[float] = None
    unmatch_reason: Optional[str] = None


def _all_universities() -> list[tuple[str, str]]:
    cursor.execute("SELECT un_id, un_text FROM universities")
    return cursor.fetchall()


def match_choices(data: QaydvaraqaData) -> list[MatchedChoice]:
    """Har bir tanlovni bazaga moslashtiradi va shu (universitet, ty, til,
    yo'nalish) uchun 2025-yilgi kontrakt ballini oladi."""
    universities = _all_universities()
    results: list[MatchedChoice] = []

    for choice in data.choices:
        uni = resolve_university(choice.university_raw, universities)
        if not uni:
            results.append(MatchedChoice(
                rank=choice.rank, university_raw=choice.university_raw,
                direction_raw=choice.direction_raw, ty_text_raw=choice.ty_text_raw,
                matched=False, unmatch_reason="Muassasa bazamizda topilmadi",
            ))
            continue
        un_id, un_text = uni

        cursor.execute(
            "SELECT DISTINCT ty_id, ty_text FROM gettypes WHERE un_id=%s", (un_id,)
        )
        ty_candidates = cursor.fetchall()
        ty = resolve_ty(choice.ty_text_raw, ty_candidates)
        if not ty:
            results.append(MatchedChoice(
                rank=choice.rank, university_raw=choice.university_raw,
                direction_raw=choice.direction_raw, ty_text_raw=choice.ty_text_raw,
                matched=False, un_text=un_text,
                unmatch_reason="Ta'lim shakli bazamizda topilmadi",
            ))
            continue
        ty_id, ty_text = ty

        lang_raw = data.lang_raw or ""
        cursor.execute(
            "SELECT DISTINCT lan_id, lan_text FROM getlangs WHERE un_id=%s AND ty_id=%s",
            (un_id, ty_id),
        )
        lang_candidates = cursor.fetchall()
        lang = resolve_lang(lang_raw, lang_candidates)
        if not lang:
            results.append(MatchedChoice(
                rank=choice.rank, university_raw=choice.university_raw,
                direction_raw=choice.direction_raw, ty_text_raw=choice.ty_text_raw,
                matched=False, un_text=un_text, ty_text=ty_text,
                unmatch_reason="Ta'lim tili bazamizda topilmadi",
            ))
            continue
        lan_id, lan_text = lang

        cursor.execute(
            "SELECT DISTINCT nomi FROM mandat WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND year=%s",
            (un_id, ty_id, lan_id, _SCORE_YEAR),
        )
        direction_candidates = [r[0] for r in cursor.fetchall()]
        nomi = resolve_direction(choice.direction_raw, direction_candidates)
        if not nomi:
            results.append(MatchedChoice(
                rank=choice.rank, university_raw=choice.university_raw,
                direction_raw=choice.direction_raw, ty_text_raw=choice.ty_text_raw,
                matched=False, un_text=un_text, ty_text=ty_text, lan_text=lan_text,
                unmatch_reason="Yo'nalish bazamizda topilmadi",
            ))
            continue

        cursor.execute(
            """SELECT con_b FROM mandat
               WHERE un_id=%s AND ty_id=%s AND lan_id=%s AND nomi=%s AND year=%s
               LIMIT 1""",
            (un_id, ty_id, lan_id, nomi, _SCORE_YEAR),
        )
        row = cursor.fetchone()
        con_b = float(row[0]) if row and row[0] is not None else None

        results.append(MatchedChoice(
            rank=choice.rank, university_raw=choice.university_raw,
            direction_raw=choice.direction_raw, ty_text_raw=choice.ty_text_raw,
            matched=con_b is not None, un_text=un_text, ty_text=ty_text,
            lan_text=lan_text, nomi=nomi, con_b=con_b,
            unmatch_reason=None if con_b is not None else "2025-yilgi ball topilmadi",
        ))

    return results


# -- Hisobot formatlash --------------------------------------------------
def _clean_uni(name: str) -> str:
    return name.strip()


# -- Super-kontrakt (tabaqalashtirilgan to'lov) hisob-kitobi ----------------
#
# Manba: "2025/2026-o'quv yilidan boshlab respublika davlat oliy ta'lim
# tashkilotlarida ... bitta talabani bazaviy to'lov-kontrakt asosida bir
# yillik o'qitish qiymati MIQDORLARI" rasmiy jadvali (foydalanuvchi
# tomonidan taqdim etilgan, 2025-yil, so'mda). Faqat BAKALAVRIAT ustunlari
# ishlatiladi — bu bo'lim faqat bakalavriat qabuli uchun.
#
# Qoida (foydalanuvchi tomonidan berilgan, 2025-yil, manba:
# https://t.me/nodavlattalim/4271):
#   o'tish balliga 1 ballgacha yetmasa   -> bazaviy narx x1.5
#   1,01 dan 2 ballgacha yetmasa         -> x2
#   2,01 dan 3 ballgacha yetmasa         -> x2.5
#   3,01 dan 4 ballgacha yetmasa         -> x3
#   4 balldan ortiq yetmasa              -> OTM o'zi belgilaydi, HISOBLAMAYMIZ
_SUPER_KONTRAKT_TIERS = (
    # (yetmagan ball yuqori chegarasi, ko'paytiruvchi)
    (1.0, 1.5), (2.0, 2.0), (3.0, 2.5), (4.0, 3.0),
)

# (kategoriya kaliti): (kunduzgi, sirtqi/masofaviy/kechki) — 2025/2026, so'm.
_BASE_TUITION = {
    "gumanitar_pedagogika": (7_400_000, 8_623_000),
    "gumanitar_sanat": (8_950_000, 10_330_000),
    "gumanitar_fanlar": (7_400_000, 8_623_000),
    "gumanitar_filologiya_maxsus": (8_150_000, 9_444_000),
    "gumanitar_jahon_siyosati": (11_250_000, 12_856_000),
    "gumanitar_matematika_tabiiy": (7_400_000, 8_623_000),
    "ijtimoiy_baza": (7_400_000, 8_623_000),
    "ijtimoiy_iqtisod": (10_500_000, 12_030_000),
    "ijtimoiy_jahon_iqtisod": (11_250_000, 12_856_000),
    "ijtimoiy_huquq": (11_250_000, 12_856_000),
    "texnik_muhandislik": (7_400_000, 8_623_000),
    "texnik_kompyuter": (8_150_000, 9_444_000),
    "texnik_ikt_iqtisod_menejment": (10_500_000, 12_030_000),
    "texnik_arxitektura_qurilish": (8_150_000, 9_444_000),
    "texnik_arxitektura_qishloq": (8_950_000, 10_330_000),
    "qishloq_suv": (7_400_000, 8_623_000),
    "sogliq": (10_500_000, 12_030_000),
    "ijtimoiy_taminot": (7_400_000, 8_623_000),
    "xizmat_asosiy": (8_150_000, 9_444_000),
    "xizmat_sport": (7_400_000, 8_623_000),
    "transport": (7_400_000, 8_623_000),
    "atrofmuhit": (7_400_000, 8_623_000),
}

# "X: Y" shaklidagi guruhlar — prefiks bo'yicha (har bir kichik variantni
# alohida sanab o'tirmaslik uchun). TEKSHIRISH TARTIBI MUHIM: aniqrog'i
# oldin turishi kerak (masalan "Tarjima nazariyasi va amaliyoti:" —
# rasmiy jadvalda ANIQ nomlangan yuqori tarifga ega, shu sabab "Filologiya"
# umumiy qoidasidan OLDIN tekshiriladi).
_PREFIX_RULES: tuple[tuple[str, str], ...] = (
    ("tarjima nazariyasi va amaliyoti:", "gumanitar_filologiya_maxsus"),
    ("aktyorlik san'ati:", "gumanitar_sanat"),
    ("amaliy san'at:", "gumanitar_sanat"),
    ("cholg'u ijrochiligi:", "gumanitar_sanat"),
    ("dirijyorlik:", "gumanitar_sanat"),
    ("dizayn:", "gumanitar_sanat"),
    ("grafika:", "gumanitar_sanat"),
    ("haykaltaroshlik:", "gumanitar_sanat"),
    ("muzeyshunoslik:", "gumanitar_fanlar"),
    ("rangtasvir:", "gumanitar_sanat"),
    ("rejissyorlik:", "gumanitar_sanat"),
    ("san'atshunoslik:", "gumanitar_sanat"),
    ("texnogen san'at:", "gumanitar_sanat"),
    ("vokal san'ati:", "gumanitar_sanat"),
    ("xalq ijodiyoti:", "gumanitar_sanat"),
    ("maxsus pedagogika:", "gumanitar_pedagogika"),
    ("sport faoliyati:", "xizmat_sport"),
    ("filologiya va tillarni o'qitish:", "gumanitar_fanlar"),
    ("ona tili va adabiyoti:", "gumanitar_fanlar"),
    ("xorijiy til va adabiyoti:", "gumanitar_fanlar"),
    ("texnologik mashinalar va jihozlar:", "texnik_muhandislik"),
)

_RE_PAREN_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")

# Alohida (prefikssiz) yo'nalishlar. Ro'yxat bazadagi 330 ta noyob `nomi`
# qiymati asosida qo'lda tuzilgan va tekshirilgan
# (`.claude` ishchi eslatmalarida to'liq ro'yxat va mulohaza saqlangan).
# Chegaraviy holatlarda (masalan "Statistika", "Kompyuter lingvistikasi")
# eng yaqin rasmiy toifaga onglik ravishda biriktirilgan — 100% aniqlik
# kafolatlanmaydi, shu sabab bu FAQAT mo'ljal sifatida ko'rsatiladi.
_EXACT_RULES: dict[str, str] = {
    "adaptiv jismoniy tarbiya va sport": "gumanitar_pedagogika",
    "aerokosmik texnologiyalar": "texnik_muhandislik",
    "agrokimyo va tuproqshunoslik": "qishloq_suv",
    "agromuhandislik": "qishloq_suv",
    "agronomiya": "qishloq_suv",
    "amaliy matematika": "gumanitar_matematika_tabiiy",
    "antropologiya va etnologiya": "gumanitar_fanlar",
    "arxeologiya": "gumanitar_fanlar",
    "arxitektura": "texnik_arxitektura_qurilish",
    "arxitektura yodgorliklari rekonstruksiyasi va restavratsiyasi": "texnik_arxitektura_qurilish",
    "arxivshunoslik": "gumanitar_fanlar",
    "astronomiya": "gumanitar_matematika_tabiiy",
    "atrof-muhit muhandisligi": "texnik_muhandislik",
    "aviatsiya muhandisligi": "texnik_muhandislik",
    "axborot tizimlari va texnologiyalari": "texnik_kompyuter",
    "axborot xavfsizligi": "texnik_kompyuter",
    "axborot xizmati va jamoatchilik bilan aloqalar": "ijtimoiy_baza",
    "bank ishi": "ijtimoiy_iqtisod",
    "barqaror transport": "transport",
    "bastakorlik san'ati": "gumanitar_sanat",
    "biologiya": "gumanitar_matematika_tabiiy",
    "biotexnologiya": "gumanitar_matematika_tabiiy",
    "biotibbiyot muhandisligi": "texnik_muhandislik",
    "biznesni boshqarish": "ijtimoiy_iqtisod",
    "boshlang'ich ta'lim": "gumanitar_pedagogika",
    "buxgalteriya hisobi": "ijtimoiy_iqtisod",
    "chaqiriqqacha harbiy ta'lim": "gumanitar_pedagogika",
    "dasturiy injiniring": "texnik_kompyuter",
    "davlat va jamiyat boshqaruvi": "ijtimoiy_baza",
    "davolash ishi": "sogliq",
    "dinshunoslik": "gumanitar_fanlar",
    "dorivor o'simliklarni yetishtirish va qayta ishlash texnologiyasi": "qishloq_suv",
    "ekologiya va atrof-muhit muhofazasi": "atrofmuhit",
    "elektr muhandisligi": "texnik_muhandislik",
    "elektronika va asbobsozlik": "texnik_muhandislik",
    "energetika muhandisligi": "texnik_muhandislik",
    "falsafa": "gumanitar_fanlar",
    "farmatsiya": "sogliq",
    "fizika": "gumanitar_matematika_tabiiy",
    "foydali qazilma konlari geologiyasi, qidiruv va razvedkasi": "texnik_muhandislik",
    "fundamental tibbiyot": "sogliq",
    "gazni chuqur qayta ishlash texnologiyasi": "texnik_muhandislik",
    "geodeziya va geoinformatika": "texnik_muhandislik",
    "geografiya": "gumanitar_matematika_tabiiy",
    "geologiya": "gumanitar_matematika_tabiiy",
    "geologiya-qidiruv ishlari texnikasi va texnologiyasi": "texnik_muhandislik",
    "gidroenergetika": "texnik_muhandislik",
    "gidrogeologiya va muhandislik geologiyasi": "texnik_muhandislik",
    "gidrologiya": "gumanitar_matematika_tabiiy",
    "gidrotexnika inshootlari va nasos stansiyalaridan foydalanish": "qishloq_suv",
    "gidrotexnika va geotexnika muhandisligi": "texnik_muhandislik",
    "havodagi harakatni boshqarish": "texnik_muhandislik",
    "havo kemalarining parvoz ekspluatatsiyasi": "texnik_muhandislik",
    "hayot faoliyati xavfsizligi": "atrofmuhit",
    "ijtimoiy ish": "ijtimoiy_taminot",
    "infokommunikatsiya injiniringi": "texnik_kompyuter",
    "inson resurslarini boshqarish": "ijtimoiy_iqtisod",
    "ipakchilik va tutchilik": "qishloq_suv",
    "iqtisodiyot": "ijtimoiy_iqtisod",
    "ishlab chqarish muhandisligi": "texnik_muhandislik",
    "islomshunoslik": "gumanitar_fanlar",
    "jahon iqtisodiyoti va xalqaro iqtisodiy munosabatlar": "ijtimoiy_jahon_iqtisod",
    "jismoniy madaniyat": "gumanitar_pedagogika",
    "jurnalistika": "ijtimoiy_baza",
    "kadastr": "texnik_muhandislik",
    "kartografiya va masofadan zondlash": "texnik_muhandislik",
    "kiberxavfsizlik injiniringi": "texnik_kompyuter",
    "kimyo": "gumanitar_matematika_tabiiy",
    "kimyo muhandisligi": "texnik_muhandislik",
    "kino-teleoperatorlik": "gumanitar_sanat",
    "kommunal infratuzilmani tashkil etish va boshqarish": "texnik_muhandislik",
    "kompyuter injiniringi": "texnik_kompyuter",
    "kompyuter lingvistikasi": "texnik_kompyuter",
    "konchilik elektr mexanikasi": "texnik_muhandislik",
    "konchilik ishi": "texnik_muhandislik",
    "kosmik texnologiyalar": "texnik_muhandislik",
    "kutubxona-axborot faoliyati": "gumanitar_fanlar",
    "logistika": "ijtimoiy_iqtisod",
    "madaniyatshunoslik": "gumanitar_fanlar",
    "maktabgacha ta'lim": "gumanitar_pedagogika",
    "marketing": "ijtimoiy_iqtisod",
    "matbaa va qadoqlash muhandisligi": "texnik_muhandislik",
    "matematika": "gumanitar_matematika_tabiiy",
    "materialshunoslik": "texnik_muhandislik",
    "mehnat muhofazasi va texnika xavfsizligi": "atrofmuhit",
    "meliorativ gidrogeologiya": "qishloq_suv",
    "menejment": "ijtimoiy_iqtisod",
    "metallar texnologiyalari": "texnik_muhandislik",
    "metallurgiya muhandisligi": "texnik_muhandislik",
    "meteorologiya va iqlimshunoslik": "gumanitar_matematika_tabiiy",
    "metrologiya va standartlashtirish": "texnik_muhandislik",
    "meva-sabzavotchilik va uzumchilik": "qishloq_suv",
    "mexanika muhandisligi": "texnik_muhandislik",
    "mexanika va matematik modellashtirish": "gumanitar_matematika_tabiiy",
    "mexatronika va robototexnika": "texnik_muhandislik",
    "milliy g'oya, ma'naviyat asoslari va huquq ta'limi": "gumanitar_pedagogika",
    "moliya va moliyaviy texnologiyalar": "ijtimoiy_iqtisod",
    "muhandislik kommunikatsiyalari qurilish va ekspluatatsiyasi": "texnik_muhandislik",
    "musiqa ta'limi": "gumanitar_pedagogika",
    "neft va gaz ishi": "texnik_muhandislik",
    "neft' va neft-gazni qayta ishlash texnologiyasi": "texnik_muhandislik",
    "noshirlik ishi": "ijtimoiy_baza",
    "noyob va radioaktiv metallar rudalarini qazib olish, qayta ishlash texnikasi va texnologiyasi": "texnik_muhandislik",
    "o'rmonchilik va aholi yashash joylarini ko'kalamzorlashtirish": "qishloq_suv",
    "o'simliklar himoyasi va karantini": "qishloq_suv",
    "o'zbek tili va adabiyoti": "gumanitar_fanlar",
    "oliy hamshiralik ishi": "sogliq",
    "oziq-ovqat texnologiyasi": "texnik_muhandislik",
    "parfyumeriya-kosmetika mahsulotlari texnologiyasi": "texnik_muhandislik",
    "pedagogika": "gumanitar_pedagogika",
    "pediatriya ishi": "sogliq",
    "pochta aloqasi texnologiyasi": "texnik_kompyuter",
    "psixologiya": "ijtimoiy_baza",
    "qayta tiklanuvchi energiya manbalari": "texnik_muhandislik",
    "qishloq xo'jaligi ekinlari seleksiyasi va urug'chiligi": "qishloq_suv",
    "qishloq xo'jaligini mexanizatsiyalashtirish": "qishloq_suv",
    "qishloq xo'jalik mahsulotlarini saqlash va qayta ishlash texnologiyasi": "qishloq_suv",
    "qiymat injiniringi va ko'chmas mulkni boshqarish": "texnik_muhandislik",
    "qurilish muhandisligi": "texnik_muhandislik",
    "radioelektron qurilmalar va tizimlar": "texnik_kompyuter",
    "sanoat farmatsiyasi": "sogliq",
    "sanoat muhandisligi va menejmenti": "texnik_muhandislik",
    "savdo ishi": "ijtimoiy_iqtisod",
    "seysmologiya va seysmometriya": "gumanitar_matematika_tabiiy",
    "shahar qurilishi va loyihalash": "texnik_arxitektura_qurilish",
    "simsiz aloqa va teleradioeshittirish injiniringi": "texnik_kompyuter",
    "siyosatshunoslik": "ijtimoiy_baza",
    "soliqlar va soliqqa tortish": "ijtimoiy_iqtisod",
    "sotsiologiya": "ijtimoiy_baza",
    "statistika": "ijtimoiy_iqtisod",
    "stomatologiya": "sogliq",
    "sun'iy intellekt": "texnik_kompyuter",
    "suv bioresurslari va akvakultura": "qishloq_suv",
    "suv ta'minoti muhandislik tizimlari": "texnik_muhandislik",
    "suv xo'jaligi va melioratsiya": "qishloq_suv",
    "tarix": "gumanitar_fanlar",
    "tasviriy san'at va muhandislik grafikasi": "gumanitar_sanat",
    "telekommunikatsiya texnologiyalari": "texnik_kompyuter",
    "televizion texnologiyalar": "texnik_kompyuter",
    "texnologik jarayonlar va ishlab chiqarishni avtomatlashtirish": "texnik_muhandislik",
    "texnologik mashinalar va jihozlar": "texnik_muhandislik",
    "texnologik ta'lim": "gumanitar_pedagogika",
    "tibbiy profilaktika ishi": "sogliq",
    "transport vositalari muhandisligi": "transport",
    "tuproq bonitirovkasi va yer degredatsiyasi": "qishloq_suv",
    "turizm va mehmondo'stlik": "xizmat_asosiy",
    "veterinariya farmatsevtikasi": "qishloq_suv",
    "veterinariya meditsinasi": "qishloq_suv",
    "veterinariya sanitariya ekspertizasi": "qishloq_suv",
    "xalqaro munosabatlar": "ijtimoiy_baza",
    "xoreografiya": "gumanitar_sanat",
    "yengil sanoat muhandisligi": "texnik_muhandislik",
    "yer kadastri va yer tuzish": "texnik_muhandislik",
    "yo'l harakatini tashkil etish": "transport",
    "yo'l muhandisligi": "texnik_muhandislik",
    "yurisprudensiya": "ijtimoiy_huquq",
    "zooinjeneriya": "qishloq_suv",
}


# Kategoriya kaliti -> foydalanuvchiga ko'rsatiladigan o'qiladigan nom
# (rasmiy jadvaldagi soha guruhlariga mos, taxminiy). Kalkulyator bo'limida
# foydalanuvchiga "qaysi soha aniqlandi" deb ko'rsatish uchun ishlatiladi.
_SOHA_DISPLAY_NAMES: dict[str, str] = {
    "gumanitar_pedagogika": "Pedagogika",
    "gumanitar_sanat": "San'at",
    "gumanitar_fanlar": "Gumanitar fanlar",
    "gumanitar_filologiya_maxsus": "Filologiya va tillarni o'qitish (tarjima nazariyasi va amaliyoti)",
    "gumanitar_jahon_siyosati": "Jahon siyosati",
    "gumanitar_matematika_tabiiy": "Matematika va tabiiy fanlar",
    "ijtimoiy_baza": "Ijtimoiy-gumanitar (sotsiologiya, psixologiya, jurnalistika)",
    "ijtimoiy_iqtisod": "Iqtisodiyot",
    "ijtimoiy_jahon_iqtisod": "Jahon iqtisodiyoti va xalqaro iqtisodiy munosabatlar",
    "ijtimoiy_huquq": "Yurisprudensiya (huquq)",
    "texnik_muhandislik": "Muhandislik va ishlab chiqarish texnologiyalari",
    "texnik_kompyuter": "Kompyuter va axborot-kommunikatsiya texnologiyalari",
    "texnik_ikt_iqtisod_menejment": "AKT sohasida iqtisodiyot va menejment",
    "texnik_arxitektura_qurilish": "Arxitektura va qurilish",
    "texnik_arxitektura_qishloq": "Qishloq hududlarini arxitekturaviy loyihalash",
    "qishloq_suv": "Qishloq, o'rmon, baliq va suv xo'jaligi, veterinariya",
    "sogliq": "Sog'liqni saqlash",
    "ijtimoiy_taminot": "Ijtimoiy ta'minot",
    "xizmat_asosiy": "Xizmat ko'rsatish sohasi",
    "xizmat_sport": "Jismoniy tarbiya va sport",
    "transport": "Transport",
    "atrofmuhit": "Atrof-muhit muhofazasi va hayot faoliyati xavfsizligi",
}


def classify_soha(nomi: str) -> Optional[str]:
    """Yo'nalish nomini rasmiy to'lov-kontrakt jadvalidagi 6 sohadan biriga
    (aniqrog'i, shu soha ichidagi narx-toifasiga) moslashtiradi.

    Bu QATʼIY jadval emas — 330 ta noyob yo'nalish nomi qo'lda ko'rib
    chiqilib, eng yaqin rasmiy toifaga biriktirilgan (chegaraviy holatlarda
    ongli ravishda PASTROQ/konservativroq toifa tanlangan). Topilmasa
    (yangi/kutilmagan yo'nalish nomi) None qaytariladi — bunday holatda
    super-kontrakt taxmini UMUMAN ko'rsatilmaydi, noto'g'ri raqam
    ko'rsatishdan ko'ra."""
    norm = _norm(nomi)
    # Aniqroq (prefiksli) qoidalar birinchi — "Tarjima nazariyasi..." kabi
    # maxsus tariflar umumiy "Filologiya..." qoidasidan ustun turishi kerak.
    for prefix, category in _PREFIX_RULES:
        if norm.startswith(prefix):
            return category
    if norm in _EXACT_RULES:
        return _EXACT_RULES[norm]
    # Qavs ichidagi izoh olib tashlab qayta urinib ko'ramiz — masalan
    # "Xoreografiya (zamonaviy raqs)" -> "Xoreografiya",
    # "Yurisprudensiya (prokurorlik faoliyati)" -> "Yurisprudensiya".
    stripped = _RE_PAREN_SUFFIX.sub("", norm).strip()
    if stripped != norm:
        for prefix, category in _PREFIX_RULES:
            if stripped.startswith(prefix):
                return category
        if stripped in _EXACT_RULES:
            return _EXACT_RULES[stripped]
    return None


def soha_info(nomi: str, ty_text: str) -> Optional[dict]:
    """Yo'nalish nomi + ta'lim shakli asosida rasmiy to'lov-kontrakt sohasini
    va bazaviy narxni aniqlaydi. `None` — soha aniqlanmadi (yangi/kutilmagan
    yo'nalish nomi). Hisobot (`format_report`) va Super-kontrakt kalkulyatori
    (bot handleri) bir xil funksiyadan foydalanadi — ikkalasida ham bir xil
    natija kafolatlanadi."""
    category = classify_soha(nomi)
    if category is None:
        return None
    base = _BASE_TUITION.get(category)
    if base is None:
        return None
    kunduzgi, boshqa = base
    is_kunduzgi = _norm(ty_text) == "kunduzgi"
    return {
        "category": category,
        "category_label": _SOHA_DISPLAY_NAMES.get(category, category),
        "base_amount": kunduzgi if is_kunduzgi else boshqa,
        "is_kunduzgi": is_kunduzgi,
    }


def super_kontrakt_amount_for_gap(base_amount: int, gap: float) -> Optional[dict]:
    """Bazaviy narx + ball farqi (gap, musbat son) asosida tabaqalashtirilgan
    to'lov-kontrakt miqdorini hisoblaydi. `None` — gap > 4 (bu holatda OTM
    narxni O'ZI belgilaydi, 2025-yildan boshlab davlat buni tartibga
    solmaydi) yoki gap <= 0 (ball yetarli, tabaqalashtirish shart emas)."""
    if gap <= 0 or gap > 4.0:
        return None
    multiplier = next(m for upper, m in _SUPER_KONTRAKT_TIERS if gap <= upper)
    return {"multiplier": multiplier, "amount": round(base_amount * multiplier)}


def super_kontrakt_estimate(nomi: str, ty_text: str, gap: float) -> Optional[dict]:
    """Ball yetishmovchiligi (gap, musbat son) asosida tabaqalashtirilgan
    to'lov-kontrakt taxminini hisoblaydi (hisobotdagi avtomatik near-miss
    ko'rsatuvi uchun) — `soha_info` + `super_kontrakt_amount_for_gap`ning
    ustiga qurilgan qulay birlashtiruvchi funksiya."""
    if gap <= 0 or gap > 4.0:
        return None
    info = soha_info(nomi, ty_text)
    if info is None:
        return None
    calc = super_kontrakt_amount_for_gap(info["base_amount"], gap)
    if calc is None:
        return None
    return {"base_amount": info["base_amount"], **calc}


def format_som(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


def format_personal_block(personal: dict) -> str:
    """Abituriyentning shaxsiy ma'lumotlari — hisobot boshida ko'rsatiladi."""
    rows = [
        ("🆔 ID", personal.get("abt_id")),
        ("🪪 F.I.O.", personal.get("fio")),
        ("📄 Pasport (ID karta)", personal.get("passport")),
        ("🔢 JShShIR", personal.get("jshshir")),
        ("🎂 Tug'ilgan sanasi", personal.get("birth_date")),
        ("🧑 Jinsi", personal.get("gender")),
    ]
    lines = ["👤 <b>Abituriyent ma'lumotlari</b>"]
    for label, value in rows:
        if value:
            lines.append(f"{label}: <b>{value}</b>")
    return "\n".join(lines)


def format_report(
    matched: list[MatchedChoice], user_ball: float, personal: Optional[dict] = None,
    bot_username: Optional[str] = None,
) -> str:
    """Chiroyli, tartibli HTML hisobot — shaxsiy ma'lumotlar, har bir tanlov
    uchun aniq kirish/kirolmaslik + milliy chegaralarga nisbatan umumiy holat."""
    lines: list[str] = []

    if personal:
        lines.append(format_personal_block(personal))
        lines.append("—" * 20)

    eligible = [m for m in matched if m.matched and m.con_b is not None and user_ball >= m.con_b]
    not_eligible = [m for m in matched if m.matched and m.con_b is not None and user_ball < m.con_b]
    unmatched = [m for m in matched if not m.matched]

    lines.append(f"🎯 <b>Sizning balingiz: {user_ball:g}</b>\n")

    if eligible:
        best_rank = min(m.rank for m in eligible)
        lines.append(f"✅ <b>{len(eligible)} ta tanlovga kirish imkoningiz bor</b> "
                     f"(ustuvorlik bo'yicha eng yaxshisi — {best_rank}-tanlov)\n")
    else:
        lines.append("😕 <b>Hozircha hech bir tanlovingizga (2025-yil ballariga ko'ra) "
                     "yetarli ball ko'rinmayapti.</b>\n")

    for m in matched:
        if not m.matched:
            continue
        gap = user_ball - m.con_b
        icon = "✅" if gap >= 0 else "❌"
        sign = "+" if gap >= 0 else ""
        entry = (
            f"{icon} <b>{m.rank}-tanlov</b> ({m.ty_text})\n"
            f"   🏛 {_clean_uni(m.un_text)}\n"
            f"   📚 {m.nomi} — {m.lan_text}\n"
            f"   📈 2025 kontrakt balli: <b>{m.con_b:g}</b> "
            f"(sizda {sign}{gap:.1f})\n"
        )
        if gap < 0:
            shortfall = -gap
            est = super_kontrakt_estimate(m.nomi, m.ty_text, shortfall)
            if est:
                entry += (
                    f"   💰 <i>Taxminiy super-kontrakt (bazaviy narx × "
                    f"{est['multiplier']:g}): <b>{format_som(est['amount'])}</b></i>\n"
                )
            elif shortfall <= 4.0:
                entry += (
                    "   💰 <i>Tabaqalashtirilgan to'lov-kontrakt qo'llanilishi mumkin, "
                    "lekin bu yo'nalish sohasi bo'yicha bazaviy narxni aniq belgilay olmadik.</i>\n"
                )
            else:
                entry += (
                    "   💰 <i>Ball farqi 4 dan katta — bu holatda to'lov-kontrakt "
                    "miqdorini OTM mustaqil belgilaydi, biz hisoblay olmaymiz.</i>\n"
                )
        lines.append(entry)

    if unmatched:
        lines.append("⚠️ <b>Bazamizda aniqlanmagan tanlovlar:</b>")
        for m in unmatched:
            lines.append(f"   {m.rank}-tanlov — {_clean_uni(m.university_raw)} "
                         f"({m.unmatch_reason})")
        lines.append("")

    lines.append("—" * 20)

    total_comparable = len(eligible) + len(not_eligible)
    if total_comparable:
        percent = round(len(eligible) / total_comparable * 100)
        prob_icon = "✅" if percent == 100 else ("😕" if percent == 0 else "📊")
        lines.append(
            f"{prob_icon} <b>SIZNING O'QISHGA KIRISH EHTIMOLLIGINGIZ {percent}%</b> "
            f"<i>(2025-yilgi ballar bilan solishtirganda)</i>\n"
        )

    lines.append("📊 <b>Minimal ballar (2025) bilan taqqoslash:</b>")
    if user_ball >= NATIONAL_GRANT_FLOOR:
        lines.append(f"🏆 Balingiz davlat granti minimal balidan "
                     f"(<b>{NATIONAL_GRANT_FLOOR:g}</b>) yuqori — grant tanlovida "
                     f"umumiy ishtirok etish imkoniyati bor.")
    elif user_ball >= NATIONAL_CONTRACT_FLOOR:
        lines.append(f"📄 Balingiz kontrakt minimal balidan (<b>{NATIONAL_CONTRACT_FLOOR:g}</b>) "
                     f"yuqori, lekin grant minimal balidan (<b>{NATIONAL_GRANT_FLOOR:g}</b>) past — "
                     f"faqat kontrakt asosida o'qish imkoniyati bor.")
    else:
        lines.append(f"⚠️ Balingiz kontrakt minimal balidan ham (<b>{NATIONAL_CONTRACT_FLOOR:g}</b>) "
                     f"past.")
    lines.append(
        "\n<i>ℹ️ Bu — Minimal grant o'tish balli, aniq yo'nalish bo'yicha "
        "grant balli emas.</i>"
    )
    lines.append(
        "<i>ℹ️ Yuqoridagi kontrakt ballari 2025-yilga oid — 2026-yilda "
        "o'zgarishi mumkin, faqat mo'ljal sifatida qarang.</i>"
    )

    if any((user_ball - m.con_b) < 0 for m in matched if m.matched and m.con_b is not None):
        lines.append(
            "\n💰 <b>Super-kontrakt (tabaqalashtirilgan to'lov) haqida:</b>\n"
            "O'tish balidan 4 ballgacha kam bo'lsa, oshirilgan to'lov-kontrakt bilan "
            "o'qishga kirish imkoniyati bor (2025-yil qoidasi):\n"
            "<blockquote>➡️ 1 ballgacha yetmasa — bazaviy narxning 1,5 barobari\n"
            "➡️ 1,01–2 ball — 2 barobari\n"
            "➡️ 2,01–3 ball — 2,5 barobari\n"
            "➡️ 3,01–4 ball — 3 barobari</blockquote>\n"
            "\n4 balldan ortiq yetmasa — bu holatda narxni OTM 2025-yildan beri "
            "mustaqil belgilaydi, biz hisoblay olmaymiz "
            "(<a href='https://t.me/nodavlattalim/4271'>manba</a>).\n"
            "\n<i>Bazaviy narxlar ham 2025/2026-yilga oid rasmiy jadvaldan — "
            "yo'nalish sohasi bo'yicha taxminiy hisoblangan, aniq raqamni "
            "OTM'ning o'zidan tasdiqlang.</i>"
        )

    if bot_username:
        lines.append(
            f"\n🤖 <i>Ma'lumotlar <a href='https://t.me/{bot_username}'>"
            f"@{bot_username}</a> orqali olindi.</i>"
        )
    return "\n".join(lines)
