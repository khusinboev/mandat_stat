from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardButton, KeyboardButton, InlineKeyboardMarkup

from config import sql, bot


class AdminPanel:
    @staticmethod
    async def admin_menu():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊Statistika"), KeyboardButton(text="🔧Kanallar")],
                [KeyboardButton(text="🔧Adminlar👨‍💻"), KeyboardButton(text="✍Xabarlar")],
                [KeyboardButton(text="🔧Kanallar2")],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def admin_channel(suffix: str = ""):
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=f"➕Kanal qo'shish{suffix}"),
                    KeyboardButton(text=f"❌Kanalni olib tashlash{suffix}"),
                ],
                [
                    KeyboardButton(text=f"📋 Kanallar ro'yxati{suffix}"),
                    KeyboardButton(text=f"🔙Orqaga qaytish{suffix}"),
                ],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def admin_channel2():
        return await AdminPanel.admin_channel(suffix="2")

    @staticmethod
    async def admin_add():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="➕Admin qo'shish"), KeyboardButton(text="❌Admin o'chirish")],
                [KeyboardButton(text="📋 Adminlar ro'yxati"), KeyboardButton(text="🔙Orqaga qaytish")],
            ],
            resize_keyboard=True,
        )

    @staticmethod
    async def admin_msg():
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📨Forward xabar yuborish"), KeyboardButton(text="📬Oddiy xabar yuborish")],
                [KeyboardButton(text="🧪Sinov: Copy yuborish"), KeyboardButton(text="🧪Sinov: Forward yuborish")],
                [KeyboardButton(text="🔙Orqaga qaytish")],
            ],
            resize_keyboard=True,
        )


class UserPanels:
    @staticmethod
    async def join_btn(user_id):
        sql.execute("SELECT chat_id FROM public.mandatorys")
        rows = sql.fetchall()
        join_inline = []
        title = 1
        for row in rows:
            all_details = await bot.get_chat(chat_id=row[0])
            url = all_details.invite_link
            if not url:
                url = await bot.export_chat_invite_link(row[0])
            join_inline.append([InlineKeyboardButton(text=f"{title} - kanal", url=url)])
            title += 1
        join_inline.append([InlineKeyboardButton(text="✅Obuna bo'ldim", callback_data="check")])
        button = InlineKeyboardMarkup(inline_keyboard=join_inline)
        return button

    @staticmethod
    async def main_manu():
        btn = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📊 Ball yetadigan yo'nalishlar"),
                    KeyboardButton(text="📚 Yoʻnalishlar boʻyicha"),
                ],
                [
                    KeyboardButton(text="📈 Viloyatlar kesimida")
                ],
                [KeyboardButton(text="◀️ Ortga")]
            ],
            resize_keyboard=True,
        )
        return btn

    @staticmethod
    async def asos_manu():
        btn = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📊 O'tish ballari"),
                    KeyboardButton(text="🎓 Perevod-2026")
                ],
                [
                    KeyboardButton(text="😎 Test ishlash")
                ]
            ],
            resize_keyboard=True,
        )
        return btn

    @staticmethod
    async def move_manu():
        btn = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📝 Baholash mezonlari️"),
                    KeyboardButton(text="📚 Fanlar majmuasi️")
                ],
                [
                    KeyboardButton(text="📊 O'tish ballari️"),
                    KeyboardButton(text="💰 Super kontrakt miqdori️"),
                ],
                [
                    KeyboardButton(text="🧮 Tabaqalashtirilgan kontrakt miqdori"),
                    KeyboardButton(text="📄 Transkript yuklash")
                ],
                [
                    KeyboardButton(text="📎 Turdosh yo'nalishlar ro'yxati")
                ],
                [
                    KeyboardButton(text="◀️ Ortga")
                ]
            ],
            resize_keyboard=True,
        )
        return btn

    @staticmethod
    async def ball_btn():
        btn = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="🏆 Grand"),
                    KeyboardButton(text="📄 Kontrakt"),
                ],
                [
                    KeyboardButton(text="🔙 Ortga")
                ]
            ],
            resize_keyboard=True,
        )
        return btn

    @staticmethod
    async def to_back():
        btn = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Ortga"), KeyboardButton(text="🔙 Bosh menu")]], resize_keyboard=True,
        )
        return btn

    @staticmethod
    async def quiz_menu():
        btn = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📝 Matematika"),
                    KeyboardButton(text="📚 Ona tili"),
                ],
                [
                    KeyboardButton(text="📚 Tarix"),
                    KeyboardButton(text="🧮 Hammasidan"),
                ],
                [
                    KeyboardButton(text="📊 Natijalarim")
                ],
                [
                    KeyboardButton(text="◀️ Ortga")
                ],
            ],
            resize_keyboard=True,
        )
        return btn
