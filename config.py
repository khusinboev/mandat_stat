import os
import logging

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

# Referral / limit tizimi
MSG_LIMIT = int(os.getenv("MSG_LIMIT", "10"))                   # Bepul xabarlar soni
REQUIRED_REFERRALS = int(os.getenv("REQUIRED_REFERRALS", "2"))  # Cheksiz foydalanish uchun kerakli taklif soni

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
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    storage = RedisStorage.from_url(REDIS_URL)
else:
    storage = MemoryStorage()
dp = Dispatcher(storage=storage)