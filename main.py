import asyncio
import logging

from config import dp, bot, get_pool
from src.db.init_db import create_all_base
from src.handlers.admins.add_admin import add_router
from src.handlers.admins.admin import admin_router
from src.handlers.admins.messages import msg_router
from src.handlers.others.groups import group_router
from src.handlers.others.channels import channel_router
from src.handlers.others.other import other_router
from src.handlers.users.filter_ball import ball_router
from src.handlers.users.filter_fac import fac_router
from src.handlers.users.filter_reg import reg_router
from src.handlers.users.users import user_router
from src.middlewares.middleware import RegisterUserMiddleware


async def on_startup():
    """Bot ishga tushganda: jadvallarni yaratish, pool ni tekshirish."""
    get_pool()
    await create_all_base()
    logging.info("Bot ishga tushdi.")


async def on_shutdown():
    """Bot to'xtaganda: connectionlarni yopish."""
    pool = get_pool()
    if pool and not pool.closed:
        pool.closeall()
    logging.info("Pool yopildi.")


async def main():
    import sys

    # Windows cp1252 muammosini hal qilish: stdout/stderr ni UTF-8 ga o'tkazamiz
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            # Fayl handler — har doim UTF-8
            logging.FileHandler("bot.log", encoding="utf-8"),
            # Console handler — Windows uchun xavfsiz
            logging.StreamHandler(sys.stdout),
        ],
    )

    await on_startup()

    # Middleware
    dp.update.middleware(RegisterUserMiddleware())

    # Routerlar (tartibi muhim — spesifik birinchi, `other` oxirgi)
    dp.include_router(admin_router)
    dp.include_router(add_router)
    dp.include_router(msg_router)
    dp.include_router(user_router)
    dp.include_router(fac_router)
    dp.include_router(reg_router)
    dp.include_router(ball_router)
    dp.include_router(group_router)
    dp.include_router(channel_router)
    dp.include_router(other_router)

    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())