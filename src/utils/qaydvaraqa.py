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


def _strip_apos(text: Optional[str]) -> str:
    return _norm(text).replace("'", "")


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


class QaydvaraqaParseError(Exception):
    """PDF matni kutilgan qayd varaqa tuzilishiga mos kelmadi."""


_RANK_TY_RE = re.compile(r"^(\d+)\s*(Kunduzgi|Kechki|Masofaviy)\s*$", re.IGNORECASE)
_FIO_RE = re.compile(r"F\.I\.O\.:\s*(.+)")
_LANG_RE = re.compile(r"Ta['ʻʼ`‘’]lim tili:\s*(\S+)")


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
    except QaydvaraqaParseError:
        raise
    except Exception as exc:
        raise QaydvaraqaParseError(f"PDF ochilmadi: {exc}") from exc

    fio_m = _FIO_RE.search(text)
    fio = fio_m.group(1).strip() if fio_m else None

    lang_m = _LANG_RE.search(text)
    lang_raw = lang_m.group(1).strip() if lang_m else None

    choices: list[RawChoice] = []
    for table in tables:
        for row in table:
            cell = (row[0] or "") if row else ""
            parts = [p.strip() for p in cell.split("\n") if p.strip()]
            if len(parts) < 3:
                continue
            m = _RANK_TY_RE.match(parts[1])
            if not m:
                continue
            choices.append(RawChoice(
                rank=int(m.group(1)), ty_text_raw=m.group(2),
                university_raw=parts[0], direction_raw=parts[2],
            ))

    if not choices:
        raise QaydvaraqaParseError(
            "Tanlovlar jadvali topilmadi — bu qaydvaraqa fayliga o'xshamaydi"
        )
    choices.sort(key=lambda c: c.rank)
    return QaydvaraqaData(fio=fio, lang_raw=lang_raw, choices=choices)


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


def format_report(matched: list[MatchedChoice], user_ball: float) -> str:
    """Chiroyli, tartibli HTML hisobot — har bir tanlov uchun aniq
    kirish/kirolmaslik + milliy chegaralarga nisbatan umumiy holat."""
    lines: list[str] = []

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
        lines.append(
            f"{icon} <b>{m.rank}-tanlov</b> ({m.ty_text})\n"
            f"   🏛 {_clean_uni(m.un_text)}\n"
            f"   📚 {m.nomi} — {m.lan_text}\n"
            f"   📈 2025 kontrakt balli: <b>{m.con_b:g}</b> "
            f"(sizda {sign}{gap:.1f})\n"
        )

    if unmatched:
        lines.append("⚠️ <b>Bazamizda aniqlanmagan tanlovlar:</b>")
        for m in unmatched:
            lines.append(f"   {m.rank}-tanlov — {_clean_uni(m.university_raw)} "
                         f"({m.unmatch_reason})")
        lines.append("")

    lines.append("—" * 20)
    lines.append("📊 <b>Milliy minimal ballar (2025) bilan taqqoslash:</b>")
    if user_ball >= NATIONAL_GRANT_FLOOR:
        lines.append(f"🏆 Balingiz davlat granti milliy minimal balidan "
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
        "\n<i>ℹ️ Bu — milliy UMUMIY chegara, aniq yo'nalish bo'yicha grant balli "
        "emas (bazamizda grant balllari mavjud emas). Yuqoridagi kontrakt "
        "ballari 2025-yilga oid — 2026-yilda o'zgarishi mumkin, faqat mo'ljal "
        "sifatida qarang.</i>"
    )
    return "\n".join(lines)
