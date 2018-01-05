# Copyright (C) 2017 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add test plan procedure to assessment

Create Date: 2018-01-05 10:59:47.258800
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

revision = '3198c7918360'
down_revision = '3911f39325b4'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.add_column(
      "assessments",
      sa.Column(
          "test_plan_procedure", sa.Boolean, nullable=False, default=True
      )
  )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  op.drop_column("assessments", "test_plan_procedure")
