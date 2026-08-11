"""Tahlil qilib bo'lmagan qaydvaraqa PDF'larini boshqarish (qo'lda ishga
tushiriladi, cron YO'Q).

`src/handlers/users/qaydvaraqa.py`dagi `_log_failed_pdf` har bir
muvaffaqiyatsiz PDF haqida `qaydvaraqa_failures` jadvaliga (foydalanuvchi
hujjatining o'zidagi file_id bilan, qayta yuklashsiz) yozadi. Bu skript
o'sha yozuvlarni ko'rish, PDF'larni qayta yuklab olish (fayl qayta
so'ralmaydi — file_id orqali) va foydalanuvchiga tayyor shablon bilan
javob yuborishni avtomatlashtiradi.

Ishlatish (repo ildizidan, PYTHONPATH kerak emas — config import qiladi):
    .venv/bin/python -m scripts.qaydvaraqa_failures list
    .venv/bin/python -m scripts.qaydvaraqa_failures fetch --all
    .venv/bin/python -m scripts.qaydvaraqa_failures fetch --id 12
    .venv/bin/python -m scripts.qaydvaraqa_failures resolve --id 12 --category russian_fixed
    .venv/bin/python -m scripts.qaydvaraqa_failures resolve --id 13 --category custom --text "..."
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from config import bot
from src.db import database

OUT_DIR = Path("data/qaydvaraqa_failures")

_REMINDER = (
    "\n\n📌 Eslatma: to'g'ri hujjatda \"TANLANGAN TA'LIM YO'NALISHLARI\" "
    "qismida TANLAGAN universitet(lar)ingiz va yo'nalish(lar)ingiz ro'yxati "
    "aniq ko'rsatilgan bo'lishi kerak. Agar hujjatda bunday ro'yxat bo'lmasa "
    "— bu noto'g'ri hujjat yoki hali tanlov qilinmagan degani."
)

CATEGORY_MESSAGES = {
    "fixed": (
        "Assalomu alaykum! Avval yuborgan qaydvaraqangiz tizimimiz "
        "tomonidan o'qib bo'linmagan edi — buni tuzatdik, endi to'liq "
        "ishlaydi. Iltimos, o'sha qaydvaraqa faylini \"🔍 Mandat tahlili\" "
        "bo'limiga qayta yuboring."
    ),
    "ruxsatnoma": (
        "Assalomu alaykum! \"🔍 Mandat tahlili\" bo'limiga yuborgan "
        "faylingiz tekshirildi — bu \"Abituriyent ruxsatnomasi\" "
        "(imtihonga kirish ruxsatnomasi) ekan, bu bo'lim uchun kerakli "
        "hujjat emas.\n\nBizga \"Abituriyent qayd varaqasi\" kerak. Buni "
        "t.me/BaholashUz orqali yuklab olib, shu yerga qayta yuboring."
        + _REMINDER
    ),
    "test_answer": (
        "Assalomu alaykum! \"🔍 Mandat tahlili\" bo'limiga yuborgan "
        "faylingiz tekshirildi — bu test natijalaringiz (javoblar varag'i) "
        "ekan, bu bo'lim uchun kerakli hujjat emas.\n\nBizga \"Abituriyent "
        "qayd varaqasi\" kerak. Agar hali universitet/yo'nalish "
        "tanlamagan bo'lsangiz, avval buni BaholashUz saytida/botida "
        "bajaring, so'ng yangi qaydvaraqani yuklab olib, shu yerga "
        "yuboring." + _REMINDER
    ),
    "empty_choices": (
        "Assalomu alaykum! \"🔍 Mandat tahlili\" bo'limiga yuborgan "
        "qaydvaraqangiz tekshirildi — unda hali tanlovlar (universitet/"
        "yo'nalish) ko'rsatilmagan ekan. Bu hujjat tanlov qilishdan OLDIN "
        "yuklab olingan bo'lishi mumkin.\n\nTest natijalaridan so'ng 15 "
        "kun ichida universitet/yo'nalish tanlang, so'ng YANGI "
        "qaydvaraqani qayta yuklab olib, shu yerga yuboring." + _REMINDER
    ),
    "scanned": (
        "Assalomu alaykum! \"🔍 Mandat tahlili\" bo'limiga yuborgan "
        "faylingiz tekshirildi — bu skanerlangan rasm/skrinshot "
        "ko'rinishida ekan, tizimimiz buni hozircha o'qiy olmaydi.\n\n"
        "Iltimos, rasmiy saytdan (yoki t.me/BaholashUz) TO'G'RIDAN-TO'G'RI "
        "yuklab olingan asl PDF faylni yuboring (skrinshot yoki skan "
        "emas)."
    ),
}


async def cmd_list() -> None:
    rows = await database.fetchall(
        """SELECT id, user_id, user_full_name, username, filename, error_text, created_at
           FROM public.qaydvaraqa_failures WHERE resolved_at IS NULL
           ORDER BY created_at"""
    )
    if not rows:
        print("Hal qilinmagan yozuv yo'q.")
        return
    for r in rows:
        fid, user_id, name, username, filename, err, created = r
        uname = f"@{username}" if username else ""
        print(f"[{fid}] {created} | {name} {uname} (ID: {user_id})")
        print(f"      fayl: {filename}")
        print(f"      xato: {err}")
        print()


async def _fetch_one(row: tuple) -> None:
    fid, user_id, name, username, filename, file_id, err, created = row
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    buf = await bot.download(file_id)
    safe_name = (filename or f"qaydvaraqa_{fid}.pdf").replace("/", "_")
    dest = OUT_DIR / f"{fid}_{safe_name}"
    dest.write_bytes(buf.read())
    uname = f"@{username}" if username else ""
    print(f"[{fid}] {name} {uname} (ID: {user_id}) -> {dest}")
    print(f"      xato: {err}")


async def cmd_fetch(ids: list[int] | None) -> None:
    if ids:
        placeholders = ",".join(["%s"] * len(ids))
        rows = await database.fetchall(
            f"""SELECT id, user_id, user_full_name, username, filename, file_id,
                       error_text, created_at
                FROM public.qaydvaraqa_failures WHERE id IN ({placeholders})""",
            tuple(ids),
        )
    else:
        rows = await database.fetchall(
            """SELECT id, user_id, user_full_name, username, filename, file_id,
                      error_text, created_at
               FROM public.qaydvaraqa_failures WHERE resolved_at IS NULL
               ORDER BY created_at"""
        )
    if not rows:
        print("Yuklab olinadigan yozuv yo'q.")
        return
    for row in rows:
        await _fetch_one(row)
    print(f"\nJami {len(rows)} ta fayl {OUT_DIR}/ ichiga yuklandi.")


async def cmd_resolve(failure_id: int, category: str, custom_text: str | None) -> None:
    if category == "custom":
        if not custom_text:
            print("XATO: --category custom uchun --text majburiy.")
            return
        text = custom_text
    else:
        text = CATEGORY_MESSAGES.get(category)
        if text is None:
            print(f"XATO: noma'lum kategoriya: {category}")
            print(f"Mavjud kategoriyalar: {', '.join(CATEGORY_MESSAGES)}, custom")
            return

    row = await database.fetchone(
        "SELECT user_id, user_full_name, username FROM public.qaydvaraqa_failures WHERE id=%s",
        (failure_id,),
    )
    if not row:
        print(f"XATO: id={failure_id} topilmadi.")
        return
    user_id, name, username = row

    await bot.send_message(chat_id=user_id, text=text)
    await database.execute(
        "UPDATE public.qaydvaraqa_failures SET resolved_at=NOW(), resolution_category=%s WHERE id=%s",
        (category, failure_id),
    )
    uname = f"@{username}" if username else ""
    print(f"OK: [{failure_id}] {name} {uname} (ID: {user_id}) ga '{category}' xabari yuborildi.")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Hal qilinmagan yozuvlarni ko'rsatadi")

    p_fetch = sub.add_parser("fetch", help="PDF'larni qayta yuklab oladi")
    p_fetch.add_argument("--id", type=int, action="append", dest="ids", help="Faqat shu id (takror berish mumkin)")
    p_fetch.add_argument("--all", action="store_true", help="Barcha hal qilinmaganlarni yuklaydi")

    p_resolve = sub.add_parser("resolve", help="Foydalanuvchiga javob yuboradi va hal qilingan deb belgilaydi")
    p_resolve.add_argument("--id", type=int, required=True)
    p_resolve.add_argument("--category", required=True, choices=[*CATEGORY_MESSAGES, "custom"])
    p_resolve.add_argument("--text", help="--category custom uchun matn")

    args = parser.parse_args()

    if args.command == "list":
        await cmd_list()
    elif args.command == "fetch":
        await cmd_fetch(args.ids if args.ids else None)
    elif args.command == "resolve":
        await cmd_resolve(args.id, args.category, args.text)

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
