import os
import json
import logging
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, WebAppInfo

from config import bot, ADMIN_ID, sql, db, REQUIRED_REFERRALS
from urllib.parse import quote
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

user_router = Router()
logger = logging.getLogger(__name__)


class CloneTestState(StatesGroup):
    waiting_samples = State()


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    return str(value)


def _message_clone_payload(message: Message) -> dict:
    payload = _to_jsonable(message.model_dump(exclude_none=True))
    payload["content_type"] = message.content_type

    # Keep a compact summary in the same payload for faster inspection.
    payload["_summary"] = {
        "text": message.text,
        "caption": message.caption,
        "document": {
            "file_id": message.document.file_id,
            "file_name": message.document.file_name,
            "mime_type": message.document.mime_type,
            "file_size": message.document.file_size,
        } if message.document else None,
    }
    return payload


def _pretty_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@user_router.message(Command("clone_test"))
async def start_clone_test(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return

    await state.set_state(CloneTestState.waiting_samples)
    await state.update_data(clone_samples=[])
    await message.answer(
        "✅ Clone test rejimi yoqildi.\n"
        "1) Oddiy text yuboring\n"
        "2) Document + caption yuboring\n\n"
        "Har bir xabar server logiga JSON qilib chiqadi. To'xtatish: /clone_stop",
        parse_mode="html"
    )


@user_router.message(Command("clone_stop"), CloneTestState.waiting_samples)
async def stop_clone_test(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return

    await state.clear()
    await message.answer("🛑 Clone test rejimi to'xtatildi.")


@user_router.message(CloneTestState.waiting_samples)
async def collect_clone_sample(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return

    data = await state.get_data()
    samples = data.get("clone_samples", [])

    payload = _message_clone_payload(message)
    payload_text = _pretty_json(payload)

    # Console + logger output for easy copy/use in next update step.
    print("CLONE_TEST_PAYLOAD:")
    print(payload_text)
    logger.info("CLONE_TEST_PAYLOAD: %s", payload_text)

    samples.append(payload)
    await state.update_data(clone_samples=samples)

    short_preview = payload_text[:3500]
    await message.answer(
        f"📥 Qabul qilindi ({len(samples)}/2).\n"
        f"<code>{short_preview}</code>",
        parse_mode="html"
    )

    if len(samples) >= 2:
        await state.clear()
        await message.answer(
            "✅ 2 ta sinov xabar olindi va log qilindi.\n"
            "Logdan nusxa yuboring, keyin shu asosida bo'lim matnlarini yangilayman.",
            parse_mode="html"
        )


@user_router.message(CommandStart())
async def start_cmd1(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    args = message.text.split() if message.text else []

    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1][4:])
            if referrer_id != user_id:
                sql.execute(
                    "SELECT referred_by, msg_count FROM public.accounts WHERE user_id=%s LIMIT 1",
                    (user_id,)
                )
                row = sql.fetchone()
                # Faqat haqiqatan yangi user: msg_count <= 1 (birinchi kirish)
                # va referred_by NULL (hali boshqa havola orqali qo'shilmagan)
                if row and row[0] is None and row[1] <= 1:
                    sql.execute(
                        "UPDATE public.accounts SET referred_by=%s WHERE user_id=%s",
                        (referrer_id, user_id),
                    )
                    sql.execute(
                        "UPDATE public.accounts SET referral_count=referral_count+1 "
                        "WHERE user_id=%s RETURNING referral_count",
                        (referrer_id,),
                    )
                    ref_row = sql.fetchone()
                    ref_count = ref_row[0] if ref_row else 0

                    if ref_count >= REQUIRED_REFERRALS:
                        notify_text = (
                            f"🎉 <b>Yangi foydalanuvchi siz orqali qo'shildi!</b>\n\n"
                            f"👥 Jami taklif qilganlar: <b>{ref_count}/{REQUIRED_REFERRALS}</b>\n\n"
                            f"✅ <b>Tabriklaymiz! Botdan endi cheksiz foydalanishingiz mumkin!</b>"
                        )
                    else:
                        notify_text = (
                            f"✅ <b>Yangi foydalanuvchi siz orqali qo'shildi!</b>\n\n"
                            f"👥 Jami taklif qilganlar: <b>{ref_count}/{REQUIRED_REFERRALS}</b>\n\n"
                            f"➡️ Yana <b>{REQUIRED_REFERRALS - ref_count}</b> ta kishi taklif qiling."
                        )
                    try:
                        await bot.send_message(referrer_id, notify_text, parse_mode="html")
                    except Exception:
                        pass
        except (ValueError, IndexError):
            pass

    await message.answer(
        "<b>Assalomu alaykum, botimizga xush kelibsiz. Quyidagi ko'rsatilgan menyudan o'zingizga kerakli bo'limni tanlang 👇</b>",
        parse_mode="html",
        reply_markup=await UserPanels.asos_manu(),
    )
    await message.answer(
        "<b>🌟 Botimizda endi yangi imkoniyat bor – Testlar bo'limi!</b>\n"
        "Bu bo'lim abituriyentlar uchun maxsus tayyorlangan va imtihonga tayyorgarlik ko'rishda yordam beradi. "
        "Bu yerda siz bilimlaringizni sinab, o'z darajangizni aniqlashingiz mumkin.\n\n"
        "Yana qanday imkoniyatlar mavjud?\n\n"
        "- <b>😎 Testga kirish:</b> Abituriyentlar uchun maxsus tayyorlangan testlarni ishlashni boshlang va o'zingizni sinab ko'ring.\n"
        "- <b>📊 O'tish ballari:</b> 2025/2026-o'quv yili OTMlarga kirish ballari.\n"
        "- <b>🎓 Perevod-2026:</b> Perevodchilar uchun barcha ma'lumotlar jamlangan bo'lim\n\n"
        "Tugmalarni bosib, imtihonga tayyorgarlikni hoziroq boshlang va kelajakdagi muvaffaqiyatingizga qadam qo'ying! 🚀",
        parse_mode="html",
    )


@user_router.callback_query(F.data == "check_referral")
async def check_referral_status(call: CallbackQuery):
    user_id = call.from_user.id
    sql.execute(
        "SELECT msg_count, referral_count FROM public.accounts WHERE user_id=%s LIMIT 1",
        (user_id,)
    )
    row = sql.fetchone()
    referral_count = row[1] if row else 0

    if referral_count >= REQUIRED_REFERRALS:
        try:
            await call.message.edit_text(
                "✅ <b>Siz yetarli do'st taklif qildingiz!</b>\n\n"
                "Botdan endi cheksiz foydalanishingiz mumkin. "
                "Boshlash uchun /start bosing.",
                parse_mode="html",
            )
        except Exception:
            pass
        await call.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=False)
    else:
        remaining = REQUIRED_REFERRALS - referral_count
        me = await bot.get_me()
        ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"
        share_url = f"https://t.me/share/url?url={quote(ref_link, safe='')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=share_url)],
            [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_referral")],
        ])
        await call.answer(
            f"Hali {remaining} ta kishi taklif qilish kerak!",
            show_alert=True,
        )
        try:
            await call.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass

