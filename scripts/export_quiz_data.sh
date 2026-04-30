#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/export_quiz_data.sh <source_db_name> <output_file.sql>
# Example:
#   ./scripts/export_quiz_data.sh ques_bot_db ./quiz_dump.sql

SOURCE_DB_NAME=${1:-}
OUTPUT_FILE=${2:-./quiz_dump.sql}

if [[ -z "${SOURCE_DB_NAME}" ]]; then
  echo "ERROR: source db name is required"
  echo "Usage: ./scripts/export_quiz_data.sh <source_db_name> <output_file.sql>"
  exit 1
fi

PGHOST=${PGHOST:-localhost}
PGPORT=${PGPORT:-5432}
PGUSER=${PGUSER:-postgres}

pg_dump \
  --host "${PGHOST}" \
  --port "${PGPORT}" \
  --username "${PGUSER}" \
  --format plain \
  --no-owner \
  --no-privileges \
  --table public.math \
  --table public.literature \
  --table public.history \
  --table public.results \
  --dbname "${SOURCE_DB_NAME}" \
  > "${OUTPUT_FILE}"

echo "Exported quiz tables to ${OUTPUT_FILE}"
