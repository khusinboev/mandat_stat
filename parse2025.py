"""
parse2025.py — mandat.uzbmb.uz saytidan 2025 yil ma'lumotlarini tortib PostgreSQL ga yozuvchi parser.

YANGILANISH STRATEGIYASI:
  - Standart rejim (--update):  mandat jadvalidagi barcha yozuvlar o'chirilib, 2025 yilgi
                                 ma'lumotlar bilan to'liq almashtiriladi.
                                 regions/universities/gettypes/getlangs — UPSERT (saqlanib qoladi).
  - --no-clean rejimi:          Hech narsa o'chirilmaydi, faqat UPSERT qilinadi.
                                 2025 da yo'q bo'lgan 2024 yozuvlari bazada qoladi.

Xavfsizlik choralari:
  - Har so'rovdan keyin tasodifiy kutish (rate limiting)
  - 429 / 5xx xatolarida eksponensial retry
  - Connection pool va session reuse
  - Progress saqlanadi: to'xtatilsa davom ettirish mumkin
  - Barcha xatolar parse2025_errors.log ga yoziladi

ISHLATISH:
  python parse2025.py                  # mandat ni tozalab 2025 yil bilan yozadi
  python parse2025.py --no-clean       # tozalamasdan faqat upsert
  python parse2025.py --no-resume      # progressni e'tiborsiz qoldirib boshidan
  python parse2025.py --dry-run        # bazaga yozmaydi, faqat API ni tekshiradi
  python parse2025.py --stats          # bazadagi joriy statistikani chiqaradi
"""

import os
import time
import random
import logging
import argparse
import psycopg2
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# ──────────────────────────── SOZLAMALAR ────────────────────────────

load_dotenv()

DB_CONFIG = {
    "dbname":   os.getenv("DB_NAME",     "example"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "parol"),
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     os.getenv("DB_PORT",     "5432"),
}

BASE_URL = "https://mandat.uzbmb.uz"
YEAR     = "2025"

REGIONS_URL      = f"{BASE_URL}/Mandat{YEAR}/GetRegions?lang=uz"
UNIVERSITIES_URL = f"{BASE_URL}/BallVuz{YEAR}/GetUniversities?RegionID={{region_id}}"
TYPES_URL        = f"{BASE_URL}/BallVuz{YEAR}/GetTypes?UniversityID={{un_id}}"
LANGS_URL        = f"{BASE_URL}/BallVuz{YEAR}/GetLangs?UniversityID={{un_id}}"
ALL_URL          = (
    f"{BASE_URL}/BallVuz{YEAR}/GetAll"
    "?RegionID={region_id}&UniversityID={un_id}&EdTypeID={ty_id}&EdLangID={lan_id}"
)

DELAY_MIN = 0.8
DELAY_MAX = 2.0

MAX_RETRIES        = 5
BACKOFF_FACTOR     = 2
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

# ──────────────────────────── LOGGING ────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("parse2025_errors.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ──────────────────────────── HTTP SESSION ────────────────────────────

def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "uz-UZ,uz;q=0.9,en;q=0.8",
        "Referer":         f"{BASE_URL}/",
    })
    return session


def safe_get(session: requests.Session, url: str, timeout: int = 30):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = BACKOFF_FACTOR ** attempt + random.uniform(1, 3)
                log.warning(f"429 Too Many Requests: {url} — {wait:.1f}s kutilmoqda (urinish {attempt})")
                time.sleep(wait)
            else:
                log.error(f"HTTP {resp.status_code}: {url}")
                return None
        except requests.exceptions.ConnectionError as e:
            wait = BACKOFF_FACTOR ** attempt
            log.warning(f"ConnectionError (urinish {attempt}): {e} — {wait}s kutilmoqda")
            time.sleep(wait)
        except requests.exceptions.Timeout:
            log.warning(f"Timeout (urinish {attempt}): {url}")
            time.sleep(BACKOFF_FACTOR ** attempt)
        except Exception as e:
            log.error(f"Kutilmagan xato: {e} | URL: {url}")
            return None
    log.error(f"Barcha urinishlar muvaffaqiyatsiz: {url}")
    return None


def sleep_rand():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

