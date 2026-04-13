#!/usr/bin/env python3
"""
my_uzbmb_parser.py — my.uzbmb.uz saytidan universitet ma'lumotlarini 
yig'ib PostgreSQL ga yozuvchi parser (parse2025.py bilan bir xil baza strukturasi).

ISHLATISH:
    python my_uzbmb_parser.py                  # To'liq parse (0 dan)
    python my_uzbmb_parser.py --resume         # Oldingi progressdan davom
    python my_uzbmb_parser.py --dry-run        # Bazaga yozmasdan test
    python my_uzbmb_parser.py --stats          # Statistikani ko'rish
    python my_uzbmb_parser.py --no-clean       # Tozalamasdan upsert
"""

import os
import sys
import time
import random
import logging
import argparse
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# PostgreSQL
try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    psycopg2 = None

# ──────────────────────────── SOZLAMALAR ────────────────────────────

load_dotenv()

BASE_URL = "https://my.uzbmb.uz"

# Rate limiting
DELAY_MIN = 0.5
DELAY_MAX = 1.5
CONCURRENT_REQUESTS = 3

# Retry sozlamalari
MAX_RETRIES = 3
BACKOFF_FACTOR = 2

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("my_uzbmb_parser.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# Progress fayli
PROGRESS_FILE = "my_uzbmb_progress.txt"

# ──────────────────────────── DATABASE (parse2025.py bilan bir xil) ────────────────────────────

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "bmb"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "parol"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

def get_conn():
    """Bazaga ulanish."""
    if psycopg2 is None:
        raise ImportError("psycopg2 o'rnatilmagan: pip install psycopg2-binary")
    return psycopg2.connect(**DB_CONFIG)

def create_tables(conn):
    """Zarur jadvallarni yaratadi (agar mavjud bo'lmasa) - parse2025.py bilan bir xil."""
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
                year      INTEGER NOT NULL DEFAULT 2025,
                UNIQUE (region_id, un_id, ty_id, lan_id, mvdir, nomi, year)
            )
        """)
        cur.execute("""
            DO $$
            DECLARE
                legacy_con RECORD;
                legacy_idx RECORD;
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'mandat' AND column_name = 'year'
                ) THEN
                    ALTER TABLE public.mandat ADD COLUMN year INTEGER;
                END IF;

                UPDATE public.mandat SET year = 2025 WHERE year IS NULL;
                ALTER TABLE public.mandat ALTER COLUMN year SET DEFAULT 2025;
                ALTER TABLE public.mandat ALTER COLUMN year SET NOT NULL;

                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.mandat'::regclass
                      AND conname = 'mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_key'
                ) THEN
                    ALTER TABLE public.mandat DROP CONSTRAINT mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_key;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'public.mandat'::regclass
                      AND conname = 'mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_year_key'
                ) THEN
                    ALTER TABLE public.mandat
                    ADD CONSTRAINT mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_year_key
                    UNIQUE (region_id, un_id, ty_id, lan_id, mvdir, nomi, year);
                END IF;

                -- Legacy (year-siz) unique constraintlarni tozalash
                FOR legacy_con IN (
                    SELECT c.conname
                    FROM pg_constraint c
                    WHERE c.conrelid = 'public.mandat'::regclass
                      AND c.contype = 'u'
                      AND pg_get_constraintdef(c.oid) ILIKE 'UNIQUE (region_id, un_id, ty_id, lan_id, mvdir, nomi)%'
                      AND pg_get_constraintdef(c.oid) NOT ILIKE '%year%'
                ) LOOP
                    EXECUTE format('ALTER TABLE public.mandat DROP CONSTRAINT %I', legacy_con.conname);
                END LOOP;

                -- Legacy (year-siz) unique indexlarni tozalash
                FOR legacy_idx IN (
                    SELECT idx.relname AS index_name
                    FROM pg_index i
                    JOIN pg_class tbl ON tbl.oid = i.indrelid
                    JOIN pg_class idx ON idx.oid = i.indexrelid
                    WHERE tbl.relname = 'mandat'
                      AND i.indisunique = true
                      AND i.indisprimary = false
                      AND pg_get_indexdef(i.indexrelid) ILIKE '%(region_id, un_id, ty_id, lan_id, mvdir, nomi)%'
                      AND pg_get_indexdef(i.indexrelid) NOT ILIKE '%year%'
                ) LOOP
                    EXECUTE format('DROP INDEX IF EXISTS public.%I', legacy_idx.index_name);
                END LOOP;
            END
            $$;
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
    log.info("✓ Jadvallar tayyor (parse2025.py strukturasi).")

