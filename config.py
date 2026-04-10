import os
import logging
from typing import Optional

import psycopg2
from psycopg2 import pool
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─── BOT ───────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ─── DATABASE ──────────────────────────────────────────────────────────
DB_NAME     = os.getenv("DB_NAME",     "example")
DB_USER     = os.getenv("DB_USER",     "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "parol")
DB_HOST     = os.getenv("DB_HOST",     "localhost")
DB_PORT     = os.getenv("DB_PORT",     "5432")

DB_CONFIG = {
    "dbname":   DB_NAME,
    "user":     DB_USER,
    "password": DB_PASSWORD,
    "host":     DB_HOST,
    "port":     DB_PORT,
}

# ─── CONNECTION POOL (50k+ user uchun) ────────────────────────────────
# minconn=5: bot ishga tushganda 5 ta tayyor connection
# maxconn=20: bir vaqtda maksimal 20 ta parallel so'rov
_db_pool: Optional[pool.ThreadedConnectionPool] = None


def get_pool() -> pool.ThreadedConnectionPool:
    """Global connection pool. Birinchi chaqiruvda yaratiladi."""
    global _db_pool
    if _db_pool is None or _db_pool.closed:
        _db_pool = pool.ThreadedConnectionPool(
            minconn=5,
            maxconn=20,
            **DB_CONFIG,
        )
        logger.info("PostgreSQL connection pool yaratildi (min=5, max=20)")  # noqa
    return _db_pool


def get_db_connection() -> psycopg2.extensions.connection:
    """
    Pool dan bitta connection oling.
    Ishlatib bo'lgach release_db_connection() ni chaqiring.
    Yoki context manager sifatida db_connection() ishlatish tavsiya etiladi.
    """
    return get_pool().getconn()


def release_db_connection(conn: psycopg2.extensions.connection) -> None:
    """Connectionni poolga qaytaradi."""
    try:
        get_pool().putconn(conn)
    except Exception as e:
        logger.error(f"Connection qaytarishda xato: {e}")


class db_connection:
    """
    Context manager: with db_connection() as (conn, cur): ...
    Avtomatik commit/rollback va connectionni poolga qaytaradi.

    Misol:
        async def some_func():
            with db_connection() as (conn, cur):
                cur.execute("SELECT ...")
                rows = cur.fetchall()
    """
    def __init__(self, autocommit: bool = False):
        self.autocommit = autocommit
        self.conn: Optional[psycopg2.extensions.connection] = None

    def __enter__(self):
        self.conn = get_db_connection()
        self.conn.autocommit = self.autocommit
        self.cur = self.conn.cursor()
        return self.conn, self.cur

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type:
                self.conn.rollback()
                logger.error(f"DB rollback: {exc_val}")
            else:
                if not self.autocommit:
                    self.conn.commit()
            self.cur.close()
            release_db_connection(self.conn)
        return False  # Exceptionni suppress qilmaymiz


# ─── LEGACY GLOBAL CURSOR (eski kod uchun, asta-sekin olib tashlanadi) ─
# DIQQAT: Bu faqat sinxron, oddiy so'rovlar uchun. Async broadcast da ishlatmang!
_legacy_conn  = psycopg2.connect(**DB_CONFIG)
_legacy_conn.autocommit = True
sql = _legacy_conn.cursor()
db  = _legacy_conn
conn   = _legacy_conn
cursor = sql

# ─── ADMINS ────────────────────────────────────────────────────────────
ADMIN_ID = ADMINS = [
    int(aid) for aid in os.getenv("ADMINS_ID", "").split(",") if aid.strip()
]

# ─── BOT & DISPATCHER ──────────────────────────────────────────────────
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(link_preview_is_disabled=True),
)
storage = MemoryStorage()
dp      = Dispatcher(storage=storage)