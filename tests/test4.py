from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

# Bot tokenini o'rnating
BOT_TOKEN = "7733022802:AAF94C5lULtbdbGGO8OjOao8PkI26JnOinE"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Namuna ma'lumotlar bazasi (aslida PostgreSQL, MySQL ishlatishingiz mumkin)
books = [
    {"id": 1, "title": "Python dasturlash asoslari", "author": "John Doe"},
    {"id": 2, "title": "JavaScript mukammal qo'llanma", "author": "Jane Smith"},
    {"id": 3, "title": "Dasturlash algoritmlari", "author": "Bob Johnson"},
]

# Inline qidiruv uchun handler
@dp.inline_query()
async def inline_search(inline_query: InlineQuery):
    query = inline_query.query.lower().strip()
    results = []

    # Agar foydalanuvchi hech narsa yozmasa, barcha kitoblarni ko'rsatamiz
    if not query:
        for book in books:
            results.append(
                InlineQueryResultArticle(
                    id=str(book["id"]),
                    title=book["title"],
                    input_message_content=InputTextMessageContent(
                        message_text=f"📚 <b>{book['title']}</b>\n👨‍💻 {book['author']}",
                        parse_mode="HTML"
                    ),
                    description=book["author"],
                )
            )
    else:
        # Qidiruv so'ziga mos keladigan kitoblarni topamiz
        for book in books:
            if query in book["title"].lower() or query in book["author"].lower():
                results.append(
                    InlineQueryResultArticle(
                        id=str(book["id"]),
                        title=book["title"],
                        input_message_content=InputTextMessageContent(
                            message_text=f"📚 <b>{book['title']}</b>\n👨‍💻 {book['author']}",
                            parse_mode="HTML"
                        ),
                        description=book["author"],
                    )
                )

    # Natijalarni yuboramiz (max 50 ta)
    await bot.answer_inline_query(
        inline_query_id=inline_query.id,
        results=results[:50],
        cache_time=1
    )

# Start komandasi
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Salom! Bu bot orqali kitoblarni qidirishingiz mumkin.\n\n"
        "Qidirish uchun: @usernamebot [qidiruv so'zi]\n"
        "Misol: @usernamebot python"
    )

# Botni ishga tushirish
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())