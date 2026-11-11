
"""add conversation ownership

Revision ID: fb6ac2911d75
Revises: f295c0eecf2a
"""

from alembic import op
import sqlalchemy as sa


revision = "fb6ac2911d75"
down_revision = "f295c0eecf2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("owner_id", sa.Integer(), nullable=True),
    )

    op.create_foreign_key(
        "fk_conversations_owner_id_users",
        "conversations",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        "ix_conversations_owner_id",
        "conversations",
        ["owner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversations_owner_id",
        table_name="conversations",
    )

    op.drop_constraint(
        "fk_conversations_owner_id_users",
        "conversations",
        type_="foreignkey",
    )

    op.drop_column("conversations", "owner_id")
