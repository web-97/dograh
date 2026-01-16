"""add livekit mode

Revision ID: c1d4b0a5d0bf
Revises: b79f19f68157
Create Date: 2026-01-17 00:59:00.000000

"""

from typing import Sequence, Union

from alembic import op
from alembic_postgresql_enum import TableReference

# revision identifiers, used by Alembic.
revision: str = "c1d4b0a5d0bf"
down_revision: Union[str, None] = "b79f19f68157"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.sync_enum_values(
        enum_schema="public",
        enum_name="workflow_run_mode",
        new_values=[
            "twilio",
            "vonage",
            "vobiz",
            "cloudonix",
            "livekit",
            "stasis",
            "webrtc",
            "smallwebrtc",
            "VOICE",
            "CHAT",
        ],
        affected_columns=[
            TableReference(
                table_schema="public", table_name="workflow_runs", column_name="mode"
            )
        ],
        enum_values_to_rename=[],
    )


def downgrade() -> None:
    op.sync_enum_values(
        enum_schema="public",
        enum_name="workflow_run_mode",
        new_values=[
            "twilio",
            "vonage",
            "vobiz",
            "cloudonix",
            "stasis",
            "webrtc",
            "smallwebrtc",
            "VOICE",
            "CHAT",
        ],
        affected_columns=[
            TableReference(
                table_schema="public", table_name="workflow_runs", column_name="mode"
            )
        ],
        enum_values_to_rename=[],
    )
