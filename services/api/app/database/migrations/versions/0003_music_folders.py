"""Persistent genre folders, without changing original audio metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0003_music_folders"
down_revision = "0002_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    folders = op.create_table(
        "music_folder",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_key", sa.String(), nullable=False, unique=True),
        sa.Column("genre", sa.String(), nullable=False),
    )
    op.create_table(
        "music_folder_entry",
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("media_asset.id"), primary_key=True),
        sa.Column("folder_id", sa.Integer(), sa.ForeignKey("music_folder.id"), nullable=False),
    )
    op.create_index("ix_music_folder_entry_folder_id", "music_folder_entry", ["folder_id"])
    op.bulk_insert(folders, [
        {"name": "Metalli", "name_key": "metalli", "genre": "metal"},
        {"name": "Elektroninen", "name_key": "elektroninen", "genre": "electronic"},
        {"name": "Country", "name_key": "country", "genre": "country"},
    ])


def downgrade() -> None:
    op.drop_table("music_folder_entry")
    op.drop_table("music_folder")
