"""webapp/db.py — read-only asyncpg pool va yordamchi funksiyalar.

Bot bilan bir xil .env dagi DB_* o'zgaruvchilardan ulanadi.
Webapp faqat o'qiydi — hech qanday yozuv qilmaydi.
"""
import os
import re
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

# Ishga tushirilgan joydan qat'i nazar (systemd, boshqa cwd) loyiha ildizidagi
# .env aniq topilsin — cwd-ga bog'liq load_dotenv() qidiruviga tayanmaymiz.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_pool: asyncpg.Pool | None = None

# DB'dagi nomi/un_text ichida turli apostrof belgilari (ʻ ʼ ' ’) aralash —
# qidiruvda ikkala tomonni ham normallashtirib solishtiramiz.
_APOSTROPHES = "ʼʻ''’‘`´ʹ"
SQL_NORM = "lower(translate({col}, 'ʼʻ''’‘`´ʹ', ''))"


def norm_query(q: str) -> str:
    return re.sub(f"[{_APOSTROPHES}]", "", q or "").lower().strip()


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            database=os.getenv("DB_NAME", "mandat"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            min_size=1,
            max_size=8,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def fetch(query: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)
