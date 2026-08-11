import os
import logging
import time

import psycopg2
from psycopg2 import InterfaceError, OperationalError
from psycopg2.pool import SimpleConnectionPool
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")


def env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

DB_CONFIG = {
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "host": DB_HOST,
    "port": DB_PORT
}

logger = logging.getLogger(__name__)


def _open_raw_connection():
    raw = psycopg2.connect(
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )
    raw.autocommit = True
    return raw


_raw_db = _open_raw_connection()
_raw_sql = _raw_db.cursor()


def _reconnect_raw() -> None:
    global _raw_db, _raw_sql
    try:
        if _raw_sql is not None and not _raw_sql.closed:
            _raw_sql.close()
    except Exception:
        pass
    try:
        if _raw_db is not None and not _raw_db.closed:
            _raw_db.close()
    except Exception:
        pass

    _raw_db = _open_raw_connection()
    _raw_sql = _raw_db.cursor()
    logger.warning("DB connection re-established after cursor/connection closure")


def _ensure_raw_connection():
    global _raw_db, _raw_sql
    if _raw_db is None or _raw_db.closed:
        _reconnect_raw()
    elif _raw_sql is None or _raw_sql.closed:
        _raw_sql = _raw_db.cursor()


class CursorProxy:
    def _raw_cursor(self):
        _ensure_raw_connection()
        return _raw_sql

    def execute(self, query, vars=None):
        try:
            return self._raw_cursor().execute(query, vars)
        except (InterfaceError, OperationalError):
            _reconnect_raw()
            return self._raw_cursor().execute(query, vars)

    def executemany(self, query, vars_list):
        try:
            return self._raw_cursor().executemany(query, vars_list)
        except (InterfaceError, OperationalError):
            _reconnect_raw()
            return self._raw_cursor().executemany(query, vars_list)

    def fetchone(self):
        return self._raw_cursor().fetchone()

    def fetchall(self):
        return self._raw_cursor().fetchall()

    def fetchmany(self, size=None):
        if size is None:
            return self._raw_cursor().fetchmany()
        return self._raw_cursor().fetchmany(size)

    @property
    def closed(self):
        return self._raw_cursor().closed

    def close(self):
        try:
            self._raw_cursor().close()
        except Exception:
            pass

    def __getattr__(self, item):
        return getattr(self._raw_cursor(), item)


class ConnectionProxy:
    def _raw_connection(self):
        _ensure_raw_connection()
        return _raw_db

    @property
    def autocommit(self):
        return self._raw_connection().autocommit

    @autocommit.setter
    def autocommit(self, value):
        self._raw_connection().autocommit = value

    @property
    def closed(self):
        return self._raw_connection().closed

    def cursor(self, *args, **kwargs):
        try:
            return self._raw_connection().cursor(*args, **kwargs)
        except (InterfaceError, OperationalError):
            _reconnect_raw()
            return self._raw_connection().cursor(*args, **kwargs)

    def commit(self):
        try:
            return self._raw_connection().commit()
        except (InterfaceError, OperationalError):
            _reconnect_raw()
            return self._raw_connection().commit()

    def rollback(self):
        try:
            return self._raw_connection().rollback()
        except (InterfaceError, OperationalError):
            _reconnect_raw()
            return self._raw_connection().rollback()

    def close(self):
        try:
            return self._raw_connection().close()
        except Exception:
            return None

    def __getattr__(self, item):
        return getattr(self._raw_connection(), item)


# Backward-compatible proxies used across handlers
db = ConnectionProxy()
sql = CursorProxy()
conn = db
cursor = sql

DB_POOL_MIN_CONN = int(os.getenv("DB_POOL_MIN_CONN", "1"))
DB_POOL_MAX_CONN = int(os.getenv("DB_POOL_MAX_CONN", "20"))
db_pool = SimpleConnectionPool(DB_POOL_MIN_CONN, DB_POOL_MAX_CONN, **DB_CONFIG)

ADMIN_ID = ADMINS = [int(admin_id) for admin_id in os.getenv("ADMINS_ID").split(",")]

# Qaydvaraqa (PDF) tahlil qilinmasa, faylning o'zi shu chat'ga yuboriladi —
# yangi/kutilmagan PDF formatlarini foydalanuvchi shikoyat qilishini
# kutmasdan tez payqash uchun. Bo'sh qoldirilsa (masalan "0") bu funksiya
# o'chadi.
QAYDVARAQA_REPORT_CHAT_ID = int(os.getenv("QAYDVARAQA_REPORT_CHAT_ID", "5246872049"))

