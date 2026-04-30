import asyncio
import sys

from config import QUIZ_IMPORT_SKIP_ON_HASH_MATCH, QUIZ_SOURCE_DB_CONFIG, db
from src.db.quiz_importer import import_quiz_data_from_source


async def main():
    force = "--force" in sys.argv
    ok, msg, rows = await import_quiz_data_from_source(
        target_conn=db,
        source_db_config=QUIZ_SOURCE_DB_CONFIG,
        skip_on_hash_match=False if force else QUIZ_IMPORT_SKIP_ON_HASH_MATCH,
    )
    print(f"{msg} (rows={rows})")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
