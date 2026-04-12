from aiogram import types
from config import db, sql


async def create_all_base():
    sql.execute("""CREATE TABLE IF NOT EXISTS public.accounts
    (
        id SERIAL NOT NULL,
        user_id BIGINT NOT NULL,
        lang_code CHARACTER VARYING(10),
        date TIMESTAMP DEFAULT now(),
        CONSTRAINT accounts_pkey PRIMARY KEY (id)
    )""")
    db.commit()
    sql.execute("CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON public.accounts (user_id)")
    db.commit()

    sql.execute("""CREATE TABLE IF NOT EXISTS public.mandatorys
    (
        id SERIAL NOT NULL,
        chat_id bigint NOT NULL,
        title character varying,
        username character varying,
        types character varying,
        CONSTRAINT channels_pkey PRIMARY KEY (id)
    )""")
    db.commit()


    sql.execute("""CREATE TABLE IF NOT EXISTS public.kanallar2
    (
        id SERIAL NOT NULL,
        chat_id bigint NOT NULL,
        title character varying,
        username character varying,
        types character varying,
        CONSTRAINT kanallar2_pkey PRIMARY KEY (id)
    )""")
    db.commit()

    sql.execute("""CREATE TABLE IF NOT EXISTS public.admins
    (
        id SERIAL NOT NULL,
        user_id BIGINT NOT NULL,
        date TIMESTAMP DEFAULT now(),
        CONSTRAINT admins_pkey PRIMARY KEY (id)
    )""")
    db.commit()

    # Legacy tables cleanup: no longer used by current bot flows.
    sql.execute("DROP TABLE IF EXISTS public.qualites")
    sql.execute("DROP TABLE IF EXISTS public.cinema")
    db.commit()

    # Optional performance indexes for parser-created tables.
    # These blocks are safe when tables are absent.
    sql.execute("""
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


class Authenticator:
    @staticmethod
    async def auth_user(message: types.Message):
        try:
            user_id = message.from_user.id
            username = message.from_user.username  if message.from_user.username else None
            lang_code = message.from_user.language_code if message.from_user.language_code else None

            sql.execute("SELECT user_id FROM accounts WHERE user_id = %s", (user_id,))
            check = sql.fetchone()
            if check is None:
                sql.execute("DELETE FROM public.accounts WHERE user_id = %s", (user_id,))
                db.commit()
                sql.execute("DELETE FROM public.user_langs WHERE user_id = %s", (user_id,))
                db.commit()
                sql.execute("DELETE FROM public.users_status WHERE user_id = %s", (user_id,))
                db.commit()
                sql.execute("DELETE FROM public.users_tts WHERE user_id = %s", (user_id,))
                db.commit()
                # sana = datetime.datetime.now(pytz.timezone('Asia/Tashkent')).strftime('%d-%m-%Y %H:%M')
                sql.execute(
                    "INSERT INTO accounts (user_id, username, lang_code) VALUES (%s, %s, %s)",
                    (user_id, username, lang_code),
                )
                db.commit()
        except: pass

    @staticmethod
    async def auth_group(message: types.Message):
        chat_id = message.chat.id
        group_type = message.chat.type
        sql.execute("SELECT chat_id FROM groups WHERE chat_id = %s", (chat_id,))
        check = sql.fetchone()
        if check is None:
            sql.execute("INSERT INTO groups (chat_id, types) VALUES (%s, %s)", (chat_id, group_type))
            db.commit()