@user_router.callback_query(F.data.in_({"check", "check2"}), F.message.chat.type == ChatType.PRIVATE)
async def check_membership(call: CallbackQuery):
    user_id = call.from_user.id
    check_fn = CheckData.check_member2 if call.data == "check2" else CheckData.check_member
    try:
        check_status, channels = await check_fn(bot, user_id)
        if check_status:
            try:
                await call.message.delete()
                await call.answer()
            except Exception:
                pass
            await bot.send_message(chat_id=user_id,
                                   text="Quyidagi menulardan birini tanlang!",
                                   parse_mode="html", reply_markup=await UserPanels.asos_manu())
        else:
            try:
                await call.answer(show_alert=True, text="Botimizdan foydalanish uchun barcha kanallarga a'zo bo'ling")
            except Exception:
                try:
                    await call.answer()
                except Exception:
                    pass
    except Exception as e:
        await bot.forward_message(chat_id=ADMIN_ID[0], from_chat_id=call.message.chat.id, message_id=call.message.message_id)
        await bot.send_message(chat_id=ADMIN_ID[0], text=f"Error in check:\n{e}")


@user_router.message(F.text == "📊 O'tish ballari")
async def start_cmd2(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Quyidagi menulardan birini tanlang!", parse_mode="html", reply_markup=await UserPanels.main_manu())

@user_router.message(F.text == "◀️ Ortga")
async def start_cmd3(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Quyidagi menulardan birini tanlang!", parse_mode="html", reply_markup=await UserPanels.asos_manu())


@user_router.message(F.text == "🎓 Perevod-2026")
async def start_cmd4(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Quyidagi menulardan birini tanlang!", parse_mode="html", reply_markup=await UserPanels.move_manu())

@user_router.message(F.text == "📝 Baholash mezonlari️")
async def start_cmd5(message: Message):
    check_status, channels = await CheckData.check_member2(bot, message.from_user.id)

    if check_status:
        await message.answer(
        "<b>⚡️Bu yilgi o‘qishni ko‘chirish imtihonlarida baholash mezonlari quyidagicha bo‘ladi:</b>\n\n"

        "👉 <b>Barcha test topshiruvchilar uchun majburiy bo‘lgan 3 ta fan bo‘yicha:</b>\n\n"

        "<b>➖ Ona tili</b> (o‘zbek, rus yoki qoraqalpoq tili) – 10 ta savol.\n"
        "Har biri uchun 1,1 balldan.\n"
        "Maksimal ball – 11 ball.\n\n"

        "<b>➖ Matematika</b> – 10 ta savol.\n"
        "Har biri uchun 1,1 balldan.\n"
        "Maksimal ball – 11 ball.\n\n"

        "<b>➖ O‘zbekiston tarixi</b> – 10 ta savol.\n"
        "Har biri uchun 1,1 balldan.\n"
        "Maksimal ball – 11 ball.\n\n"

        "✅ <b>Jami to‘plash mumkin bo‘lgan ball – 33 ball.</b>\n\n"

        "👉 <b>Bakalavriat taʼlim yoʻnalishiga mos boʻlgan 2 ta mutaxassislik fan bo‘yicha:</b>\n\n"

        "<b>➖ 1-fan</b> – 30 ta savol.\n"
        "Har biri uchun 3,1 balldan.\n"
        "Maksimal ball – 93 ball.\n\n"

        "<b>➖ 2-fan</b> – 30 ta savol.\n"
        "Har biri uchun 2,1 balldan.\n"
        "Maksimal ball – 63 ball.\n\n"

        "✅ <b>Jami to‘plash mumkin bo‘lgan ball – 156 ball.</b>\n\n"

        "📝 <i>Umumiy holda, 2026/2027-o‘quv yilida o‘qishni ko‘chirish talabida bo‘lganlar uchun "
        "5 ta fan bo‘yicha jami 90 ta test topshirig‘i beriladi. "
        "Bunda to‘plash mumkin bo‘lgan maksimal ball – <b>189 ball</b>ni tashkil etadi.</i>\n\n"

        "<i>© <a href='https://t.me/mandatjavobbot?start=share'>@mandatjavobbot</a> — O‘qishni ko‘chirishga oid ma’lumotlar bazasi!</i>",
        parse_mode="HTML"
    )
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn2(channels))

@user_router.message(F.text == "📚 Fanlar majmuasi️")
async def start_cmd6(message: Message):
    check_status, channels = await CheckData.check_member2(bot, message.from_user.id)

    if check_status:
        await message.answer_document(document="BQACAgIAAxkBAV87w2nm4Pm2iJa8zX0pVF6RUi61uN9cAALhpAACM8QwS3TcgLm7CZnfOwQ",
        caption="<b>📕 FANLAR MAJMUASI! \n\n"
"📝 O'qishni ko'chirish imtihonlarida test topshiriladigan fanlar majmuasi.\n\n"
"✔️ Yo'nalishlar bo'yicha qaysi fandan imtihon bo'lishi ko'rsatilgan.\n\n"
"⚠️ Oʻqishni koʻchirishda aynan mana shu 2025/2026-o'quv yilidagi fanlar majmuasidan foydalaniladi. \n\n"
"© @mandatjavobbot — O'qishni ko'chirishga oid ma'lumotlar bazasi!</b>"
    , parse_mode="html")
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn2(channels))

@user_router.message(F.text == "📊 O'tish ballari️")
async def start_cmd7(message: Message):
    check_status, channels = await CheckData.check_member2(bot, message.from_user.id)

    if check_status:
        await message.answer_photo(photo="AgACAgIAAxkBAAHxJvRofhQTCwdIp6X_ZwJrQ9eIPMDENAACNvIxG0SS-EtT5x82hi17mgEAAwIAA3kAAzYE", caption="<b>⚡️O‘qishni ko‘chirishda qancha ball to'plash kerak?</b>\n\n"
"2025/2026-oʻquv yili uchun xorijiy va nodavlat oliy taʼlim muassasalaridan talabalar oʻqishini respublika <b>davlat oliy taʼlim muassasalariga koʻchirish boʻyicha oʻtkaziladigan maxsus sinovlar boʻyicha oʻtish ballari</b> tasdiqlangan.\n\n"
"<b>Yuqoridagi o’tish ballari quyidagilarga taalluqli:</b>\n\n"
"1️⃣ xorijdagi OTMlardan yurtimizdagi davlat OTMlariga o’qishini ko’chirmoqchi bo’lganlarga;\n"
"2️⃣ yurtimizdagi nodavlat OTMlar hamda xorijiy OTMlarning filiallaridan davlat OTMlariga o’qishini ko’chirmoqchi bo’lganlarga.\n\n"
"Eslatma: o’qishni ko’chirish bo’yicha arizalar <b>15-iyuldan 5-avgustgacha</b> qabul qilinadi.\n\n"
"<b>© @mandatjavobbot — O'qishni ko'chirishga oid ma'lumotlar bazasi!!</b>", parse_mode="html")
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn2(channels))