# ──────────────────────────── DATABASE ────────────────────────────

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def create_tables(conn):
    """Zarur jadvallarni yaratadi (agar mavjud bo'lmasa)."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS regions (
                id          SERIAL PRIMARY KEY,
                region_id   INTEGER UNIQUE,
                region_name VARCHAR UNIQUE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS universities (
                id          SERIAL PRIMARY KEY,
                region_id   INTEGER,
                un_disabled VARCHAR,
                un_group    VARCHAR,
                un_selected VARCHAR,
                un_text     VARCHAR,
                un_id       VARCHAR UNIQUE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gettypes (
                id          SERIAL PRIMARY KEY,
                region_id   INTEGER,
                un_id       VARCHAR,
                ty_disabled VARCHAR,
                ty_group    VARCHAR,
                ty_selected VARCHAR,
                ty_text     VARCHAR,
                ty_id       VARCHAR,
                UNIQUE (region_id, un_id, ty_text, ty_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS getlangs (
                id           SERIAL PRIMARY KEY,
                region_id    INTEGER,
                un_id        VARCHAR,
                ty_id        VARCHAR,
                lan_disabled VARCHAR,
                lan_group    VARCHAR,
                lan_selected VARCHAR,
                lan_text     VARCHAR,
                lan_id       VARCHAR,
                UNIQUE (region_id, un_id, ty_id, lan_text, lan_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mandat (
                id        SERIAL PRIMARY KEY,
                region_id INTEGER,
                un_id     VARCHAR,
                ty_id     VARCHAR,
                lan_id    VARCHAR,
                mvdir     BIGINT,
                nomi      VARCHAR,
                gr_k      INTEGER,
                con_k     INTEGER,
                gr_b      REAL,
                con_b     REAL,
                olimp     INTEGER,
                UNIQUE (region_id, un_id, ty_id, lan_id, mvdir, nomi)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id      SERIAL PRIMARY KEY,
                un_id   VARCHAR NOT NULL,
                ty_id   VARCHAR NOT NULL,
                lan_id  VARCHAR NOT NULL,
                mvdir   VARCHAR NOT NULL,
                file_id VARCHAR NOT NULL,
                UNIQUE (un_id, ty_id, lan_id, mvdir)
            )
        """)
    conn.commit()
    log.info("Jadvallar tayyor.")


def clean_mandat(conn):
    """
    mandat jadvalidagi barcha yozuvlarni o'chiradi.
    photos ham o'chiriladi — chunki eski karta rasmlari 2025 ball bilan mos kelmaydi.

    Faqat mandat va photos o'chiriladi. regions/universities/gettypes/getlangs
    saqlanib qoladi (ular tarkiban o'zgarishi kam).
    """
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM mandat")
        count = cur.fetchone()[0]
        log.info(f"mandat jadvalidagi mavjud yozuvlar soni: {count}")

        cur.execute("DELETE FROM photos")
        cur.execute("DELETE FROM mandat")
    conn.commit()
    log.info("✓ mandat va photos jadvallari tozalandi. 2025 yil ma'lumotlari yoziladi...")

# ──────────────────────────── PROGRESS ────────────────────────────

PROGRESS_FILE = "parse2025_progress.txt"


def load_progress() -> int:
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                return int(f.read().strip())
        except Exception:
            pass
    return 0


def save_progress(region_id: int):
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(region_id))


def reset_progress():
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
    log.info("Progress tozalandi — boshidan boshlanadi.")

# ──────────────────────────── UPSERT ────────────────────────────

