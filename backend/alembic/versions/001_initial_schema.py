"""Initial schema for TraceGuard: events, incidents, actions, evidence, agent_runs

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-10-31 14:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONType = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


def upgrade() -> None:
    # 1. Events table
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("seq", sa.Integer, autoincrement=True, unique=True, nullable=False),
        sa.Column("paypal_event_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("order_ref", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("payload", JSONType, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("prev_hash", sa.String(length=64), nullable=True),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_events_seq", "events", ["seq"])
    op.create_index("ix_events_paypal_event_id", "events", ["paypal_event_id"])
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_order_ref", "events", ["order_ref"])
    op.create_index("ix_events_resource_id", "events", ["resource_id"])
    op.create_index("ix_events_order_occurred", "events", ["order_ref", "occurred_at"])

    # 2. Incidents table
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("order_ref", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_incidents_order_ref", "incidents", ["order_ref"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_order_type", "incidents", ["order_ref", "type"])

    # 3. Actions table
    op.create_table(
        "actions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "incident_id",
            sa.String(length=64),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload", JSONType, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_actions_incident_id", "actions", ["incident_id"])
    op.create_index("ix_actions_status", "actions", ["status"])
    op.create_index("ix_actions_idempotency_key", "actions", ["idempotency_key"])

    # 4. Evidence table
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("order_ref", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_evidence_order_ref", "evidence", ["order_ref"])
    op.create_index("ix_evidence_order_kind", "evidence", ["order_ref", "kind"])

    # 5. Agent runs table
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "incident_id",
            sa.String(length=64),
            sa.ForeignKey("incidents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("steps", JSONType, nullable=False),
        sa.Column("tool_calls", JSONType, nullable=False),
        sa.Column("tokens_used", JSONType, nullable=False),
        sa.Column("claims", JSONType, nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("validation_errors", JSONType, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_runs_incident_id", "agent_runs", ["incident_id"])


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("evidence")
    op.drop_table("actions")
    op.drop_table("incidents")
    op.drop_table("events")