@user_router.message(F.text == "💰 Super kontrakt miqdori️")
async def start_cmd8(message: Message):
    check_status, channels = await CheckData.check_member2(bot, message.from_user.id)

    if check_status:
        await message.answer("<b>⚡️O'QISHNI KO'CHIRISHDA SUPER KONTRAKT MIQDORI QANCHA❓</b>\n\n"
"<u>Super-kontrakt miqdori quyidagicha:</u>\n\n"
"👉 Agar 0.1 balldan — <b>1.0 ballgacha</b> yetmasa oddiy kontraktning <b>1.5 barobarini</b> to'laydi;\n"
"👉 Agar 1,1 baldan — <b>2,0  ballgacha</b> yetmasa oddiy kontraktning <b>2 barobarini</b> to'laydi;\n"
"👉 Agar 2,1 baldan — <b>3.0 ballgacha</b> yetmasa oddiy kontraktning <b>2.5 barobarini</b> to'laydi;\n"
"👉 Agar 3,1 balldan — <b>4.0 ballgacha</b> yetmasa oddiy kontraktning <b>3 barobarini</b> to'laydi;\n\n"
"☝️ Agar <b>4,0 balldan ortiq ball yetmasa</b> tabaqalashtirilgan to'lov-kontraktning minimal miqdorini to'laydi. Bu miqdor yo'nalishlarga qarab bazaviy kontraktning <b>8 barobardan 25 barobargacha</b> belgilanishi mumkin.\n\n"
"<b>© @mandatjavobbot — O'qishni ko'chirishga oid ma'lumotlar bazasi!</b>", parse_mode="html")
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn2(channels))

