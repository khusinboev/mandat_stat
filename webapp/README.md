# O'tish ballari — Telegram Mini WebApp

2025-yil kontrakt o'tish ballarini ko'rsatuvchi **faqat namoyish** (read-only)
mini webapp. Bot bilan bog'lanmaydi — faqat `mandat` PostgreSQL bazasidan o'qiydi.

## Tuzilishi

```
webapp/
  main.py            # FastAPI — 8 ta read-only API endpoint + static
  db.py              # asyncpg pool (.env dagi DB_* dan ulanadi)
  static/
    index.html       # SPA qobig'i (Telegram WebApp SDK ulangan)
    app.js           # hash-router, 7 ta ekran, kun/tun, bottom-sheet
    style.css        # mobil-birinchi dizayn, light/dark tokenlar
  landing/
    index.html       # Domen ildiziga (masalan talim24.uz) qo'yiladigan oddiy
                      # bir-tugmali sahifa — botga yo'naltiradi. nginx to'g'ridan-to'g'ri
                      # statik fayl sifatida beradi, FastAPI'ga bog'liq emas.
```

## Ishga tushirish

```bash
.venv/bin/uvicorn webapp.main:app --host 0.0.0.0 --port 8080
```

Brauzerda: http://localhost:8080

## Ekranlar

| Yo'l | Nima ko'rsatadi |
|---|---|
| `#/` | Statistika, umumiy qidiruv, eng yuqori ballar |
| `#/regions` | 14 hudud → OTMlar ro'yxati |
| `#/uni/{id}` | OTM yo'nalishlari (shakl/til chip-filtrlari bilan) |
| `#/dirs` | 348 yo'nalish, jonli qidiruv |
| `#/dir/{nomi}` | Yo'nalish barcha OTMlarda solishtirma |
| `#/ball` | "Ballim yetadimi?" — ball kiritib mos yo'nalishlarni ko'rish |

Har qanday yo'nalish qatoriga bosilsa pastdan tafsilot kartasi (bottom sheet) chiqadi.

## Production'ga chiqarish (systemd)

Servisni doimiy fon jarayoni qilish uchun tayyor shablon: [`deploy/mandat-webapp.service`](../deploy/mandat-webapp.service).

```bash
sudo cp deploy/mandat-webapp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mandat-webapp
sudo systemctl status mandat-webapp
```

Shablon `127.0.0.1:8080` ga bog'lanadi — tashqi trafik faqat nginx orqali kiradi
(pastga qarang). Bot uchun xuddi shunday tayyor shablon:
[`deploy/mandat-bot.service`](../deploy/mandat-bot.service).

## Telegram Mini App sifatida ulash (domen ulanganda)

1. **Nginx + SSL:** [`deploy/nginx-webapp.conf.example`](../deploy/nginx-webapp.conf.example)
   shablonida `YOUR_DOMAIN` ni almashtirib joylang, so'ng `certbot --nginx -d YOUR_DOMAIN`
   bilan HTTPS oling (Telegram Mini App **faqat HTTPS**ni qabul qiladi — bu shart).
2. @BotFather → Bot Settings → Menu Button → HTTPS URL'ni kiriting.
3. Tema Telegram'ning kun/tun rejimiga avtomatik moslashadi
   (`Telegram.WebApp.colorScheme`), foydalanuvchi header'dagi tugma bilan
   qo'lda ham almashtira oladi (tanlov `localStorage`da saqlanadi).

Domen hali yo'q bo'lsa ham hammasi shu holicha ishlaydi — faqat 3-bosqichni
(BotFather URL) domen tayyor bo'lgach bajarasiz.

### Domen ildizi (masalan talim24.uz, portsiz)

Agar webapp alohida portda (masalan 9876) ishlasa-yu, domenning o'zi
(https://talim24.uz/) bo'sh tursa — shu domen ildiziga `landing/index.html`ni
ulab qo'yish mumkin: [`deploy/nginx-talim24-landing.conf`](../deploy/nginx-talim24-landing.conf)
namunasida ko'rsatilganidek, nginx uni to'g'ridan-to'g'ri statik fayl sifatida
beradi (FastAPI ishlab turishi shart emas).

## Ball darajalari rang tizimi

Raqam har doim ko'rinadi — rang faqat qo'shimcha vizual belgi:

- 🟢 85 gacha · 🟡 85–115 · 🟠 115–150 · 🔴 150+ · `—` e'lon qilinmagan

## Ma'lumot yangilash

Baza `parse2025.py` bilan to'ldiriladi (loyiha ildizida). Webapp hech narsa yozmaydi.