# Referral / limit tizimi
REFERRAL_SYSTEM_ENABLED = env_bool("REFERRAL_SYSTEM_ENABLED", "true")
MSG_LIMIT = int(os.getenv("MSG_LIMIT", "10"))                   # Bepul xabarlar soni
REQUIRED_REFERRALS = int(os.getenv("REQUIRED_REFERRALS", "2"))  # Cheksiz foydalanish uchun kerakli taklif soni

_SETTINGS_CACHE_TTL_SECONDS = 5.0
_settings_cache: dict[str, tuple[str, float]] = {}


def _ensure_runtime_settings_table() -> None:
    sql.execute(
        """
        CREATE TABLE IF NOT EXISTS public.runtime_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT now()
        )
        """
    )


def _get_runtime_setting(key: str, default: str) -> str:
    now = time.monotonic()
    cached = _settings_cache.get(key)
    if cached and now - cached[1] < _SETTINGS_CACHE_TTL_SECONDS:
        return cached[0]

    try:
        _ensure_runtime_settings_table()
        sql.execute("SELECT value FROM public.runtime_settings WHERE key=%s", (key,))
        row = sql.fetchone()
        value = row[0] if row else default
    except Exception:
        value = default

    _settings_cache[key] = (value, now)
    return value


def set_runtime_setting(key: str, value: str) -> None:
    _ensure_runtime_settings_table()
    sql.execute(
        """
        INSERT INTO public.runtime_settings (key, value)
        VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            updated_at = now()
        """,
        (key, value),
    )
    _settings_cache[key] = (value, time.monotonic())


def is_referral_system_enabled() -> bool:
    value = _get_runtime_setting(
        "referral_system_enabled",
        "true" if REFERRAL_SYSTEM_ENABLED else "false",
    )
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def set_referral_system_enabled(enabled: bool) -> None:
    set_runtime_setting("referral_system_enabled", "true" if enabled else "false")

# Quiz import sozlamalari
AUTO_IMPORT_QUIZ = env_bool("AUTO_IMPORT_QUIZ", "false")
QUIZ_IMPORT_SKIP_ON_HASH_MATCH = env_bool("QUIZ_IMPORT_SKIP_ON_HASH_MATCH", "true")

QUIZ_SOURCE_DB_CONFIG = {
    "dbname": os.getenv("QUES_BOT_DB_NAME", DB_NAME),
    "user": os.getenv("QUES_BOT_DB_USER", DB_USER),
    "password": os.getenv("QUES_BOT_DB_PASSWORD", DB_PASSWORD),
    "host": os.getenv("QUES_BOT_DB_HOST", DB_HOST),
    "port": os.getenv("QUES_BOT_DB_PORT", DB_PORT),
}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(link_preview_is_disabled=True))

# O'tish ballari Telegram Mini WebApp (ixtiyoriy). Bo'sh bo'lsa webapp tugmasi ko'rsatilmaydi.
# Telegram web_app tugmalari faqat HTTPS URL bilan ishlaydi.
WEBAPP_URL = os.getenv("WEBAPP_URL", "")

# Shu bot instansiyasining @username'i (original va klon uchun alohida).
# Webapp'dagi "ulashish" tugmasi qaysi botga qaytishni bilishi uchun WEBAPP_URL'ga
# query parametr sifatida qo'shiladi; caption'lardagi hardcoded havolalar o'rniga ham ishlatiladi.
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

# nodavlattalim.uz portalidagi "O'tish ballari" bo'limi havolasi (ixtiyoriy).
# Bo'sh bo'lsa tugma ko'rsatilmaydi — botni portalga funnel qilish uchun.
PORTAL_OTISH_URL = os.getenv("PORTAL_OTISH_URL", "")

REDIS_URL = os.getenv("REDIS_URL")

# "Mandat saytdagi o'rni" va "Balingizga mos yo'nalish" bo'limlari keshni
# Redis'da saqlaydi (src/utils/orin.py, ballinfo.py). Bir Redis serverida
# bir nechta bot ishlaganda kalitlar aralashmasligi uchun har biri o'z
# DB raqamiga ega bo'ladi. REDIS_URL berilgan bo'lsa, raqam o'shandan olinadi.
def _redis_db_from_url(url: str | None, default: int = 0) -> int:
    if not url:
        return default
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else default


REDIS_DB = int(os.getenv("REDIS_DB", _redis_db_from_url(REDIS_URL, 0)))

if REDIS_URL:
    storage = RedisStorage.from_url(REDIS_URL)
else:
    storage = MemoryStorage()
dp = Dispatcher(storage=storage)