"""
Test System Architecture Documentation

## Loyihaning Test Sistema Qo'llanmasi

### 1. Test Variantlar Tuzilmasi

Loyihada 3 ta asosiy test variant bor:
- Test 1: Ona tili (literature jadvalida)
- Test 2: Matematika (math jadvalida)  
- Test 3: O'zbekiston tarixi (history jadvalida)

Har bir test:
- 30 ta savol bilan
- A, B, C, D javob variantlari bilan
- Rasm formatida saqlanadi

### 2. Database Sxemasi (SO'NG)

```
math, literature, history tables:
├── id (SERIAL PRIMARY KEY)
├── varyant (VARCHAR) — Test varianti kodi ("1", "2", "3")
├── answer (VARCHAR) — To'g'ri javob ("A", "B", "C", "D")
├── file_id (VARCHAR) — Fayl identifikatori
├── status (VARCHAR) — Holati
├── photo (VARCHAR) — Rasm yo'li (masalan: /path/to/q01.png)
├── created_at (TIMESTAMP)
├── test_variant_id (INT) — Test varianti ID'si (1, 2, 3, ...)  [YANGI]
├── image_path (VARCHAR) — Rasm to'liq yo'li                   [YANGI]
└── question_number (INT) — Savol raqami (1-30)               [YANGI]
```

### 3. PDF Ishlab Chiqarishni Almashtirish

**Oldiy Tuzilma:**
```
test_pdf_worker_base/
├── input_pdfs/        — Kirish PDF'lari (gitignore'da)
├── output_images/     — Chiqarish rasmlar (gitignore'da)
├── answer_keys/       — Javob kalitlari
└── scripts/           — Ishlab chiqarish skriptlar
```

**Yangi Fayllar:**
- `process_pdf_tests.py` — PDF→Rasm konvertori
- `manifest.csv` — Savol+Javob+Rasm yo'li mapping

### 4. Integration Qadamlari

#### Qadam 1: Alembic Migratsiya Qo'llash
```bash
cd /home/adhambek/projects/pythons/mandat_stat
alembic upgrade head
```

Bu jadvallarga 3 ta yangi ustun qo'shadi:
- test_variant_id
- image_path
- question_number

#### Qadam 2: Test Variantlarini Import Qilish
```python
from src.db.test_variant_importer import import_all_test_variants
results = import_all_test_variants()
print(results)
```

Bu manifest.csv fayllardan ma'lumotlarni yuklaydi.

#### Qadam 3: Frontend'da Integratsiya
```python
from src.db.test_variant_importer import get_test_variant_questions

# 1-test (Ona tili) da 1-savol olish
questions = get_test_variant_questions("literature", variant_id=1, question_no=1)
# Natija:
# [{
#     'id': 1,
#     'varyant': '1',
#     'answer': 'A',
#     'photo': '/path/to/q01.png',
#     'question_number': 1
# }]
```

### 5. Yangi Qo'llash Usullari

#### Bitta Test Variantini Import Qilish
```python
from pathlib import Path
from src.db.test_variant_importer import import_test_variant

success, msg, count = import_test_variant(
    "1-test",
    manifest_path=Path("test_pdf_worker_base/output_images/1-test/manifest.csv")
)
print(f"Imported {count} questions: {msg}")
```

#### Barcha Test Variantlarini Import Qilish
```python
from src.db.test_variant_importer import import_all_test_variants

results = import_all_test_variants()
# Natija:
# {
#     "1-test": {"success": True, "message": "...", "rows_imported": 30},
#     "2-test": {"success": True, "message": "...", "rows_imported": 30},
#     "3-test": {"success": True, "message": "...", "rows_imported": 30}
# }
```

#### Test Savollari Olish
```python
from src.db.test_variant_importer import get_test_variant_questions

# Ima'erat (1-test) eshak savollari
questions = get_test_variant_questions("literature", variant_id=1)
# [
#     {'id': 1, 'varyant': '1', 'answer': 'A', 'photo': '...', 'question_number': 1},
#     {'id': 2, 'varyant': '2', 'answer': 'B', 'photo': '...', 'question_number': 2},
#     ...
# ]

# Bitta savol
question = get_test_variant_questions("literature", variant_id=1, question_no=5)
```

### 6. Handler'ni Yangilash

`src/handlers/users/tests.py` da test_variant_id bilan filter qilish:

```python
from src.db.test_variant_importer import get_test_variant_questions

# Ona tili test (1-test)
questions = get_test_variant_questions("literature", variant_id=1)

# Matematika test (2-test)  
questions = get_test_variant_questions("math", variant_id=2)

# O'zbekiston tarixi test (3-test)
questions = get_test_variant_questions("history", variant_id=3)
```

### 7. Production'ga Joylashtirish

1. **Alembic Migratsiya:**
   - `alembic upgrade head` qo'llash
   - Jadvallarga ustunlar qo'shilib, indexlar yaratiladi

2. **Rasmlarni Ko'chirish:**
   - `test_pdf_worker_base/output_images/` → server statik papkasiga
   - Masalan: `/var/www/static/test_images/`

3. **Manifest'larni Import Qilish:**
   - `import_all_test_variants()` qo'llash
   - Database'ga 90 ta savol qo'shilib, rasm yo'llari saqlanadi

4. **Handler'ni Yangilash:**
   - Test variant ID'si bilan database query'lar

### 8. File Manzillari

**Alembic Migratsiya:**
- [alembic/versions/0003_add_test_variant_support.py](alembic/versions/0003_add_test_variant_support.py)

**Import Skripti:**
- [src/db/test_variant_importer.py](src/db/test_variant_importer.py)

**Integratsiya Qo'llanmasi:**
- [TEST_INTEGRATION_GUIDE.md](TEST_INTEGRATION_GUIDE.md)

**GitIgnore Yangilama:**
- [.gitignore](.gitignore) → `test_pdf_worker_base/` qo'shildi

### 9. Ma'lumot Mapping

```
PDF Test Files (input)
    ↓
process_pdf_tests.py (extraction)
    ↓
output_images/{test_id}/manifest.csv
    ├── test_id: "1-test", "2-test", "3-test"
    ├── question_no: 1-30
    ├── answer: A, B, C, D
    └── image_path: q01.png, q02.png, ..., q30.png
    ↓
test_variant_importer.py (mapping)
    ├── 1-test → literature table, variant_id=1
    ├── 2-test → math table, variant_id=2
    └── 3-test → history table, variant_id=3
    ↓
Database Tables (output)
    └── {varyant, answer, photo, test_variant_id, question_number}
```

### 10. Foydalanish Misollar

```python
# Barcha 1-test savollarini olish
questions = get_test_variant_questions("literature", 1)
# 30 ta savol qayturadi

# 1-test ning 5-savolini olish
q5 = get_test_variant_questions("literature", 1, 5)
# Bitta savol qayturadi

# Savol rasmini ko'rsatish
img_path = q5[0]['photo']  # "/path/to/q05.png"
```

### 11. Debugging

Agar import qilinmagan bo'lsa:
```python
from pathlib import Path
from src.db.test_variant_importer import import_test_variant

# Alohida test'ni import qilish va xatolarni ko'rish
success, msg, count = import_test_variant("1-test", Path("test_pdf_worker_base/output_images/1-test/manifest.csv"))
print(f"Success: {success}")
print(f"Message: {msg}")
print(f"Count: {count}")
```
"""

# Integration Architecture for Test System
#
# Architecture Pattern:
# ├── PDF Source (1-test, 2-test, 3-test)
# ├── PDF Processing Worker (process_pdf_tests.py)
# ├── Question + Image Output (manifest.csv + q01.png ... q30.png)
# ├── Database Schema Update (Alembic Migration 0003)
# ├── Data Import Layer (test_variant_importer.py)
# └── Query / Frontend Integration (tests.py, handlers)
#
# Data Flow:
# 1. PDF files → process_pdf_tests.py (extraction)
# 2. Questions, images → manifest.csv (mapping)
# 3. manifest.csv → test_variant_importer → database tables
# 4. tests.py (handler) queries database with test_variant_id filter
#
# Test Variant IDs:
# - 1: Ona tili (literature table)
# - 2: Matematika (math table)
# - 3: O'zbekiston tarixi (history table)
