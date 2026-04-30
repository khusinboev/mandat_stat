import asyncio
import logging

from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import ErrorEvent

from config import (
    AUTO_IMPORT_QUIZ,
    QUIZ_IMPORT_SKIP_ON_HASH_MATCH,
    QUIZ_SOURCE_DB_CONFIG,
    db,
    dp,
    bot,
)
from src.db.init_db import create_all_base
from src.db.quiz_importer import import_quiz_data_from_source
from src.handlers.admins.add_admin import add_router
from src.handlers.admins.admin import admin_router
from src.handlers.admins.messages import msg_router
from src.handlers.others.groups import group_router
from src.handlers.others.channels import channel_router
from src.handlers.others.other import other_router
from src.handlers.users.filter_ball import ball_router
from src.handlers.users.filter_fac import fac_router
from src.handlers.users.filter_reg import reg_router
from src.handlers.users.tests import test_router
from src.handlers.users.users import user_router
from src.middlewares.middleware import RegisterUserMiddleware, PerformanceMiddleware


async def on_startup():
    await create_all_base()
    if AUTO_IMPORT_QUIZ:
        ok, msg, rows = await import_quiz_data_from_source(
            target_conn=db,
            source_db_config=QUIZ_SOURCE_DB_CONFIG,
            skip_on_hash_match=QUIZ_IMPORT_SKIP_ON_HASH_MATCH,
        )
        level = logging.INFO if ok else logging.ERROR
        logging.log(level, "%s (rows=%s)", msg, rows)


@dp.errors()
async def global_error_handler(event: ErrorEvent) -> bool:
    exc = event.exception
    if isinstance(exc, TelegramForbiddenError):
        # Foydalanuvchi botni bloklagan — jim o'tkazib yuboramiz
        logging.debug("Bot blocked by user: %s", exc)
        return True
    if isinstance(exc, TelegramBadRequest):
        logging.warning("TelegramBadRequest: %s", exc)
        return True
    logging.exception("Unhandled error: %s", exc)
    return False


async def main():
    await on_startup()
    logging.basicConfig(level=logging.INFO)

    dp.update.middleware(RegisterUserMiddleware())
    dp.update.middleware(PerformanceMiddleware())

    dp.include_router(admin_router)
    dp.include_router(add_router)
    dp.include_router(msg_router)
    dp.include_router(user_router)
    dp.include_router(test_router)
    dp.include_router(fac_router)
    dp.include_router(reg_router)
    dp.include_router(ball_router)
    dp.include_router(group_router)
    dp.include_router(channel_router)
    dp.include_router(other_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())