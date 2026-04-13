#!/usr/bin/env python3
"""
test_3regions.py — Faqat Farg'ona, Xorazm va Qoraqolpoq viloyatlarini
mavjud bazaga qo'shadigan test parser (jadvallarni tozalamasdan).

ISHLATISH:
    python test_3regions.py            # Uchala viloyatni parse qilish
    python test_3regions.py --dry-run  # Bazaga yozmasdan test
"""

import os
import sys
import random
import logging
import argparse
import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    psycopg2 = None

# ──────────────────────────── SOZLAMALAR ────────────────────────────

load_dotenv()

BASE_URL = "https://my.uzbmb.uz"

# Faqat shu uchta viloyat ID lari (logdagi ID lar)
TARGET_REGION_IDS = {1730, 1733, 1735}

# Rate limiting
ELAY_MIN = 0.5
DELAY_MAX = 1.5
CONCURRENT_REQUESTS = 3

# Retry sozlamalari
MAX_RETRIES = 5
BACKOFF_FACTOR = 3

# User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("test_3regions.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ──────────────────────────── DATABASE ────────────────────────────

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "bmb"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "parol"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

def get_conn():
    if psycopg2 is None:
        raise ImportError("psycopg2 o'rnatilmagan: pip install psycopg2-binary")
    return psycopg2.connect(**DB_CONFIG)

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

