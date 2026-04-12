from aiogram.types import Update
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from datetime import datetime
import logging
import os
import time
import pytz
from config import db_pool


logger = logging.getLogger(__name__)
SLOW_UPDATE_MS = float(os.getenv("SLOW_UPDATE_MS", "700"))

class RegisterUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        if not event.message:
            return await handler(event, data)  # Middleware davom etsin

        user = event.message.from_user
        user_id = user.id
        date = datetime.now(pytz.timezone("Asia/Tashkent")).date()
        lang_code = user.language_code if user.language_code else "uz"

        conn = None
        cur = None
        try:
            conn = db_pool.getconn()
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM public.accounts WHERE user_id = %s", (user_id,))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO public.accounts (user_id, lang_code, date) VALUES (%s, %s, %s)",
                    (user_id, lang_code, date),
                )
                conn.commit()
        finally:
            if cur is not None:
                cur.close()
            if conn is not None:
                db_pool.putconn(conn)

        return await handler(event, data)  # Middleware davom etadi


class PerformanceMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        started_at = time.perf_counter()
        result = await handler(event, data)
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        if elapsed_ms >= SLOW_UPDATE_MS:
            user_id = None
            if getattr(event, "message", None) and event.message.from_user:
                user_id = event.message.from_user.id
            logger.warning("Slow update detected: %.2fms user_id=%s", elapsed_ms, user_id)

        return result