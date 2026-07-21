# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# mandat_stat

O'zbekiston OTM'lariga kirish **2025 o'tish ballari (mandat)** bo'yicha Telegram
bot. `mandat.uzbmb.uz` saytidan ma'lumot parser bilan yig'iladi, PostgreSQL'ga
yoziladi va bot orqali (hudud / yo'nalish / ball bo'yicha) filterlab ko'rsatiladi.
Qo'shimcha: o'z-o'zini test qilish (quiz), referal-limit tizimi, admin broadcast
va faqat-o'qish FastAPI Mini WebApp. aiogram 3.20, psycopg2 (async emas), Redis FSM.

**Har sessiya boshida:** `.claude/PROJECT.md` faylini o'qing — server manzillari,
bot tokeni, lokal DB/deploy tafsilotlari va infra qarorlari shu yerda (fayl
gitignored, shu sabab bu faylda takrorlanmagan).

## Uch alohida ishga tushiriladigan komponent (bitta PostgreSQL bazani baham ko'radi)

- **Bot** — `python main.py` (long polling). Barcha handler router'lari shu yerda
  ulanadi va `on_startup` da sxema yaratiladi.
- **Parser** — `python parse2025.py` — bazani to'ldiradi (bot'dan mustaqil).
- **WebApp** — `.venv/bin/uvicorn webapp.main:app --host 0.0.0.0 --port 8080` —
  bazadan faqat o'qiydigan Telegram Mini App (bot'dan butunlay mustaqil).

To'liq lokal/server qo'llanma: [RUN_GUIDE.md](RUN_GUIDE.md). WebApp tafsilotlari:
[webapp/README.md](webapp/README.md).

## Muhim: baza bilan ishlashning UCH xil mexanizmi

Bu loyihaning eng nostandart tomoni — sinxron va async kod aralash.

