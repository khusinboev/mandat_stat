from aiogram.types import (
    ReplyKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, InlineKeyboardMarkup
)

from config import db_connection, bot


class AdminPanel:

    @staticmethod
    async def admin_menu() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📊Statistika"),
                    KeyboardButton(text="🔧Kanallar"),
                ],
                [
                    KeyboardButton(text="🔧Adminlar👨‍💻"),
                    KeyboardButton(text="✍Xabarlar"),
                ],
                [
                    KeyboardButton(text="🔧Kanallar2"),
                ],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def admin_channel() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="➕Kanal qo'shish"),
                    KeyboardButton(text="❌Kanalni olib tashlash"),
                ],
                [
                    KeyboardButton(text="📋 Kanallar ro'yxati"),
                    KeyboardButton(text="🔙Orqaga qaytish"),
                ],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def admin_channel2() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="➕Kanal qo'shish2"),
                    KeyboardButton(text="❌Kanalni olib tashlash2"),
                ],
                [
                    KeyboardButton(text="📋 Kanallar ro'yxati2"),
                    KeyboardButton(text="🔙Orqaga qaytish2"),
                ],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def admin_add() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="➕Admin qo'shish"),
                    KeyboardButton(text="❌Admin o'chirish"),
                ],
                [
                    KeyboardButton(text="📋 Adminlar ro'yxati"),
                    KeyboardButton(text="🔙Orqaga qaytish"),
                ],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def admin_msg() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📨Forward xabar yuborish"),
                    KeyboardButton(text="📬Oddiy xabar yuborish"),
                ],
                [
                    KeyboardButton(text="🧪Sinov: Copy yuborish"),
                    KeyboardButton(text="🧪Sinov: Forward yuborish"),
                ],
                [
                    KeyboardButton(text="🔙Orqaga qaytish"),
                ],
            ],
            resize_keyboard=True,
        )


class UserPanels:

    @staticmethod
    async def join_btn(user_id: int) -> InlineKeyboardMarkup:
        with db_connection() as (conn, cur):
            cur.execute("SELECT chat_id FROM public.mandatorys")
            rows = cur.fetchall()

        join_inline = []
        for index, (chat_id,) in enumerate(rows, 1):
            try:
                chat = await bot.get_chat(chat_id=chat_id)
                url = chat.invite_link or await bot.export_chat_invite_link(chat_id)
                join_inline.append([
                    InlineKeyboardButton(text=f"{index} - kanal", url=url)
                ])
            except Exception:
                pass

        join_inline.append([
            InlineKeyboardButton(text="✅Obuna bo'ldim", callback_data="check")
        ])
        return InlineKeyboardMarkup(inline_keyboard=join_inline)

    @staticmethod
    async def main_manu() -> ReplyKeyboardMarkup:
        """Bakalavriat 2025 ichki menyusi."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📊 Ball yetadigan yo'nalishlar"),
                    KeyboardButton(text="📚 Yoʻnalishlar boʻyicha"),
                ],
                [
                    KeyboardButton(text="📈 Viloyatlar kesimida"),
                ],
                [
                    KeyboardButton(text="◀️ Ortga"),
                ],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def asos_manu() -> ReplyKeyboardMarkup:
        """Bosh menyu."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    # ✅ 2024 → 2025 tuzatildi
                    KeyboardButton(text="📕BAKALAVRIAT 2025"),
                    KeyboardButton(text="📘O'qishni ko'chirish"),
                ],
                [
                    KeyboardButton(text="📚 Namunaviy test topshiriqlari"),
                ],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def move_manu() -> ReplyKeyboardMarkup:
        """O'qishni ko'chirish menyusi."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📝 Baholash mezonlari️"),
                    KeyboardButton(text="📚 Fanlar majmuasi️"),
                ],
                [
                    KeyboardButton(text="📊 O'tish ballari️"),
                    KeyboardButton(text="💰 Super kontrakt miqdori️"),
                ],
                [
                    KeyboardButton(text="🧮 Tabaqalashtirilgan kontrakt miqdori"),
                    KeyboardButton(text="📄 Transkript yuklash"),
                ],
                [
                    KeyboardButton(text="◀️ Ortga"),
                ],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def ball_btn() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="🏆 Grand"),
                    KeyboardButton(text="📄 Kontrakt"),
                ],
                [
                    KeyboardButton(text="🔙 Ortga"),
                ],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def to_back() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="🔙 Ortga"),
                    KeyboardButton(text="🔙 Bosh menu"),
                ]
            ],
            resize_keyboard=True,
        )
