# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add issuetracker history table

Create Date: 2018-09-09 17:06:22.757113
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

revision = '1d7ae0031bc8'
down_revision = '9beabcd92f34'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.create_table(
      "issuetracker_sync_history",
      sa.Column("id", sa.Integer(), primary_key=True),
      sa.Column("bg_task_id", sa.Integer(), nullable=False),
      sa.Column("object_type", sa.String(250), nullable=False),
      sa.Column("object_id", sa.Integer(), nullable=False),
      sa.Column("result", sa.Boolean(), nullable=False),
      sa.Column("error", sa.String(250), nullable=True),
      sa.Column('modified_by_id', sa.Integer(), nullable=True),
      sa.Column('created_at', sa.DateTime()),
      sa.Column('updated_at', sa.DateTime()),
      sa.ForeignKeyConstraint(["bg_task_id"], ["background_tasks.id"],),
  )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  op.drop_table("issuetracker_sync_history")