1. **`config.py` global proxy** (`db`, `sql`, `conn`, `cursor`) — modul import
   bo'lganda ochiladigan bitta **raw psycopg2** ulanish (`autocommit=True`),
   `ConnectionProxy`/`CursorProxy` ichida o'ralgan. `InterfaceError`/
   `OperationalError` da avtomatik qayta ulanadi. Deyarli barcha handler'lar shuni
   ishlatadi. ⚠️ Bu **bloklovchi** chaqiruvlar async handler ichida ishlaydi
   (`run_in_executor` yo'q) — loyihaning ongli xususiyati, "tuzatish" shart emas.
   ⚠️ `config` import bo'lishi uchun baza **ishlab turishi shart** — aks holda bot
   umuman import bo'lmaydi. `ADMINS_ID` ham import paytida parse qilinadi.
2. **`config.db_pool`** (`SimpleConnectionPool`) — faqat `RegisterUserMiddleware`
   har bir update'da foydalanuvchini ro'yxatga olish uchun ishlatadi.
3. **`webapp/db.py`** — WebApp'ning alohida **asyncpg** pool'i. Bot kodiga
   bog'liq emas.

## Sxema imperativ tarzda yaratiladi (alembic asosiy emas)

`alembic/` mavjud, lekin haqiqiy sxema evolyutsiyasi **kodda** boshqariladi:

- `src/db/init_db.py::create_all_base()` — bot startup'da chaqiriladi; `CREATE
  TABLE IF NOT EXISTS` + idempotent `DO $$ ... $$` bloklari (kolonna/indeks/
  constraint qo'shish). Yangi jadval/kolonna kerak bo'lsa shu yerga qo'shing.
- `parse2025.py::create_tables()` — parserga tegishli jadvallarni (regions,
  universities, gettypes, getlangs, mandat, photos) o'zi yaratadi.

Ikki joyda `mandat.year` va uning unique-constraint mantig'i takrorlanadi — biror
o'zgartirsangiz ikkovini ham yangilang.

## Domen modeli (mandat ma'lumotlari)

Iyerarxiya: `regions` → `universities` (un_id) → `gettypes` (ty_id, ta'lim shakli)
→ `getlangs` (lan_id, til) → `mandat` (yo'nalish satrlari). `mandat`da asosiy
ustunlar: `gr_b`/`con_b` = grant/kontrakt o'tish balli, `gr_k`/`con_k` = joylar
soni, `olimp`, `year` (default 2025). Bot'ning uch foydalanuvchi filtri shu
iyerarxiyani turli kirish nuqtasidan aylanadi:

- `src/handlers/users/filter_reg.py` — "📈 Viloyatlar kesimida" (hudud → OTM → …)
- `src/handlers/users/filter_fac.py` — "📚 Yo'nalishlar bo'yicha"
- `src/handlers/users/filter_ball.py` — "📊 Ball yetadigan yo'nalishlar" (ball kiritib mos yo'nalishlar)

## Router'lar va handler'lar

`main.py` router'larni tartib bilan ulaydi (`admin_router`, `add_router`,
`msg_router`, `user_router`, `test_router`, `fac_router`, `reg_router`,
`ball_router`, `group_router`, `channel_router`, `other_router`). `other_router`
catch-all bo'lgani uchun oxirida turishi shart. Menyular reply-keyboard asosida
(matn tugma nomlari bilan filter qilinadi) — tugma matnlari `src/keyboards/buttons.py` da.

## Referal / limit tizimi

`RegisterUserMiddleware` (`src/middlewares/middleware.py`) har bir foydalanuvchini
`accounts` jadvaliga yozadi va `msg_count` ni oshiradi. `MSG_LIMIT` (default 10)
tekin xabardan so'ng, admin bo'lmagan userlar `?start=ref_<id>` havolasi orqali
`REQUIRED_REFERRALS` (default 2) do'st taklif qilmaguncha bloklanadi. `/start` va
callback'lar hamisha o'tadi. Tizimni runtime'da yoqib/o'chirish `runtime_settings`
jadvali orqali (`config.is_referral_system_enabled`/`set_referral_system_enabled`,
5s kesh) — admin paneldagi "🎯 Referal" tugmasi ham shuni almashtiradi.

## Broadcast dvigateli

`src/handlers/admins/messages.py` — `accounts` bo'ylab **keyset pagination**
(`iter_user_id_batches`), `asyncio.Semaphore` bilan konkurent yuborish, copy va
forward rejimlari, sinov rejimlari (yuborib darhol o'chiradi), backoff bilan
retry, jonli progress (tezlik/ETA), muvaffaqiyatsiz userlar faylga yoziladi.
Barcha limitlar env orqali sozlanadi (`MAX_BROADCAST_CONCURRENCY`,
`DEFAULT_BROADCAST_BATCH_SIZE`, `DEFAULT_DB_PAGE_SIZE`, `PROGRESS_UPDATE_*`).

## Quiz / test moduli

"😎 Test ishlash" bo'limi (`src/handlers/users/tests.py`) — `math`, `literature`,
`history` savol jadvallari va `results`. Savollar **boshqa bot bazasidan** import
qilinadi: `src/db/quiz_importer.py` — manba DB hash'i o'zgargan bo'lsagina to'liq
`TRUNCATE`+qayta yuklash. Import startup'da (`AUTO_IMPORT_QUIZ=true`) yoki qo'lda
`python scripts/import_quiz_data.py [--force]` bilan bo'ladi. Manba DB env'da
`QUES_BOT_DB_*` bilan beriladi.

## Klon / ko'p-bot qo'llab-quvvatlash

Bot sxemani baham ko'radigan bir nechta instansiyaga klonlash uchun mo'ljallangan:
- `bot_static_files` jadvali har bir bot uchun `file_id`larni keshlaydi (bitta
  botning `file_id`si boshqasida ishlamaydi; `users.py`dagi `_send_static_document`/
  `_send_static_photo` fallback qilib qayta keshlaydi).
- `BOT_USERNAME` / `WEBAPP_URL` env qiymatlari ulashish havolalarini bot'ga xos
  qiladi — klon uchun **alohida** qiymat bering.

## Ikkita majburiy obuna kanal to'plami

`mandatorys` va `kanallar2` — ikki mustaqil kanal to'plami, admin paneldan alohida
boshqariladi (`src/handlers/admins/admin.py` dagi `_CHANNEL_CONFIGS`). Obuna
tekshiruvi kirish nuqtalarida amalga oshadi (`/start`da ham).

## Buyruqlar

```bash
# Bot
python main.py

# Parser — standart: parser jadvallarini tozalab 0 dan yuklaydi
python parse2025.py
python parse2025.py --no-clean     # tozalamasdan upsert (eski yillar qoladi)
python parse2025.py --dry-run      # bazaga yozmaydi, faqat API ni tekshiradi
python parse2025.py --stats        # bazadagi joriy statistika
python parse2025.py --no-resume    # progressni e'tiborsiz qoldirib boshidan

# WebApp
.venv/bin/uvicorn webapp.main:app --host 0.0.0.0 --port 8080

# Quiz import / export
python scripts/import_quiz_data.py [--force]
bash scripts/export_quiz_data.sh <source_db> ./quiz_dump.sql

# Migratsiya (kamdan-kam; sxema asosan kodda boshqariladi)
alembic upgrade head
```

Rasmiy avtomatlashtirilgan test to'plami yo'q — `tests/` va ildizdagi `test*.py`,
`test_3regions.py` qo'lda ishlatiladigan ad-hoc skriptlar (rasm generatsiyasi
uchun `arial.ttf`/`edu.png` shu papkada).

## Deploy

`deploy/` da tayyor shablonlar: `mandat-bot.service`, `mandat-webapp.service`
(systemd), `nginx-webapp.conf.example`, `nginx-talim24-landing.conf`. Telegram
Mini App **faqat HTTPS** — WebApp domenga certbot bilan SSL ulanishi shart.

## Muhim env o'zgaruvchilar

`.env` (namuna: [.env.example](.env.example)). Minimal: `BOT_TOKEN`, `ADMINS_ID`
(vergul bilan), `DB_*`. FSM davomiyligi uchun `REDIS_URL` (bo'lmasa MemoryStorage).
Referal: `REFERRAL_SYSTEM_ENABLED`, `MSG_LIMIT`, `REQUIRED_REFERRALS`. Quiz import:
`AUTO_IMPORT_QUIZ`, `QUES_BOT_DB_*`. WebApp tugmasi: `WEBAPP_URL` (bo'sh bo'lsa
tugma ko'rsatilmaydi), `BOT_USERNAME`. `WEBHOOK_*` long polling'da ishlatilmaydi.
