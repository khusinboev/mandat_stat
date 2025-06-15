from config import sql, db


async def cinema_info_add(cinema_id: int, cinema_name: str, cinema_url: str):
    sql.execute("SELECT 1 FROM public.cinema WHERE cinema_id = %s", (cinema_id,))
    if sql.fetchone():
        raise ValueError(f"cinema_id {cinema_id} already exists")

    sql.execute("""
        INSERT INTO public.cinema (cinema_id, cinema_name, cinema_url)
        VALUES (%s, %s, %s)
    """, (cinema_id, cinema_name, cinema_url))
    db.commit()


async def cinema_add(cinema_id: int, cinema_key: str, cinema_quality: str):
    assert cinema_quality in ("low", "medium", "high"), "Noto'g'ri sifat qiymati"
    sql.execute("""
            INSERT INTO public.qualites (cinema_id, cinema_key, cinema_quality)
            VALUES (%s, %s, %s)
            ON CONFLICT (cinema_id, cinema_quality)
            DO UPDATE SET cinema_key = EXCLUDED.cinema_key
        """, (cinema_id, cinema_key, cinema_quality))
    db.commit()


async def cinema_delete(cinema_id: int) -> bool:
    try:
        sql.execute("SELECT 1 FROM public.cinema WHERE cinema_id = %s", (cinema_id,))
        exists = sql.fetchone()
        if not exists:
            print(f"Cinema ID {cinema_id} topilmadi.")
            return False

        sql.execute("DELETE FROM public.cinema WHERE cinema_id = %s", (cinema_id,))
        db.commit()
        print(f"Cinema ID {cinema_id} muvaffaqiyatli o‘chirildi.")
        return True

    except Exception as e:
        db.rollback()
        print(f"Xatolik yuz berdi: {e}")
        return False
