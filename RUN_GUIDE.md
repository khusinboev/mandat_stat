# Mandat Stat run qo'llanma

Ushbu hujjat loyihani:
- Windows local muhitda to'liq ishga tushirish
- Ubuntu serverda productionga yaqin holatda ishga tushirish

uchun bosqichma-bosqich yo'riqnoma beradi.

## 1. Talab qilinadigan komponentlar

- Python 3.11 yoki 3.12
- PostgreSQL 14+
- Redis 6+ (tavsiya etiladi, FSM state saqlash uchun)
- Telegram bot token

Loyiha ishlash rejimi:
- Bot: long polling (main.py)
- Parser: parse2025.py orqali DB ni to'ldirish

## 2. Muhim env o'zgaruvchilar

Asosiylari:
- BOT_TOKEN
- ADMINS_ID (vergul bilan ajratilgan admin ID lar)
- DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

Scale va monitoring uchun:
- DB_POOL_MIN_CONN
- DB_POOL_MAX_CONN
- REDIS_URL
- MAX_BROADCAST_CONCURRENCY
- DEFAULT_BROADCAST_BATCH_SIZE
- DEFAULT_DB_PAGE_SIZE
- PROGRESS_UPDATE_EVERY_USERS
- PROGRESS_UPDATE_MIN_SECONDS
- SLOW_UPDATE_MS

Quiz import uchun:
- AUTO_IMPORT_QUIZ
- QUIZ_IMPORT_SKIP_ON_HASH_MATCH
- QUES_BOT_DB_NAME
- QUES_BOT_DB_USER
- QUES_BOT_DB_PASSWORD
- QUES_BOT_DB_HOST
- QUES_BOT_DB_PORT

Namuna konfiguratsiya: [.env.example](.env.example)

## 3. Windows localda to'liq ishga tushirish

### 3.1. Repository va virtual environment

PowerShell:

```powershell
cd D:\own\projects\python\mandat_stat
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3.2. PostgreSQL tayyorlash

Agar localda postgres o'rnatilgan bo'lsa:

```powershell
psql -U postgres
```

psql ichida:

```sql
CREATE DATABASE mandat_stat;
CREATE USER mandat_user WITH PASSWORD 'StrongPassword123!';
GRANT ALL PRIVILEGES ON DATABASE mandat_stat TO mandat_user;
```

Agar schema/table ruxsat muammosi bo'lsa:

```sql
\c mandat_stat
GRANT ALL ON SCHEMA public TO mandat_user;
ALTER SCHEMA public OWNER TO mandat_user;
```

### 3.3. Redis ishga tushirish

Variant A (Windows service yoki alohida redis install):
- Redis ni 6379 portda ishga tushiring.

Variant B (Docker bo'lsa):

```powershell
docker run -d --name mandat-redis -p 6379:6379 redis:7
```

### 3.4. .env yaratish

Loyiha papkasida .env fayl yarating:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
ADMINS_ID=123456789

DB_NAME=mandat_stat
DB_USER=mandat_user
DB_PASSWORD=StrongPassword123!
DB_HOST=localhost
DB_PORT=5432
DB_POOL_MIN_CONN=1
DB_POOL_MAX_CONN=20

REDIS_URL=redis://localhost:6379
MAX_BROADCAST_CONCURRENCY=20
DEFAULT_BROADCAST_BATCH_SIZE=100
DEFAULT_DB_PAGE_SIZE=1000
PROGRESS_UPDATE_EVERY_USERS=500
PROGRESS_UPDATE_MIN_SECONDS=2
SLOW_UPDATE_MS=700
```

Izoh:
- WEBHOOK_URL va WEBHOOK_SECRET long polling rejimida shart emas.

### 3.5. Parserni ishga tushirish (full reset + 0 dan yuklash)

```powershell
python parse2025.py
```

Bu rejim parser jadvallarini to'liq tozalab, ma'lumotni 0 dan qayta yuklaydi.

Agar test rejim kerak bo'lsa:

```powershell
python parse2025.py --dry-run
```

Agar tozalamasdan upsert kerak bo'lsa:

```powershell
python parse2025.py --no-clean
```

### 3.6. Botni ishga tushirish

```powershell
python main.py
```

### 3.7. Quiz DB import (ixtiyoriy)

Agar AUTO_IMPORT_QUIZ=true bo'lsa, bot startup vaqtida quiz jadvallarini source DB dan target DB ga import qiladi.

Manual import:

```powershell
python scripts/import_quiz_data.py
```

Majburan (hash tekshiruvsiz) qayta import:

