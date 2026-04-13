from aiogram import Bot
from aiogram.filters import BaseFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, User, Message

from config import sql, db, bot, ADMIN_ID


class CheckData:
    @staticmethod
    async def check_member(bot: Bot, user_id: int, table: str = "mandatorys"):
        sql.execute(f"SELECT chat_id FROM public.{table}")
        mandatory = sql.fetchall()
        if not mandatory:
            return True, []

        channels = []
        for chat_id in mandatory:
            try:
                r = await bot.get_chat_member(chat_id=chat_id[0], user_id=user_id)
                if r.status == "left" and user_id not in ADMIN_ID:
                    channels.append(chat_id[0])
            except Exception as e:
                print(f"Xatolik: {e}")
        return (len(channels) == 0), channels

    @staticmethod
    async def check_member2(bot: Bot, user_id: int):
        return await CheckData.check_member(bot, user_id, table="kanallar2")

    @staticmethod
    async def channels_btn(channels: list, table: str = "mandatorys", callback: str = "check"):
        keyboard = []
        for index, channel_id in enumerate(channels, 1):
            sql.execute(f"SELECT username FROM public.{table} WHERE chat_id=%s", (channel_id,))
            link = sql.fetchone()
            if link:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"📢 Kanal-{index}",
                        url=link[0]
                    )
                ])
        keyboard.append([InlineKeyboardButton(text="✅Qo'shildim", callback_data=callback)])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @staticmethod
    async def channels_btn2(channels: list):
        return await CheckData.channels_btn(channels, table="kanallar2", callback="check2")


class PanelFunc:
    @staticmethod
    async def channel_add(chat_id, link, table: str = "mandatorys"):
        sql.execute(f"INSERT INTO public.{table} (chat_id, username) VALUES (%s, %s)", (chat_id, link))
        db.commit()

    @staticmethod
    async def channel_add2(chat_id, link):
        await PanelFunc.channel_add(chat_id, link, table="kanallar2")

    @staticmethod
    async def channel_delete(id, table: str = "mandatorys"):
        sql.execute(f"DELETE FROM public.{table} WHERE chat_id = %s", (id,))
        db.commit()

    @staticmethod
    async def channel_delete2(id):
        await PanelFunc.channel_delete(id, table="kanallar2")

    @staticmethod
    async def channel_list(table: str = "mandatorys"):
        sql.execute(f"SELECT chat_id, username from public.{table}")
        result = ''
        for row in sql.fetchall():
            chat_id = row[0]
            try:
                all_details = await bot.get_chat(chat_id=chat_id)
                title = all_details.title
                link = row[1]
                info = all_details.description
                result += (
                    f"------------------------------------------------\n"
                    f"Kanal useri: > @{all_details.username}\n"
                    f"Kamal nomi: > {title}\n"
                    f"Kanal id si: > {link}\n"
                    f"Kanal haqida: > {info}\n"
                )
            except Exception as e:
                result += f"Kanalni admin qiling\n\nError: {e}"
        return result

    @staticmethod
    async def channel_list2():
        return await PanelFunc.channel_list(table="kanallar2")

    @staticmethod
    async def admin_add(chat_id):
        sql.execute("INSERT INTO public.admins (user_id) VALUES (%s)", (chat_id,))
        db.commit()

    @staticmethod
    async def admin_delete(id):
        sql.execute("DELETE FROM public.admins WHERE user_id = %s", (id,))
        db.commit()

    @staticmethod
    async def admin_list():
        sql.execute("SELECT user_id from public.admins")
        result = ""
        for row in sql.fetchall():
            chat_id = row[0]
            try:
                user: User = await bot.get_chat(chat_id)
                username = f"@{user.username}" if user.username else "❌ Topilmadi"
                full_name = user.full_name
                result += f"👤 Foydalanuvchi:\n🔹 Ism: {full_name}\n🔹 Username: {username}\n🔹 ID: <code>{user.id}</code>\n\n"
            except Exception as e:
                result += f"xatolik:\n🔹 ID: <code>{chat_id}</code>\n\n"
        return result