def clean_all_parser_tables(conn, drop_tables: bool = True):
    """Parser bilan bog'liq jadvallarni tozalaydi yoki butunlay qayta yaratadi."""
    with conn.cursor() as cur:
        if drop_tables:
            cur.execute("""
                DROP TABLE IF EXISTS photos CASCADE;
                DROP TABLE IF EXISTS mandat CASCADE;
                DROP TABLE IF EXISTS getlangs CASCADE;
                DROP TABLE IF EXISTS gettypes CASCADE;
                DROP TABLE IF EXISTS universities CASCADE;
                DROP TABLE IF EXISTS regions CASCADE;
            """)
        else:
            cur.execute("TRUNCATE TABLE photos, mandat, getlangs, gettypes, universities, regions RESTART IDENTITY")
    conn.commit()
    if drop_tables:
        log.info("✓ Parser jadvallari drop qilindi (0 dan qayta yaratiladi).")
    else:
        log.info("✓ Parser jadvallari to'liq tozalandi.")

# ──────────────────────────── PROGRESS ────────────────────────────

def load_progress() -> int:
    """Progressni o'qish (region_id sifatida)."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                return int(f.read().strip())
        except Exception:
            pass
    return 0

def save_progress(region_id: int):
    """Progressni saqlash."""
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(region_id))

def reset_progress():
    """Progressni tozalash."""
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        log.info("✓ Progress tozalandi")

# ──────────────────────────── UPSERT (parse2025.py bilan bir xil) ────────────────────────────

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
                  mvdir, nomi, gr_k, con_k, gr_b, con_b, olimp, year=2025):
    """Mandat ma'lumotlarini saqlash yoki yangilash."""
    cur.execute("""
        INSERT INTO mandat (region_id, un_id, ty_id, lan_id, mvdir, nomi, gr_k, con_k, gr_b, con_b, olimp, year)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (region_id, un_id, ty_id, lan_id, mvdir, nomi, year)
        DO UPDATE SET
            gr_k  = EXCLUDED.gr_k,
            con_k = EXCLUDED.con_k,
            gr_b  = EXCLUDED.gr_b,
            con_b = EXCLUDED.con_b,
            olimp = EXCLUDED.olimp
    """, (region_id, un_id, ty_id, lan_id, mvdir, nomi, gr_k, con_k, gr_b, con_b, olimp, year))

# ──────────────────────────── PARSER ────────────────────────────

