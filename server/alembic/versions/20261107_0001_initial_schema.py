"""Initial schema: every table in docs/KinLAN_Technical_Plan.md, Section 5.2.

Revision ID: 0001
Revises:
Create Date: 2026-11-07 17:23:03.796371

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# Each enum type is created once, before the tables that use it (role and ping_target are shared).
ROLE = postgresql.ENUM("owner", "admin", "viewer", name="role", create_type=False)
SITE_STATUS = postgresql.ENUM(
    "online", "degraded", "unreachable", "pending", name="site_status", create_type=False
)
COMMAND_STATUS = postgresql.ENUM(
    "pending", "running", "done", "failed", "expired", name="command_status", create_type=False
)
DEVICE_TYPE = postgresql.ENUM(
    "router",
    "computer",
    "laptop",
    "phone",
    "tv",
    "printer",
    "unknown",
    name="device_type",
    create_type=False,
)
OUTAGE_CAUSE = postgresql.ENUM("isp", "lan", "unknown", name="outage_cause", create_type=False)
DETECTED_BY = postgresql.ENUM("agent", "server", name="detected_by", create_type=False)
PING_TARGET = postgresql.ENUM("gateway", "internet", name="ping_target", create_type=False)
ENUMS = [ROLE, SITE_STATUS, COMMAND_STATUS, DEVICE_TYPE, OUTAGE_CAUSE, DETECTED_BY, PING_TARGET]

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "circles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_circles_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_circles")),
    )
    op.create_table(
        "push_tokens",
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_push_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token", name=op.f("pk_push_tokens")),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["replaced_by"],
            ["refresh_tokens.id"],
            name=op.f("fk_refresh_tokens_replaced_by_refresh_tokens"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)
    op.create_table(
        "invites",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("circle_id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("role", ROLE, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_by", sa.UUID(), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["circle_id"],
            ["circles.id"],
            name=op.f("fk_invites_circle_id_circles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["used_by"], ["users.id"], name=op.f("fk_invites_used_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invites")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_invites_code_hash")),
    )
    op.create_table(
        "memberships",
        sa.Column("circle_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", ROLE, nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["circle_id"],
            ["circles.id"],
            name=op.f("fk_memberships_circle_id_circles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_memberships_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("circle_id", "user_id", name=op.f("pk_memberships")),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"], unique=False)
    op.create_table(
        "sites",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("circle_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", SITE_STATUS, nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cidr", sa.String(length=43), nullable=True),
        sa.Column("gateway_ip", postgresql.INET(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["circle_id"],
            ["circles.id"],
            name=op.f("fk_sites_circle_id_circles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sites")),
    )
    op.create_index("ix_sites_circle_id", "sites", ["circle_id"], unique=False)
    op.create_table(
        "agents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("os", sa.String(length=80), nullable=True),
        sa.Column("version", sa.String(length=32), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name=op.f("fk_agents_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agents")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_agents_token_hash")),
    )
    op.create_table(
        "alert_settings",
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("loss_pct", sa.Float(), nullable=False),
        sa.Column("offline_seconds", sa.Integer(), nullable=False),
        sa.Column("notify_new_device", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_alert_settings_site_id_sites"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("site_id", name=op.f("pk_alert_settings")),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("subject_ref", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("acked_by", sa.UUID(), nullable=True),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["acked_by"], ["users.id"], name=op.f("fk_alerts_acked_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name=op.f("fk_alerts_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index(
        "ix_alerts_site_created",
        "alerts",
        ["site_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_table(
        "commands",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", COMMAND_STATUS, nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_commands_requested_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name=op.f("fk_commands_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commands")),
    )
    op.create_index("ix_commands_site_status", "commands", ["site_id", "status"], unique=False)
    op.create_table(
        "devices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("mac", sa.String(length=17), nullable=False),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("vendor", sa.String(length=120), nullable=True),
        sa.Column("device_type", DEVICE_TYPE, nullable=False),
        sa.Column("custom_name", sa.String(length=80), nullable=True),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("trusted", sa.Boolean(), nullable=False),
        sa.Column("baseline", sa.Boolean(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("online", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_devices_owner_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name=op.f("fk_devices_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        sa.UniqueConstraint("site_id", "mac", name="uq_devices_site_id_mac"),
    )
    op.create_table(
        "outages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cause", OUTAGE_CAUSE, nullable=False),
        sa.Column("detected_by", DETECTED_BY, nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name=op.f("fk_outages_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outages")),
    )
    op.create_index(
        "ix_outages_site_started",
        "outages",
        ["site_id", sa.literal_column("started_at DESC")],
        unique=False,
    )
    op.create_table(
        "pairing_codes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_pairing_codes_site_id_sites"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pairing_codes")),
    )
    op.create_table(
        "ping_hourly",
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("target", PING_TARGET, nullable=False),
        sa.Column("hour", sa.DateTime(timezone=True), nullable=False),
        sa.Column("avg_ms", sa.Float(), nullable=True),
        sa.Column("min_ms", sa.Float(), nullable=True),
        sa.Column("max_ms", sa.Float(), nullable=True),
        sa.Column("loss_pct", sa.Float(), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name=op.f("fk_ping_hourly_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("site_id", "target", "hour", name=op.f("pk_ping_hourly")),
    )
    op.create_table(
        "ping_samples",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("target", PING_TARGET, nullable=False),
        sa.Column("ip", postgresql.INET(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rtt_ms", sa.Float(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_ping_samples_site_id_sites"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ping_samples")),
    )
    op.create_index(
        "ix_ping_samples_site_target_ts",
        "ping_samples",
        ["site_id", "target", sa.literal_column("ts DESC")],
        unique=False,
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("range_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("range_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("pdf", sa.LargeBinary(), nullable=True),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_reports_requested_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name=op.f("fk_reports_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_table(
        "ingest_batches",
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_ingest_batches_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("batch_id", name=op.f("pk_ingest_batches")),
    )
    op.create_table(
        "ping_tests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column(
            "ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("sent", sa.Integer(), nullable=False),
        sa.Column("received", sa.Integer(), nullable=False),
        sa.Column("loss_pct", sa.Float(), nullable=False),
        sa.Column("min_ms", sa.Float(), nullable=True),
        sa.Column("avg_ms", sa.Float(), nullable=True),
        sa.Column("max_ms", sa.Float(), nullable=True),
        sa.Column("jitter_ms", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_ping_tests_device_id_devices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ping_tests")),
    )
    op.create_index(
        "ix_ping_tests_device_ts",
        "ping_tests",
        ["device_id", sa.literal_column("ts DESC")],
        unique=False,
    )
    op.create_table(
        "port_findings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("service", sa.String(length=40), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_port_findings_device_id_devices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_port_findings")),
        sa.UniqueConstraint("device_id", "port", name="uq_port_findings_device_id_port"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("port_findings")
    op.drop_index("ix_ping_tests_device_ts", table_name="ping_tests")
    op.drop_table("ping_tests")
    op.drop_table("ingest_batches")
    op.drop_table("reports")
    op.drop_index("ix_ping_samples_site_target_ts", table_name="ping_samples")
    op.drop_table("ping_samples")
    op.drop_table("ping_hourly")
    op.drop_table("pairing_codes")
    op.drop_index("ix_outages_site_started", table_name="outages")
    op.drop_table("outages")
    op.drop_table("devices")
    op.drop_index("ix_commands_site_status", table_name="commands")
    op.drop_table("commands")
    op.drop_index("ix_alerts_site_created", table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("alert_settings")
    op.drop_table("agents")
    op.drop_index("ix_sites_circle_id", table_name="sites")
    op.drop_table("sites")
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("invites")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("push_tokens")
    op.drop_table("circles")
    op.drop_table("users")
    bind = op.get_bind()
    for enum in reversed(ENUMS):
        enum.drop(bind, checkfirst=True)
