from urllib.parse import quote

from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardButton, KeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import sql, bot, is_referral_system_enabled, WEBAPP_URL, BOT_USERNAME, PORTAL_OTISH_URL


_resolved_username: str | None = None


async def _bot_username() -> str:
    """BOT_USERNAME .envda berilmagan bo'lsa, tokendan (bot.get_me) avtomatik
    aniqlaydi va keshlaydi — original va klon botlar hech qachon adashmaydi,
    hech kim qo'lda username kiritishni unutib qo'ymaydi."""
    global _resolved_username
    if BOT_USERNAME:
        return BOT_USERNAME
    if _resolved_username is None:
        me = await bot.get_me()
        _resolved_username = me.username
    return _resolved_username


async def _webapp_url() -> str:
    """O'tish ballari webapp havolasi + shu bot nomi (?bot=username) — webapp
    'ulashish' tugmasi aynan shu botga qaytishi uchun (original/klon adashmasin).
    PORTAL_OTISH_URL berilgan bo'lsa yangi web portal (nodavlattalim.uz)
    ishlatiladi, aks holda eski WEBAPP_URL (talim24)."""
    base = PORTAL_OTISH_URL or WEBAPP_URL
    if not base:
        return ""
    username = await _bot_username()
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}bot={quote(username)}"


class AdminPanel:
    @staticmethod
    async def admin_menu():
        referral_status = "ON" if is_referral_system_enabled() else "OFF"
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊Statistika"), KeyboardButton(text="🔧Kanallar")],
                [KeyboardButton(text="🔧Adminlar👨‍💻"), KeyboardButton(text="✍Xabarlar")],
                [KeyboardButton(text="🔧Kanallar2"), KeyboardButton(text=f"🎯 Referal: {referral_status}")],
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
        keyboard = [
            [
                KeyboardButton(text="📊 Ball yetadigan yo'nalishlar"),
                KeyboardButton(text="📚 Yoʻnalishlar boʻyicha"),
            ],
            [
                KeyboardButton(text="📈 Viloyatlar kesimida")
            ],
        ]
        web_url = await _webapp_url()
        if web_url:
            keyboard.append([
                KeyboardButton(text="🌐 Veb-sahifada ko'rish", web_app=WebAppInfo(url=web_url)),
            ])
        keyboard.append([KeyboardButton(text="◀️ Ortga")])
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    async def asos_manu():
        url = await _webapp_url()
        otish_ballari_btn = (
            KeyboardButton(text="📊 O'tish ballari", web_app=WebAppInfo(url=url))
            if url else KeyboardButton(text="📊 O'tish ballari")
        )
        keyboard = [
            [
                KeyboardButton(text="📊 Mandat saytdagi o'rni"),
                KeyboardButton(text="🎯 Balingizga mos yo'nalish")
            ],
            [
                otish_ballari_btn,
                KeyboardButton(text="🎓 Perevod-2026")
            ],
            [
                KeyboardButton(text="😎 Test ishlash")
            ]
        ]
        btn = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        return btn

    @staticmethod
    async def move_manu():
        btn = ReplyKeyboardMarkup(
            keyboard=[
                [
                    # Eng tepada, bitta qatorda alohida turadi
                    KeyboardButton(text="🔥 Diagnostik test ishlash")
                ],
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
