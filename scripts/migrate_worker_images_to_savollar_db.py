from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "test_pdf_worker_base" / "output_images"
KEYS_FILE = ROOT / "test_pdf_worker_base" / "answer_keys" / "keys.json"
SQLITE_DB = ROOT / "src" / "db" / "savollar.db"

# User requested subject folders under src/handlers/users
USERS_SUBJECT_DIR = ROOT / "src" / "handlers" / "users"
# Runtime resolver in tests.py first checks src/handlers/users/images
USERS_IMAGES_DIR = ROOT / "src" / "handlers" / "users" / "images"

SUBJECT_MAP = {
    "literature": range(1, 11),
    "math": range(11, 21),
    "history": range(21, 31),
}


def max_existing_index(subject: str) -> int:
    # Keep continuity with existing numbering in src/handlers/users/<subject>
    base_dir = USERS_SUBJECT_DIR / subject
    max_idx = 0
    if base_dir.exists():
        for p in base_dir.glob("*.png"):
            stem = p.stem
            if stem.isdigit():
                max_idx = max(max_idx, int(stem))
    return max_idx


def ensure_dirs() -> None:
    for s in SUBJECT_MAP:
        (USERS_SUBJECT_DIR / s).mkdir(parents=True, exist_ok=True)
        (USERS_IMAGES_DIR / s).mkdir(parents=True, exist_ok=True)


def subject_for_q(q_no: int) -> str:
    for subject, rng in SUBJECT_MAP.items():
        if q_no in rng:
            return subject
    raise ValueError(f"Unexpected question number: {q_no}")


def get_next_variants(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.cursor()
    max_v = 0
    for table in ("math", "literature", "history"):
        cur.execute(f"SELECT COALESCE(MAX(varyant), 0) FROM {table}")
        max_v = max(max_v, int(cur.fetchone()[0] or 0))
    return {
        "1-test": max_v + 1,
        "2-test": max_v + 2,
        "3-test": max_v + 3,
    }


def main() -> None:
    ensure_dirs()

    with KEYS_FILE.open("r", encoding="utf-8") as f:
        keys = json.load(f)

    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    variant_map = get_next_variants(conn)
    subject_counter = {s: max_existing_index(s) for s in SUBJECT_MAP}

    inserts = {"literature": [], "math": [], "history": []}

    for test_name in ("1-test", "2-test", "3-test"):
        test_dir = WORKER / test_name / "question_blocks"
        if not test_dir.exists():
            raise FileNotFoundError(f"Missing source folder: {test_dir}")

        answers = keys[test_name].strip().upper()
        if len(answers) != 30:
            raise ValueError(f"Answer key for {test_name} is not 30 chars")

        varyant = variant_map[test_name]

        for q_no in range(1, 31):
            subject = subject_for_q(q_no)
            src_img = test_dir / f"q{q_no:02d}.png"
            if not src_img.exists():
                raise FileNotFoundError(f"Missing image: {src_img}")

            subject_counter[subject] += 1
            new_idx = subject_counter[subject]
            filename = f"{new_idx}.png"

            # 1) Requested subject folders under src/handlers/users/<subject>
            dst_subject = USERS_SUBJECT_DIR / subject / filename
            shutil.copy2(src_img, dst_subject)

            # 2) Runtime resolver folder src/handlers/users/images/<subject>
            dst_images = USERS_IMAGES_DIR / subject / filename
            shutil.copy2(src_img, dst_images)

            photo = f"{subject}/{filename}"
            answer = answers[q_no - 1]
            inserts[subject].append((photo, answer, None, varyant, "True"))

    for subject in ("literature", "math", "history"):
        cur.executemany(
            f"INSERT INTO {subject} (photo, answer, file_id, varyant, status) VALUES (?, ?, ?, ?, ?)",
            inserts[subject],
        )

    conn.commit()

    print("Migration completed")
    print("Inserted rows:")
    for subject in ("literature", "math", "history"):
        print(f"  {subject}: {len(inserts[subject])}")
    print("Variants used:")
    for t in ("1-test", "2-test", "3-test"):
        print(f"  {t} -> varyant {variant_map[t]}")
    print("Last indexes:")
    for subject in ("literature", "math", "history"):
        print(f"  {subject}: {subject_counter[subject]}")


if __name__ == "__main__":
    main()
