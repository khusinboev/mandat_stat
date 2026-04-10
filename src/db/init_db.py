import logging
from config import db_connection

logger = logging.getLogger(__name__)


async def create_all_base():
    """Barcha kerakli jadvallarni yaratadi (agar mavjud bo'lmasa)."""
    with db_connection() as (conn, cur):
        # ── Foydalanuvchilar ──────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.accounts (
                id        SERIAL PRIMARY KEY,
                user_id   BIGINT NOT NULL UNIQUE,
                lang_code CHARACTER VARYING(10),
                date      TIMESTAMP DEFAULT now()
            )
        """)

        # user_id ga index (tezkor SELECT/CHECK uchun)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_user_id
            ON public.accounts (user_id)
        """)

        # ── Majburiy kanallar (1-guruh) ───────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.mandatorys (
                id       SERIAL PRIMARY KEY,
                chat_id  BIGINT NOT NULL UNIQUE,
                title    CHARACTER VARYING,
                username CHARACTER VARYING,
                types    CHARACTER VARYING
            )
        """)

        # ── Kanallar 2-guruh ──────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.kanallar2 (
                id       SERIAL PRIMARY KEY,
                chat_id  BIGINT NOT NULL UNIQUE,
                title    CHARACTER VARYING,
                username CHARACTER VARYING,
                types    CHARACTER VARYING
            )
        """)

        # ── Adminlar ──────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.admins (
                id      SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE,
                date    TIMESTAMP DEFAULT now()
            )
        """)

        # ── Mandat jadvallari (parse2025.py bilan mos) ────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.regions (
                id          SERIAL PRIMARY KEY,
                region_id   INTEGER UNIQUE,
                region_name VARCHAR UNIQUE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.universities (
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
            CREATE TABLE IF NOT EXISTS public.gettypes (
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
            CREATE TABLE IF NOT EXISTS public.getlangs (
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
            CREATE TABLE IF NOT EXISTS public.mandat (
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

        # mandat — tez-tez ishlatiladigan ustunlarga index
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_mandat_region_un
            ON public.mandat (region_id, un_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_mandat_gr_b
            ON public.mandat (gr_b) WHERE gr_b > 0
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_mandat_con_b
            ON public.mandat (con_b) WHERE con_b > 0
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.photos (
                id      SERIAL PRIMARY KEY,
                un_id   VARCHAR NOT NULL,
                ty_id   VARCHAR NOT NULL,
                lan_id  VARCHAR NOT NULL,
                mvdir   VARCHAR NOT NULL,
                file_id VARCHAR NOT NULL,
                UNIQUE (un_id, ty_id, lan_id, mvdir)
            )
        """)

    logger.info("Barcha jadvallar va indexlar tayyor.")


async def register_user(user_id: int, lang_code: str) -> bool:
    """
    Foydalanuvchini bazaga qo'shadi.
    Qaytaradi: True — yangi foydalanuvchi, False — allaqachon bor.
    """
    with db_connection() as (conn, cur):
        cur.execute(
            "SELECT 1 FROM public.accounts WHERE user_id = %s",
            (user_id,)
        )
        if cur.fetchone():
            return False  # Allaqachon ro'yxatdan o'tgan

        cur.execute(
            "INSERT INTO public.accounts (user_id, lang_code) VALUES (%s, %s)",
            (user_id, lang_code or "uz"),
        )
        return True