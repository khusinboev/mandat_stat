#!/usr/bin/env python3
"""
Quick Reference: Test Variant Integration

Yangi 90-test (3×30) ni loyihaga qo'shish uchun quyidagi amallarni bajarasiz:

STEP 1: Database Migratsiya
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
cd /home/adhambek/projects/pythons/mandat_stat
alembic upgrade head

STEP 2: Test Variantlarini Import Qilish  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
python -m src.db.test_variant_importer

# Yoki Python CLI'da:
from src.db.test_variant_importer import import_all_test_variants
results = import_all_test_variants()
print(results)

STEP 3: Frontend'da Qo'llash
━━━━━━━━━━━━━━━━━━━━━━━━━━━
from src.db.test_variant_importer import get_test_variant_questions

# Ona tili (1-test) ning barcha savollari
q1_all = get_test_variant_questions("literature", 1)

# Matematika (2-test) ning 5-savoli  
q2_5 = get_test_variant_questions("math", 2, 5)

# O'zbekiston tarixi (3-test) ning 10-savoli
q3_10 = get_test_variant_questions("history", 3, 10)

KEY INFO
━━━━━━━
Test Variant Mapping:
  1-test (Ona tili)        → literature table, variant_id=1
  2-test (Matematika)      → math table, variant_id=2
  3-test (O'zbekiston)     → history table, variant_id=3

Database `varyant` semantics:
  One value per paper variant ("1", "2", "3") reused across all 30 questions

Database Columns (YANGI):
  test_variant_id   : Test variant ID'si (1, 2, 3)
  image_path        : Rasm fayli yo'li
  question_number   : Savol raqami (1-30)

Generated Files:
  ✓ Alembic Migration: alembic/versions/0003_add_test_variant_support.py
  ✓ Import Script: src/db/test_variant_importer.py
  ✓ GitIgnore: test_pdf_worker_base/ qo'shildi
  ✓ Docs: TEST_INTEGRATION_GUIDE.md, TEST_SYSTEM_ARCHITECTURE.md
"""

if __name__ == "__main__":
    print(__doc__)