@user_router.message(F.text == "🧮 Tabaqalashtirilgan kontrakt miqdori")
async def start_cmd9(message: Message):
    check_status, channels = await CheckData.check_member2(bot, message.from_user.id)

    if check_status:
        await message.answer(
            "<b>⚡️2025/2026-o'quv yilidan tabaqalashtirilgan toʻlov-kontrakt miqdori "
            "OTM rektorlari (direktorlari) tomonidan belgilanadi</b>\n\n"
            "Davlat komissiyasi <a href='https://t.me/nodavlattalim/4271'>bayoniga</a> muvofiq, "
            "2025/2026-oʻquv yili uchun kirish imtihonlari natijalariga koʻra "
            "<b>56,7 va undan yuqori ball toʻplagan lekin talabalikka tavsiya etilmagan abituriyentlarni</b> "
            "bakalavriat taʼlim yoʻnalishlariga qoʻshimcha qabul qilishda tabaqalashtirilgan "
            "toʻlov-kontrakt miqdorini rektor (direktor) tomonidan mustaqil belgilash quyidagi "
            "tartibda amaliyotga joriy etiladi:\n\n"
            "➖ qabul chegaralariga <b>4,05 ballgacha yetmagan abituriyentlar uchun belgilangan "
            "tabaqalashtirilgan toʻlov-kontrakt miqdorlari</b> Vazirlar Mahkamasining "
            "2025-yil 13-sentyabrdagi 578-son qarori bilan tasdiqlangan "
            "<a href='https://www.lex.uz/docs/-7726569#:~:text=holda%20amalga%20oshiradi.-,Bunda%20to%E2%80%98lov%2Dkontrakt%20miqdori%20amalda%20o%E2%80%98rnatilgan%20bazaviy%20to%E2%80%98lov%2Dkontrakt%20miqdoriga%20nisbatan%20quyidagi%20miqdorlarda%20belgilanadi%3A,-1%2C05%20ballgacha%20yetmagan'>Nizom talablari</a> "
            "(1-ilova 73-band)ga asosan belgilanadi;\n\n"
            "➖ qabul chegaralariga <b>4,05 balldan ortiq ball yetmagan abituriyentlar uchun "
            "tabaqalashtirilgan toʻlov-kontrakt miqdorlari</b> oliy taʼlim muassasalari "
            "rektorlari (direktorlari) tomonidan <b>bazaviy toʻlov-kontraktning 3,0 barobaridan "
            "kam boʻlmagan miqdorda</b> belgilanadi.\n\n"
            "2025/2026-oʻquv yili qabulida tabaqalashtirilgan toʻlov-kontrakt asosida tahsil olish "
            "istagini bildirgan abituriyentlarga <b>bir yillik oʻqitish qiymatining 50 foizini "
            "2025-yilning 31-oktyabrga qadar (shu kuni ham) toʻlashga ruxsat beriladi</b>.\n\n"
            "Shuningdek, bakalavriat taʼlim yoʻnalishlariga kirish imtihonlari natijasi boʻyicha "
            "tanlovda ishtirok etib, <b>ikkinchi-beshinchi bakalavriat taʼlim yoʻnalishlaridan biri "
            "boʻyicha davlat granti yoki toʻlov-kontrakt asosida talabalikka tavsiya etilgan "
            "abituriyentlarga oʻz xohishlariga koʻra ustuvorligi boʻyicha tanlagan birinchi "
            "bakalavriat taʼlim yoʻnalishida tabaqalashtirilgan toʻlov-kontrakt asosida oʻqishga "
            "ruxsat berildi</b> (maqsadli qabul asosida talabalikka tavsiya qilinganlar bundan mustasno).\n\n"
            "<b>© @mandatjavobbot — O'qishni ko'chirishga oid ma'lumotlar bazasi!</b>",
            parse_mode="html"
        )
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn2(channels))