class ThreeRegionParser:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        self.conn = None if dry_run else get_conn()

        self.type_ids: Dict[str, str] = {}
        self.lang_ids: Dict[str, str] = {}
        self.type_counter = 1
        self.lang_counter = 1

    def get_random_headers(self):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "uz-UZ,uz;q=0.9,ru;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "no-cache",
            "Referer": f"{BASE_URL}/university/1",
        }

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60, connect=30, sock_read=30)
        connector = aiohttp.TCPConnector(
            limit_per_host=1,
            limit=1,
            ttl_dns_cache=300,
            ssl=True,
        )
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=self.get_random_headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(1)
        if self.conn:
            self.conn.close()

    async def fetch(self, url: str, retries: int = 0) -> Optional[str]:
        async with self.semaphore:
            try:
                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                headers = self.get_random_headers()
                async with self.session.get(url, headers=headers, allow_redirects=True, ssl=True) as resp:
                    if resp.status == 200:
                        return await resp.text()

                    elif resp.status == 400:
                        wait = BACKOFF_FACTOR ** (retries + 2) + random.uniform(1, 5)
                        if retries < MAX_RETRIES:
                            log.warning(f"HTTP 400: {url} — {wait:.1f}s kutish (urinish {retries + 1}/{MAX_RETRIES})")
                            await asyncio.sleep(wait)
                            return await self.fetch(url, retries + 1)
                        log.error(f"HTTP 400 (barcha urinishlar muvaffaqiyatsiz): {url}")
                        return None

                    elif resp.status == 429:
                        wait = BACKOFF_FACTOR ** (retries + 2) + random.uniform(2, 8)
                        if retries < MAX_RETRIES:
                            log.warning(f"HTTP 429 (rate limit): {url} — {wait:.1f}s kutish")
                            await asyncio.sleep(wait)
                            return await self.fetch(url, retries + 1)
                        log.error(f"HTTP 429: {url}")
                        return None

                    elif resp.status in (500, 502, 503, 504):
                        wait = BACKOFF_FACTOR ** (retries + 1) + random.uniform(1, 3)
                        if retries < MAX_RETRIES:
                            log.warning(f"HTTP {resp.status}: {url} — {wait:.1f}s kutish (urinish {retries + 1}/{MAX_RETRIES})")
                            await asyncio.sleep(wait)
                            return await self.fetch(url, retries + 1)
                        log.error(f"HTTP {resp.status}: {url}")
                        return None

                    else:
                        log.error(f"HTTP {resp.status}: {url}")
                        return None

            except asyncio.TimeoutError:
                wait = BACKOFF_FACTOR ** (retries + 1) + random.uniform(2, 5)
                if retries < MAX_RETRIES:
                    log.warning(f"Timeout: {url} — {wait:.1f}s kutish (urinish {retries + 1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait)
                    return await self.fetch(url, retries + 1)
                log.error(f"Timeout: {url}")
                return None

            except Exception as e:
                wait = BACKOFF_FACTOR ** (retries + 1) + random.uniform(1, 3)
                if retries < MAX_RETRIES:
                    log.warning(f"Xato {type(e).__name__}: {e} — {wait:.1f}s kutish (urinish {retries + 1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait)
                    return await self.fetch(url, retries + 1)
                log.error(f"Barcha urinishlar muvaffaqiyatsiz: {url}")
                return None

    def parse_regions(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        regions = []
        for slide in soup.select(".bd-university-tkey"):
            data_id = slide.get("data-id", "")
            try:
                region_id = int(data_id.replace("bd-university-tab", ""))
            except ValueError:
                continue
            if region_id not in TARGET_REGION_IDS:
                continue
            region_name = slide.get_text(strip=True)
            regions.append({"region_id": region_id, "region_name": region_name})
        return regions

    def parse_universities(self, html: str, region_id: int) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        unis = []

        tab = soup.find(
            lambda tag: tag.name == "div"
            and tag.get("data-id") == f"bd-university-tab{region_id}"
            and "bd-university-tab-content" in tag.get("class", [])
        )

        if not tab:
            all_tabs = soup.find_all(
                lambda tag: tag.name == "div"
                and "bd-university-tab-content" in tag.get("class", [])
            )
            found_ids = [t.get("data-id") for t in all_tabs if t.get("data-id")]
            log.warning(f"[DEBUG] Region {region_id} uchun tab topilmadi. Mavjud data-id lar: {found_ids}")
            return unis

        for a in tab.select("a[href]"):
            badge = a.find("small", class_="badge")
            if not badge or badge.get_text(strip=True) != "Davlat":
                continue
            href = a["href"]
            try:
                uni_id = int(href.split("/")[-1])
            except (ValueError, IndexError):
                continue
            name_span = next(
                (s for s in a.find_all("span")
                 if not s.find("img") and not s.get("class") and s.get_text(strip=True)),
                None,
            )
            name = name_span.get_text(strip=True) if name_span else f"University {uni_id}"
            unis.append({
                "uni_id": uni_id,
                "name": name,
                "url": f"{BASE_URL}{href}",
                "region_id": region_id,
            })
        return unis

    def get_type_id(self, edu_mode: str) -> str:
        if not edu_mode:
            return "1"
        if edu_mode not in self.type_ids:
            self.type_ids[edu_mode] = str(self.type_counter)
            self.type_counter += 1
        return self.type_ids[edu_mode]

    def get_lang_id(self, edu_lang: str) -> str:
        if not edu_lang:
            return "1"
        if edu_lang not in self.lang_ids:
            self.lang_ids[edu_lang] = str(self.lang_counter)
            self.lang_counter += 1
        return self.lang_ids[edu_lang]

    def get_total_pages(self, html: str) -> int:
        soup = BeautifulSoup(html, "lxml")
        pages = []
        for a in soup.select("ul#page-id li a"):
            try:
                pages.append(int(a.get_text(strip=True)))
            except ValueError:
                pass
        return max(pages) if pages else 1

    def parse_directions_to_mandat(self, html: str, uni_id: int, region_id: int) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        mandat_items = []

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
                            raw = cols[year_idx].get_text(strip=True).replace(str(year), "").strip().replace(",", ".")
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

    async def parse_university_directions(self, uni: Dict[str, Any], region_id: int):
        uni_id = uni["uni_id"]
        uni_name = uni["name"]
        log.info(f"  → Universitet: {uni_name[:60]} (ID: {uni_id})")

        if self.conn:
            with self.conn.cursor() as cur:
                upsert_university(cur, region_id, "false", "", "false", uni_name, str(uni_id))
            self.conn.commit()

        url = f"{BASE_URL}/university-about-direction/{uni_id}?page=1"
        html = await self.fetch(url)
        if not html:
            log.error(f"    ✗ Sahifa yuklanmadi: {url}")
            return

        total_pages = self.get_total_pages(html)
        log.info(f"    Sahifalar: {total_pages}")

        mandat_items = self.parse_directions_to_mandat(html, uni_id, region_id)

        for page in range(2, total_pages + 1):
            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            page_url = f"{BASE_URL}/university-about-direction/{uni_id}?page={page}"
            page_html = await self.fetch(page_url)
            if page_html:
                mandat_items.extend(self.parse_directions_to_mandat(page_html, uni_id, region_id))
            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        saved_count = 0
        if self.conn and mandat_items:
            with self.conn.cursor() as cur:
                saved_types: set = set()
                saved_langs: set = set()
                for item in mandat_items:
                    type_key = (region_id, str(uni_id), item["edu_mode"], item["ty_id"])
                    if type_key not in saved_types:
                        upsert_type(cur, region_id, str(uni_id), "false", "", "false", item["edu_mode"], item["ty_id"])
                        saved_types.add(type_key)

                    lang_key = (region_id, str(uni_id), item["ty_id"], item["edu_lang"], item["lan_id"])
                    if lang_key not in saved_langs:
                        upsert_lang(cur, region_id, str(uni_id), item["ty_id"], "false", "", "false", item["edu_lang"], item["lan_id"])
                        saved_langs.add(lang_key)

                    upsert_mandat(
                        cur,
                        item["region_id"], item["un_id"], item["ty_id"], item["lan_id"],
                        item["mvdir"], item["nomi"], item["gr_k"], item["con_k"],
                        item["gr_b"], item["con_b"], item["olimp"], item.get("year", 2025),
                    )
                    saved_count += 1
            self.conn.commit()

        log.info(f"    ✓ {saved_count} ta yo'nalish saqlandi")

    async def run(self):
        log.info("🚀 Test parser ishga tushdi (faqat 3 viloyat: Farg'ona, Xorazm, Qoraqolpoq)")
        log.info(f"   Dry run: {self.dry_run}")
        log.info(f"   Maqsadli region ID lar: {sorted(TARGET_REGION_IDS)}")

        # Asosiy sahifa (barcha viloyatlar va universitetlar shu sahifada)
        html = await self.fetch(f"{BASE_URL}/university/1")
        if not html:
            log.error("✗ Asosiy sahifa yuklanmadi!")
            return

        # Faqat TARGET_REGION_IDS dagi viloyatlarni filter qilish
        regions = self.parse_regions(html)
        log.info(f"📊 Topilgan maqsadli viloyatlar: {len(regions)}")

        if not regions:
            log.error("✗ Maqsadli viloyatlar topilmadi! data-id lar nomuvofiq bo'lishi mumkin.")
            return

        for i, region in enumerate(regions):
            region_id = region["region_id"]
            region_name = region["region_name"]

            log.info(f"\n{'='*60}")
            log.info(f"📍 Viloyat: {region_name} (ID: {region_id})")
            log.info(f"{'='*60}")

            if self.conn:
                with self.conn.cursor() as cur:
                    upsert_region(cur, region_id, region_name)
                self.conn.commit()

            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

            universities = self.parse_universities(html, region_id)
            log.info(f"  Topilgan universitetlar: {len(universities)}")

            for j, uni in enumerate(universities):
                await self.parse_university_directions(uni, region_id)
                if j < len(universities) - 1:
                    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

            log.info(f"  ✓ Viloyat #{region_id} tugadi")

            if i < len(regions) - 1:
                await asyncio.sleep(random.uniform(2, 4))

        log.info("\n" + "=" * 60)
        log.info("✅ TEST PARSER YAKUNLANDI")
        log.info("=" * 60)

        if not self.dry_run and self.conn:
            self.print_stats()

    def print_stats(self):
        with self.conn.cursor() as cur:
            tables = ["regions", "universities", "gettypes", "getlangs", "mandat"]
            log.info("\n📊 STATISTIKA:")
            for table in tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cur.fetchone()[0]
                    log.info(f"  {table:<20}: {count:>6} ta")
                except Exception:
                    log.info(f"  {table:<20}: jadval topilmadi")


# ──────────────────────────── ENTRY POINT ────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Farg'ona, Xorazm va Qoraqolpoq viloyatlari uchun test parser",
    )
    parser.add_argument("--dry-run", action="store_true", help="Bazaga yozmaydi — faqat test rejimi")
    args = parser.parse_args()

    async def run():
        async with ThreeRegionParser(dry_run=args.dry_run) as p:
            await p.run()

    asyncio.run(run())


if __name__ == "__main__":
    main()