def upsert_region(cur, region_id, region_name):
    cur.execute("""
        INSERT INTO regions (region_id, region_name)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (region_id, region_name))


def upsert_university(cur, region_id, un_disabled, un_group, un_selected, un_text, un_id):
    cur.execute("""
        INSERT INTO universities (region_id, un_disabled, un_group, un_selected, un_text, un_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (un_id) DO NOTHING
    """, (region_id, un_disabled, un_group, un_selected, un_text, un_id))


def upsert_type(cur, region_id, un_id, ty_disabled, ty_group, ty_selected, ty_text, ty_id):
    cur.execute("""
        INSERT INTO gettypes (region_id, un_id, ty_disabled, ty_group, ty_selected, ty_text, ty_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (region_id, un_id, ty_text, ty_id) DO NOTHING
    """, (region_id, un_id, ty_disabled, ty_group, ty_selected, ty_text, ty_id))


def upsert_lang(cur, region_id, un_id, ty_id, lan_disabled, lan_group, lan_selected, lan_text, lan_id):
    cur.execute("""
        INSERT INTO getlangs (region_id, un_id, ty_id, lan_disabled, lan_group, lan_selected, lan_text, lan_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (region_id, un_id, ty_id, lan_text, lan_id) DO NOTHING
    """, (region_id, un_id, ty_id, lan_disabled, lan_group, lan_selected, lan_text, lan_id))


def upsert_mandat(cur, region_id, un_id, ty_id, lan_id,
                  mvdir, nomi, gr_k, con_k, gr_b, con_b, olimp):
    """
    Agar yozuv mavjud bo'lsa — balllarni yangilaydi.
    Yangi yo'nalish bo'lsa — qo'shadi.
    """
    cur.execute("""
        INSERT INTO mandat (region_id, un_id, ty_id, lan_id, mvdir, nomi, gr_k, con_k, gr_b, con_b, olimp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (region_id, un_id, ty_id, lan_id, mvdir, nomi)
        DO UPDATE SET
            gr_k  = EXCLUDED.gr_k,
            con_k = EXCLUDED.con_k,
            gr_b  = EXCLUDED.gr_b,
            con_b = EXCLUDED.con_b,
            olimp = EXCLUDED.olimp
    """, (region_id, un_id, ty_id, lan_id, mvdir, nomi, gr_k, con_k, gr_b, con_b, olimp))

# ──────────────────────────── ASOSIY PARSER ────────────────────────────

def parse(resume: bool = True, dry_run: bool = False, clean: bool = True):
    """
    Barcha ma'lumotlarni API dan tortib bazaga yozadi.

    :param resume:  True bo'lsa — oldingi progressdan davom ettiradi
    :param dry_run: True bo'lsa — bazaga yozmaydi (test rejimi)
    :param clean:   True bo'lsa — mandat va photos jadvallarini tozalaydi (tavsiya etiladi)
    """
    last_region = load_progress() if resume else 0
    if not resume:
        reset_progress()

    session = make_session()
    conn    = None if dry_run else get_conn()

    if conn:
        create_tables(conn)

        # --no-clean berilmasa mandat ni tozalaymiz
        if clean and last_region == 0:
            # Progressdan davom etilayotgan bo'lsa tozalamaymiz (qisman yangilangan bo'lishi mumkin)
            clean_mandat(conn)
        elif clean and last_region > 0:
            log.info(
                f"Progress mavjud (oxirgi region: {last_region}). "
                "Mandat tozalanmaydi — davom etish rejimi."
            )

    # 1. Regionlar
    log.info(f"Regionlar yuklanmoqda: {REGIONS_URL}")
    regions = safe_get(session, REGIONS_URL)
    if not regions:
        log.error("Regionlarni yuklash muvaffaqiyatsiz. Dastur to'xtatildi.")
        if conn:
            conn.close()
        return
    sleep_rand()

    log.info(f"Topilgan regionlar soni: {len(regions)}")

    total_mandat = 0
    skipped      = 0

    for r_idx, region in enumerate(regions, 1):
        region_id   = int(region["region_id"])
        region_name = region["region_name"]

        if region_id <= last_region:
            log.info(f"[{r_idx}/{len(regions)}] Region #{region_id} '{region_name}' — o'tkazildi (progress)")
            skipped += 1
            continue

        log.info(f"[{r_idx}/{len(regions)}] Region: {region_id} — {region_name}")

        if conn:
            with conn.cursor() as cur:
                upsert_region(cur, region_id, region_name)
            conn.commit()

        # 2. Universitetlar
        url = UNIVERSITIES_URL.format(region_id=region_id)
        univers = safe_get(session, url)
        sleep_rand()

        if not univers:
            log.warning(f"  Universitetlar topilmadi: region {region_id}")
            save_progress(region_id)
            continue

        for u_idx, univer in enumerate(univers, 1):
            un_id       = univer["value"]
            un_text     = univer["text"]
            un_disabled = univer.get("disabled", "")
            un_group    = univer.get("group", "")
            un_selected = univer.get("selected", "")

            log.info(f"  [{u_idx}/{len(univers)}] Universitet: {un_id} — {un_text[:60]}")

            if conn:
                with conn.cursor() as cur:
                    upsert_university(cur, region_id, un_disabled, un_group, un_selected, un_text, un_id)
                conn.commit()

            # 3. Ta'lim shakllari
            url = TYPES_URL.format(un_id=un_id)
            get_types = safe_get(session, url)
            sleep_rand()

            if not get_types:
                log.warning(f"    Types topilmadi: un_id={un_id}")
                continue

            # 4. Ta'lim tillari
            url = LANGS_URL.format(un_id=un_id)
            get_langs = safe_get(session, url)
            sleep_rand()

            if not get_langs:
                log.warning(f"    Langs topilmadi: un_id={un_id}")
                continue

            for get_type in get_types:
                ty_id       = get_type["value"]
                ty_text     = get_type["text"]
                ty_disabled = get_type.get("disabled", "")
                ty_group    = get_type.get("group", "")
                ty_selected = get_type.get("selected", "")

                if conn:
                    with conn.cursor() as cur:
                        upsert_type(cur, region_id, un_id,
                                    ty_disabled, ty_group, ty_selected, ty_text, ty_id)
                    conn.commit()

                for get_lang in get_langs:
                    lan_id       = get_lang["value"]
                    lan_text     = get_lang["text"]
                    lan_disabled = get_lang.get("disabled", "")
                    lan_group    = get_lang.get("group", "")
                    lan_selected = get_lang.get("selected", "")

                    if conn:
                        with conn.cursor() as cur:
                            upsert_lang(cur, region_id, un_id, ty_id,
                                        lan_disabled, lan_group, lan_selected, lan_text, lan_id)
                        conn.commit()

                    # 5. Mandat ma'lumotlari
                    url = ALL_URL.format(
                        region_id=region_id,
                        un_id=un_id,
                        ty_id=ty_id,
                        lan_id=lan_id,
                    )
                    get_datas = safe_get(session, url)
                    sleep_rand()

                    if not get_datas:
                        continue

                    if conn:
                        with conn.cursor() as cur:
                            for item in get_datas:
                                upsert_mandat(
                                    cur,
                                    region_id, un_id, ty_id, lan_id,
                                    item.get("mvdir"),
                                    item.get("nomi"),
                                    item.get("gr_k", 0),
                                    item.get("con_k", 0),
                                    item.get("gr_b", 0.0),
                                    item.get("con_b", 0.0),
                                    item.get("olimp", 0),
                                )
                        conn.commit()
                        total_mandat += len(get_datas)

                    log.info(
                        f"      ty={ty_id} lan={lan_id} → {len(get_datas)} yo'nalish saqlandi"
                    )

        save_progress(region_id)
        log.info(f"  ✓ Region #{region_id} tugadi. Jami mandat: {total_mandat}")

    # Yakuniy hisobot
    log.info("=" * 60)
    log.info("✅ PARSE YAKUNLANDI")
    log.info(f"   O'tkazilgan regionlar (resume): {skipped}")
    log.info(f"   Jami saqlangan mandat yozuvlari: {total_mandat}")
    log.info("=" * 60)

    if conn:
        conn.close()

    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        log.info("Progress fayli o'chirildi.")


# ──────────────────────────── STATISTIKA ────────────────────────────

def print_stats():
    conn = get_conn()
    cur  = conn.cursor()
    print("\n📊 Baza statistikasi:")
    for table in ("regions", "universities", "gettypes", "getlangs", "mandat", "photos"):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table:<20}: {count:>8} ta yozuv")
        except Exception:
            print(f"  {table:<20}: jadval topilmadi")
    cur.close()
    conn.close()


# ──────────────────────────── ENTRY POINT ────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="mandat.uzbmb.uz — 2025 yil ma'lumotlarini yuklovchi va yangilovchi parser",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Misollar:
  python parse2025.py                 # Standart: mandat tozalanib 2025 yil yoziladi
  python parse2025.py --no-clean      # Tozalamasdan upsert (2024 yozuvlari qoladi)
  python parse2025.py --no-resume     # Progressni e'tiborsiz qoldirib boshidan
  python parse2025.py --dry-run       # Bazaga yozmaydi, faqat API ni tekshiradi
  python parse2025.py --stats         # Bazadagi statistikani chiqaradi
        """
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="mandat jadvalini tozalamasdan faqat upsert qiladi\n"
             "(2024 da bor, 2025 da yo'q yozuvlar bazada qoladi)"
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Progressni e'tiborsiz qoldirib boshidan boshlaydi"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Bazaga yozmaydi — faqat API so'rovlarini tekshiradi"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Bazadagi joriy statistikani chiqaradi"
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=DELAY_MIN,
        help=f"So'rovlar orasidagi minimal kutish (default: {DELAY_MIN}s)"
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=DELAY_MAX,
        help=f"So'rovlar orasidagi maksimal kutish (default: {DELAY_MAX}s)"
    )
    args = parser.parse_args()

    DELAY_MIN = args.delay_min
    DELAY_MAX = args.delay_max

    if args.stats:
        print_stats()
    else:
        parse(
            resume  = not args.no_resume,
            dry_run = args.dry_run,
            clean   = not args.no_clean,
        )