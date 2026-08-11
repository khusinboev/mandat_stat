# Arxiv

Loyihaning muntazam ishlashi uchun kerak bo'lmagan, lekin kelajakda foydali
bo'lib qolishi mumkin bo'lgan bir martalik skriptlar shu yerda saqlanadi
(o'chirilmaydi, faqat asosiy tuzilmadan chetlashtiriladi).

- `scripts/migrate_worker_images_to_savollar_db.py` — test_pdf_worker_base
  (gitignored, lokal) papkasidagi savol rasmlarini `src/db/savollar.db`ga
  bir martalik ko'chirish uchun yozilgan.
- `scripts/push_savollar_to_postgres.py` — `savollar.db` (SQLite)dan
  PostgreSQL'ga bir martalik import. Muntazam import uchun
  `scripts/import_quiz_data.py` ishlatiladi (CLAUDE.md'da hujjatlangan).