@user_router.message(F.text == "📄 Transkript yuklash")
async def transkript_handler(message: Message):
    check_status, channels = await CheckData.check_member2(bot, message.from_user.id)
    if check_status:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Transkript yuklash 🗂", web_app=WebAppInfo(url="https://my.hemis.uz/"))]
        ])
        await message.answer(text="<b>O'qishni ko'chirishda asosiy hujjat transkript. Transkriptni yuklash uchun pastdagi havolani bosing</b> 👇\n\n",
                             reply_markup=keyboard, parse_mode="html")
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn2(channels))


@user_router.message(F.text == "😎 Test ishlash")
async def sample_tests_handler(message: Message):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)

    if check_status:
        await message.answer(
        "<b>⚡️Bilimni baholash agentligi tomonidan olinadigan imtihonlarning "
        "<u>majburiy va mutaxassislik</u> fanlaridan <u>namunaviy test topshiriqlari</u></b>\n\n"

        "<b>Majburiy bloklar:</b>\n"
        "👉 <a href='https://t.me/nodavlattalim/1393'>Ona tili</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1394'>Rus tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1395'>Qoraqalpoq tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1396'>Matematika</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1397'>Matematika (rus)</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1398'>O‘zbekiston tarixi</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1399'>O‘zbekiston tarixi (rus)</a>\n\n"

        "<b>Mutaxassislik fanlari:</b>\n"
        "👉 <a href='https://t.me/nodavlattalim/1400'>Huquqshunoslik</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1401'>Tarix</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1402'>Biologiya</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1403'>Fizika</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1404'>Kimyo</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1405'>Matematika</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1406'>Geografiya</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1407'>Ingliz tili</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1408'>Nemis tili</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1409'>Fransuz tili</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1410'>Ona tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1412'>Rus tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1411'>Qoraqalpoq tili va adabiyoti</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1413'>Ona tili va adabiyoti (o‘zga tilli guruhlar uchun)</a>\n"
        "👉 <a href='https://t.me/nodavlattalim/1414'>Rus tili va adabiyoti (o‘zga tilli guruhlar uchun)</a>\n\n"

        "<b>© <a href='https://t.me/mandatjavobbot?start=share'>@mandatjavobbot</a> - oʻtish ballari va mandat natijalari</b>",
        parse_mode="HTML"
    )
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))


