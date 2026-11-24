
"""add email verification fields

Revision ID: f213287b2a0c
Revises: fb6ac2911d75
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f213287b2a0c"
down_revision: Union[str, Sequence[str], None] = "fb6ac2911d75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_verified",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("verification_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "verification_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "verification_token_expires_at")
    op.drop_column("users", "verification_token_hash")
    op.drop_column("users", "is_verified")
