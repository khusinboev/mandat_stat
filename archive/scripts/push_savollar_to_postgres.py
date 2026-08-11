#!/usr/bin/env python3
"""
SQLite savollar.db → PostgreSQL public.{math,literature,history} ko'chirmasi.

Faqat SQLite da mavjud bo'lib, Postgresda yo'q bo'lgan qatorlarni qo'shadi.
Takroran ishlatish xavfsiz (idempotent): allaqachon kiritilganlar o'tkazib yuboriladi.

Ishlatish:
    python scripts/push_savollar_to_postgres.py
    python scripts/push_savollar_to_postgres.py --dry-run        # faqat ko'rish
    python scripts/push_savollar_to_postgres.py --table math     # faqat bitta jadvalni
    python scripts/push_savollar_to_postgres.py --varyant 6      # faqat bitta variantni
"""
import argparse
import sqlite3
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import os

# .env faylini yuklash
load_dotenv(Path(__file__).parent.parent / ".env")

SQLITE_DB = Path(__file__).parent.parent / "src" / "db" / "savollar.db"
TABLES = ("literature", "math", "history")


def get_pg_conn():
    return psycopg2.connect(
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )


def existing_pg_keys(pg_cur, table: str) -> set:
    """Postgresda allaqachon mavjud (varyant, photo) juftlarini oladi."""
    pg_cur.execute(f"SELECT varyant::text, photo FROM public.{table}")
    return {(str(r[0]), r[1]) for r in pg_cur.fetchall()}


def push_table(sqlite_conn, pg_conn, table: str, varyant_filter=None, dry_run=False):
    sq_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()

    query = f"SELECT photo, answer, varyant, status FROM {table}"
    params = []
    if varyant_filter is not None:
        query += " WHERE varyant = ?"
        params.append(varyant_filter)
    sq_cur.execute(query, params)
    rows = sq_cur.fetchall()

    if not rows:
        print(f"  [{table}] SQLite bo'sh — o'tkazib yuborildi")
        return 0

    existing = existing_pg_keys(pg_cur, table)

    to_insert = []
    skipped = 0
    for photo, answer, varyant, status in rows:
        key = (str(varyant), photo)
        if key in existing:
            skipped += 1
            continue
        # Bot diskdan rasm olishi uchun file_id har doim bo'sh saqlanadi.
        to_insert.append((str(varyant), answer, None, status or "True", photo))

    print(f"  [{table}] Jami: {len(rows)} | Mavjud: {skipped} | Yangi: {len(to_insert)}")

    if not to_insert:
        return 0

    if dry_run:
        print(f"  [{table}] DRY-RUN: {len(to_insert)} qator kiritilmas edi")
        return len(to_insert)

    execute_values(
        pg_cur,
        f"INSERT INTO public.{table} (varyant, answer, file_id, status, photo) VALUES %s",
        to_insert,
        page_size=500,
    )
    pg_conn.commit()
    print(f"  [{table}] ✅ {len(to_insert)} qator kiritildi")
    return len(to_insert)


def main():
    parser = argparse.ArgumentParser(description="savollar.db → PostgreSQL push")
    parser.add_argument("--dry-run", action="store_true", help="Amalda kiritmasdan ko'rsatish")
    parser.add_argument("--table", choices=TABLES, help="Faqat shu jadvalni ishlatish")
    parser.add_argument("--varyant", type=int, help="Faqat shu variant raqamini kiritish")
    args = parser.parse_args()

    if not SQLITE_DB.exists():
        raise FileNotFoundError(f"SQLite DB topilmadi: {SQLITE_DB}")

    tables = [args.table] if args.table else list(TABLES)

    sqlite_conn = sqlite3.connect(SQLITE_DB)
    pg_conn = get_pg_conn()

    total = 0
    try:
        for table in tables:
            total += push_table(
                sqlite_conn, pg_conn, table,
                varyant_filter=args.varyant,
                dry_run=args.dry_run,
            )
    finally:
        sqlite_conn.close()
        pg_conn.close()

    if args.dry_run:
        print(f"\nDRY-RUN: Jami {total} yangi qator topildi (kiritilmadi)")
    else:
        print(f"\nJami {total} yangi qator PostgreSQL ga kiritildi")


if __name__ == "__main__":
    main()