def split_text_by_words(text, max_len=45):
    words = text.split()
    result = ''
    line = ''

    for word in words:
        # Agar yangi so‘zni qo‘shganda line uzunligi max_len'dan oshmasa
        if len(line) + len(word) + 1 <= max_len:
            if line:
                line += ' ' + word
            else:
                line = word
        else:
            # Yangi qatorga o'tamiz
            result += line + '\n'
            line = word

    # Oxirgi qatorni ham qo‘shamiz
    if line:
        result += line

    return result

def create_card(univer, faculty, lang, edu, grand, kont, olmp, name):
    univer = split_text_by_words(univer)
    faculty = split_text_by_words(faculty)
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    template_path = CURRENT_DIR+"/edu.png"
    output_path = f"{CURRENT_DIR}/photos/{name}.jpg"
    try:
        # Rasmni ochish
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template image '{template_path}' not found!")

        image = Image.open(template_path)
        draw = ImageDraw.Draw(image)

        # Shriftlarni yuklash (o'zingizga mos fayllarni ko'rsating)
        try:
            # DejaVu Sans Bold — kirill va lotin harflarini qo'llab-quvvatlaydi
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            title_font = ImageFont.truetype(font_path, 100)
            main_font = ImageFont.truetype(font_path, 90)
        except Exception:
            try:
                # Fallback: loyiha ichidagi Quicksand (faqat lotin)
                title_font = ImageFont.truetype(CURRENT_DIR+"/Quicksand-Bold.otf", 100)
                main_font = ImageFont.truetype(CURRENT_DIR+"/Quicksand-Bold.otf", 90)
            except Exception:
                title_font = ImageFont.load_default()
                main_font = ImageFont.load_default()

        # 1. Universitet nomi (binoning ustidagi ochiq maydonga)
        draw.text((500, 200), str(univer), font=title_font, fill="black")

        # 2. Ta'lim yo'nalishi ("AJ" yozuvi o'rniga)
        # "AJ" ni o'chirish uchun uning joyiga oq rangda to'rtburchak chizamiz
        draw.text((300, 800), str(faculty), font=main_font, fill="black")

        # 3. Ta'lim tili (oldingi yozuv ostida)
        draw.text((550, 1600), str(lang), font=main_font, fill="white")

        # 4. Ta'lim shakli
        draw.text((1500, 1600), str(edu), font=main_font, fill="white")

        # 5. Mandat yili
        draw.text((2450, 1600), "2025", font=main_font, fill="white")

        # 6. Grantlar
        draw.text((650, 2120), str(grand), font=main_font, fill="black")

        # 7. Kontraktlar
        draw.text((1420, 2120), str(kont), font=main_font, fill="black")

        # 8. Olimpiada g'oliblari soni
        draw.text((2550, 2170), str(olmp), font=main_font, fill="black")

        # Natijani saqlash
        image.save(output_path)
        print(f"Karta muvaffaqiyatli yaratildi: {output_path}")
        return True

    except Exception as e:
        print(f"Xatolik yuz berdi: {str(e)}")
        return False
