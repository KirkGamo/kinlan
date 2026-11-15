"""Push delivery: per-member push switches, alerts.pushed_at and Expo push tickets (#54).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-15 23:55:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Briefs section 5: outages, new devices and risky ports buzz by default; performance doesn't.
    for name, default in [
        ("push_outages", sa.true()),
        ("push_devices", sa.true()),
        ("push_security", sa.true()),
        ("push_performance", sa.false()),
    ]:
        op.add_column(
            "memberships", sa.Column(name, sa.Boolean(), server_default=default, nullable=False)
        )
    op.add_column("alerts", sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True))
    # Alerts raised before push existed are history, not news: never push them.
    op.execute("UPDATE alerts SET pushed_at = created_at")
    op.create_table(
        "push_tickets",
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("ticket_id", name=op.f("pk_push_tickets")),
    )
    op.create_index(
        "ix_alerts_unpushed",
        "alerts",
        ["created_at"],
        postgresql_where=sa.text("pushed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_unpushed", table_name="alerts")
    op.drop_table("push_tickets")
    op.drop_column("alerts", "pushed_at")
    for name in ["push_performance", "push_security", "push_devices", "push_outages"]:
        op.drop_column("memberships", name)
