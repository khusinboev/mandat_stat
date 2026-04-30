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
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'mandat' AND column_name = 'year'
            ) THEN
                ALTER TABLE public.mandat ADD COLUMN year INTEGER;
            END IF;

            UPDATE public.mandat SET year = 2025 WHERE year IS NULL;
            ALTER TABLE public.mandat ALTER COLUMN year SET DEFAULT 2025;
            ALTER TABLE public.mandat ALTER COLUMN year SET NOT NULL;

            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'public.mandat'::regclass
                  AND conname = 'mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_key'
            ) THEN
                ALTER TABLE public.mandat
                DROP CONSTRAINT mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_key;
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'public.mandat'::regclass
                  AND conname = 'mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_year_key'
            ) THEN
                ALTER TABLE public.mandat
                ADD CONSTRAINT mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_year_key
                UNIQUE (region_id, un_id, ty_id, lan_id, mvdir, nomi, year);
            END IF;

            CREATE INDEX IF NOT EXISTS idx_mandat_region_un_ty_lan ON public.mandat (region_id, un_id, ty_id, lan_id);
            CREATE INDEX IF NOT EXISTS idx_mandat_ty_grb ON public.mandat (ty_id, gr_b);
            CREATE INDEX IF NOT EXISTS idx_mandat_ty_conb ON public.mandat (ty_id, con_b);
            CREATE INDEX IF NOT EXISTS idx_mandat_year_ty_grb ON public.mandat (year, ty_id, gr_b);
            CREATE INDEX IF NOT EXISTS idx_mandat_year_ty_conb ON public.mandat (year, ty_id, con_b);
            CREATE INDEX IF NOT EXISTS idx_mandat_lookup_with_year ON public.mandat (un_id, ty_id, lan_id, mvdir, nomi, year);
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

        -- accounts jadvaliga referral/limit kolonlari
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='accounts' AND column_name='msg_count') THEN
            ALTER TABLE public.accounts ADD COLUMN msg_count INTEGER NOT NULL DEFAULT 0;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='accounts' AND column_name='referral_count') THEN
            ALTER TABLE public.accounts ADD COLUMN referral_count INTEGER NOT NULL DEFAULT 0;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='accounts' AND column_name='referred_by') THEN
            ALTER TABLE public.accounts ADD COLUMN referred_by BIGINT;
        END IF;
        CREATE INDEX IF NOT EXISTS idx_accounts_referred_by ON public.accounts (referred_by);
    END $$;
    """)
    db.commit()

    sql.execute("""
    CREATE TABLE IF NOT EXISTS public.math (
        id SERIAL PRIMARY KEY,
        varyant VARCHAR(50) NOT NULL,
        answer VARCHAR(10) NOT NULL,
        file_id VARCHAR,
        status VARCHAR(20) DEFAULT 'True',
        photo VARCHAR,
        created_at TIMESTAMP DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS public.literature (
        id SERIAL PRIMARY KEY,
        varyant VARCHAR(50) NOT NULL,
        answer VARCHAR(10) NOT NULL,
        file_id VARCHAR,
        status VARCHAR(20) DEFAULT 'True',
        photo VARCHAR,
        created_at TIMESTAMP DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS public.history (
        id SERIAL PRIMARY KEY,
        varyant VARCHAR(50) NOT NULL,
        answer VARCHAR(10) NOT NULL,
        file_id VARCHAR,
        status VARCHAR(20) DEFAULT 'True',
        photo VARCHAR,
        created_at TIMESTAMP DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS public.results (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        math BOOLEAN DEFAULT FALSE,
        literature BOOLEAN DEFAULT FALSE,
        history BOOLEAN DEFAULT FALSE,
        number INTEGER DEFAULT 0,
        finished_at TIMESTAMP DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS public.quiz_import_state (
        id SERIAL PRIMARY KEY,
        source_db_name VARCHAR,
        import_type VARCHAR,
        source_data_hash VARCHAR,
        total_rows_imported INTEGER DEFAULT 0,
        status VARCHAR DEFAULT 'success',
        import_log TEXT,
        last_import_at TIMESTAMP DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_math_varyant_status ON public.math (varyant, status);
    CREATE INDEX IF NOT EXISTS idx_math_file_id ON public.math (file_id);
    CREATE INDEX IF NOT EXISTS idx_literature_varyant_status ON public.literature (varyant, status);
    CREATE INDEX IF NOT EXISTS idx_literature_file_id ON public.literature (file_id);
    CREATE INDEX IF NOT EXISTS idx_history_varyant_status ON public.history (varyant, status);
    CREATE INDEX IF NOT EXISTS idx_history_file_id ON public.history (file_id);
    CREATE INDEX IF NOT EXISTS idx_results_user_id ON public.results (user_id);
    CREATE INDEX IF NOT EXISTS idx_quiz_import_state_hash ON public.quiz_import_state (source_data_hash);
    """)
    db.commit()
