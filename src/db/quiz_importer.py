import hashlib
import json
import psycopg2
from psycopg2.extras import execute_values


QUIZ_TABLES = ("math", "literature", "history")
QUIZ_COLUMNS = ("varyant", "answer", "file_id", "status", "photo")


def _normalize_db_config(config: dict) -> dict:
    return {
        "dbname": config.get("dbname"),
        "user": config.get("user"),
        "password": config.get("password"),
        "host": config.get("host"),
        "port": config.get("port"),
    }


def _calc_source_hash(source_conn) -> tuple[str, dict]:
    cur = source_conn.cursor()
    payload = {}
    for table_name in QUIZ_TABLES:
        cur.execute(f"SELECT COUNT(*), COALESCE(MAX(id), 0) FROM public.{table_name}")
        count, max_id = cur.fetchone()
        payload[table_name] = {"count": int(count), "max_id": int(max_id)}

    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.md5(raw).hexdigest(), payload


def _fetch_rows(source_conn, table_name: str):
    cur = source_conn.cursor()
    cur.execute(
        f"SELECT varyant, answer, file_id, status, photo FROM public.{table_name} ORDER BY id"
    )
    return cur.fetchall()


def _insert_import_state(target_conn, source_db_name: str, import_type: str, source_hash: str,
                         total_rows: int, status: str, import_log: str):
    cur = target_conn.cursor()
    cur.execute(
        """
        INSERT INTO public.quiz_import_state
        (source_db_name, import_type, source_data_hash, total_rows_imported, status, import_log)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (source_db_name, import_type, source_hash, total_rows, status, import_log),
    )
    target_conn.commit()


async def import_quiz_data_from_source(
    *,
    target_conn,
    source_db_config: dict,
    skip_on_hash_match: bool = True,
) -> tuple[bool, str, int]:
    source_cfg = _normalize_db_config(source_db_config)
    source_conn = None

    source_db_name = source_cfg.get("dbname") or "unknown"
    try:
        source_conn = psycopg2.connect(**source_cfg)
        source_conn.autocommit = True

        source_hash, hash_payload = _calc_source_hash(source_conn)

        target_cur = target_conn.cursor()
        target_cur.execute(
            """
            SELECT source_data_hash
            FROM public.quiz_import_state
            WHERE status = 'success'
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = target_cur.fetchone()
        last_hash = row[0] if row else None

        if skip_on_hash_match and last_hash == source_hash:
            return True, "Quiz import skipped: source hash unchanged", 0

        all_rows = {}
        total_rows = 0
        for table_name in QUIZ_TABLES:
            rows = _fetch_rows(source_conn, table_name)
            all_rows[table_name] = rows
            total_rows += len(rows)

        target_cur.execute("TRUNCATE TABLE public.math, public.literature, public.history RESTART IDENTITY")
        target_conn.commit()

        for table_name, rows in all_rows.items():
            if not rows:
                continue
            execute_values(
                target_cur,
                f"INSERT INTO public.{table_name} (varyant, answer, file_id, status, photo) VALUES %s",
                rows,
                page_size=1000,
            )
        target_conn.commit()

        _insert_import_state(
            target_conn=target_conn,
            source_db_name=source_db_name,
            import_type="full_truncate",
            source_hash=source_hash,
            total_rows=total_rows,
            status="success",
            import_log=json.dumps(hash_payload, ensure_ascii=False),
        )
        return True, "Quiz import completed", total_rows

    except Exception as exc:
        if target_conn:
            try:
                _insert_import_state(
                    target_conn=target_conn,
                    source_db_name=source_db_name,
                    import_type="full_truncate",
                    source_hash="",
                    total_rows=0,
                    status="failed",
                    import_log=str(exc),
                )
            except Exception:
                pass
        return False, f"Quiz import failed: {exc}", 0
    finally:
        if source_conn:
            source_conn.close()
