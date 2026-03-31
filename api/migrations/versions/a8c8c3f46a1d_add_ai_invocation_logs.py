"""add_ai_invocation_logs

Revision ID: a8c8c3f46a1d
Revises: 35c5c17fcff7
Create Date: 2026-03-31 20:35:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8c8c3f46a1d"
down_revision: Union[str, Sequence[str], None] = "35c5c17fcff7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_invocation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("requested_provider_name", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("prompt_key", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("fallback_reason", sa.Text(), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("review_reasons_json", sa.JSON(), nullable=True),
        sa.Column("evaluation_summary", sa.Text(), nullable=False),
        sa.Column("evaluation_checks_json", sa.JSON(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_invocation_logs_action_type"), "ai_invocation_logs", ["action_type"], unique=False)
    op.create_index(op.f("ix_ai_invocation_logs_claim_id"), "ai_invocation_logs", ["claim_id"], unique=False)
    op.create_index(op.f("ix_ai_invocation_logs_id"), "ai_invocation_logs", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_invocation_logs_id"), table_name="ai_invocation_logs")
    op.drop_index(op.f("ix_ai_invocation_logs_claim_id"), table_name="ai_invocation_logs")
    op.drop_index(op.f("ix_ai_invocation_logs_action_type"), table_name="ai_invocation_logs")
    op.drop_table("ai_invocation_logs")
