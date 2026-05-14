"""initial mandat schema

Revision ID: 0001_initial_mandat
Revises:
Create Date: 2026-05-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial_mandat"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "mandat"


def upgrade() -> None:
    # Ensure isolated schema exists.
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("lang_code", sa.String(length=10), nullable=True),
        sa.Column("date", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        sa.Column("msg_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("referral_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("referred_by", sa.BigInteger(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_accounts_user_id", "accounts", ["user_id"], unique=False, schema=SCHEMA)
    op.create_index("idx_accounts_referred_by", "accounts", ["referred_by"], unique=False, schema=SCHEMA)

    op.create_table(
        "mandatorys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("types", sa.String(), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        "kanallar2",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("types", sa.String(), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("date", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        "math",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("varyant", sa.String(length=50), nullable=False),
        sa.Column("answer", sa.String(length=10), nullable=False),
        sa.Column("file_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'True'"), nullable=True),
        sa.Column("photo", sa.String(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_math_varyant_status", "math", ["varyant", "status"], unique=False, schema=SCHEMA)
    op.create_index("idx_math_file_id", "math", ["file_id"], unique=False, schema=SCHEMA)

    op.create_table(
        "literature",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("varyant", sa.String(length=50), nullable=False),
        sa.Column("answer", sa.String(length=10), nullable=False),
        sa.Column("file_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'True'"), nullable=True),
        sa.Column("photo", sa.String(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_literature_varyant_status", "literature", ["varyant", "status"], unique=False, schema=SCHEMA)
    op.create_index("idx_literature_file_id", "literature", ["file_id"], unique=False, schema=SCHEMA)

    op.create_table(
        "history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("varyant", sa.String(length=50), nullable=False),
        sa.Column("answer", sa.String(length=10), nullable=False),
        sa.Column("file_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'True'"), nullable=True),
        sa.Column("photo", sa.String(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_history_varyant_status", "history", ["varyant", "status"], unique=False, schema=SCHEMA)
    op.create_index("idx_history_file_id", "history", ["file_id"], unique=False, schema=SCHEMA)

    op.create_table(
        "results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("math", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("literature", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("history", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("number", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_results_user_id", "results", ["user_id"], unique=False, schema=SCHEMA)

    op.create_table(
        "quiz_import_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("source_db_name", sa.String(), nullable=True),
        sa.Column("import_type", sa.String(), nullable=True),
        sa.Column("source_data_hash", sa.String(), nullable=True),
        sa.Column("total_rows_imported", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("status", sa.String(), server_default=sa.text("'success'"), nullable=True),
        sa.Column("import_log", sa.Text(), nullable=True),
        sa.Column("last_import_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_quiz_import_state_hash", "quiz_import_state", ["source_data_hash"], unique=False, schema=SCHEMA)

    # Preserve prior inline migration behavior for pre-existing reference tables.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('mandat.mandat') IS NOT NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'mandat' AND table_name = 'mandat' AND column_name = 'year'
                ) THEN
                    ALTER TABLE mandat.mandat ADD COLUMN year INTEGER;
                END IF;

                UPDATE mandat.mandat SET year = 2025 WHERE year IS NULL;
                ALTER TABLE mandat.mandat ALTER COLUMN year SET DEFAULT 2025;
                ALTER TABLE mandat.mandat ALTER COLUMN year SET NOT NULL;

                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'mandat.mandat'::regclass
                      AND conname = 'mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_key'
                ) THEN
                    ALTER TABLE mandat.mandat
                    DROP CONSTRAINT mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_key;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'mandat.mandat'::regclass
                      AND conname = 'mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_year_key'
                ) THEN
                    ALTER TABLE mandat.mandat
                    ADD CONSTRAINT mandat_region_id_un_id_ty_id_lan_id_mvdir_nomi_year_key
                    UNIQUE (region_id, un_id, ty_id, lan_id, mvdir, nomi, year);
                END IF;

                CREATE INDEX IF NOT EXISTS idx_mandat_region_un_ty_lan ON mandat.mandat (region_id, un_id, ty_id, lan_id);
                CREATE INDEX IF NOT EXISTS idx_mandat_ty_grb ON mandat.mandat (ty_id, gr_b);
                CREATE INDEX IF NOT EXISTS idx_mandat_ty_conb ON mandat.mandat (ty_id, con_b);
                CREATE INDEX IF NOT EXISTS idx_mandat_year_ty_grb ON mandat.mandat (year, ty_id, gr_b);
                CREATE INDEX IF NOT EXISTS idx_mandat_year_ty_conb ON mandat.mandat (year, ty_id, con_b);
                CREATE INDEX IF NOT EXISTS idx_mandat_lookup_with_year ON mandat.mandat (un_id, ty_id, lan_id, mvdir, nomi, year);
                CREATE INDEX IF NOT EXISTS idx_mandat_nomi_lower ON mandat.mandat (lower(nomi));
            END IF;

            IF to_regclass('mandat.regions') IS NOT NULL THEN
                CREATE INDEX IF NOT EXISTS idx_regions_name_lower ON mandat.regions (lower(region_name));
            END IF;

            IF to_regclass('mandat.universities') IS NOT NULL THEN
                CREATE INDEX IF NOT EXISTS idx_universities_text_lower ON mandat.universities (lower(un_text));
                CREATE INDEX IF NOT EXISTS idx_universities_region_unid ON mandat.universities (region_id, un_id);
            END IF;

            IF to_regclass('mandat.gettypes') IS NOT NULL THEN
                CREATE INDEX IF NOT EXISTS idx_gettypes_unid_lower_text ON mandat.gettypes (un_id, lower(ty_text));
            END IF;

            IF to_regclass('mandat.getlangs') IS NOT NULL THEN
                CREATE INDEX IF NOT EXISTS idx_getlangs_lanid_lower_text ON mandat.getlangs (lan_id, lower(lan_text));
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_index("idx_quiz_import_state_hash", table_name="quiz_import_state", schema=SCHEMA)
    op.drop_table("quiz_import_state", schema=SCHEMA)

    op.drop_index("idx_results_user_id", table_name="results", schema=SCHEMA)
    op.drop_table("results", schema=SCHEMA)

    op.drop_index("idx_history_file_id", table_name="history", schema=SCHEMA)
    op.drop_index("idx_history_varyant_status", table_name="history", schema=SCHEMA)
    op.drop_table("history", schema=SCHEMA)

    op.drop_index("idx_literature_file_id", table_name="literature", schema=SCHEMA)
    op.drop_index("idx_literature_varyant_status", table_name="literature", schema=SCHEMA)
    op.drop_table("literature", schema=SCHEMA)

    op.drop_index("idx_math_file_id", table_name="math", schema=SCHEMA)
    op.drop_index("idx_math_varyant_status", table_name="math", schema=SCHEMA)
    op.drop_table("math", schema=SCHEMA)

    op.drop_table("admins", schema=SCHEMA)
    op.drop_table("kanallar2", schema=SCHEMA)
    op.drop_table("mandatorys", schema=SCHEMA)

    op.drop_index("idx_accounts_referred_by", table_name="accounts", schema=SCHEMA)
    op.drop_index("idx_accounts_user_id", table_name="accounts", schema=SCHEMA)
    op.drop_table("accounts", schema=SCHEMA)
