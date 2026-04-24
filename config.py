import os

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

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
db = psycopg2.connect(
    database=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
db.autocommit = True
sql = db.cursor()

# Backward-compatible aliases used by filter handlers
conn = db
cursor = sql

DB_POOL_MIN_CONN = int(os.getenv("DB_POOL_MIN_CONN", "1"))
DB_POOL_MAX_CONN = int(os.getenv("DB_POOL_MAX_CONN", "20"))
db_pool = SimpleConnectionPool(DB_POOL_MIN_CONN, DB_POOL_MAX_CONN, **DB_CONFIG)

ADMIN_ID = ADMINS = [int(admin_id) for admin_id in os.getenv("ADMINS_ID").split(",")]

# Referral / limit tizimi
MSG_LIMIT = int(os.getenv("MSG_LIMIT", "10"))                   # Bepul xabarlar soni
REQUIRED_REFERRALS = int(os.getenv("REQUIRED_REFERRALS", "2"))  # Cheksiz foydalanish uchun kerakli taklif soni

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(link_preview_is_disabled=True))
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    storage = RedisStorage.from_url(REDIS_URL)
else:
    storage = MemoryStorage()
dp = Dispatcher(storage=storage)