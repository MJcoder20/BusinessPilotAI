
"""add supabase auth user mapping

Revision ID: aaf1a4e3c23b
Revises: 4c6544305081
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "aaf1a4e3c23b"
down_revision: Union[str, Sequence[str], None] = "4c6544305081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "supabase_user_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_unique_constraint(
        "uq_users_supabase_user_id",
        "users",
        ["supabase_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_users_supabase_user_id",
        "users",
        type_="unique",
    )

    op.drop_column("users", "supabase_user_id")
