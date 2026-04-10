import logging
from aiogram import Bot
from aiogram.filters import BaseFilter
from aiogram.types import (
    CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, User, Message
)

from config import db_connection, bot, ADMIN_ID

logger = logging.getLogger(__name__)


class CheckData:
    """Kanal a'zoligini tekshirish."""

    @staticmethod
    async def check_member(bot: Bot, user_id: int):
        """
        1-guruh kanallarini tekshiradi.
        Qaytaradi: (barcha_kanallarda_a'zo: bool, yetishmayotgan_kanallar: list)
        """
        with db_connection() as (conn, cur):
            cur.execute("SELECT chat_id FROM public.mandatorys")
            mandatory = cur.fetchall()

        if not mandatory:
            return True, []

        if user_id in ADMIN_ID:
            return True, []

        missing = []
        for (chat_id,) in mandatory:
            try:
                member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                if member.status == "left":
                    missing.append(chat_id)
            except Exception as e:
                logger.warning(f"check_member xato (chat={chat_id}): {e}")

        return len(missing) == 0, missing

    @staticmethod
    async def channels_btn(channels: list) -> InlineKeyboardMarkup:
        keyboard = []
        with db_connection() as (conn, cur):
            for index, channel_id in enumerate(channels, 1):
                cur.execute(
                    "SELECT username FROM public.mandatorys WHERE chat_id = %s",
                    (channel_id,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    keyboard.append([
                        InlineKeyboardButton(
                            text=f"📢 Kanal-{index}",
                            url=row[0]
                        )
                    ])
        keyboard.append([InlineKeyboardButton(text="✅Qo'shildim", callback_data="check")])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    async def check_member2(bot: Bot, user_id: int):
        """
        2-guruh kanallarini tekshiradi.
        """
        with db_connection() as (conn, cur):
            cur.execute("SELECT chat_id FROM public.kanallar2")
            mandatory = cur.fetchall()

        if not mandatory:
            return True, []

        if user_id in ADMIN_ID:
            return True, []

        missing = []
        for (chat_id,) in mandatory:
            try:
                member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                if member.status == "left":
                    missing.append(chat_id)
            except Exception as e:
                logger.warning(f"check_member2 xato (chat={chat_id}): {e}")

        return len(missing) == 0, missing

    @staticmethod
    async def channels_btn2(channels: list) -> InlineKeyboardMarkup:
        keyboard = []
        with db_connection() as (conn, cur):
            for index, channel_id in enumerate(channels, 1):
                cur.execute(
                    "SELECT username FROM public.kanallar2 WHERE chat_id = %s",
                    (channel_id,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    keyboard.append([
                        InlineKeyboardButton(
                            text=f"📢 Kanal-{index}",
                            url=row[0]
                        )
                    ])
        keyboard.append([InlineKeyboardButton(text="✅Qo'shildim", callback_data="check2")])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)


class PanelFunc:
    """Admin panel funksiyalari."""

    @staticmethod
    async def channel_add(chat_id: int, link: str):
        with db_connection() as (conn, cur):
            cur.execute(
                "INSERT INTO public.mandatorys (chat_id, username) VALUES (%s, %s) "
                "ON CONFLICT (chat_id) DO UPDATE SET username = EXCLUDED.username",
                (chat_id, link)
            )

    @staticmethod
    async def channel_delete(chat_id: int):
        with db_connection() as (conn, cur):
            cur.execute(
                "DELETE FROM public.mandatorys WHERE chat_id = %s",
                (chat_id,)
            )

    @staticmethod
    async def channel_list() -> str:
        with db_connection() as (conn, cur):
            cur.execute("SELECT chat_id, username FROM public.mandatorys")
            rows = cur.fetchall()

        result = ""
        for chat_id, username in rows:
            try:
                chat = await bot.get_chat(chat_id=chat_id)
                result += (
                    f"------------------------------------------------\n"
                    f"Kanal: @{chat.username}\n"
                    f"Nomi: {chat.title}\n"
                    f"ID: {chat_id}\n"
                    f"Havola: {username}\n"
                )
            except Exception as e:
                result += f"ID: {chat_id} — botni admin qiling\nXato: {e}\n\n"
        return result

    @staticmethod
    async def channel_add2(chat_id: int, link: str):
        with db_connection() as (conn, cur):
            cur.execute(
                "INSERT INTO public.kanallar2 (chat_id, username) VALUES (%s, %s) "
                "ON CONFLICT (chat_id) DO UPDATE SET username = EXCLUDED.username",
                (chat_id, link)
            )

    @staticmethod
    async def channel_delete2(chat_id: int):
        with db_connection() as (conn, cur):
            cur.execute(
                "DELETE FROM public.kanallar2 WHERE chat_id = %s",
                (chat_id,)
            )

    @staticmethod
    async def channel_list2() -> str:
        with db_connection() as (conn, cur):
            cur.execute("SELECT chat_id, username FROM public.kanallar2")
            rows = cur.fetchall()

        result = ""
        for chat_id, username in rows:
            try:
                chat = await bot.get_chat(chat_id=chat_id)
                result += (
                    f"------------------------------------------------\n"
                    f"Kanal: @{chat.username}\n"
                    f"Nomi: {chat.title}\n"
                    f"ID: {chat_id}\n"
                    f"Havola: {username}\n"
                )
            except Exception as e:
                result += f"ID: {chat_id} — botni admin qiling\nXato: {e}\n\n"
        return result

    @staticmethod
    async def admin_add(user_id: int):
        with db_connection() as (conn, cur):
            cur.execute(
                "INSERT INTO public.admins (user_id) VALUES (%s) "
                "ON CONFLICT (user_id) DO NOTHING",
                (user_id,)
            )

    @staticmethod
    async def admin_delete(user_id: int):
        with db_connection() as (conn, cur):
            cur.execute(
                "DELETE FROM public.admins WHERE user_id = %s",
                (user_id,)
            )

    @staticmethod
    async def admin_list() -> str:
        with db_connection() as (conn, cur):
            cur.execute("SELECT user_id FROM public.admins")
            rows = cur.fetchall()

        result = ""
        for (user_id,) in rows:
            try:
                user: User = await bot.get_chat(user_id)
                username = f"@{user.username}" if user.username else "❌ Topilmadi"
                result += (
                    f"👤 Foydalanuvchi:\n"
                    f"🔹 Ism: {user.full_name}\n"
                    f"🔹 Username: {username}\n"
                    f"🔹 ID: <code>{user.id}</code>\n\n"
                )
            except Exception as e:
                result += f"🔹 ID: <code>{user_id}</code> — xatolik: {e}\n\n"
        return result


class AdminFilter(BaseFilter):
    """Statik + DB admin filteri."""

    def __init__(self, static_admins: list):
        self.static_admins = set(static_admins)

    async def __call__(self, message: Message) -> bool:
        with db_connection() as (conn, cur):
            cur.execute("SELECT user_id FROM public.admins")
            db_admins = {int(row[0]) for row in cur.fetchall()}
        return message.from_user.id in (db_admins | self.static_admins)
