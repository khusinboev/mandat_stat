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

    sql.execute("""CREATE TABLE IF NOT EXISTS public.admins
    (
        id SERIAL NOT NULL,
        user_id BIGINT NOT NULL,
        date TIMESTAMP DEFAULT now(),
        CONSTRAINT admins_pkey PRIMARY KEY (id)
    )""")
    db.commit()

    sql.execute("""
    CREATE TABLE IF NOT EXISTS public.cinema(
            cinema_id INTEGER NOT NULL,
            cinema_name CHARACTER VARYING,
            cinema_url CHARACTER VARYING,
            date TIMESTAMP DEFAULT now(),
            CONSTRAINT cinema_pkey PRIMARY KEY (cinema_id)
        )""")
    db.commit()

    sql.execute("""
        CREATE TABLE IF NOT EXISTS public.qualites (
            id SERIAL PRIMARY KEY,
            cinema_id INTEGER NOT NULL,
            cinema_key VARCHAR NOT NULL,
            cinema_quality VARCHAR NOT NULL CHECK (cinema_quality IN ('low', 'medium', 'high')),
            CONSTRAINT fk_cinema FOREIGN KEY (cinema_id) REFERENCES public.cinema (cinema_id) ON DELETE CASCADE,
            CONSTRAINT unique_cinema_id_quality UNIQUE (cinema_id, cinema_quality)
        )
    """)
    db.commit()


class Authenticator:
    @staticmethod
    async def auth_user(message: types.Message):
        try:
            user_id = message.from_user.id
            username = message.from_user.username  if message.from_user.username else None
            lang_code = message.from_user.language_code if message.from_user.language_code else None

            sql.execute(f"""SELECT user_id FROM accounts WHERE user_id = {user_id}""")
            check = sql.fetchone()
            if check is None:
                sql.execute(f"DELETE FROM public.accounts WHERE user_id ='{user_id}'")
                db.commit()
                sql.execute(f"DELETE FROM public.user_langs WHERE user_id ='{user_id}'")
                db.commit()
                sql.execute(f"DELETE FROM public.users_status WHERE user_id ='{user_id}'")
                db.commit()
                sql.execute(f"DELETE FROM public.users_tts WHERE user_id ='{user_id}'")
                db.commit()
                # sana = datetime.datetime.now(pytz.timezone('Asia/Tashkent')).strftime('%d-%m-%Y %H:%M')
                sql.execute(f"INSERT INTO accounts (user_id, username, lang_code) "
                            f"VALUES ('{user_id}', '{username}', '{lang_code}')")
                db.commit()
        except: pass

    @staticmethod
    async def auth_group(message: types.Message):
        chat_id = message.chat.id
        group_type = message.chat.type
        sql.execute(f"""SELECT chat_id FROM groups WHERE chat_id = {chat_id}""")
        check = sql.fetchone()
        if check is None:
            sql.execute(f"""INSERT INTO groups (chat_id, types) VALUES ('{chat_id}', '{group_type}')""")
            db.commit()
