"""DNS and web samples: the agent checks name lookup and HTTPS every few minutes (#96).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-29 04:00:00

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A new enum value can't be used in the transaction that adds it, so add them outside one.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE ping_target ADD VALUE IF NOT EXISTS 'dns'")
        op.execute("ALTER TYPE ping_target ADD VALUE IF NOT EXISTS 'web'")


def downgrade() -> None:
    # PostgreSQL can't drop an enum value, so the values stay; the rows that use them go.
    op.execute("DELETE FROM ping_hourly WHERE target::text IN ('dns', 'web')")
    op.execute("DELETE FROM ping_samples WHERE target::text IN ('dns', 'web')")
