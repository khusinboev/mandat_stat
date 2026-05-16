"""add bot_static_files table

Revision ID: 0002_bot_static_files
Revises: 0001_initial_mandat
Create Date: 2026-05-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_bot_static_files"
down_revision: Union[str, None] = "0001_initial_mandat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bot-specific static file cache: har bir bot instance o'z file_id larini
    # shu jadvalda saqlaydi. Hardcoded file_id boshqa botda ishlamasa,
    # bu jadvaldan bot o'z file_id sini oladi.
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.bot_static_files (
            key TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT now()
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.bot_static_files;")
