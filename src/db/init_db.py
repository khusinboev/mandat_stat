from config import db, sql


async def create_all_base():
    sql.execute("""
    CREATE TABLE IF NOT EXISTS public.accounts (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        lang_code VARCHAR(10),
        date TIMESTAMP DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON public.accounts (user_id);

    CREATE TABLE IF NOT EXISTS public.mandatorys (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        title VARCHAR,
        username VARCHAR,
        types VARCHAR
    );

    CREATE TABLE IF NOT EXISTS public.kanallar2 (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        title VARCHAR,
        username VARCHAR,
        types VARCHAR
    );

    CREATE TABLE IF NOT EXISTS public.admins (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        date TIMESTAMP DEFAULT now()
    );

    DO $$
    BEGIN
        IF to_regclass('public.mandat') IS NOT NULL THEN
            CREATE INDEX IF NOT EXISTS idx_mandat_region_un_ty_lan ON public.mandat (region_id, un_id, ty_id, lan_id);
            CREATE INDEX IF NOT EXISTS idx_mandat_ty_grb ON public.mandat (ty_id, gr_b);
            CREATE INDEX IF NOT EXISTS idx_mandat_ty_conb ON public.mandat (ty_id, con_b);
            CREATE INDEX IF NOT EXISTS idx_mandat_nomi_lower ON public.mandat (lower(nomi));
        END IF;

        IF to_regclass('public.regions') IS NOT NULL THEN
            CREATE INDEX IF NOT EXISTS idx_regions_name_lower ON public.regions (lower(region_name));
        END IF;

        IF to_regclass('public.universities') IS NOT NULL THEN
            CREATE INDEX IF NOT EXISTS idx_universities_text_lower ON public.universities (lower(un_text));
            CREATE INDEX IF NOT EXISTS idx_universities_region_unid ON public.universities (region_id, un_id);
        END IF;

        IF to_regclass('public.gettypes') IS NOT NULL THEN
            CREATE INDEX IF NOT EXISTS idx_gettypes_unid_lower_text ON public.gettypes (un_id, lower(ty_text));
        END IF;

        IF to_regclass('public.getlangs') IS NOT NULL THEN
            CREATE INDEX IF NOT EXISTS idx_getlangs_lanid_lower_text ON public.getlangs (lan_id, lower(lan_text));
        END IF;
    END $$;
    """)
    db.commit()
