"""add itniotech mode

Revision ID: 6d6d9a1f2f3a
Revises: fefdd1835b7d
Create Date: 2026-01-14 12:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
from alembic_postgresql_enum import TableReference

# revision identifiers, used by Alembic.
revision: str = "6d6d9a1f2f3a"
down_revision: Union[str, None] = "fefdd1835b7d"
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
            "itniotech",
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