class UzbmbParser:
    def __init__(self, dry_run: bool = False, resume: bool = False, clean: bool = True):
        self.dry_run = dry_run
        self.resume = resume
        self.clean = clean
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        self.conn = None if dry_run else get_conn()
        
        # Ta'lim shakli va tillar uchun ID counter
        self.type_ids = {}
        self.lang_ids = {}
        self.type_counter = 1
        self.lang_counter = 1

        if self.conn:
            if clean:
                clean_all_parser_tables(self.conn, drop_tables=True)
            create_tables(self.conn)

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uz-UZ,uz;q=0.9,ru;q=0.8",
            "Referer": f"{BASE_URL}/university/1",
        }

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers=self.headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        if self.conn:
            self.conn.close()

    async def fetch(self, url: str, retries: int = 0) -> Optional[str]:
        """URL dan HTML olish (retry bilan)."""
        async with self.semaphore:
            try:
                async with self.session.get(url) as resp:
                    if resp.status == 200:
                        await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                        return await resp.text()
                    elif resp.status == 429 and retries < MAX_RETRIES:
                        wait = BACKOFF_FACTOR ** (retries + 1)
                        log.warning(f"429 xato, {wait}s kutish... ({url})")
                        await asyncio.sleep(wait)
                        return await self.fetch(url, retries + 1)
                    else:
                        log.error(f"HTTP {resp.status}: {url}")
                        return None
            except Exception as e:
                if retries < MAX_RETRIES:
                    wait = BACKOFF_FACTOR ** (retries + 1)
                    log.warning(f"Xato: {e}, {wait}s kutish... ({url})")
                    await asyncio.sleep(wait)
                    return await self.fetch(url, retries + 1)
                log.error(f"Barcha urinishlar muvaffaqiyatsiz: {url}")
                return None

    def parse_regions(self, html: str) -> List[Dict[str, Any]]:
        """Viloyatlar ro'yxatini ajratib olish."""
        soup = BeautifulSoup(html, "lxml")
        regions = []

        for slide in soup.select(".bd-university-tkey"):
            data_id = slide.get("data-id", "")
            try:
                region_id = int(data_id.replace("bd-university-tab", ""))
            except ValueError:
                continue

            region_name = slide.get_text(strip=True)
            regions.append({
                "region_id": region_id,
                "region_name": region_name
            })

        return regions

    def parse_universities(self, html: str, region_id: int) -> List[Dict[str, Any]]:
        """Universitetlarni ajratib olish."""
        soup = BeautifulSoup(html, "lxml")
        unis = []

        tab = soup.find(
            lambda tag: tag.name == "div"
            and tag.get("data-id") == f"bd-university-tab{region_id}"
            and "bd-university-tab-content" in tag.get("class", [])
        )

        if not tab:
            # Debug: Qaysi data-id lar mavjud ekanligini ko'rish
            all_tabs = soup.find_all(
                lambda tag: tag.name == "div"
                and "bd-university-tab-content" in tag.get("class", [])
            )
            found_ids = [t.get("data-id") for t in all_tabs if t.get("data-id")]
            log.warning(f"[DEBUG] Region {region_id} uchun tab topilmadi. Mavjud data-id lar: {found_ids}")
            return unis

        for a in tab.select("a[href]"):
            badge = a.find("small", class_="badge")
            # Faqat Davlat universitetlari
            if not badge or badge.get_text(strip=True) != "Davlat":
                continue

            href = a["href"]
            try:
                uni_id = int(href.split("/")[-1])
            except (ValueError, IndexError):
                continue

            full_url = f"{BASE_URL}{href}"

            name_span = next(
                (s for s in a.find_all("span")
                 if not s.find("img") and not s.get("class") and s.get_text(strip=True)),
                None,
            )
            name = name_span.get_text(strip=True) if name_span else f"University {uni_id}"

            unis.append({
                "uni_id": uni_id,
                "name": name,
                "url": full_url,
                "region_id": region_id
            })

        return unis

    def get_type_id(self, edu_mode: str) -> str:
        """Ta'lim shakli uchun ID olish."""
        if not edu_mode:
            return "1"
        if edu_mode not in self.type_ids:
            self.type_ids[edu_mode] = str(self.type_counter)
            self.type_counter += 1
        return self.type_ids[edu_mode]

    def get_lang_id(self, edu_lang: str) -> str:
        """Ta'lim tili uchun ID olish."""
        if not edu_lang:
            return "1"
        if edu_lang not in self.lang_ids:
            self.lang_ids[edu_lang] = str(self.lang_counter)
            self.lang_counter += 1
        return self.lang_ids[edu_lang]

    def parse_directions_to_mandat(self, html: str, uni_id: int, region_id: int) -> List[Dict[str, Any]]:
        """Yo'nalishlarni parse2025.py mandat strukturasiga o'tkazish."""
        soup = BeautifulSoup(html, "lxml")
        mandat_items = []

        def dash_to_none(val):
            return None if val in (None, "-", "", "—") else val

        for card in soup.select("div.card_box"):
            key_str = card.get("data-key")
            try:
                direction_key = int(key_str)
            except (TypeError, ValueError):
                continue

            btn = card.select_one("button.accordion-button")
            if not btn:
                continue

            divs = btn.select("div > div")
            name = divs[0].get_text(strip=True) if len(divs) > 0 else None
            if not name:
                continue

            spans = btn.select("div > div:nth-child(2) span") if len(divs) > 1 else []
            edu_mode = spans[0].get_text(strip=True) if len(spans) > 0 else "Kunduzgi"
            edu_lang = spans[1].get_text(strip=True) if len(spans) > 1 else "O'zbek"

            # Ta'lim shakli va tili ID lari
            ty_id = self.get_type_id(edu_mode)
            lan_id = self.get_lang_id(edu_lang)

            body = card.select_one(".accordion-body")
            grant_count = 0
            contract_count = 0
            scores_by_year: Dict[int, Dict[str, float]] = {}
            olimp_count = 0

            if body:
                body_cols = body.select(".bd-accordion-table-body .col")
                if len(body_cols) >= 5:
                    grant_count_str = body_cols[1].get_text(strip=True).replace("Grand soni", "").strip()
                    contract_count_str = body_cols[2].get_text(strip=True).replace("Kontrakt soni", "").strip()

                    try:
                        grant_count = int(grant_count_str) if grant_count_str else 0
                    except ValueError:
                        grant_count = 0

                    try:
                        contract_count = int(contract_count_str) if contract_count_str else 0
                    except ValueError:
                        contract_count = 0

                # O'tish ballari (2025/2024/2023 mavjud bo'lsa alohida saqlaymiz)
                for table in body.select(".d-grid"):
                    headers = [h.get_text(strip=True) for h in table.select(".bd-accordion-table-header div")]
                    if "O'tish bali" not in headers:
                        continue

                    year_cols = []
                    for idx, h in enumerate(headers):
                        if h.isdigit():
                            y = int(h)
                            if 2023 <= y <= 2025:
                                year_cols.append((y, idx))
                                if y not in scores_by_year:
                                    scores_by_year[y] = {"gr_b": 0.0, "con_b": 0.0}

                    for row in table.select(".bd-accordion-table-body"):
                        cols = row.select("div")
                        if not cols:
                            continue

                        score_type_raw = cols[0].get_text(strip=True).replace("O'tish bali", "").strip().lower()

                        for year, year_idx in year_cols:
                            if year_idx >= len(cols):
                                continue

                            raw = cols[year_idx].get_text(strip=True).replace(str(year), "").strip()
                            raw = raw.replace(",", ".")
                            try:
                                score = float(raw)
                            except ValueError:
                                continue

                            if "grand" in score_type_raw:
                                scores_by_year[year]["gr_b"] = score
                            elif "kontrakt" in score_type_raw or "contract" in score_type_raw:
                                scores_by_year[year]["con_b"] = score

            if not scores_by_year:
                scores_by_year[2025] = {"gr_b": 0.0, "con_b": 0.0}

            for year in sorted(scores_by_year.keys(), reverse=True):
                mandat_items.append({
                    "region_id": region_id,
                    "un_id": str(uni_id),
                    "ty_id": ty_id,
                    "lan_id": lan_id,
                    "mvdir": direction_key,
                    "nomi": name,
                    "gr_k": grant_count,
                    "con_k": contract_count,
                    "gr_b": scores_by_year[year]["gr_b"],
                    "con_b": scores_by_year[year]["con_b"],
                    "olimp": olimp_count,
                    "edu_mode": edu_mode,
                    "edu_lang": edu_lang,
                    "year": year,
                })

        return mandat_items

    def get_total_pages(self, html: str) -> int:
        """Paginatsiya sonini aniqlash."""
        soup = BeautifulSoup(html, "lxml")
        pages = []
        for a in soup.select("ul#page-id li a"):
            try:
                pages.append(int(a.get_text(strip=True)))
            except ValueError:
                pass
        return max(pages) if pages else 1

    async def parse_university_directions(self, uni: Dict[str, Any], region_id: int):
        """Bitta universitetning barcha yo'nalishlarini parse qilish."""
        uni_id = uni['uni_id']
        uni_name = uni['name']

        log.info(f"  → Universitet: {uni_name[:60]} (ID: {uni_id})")

        # Universitetni saqlash (parse2025.py strukturasi)
        if self.conn:
            with self.conn.cursor() as cur:
                upsert_university(
                    cur, region_id, 
                    "false", "", "false", 
                    uni_name, str(uni_id)
                )
            self.conn.commit()

        # Birinchi sahifa
        url = f"{BASE_URL}/university-about-direction/{uni_id}?page=1"
        html = await self.fetch(url)

        if not html:
            log.error(f"    ✗ Sahifa yuklanmadi: {url}")
            return

        # Paginatsiya
        total_pages = self.get_total_pages(html)
        log.info(f"    Sahifalar: {total_pages}")

        # Birinchi sahifadagi yo'nalishlar
        mandat_items = self.parse_directions_to_mandat(html, uni_id, region_id)

        # Qolgan sahifalar
        for page in range(2, total_pages + 1):
            page_url = f"{BASE_URL}/university-about-direction/{uni_id}?page={page}"
            page_html = await self.fetch(page_url)
            if page_html:
                page_items = self.parse_directions_to_mandat(page_html, uni_id, region_id)
                mandat_items.extend(page_items)

        # Saqlash
        saved_count = 0
        if self.conn and mandat_items:
            with self.conn.cursor() as cur:
                # Ta'lim shakllarini va tillarni saqlash
                saved_types = set()
                saved_langs = set()
                
                for item in mandat_items:
                    # Type saqlash
                    type_key = (region_id, str(uni_id), item['edu_mode'], item['ty_id'])
                    if type_key not in saved_types:
                        upsert_type(
                            cur, region_id, str(uni_id),
                            "false", "", "false",
                            item['edu_mode'], item['ty_id']
                        )
                        saved_types.add(type_key)

                    # Lang saqlash
                    lang_key = (region_id, str(uni_id), item['ty_id'], item['edu_lang'], item['lan_id'])
                    if lang_key not in saved_langs:
                        upsert_lang(
                            cur, region_id, str(uni_id), item['ty_id'],
                            "false", "", "false",
                            item['edu_lang'], item['lan_id']
                        )
                        saved_langs.add(lang_key)

                    # Mandat saqlash
                    upsert_mandat(
                        cur,
                        item['region_id'],
                        item['un_id'],
                        item['ty_id'],
                        item['lan_id'],
                        item['mvdir'],
                        item['nomi'],
                        item['gr_k'],
                        item['con_k'],
                        item['gr_b'],
                        item['con_b'],
                        item['olimp'],
                        item.get('year', 2025),
                    )
                    saved_count += 1
            self.conn.commit()

        log.info(f"    ✓ {saved_count} ta yo'nalish saqlandi")

    async def parse_region(self, region: Dict[str, Any], last_region: int):
        """Bitta viloyatning barcha universitetlarini parse qilish."""
        region_id = region['region_id']
        region_name = region['region_name']

        if region_id <= last_region:
            log.info(f"[{region_id}] Viloyat '{region_name}' — o'tkazildi (progress)")
            return

        log.info(f"\n{'='*60}")
        log.info(f"📍 Viloyat: {region_name} (ID: {region_id})")
        log.info(f"{'='*60}")

        # Viloyatni saqlash
        if self.conn:
            with self.conn.cursor() as cur:
                upsert_region(cur, region_id, region_name)
            self.conn.commit()

        # Asosiy sahifani olish
        html = await self.fetch(f"{BASE_URL}/university/1")
        if not html:
            log.error(f"✗ Viloyat sahifasi yuklanmadi")
            return

        # Universitetlarni ajratish
        universities = self.parse_universities(html, region_id)
        log.info(f"  Topilgan universitetlar: {len(universities)}")

        # Har bir universitetni parse qilish
        for uni in universities:
            await self.parse_university_directions(uni, region_id)

        save_progress(region_id)
        log.info(f"  ✓ Viloyat #{region_id} tugadi")

    async def run(self):
        """Asosiy ish jarayoni."""
        log.info("🚀 Parser ishga tushdi (parse2025.py baza strukturasi)")
        log.info(f"   Dry run: {self.dry_run}")
        log.info(f"   Resume: {self.resume}")
        log.info(f"   Clean: {self.clean}")

        last_region = 0 if self.clean else (load_progress() if self.resume else 0)
        
        if self.clean:
            reset_progress()

        # Asosiy sahifa
        html = await self.fetch(f"{BASE_URL}/university/1")
        if not html:
            log.error("✗ Asosiy sahifa yuklanmadi!")
            return

        # Viloyatlarni olish
        regions = self.parse_regions(html)
        log.info(f"\n📊 Topilgan viloyatlar: {len(regions)}")

        total_mandat = 0

        # Har bir viloyat
        for region in regions:
            await self.parse_region(region, last_region)

        # Yakunlash
        log.info("\n" + "="*60)
        log.info("✅ PARSER YAKUNLANDI")
        log.info("="*60)

        if not self.dry_run:
            self.print_stats()

        # Progress tozalash
        reset_progress()

    def print_stats(self):
        """Statistikani chiqarish."""
        if not self.conn:
            return

        with self.conn.cursor() as cur:
            tables = ['regions', 'universities', 'gettypes', 'getlangs', 'mandat', 'photos']
            log.info("\n📊 STATISTIKA:")
            for table in tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cur.fetchone()[0]
                    log.info(f"  {table:<20}: {count:>6} ta")
                except Exception:
                    log.info(f"  {table:<20}: jadval topilmadi")

# ──────────────────────────── STATISTIKA ────────────────────────────

def print_stats():
    conn = get_conn()
    cur = conn.cursor()
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

def main():
    global DELAY_MIN, DELAY_MAX
    parser = argparse.ArgumentParser(
        description="my.uzbmb.uz parser (parse2025.py bilan bir xil baza strukturasi)",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Misollar:
    python my_uzbmb_parser.py              # Standart: jadvallarni tozalab 0 dan
    python my_uzbmb_parser.py --no-clean   # Tozalamasdan upsert
    python my_uzbmb_parser.py --resume     # Progressdan davom ettirish
    python my_uzbmb_parser.py --dry-run    # Bazaga yozmasdan test
    python my_uzbmb_parser.py --stats      # Statistikani ko'rish
        """
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Jadvallarni tozalamasdan faqat upsert qiladi"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Progressdan davom ettirish"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Bazaga yozmaydi — faqat test rejimi"
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
        async def run():
            async with UzbmbParser(
                dry_run=args.dry_run,
                resume=args.resume,
                clean=not args.no_clean
            ) as p:
                await p.run()
        asyncio.run(run())

if __name__ == "__main__":
    main()