```powershell
python scripts/import_quiz_data.py --force
```

Source DB dan SQL export:

```powershell
bash ./scripts/export_quiz_data.sh ques_bot_db ./quiz_dump.sql
```

### 3.8. Tezkor tekshiruv

- Botga start yuboring
- User flow larni tekshiring: filter bo'limlari
- Admin paneldan xabar yuborishni tekshiring: progress, speed, ETA chiqishini ko'ring

## 4. Ubuntu serverda to'liq ishga tushirish

Quyidagi buyruqlar Ubuntu 22.04/24.04 uchun.

### 4.1. System paketlar

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git postgresql postgresql-contrib redis-server
```

Redis ni yoqish:

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server
```

### 4.2. Loyiha kodini olish

```bash
cd /opt
sudo git clone <YOUR_REPO_URL> mandat_stat
sudo chown -R $USER:$USER /opt/mandat_stat
cd /opt/mandat_stat
```

### 4.3. Virtual environment va dependency

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4.4. PostgreSQL sozlash

```bash
sudo -u postgres psql
```

psql ichida:

```sql
CREATE DATABASE mandat_stat;
CREATE USER mandat_user WITH PASSWORD 'StrongPassword123!';
GRANT ALL PRIVILEGES ON DATABASE mandat_stat TO mandat_user;
\c mandat_stat
GRANT ALL ON SCHEMA public TO mandat_user;
ALTER SCHEMA public OWNER TO mandat_user;
```

### 4.5. .env fayl

```bash
cp .env.example .env
nano .env
```

Minimal kerakli qiymatlarni to'g'ri to'ldiring:
- BOT_TOKEN
- ADMINS_ID
- DB_*
- REDIS_URL=redis://localhost:6379

### 4.6. Parserni ishga tushirish

```bash
source .venv/bin/activate
python parse2025.py
```

### 4.7. Botni manual ishga tushirish

```bash
source .venv/bin/activate
python main.py
```

## 5. Ubuntu systemd bilan doimiy run

### 5.1. Service fayl yaratish

```bash
sudo nano /etc/systemd/system/mandat-bot.service
```

Ichiga:

```ini
[Unit]
Description=Mandat Stat Telegram Bot
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/mandat_stat
EnvironmentFile=/opt/mandat_stat/.env
ExecStart=/opt/mandat_stat/.venv/bin/python /opt/mandat_stat/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

User va path ni serveringizga moslang.

### 5.2. Service ni yoqish

```bash
sudo systemctl daemon-reload
sudo systemctl enable mandat-bot
sudo systemctl start mandat-bot
sudo systemctl status mandat-bot
```

Loglarni ko'rish:

```bash
journalctl -u mandat-bot -f
```

## 6. Parserni cron orqali yangilash (ixtiyoriy)

Agar parserni har kuni yangilamoqchi bo'lsangiz:

```bash
crontab -e
```

Masalan, har kuni 03:30 da:

```cron
30 3 * * * cd /opt/mandat_stat && /opt/mandat_stat/.venv/bin/python parse2025.py >> /opt/mandat_stat/parse_cron.log 2>&1
```

## 7. Monitoring va tuning tavsiyalari

Broadcast monitoring allaqachon real-time ishlaydi:
- Yuborilgan soni
- Yuborilmagan soni
- Tezlik (user/s)
- ETA
- Xatoliklar breakdown

Yuklama oshsa sozlang:
- MAX_BROADCAST_CONCURRENCY (masalan 20 -> 40)
- DEFAULT_BROADCAST_BATCH_SIZE
- DB_POOL_MAX_CONN
- PROGRESS_UPDATE_EVERY_USERS

## 8. Muammo va yechimlar

1. Bot start bo'lmayapti, DB xato:
- DB credential larni .env da tekshiring
- postgres status ni tekshiring

2. FSM state yo'qolib qolmoqda:
- REDIS_URL to'g'riligini tekshiring
- redis-server ishlayotganini tekshiring

3. Broadcast sekin:
- MAX_BROADCAST_CONCURRENCY ni bosqichma-bosqich oshiring
- DB pool limitlarni moslang

4. Parser API timeout:
- parse2025.py dagi delay/retry parametrlari bilan ishga tushiring
- kechasi ishga tushirish tavsiya etiladi

## 9. Minimal run ketma-ketligi

Har ikki muhit uchun eng qisqa ketma-ketlik:
1. .env sozlash
2. pip install -r requirements.txt
3. python parse2025.py
4. python main.py

Shu ketma-ketlik bilan loyiha to'liq ishlaydi.
