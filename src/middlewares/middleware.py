import logging
from aiogram.types import Update
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from src.db.init_db import register_user

logger = logging.getLogger(__name__)


class RegisterUserMiddleware(BaseMiddleware):
    """
    Har bir message kelganda foydalanuvchini bazaga ro'yxatdan o'tkazadi.
    Connection pool ishlatadi — 50k+ user uchun xavfsiz.
    """

    async def __call__(self, handler, event: Update, data: dict):
        if not event.message:
            return await handler(event, data)

        user = event.message.from_user
        if not user:
            return await handler(event, data)

        try:
            is_new = await register_user(
                user_id=user.id,
                lang_code=user.language_code or "uz",
            )
            if is_new:
                logger.info(f"Yangi foydalanuvchi: {user.id} ({user.username})")
        except Exception as e:
            # Middleware xatosi butun botni to'xtatmasin
            logger.error(f"RegisterUserMiddleware xato: {e}")

        return await handler(event, data)
