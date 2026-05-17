"""Add test_variant_id and image_path columns to quiz tables.

Revision ID: 0003_add_test_variant_support
Revises: 0002_add_bot_static_files
Create Date: 2026-05-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_add_test_variant_support"
down_revision: Union[str, None] = "0002_add_bot_static_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to math table
    op.add_column('math', sa.Column('test_variant_id', sa.Integer(), nullable=True))
    op.add_column('math', sa.Column('image_path', sa.String(255), nullable=True))
    op.add_column('math', sa.Column('question_number', sa.Integer(), nullable=True))

    # Add columns to literature table
    op.add_column('literature', sa.Column('test_variant_id', sa.Integer(), nullable=True))
    op.add_column('literature', sa.Column('image_path', sa.String(255), nullable=True))
    op.add_column('literature', sa.Column('question_number', sa.Integer(), nullable=True))

    # Add columns to history table
    op.add_column('history', sa.Column('test_variant_id', sa.Integer(), nullable=True))
    op.add_column('history', sa.Column('image_path', sa.String(255), nullable=True))
    op.add_column('history', sa.Column('question_number', sa.Integer(), nullable=True))

    # Create index for faster test_variant lookups
    op.create_index('idx_math_test_variant_id', 'math', ['test_variant_id'])
    op.create_index('idx_literature_test_variant_id', 'literature', ['test_variant_id'])
    op.create_index('idx_history_test_variant_id', 'history', ['test_variant_id'])


def downgrade() -> None:
    # Drop indices
    op.drop_index('idx_history_test_variant_id', table_name='history')
    op.drop_index('idx_literature_test_variant_id', table_name='literature')
    op.drop_index('idx_math_test_variant_id', table_name='math')

    # Drop columns from history table
    op.drop_column('history', 'question_number')
    op.drop_column('history', 'image_path')
    op.drop_column('history', 'test_variant_id')

    # Drop columns from literature table
    op.drop_column('literature', 'question_number')
    op.drop_column('literature', 'image_path')
    op.drop_column('literature', 'test_variant_id')

    # Drop columns from math table
    op.drop_column('math', 'question_number')
    op.drop_column('math', 'image_path')
    op.drop_column('math', 'test_variant_id')
