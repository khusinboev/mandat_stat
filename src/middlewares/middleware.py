from aiogram.types import Update, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from datetime import datetime
from urllib.parse import quote
import logging
import os
import time
import pytz
from config import db_pool, ADMIN_ID, bot, MSG_LIMIT, REQUIRED_REFERRALS


logger = logging.getLogger(__name__)
SLOW_UPDATE_MS = float(os.getenv("SLOW_UPDATE_MS", "700"))

# Bot username keshi (bir marta olinadi, keyin qayta ishlatiladi)
_BOT_USERNAME: str | None = None


async def _get_bot_username() -> str:
    global _BOT_USERNAME
    if not _BOT_USERNAME:
        me = await bot.get_me()
        _BOT_USERNAME = me.username
    return _BOT_USERNAME


def _limit_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    share_url = f"https://t.me/share/url?url={quote(ref_link, safe='')}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=share_url)],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_referral")],
    ])


class RegisterUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        # Foydalanuvchi va hodisa turini aniqlash
        user = None
        is_message = False
        is_inline = False

        if event.message and event.message.from_user:
            user = event.message.from_user
            is_message = True
        elif event.inline_query and event.inline_query.from_user:
            user = event.inline_query.from_user
            is_inline = True
        else:
            # callback_query va boshqa turlar — limitdan o'tadi (check_referral tugmasi ishlashi uchun)
            return await handler(event, data)

        user_id = user.id
        lang_code = user.language_code or "uz"
        date = datetime.now(pytz.timezone("Asia/Tashkent")).date()

        # Adminlar ham accounts jadvaliga yoziladi (statistika uchun),
        # lekin ular uchun limit qo'llanmaydi.
        is_admin = user_id in ADMIN_ID

        # DB: ro'yxatdan o'tkazish + msg_count yangilash
        msg_count = 0
        referral_count = 0
        conn = None
        cur = None
        try:
            conn = db_pool.getconn()
            cur = conn.cursor()
            cur.execute(
                "SELECT msg_count, referral_count FROM public.accounts WHERE user_id=%s LIMIT 1",
                (user_id,)
            )
            row = cur.fetchone()
            if row is None:
                # Yangi foydalanuvchi — birinchi xabar hisoblanadi
                count_val = 1 if is_message else 0
                cur.execute(
                    "INSERT INTO public.accounts (user_id, lang_code, date, msg_count, referral_count) "
                    "VALUES (%s, %s, %s, %s, 0)",
                    (user_id, lang_code, date, count_val),
                )
                conn.commit()
                msg_count = count_val
                referral_count = 0
            else:
                msg_count, referral_count = row
                if is_message and msg_count <= MSG_LIMIT:
                    msg_count += 1
                    cur.execute(
                        "UPDATE public.accounts SET msg_count=%s WHERE user_id=%s",
                        (msg_count, user_id),
                    )
                    conn.commit()
        except Exception as e:
            logger.error("RegisterUserMiddleware DB xatosi: %s", e)
        finally:
            if cur:
                cur.close()
            if conn:
                db_pool.putconn(conn)

        # /start buyruq har doim o'tadi — referral payload qayta ishlashi uchun
        if is_message and event.message.text and event.message.text.startswith("/start"):
            return await handler(event, data)

        # Limit tekshiruvi
        is_limited = (not is_admin) and msg_count > MSG_LIMIT and referral_count < REQUIRED_REFERRALS

        if is_limited:
            if is_inline:
                try:
                    await event.inline_query.answer(
                        results=[],
                        cache_time=0,
                        is_personal=True,
                        switch_pm_text="⛔ Limit tugadi! Botga o'ting",
                        switch_pm_parameter="ref_check",
                    )
                except Exception:
                    pass
                return

            if is_message:
                # Joriy FSM holatini tozalash
                fsm = data.get("state")
                if fsm:
                    try:
                        await fsm.clear()
                    except Exception:
                        pass

                username = await _get_bot_username()
                ref_link = f"https://t.me/{username}?start=ref_{user_id}"
                remaining = REQUIRED_REFERRALS - referral_count

                await event.message.answer(
                    f"⛔ <b>Siz {MSG_LIMIT} ta xabar limitini tugatdingiz!</b>\n\n"
                    f"Botdan foydalanishni davom ettirish uchun "
                    f"<b>{REQUIRED_REFERRALS} ta</b> do'stingizni quyidagi referal havola "
                    f"orqali taklif qiling:\n\n"
                    f"<code>{ref_link}</code>\n\n"
                    f"👥 Taklif qilganlar: <b>{referral_count}/{REQUIRED_REFERRALS}</b>\n"
                    f"➡️ Yana <b>{remaining}</b> ta kishi taklif qiling",
                    parse_mode="html",
                    reply_markup=_limit_keyboard(ref_link),
                )
                return

        return await handler(event, data)


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