
"""repair missing email verification fields

Revision ID: 4c6544305081
Revises: f213287b2a0c
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "4c6544305081"
down_revision: Union[str, Sequence[str], None] = "f213287b2a0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_context().as_sql:
        # These columns are created by the preceding migration.
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("users")
    }

    if "is_verified" not in existing_columns:
        op.add_column(
            "users",
            sa.Column(
                "is_verified",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            ),
        )

    if "verification_token_hash" not in existing_columns:
        op.add_column(
            "users",
            sa.Column(
                "verification_token_hash",
                sa.String(length=64),
                nullable=True,
            ),
        )

    if "verification_token_expires_at" not in existing_columns:
        op.add_column(
            "users",
            sa.Column(
                "verification_token_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )
def downgrade() -> None:
    # Keep the repaired columns to avoid accidentally losing user data.
    pass
