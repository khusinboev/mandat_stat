# Test Bazasini Kengaytirish - Integratsiya Qo'llanmasi

## Hozirgi Tuzilma

### Database Jadvallar
- `math` — Matematika savollari
- `literature` — Ona tili savollari
- `history` — O'zbekiston tarixi savollari

### Har Bir Jadvaldagi Ustunlar
```sql
id (SERIAL PRIMARY KEY)
varyant VARCHAR(50)         -- Savol varianti (1.A, 2.B, 3.C, ...)
answer VARCHAR(10)          -- To'g'ri javob (A, B, C, D)
file_id VARCHAR             -- File/image identifikatori
status VARCHAR(20)          -- Holati (True/False)
photo VARCHAR               -- Rasm yo'li/URL
created_at TIMESTAMP        -- Yaratilgan vaqti
```

### Testlar Qanday Ishlaydi
1. **SUBJECT_NAME_TO_CODE** mapping:
   - "Ona tili" → "literature"
   - "Matematika" → "math"
   - "O'zbekiston tarixi" → "history"

2. **Test Variantlar**:
   - Har bir test 30 ta savol bilan bo'lib, har bir savol A/B/C/D javobiga ega
   - `varyant` butun test variantini bildiradi: "1", "2", "3"
   - Javoblar "A", "B", "C", "D" formatida saqlanadi

## Yangi Test Integrasiya Strategiyasi

### Option 1: Mavjud Jadvallarga Qo'shish (TAVSIYA QILINGAN)

**Afzalliklar:**
- Minimal schema o'zgarish
- Iloji boricha osongina integratsiya
- Mavjud kodga yetakchi ta'sir yo'q

**Qadamlar:**
1. Jadvallarga `test_variant_id` va `image_path` ustunlari qo'shish
2. Manifest.csv fayllardan test ma'lumotlarini import qilish
3. Query'larni boshqarish (masalan, WHERE test_variant_id = 1)

### Option 2: Alohida Test Jadvallari Yaratish

**Afzalliklar:**
- Har bir test variant alohida jadvald
- Kengayish uchun yanada flex

**Jadvallar:**
- `test_1_questions` (Ona tili test 1)
- `test_2_questions` (Matematika test 2)
- `test_3_questions` (O'zbekiston tarixi test 3)

### Option 3: Test Metadata + Mapping Jadvali

**Afzalliklar:**
- Eng nufuzli yechim
- Multi-variant test'larni saqlash

**Jadvalllar:**
- `test_batches` — Test to'plamlari (id, subject, batch_name, created_at)
- `test_questions` — Savol markazi (id, batch_id, question_no, answer, image_path)
- `test_questions_variants` — Savol variantlari

## Tavsiya Qilingan Qadamlar

### 1. Jadval Sxemasini Kengaytirish (Alembic Migration)

```python
# Yangi ustunlar mavjud jadvallarga
ALTER TABLE public.math ADD COLUMN test_variant_id INT DEFAULT NULL;
ALTER TABLE public.literature ADD COLUMN test_variant_id INT DEFAULT NULL;
ALTER TABLE public.history ADD COLUMN test_variant_id INT DEFAULT NULL;
ALTER TABLE public.math ADD COLUMN image_path VARCHAR(255) DEFAULT NULL;
ALTER TABLE public.literature ADD COLUMN image_path VARCHAR(255) DEFAULT NULL;
ALTER TABLE public.history ADD COLUMN image_path VARCHAR(255) DEFAULT NULL;
```

### 2. Import Script Yozish

```python
# src/db/test_import.py
# Manifest.csv → Database
# - test_id → subject table tanlash
# - varyant → test papkasi/variant kodi (1, 2, 3)
# - question_no → question_number (1-30)
# - answer → javob (A-D)
# - image_path → image_path ustuni
```

### 3. Frontend'da Integratsiya

- Tests handler'da test_variant_id bilan filter qilish
- Image'lar CLI topish va qo'llanish

## Yoki Serverga Ko'chirish Uchun Qadamlar

1. **test_pdf_worker_base** → .gitignore ga qo'shish (amalga oshirilgan)
2. **Manifest CSV'larni** kengaytirilgan jadvalga import qilish
3. **Image'larni** statik papkaga nusxa qilish (masalan, `src/static/test_images/`)
4. **Test handler'ni** yangilab, test_variant_id bilan query qilish

## File Struktura

```
test_pdf_worker_base/
├── input_pdfs/              (3 ta PDF)
├── output_images/           (30×3 = 90 ta rasm)
│   ├── 1-test/
│   │   ├── question_blocks/
│   │   ├── manifest.csv
│   │   └── summary.json
│   ├── 2-test/
│   └── 3-test/
├── answer_keys/
│   └── keys.json
└── scripts/
    ├── process_pdf_tests.py (Main worker)
    └── requirements.txt
```

## Keyingi Bosqichlar

1. **Alembic Migration** yaratish
2. **Import script** yozish
3. **Test handler** yangilash
4. **Image hosting** qo'shish
5. **Server deployment**
